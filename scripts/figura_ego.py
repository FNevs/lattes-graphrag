"""Gera figuras de ego-network legiveis em P&B a partir do graph.graphml.

O grafo completo (1114 nos) vira um hairball ilegivel em A4. Este script recorta
a vizinhanca de um no central em profundidade 1 e 2, dimensiona os nos pelo grau
no grafo COMPLETO e rotula so os mais conectados.

Reproduz as figuras da monografia: as sementes e os parametros de layout estao
fixos, entao rodar de novo gera a mesma imagem.
"""

from __future__ import annotations

import argparse
import logging
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

# Sem hashsalt fixo o matplotlib sorteia os ids de clip-path do SVG a cada
# processo, e o arquivo muda mesmo com a figura identica.
matplotlib.rcParams["svg.hashsalt"] = "lattes-graphrag"

import matplotlib.patheffects as pe
import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D

LOGGER = logging.getLogger(__name__)

EGO_PADRAO = "EDUARDO MANUEL DE FREITAS JORGE"
SEMENTE_LAYOUT = 7
DPI_PNG = 600

# Forma + tom de cinza por tipo: a figura tem que sobreviver a impressao P&B,
# entao a forma carrega a informacao e a cor so reforca.
ESTILO_TIPO: dict[str, tuple[str, str]] = {
    "PERSON": ("o", "#FFFFFF"),
    "ORGANIZATION": ("s", "#9E9E9E"),
    "EVENT": ("^", "#DCDCDC"),
    "GEO": ("D", "#5A5A5A"),
    "SOFTWARE": ("v", "#3A3A3A"),
    "SEM TIPO": ("X", "#F2F2F2"),
}

# Valores literais de extract_graph.entity_types em settings.yaml. Tipos fora
# desta lista nao foram configurados e chegaram por gleaning do LLM; 'SEM TIPO'
# sao nos que so existem como extremo de relacao, sem registro em
# entities.parquet. Os dois casos sao artefatos de extracao, e a figura precisa
# declarar isso -- senao contradiz o texto da monografia.
ENTITY_TYPES_CONFIGURADOS = ("ORGANIZATION", "PERSON", "GEO", "EVENT")

# Tracejado usado no contorno dos nos que sao artefato de extracao.
TRACEJADO = (0, (2.5, 1.5))

HALO = [pe.withStroke(linewidth=2.2, foreground="white")]


def _e_artefato(tipo: str) -> bool:
    """Diz se um tipo e artefato de extracao (nao consta em entity_types).

    Parameters
    ----------
    tipo : str
        Nome do tipo, em maiusculas (ex.: "SOFTWARE", "SEM TIPO").

    Returns
    -------
    bool
        True quando o tipo nao foi configurado em settings.yaml.
    """
    return tipo not in ENTITY_TYPES_CONFIGURADOS


def _rotulo_tipo(tipo: str) -> str:
    """Formata o nome do tipo para a legenda.

    Os tipos configurados sao mostrados em ingles e minusculo por serem os
    valores literais de settings.yaml e de entities.parquet -- o texto da
    monografia os cita assim, em italico. "SEM TIPO" e descricao, nao valor
    literal, e por isso fica em portugues.

    Parameters
    ----------
    tipo : str
        Nome do tipo, em maiusculas.

    Returns
    -------
    str
        Rotulo para exibicao.
    """
    return "sem tipo" if tipo == "SEM TIPO" else tipo.lower()


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


