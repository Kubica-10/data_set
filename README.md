📄 PDF Dataset Generator
https://img.shields.io/badge/Python-3.8+-blue.svg
https://img.shields.io/badge/Flask-2.3+-green.svg

Uma aplicação web inteligente para converter PDFs em datasets estruturados (TXT, JSON, CSV, Parquet) com detecção automática de conteúdo e filtragem de metadados.

🚀 Começando
Instalação Rápida
bash
# Instale as dependências
pip install flask PyMuPDF pandas pyarrow werkzeug

# Execute a aplicação
python app.py
Acesse no navegador
text
http://localhost:5000
📊 Formatos de Saída
TXT - Texto formatado

JSON - Estruturado para APIs

CSV - Planilha para análise

Parquet - Otimizado para Big Data

🎯 Funcionalidades
✅ Processamento de qualquer tipo de PDF

✅ Detecção inteligente de conteúdo bíblico

✅ Filtro automático de metadados

✅ Interface moderna com drag & drop

✅ Suporte a múltiplos arquivos

📁 Estrutura do Projeto
text
pdf-dataset-generator/
├── app.py                 # Aplicação principal
├── templates/
│   └── index.html        # Interface web
├── uploads/              # PDFs temporários
└── outputs/              # Datasets gerados
🔧 Comandos para GitHub
bash
# Adicione ao Git
git add .

# Commit
git commit -m "🚀 Versão 2.0 - PDF Dataset Generator completo"

# Configure o repositório
git remote add origin https://github.com/seu-usuario/pdf-dataset-generator.git

# Envie para o GitHub
git push -u origin main
⚡ Uso Rápido
Execute python app.py

Acesse http://localhost:5000

Selecione os PDFs

Clique em "Gerar Dataset"

Faça o download nos formatos desejados

Desenvolvido com ❤️ para a comunidade

