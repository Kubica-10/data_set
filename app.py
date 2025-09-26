import os
import json
import pandas as pd
from flask import Flask, request, render_template, send_file, redirect, url_for, flash
import fitz  # PyMuPDF
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "supersecretkey"

UPLOAD_FOLDER = 'uploads'
OUTPUT_FOLDER = 'outputs'
ALLOWED_EXTENSIONS = {'pdf'}
MAX_BLOCK_SIZE = 5000

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['OUTPUT_FOLDER'] = OUTPUT_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def extrair_texto_pdf(path):
    doc = fitz.open(path)
    texto_total = ""
    for page in doc:
        texto_total += page.get_text() + "\n\n"
    doc.close()
    return texto_total.strip()

def gerar_versiculos(texto, livro):
    """
    Gera lista de registros com campos: livro, capitulo, versiculo, texto.
    Se o PDF não tiver versículos, retorna como único bloco.
    """
    versiculos = []
    linhas = texto.splitlines()
    capitulo_atual = 1
    versiculo_atual = 0

    for linha in linhas:
        linha = linha.strip()
        if not linha:
            continue
        versiculo_atual += 1
        versiculos.append({
            'livro': livro,
            'capitulo': capitulo_atual,
            'versiculo': versiculo_atual,
            'texto': linha
        })

    # Caso PDF esteja vazio ou só tenha linhas em branco
    if not versiculos:
        versiculos.append({
            'livro': livro,
            'capitulo': 1,
            'versiculo': 1,
            'texto': texto
        })

    return versiculos

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        # Limpar pastas
        for f in os.listdir(UPLOAD_FOLDER):
            os.remove(os.path.join(UPLOAD_FOLDER, f))
        for f in os.listdir(OUTPUT_FOLDER):
            os.remove(os.path.join(OUTPUT_FOLDER, f))

        files = request.files.getlist('pdf_file')
        if not files or files[0].filename == '':
            flash("Nenhum arquivo selecionado.", "error")
            return redirect(request.url)

        todos_versiculos = []
        texto_completo = ""

        for file in files:
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                upload_path = os.path.join(UPLOAD_FOLDER, filename)
                file.save(upload_path)

                texto_pdf = extrair_texto_pdf(upload_path)
                livro_nome = os.path.splitext(filename)[0]
                versiculos = gerar_versiculos(texto_pdf, livro_nome)
                todos_versiculos.extend(versiculos)
                texto_completo += f"--- {livro_nome} ---\n{texto_pdf}\n\n"

        # TXT
        txt_path = os.path.join(OUTPUT_FOLDER, "dataset.txt")
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(texto_completo)

        # JSON
        json_path = os.path.join(OUTPUT_FOLDER, "dataset.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(todos_versiculos, f, ensure_ascii=False, indent=2)

        # CSV
        csv_path = os.path.join(OUTPUT_FOLDER, "dataset.csv")
        df = pd.DataFrame(todos_versiculos)
        df.to_csv(csv_path, index=False, encoding="utf-8")

        # PARQUET
        parquet_path = os.path.join(OUTPUT_FOLDER, "dataset.parquet")
        df.to_parquet(parquet_path, index=False)

        flash(f"✅ Dataset gerado com sucesso! {len(todos_versiculos)} registros.", "success")
        return redirect(url_for('index'))

    return render_template('index.html')

@app.route('/download/<tipo>')
def download_dataset(tipo):
    arquivos_validos = {
        'txt': 'dataset.txt',
        'json': 'dataset.json',
        'csv': 'dataset.csv',
        'parquet': 'dataset.parquet'
    }
    if tipo not in arquivos_validos:
        flash("Tipo de arquivo inválido.", "error")
        return redirect(url_for('index'))

    caminho = os.path.join(OUTPUT_FOLDER, arquivos_validos[tipo])
    if os.path.exists(caminho):
        return send_file(caminho, as_attachment=True)
    else:
        flash("Arquivo não encontrado.", "error")
        return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)