def carregar_contexto(output_dir: Path) -> tuple[nx.Graph, dict[str, str], dict[str, int]]:
    """Carrega o grafo, o mapa de tipos e o grau de cada no.

    O GraphML do GraphRAG nao traz o atributo `type`, entao o tipo vem de
    entities.parquet casando pelo titulo (que e o id do no).

    Parameters
    ----------
    output_dir : Path
        Diretorio com os artefatos gerados pelo GraphRAG.

    Returns
    -------
    tuple[nx.Graph, dict[str, str], dict[str, int]]
        Grafo, mapa titulo -> tipo e mapa no -> grau no grafo completo.

    Raises
    ------
    FileNotFoundError
        Quando o GraphML ou entities.parquet nao existem.
    """
    caminho_grafo = output_dir / "graph.graphml"
    if not caminho_grafo.exists():
        raise FileNotFoundError(
            f"GraphML nao encontrado: {caminho_grafo}. "
            "Verifique se settings.yaml tem snapshots.graphml: true."
        )
    LOGGER.info("Carregando: %s", caminho_grafo)
    grafo = nx.read_graphml(caminho_grafo)

    entidades = pd.read_parquet(output_dir / "entities.parquet")
    tipos = dict(zip(entidades["title"], entidades["type"]))
    graus = dict(grafo.degree())
    return grafo, tipos, graus


def subgrafo_ego(grafo: nx.Graph, ego: str, raio: int) -> nx.Graph:
    """Recorta a vizinhanca do ego com ordem de nos canonica.

    `nx.ego_graph` herda a ordem de iteracao de um set interno do networkx
    (FilterAtlas percorre o set de nos quando o subgrafo e menor que metade do
    grafo). Ordem de set de strings e randomizada por processo via
    PYTHONHASHSEED, o que muda a ordem dos nos, a matriz de adjacencia e o
    layout resultante -- mesmo com seed fixa no spring_layout. Reconstruir o
    subgrafo em ordem alfabetica e o que torna a figura reproduzivel.

    As arestas tambem sao reinseridas de forma canonica. Nao basta ordenar: a
    propria orientacao da tupla que sai de `edges()` varia com o seed (a mesma
    aresta aparece como (X, Y) ou (Y, X)), entao (u, v) e normalizado antes da
    ordenacao. A ordem de insercao define a ordem de desenho -- ou seja, quem
    fica por cima de quem.

    Parameters
    ----------
    grafo : nx.Graph
        Grafo completo.
    ego : str
        No central.
    raio : int
        Profundidade da vizinhanca.

    Returns
    -------
    nx.Graph
        Subgrafo com nos e arestas em ordem alfabetica estavel.
    """
    bruto = nx.ego_graph(grafo, ego, radius=raio)
    sub = nx.Graph()
    sub.add_nodes_from(sorted(bruto.nodes()))
    sub.add_edges_from(
        sorted(
            ((min(u, v), max(u, v), d) for u, v, d in bruto.edges(data=True)),
            key=lambda aresta: (aresta[0], aresta[1]),
        )
    )
    return sub


def encurtar(texto: str, limite: int) -> str:
    """Encurta rotulos longos preservando o inicio do nome.

    Parameters
    ----------
    texto : str
        Texto original do rotulo.
    limite : int
        Numero maximo de caracteres.

    Returns
    -------
    str
        Texto encurtado com reticencias quando excede o limite.
    """
    texto = " ".join(texto.split())
    if len(texto) <= limite:
        return texto
    return texto[: limite - 1].rstrip() + "…"


def _tamanho_no(no: str, graus: dict[str, int], escala: float) -> float:
    """Calcula a area do marcador a partir do grau no grafo completo.

    A raiz quadrada evita que os hubs (grau 50) esmaguem visualmente os nos de
    grau 1, ja que o parametro do matplotlib e area, nao diametro.

    Parameters
    ----------
    no : str
        Identificador do no.
    graus : dict[str, int]
        Mapa no -> grau no grafo completo.
    escala : float
        Fator de escala do marcador.

    Returns
    -------
    float
        Area do marcador para o parametro node_size.
    """
    return 40 + escala * math.sqrt(graus.get(no, 1))


