"""Mapeamento e exportacao de entidades, relacionamentos e comunidades do Knowledge Graph."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Optional

import pandas as pd

LOGGER = logging.getLogger(__name__)

COLUNAS_ENTIDADES = [
    "human_readable_id",
    "title",
    "type",
    "description",
    "frequency",
    "degree",
]

COLUNAS_RELACIONAMENTOS = [
    "human_readable_id",
    "source",
    "target",
    "description",
    "weight",
    "combined_degree",
]

COLUNAS_COMUNIDADES = [
    "human_readable_id",
    "community",
    "level",
    "title",
    "size",
]


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


def carregar_parquet(caminho: Path) -> pd.DataFrame:
    """Carrega um arquivo Parquet e retorna como DataFrame.

    Parameters
    ----------
    caminho : Path
        Caminho para o arquivo Parquet.

    Returns
    -------
    pd.DataFrame
        DataFrame com os dados do Parquet.

    Raises
    ------
    FileNotFoundError
        Quando o arquivo nao existe no caminho informado.
    """
    if not caminho.exists():
        raise FileNotFoundError(f"Arquivo Parquet nao encontrado: {caminho}")
    LOGGER.info("Carregando: %s", caminho)
    return pd.read_parquet(caminho)


def resumir_entidades(df: pd.DataFrame) -> pd.DataFrame:
    """Gera tabela resumida de entidades do grafo.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame bruto de entidades (entities.parquet).

    Returns
    -------
    pd.DataFrame
        DataFrame com colunas selecionadas, ordenado por grau e frequencia.
    """
    colunas_disponiveis = [c for c in COLUNAS_ENTIDADES if c in df.columns]
    resumo = df.loc[:, colunas_disponiveis].copy()
    resumo.loc[:, "description"] = resumo["description"].str.slice(0, 200)

    colunas_ordenacao = [c for c in ["degree", "frequency"] if c in resumo.columns]
    if colunas_ordenacao:
        resumo = resumo.sort_values(colunas_ordenacao, ascending=False)

    return resumo.reset_index(drop=True)


def resumir_relacionamentos(df: pd.DataFrame) -> pd.DataFrame:
    """Gera tabela resumida de relacionamentos do grafo.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame bruto de relacionamentos (relationships.parquet).

    Returns
    -------
    pd.DataFrame
        DataFrame com colunas selecionadas, ordenado por peso.
    """
    colunas_disponiveis = [c for c in COLUNAS_RELACIONAMENTOS if c in df.columns]
    resumo = df.loc[:, colunas_disponiveis].copy()
    resumo.loc[:, "description"] = resumo["description"].str.slice(0, 200)

    if "weight" in resumo.columns:
        resumo = resumo.sort_values("weight", ascending=False)

    return resumo.reset_index(drop=True)


def resumir_comunidades(df: pd.DataFrame) -> pd.DataFrame:
    """Gera tabela resumida de comunidades detectadas no grafo.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame bruto de comunidades (communities.parquet).

    Returns
    -------
    pd.DataFrame
        DataFrame com colunas selecionadas, ordenado por nivel e tamanho.
    """
    colunas_disponiveis = [c for c in COLUNAS_COMUNIDADES if c in df.columns]
    resumo = df.loc[:, colunas_disponiveis].copy()

    colunas_ordenacao = [c for c in ["level", "size"] if c in resumo.columns]
    if colunas_ordenacao:
        resumo = resumo.sort_values(colunas_ordenacao, ascending=[True, False])

    return resumo.reset_index(drop=True)


def gerar_estatisticas(
    entidades: pd.DataFrame,
    relacionamentos: pd.DataFrame,
    comunidades: pd.DataFrame,
) -> str:
    """Gera resumo estatistico do Knowledge Graph.

    Parameters
    ----------
    entidades : pd.DataFrame
        DataFrame bruto de entidades.
    relacionamentos : pd.DataFrame
        DataFrame bruto de relacionamentos.
    comunidades : pd.DataFrame
        DataFrame bruto de comunidades.

    Returns
    -------
    str
        Texto formatado com as estatisticas do grafo.
    """
    linhas = [
        "=" * 60,
        "ESTATISTICAS DO KNOWLEDGE GRAPH",
        "=" * 60,
        "",
        f"Total de entidades:        {len(entidades):>6}",
        f"Total de relacionamentos:  {len(relacionamentos):>6}",
        f"Total de comunidades:      {len(comunidades):>6}",
        "",
    ]

    if "type" in entidades.columns:
        contagem_tipos = entidades["type"].value_counts()
        linhas.append("--- Entidades por tipo ---")
        for tipo, qtd in contagem_tipos.items():
            linhas.append(f"  {tipo:<30} {qtd:>5}")
        linhas.append("")

    if "level" in comunidades.columns:
        contagem_niveis = comunidades["level"].value_counts().sort_index()
        linhas.append("--- Comunidades por nivel ---")
        for nivel, qtd in contagem_niveis.items():
            linhas.append(f"  Nivel {nivel:<24} {qtd:>5}")
        linhas.append("")

    if "degree" in entidades.columns:
        linhas.append("--- Grau das entidades (top 10) ---")
        top_grau = entidades.nlargest(10, "degree").loc[:, ["title", "type", "degree"]]
        for _, row in top_grau.iterrows():
            linhas.append(f"  {row['title']:<35} ({row['type']}) grau={row['degree']}")
        linhas.append("")

    if "weight" in relacionamentos.columns:
        linhas.append("--- Relacionamentos mais fortes (top 10) ---")
        top_peso = relacionamentos.nlargest(10, "weight").loc[
            :, ["source", "target", "weight"]
        ]
        for _, row in top_peso.iterrows():
            linhas.append(
                f"  {row['source']:<25} -> {row['target']:<25} peso={row['weight']:.1f}"
            )
        linhas.append("")

    linhas.append("=" * 60)
    return "\n".join(linhas)


def exportar_csv(
    df: pd.DataFrame,
    caminho: Path,
    nome: str,
) -> Path:
    """Exporta um DataFrame em formato CSV.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame a ser exportado.
    caminho : Path
        Diretorio de destino para o arquivo CSV.
    nome : str
        Nome base do arquivo (sem extensao).

    Returns
    -------
    Path
        Caminho completo do arquivo CSV gerado.
    """
    caminho.mkdir(parents=True, exist_ok=True)
    arquivo = caminho / f"{nome}.csv"
    df.to_csv(arquivo, index=False, encoding="utf-8-sig")
    LOGGER.info("CSV exportado: %s (%s linhas)", arquivo, len(df))
    return arquivo


def executar_mapeamento(
    output_dir: Path,
    export_dir: Optional[Path] = None,
) -> str:
    """Executa o mapeamento completo do Knowledge Graph.

    Parameters
    ----------
    output_dir : Path
        Diretorio com os arquivos Parquet gerados pelo GraphRAG.
    export_dir : Optional[Path], default=None
        Diretorio para exportar CSVs. Se None, usa output_dir/tabelas.

    Returns
    -------
    str
        Texto com estatisticas formatadas do grafo.

    Raises
    ------
    FileNotFoundError
        Quando algum Parquet obrigatorio nao existe.
    """
    if export_dir is None:
        export_dir = output_dir / "tabelas"

    entidades_raw = carregar_parquet(output_dir / "entities.parquet")
    relacionamentos_raw = carregar_parquet(output_dir / "relationships.parquet")
    comunidades_raw = carregar_parquet(output_dir / "communities.parquet")

    entidades = resumir_entidades(entidades_raw)
    relacionamentos = resumir_relacionamentos(relacionamentos_raw)
    comunidades = resumir_comunidades(comunidades_raw)

    exportar_csv(entidades, export_dir, "entidades")
    exportar_csv(relacionamentos, export_dir, "relacionamentos")
    exportar_csv(comunidades, export_dir, "comunidades")

    estatisticas = gerar_estatisticas(
        entidades_raw, relacionamentos_raw, comunidades_raw
    )

    arquivo_stats = export_dir / "estatisticas.txt"
    arquivo_stats.write_text(estatisticas, encoding="utf-8")
    LOGGER.info("Estatisticas salvas: %s", arquivo_stats)

    return estatisticas


def criar_parser_argumentos() -> argparse.ArgumentParser:
    """Cria parser de argumentos para execucao via linha de comando.

    Returns
    -------
    argparse.ArgumentParser
        Parser configurado para o mapeamento do grafo.
    """
    parser = argparse.ArgumentParser(
        description="Mapeia entidades, relacionamentos e comunidades do Knowledge Graph.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output"),
        help="Diretorio com os Parquets gerados pelo GraphRAG (default: output).",
    )
    parser.add_argument(
        "--export-dir",
        type=Path,
        default=None,
        help="Diretorio para salvar os CSVs (default: output/tabelas).",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        help="Nivel de log (DEBUG, INFO, WARNING, ERROR).",
    )
    return parser


def main() -> int:
    """Executa o pipeline de mapeamento do Knowledge Graph.

    Returns
    -------
    int
        Codigo de status da execucao (0 para sucesso).

    Raises
    ------
    FileNotFoundError
        Quando os arquivos Parquet nao existem.
    """
    parser = criar_parser_argumentos()
    args = parser.parse_args()
    configurar_logging(nivel=args.log_level)

    estatisticas = executar_mapeamento(
        output_dir=args.output_dir,
        export_dir=args.export_dir,
    )

    print(estatisticas)
    LOGGER.info("Mapeamento concluido com sucesso.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
