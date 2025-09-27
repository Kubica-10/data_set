import os
import json
import re
import pandas as pd
from flask import Flask, request, render_template, send_file, redirect, url_for, flash, session
import fitz  # PyMuPDF
from werkzeug.utils import secure_filename
from datetime import datetime

app = Flask(__name__)
app.secret_key = "supersecretkey"
app.config['SESSION_TYPE'] = 'filesystem'

UPLOAD_FOLDER = 'uploads'
OUTPUT_FOLDER = 'outputs'
ALLOWED_EXTENSIONS = {'pdf'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['OUTPUT_FOLDER'] = OUTPUT_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def extrair_texto_por_linhas(path):
    """Extrai texto linha por linha, mantendo a ordem original"""
    try:
        doc = fitz.open(path)
        texto_completo = []
        
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            text = page.get_text()
            
            linhas = text.split('\n')
            for linha_num, linha in enumerate(linhas, 1):
                linha_limpa = linha.strip()
                if linha_limpa:
                    texto_completo.append({
                        'pagina': page_num + 1,
                        'linha_global': len(texto_completo) + 1,
                        'linha_pagina': linha_num,
                        'texto': linha_limpa
                    })
        
        doc.close()
        return texto_completo
    except Exception as e:
        print(f"Erro ao extrair texto: {e}")
        return []

class ClassificadorTexto:
    """Classifica textos de forma inteligente para qualquer tipo de PDF"""
    
    def __init__(self):
        self.padroes_metadados = [
            r'^\d{1,4}$',  # Apenas números (páginas, códigos)
            r'^[©Ⓒⓒ]',    # Símbolos de copyright
            r'(?i)(copyright|editora|publicações|tradução|versão|edição|impressão)',
            r'(?i)(página|page|\bpg\.|\bpp?\.)',
            r'(?i)(www\.|http|\.com|\.br|\.org)',
            r'(?i)(todos os direitos reservados|all rights reserved)',
            r'^[IVXLCDM]+$',  # Números romanos
        ]
        
        self.padroes_biblia = [
            r'^(\d+)[:\.](\d+)',  # 1:1, 1.1
            r'^(\d+)\s+[A-Za-zÀ-ÿ]',  # 1 Texto
            r'(?i)(gênesis|êxodo|levítico|números|deuteronômio|josué|juízes|rute|'
            r'samuel|reis|crônicas|esdras|neemias|ester|jó|salmos|provérbios|'
            r'eclesiastes|cânticos|isaías|jeremias|lamentações|ezequiel|daniel|'
            r'oséias|joel|amós|obadias|jonas|miquéias|naum|habacuque|sofonias|'
            r'ageu|zacarias|malaquias|mateus|marcos|lucas|joão|atos|romanos|'
            r'coríntios|gálatas|efésios|filipenses|colossenses|tessalonicenses|'
            r'timóteo|tito|filemom|hebreus|tiago|pedro|judas|apocalipse)'
        ]
        
        self.palavras_metadados = [
            'copyright', 'editora', 'publicações', 'tradução', 'versão', 'edição',
            'página', 'page', 'bvbooks', 'king james', 'bkj', 'livro', 'índice',
            'sumário', 'capítulo', 'www.', 'http', 'https', '.com', '.br', '.org',
            'all rights reserved', 'todos os direitos reservados'
        ]

    def classificar_linha(self, texto, contexto_anterior=None):
        """Classifica uma linha de texto"""
        texto_lower = texto.lower()
        
        # 1. Verifica se é metadado
        if self._eh_metadado(texto):
            return 'metadado'
        
        # 2. Verifica se é estrutura bíblica
        if self._eh_estrutura_biblica(texto):
            return 'estrutura_biblica'
        
        # 3. Verifica se é conteúdo bíblico (baseado no contexto)
        if contexto_anterior == 'estrutura_biblica' or self._eh_conteudo_biblico(texto):
            return 'conteudo_biblico'
        
        # 4. Verifica se é título ou cabeçalho
        if self._eh_titulo(texto):
            return 'titulo'
        
        # 5. Padrão geral de conteúdo
        return 'conteudo'

    def _eh_metadado(self, texto):
        """Verifica se é metadado"""
        if len(texto.strip()) < 3:
            return True
            
        if texto.strip().isdigit() and len(texto.strip()) < 5:
            return True
            
        if any(re.search(padrao, texto, re.IGNORECASE) for padrao in self.padroes_metadados):
            return True
            
        if any(palavra in texto.lower() for palavra in self.palavras_metadados):
            return True
            
        return False

    def _eh_estrutura_biblica(self, texto):
        """Verifica se é estrutura bíblica (livro, capítulo, versículo)"""
        # Padrões de versículos
        if re.match(r'^\d+[:\.]\d+', texto):  # 1:1, 1.1
            return True
        if re.match(r'^\s*\d+\s+[A-Za-zÀ-ÿ]', texto):  # 1 Texto
            return True
        
        # Nomes de livros (curtos e específicos)
        if len(texto) < 50 and any(re.search(padrao, texto, re.IGNORECASE) for padrao in self.padroes_biblia[2:]):
            return True
            
        return False

    def _eh_conteudo_biblico(self, texto):
        """Verifica se é conteúdo bíblico"""
        palavras_biblicas = ['jesus', 'cristo', 'deus', 'senhor', 'espírito', 'santo', 
                           'fé', 'graça', 'amém', 'aleluia', 'bíblia', 'evangelho']
        
        if any(palavra in texto.lower() for palavra in palavras_biblicas):
            return True
            
        if len(texto) > 30 and any(caract in texto for caract in [',', '.', ';', ':']):
            return True
            
        return False

    def _eh_titulo(self, texto):
        """Verifica se é título"""
        if len(texto) < 100 and (texto.isupper() or texto.istitle()):
            return True
        return False

def processar_pdf_universal(texto_linhas, arquivo_nome):
    """Processa qualquer PDF de forma inteligente"""
    classificador = ClassificadorTexto()
    registros = []
    contexto_anterior = None
    
    for i, linha in enumerate(texto_linhas):
        texto = linha['texto']
        
        # Classifica a linha atual
        tipo = classificador.classificar_linha(texto, contexto_anterior)
        
        # Atualiza contexto para próxima linha
        contexto_anterior = tipo if tipo != 'metadado' else contexto_anterior
        
        # Ignora metadados completamente
        if tipo == 'metadado':
            continue
        
        # Para estrutura bíblica, tenta extrair informações
        if tipo == 'estrutura_biblica':
            info_estrutura = extrair_info_estrutura_biblica(texto)
            registro = {
                'arquivo': arquivo_nome,
                'pagina': linha['pagina'],
                'linha_global': linha['linha_global'],
                'linha_pagina': linha['linha_pagina'],
                'tipo': tipo,
                'texto': texto
            }
            registro.update(info_estrutura)
            registros.append(registro)
        else:
            # Para outros tipos, registro simples
            registros.append({
                'arquivo': arquivo_nome,
                'pagina': linha['pagina'],
                'linha_global': linha['linha_global'],
                'linha_pagina': linha['linha_pagina'],
                'tipo': tipo,
                'texto': texto
            })
    
    return registros

def extrair_info_estrutura_biblica(texto):
    """Extrai informações de estrutura bíblica quando possível"""
    info = {}
    
    # Tenta extrair livro, capítulo e versículo
    match = re.match(r'^(\d+)[:\.](\d+)\s*(.*)$', texto)
    if match:
        info['capitulo'] = int(match.group(1))
        info['versiculo'] = int(match.group(2))
        info['texto_versiculo'] = match.group(3)
        return info
    
    match = re.match(r'^([A-Za-zÀ-ÿ\s]+)\s+(\d+)$', texto)
    if match:
        info['livro'] = match.group(1).strip()
        info['capitulo'] = int(match.group(2))
        return info
    
    match = re.match(r'^(\d+)\s+(.*)$', texto)
    if match:
        info['versiculo'] = int(match.group(1))
        info['texto_versiculo'] = match.group(2)
        return info
    
    return info

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        # Limpa pastas
        for pasta in [UPLOAD_FOLDER, OUTPUT_FOLDER]:
            for f in os.listdir(pasta):
                try:
                    os.remove(os.path.join(pasta, f))
                except:
                    pass
        
        files = request.files.getlist('pdf_file')
        if not files or files[0].filename == '':
            flash("❌ Nenhum arquivo selecionado.", "error")
            return redirect(url_for('index'))
        
        todos_registros = []
        arquivos_processados = 0
        mensagens = []

        for file in files:
            if file and allowed_file(file.filename):
                try:
                    filename = secure_filename(file.filename)
                    filepath = os.path.join(UPLOAD_FOLDER, filename)
                    file.save(filepath)
                    
                    # Extrai texto linha por linha
                    texto_linhas = extrair_texto_por_linhas(filepath)
                    
                    if not texto_linhas:
                        mensagens.append(f"❌ {filename}: Não foi possível extrair texto")
                        continue
                    
                    # Processa de forma universal
                    registros = processar_pdf_universal(texto_linhas, filename)
                    
                    if registros:
                        todos_registros.extend(registros)
                        arquivos_processados += 1
                        mensagens.append(f"✅ {filename}: {len(registros)} registros processados")
                    else:
                        mensagens.append(f"⚠️ {filename}: Nenhum conteúdo válido encontrado")
                    
                except Exception as e:
                    mensagens.append(f"❌ Erro ao processar {filename}: {str(e)}")
        
        # Gera dataset se houver registros
        if todos_registros:
            try:
                df = pd.DataFrame(todos_registros)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                
                # TXT
                txt_path = os.path.join(OUTPUT_FOLDER, f"dataset_{timestamp}.txt")
                with open(txt_path, "w", encoding="utf-8") as f:
                    for r in todos_registros:
                        f.write(f"[{r['tipo'].upper()}] Pág {r['pagina']} - {r['texto']}\n")
                
                # JSON
                json_path = os.path.join(OUTPUT_FOLDER, f"dataset_{timestamp}.json")
                df.to_json(json_path, orient='records', force_ascii=False, indent=2)
                
                # CSV
                csv_path = os.path.join(OUTPUT_FOLDER, f"dataset_{timestamp}.csv")
                df.to_csv(csv_path, index=False, encoding='utf-8')
                
                # Parquet
                parquet_path = os.path.join(OUTPUT_FOLDER, f"dataset_{timestamp}.parquet")
                df.to_parquet(parquet_path, index=False)
                
                session['dataset_info'] = {
                    'gerado': True,
                    'timestamp': timestamp,
                    'total_registros': len(todos_registros),
                    'total_arquivos': arquivos_processados
                }
                
                mensagens.append(f"🎉 Dataset gerado! {len(todos_registros)} registros de {arquivos_processados} arquivo(s)")
                
            except Exception as e:
                mensagens.append(f"❌ Erro ao gerar arquivos: {str(e)}")
        else:
            mensagens.append("❌ Nenhum dado válido extraído")
        
        # Armazena mensagens na session
        session['mensagens'] = mensagens
        return redirect(url_for('index'))
    
    # GET request - recupera mensagens e info
    mensagens = session.pop('mensagens', [])
    dataset_info = session.pop('dataset_info', {})
    
    # Exibe mensagens
    for msg in mensagens:
        if msg.startswith('❌'): flash(msg, 'error')
        elif msg.startswith('⚠️'): flash(msg, 'warning')
        elif msg.startswith('🎉'): flash(msg, 'success')
        else: flash(msg, 'info')
    
    return render_template('index.html', **dataset_info)

@app.route('/download/<tipo>')
def download_dataset(tipo):
    timestamp = request.args.get('t', '')
    arquivos_validos = {
        'txt': f"dataset_{timestamp}.txt",
        'json': f"dataset_{timestamp}.json",
        'csv': f"dataset_{timestamp}.csv", 
        'parquet': f"dataset_{timestamp}.parquet"
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
    app.run(debug=True, port=5000)