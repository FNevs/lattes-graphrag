"""Metricas estruturais do Knowledge Graph para o plano de validacao do TCC."""

from __future__ import annotations

import argparse
import logging
import math
import statistics
from collections import Counter
from pathlib import Path
from typing import Optional

import networkx as nx
import pandas as pd

LOGGER = logging.getLogger(__name__)

# Leiden exige igraph + leidenalg, que nao fazem parte do venv minimo do
# GraphRAG. Sem eles o script segue rodando e cai no Louvain do networkx.
try:
    import igraph as ig
    import leidenalg as la

    LEIDEN_DISPONIVEL = True
except ImportError:  # pragma: no cover
    LEIDEN_DISPONIVEL = False

SEMENTES_LEIDEN = 10
SEMENTE_LOUVAIN = 42


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


def carregar_grafo(caminho: Path) -> nx.Graph:
    """Carrega o snapshot GraphML gerado pelo GraphRAG.

    Parameters
    ----------
    caminho : Path
        Caminho para o arquivo graph.graphml.

    Returns
    -------
    nx.Graph
        Grafo nao-direcionado com atributo `weight` nas arestas.

    Raises
    ------
    FileNotFoundError
        Quando o arquivo nao existe no caminho informado.
    """
    if not caminho.exists():
        raise FileNotFoundError(
            f"GraphML nao encontrado: {caminho}. "
            "Verifique se settings.yaml tem snapshots.graphml: true."
        )
    LOGGER.info("Carregando: %s", caminho)
    return nx.read_graphml(caminho)


def mapear_tipos(entidades: pd.DataFrame) -> dict[str, str]:
    """Mapeia titulo da entidade para o seu tipo.

    O GraphML do GraphRAG nao carrega o atributo `type`, entao o tipo precisa
    vir de entities.parquet, casando pelo titulo (que e o id do no).

    Parameters
    ----------
    entidades : pd.DataFrame
        DataFrame bruto de entidades (entities.parquet).

    Returns
    -------
    dict[str, str]
        Dicionario titulo -> tipo.
    """
    return dict(zip(entidades["title"], entidades["type"]))


def analisar_populacoes(grafo: nx.Graph, entidades: pd.DataFrame) -> list[str]:
    """Compara as duas populacoes de entidades: parquet versus grafo.

    entities.parquet e graph.graphml nao tem a mesma contagem. A diferenca vem
    de entidades isoladas (degree 0, fora do GraphML) e de nos-fantasma, que so
    existem como extremos de relacionamentos e nunca foram registrados como
    entidade -- artefatos de extracao do LLM.

    Parameters
    ----------
    grafo : nx.Graph
        Grafo carregado do GraphML.
    entidades : pd.DataFrame
        DataFrame bruto de entidades.

    Returns
    -------
    list[str]
        Linhas formatadas do relatorio.
    """
    tipos = mapear_tipos(entidades)
    titulos = set(entidades["title"])
    nos = set(grafo.nodes())

    isoladas = titulos - nos
    fantasmas = nos - titulos

    linhas = ["--- Populacoes de entidades ---", ""]
    linhas.append(f"  entities.parquet:                 {len(entidades):>5}")
    linhas.append(f"  (-) isoladas (degree == 0):       {len(isoladas):>5}")
    linhas.append(f"  (+) nos-fantasma (so em relacoes):{len(fantasmas):>5}")
    linhas.append(f"  (=) nos no graph.graphml:         {grafo.number_of_nodes():>5}")
    linhas.append("")

    linhas.append("--- Entidades por tipo (entities.parquet) ---")
    for tipo, qtd in entidades["type"].value_counts().items():
        linhas.append(f"  {tipo:<30} {qtd:>5}")
    linhas.append("")

    linhas.append("--- Entidades por tipo (nos do grafo) ---")
    contagem = Counter(tipos.get(n, "SEM TIPO") for n in grafo.nodes())
    total = grafo.number_of_nodes()
    for tipo, qtd in contagem.most_common():
        linhas.append(f"  {tipo:<30} {qtd:>5}  ({100 * qtd / total:5.2f}%)")
    linhas.append("")

    if fantasmas:
        linhas.append("--- Nos-fantasma por grau (top 10) ---")
        for no in sorted(fantasmas, key=lambda n: -grafo.degree(n))[:10]:
            linhas.append(f"  grau={grafo.degree(no):>3}  {no}")
        linhas.append("")

    return linhas


