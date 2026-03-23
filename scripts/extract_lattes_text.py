"""Extracao e limpeza de texto de curriculos Lattes em XML."""

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

    texto_nfkc = unicodedata.normalize("NFKC", texto)
    texto_sem_controle = "".join(
        char for char in texto_nfkc if unicodedata.category(char)[0] != "C"
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

    arvore = et.parse(xml_path)
    raiz = arvore.getroot()

    linhas: list[str] = []
    for elemento in raiz.iter():
        tag_limpa = normalizar_texto(elemento.tag.replace("-", " "))
        texto_elemento = normalizar_texto(elemento.text or "")
        if texto_elemento:
            linhas.append(f"{tag_limpa}: {texto_elemento}")

        for chave, valor in elemento.attrib.items():
            valor_limpo = normalizar_texto(valor)
            if not valor_limpo:
                continue
            chave_legivel = formatar_chave_atributo(chave)
            linhas.append(f"{tag_limpa} | {chave_legivel}: {valor_limpo}")

    linhas_unicas = [linha for linha in dict.fromkeys(linhas) if linha]
    if not linhas_unicas:
        raise ValueError(f"Nenhum texto valido encontrado no XML: {xml_path}")

    return linhas_unicas


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


def processar_arquivo(xml_path: Path, output_dir: Path) -> ArquivoProcessado:
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
    output_path = output_dir / f"{xml_path.stem}.txt"
    quantidade_linhas = salvar_texto(linhas=linhas, output_path=output_path)
    return ArquivoProcessado(
        xml_path=xml_path,
        txt_path=output_path,
        quantidade_linhas=quantidade_linhas,
    )


def processar_diretorio(input_dir: Path, output_dir: Path) -> list[ArquivoProcessado]:
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
        resultado = processar_arquivo(xml_path=xml_path, output_dir=output_dir)
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
    )
    LOGGER.info("Processamento concluido. Arquivos gerados: %s", len(resultados))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