def _desenhar_grafo(
    ax,
    subgrafo: nx.Graph,
    posicoes: dict,
    tipos: dict[str, str],
    graus: dict[str, int],
    ego: str,
    escala: float,
    cor_aresta: str,
    alpha_aresta: float,
    largura_base: float,
    largura_var: float,
    linha_no: float,
) -> None:
    """Desenha arestas e nos do subgrafo no eixo informado.

    Parameters
    ----------
    ax : matplotlib.axes.Axes
        Eixo de destino.
    subgrafo : nx.Graph
        Subgrafo a desenhar.
    posicoes : dict
        Mapa no -> coordenada.
    tipos : dict[str, str]
        Mapa titulo -> tipo.
    graus : dict[str, int]
        Mapa no -> grau no grafo completo.
    ego : str
        No central, desenhado como estrela preta.
    escala : float
        Fator de escala dos marcadores.
    cor_aresta : str
        Cor das arestas.
    alpha_aresta : float
        Transparencia das arestas.
    largura_base : float
        Largura minima da aresta.
    largura_var : float
        Amplitude de largura proporcional ao peso.
    linha_no : float
        Espessura do contorno dos nos.

    Returns
    -------
    None
        Nao retorna valor.
    """
    pesos = [float(d.get("weight", 1.0)) for _, _, d in subgrafo.edges(data=True)]
    menor, maior = min(pesos), max(pesos)
    larguras = [
        largura_base + largura_var * ((p - menor) / (maior - menor) if maior > menor else 0.5)
        for p in pesos
    ]
    nx.draw_networkx_edges(
        subgrafo, posicoes, ax=ax, width=larguras,
        edge_color=cor_aresta, alpha=alpha_aresta,
    )

    for tipo, (marcador, preenchimento) in ESTILO_TIPO.items():
        nos = [
            n for n in subgrafo.nodes()
            if tipos.get(n, "SEM TIPO") == tipo and n != ego
        ]
        if not nos:
            continue
        col = nx.draw_networkx_nodes(
            subgrafo, posicoes, nodelist=nos, ax=ax, node_shape=marcador,
            node_size=[_tamanho_no(n, graus, escala) for n in nos],
            node_color=preenchimento, edgecolors="black", linewidths=linha_no,
        )
        if _e_artefato(tipo):
            col.set_linestyle(TRACEJADO)

    nx.draw_networkx_nodes(
        subgrafo, posicoes, nodelist=[ego], ax=ax, node_shape="*",
        node_size=_tamanho_no(ego, graus, escala) * 3.5,
        node_color="black", edgecolors="black", linewidths=1.2,
    )


def _legenda_rodape(fig, subgrafo: nx.Graph, tipos: dict[str, str]) -> None:
    """Adiciona a legenda no rodape, fora da area do grafo.

    Parameters
    ----------
    fig : matplotlib.figure.Figure
        Figura de destino.
    subgrafo : nx.Graph
        Subgrafo desenhado, usado para listar so os tipos presentes.
    tipos : dict[str, str]
        Mapa titulo -> tipo.

    Returns
    -------
    None
        Nao retorna valor.
    """
    # So entram na legenda os tipos que realmente aparecem neste subgrafo: em
    # profundidade 1 nao ha nenhum no 'geo', e anunciar geo na legenda faria a
    # figura prometer algo que ela nao mostra.
    presentes = [
        t for t in ESTILO_TIPO
        if any(tipos.get(n, "SEM TIPO") == t for n in subgrafo.nodes())
    ]
    configurados = [t for t in presentes if not _e_artefato(t)]
    artefatos = [t for t in presentes if _e_artefato(t)]

    def marcador_de(tipo: str, ax_para_scatter):
        """Handle de legenda; artefatos recebem contorno tracejado."""
        forma, preenchimento = ESTILO_TIPO[tipo]
        if _e_artefato(tipo):
            # Line2D nao suporta contorno tracejado no marcador; um scatter
            # vazio vira PathCollection, que suporta.
            h = ax_para_scatter.scatter(
                [], [], marker=forma, s=70, facecolor=preenchimento,
                edgecolor="black", linewidths=0.9, label=_rotulo_tipo(tipo),
            )
            h.set_linestyle(TRACEJADO)
            return h
        return Line2D([], [], marker=forma, color="none",
                      markerfacecolor=preenchimento, markeredgecolor="black",
                      markersize=8, label=_rotulo_tipo(tipo))

    ax = fig.axes[0]
    blocos = [
        ("Categorias configuradas (entity_types)",
         [marcador_de(t, ax) for t in configurados], 0.20),
        ("Artefatos de extração",
         [marcador_de(t, ax) for t in artefatos], 0.545),
        ("Leitura",
         [Line2D([], [], marker="*", color="none", markerfacecolor="black",
                 markeredgecolor="black", markersize=15, label="ego"),
          Line2D([], [], marker="o", color="none", markerfacecolor="white",
                 markeredgecolor="black", markersize=4, label="tamanho ∝ grau")],
         0.815),
    ]
    for titulo, handles, x in blocos:
        if not handles:
            continue
        leg = fig.legend(
            handles=handles, loc="lower center", bbox_to_anchor=(x, 0.004),
            ncol=len(handles), fontsize=8, frameon=True, framealpha=1.0,
            edgecolor="#BBBBBB", title=titulo, title_fontsize=8.5,
            columnspacing=1.4, borderpad=0.6, handletextpad=0.5,
        )
        leg.get_title().set_fontweight("bold")
        fig.add_artist(leg)