def analisar_topologia(grafo: nx.Graph, entidades: pd.DataFrame) -> list[str]:
    """Calcula grau, centralidade de grau e distribuicao dos graus.

    Parameters
    ----------
    grafo : nx.Graph
        Grafo carregado do GraphML.
    entidades : pd.DataFrame
        DataFrame bruto de entidades, usado para rotular o top de grau.

    Returns
    -------
    list[str]
        Linhas formatadas do relatorio.
    """
    tipos = mapear_tipos(entidades)
    graus = [d for _, d in grafo.degree()]
    centralidade = nx.degree_centrality(grafo)
    componentes = list(nx.connected_components(grafo))

    linhas = ["--- Topologia ---", ""]
    linhas.append(f"  Nos:                       {grafo.number_of_nodes():>10}")
    linhas.append(f"  Arestas:                   {grafo.number_of_edges():>10}")
    linhas.append(f"  Densidade:                 {nx.density(grafo):>10.6f}")
    linhas.append(f"  Self-loops:                {nx.number_of_selfloops(grafo):>10}")
    linhas.append(f"  Componentes conexos:       {len(componentes):>10}")
    linhas.append(f"  Maior componente:          {max(len(c) for c in componentes):>10}")
    linhas.append("")

    linhas.append("--- Grau e centralidade ---")
    linhas.append(f"  Grau medio (2E/N):         {2 * grafo.number_of_edges() / grafo.number_of_nodes():>10.4f}")
    linhas.append(f"  Grau mediano:              {statistics.median(graus):>10}")
    linhas.append(f"  Grau minimo / maximo:      {min(graus):>4} / {max(graus)}")
    linhas.append(f"  Centralidade de grau media:{sum(centralidade.values()) / len(centralidade):>10.6f}")
    linhas.append(f"  Centralidade mediana:      {statistics.median(centralidade.values()):>10.6f}")
    linhas.append(f"  Centralidade maxima:       {max(centralidade.values()):>10.6f}")
    linhas.append("")

    linhas.append("--- Distribuicao dos graus ---")
    histograma = Counter(graus)
    acumulado = 0
    for grau in sorted(histograma):
        acumulado += histograma[grau]
        if grau <= 12:
            linhas.append(
                f"  grau {grau:>3}: {histograma[grau]:>5} nos "
                f"({100 * histograma[grau] / len(graus):>5.2f}%)  "
                f"acumulado {100 * acumulado / len(graus):>6.2f}%"
            )
    linhas.append(f"  grau > 12: {sum(q for g, q in histograma.items() if g > 12):>5} nos")
    linhas.append("")

    linhas.append("--- Nos de maior grau (top 10) ---")
    for no, grau in sorted(grafo.degree(), key=lambda x: -x[1])[:10]:
        linhas.append(f"  grau={grau:>3}  ({tipos.get(no, 'SEM TIPO'):<12}) {no}")
    linhas.append("")

    return linhas


