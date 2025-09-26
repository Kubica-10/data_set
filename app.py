import os
import json
import csv
from flask import Flask, request, render_template, send_file, redirect, url_for, flash
import fitz  # PyMuPDF
import regex as re
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "supersecretkey"

# Configurações
UPLOAD_FOLDER = 'uploads'
OUTPUT_FOLDER = 'outputs'
ALLOWED_EXTENSIONS = {'pdf'}
MAX_BLOCK_SIZE = 5000  # Limite de caracteres por bloco

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['OUTPUT_FOLDER'] = OUTPUT_FOLDER

# Criar diretórios se não existirem
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)


def allowed_file(filename):
    """Verifica se o arquivo tem extensão permitida"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def extrair_texto_pdf(path):
    """Extrai texto de um arquivo PDF usando PyMuPDF"""
    doc = fitz.open(path)
    texto_total = ""
    paginas_textos = []
    
    for i, page in enumerate(doc):
        page_text = page.get_text()
        print(f"[PDF] Página {i+1}: {len(page_text)} caracteres")
        paginas_textos.append(page_text)
        texto_total += page_text + "\n\n"
    
    doc.close()
    return texto_total.strip(), paginas_textos


def extrair_capitulos(texto):
    """Extrai capítulos e versículos do texto bíblico"""
    versiculos = []
    livro_atual = None
    capitulo_atual = None

    print(f"[DEBUG] Texto recebido: {len(texto)} caracteres")
    
    # Padrões regex mais flexíveis
    capitulo_patterns = [
        re.compile(r"^([A-ZÁÀÂÃÉÊÍÓÔÕÚÇ\s]+)\s+(\d+)$", re.MULTILINE | re.IGNORECASE),  # "GÊNESIS 1"
        re.compile(r"^([A-ZÁÀÂÃÉÊÍÓÔÕÚÇ\s]+)\s+CAPÍTULO\s+(\d+)", re.MULTILINE | re.IGNORECASE),  # "GÊNESIS CAPÍTULO 1"
        re.compile(r"^CAPÍTULO\s+(\d+)", re.MULTILINE | re.IGNORECASE),  # "CAPÍTULO 1"
    ]
    
    versiculo_patterns = [
        re.compile(r"^(\d+)\s+(.+)", re.MULTILINE),  # "1 No princípio..."
        re.compile(r"^(\d+)\.?\s+(.+)", re.MULTILINE),  # "1. No princípio..."
        re.compile(r"(\d+)\s*[-–]\s*(.+)", re.MULTILINE),  # "1 - No princípio..."
    ]

    linhas = texto.splitlines()
    print(f"[DEBUG] Total de linhas: {len(linhas)}")
    
    # Primeira passagem: identificar possíveis capítulos
    for i, linha in enumerate(linhas[:20]):  # Mostra primeiras 20 linhas
        print(f"[DEBUG] Linha {i}: '{linha.strip()}'")
    
    i = 0
    while i < len(linhas):
        linha = linhas[i].strip()
        
        if not linha:  # Pula linhas vazias
            i += 1
            continue
        
        # Verifica se é um novo capítulo
        cap_encontrado = False
        for pattern in capitulo_patterns:
            cap_match = pattern.match(linha)
            if cap_match:
                if len(cap_match.groups()) == 2:
                    livro_atual = cap_match.group(1).strip().title()
                    capitulo_atual = int(cap_match.group(2))
                else:
                    capitulo_atual = int(cap_match.group(1))
                    if not livro_atual:
                        livro_atual = "Livro Desconhecido"
                
                print(f"[DEBUG] Capítulo encontrado: {livro_atual} {capitulo_atual}")
                cap_encontrado = True
                break
        
        if cap_encontrado:
            i += 1
            continue

        # Verifica se é um versículo
        vers_encontrado = False
        for pattern in versiculo_patterns:
            vers_match = pattern.match(linha)
            if vers_match and livro_atual and capitulo_atual is not None:
                try:
                    versiculo_num = int(vers_match.group(1))
                    versiculo_texto = vers_match.group(2).strip()
                    
                    # Continua lendo até o próximo versículo ou capítulo
                    j = i + 1
                    while j < len(linhas):
                        prox_linha = linhas[j].strip()
                        if not prox_linha:
                            j += 1
                            continue
                        
                        # Verifica se a próxima linha é um novo versículo ou capítulo
                        is_next_verse = any(p.match(prox_linha) for p in versiculo_patterns)
                        is_next_chapter = any(p.match(prox_linha) for p in capitulo_patterns)
                        
                        if is_next_verse or is_next_chapter:
                            break
                        
                        versiculo_texto += " " + prox_linha
                        j += 1

                    versiculos.append({
                        'livro': livro_atual,
                        'capitulo': capitulo_atual,
                        'versiculo': versiculo_num,
                        'texto': versiculo_texto.strip()
                    })
                    
                    print(f"[DEBUG] Versículo encontrado: {livro_atual} {capitulo_atual}:{versiculo_num}")
                    vers_encontrado = True
                    i = j
                    break
                except (ValueError, IndexError):
                    continue
        
        if not vers_encontrado:
            i += 1

    print(f"[DEBUG] Total de versículos extraídos: {len(versiculos)}")
    return versiculos


def dividir_blocos(versiculos, max_chars=MAX_BLOCK_SIZE):
    """Divide os versículos em blocos de tamanho limitado"""
    blocos = []
    bloco_atual = []
    tamanho_atual = 0

    for v in versiculos:
        texto = v['texto']
        tamanho_versiculo = len(texto)

        # Se adicionar este versículo exceder o limite, salva o bloco atual
        if tamanho_atual + tamanho_versiculo > max_chars and bloco_atual:
            blocos.append(bloco_atual)
            bloco_atual = []
            tamanho_atual = 0

        bloco_atual.append(v)
        tamanho_atual += tamanho_versiculo

    # Adiciona o último bloco se houver
    if bloco_atual:
        blocos.append(bloco_atual)

    return blocos


@app.route('/', methods=['GET', 'POST'])
def index():
    """Rota principal - upload e processamento de arquivos"""
    if request.method == 'POST':
        # Limpa diretórios de upload e output
        for f in os.listdir(UPLOAD_FOLDER):
            os.remove(os.path.join(UPLOAD_FOLDER, f))
        for f in os.listdir(OUTPUT_FOLDER):
            os.remove(os.path.join(OUTPUT_FOLDER, f))

        # Obtém arquivos enviados
        files = request.files.getlist('pdf_file')
        if not files or files[0].filename == '':
            flash("Nenhum arquivo selecionado.", "error")
            return redirect(request.url)

        todos_versiculos = []
        texto_completo = ""

        # Processa cada arquivo PDF
        for file in files:
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                filepath = os.path.join(UPLOAD_FOLDER, filename)
                file.save(filepath)
                
                print(f"[DEBUG] Processando arquivo: {filename}")
                
                # Extrai texto do PDF
                texto_pdf, _ = extrair_texto_pdf(filepath)

                if len(texto_pdf.strip()) == 0:
                    flash(f"O arquivo '{filename}' não contém texto extraível.", "error")
                    continue

                print(f"[DEBUG] Texto extraído: {len(texto_pdf)} caracteres")
                
                # Salva uma amostra do texto para debug
                debug_path = os.path.join(OUTPUT_FOLDER, f"debug_{filename}.txt")
                with open(debug_path, "w", encoding="utf-8") as f:
                    f.write(f"=== TEXTO EXTRAÍDO DE {filename} ===\n\n")
                    f.write(texto_pdf[:2000])  # Primeiros 2000 caracteres
                    f.write("\n\n=== FIM DA AMOSTRA ===")

                # Extrai versículos
                versiculos = extrair_capitulos(texto_pdf)
                if len(versiculos) == 0:
                    flash(f"Nenhum versículo detectado no arquivo '{filename}'. Verifique o formato do PDF.", "error")
                    # Mesmo assim, salva o texto bruto
                    texto_completo += f"--- Início do arquivo: {filename} ---\n\n" + texto_pdf + f"\n\n--- Fim do arquivo: {filename} ---\n\n"
                    continue

                print(f"[DEBUG] Versículos encontrados: {len(versiculos)}")
                todos_versiculos.extend(versiculos)
                texto_completo += f"--- Início do arquivo: {filename} ---\n\n" + texto_pdf + f"\n\n--- Fim do arquivo: {filename} ---\n\n"
            else:
                flash(f"Arquivo inválido: {file.filename}", "error")

        # Sempre salva o texto completo, mesmo sem versículos estruturados
        if texto_completo:
            txt_path = os.path.join(OUTPUT_FOLDER, "dataset_biblico.txt")
            with open(txt_path, "w", encoding="utf-8") as f:
                f.write(texto_completo)
            print(f"[DEBUG] Arquivo TXT salvo: {txt_path}")

        # Salva JSON e CSV apenas se houver versículos estruturados
        if len(todos_versiculos) > 0:
            json_path = os.path.join(OUTPUT_FOLDER, "dataset_biblico.json")
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(todos_versiculos, f, ensure_ascii=False, indent=2)
            print(f"[DEBUG] Arquivo JSON salvo: {json_path}")

            csv_path = os.path.join(OUTPUT_FOLDER, "dataset_biblico.csv")
            with open(csv_path, "w", encoding="utf-8", newline='') as f:
                writer = csv.DictWriter(f, fieldnames=['livro', 'capitulo', 'versiculo', 'texto'])
                writer.writeheader()
                for v in todos_versiculos:
                    writer.writerow(v)
            print(f"[DEBUG] Arquivo CSV salvo: {csv_path}")
            
            flash(f"✅ Dataset gerado com sucesso! {len(todos_versiculos)} versículos processados.", "success")
        else:
            flash("⚠️ Nenhum versículo foi detectado, mas o texto bruto foi salvo em formato TXT.", "info")

        return redirect(url_for('index'))

    return render_template('index.html')


@app.route('/download/<tipo>')
def download_dataset(tipo):
    """Rota para download dos datasets gerados"""
    arquivos_validos = {
        'txt': 'dataset_biblico.txt',
        'json': 'dataset_biblico.json',
        'csv': 'dataset_biblico.csv'
    }

    if tipo not in arquivos_validos:
        flash("Tipo de arquivo inválido.", "error")
        return redirect(url_for('index'))

    caminho = os.path.join(OUTPUT_FOLDER, arquivos_validos[tipo])
    if os.path.exists(caminho):
        return send_file(caminho, as_attachment=True)
    else:
        flash("⚠️ Arquivo não encontrado. Gere o dataset primeiro.", "error")
        return redirect(url_for('index'))


if __name__ == '__main__':
    app.run(debug=True)