def _salvar(fig, export_dir: Path, nome: str) -> None:
    """Exporta a figura em PNG de alta resolucao e SVG.

    Parameters
    ----------
    fig : matplotlib.figure.Figure
        Figura a exportar.
    export_dir : Path
        Diretorio de destino.
    nome : str
        Nome base do arquivo (sem extensao).

    Returns
    -------
    None
        Nao retorna valor.
    """
    export_dir.mkdir(parents=True, exist_ok=True)
    for extensao in ("png", "svg"):
        arquivo = export_dir / f"{nome}.{extensao}"
        fig.savefig(
            arquivo,
            dpi=DPI_PNG if extensao == "png" else None,
            facecolor="white", bbox_inches="tight", pad_inches=0.2,
            # Sem isso o SVG carrega a data de geracao e nunca sai igual.
            metadata={"Date": None} if extensao == "svg" else None,
        )
        LOGGER.info("Figura exportada: %s", arquivo)
    plt.close(fig)


def gerar_figura_profundidade_1(
    grafo: nx.Graph,
    tipos: dict[str, str],
    graus: dict[str, int],
    ego: str,
    export_dir: Path,
) -> None:
    """Gera a ego-network de profundidade 1 em layout radial.

    Com poucos vizinhos cabe rotular todos. Os nos sao distribuidos no circulo
    com passo coprimo ao total, para que os hubs nao caiam lado a lado e seus
    marcadores grandes nao se sobreponham.

    Parameters
    ----------
    grafo : nx.Graph
        Grafo completo.
    tipos : dict[str, str]
        Mapa titulo -> tipo.
    graus : dict[str, int]
        Mapa no -> grau no grafo completo.
    ego : str
        No central.
    export_dir : Path
        Diretorio de destino das figuras.

    Returns
    -------
    None
        Nao retorna valor.
    """
    sub = subgrafo_ego(grafo, ego, raio=1)
    vizinhos = sorted(
        [n for n in sub.nodes() if n != ego], key=lambda n: (-graus[n], n)
    )
    total = len(vizinhos)

    passo = 13 if math.gcd(13, total) == 1 else 1
    ordenados: list[str] = [""] * total
    for i, no in enumerate(vizinhos):
        ordenados[(i * passo) % total] = no

    posicoes = {ego: np.array([0.0, 0.0])}
    for i, no in enumerate(ordenados):
        angulo = 2 * math.pi * i / total + math.pi / 2
        posicoes[no] = np.array([math.cos(angulo), math.sin(angulo)])

    fig, ax = plt.subplots(figsize=(12, 9.2))
    _desenhar_grafo(
        ax, sub, posicoes, tipos, graus, ego, escala=85,
        cor_aresta="#606060", alpha_aresta=0.5,
        largura_base=0.3, largura_var=1.4, linha_no=0.7,
    )

    for i, no in enumerate(ordenados):
        angulo = 2 * math.pi * i / total + math.pi / 2
        graus_ang = math.degrees(angulo) % 360
        inverter = 90 < graus_ang < 270
        ax.text(
            math.cos(angulo) * 1.10, math.sin(angulo) * 1.10,
            f"{encurtar(no, 34)} ({graus[no]})",
            rotation=graus_ang + 180 if inverter else graus_ang,
            rotation_mode="anchor",
            ha="right" if inverter else "left", va="center",
            fontsize=6.6, path_effects=HALO,
        )

    ax.text(
        0, -0.145, f"{ego} ({graus[ego]})", ha="center", va="top",
        fontsize=8.5, fontweight="bold", path_effects=HALO,
    )
    ax.set_aspect("equal")
    ax.set_xlim(-2.95, 2.95)
    ax.set_ylim(-2.25, 2.25)
    ax.axis("off")

    fig.suptitle(
        f"Ego-network de {ego} — profundidade 1\n"
        f"{sub.number_of_nodes()} nós, {sub.number_of_edges()} arestas · "
        "grau no grafo completo entre parênteses",
        fontsize=11, y=0.975,
    )
    _legenda_rodape(fig, sub, tipos)
    # bottom folgado: a legenda em blocos e mais alta que a lista simples.
    fig.subplots_adjust(top=0.90, bottom=0.13, left=0.02, right=0.98)
    _salvar(fig, export_dir, "ego_jorge_d1")


