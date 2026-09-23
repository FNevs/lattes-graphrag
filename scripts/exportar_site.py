"""Exporta o grafo de uma ou mais versoes para JSON, para a pagina em site/.

Le apenas os .parquet de runs/<versao>/output com DuckDB: nao chama a Azure e nao
custa nada. As arestas usam indices dos nos (arquivo menor) e os relatorios de
comunidade vao para um arquivo separado, carregado sob demanda pela pagina.

Uso:
    python scripts/exportar_site.py                      # todas as versoes em runs/
    python scripts/exportar_site.py runs/v2-npai         # uma versao
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import duckdb
import pandas as pd

SAIDA = Path("site/dados")
PRODUCOES = ("PUBLICATION", "SOFTWARE", "PROJECT")
TAMANHO_DESCRICAO = 400
DESCRICOES = {
    "v0-tcc1": "TCC1: 1 curriculo, gpt-4o-mini, GraphRAG 3.0.4, texto NFKC, prompts padrao.",
    "v1-base-nfkc": "Mesmo curriculo e texto do TCC1 com gpt-4.1-mini e GraphRAG 3.1.0.",
    "v1-nfc": "Correcao da normalizacao: NFC no lugar de NFKC.",
    "v1-tuned": "Prompts adaptados ao dominio Lattes, 9 tipos de entidade, saidas em portugues.",
    "v1-formatoE": "Extrator reescrito: um registro do Lattes por linha (diagnostico, sem relatorios).",
    "v2-npai": "Os 8 curriculos do NPAI, formato novo e nome do titular em cada chunk.",
}


def texto(valor) -> str:
    """Converte valor de coluna (que pode ser NA do pandas) em string."""

    return "" if valor is None or pd.isna(valor) else str(valor)


def numero(valor) -> float:
    """Converte valor de coluna (que pode ser NA do pandas) em float."""

    return 0.0 if valor is None or pd.isna(valor) else float(valor)


def tabela(con: duckdb.DuckDBPyConnection, pasta: Path, nome: str):
    """Registra um .parquet como view, se ele existir."""

    arquivo = pasta / f"{nome}.parquet"
    if not arquivo.exists():
        return False
    con.execute(f"CREATE OR REPLACE VIEW {nome} AS SELECT * FROM '{arquivo.as_posix()}'")
    return True


def exportar(versao_dir: Path) -> dict | None:
    """Gera os JSON de uma versao e devolve o resumo dela."""

    pasta = versao_dir / "output"
    con = duckdb.connect()
    if not tabela(con, pasta, "entities") or not tabela(con, pasta, "relationships"):
        print(f"  {versao_dir.name}: sem entities/relationships, pulando")
        return None
    tem_comunidades = tabela(con, pasta, "communities")
    tem_relatorios = tabela(con, pasta, "community_reports")
    tem_docs = tabela(con, pasta, "documents")
    tem_trechos = tabela(con, pasta, "text_units")

    entidades = con.sql(f"""
        SELECT title, type, degree, frequency, left(description, {TAMANHO_DESCRICAO}) AS description
        FROM entities ORDER BY degree DESC, title""").df()
    indice = {t: i for i, t in enumerate(entidades["title"])}

    # Curriculos em que cada entidade aparece (equivalente aos "dominios" do viewer).
    por_pesquisador: dict[str, list[int]] = {}
    pesquisadores: list[dict] = []
    if tem_docs and tem_trechos:
        docs = con.sql("SELECT id, title FROM documents ORDER BY title").df()
        # "<titular> - <id>.txt" nas versoes novas; nas antigas, so o id do Lattes.
        nomes = {r.id: r.title.removesuffix(".txt").rsplit(" - ", 1)[0] for r in docs.itertuples()}
        vinculo = con.sql("""
            SELECT e.title AS entidade, t.document_id AS doc
            FROM entities e, unnest(e.text_unit_ids) AS u(uid)
            JOIN text_units t ON t.id = u.uid GROUP BY 1, 2""").df()
        ordem = {d: i for i, d in enumerate(docs["id"])}
        for linha in vinculo.itertuples():
            por_pesquisador.setdefault(linha.entidade, []).append(ordem[linha.doc])
        contagem = vinculo.groupby("doc").size().to_dict()
        graus = dict(zip(entidades["title"], entidades["degree"]))
        for doc_id, i in ordem.items():
            nome = nomes[doc_id]
            pesquisadores.append({
                "i": i, "nome": nome, "entidades": int(contagem.get(doc_id, 0)),
                "grau": int(graus.get(nome.upper(), 0)),
                # indice do no do titular; None se o nome nao casar exatamente
                "no": indice.get(nome.upper()),
            })

    nos = [
        {
            "t": r.title, "y": r.type, "d": int(r.degree), "f": int(r.frequency),
            "s": texto(r.description), "p": sorted(por_pesquisador.get(r.title, [])),
        }
        for r in entidades.itertuples()
    ]

    relacoes = con.sql("SELECT source, target, weight, left(description, 300) AS description FROM relationships").df()
    arestas = [
        [indice[r.source], indice[r.target], round(numero(r.weight) or 1.0, 1), texto(r.description)]
        for r in relacoes.itertuples()
        if r.source in indice and r.target in indice
    ]

    comunidades = []
    if tem_comunidades:
        colunas = "c.community AS id, c.level, c.parent, c.size, c.title"
        # Titulo do relatorio quando existe: "Community 16" nao diz nada a quem le.
        sql = (f"SELECT {colunas}, r.summary, r.rank, r.title AS titulo_relatorio FROM communities c "
               "LEFT JOIN community_reports r ON r.community = c.community AND r.level = c.level"
               if tem_relatorios else
               f"SELECT {colunas}, NULL AS summary, NULL AS rank, NULL AS titulo_relatorio FROM communities c")
        for r in con.sql(sql + " ORDER BY c.level, c.size DESC").df().itertuples():
            comunidades.append({
                "id": int(r.id), "n": int(r.level), "pai": int(r.parent), "tam": int(r.size),
                "t": texto(r.titulo_relatorio) or r.title, "s": texto(r.summary)[:600], "nota": numero(r.rank),
            })
        # comunidade de nivel 0 de cada no, para colorir
        nivel0 = con.sql("""
            SELECT c.community AS id, e.title AS entidade
            FROM communities c, unnest(c.entity_ids) AS u(eid)
            JOIN entities e ON e.id = u.eid WHERE c.level = 0""").df()
        for r in nivel0.itertuples():
            if r.entidade in indice:
                nos[indice[r.entidade]]["c"] = int(r.id)

    # Rede de coautoria: pessoas que dividem a mesma producao (caminho de dois passos).
    coautoria = con.sql(f"""
        WITH autoria AS (
          SELECT p.title AS pessoa, o.title AS prod FROM relationships r
          JOIN entities p ON p.title = r.source AND p.type = 'PERSON'
          JOIN entities o ON o.title = r.target AND o.type IN {PRODUCOES}
          UNION
          SELECT p.title, o.title FROM relationships r
          JOIN entities p ON p.title = r.target AND p.type = 'PERSON'
          JOIN entities o ON o.title = r.source AND o.type IN {PRODUCOES})
        SELECT a.pessoa AS p1, b.pessoa AS p2, count(*) AS n
        FROM autoria a JOIN autoria b ON a.prod = b.prod AND a.pessoa < b.pessoa
        GROUP BY 1, 2 HAVING count(*) >= 2 ORDER BY 3 DESC LIMIT 4000""").df()
    pares = [[indice[r.p1], indice[r.p2], int(r.n)] for r in coautoria.itertuples()
             if r.p1 in indice and r.p2 in indice]

    # Rede entre os titulares, para a visao geral: quantas producoes cada par divide
    # e alguns titulos de exemplo (o painel mostra ao clicar na aresta).
    rede_titulares = []
    titulares = {p["nome"].upper(): p["i"] for p in pesquisadores}
    if len(titulares) > 1:
        lista = ", ".join("'" + n.replace("'", "''") + "'" for n in titulares)
        comuns = con.sql(f"""
            WITH autoria AS (
              SELECT p.title AS pessoa, o.title AS prod FROM relationships r
              JOIN entities p ON p.title = r.source AND p.type = 'PERSON'
              JOIN entities o ON o.title = r.target AND o.type IN {PRODUCOES}
              UNION
              SELECT p.title, o.title FROM relationships r
              JOIN entities p ON p.title = r.target AND p.type = 'PERSON'
              JOIN entities o ON o.title = r.source AND o.type IN {PRODUCOES})
            SELECT a.pessoa AS p1, b.pessoa AS p2, count(*) AS n,
                   list(a.prod ORDER BY a.prod)[1:12] AS exemplos
            FROM autoria a JOIN autoria b ON a.prod = b.prod AND a.pessoa < b.pessoa
            WHERE upper(a.pessoa) IN ({lista}) AND upper(b.pessoa) IN ({lista})
            GROUP BY 1, 2 ORDER BY 3 DESC""").df()
        for r in comuns.itertuples():
            rede_titulares.append([titulares[r.p1.upper()], titulares[r.p2.upper()], int(r.n), list(r.exemplos)])

    manifesto = {}
    arquivo_manifesto = versao_dir / "MANIFEST.json"
    if arquivo_manifesto.exists():
        # utf-8-sig: os manifestos gravados pelo PowerShell vem com BOM.
        manifesto = json.loads(arquivo_manifesto.read_text(encoding="utf-8-sig"))

    dados = {
        "meta": {
            "versao": versao_dir.name,
            "descricao": DESCRICOES.get(versao_dir.name, manifesto.get("descricao", "")),
            "data": manifesto.get("data_indexacao", ""),
            "modelo": manifesto.get("modelo_chat", ""),
            "custo": manifesto.get("custo_usd_medidor_azure"),
            "curriculos": len(pesquisadores) or len(manifesto.get("curriculos", [])),
            "entidades": len(nos), "relacoes": len(arestas),
            "comunidades": len(comunidades), "relatorios": tem_relatorios,
            "isoladas": sum(1 for n in nos if n["d"] == 0),
        },
        "pesquisadores": pesquisadores,
        "tipos": entidades["type"].value_counts().to_dict(),
        "nos": nos, "arestas": arestas, "comunidades": comunidades, "coautoria": pares,
        "rede_titulares": rede_titulares,
    }
    SAIDA.mkdir(parents=True, exist_ok=True)
    destino = SAIDA / f"{versao_dir.name}.json"
    destino.write_text(json.dumps(dados, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    if tem_relatorios:
        relatorios = con.sql("SELECT community AS id, level AS n, title AS t, full_content AS c, rank FROM community_reports").df()
        (SAIDA / f"{versao_dir.name}.relatorios.json").write_text(
            json.dumps({str(r.id): {"t": texto(r.t), "c": texto(r.c), "nota": numero(r.rank), "n": int(r.n)}
                        for r in relatorios.itertuples()}, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8")

    tamanho = destino.stat().st_size / 1e6
    print(f"  {versao_dir.name}: {len(nos)} nos, {len(arestas)} arestas, "
          f"{len(comunidades)} comunidades, {len(pares)} pares de coautoria -> {tamanho:.1f} MB")
    return dados["meta"]


def main() -> int:
    """Exporta as versoes pedidas e grava o indice versoes.json."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("versoes", nargs="*", type=Path, help="Pastas runs/<versao> (padrao: todas).")
    args = parser.parse_args()

    versoes = args.versoes or sorted(p for p in Path("runs").iterdir()
                                     if (p / "output" / "entities.parquet").exists())
    if not versoes:
        print("Nenhuma versao encontrada em runs/", file=sys.stderr)
        return 1

    metas = [m for v in versoes if (m := exportar(v))]
    SAIDA.mkdir(parents=True, exist_ok=True)
    # Mescla com o indice existente: exportar uma versao nao pode tirar as outras do seletor.
    indice_arquivo = SAIDA / "versoes.json"
    anteriores = json.loads(indice_arquivo.read_text(encoding="utf-8")) if indice_arquivo.exists() else []
    por_versao = {m["versao"]: m for m in anteriores if (SAIDA / f"{m['versao']}.json").exists()}
    por_versao.update({m["versao"]: m for m in metas})
    indice_arquivo.write_text(
        json.dumps(sorted(por_versao.values(), key=lambda m: m["entidades"], reverse=True),
                   ensure_ascii=False, indent=1),
        encoding="utf-8")
    print(f"{len(metas)} versoes exportadas para {SAIDA}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
