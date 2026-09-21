"""Roda as consultas de scripts/consultas_grafo.sql em uma versao do grafo, com DuckDB.

Nao usa a Azure e nao custa nada: le direto os .parquet.

Uso:
    python scripts/explorar_grafo.py                      # runs/v1-tuned/output
    python scripts/explorar_grafo.py runs/v1-nfc/output   # outra versao
    python scripts/explorar_grafo.py runs/v1-tuned/output --consulta 5
    python scripts/explorar_grafo.py runs/v1-tuned/output --ui   # interface web local
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import duckdb

SQL = Path(__file__).with_name("consultas_grafo.sql")
PASTA_PADRAO = "runs/v1-tuned/output"


def carregar_consultas(pasta: str) -> tuple[list[str], list[tuple[str, str]]]:
    """Separa o SQL em views e consultas numeradas, apontando para a pasta pedida.

    Parameters
    ----------
    pasta : str
        Pasta com os .parquet da versao (ex.: ``runs/v1-nfc/output``).

    Returns
    -------
    tuple[list[str], list[tuple[str, str]]]
        Comandos de criacao das views e pares (titulo, sql) das consultas.
    """

    texto = SQL.read_text(encoding="utf-8").replace(PASTA_PADRAO, pasta.replace("\\", "/"))
    # O proprio DuckDB separa os comandos: dividir por ';' quebraria em comentarios.
    comandos = [s.query.strip().rstrip(";") for s in duckdb.connect().extract_statements(texto)]
    views: list[str] = []
    consultas: list[tuple[str, str]] = []
    for comando in comandos:
        sem_comentario = re.sub(r"^\s*--.*$", "", comando, flags=re.MULTILINE).strip()
        if not sem_comentario:
            continue
        if sem_comentario.upper().startswith("CREATE"):
            views.append(sem_comentario)
            continue
        titulos = re.findall(r"^-- (\d+\..*)$", comando, re.MULTILINE)
        consultas.append((titulos[0] if titulos else sem_comentario[:60], sem_comentario))
    return views, consultas


def main() -> int:
    """Executa as consultas e imprime os resultados."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pasta", nargs="?", default=PASTA_PADRAO)
    parser.add_argument("--consulta", type=int, help="Numero de uma consulta so.")
    parser.add_argument("--linhas", type=int, default=15, help="Linhas por consulta.")
    parser.add_argument("--ui", action="store_true", help="Abre a interface web do DuckDB.")
    args = parser.parse_args()

    views, consultas = carregar_consultas(args.pasta)
    con = duckdb.connect()
    for view in views:
        con.execute(view)

    if args.ui:
        con.execute("INSTALL ui; LOAD ui; CALL start_ui()")
        print(f"Interface do DuckDB aberta no navegador. Views: entidades, relacoes, "
              f"comunidades, relatorios, trechos (de {args.pasta}).")
        input("Enter para encerrar...")
        return 0

    for numero, (titulo, sql) in enumerate(consultas, start=1):
        if args.consulta and numero != args.consulta:
            continue
        print(f"\n=== {titulo}")
        try:
            print(con.sql(sql).df().head(args.linhas).to_string(max_colwidth=70))
        except Exception as erro:  # noqa: BLE001 - diagnostico de consulta
            print(f"  ERRO: {erro}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
