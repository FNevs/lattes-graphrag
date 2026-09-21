"""Consulta uma versao congelada em runs/<versao>/output com o graphrag query.

O ``--data`` do ``graphrag query`` so redireciona os .parquet; o LanceDB continua
em ``output/lancedb`` (settings.yaml). Este script aponta os dois para a mesma
pasta e repassa o resto para a linha de comando do GraphRAG.

Uso:
    python scripts/consultar.py runs/v1-tuned/output --method local --no-streaming "pergunta"
"""

from __future__ import annotations

import sys
from pathlib import Path

import graphrag.cli.query as consulta
from graphrag.cli.main import app


def main() -> int:
    """Ajusta o caminho do LanceDB e executa ``graphrag query``."""

    pasta = Path(sys.argv[1]).resolve()
    carregar_original = consulta.load_config

    def carregar(root_dir, cli_overrides=None):
        extras = dict(cli_overrides or {})
        extras["vector_store"] = {"db_uri": str(pasta / "lancedb")}
        return carregar_original(root_dir=root_dir, cli_overrides=extras)

    consulta.load_config = carregar
    app(["query", "--root", ".", "--data", str(pasta), *sys.argv[2:]])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