def analisar_comunidades_graphrag(
    grafo: nx.Graph,
    comunidades: pd.DataFrame,
    entidades: pd.DataFrame,
) -> list[str]:
    """Avalia a particao Leiden hierarquica produzida pelo proprio GraphRAG.

    Este e o particionamento que gerou os community reports. Nao confundir com
    um Leiden rodado por cima do grafo depois (ver `recalcular_leiden`): como o
    GraphRAG usa max_cluster_size, as comunidades sao pequenas e a modularidade
    resultante e bem menor.

    Parameters
    ----------
    grafo : nx.Graph
        Grafo carregado do GraphML.
    comunidades : pd.DataFrame
        DataFrame bruto de comunidades (communities.parquet).
    entidades : pd.DataFrame
        DataFrame bruto de entidades, usado para resolver id -> titulo.

    Returns
    -------
    list[str]
        Linhas formatadas do relatorio.
    """
    linhas = ["--- Comunidades do GraphRAG (Leiden hierarquico) ---", ""]

    for nivel in sorted(comunidades["level"].unique()):
        sub = comunidades[comunidades["level"] == nivel]
        tamanhos = sub["entity_ids"].apply(len)
        linhas.append(
            f"  Nivel {nivel}: {len(sub):>3} comunidades | "
            f"tam. medio {tamanhos.mean():>6.2f} | mediano {tamanhos.median():>5.1f} | "
            f"min {tamanhos.min()} | max {tamanhos.max()}"
        )
    tamanhos_geral = comunidades["entity_ids"].apply(len)
    linhas.append(
        f"  TOTAL: {len(comunidades)} comunidades | "
        f"tam. medio {tamanhos_geral.mean():.2f}"
    )
    linhas.append("")

    id_para_titulo = dict(zip(entidades["id"], entidades["title"]))
    linhas.append("--- Modularidade da particao do GraphRAG ---")
    for nivel in sorted(comunidades["level"].unique()):
        sub = comunidades[comunidades["level"] == nivel]
        particao: list[set[str]] = []
        vistos: set[str] = set()
        for ids in sub["entity_ids"]:
            grupo = {
                id_para_titulo[i]
                for i in ids
                if i in id_para_titulo and id_para_titulo[i] in grafo
            }
            grupo -= vistos
            vistos |= grupo
            if grupo:
                particao.append(grupo)

        # Nos fora da particao daquele nivel entram como singletons para que a
        # modularidade seja calculada sobre uma particao completa do grafo.
        restantes = set(grafo.nodes()) - vistos
        completa = particao + [{n} for n in restantes]

        q_simples = nx.community.modularity(grafo, completa, weight=None)
        q_pond = nx.community.modularity(grafo, completa, weight="weight")
        linhas.append(
            f"  Nivel {nivel}: {len(particao):>3} comunidades "
            f"(+{len(restantes)} singletons) | "
            f"Q nao-pond = {q_simples:.4f} | Q pond = {q_pond:.4f}"
        )
    linhas.append("")
    return linhas


def recalcular_leiden(grafo: nx.Graph) -> list[str]:
    """Roda Leiden por cima do grafo, para comparar com o valor do Gephi.

    Executa varias sementes e reporta a melhor modularidade, ja que o Leiden e
    estocastico.

    Parameters
    ----------
    grafo : nx.Graph
        Grafo carregado do GraphML.

    Returns
    -------
    list[str]
        Linhas formatadas do relatorio.
    """
    linhas = ["--- Leiden recalculado sobre o grafo ---", ""]

    if not LEIDEN_DISPONIVEL:
        linhas.append("  igraph/leidenalg nao instalados -- Leiden ignorado.")
        linhas.append("  Instale com: pip install igraph leidenalg")
        linhas.append("")
        return linhas + _louvain_referencia(grafo)

    nos = list(grafo.nodes())
    indice = {no: i for i, no in enumerate(nos)}
    arestas = [(indice[u], indice[v]) for u, v in grafo.edges()]
    pesos = [float(d.get("weight", 1.0)) for _, _, d in grafo.edges(data=True)]

    g = ig.Graph(n=len(nos), edges=arestas, directed=False)
    g.vs["name"] = nos
    g.es["weight"] = pesos

    for rotulo, w in (("nao-ponderado", None), ("ponderado", pesos)):
        melhor = None
        for semente in range(SEMENTES_LEIDEN):
            particao = la.find_partition(
                g,
                la.ModularityVertexPartition,
                weights=w,
                n_iterations=-1,
                seed=semente,
            )
            if melhor is None or particao.modularity > melhor.modularity:
                melhor = particao
        tamanhos = [len(c) for c in melhor]
        linhas.append(
            f"  Leiden {rotulo:<14}: Q = {melhor.modularity:.4f} | "
            f"{len(melhor):>3} comunidades | "
            f"tam. medio {sum(tamanhos) / len(tamanhos):.2f} | max {max(tamanhos)}"
        )
    linhas.append("")
    return linhas + _louvain_referencia(grafo)