def gerar_figura_profundidade_2(
    grafo: nx.Graph,
    tipos: dict[str, str],
    graus: dict[str, int],
    ego: str,
    export_dir: Path,
    n_rotulos: int = 16,
) -> None:
    """Gera a ego-network de profundidade 2 com rotulos em colunas laterais.

    Em 175 nos o miolo fica denso demais para rotular no lugar: qualquer rotulo
    cai em cima de no ou aresta. Os rotulos vao para duas colunas fora do grafo,
    ligados por linha-guia, o que garante que todos os hubs sejam identificados.

    Parameters
    ----------
    grafo : nx.Graph
        Grafo completo.
    tipos : dict[str, str]
        Mapa titulo -> tipo.
    graus : dict[str, int]
        Mapa no -> grau no grafo completo.
    ego : str
        No central.
    export_dir : Path
        Diretorio de destino das figuras.
    n_rotulos : int, default=16
        Quantidade de nos de maior grau a rotular.

    Returns
    -------
    None
        Nao retorna valor.
    """
    sub = subgrafo_ego(grafo, ego, raio=2)
    posicoes = nx.spring_layout(sub, k=0.62, iterations=1200, seed=SEMENTE_LAYOUT)

    centro = np.array(list(posicoes.values())).mean(axis=0)
    raio = max(np.linalg.norm(posicoes[n] - centro) for n in sub.nodes())

    fig, ax = plt.subplots(figsize=(13, 8.6))
    _desenhar_grafo(
        ax, sub, posicoes, tipos, graus, ego, escala=105,
        cor_aresta="#666666", alpha_aresta=0.45,
        largura_base=0.3, largura_var=1.3, linha_no=0.65,
    )
    ax.set_aspect("equal")
    ax.set_xlim(centro[0] - raio * 2.15, centro[0] + raio * 2.15)
    ax.set_ylim(centro[1] - raio * 1.18, centro[1] + raio * 1.18)
    ax.axis("off")

    alvos = sorted([n for n in sub.nodes() if n != ego], key=lambda n: (-graus[n], n))
    alvos = alvos[:n_rotulos]
    esquerda = sorted(
        [n for n in alvos if posicoes[n][0] < centro[0]], key=lambda n: posicoes[n][1]
    )
    direita = sorted(
        [n for n in alvos if posicoes[n][0] >= centro[0]], key=lambda n: posicoes[n][1]
    )

    for nos, lado in ((esquerda, -1), (direita, 1)):
        if not nos:
            continue
        x = centro[0] + lado * raio * 1.22
        ys = (
            np.linspace(centro[1] - raio * 1.05, centro[1] + raio * 1.05, len(nos))
            if len(nos) > 1
            else [centro[1]]
        )
        for no, y in zip(nos, ys):
            ax.annotate(
                f"{encurtar(no, 28)} ({graus[no]})",
                xy=posicoes[no], xytext=(x, y),
                ha="right" if lado < 0 else "left", va="center",
                fontsize=7, path_effects=HALO, zorder=6,
                arrowprops=dict(
                    arrowstyle="-", lw=0.5, color="#8A8A8A",
                    shrinkA=0, shrinkB=3, connectionstyle="arc3,rad=0.08",
                ),
            )

    x_ego, y_ego = posicoes[ego]
    ax.text(
        x_ego, y_ego - 0.06, f"{ego} ({graus[ego]})", ha="center", va="top",
        fontsize=8.5, fontweight="bold", path_effects=HALO, zorder=7,
    )

    fig.suptitle(
        f"Ego-network de {ego} — profundidade 2\n"
        f"{sub.number_of_nodes()} nós, {sub.number_of_edges()} arestas · "
        f"rótulos: {n_rotulos} nós de maior grau "
        "(grau no grafo completo entre parênteses)",
        fontsize=11, y=0.975,
    )
    _legenda_rodape(fig, sub, tipos)
    fig.subplots_adjust(top=0.90, bottom=0.07, left=0.02, right=0.98)
    _salvar(fig, export_dir, "ego_jorge_d2")


