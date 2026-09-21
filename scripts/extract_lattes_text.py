"""Extracao e limpeza de texto de curriculos Lattes em XML.

Formato de saida: um registro do Lattes por linha. Uma producao (artigo, trabalho
em evento, software, patente...), orientacao, banca, participacao em evento,
projeto, formacao ou vinculo profissional vira UMA linha com os seus campos e a
lista das pessoas envolvidas, para que titulo e autores nunca fiquem separados.

Versoes anteriores emitiam uma linha por atributo e removiam linhas repetidas no
arquivo inteiro, o que apagava 62% do XML -- cada coautor so sobrevivia na
primeira producao em que aparecia.
"""

from __future__ import annotations

import argparse
import logging
import re
import unicodedata
import xml.etree.ElementTree as et
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

LOGGER = logging.getLogger(__name__)
WHITESPACE_RE = re.compile(r"\s+")
ATTRIBUTE_SPLIT_RE = re.compile(r"[_\-]+")

# Pessoas listadas dentro de um registro: rotulo da lista, atributo do nome completo
# e atributo do nome para citacao.
PESSOAS = {
    "AUTORES": ("autores", "NOME-COMPLETO-DO-AUTOR", "NOME-PARA-CITACAO"),
    "INTEGRANTES-DO-PROJETO": ("integrantes", "NOME-COMPLETO", "NOME-PARA-CITACAO"),
    "PARTICIPANTE-BANCA": (
        "participantes da banca",
        "NOME-COMPLETO-DO-PARTICIPANTE-DA-BANCA",
        "NOME-PARA-CITACAO-DO-PARTICIPANTE-DA-BANCA",
    ),
    "PARTICIPANTE-DE-EVENTOS-CONGRESSOS": (
        "participantes",
        "NOME-COMPLETO-DO-PARTICIPANTE-DE-EVENTOS-CONGRESSOS",
        "NOME-PARA-CITACAO-DO-PARTICIPANTE-DE-EVENTOS-CONGRESSOS",
    ),
}
# Outros itens listados dentro de um registro: rotulo da lista, atributo principal e
# atributo mostrado entre parenteses.
ITENS = {
    "PRODUCAO-CT-DO-PROJETO": ("producoes do projeto", "TITULO-DA-PRODUCAO-CT", "TIPO-PRODUCAO-CT"),
    "FINANCIADOR-DO-PROJETO": ("financiadores", "NOME-INSTITUICAO", "NATUREZA"),
    "ORIENTACAO": ("orientacoes do projeto", "TITULO-ORIENTACAO", "TIPO-ORIENTACAO"),
}
# Registros que nao tem filho DADOS-BASICOS-* (projetos e formacao academica).
REGISTROS_SEM_DADOS_BASICOS = frozenset(
    {
        "PROJETO-DE-PESQUISA",
        "GRADUACAO",
        "ESPECIALIZACAO",
        "MESTRADO",
        "MESTRADO-PROFISSIONALIZANTE",
        "DOUTORADO",
        "POS-DOUTORADO",
        "LIVRE-DOCENCIA",
        "CURSO-TECNICO-PROFISSIONALIZANTE",
        "ENSINO-FUNDAMENTAL-PRIMEIRO-GRAU",
        "ENSINO-MEDIO-SEGUNDO-GRAU",
        "APERFEICOAMENTO",
        "RESIDENCIA-MEDICA",
    }
)
# Atributos que nao viram entidade (identificadores, codigos, flags, ordem, links) e
# traducoes do mesmo conteudo (-INGLES, -EN).
PREFIXOS_IGNORADOS = (
    "SEQUENCIA",
    "CODIGO",
    "FLAG",
    "NRO-ID",
    "NUMERO-ID",
    "ORDEM",
    "HOME-PAGE",
    "DOI",
    "ISSN",
    "ISBN",
    "ORCID",
    "HORA",
    "SISTEMA-ORIGEM",
)
SUFIXOS_IGNORADOS = ("-INGLES", "-EN")
# Dado pessoal sem uso no grafo. De DADOS-GERAIS so vai a identificacao: os demais
# atributos sao nascimento, falecimento, PCD (dado de saude) e afins.
ELEMENTOS_OMITIDOS = frozenset({"ENDERECO"})
DADOS_GERAIS_MANTIDOS = ("NOME-COMPLETO", "NOME-EM-CITACOES-BIBLIOGRAFICAS")
# Valores longos (descricoes) vao para o fim da linha, depois das pessoas.
TAMANHO_TEXTO_LONGO = 200
ROTULO_TITULAR = "titular do curriculo"


