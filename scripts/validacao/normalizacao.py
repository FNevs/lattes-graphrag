"""Chaves de comparacao e casamento de nomes para a validacao do grafo contra o XML.

O grafo e o XML nunca escrevem a mesma coisa do mesmo jeito: o GraphRAG poe titulos em
maiusculas e as vezes os encurta; o Lattes registra a mesma pessoa como "Hugo Saba
Pereira Cardoso", "SABA, H." ou "CARDOSO, HUGO S.P.". Tudo aqui compara por uma chave
normalizada (sem acento, sem pontuacao, minuscula) e, para pessoas, por compatibilidade
de sobrenome e iniciais.
"""

from __future__ import annotations

import re
import unicodedata

from rapidfuzz import fuzz

NAO_ALFANUMERICO = re.compile(r"[^0-9a-z]+")
# Particulas que nao identificam ninguem: "Jose Garcia Vivas Miranda" e "Jose Garcia
# Vivas de Miranda" sao a mesma pessoa.
PARTICULAS = frozenset({"de", "da", "do", "das", "dos", "e", "del", "della", "di", "van", "von"})
SUFIXOS = frozenset({"filho", "filha", "junior", "jr", "neto", "neta", "sobrinho"})


def chave(texto: str | None) -> str:
    """Forma de comparacao: sem acento, minuscula, so letras e digitos separados por espaco."""

    if not texto:
        return ""
    decomposto = unicodedata.normalize("NFKD", texto)
    sem_acento = "".join(c for c in decomposto if not unicodedata.combining(c))
    return NAO_ALFANUMERICO.sub(" ", sem_acento.casefold()).strip()


def contem(texto_chave: str, trecho_chave: str) -> bool:
    """`trecho_chave` aparece em `texto_chave` como sequencia de palavras inteiras."""

    if not trecho_chave or not texto_chave:
        return False
    return f" {trecho_chave} " in f" {texto_chave} "


def semelhanca(a: str, b: str) -> float:
    """Semelhanca de 0 a 100 entre duas chaves (titulos, instituicoes, eventos).

    Usa a maior entre a comparacao direta e a comparacao com as palavras ordenadas. Nao
    usa `token_set_ratio`: ele da 100 para "universidade" contra "universidade federal
    da bahia", o que casaria qualquer instituicao com qualquer outra.
    """

    if not a or not b:
        return 0.0
    if a == b:
        return 100.0
    return max(fuzz.ratio(a, b), fuzz.token_sort_ratio(a, b))


def tokens_de_nome(nome_chave: str) -> list[str]:
    """Palavras de um nome sem as particulas ("de", "da", "dos"...)."""

    return [t for t in nome_chave.split() if t not in PARTICULAS]


def formas_de_citacao(citacoes: str | None) -> list[str]:
    """Separa "SABA, H.;CARDOSO, Hugo Saba" (ou com " / ") em chaves de nome.

    "SOBRENOME, Nome" vira "nome sobrenome", para comparar na mesma ordem do nome completo.
    """

    if not citacoes:
        return []
    formas = []
    for parte in re.split(r"[;/]", citacoes):
        parte = parte.strip().strip(",")
        if not parte:
            continue
        if "," in parte:
            sobrenome, _, prenomes = parte.partition(",")
            parte = f"{prenomes} {sobrenome}"
        k = chave(parte)
        if k:
            formas.append(k)
    return formas


def nome_compativel(candidato: str, completo: str) -> bool:
    """O nome `candidato` (chave) pode ser uma forma abreviada do nome `completo` (chave)?

    Regras, todas necessarias:
    - o candidato tem pelo menos 2 palavras ("saba" sozinho nao identifica ninguem);
    - cada palavra do candidato corresponde a uma palavra distinta do nome completo,
      por igualdade ou, se for uma inicial, pela primeira letra;
    - a primeira palavra do candidato (o prenome ou a inicial dele) casa com a primeira do
      nome completo: "A. Nascimento" nao e "Marcelo Antonio do Nascimento";
    - pelo menos uma palavra por extenso casa com um sobrenome (qualquer palavra que nao
      seja a primeira do nome completo);
    - a ordem relativa e preservada ou o candidato e "sobrenome + iniciais" (formato de
      citacao), que o Lattes inverte.

    Exemplos verdadeiros para "hugo saba pereira cardoso": "hugo saba", "h saba",
    "hugo s p cardoso", "cardoso hugo s p". Falso: "hugo pereira silva".
    """

    cand = tokens_de_nome(candidato)
    comp = tokens_de_nome(completo)
    if len(cand) < 2 or not comp:
        return False
    if cand == comp:
        return True

    def casa(ordem: list[str]) -> bool:
        usados: set[int] = set()
        por_extenso_em_sobrenome = False
        posicao = -1
        for palavra in ordem:
            achou = None
            for i, alvo in enumerate(comp):
                if i in usados or i <= posicao:
                    continue
                if (len(palavra) == 1 and alvo.startswith(palavra)) or palavra == alvo:
                    achou = i
                    break
            if achou is None or (posicao == -1 and achou != 0):
                return False
            usados.add(achou)
            posicao = achou
            if len(palavra) > 1 and achou > 0 and comp[achou] not in SUFIXOS:
                por_extenso_em_sobrenome = True
        return por_extenso_em_sobrenome

    if casa(cand):
        return True
    # "cardoso hugo s p": sobrenome primeiro (formato de citacao invertido)
    return casa(cand[1:] + cand[:1])


def pontuar_pessoa(candidato: str, nomes_completos: list[str], citacoes: list[str]) -> float:
    """Pontua de 0 a 100 se `candidato` (chave) e a pessoa descrita pelos nomes e citacoes.

    100: igual ao nome completo ou a uma forma de citacao declarada.
    96: forma compativel com algum nome completo (sobrenome + iniciais, nome encurtado).
    Abaixo disso: semelhanca aproximada com o nome completo mais parecido.
    """

    if not candidato:
        return 0.0
    if candidato in nomes_completos or candidato in citacoes:
        return 100.0
    # nos dois sentidos para nomes completos: o grafo pode abreviar ("H. SABA") ou o XML
    # pode ("Matheus G. A. Tanure" na lista de autores, "MATHEUS GUIMARAES ANDRADE TANURE"
    # no grafo). Citacoes so num sentido: "NASCIMENTO, A." e curta demais para dizer que
    # "ALEXSANDRO DE OLINDA NASCIMENTO" e a mesma pessoa.
    if any(nome_compativel(candidato, n) or nome_compativel(n, candidato) for n in nomes_completos):
        return 96.0
    melhor = max((semelhanca(candidato, n) for n in nomes_completos), default=0.0)
    return melhor
