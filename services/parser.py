import regex as re

# Expressão mais robusta: permite letras minúsculas e nomes compostos (e.g. 1 João)
padrao_versiculo = re.compile(
    r"""
    (?P<livro>[1-3]?\s?[A-ZÁ-Úa-zá-úçõêâîéíóúàèùãõü\-]+(?:\s+[A-ZÁ-Úa-zá-úçõêâîéíóúàèùãõü\-]+)*)  # Livro
    \s+
    (?P<capitulo>\d+)
    :
    (?P<versiculo>\d+)
    \s+
    (?P<texto>.+)
    """,
    re.VERBOSE
)

def extrair_versiculos(texto):
    dados = []
    linhas = texto.splitlines()
    for linha in linhas:
        linha = linha.strip()
        if not linha:
            continue
        match = padrao_versiculo.match(linha)
        if match:
            dados.append({
                "livro": match.group("livro"),
                "capitulo": int(match.group("capitulo")),
                "versiculo": int(match.group("versiculo")),
                "texto": match.group("texto")
            })
    return dados