def criar_parser_argumentos() -> argparse.ArgumentParser:
    """Cria parser de argumentos para execucao via linha de comando.

    Returns
    -------
    argparse.ArgumentParser
        Parser configurado para a geracao das figuras.
    """
    parser = argparse.ArgumentParser(
        description="Gera figuras de ego-network do Knowledge Graph em PNG e SVG.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output"),
        help="Diretorio com os artefatos do GraphRAG (default: output).",
    )
    parser.add_argument(
        "--export-dir",
        type=Path,
        default=Path("docs/diagramas/ego"),
        help="Diretorio de destino (default: docs/diagramas/ego).",
    )
    parser.add_argument(
        "--ego",
        type=str,
        default=EGO_PADRAO,
        help=f"No central da ego-network (default: {EGO_PADRAO}).",
    )
    parser.add_argument(
        "--profundidade",
        type=str,
        choices=["1", "2", "ambas"],
        default="ambas",
        help="Profundidade a gerar (default: ambas).",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        help="Nivel de log (DEBUG, INFO, WARNING, ERROR).",
    )
    return parser


def main() -> int:
    """Gera as figuras de ego-network para a monografia.

    Returns
    -------
    int
        Codigo de status da execucao (0 para sucesso).

    Raises
    ------
    FileNotFoundError
        Quando os artefatos do GraphRAG nao existem.
    KeyError
        Quando o no informado em --ego nao existe no grafo.
    """
    parser = criar_parser_argumentos()
    args = parser.parse_args()
    configurar_logging(nivel=args.log_level)

    grafo, tipos, graus = carregar_contexto(args.output_dir)
    if args.ego not in grafo:
        raise KeyError(f"No nao encontrado no grafo: {args.ego}")

    if args.profundidade in ("1", "ambas"):
        gerar_figura_profundidade_1(grafo, tipos, graus, args.ego, args.export_dir)
    if args.profundidade in ("2", "ambas"):
        gerar_figura_profundidade_2(grafo, tipos, graus, args.ego, args.export_dir)

    LOGGER.info("Geracao de figuras concluida com sucesso.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