def _louvain_referencia(grafo: nx.Graph) -> list[str]:
    """Roda Louvain como referencia de modularidade.

    So depende do networkx, entao continua disponivel mesmo quando o Leiden nao
    esta instalado.

    Parameters
    ----------
    grafo : nx.Graph
        Grafo carregado do GraphML.

    Returns
    -------
    list[str]
        Linhas formatadas do relatorio.
    """
    linhas = ["--- Louvain (networkx), referencia ---"]
    for rotulo, peso in (("nao-ponderado", None), ("ponderado", "weight")):
        cs = nx.community.louvain_communities(grafo, weight=peso, seed=SEMENTE_LOUVAIN)
        q = nx.community.modularity(grafo, cs, weight=peso)
        linhas.append(f"  Louvain {rotulo:<14}: Q = {q:.4f} | {len(cs):>3} comunidades")
    linhas.append("")
    return linhas


def gerar_relatorio(output_dir: Path) -> str:
    """Monta o relatorio completo de metricas estruturais.

    Parameters
    ----------
    output_dir : Path
        Diretorio com os artefatos gerados pelo GraphRAG.

    Returns
    -------
    str
        Texto formatado com todas as metricas.

    Raises
    ------
    FileNotFoundError
        Quando o GraphML ou algum Parquet obrigatorio nao existe.
    """
    grafo = carregar_grafo(output_dir / "graph.graphml")
    entidades = pd.read_parquet(output_dir / "entities.parquet")
    relacionamentos = pd.read_parquet(output_dir / "relationships.parquet")
    comunidades = pd.read_parquet(output_dir / "communities.parquet")

    linhas = [
        "=" * 70,
        "METRICAS ESTRUTURAIS DO KNOWLEDGE GRAPH",
        "=" * 70,
        "",
        f"Entidades extraidas:   {len(entidades):>6}",
        f"Relacionamentos:       {len(relacionamentos):>6}",
        f"Comunidades:           {len(comunidades):>6}",
        "",
    ]
    linhas += analisar_populacoes(grafo, entidades)
    linhas += analisar_topologia(grafo, entidades)
    linhas += analisar_comunidades_graphrag(grafo, comunidades, entidades)
    linhas += recalcular_leiden(grafo)
    linhas.append("=" * 70)
    return "\n".join(linhas)


def criar_parser_argumentos() -> argparse.ArgumentParser:
    """Cria parser de argumentos para execucao via linha de comando.

    Returns
    -------
    argparse.ArgumentParser
        Parser configurado para o calculo de metricas.
    """
    parser = argparse.ArgumentParser(
        description="Calcula metricas estruturais do Knowledge Graph do GraphRAG.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output"),
        help="Diretorio com os artefatos do GraphRAG (default: output).",
    )
    parser.add_argument(
        "--salvar-em",
        type=Path,
        default=None,
        help="Arquivo .txt para gravar o relatorio (default: apenas stdout).",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        help="Nivel de log (DEBUG, INFO, WARNING, ERROR).",
    )
    return parser


def main() -> int:
    """Executa o calculo de metricas estruturais do grafo.

    Returns
    -------
    int
        Codigo de status da execucao (0 para sucesso).

    Raises
    ------
    FileNotFoundError
        Quando os artefatos do GraphRAG nao existem.
    """
    parser = criar_parser_argumentos()
    args = parser.parse_args()
    configurar_logging(nivel=args.log_level)

    relatorio = gerar_relatorio(output_dir=args.output_dir)
    print(relatorio)

    if args.salvar_em is not None:
        args.salvar_em.parent.mkdir(parents=True, exist_ok=True)
        args.salvar_em.write_text(relatorio, encoding="utf-8")
        LOGGER.info("Relatorio salvo: %s", args.salvar_em)

    LOGGER.info("Calculo de metricas concluido com sucesso.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