@dataclass(frozen=True)
class ArquivoProcessado:
    """Representa o resultado do processamento de um XML.

    Attributes
    ----------
    xml_path : Path
        Caminho do arquivo XML de origem.
    txt_path : Path
        Caminho do arquivo TXT gerado.
    quantidade_linhas : int
        Quantidade de linhas salvas no arquivo de saida.
    """

    xml_path: Path
    txt_path: Path
    quantidade_linhas: int


def configurar_logging(nivel: str = "INFO") -> None:
    """Configura o logger padrao do script.

    Parameters
    ----------
    nivel : str, default="INFO"
        Nivel de log desejado (DEBUG, INFO, WARNING, ERROR).

    Returns
    -------
    None
        Nao retorna valor.
    """

    logging.basicConfig(
        level=getattr(logging, nivel.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


def normalizar_texto(texto: str) -> str:
    """Normaliza espacos e caracteres de um texto.

    Parameters
    ----------
    texto : str
        Texto bruto para normalizacao.

    Returns
    -------
    str
        Texto limpo, com espacos padronizados.
    """

    # NFC, e nao NFKC: a decomposicao de compatibilidade do NFKC troca os
    # indicadores ordinais por letras ("70ª" -> "70a", "Nº" -> "No") e parte
    # tokens com acento solto ("SUCESU´2005" -> "SUCESU ́2005").
    texto_normalizado = unicodedata.normalize("NFC", texto)
    texto_sem_controle = "".join(
        char for char in texto_normalizado if unicodedata.category(char)[0] != "C"
    )
    texto_sem_espacos_repetidos = WHITESPACE_RE.sub(" ", texto_sem_controle).strip()
    return texto_sem_espacos_repetidos


def formatar_chave_atributo(chave: str) -> str:
    """Converte nomes de atributos em uma chave mais legivel.

    Parameters
    ----------
    chave : str
        Nome de atributo no formato usado no XML do Lattes.

    Returns
    -------
    str
        Nome de atributo com separacao em espacos.
    """

    partes = [parte for parte in ATTRIBUTE_SPLIT_RE.split(chave) if parte]
    return " ".join(partes).lower()


def extrair_linhas_texto(xml_path: Path) -> list[str]:
    """Extrai linhas textuais relevantes de um curriculo Lattes.

    Parameters
    ----------
    xml_path : Path
        Caminho para o arquivo XML de curriculo.

    Returns
    -------
    list[str]
        Lista de linhas limpas prontas para serializacao.

    Raises
    ------
    FileNotFoundError
        Quando o arquivo XML informado nao existe.
    ValueError
        Quando nenhuma linha textual valida e encontrada.
    et.ParseError
        Quando o XML esta malformado.
    """

    if not xml_path.exists():
        raise FileNotFoundError(f"Arquivo XML nao encontrado: {xml_path}")

    raiz = et.parse(xml_path).getroot()
    dados_gerais = raiz.find("DADOS-GERAIS")
    titular = normalizar_texto(dados_gerais.get("NOME-COMPLETO", "")) if dados_gerais is not None else ""

    linhas: list[str] = []
    _percorrer(raiz, None, {}, titular, linhas)

    # So repeticoes vizinhas: a deduplicacao no arquivo inteiro apagava coautores.
    linhas_sem_repeticao = [
        linha for indice, linha in enumerate(linhas) if indice == 0 or linha != linhas[indice - 1]
    ]
    if not linhas_sem_repeticao:
        raise ValueError(f"Nenhum texto valido encontrado no XML: {xml_path}")

    return linhas_sem_repeticao


def _eh_registro(elemento: et.Element, pai: et.Element | None) -> bool:
    """Indica se o elemento e um registro do Lattes, emitido em uma linha so."""

    if elemento.tag in REGISTROS_SEM_DADOS_BASICOS:
        return True
    if any(filho.tag.startswith("DADOS-BASICOS") for filho in elemento):
        return True
    # Vinculos e atividades de uma atuacao profissional.
    return pai is not None and (
        pai.tag == "ATUACAO-PROFISSIONAL" or pai.tag.startswith("ATIVIDADES-DE-")
    )


def _campos(elemento: et.Element) -> list[tuple[str, str]]:
    """Devolve os pares (chave legivel, valor) uteis de um elemento."""

    campos: list[tuple[str, str]] = []
    texto = normalizar_texto(elemento.text or "")
    if texto:
        campos.append(("texto", texto))
    for chave, valor in elemento.attrib.items():
        if chave.startswith(PREFIXOS_IGNORADOS) or chave.endswith(SUFIXOS_IGNORADOS):
            continue
        if elemento.tag == "DADOS-GERAIS" and chave not in DADOS_GERAIS_MANTIDOS:
            continue
        valor_limpo = normalizar_texto(valor)
        if "CITACAO" in chave or "CITACOES" in chave:
            # Varias formas de citacao separadas por ';', que e o separador de campos.
            valor_limpo = " / ".join(parte.strip() for parte in valor_limpo.split(";") if parte.strip())
        if valor_limpo:
            campos.append((formatar_chave_atributo(chave), valor_limpo))
    return campos


def _pessoa(elemento: et.Element) -> str:
    """Formata uma pessoa como 'Nome Completo (CITACAO)'."""

    _, atributo_nome, atributo_citacao = PESSOAS[elemento.tag]
    nome = normalizar_texto(elemento.get(atributo_nome, ""))
    # O titular do curriculo traz todas as suas formas de citacao; basta a primeira.
    citacao = normalizar_texto(elemento.get(atributo_citacao, "")).split(";")[0].strip()
    texto = f"{nome} ({citacao})" if nome and citacao and citacao != nome else nome or citacao
    if elemento.get("FLAG-RESPONSAVEL") == "SIM":
        texto += " [responsavel]"
    return texto


def _item(elemento: et.Element) -> str:
    """Formata um item de lista (producao, financiador...) como 'Principal (detalhe)'."""

    _, atributo_principal, atributo_detalhe = ITENS[elemento.tag]
    principal = normalizar_texto(elemento.get(atributo_principal, ""))
    detalhe = normalizar_texto(elemento.get(atributo_detalhe, ""))
    return f"{principal} ({detalhe})" if principal and detalhe else principal or detalhe


def _linha(
    tag: str,
    principais: list[tuple[str, str]],
    contexto: dict[str, str],
    listas: dict[str, list[str]],
    demais: list[tuple[str, str]],
) -> str:
    """Monta a linha 'ROTULO: chave=valor; ...; autores: A; B; ...'.

    A ordem (dados basicos, contexto, listas, detalhes) deixa titulo e pessoas no
    inicio da linha: se o chunk cortar a linha, o que se perde sao detalhes.
    """

    listados = " ".join(item for itens in listas.values() for item in itens).upper()
    contexto_util = [
        (chave, valor)
        for chave, valor in contexto.items()
        if not (chave == ROTULO_TITULAR and valor.upper() in listados)
    ]
    # Pares chave=valor identicos aparecem quando o mesmo campo existe em dois filhos.
    campos = list(dict.fromkeys([*principais, *contexto_util]))
    campos_finais = [campo for campo in dict.fromkeys(demais) if campo not in campos]
    partes = [f"{chave}={valor}" for chave, valor in campos]
    partes += [f"{rotulo}: " + "; ".join(itens) for rotulo, itens in listas.items()]
    partes += [f"{chave}={valor}" for chave, valor in campos_finais]
    return f"{normalizar_texto(tag.replace('-', ' '))}: " + "; ".join(partes)


def _registro(
    elemento: et.Element, contexto: dict[str, str]
) -> tuple[str, list[tuple[et.Element, et.Element]]]:
    """Achata um registro em uma linha; devolve tambem os registros aninhados nele."""

    principais: list[tuple[str, str]] = []
    demais: list[tuple[str, str]] = []
    listas: dict[str, list[str]] = {}
    aninhados: list[tuple[et.Element, et.Element]] = []

    def separar(campos: list[tuple[str, str]], basicos: bool) -> None:
        for chave, valor in campos:
            longo = len(valor) > TAMANHO_TEXTO_LONGO
            (principais if basicos and not longo else demais).append((chave, valor))

    def visitar(no: et.Element) -> None:
        for filho in no:
            if filho.tag in ELEMENTOS_OMITIDOS:
                continue
            if _eh_registro(filho, no):
                aninhados.append((filho, no))
            elif filho.tag in PESSOAS:
                listas.setdefault(PESSOAS[filho.tag][0], []).append(_pessoa(filho))
            elif filho.tag in ITENS:
                listas.setdefault(ITENS[filho.tag][0], []).append(_item(filho))
            else:
                separar(_campos(filho), filho.tag.startswith("DADOS-BASICOS"))
                visitar(filho)

    separar(_campos(elemento), basicos=True)
    visitar(elemento)
    # Textos longos por ultimo: se o chunk cortar a linha, perde-se descricao, nao relacao.
    demais.sort(key=lambda campo: len(campo[1]) > TAMANHO_TEXTO_LONGO)
    return _linha(elemento.tag, principais, contexto, listas, demais), aninhados


def _percorrer(
    elemento: et.Element,
    pai: et.Element | None,
    contexto: dict[str, str],
    titular: str,
    linhas: list[str],
) -> None:
    """Percorre o XML emitindo uma linha por registro ou elemento com atributos.

    O contexto leva ao registro o que o Lattes deixa implicito: o titular do
    curriculo (formacao, atuacao, orientacoes) e a instituicao de uma atuacao
    profissional (os vinculos nao repetem o nome dela).
    """

    if elemento.tag in ELEMENTOS_OMITIDOS:
        return
    if _eh_registro(elemento, pai):
        if "ORIENTAC" in elemento.tag and titular:
            contexto = {**contexto, ROTULO_TITULAR: titular}
        linha, aninhados = _registro(elemento, contexto)
        linhas.append(linha)
        for filho, pai_filho in aninhados:
            _percorrer(filho, pai_filho, contexto, titular, linhas)
        return

    campos = _campos(elemento)
    if campos:
        linhas.append(_linha(elemento.tag, campos, contexto, {}, []))

    contexto_filhos = dict(contexto)
    if elemento.tag == "DADOS-GERAIS" and titular:
        contexto_filhos[ROTULO_TITULAR] = titular
    if elemento.tag == "ATUACAO-PROFISSIONAL":
        contexto_filhos["instituicao"] = normalizar_texto(elemento.get("NOME-INSTITUICAO", ""))
    for filho in elemento:
        _percorrer(filho, elemento, contexto_filhos, titular, linhas)


def salvar_texto(
    linhas: Iterable[str],
    output_path: Path,
    separador_linha: str = "\n",
) -> int:
    """Salva linhas de texto limpas em arquivo TXT.

    Parameters
    ----------
    linhas : Iterable[str]
        Conteudo textual a ser salvo.
    output_path : Path
        Caminho de destino para o arquivo TXT.
    separador_linha : str, default="\\n"
        Separador utilizado entre linhas no arquivo final.

    Returns
    -------
    int
        Quantidade de linhas efetivamente gravadas.
    """

    output_path.parent.mkdir(parents=True, exist_ok=True)
    linhas_lista = [linha for linha in linhas if linha]
    conteudo = separador_linha.join(linhas_lista)
    output_path.write_text(conteudo, encoding="utf-8")
    return len(linhas_lista)


def nome_saida(xml_path: Path, por_titular: bool) -> str:
    """Define o nome do TXT de saida.

    Parameters
    ----------
    xml_path : Path
        Caminho do XML de origem.
    por_titular : bool
        Quando verdadeiro, usa "<nome do titular> - <id lattes>", para que o
        ``title`` do documento no GraphRAG (que e o nome do arquivo) identifique o
        pesquisador. Assim ``chunking.prepend_metadata: [title]`` leva o nome do
        titular para o topo de cada chunk.

    Returns
    -------
    str
        Nome do arquivo, sem diretorio.
    """

    if not por_titular:
        return f"{xml_path.stem}.txt"
    dados_gerais = et.parse(xml_path).getroot().find("DADOS-GERAIS")
    titular = normalizar_texto(dados_gerais.get("NOME-COMPLETO", "")) if dados_gerais is not None else ""
    titular = re.sub(r'[\\/:*?"<>|]', "", titular).strip()
    return f"{titular} - {xml_path.stem}.txt" if titular else f"{xml_path.stem}.txt"


def processar_arquivo(xml_path: Path, output_dir: Path, nomear_por_titular: bool = False) -> ArquivoProcessado:
    """Processa um XML e salva um TXT correspondente.

    Parameters
    ----------
    xml_path : Path
        Caminho para o arquivo XML de entrada.
    output_dir : Path
        Diretorio onde os TXT processados serao salvos.

    Returns
    -------
    ArquivoProcessado
        Metadados do processamento concluido.
    """

    linhas = extrair_linhas_texto(xml_path=xml_path)
    output_path = output_dir / nome_saida(xml_path, nomear_por_titular)
    quantidade_linhas = salvar_texto(linhas=linhas, output_path=output_path)
    return ArquivoProcessado(
        xml_path=xml_path,
        txt_path=output_path,
        quantidade_linhas=quantidade_linhas,
    )


def processar_diretorio(
    input_dir: Path, output_dir: Path, nomear_por_titular: bool = False
) -> list[ArquivoProcessado]:
    """Processa todos os XMLs de um diretorio e gera TXT para cada arquivo.

    Parameters
    ----------
    input_dir : Path
        Diretorio com um ou mais curriculos Lattes em XML.
    output_dir : Path
        Diretorio de saida para os arquivos TXT.

    Returns
    -------
    list[ArquivoProcessado]
        Lista de resultados para todos os arquivos processados.

    Raises
    ------
    FileNotFoundError
        Quando o diretorio de entrada nao existe.
    ValueError
        Quando nenhum arquivo XML e encontrado.
    """

    if not input_dir.exists():
        raise FileNotFoundError(f"Diretorio de entrada nao encontrado: {input_dir}")

    xml_files = sorted(input_dir.glob("*.xml"))
    if not xml_files:
        raise ValueError(f"Nenhum arquivo XML encontrado em: {input_dir}")

    resultados: list[ArquivoProcessado] = []
    for xml_path in xml_files:
        LOGGER.info("Processando XML: %s", xml_path)
        resultado = processar_arquivo(
            xml_path=xml_path, output_dir=output_dir, nomear_por_titular=nomear_por_titular
        )
        LOGGER.info(
            "Arquivo salvo: %s (%s linhas)",
            resultado.txt_path,
            resultado.quantidade_linhas,
        )
        resultados.append(resultado)

    return resultados


def criar_parser_argumentos() -> argparse.ArgumentParser:
    """Cria parser de argumentos para execucao via linha de comando.

    Parameters
    ----------
    None
        Nao recebe parametros.

    Returns
    -------
    argparse.ArgumentParser
        Parser configurado para o fluxo de extracao.
    """

    parser = argparse.ArgumentParser(
        description="Extrai texto limpo de curriculos Lattes (XML) para TXT.",
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path("input_xml"),
        help="Diretorio com arquivos XML de curriculo Lattes.",
    )
    parser.add_argument(
        "--nomear-por-titular",
        action="store_true",
        help="Nomeia o TXT como '<titular> - <id>.txt' (vira o title do documento).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("input"),
        help="Diretorio de saida para os arquivos TXT.",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        help="Nivel de log (DEBUG, INFO, WARNING, ERROR).",
    )
    return parser


def main() -> int:
    """Executa o pipeline de extracao de XML para texto.

    Parameters
    ----------
    None
        Nao recebe parametros diretos; usa argumentos de CLI.

    Returns
    -------
    int
        Codigo de status da execucao (0 para sucesso).

    Raises
    ------
    FileNotFoundError
        Quando o diretorio de entrada nao existe.
    ValueError
        Quando nao ha XML valido para processamento.
    et.ParseError
        Quando algum XML esta malformado.
    """

    parser = criar_parser_argumentos()
    args = parser.parse_args()

    configurar_logging(nivel=args.log_level)
    resultados = processar_diretorio(
        input_dir=args.input_dir,
        output_dir=args.output_dir,
        nomear_por_titular=args.nomear_por_titular,
    )
    LOGGER.info("Processamento concluido. Arquivos gerados: %s", len(resultados))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

