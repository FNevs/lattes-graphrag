"""Custo real de uma janela de horario, pelas metricas de tokens do recurso na Azure.

O log do GraphRAG subconta ~5% e nao registra as consultas; o medidor e a referencia
(docs/REGISTRO-EXECUCAO-TCC2.md, secao 2). Precisa do `az login` feito.

Uso: .venv\\Scripts\\python.exe scripts\\validacao\\medir_custo.py 2026-10-07T19:15:00Z 2026-10-07T19:30:00Z
"""

from __future__ import annotations

import json
import subprocess
import sys
from collections import defaultdict

RECURSO = ("lattes-graphrag-tcc", "rg-lattes-graphrag")
# US$ por 1 M de tokens (entrada, saida); mesmos precos do litellm
PRECOS = {"gpt-4.1-mini": (0.40, 1.60), "gpt-4.1": (2.00, 8.00), "text-embedding-3-small": (0.02, 0.0)}


def az(*args: str) -> str:
    return subprocess.run(["az", *args], capture_output=True, text=True, check=True, shell=True).stdout


def tokens(recurso_id: str, metrica: str, inicio: str, fim: str) -> dict[str, int]:
    saida = json.loads(az("monitor", "metrics", "list", "--resource", recurso_id, "--metric", metrica,
                          "--start-time", inicio, "--end-time", fim, "--interval", "PT1M",
                          "--aggregation", "Total", "--filter", "ModelDeploymentName eq '*'", "-o", "json"))
    total: dict[str, int] = defaultdict(int)
    for serie in saida["value"][0]["timeseries"]:
        nome = serie["metadatavalues"][0]["value"] if serie.get("metadatavalues") else "?"
        total[nome] += int(sum(p.get("total") or 0 for p in serie["data"]))
    return dict(total)


def main() -> None:
    inicio, fim = sys.argv[1], sys.argv[2]
    rid = az("cognitiveservices", "account", "show", "-n", RECURSO[0], "-g", RECURSO[1], "--query", "id", "-o", "tsv").strip()
    entrada = tokens(rid, "ProcessedPromptTokens", inicio, fim)
    saida = tokens(rid, "GeneratedTokens", inicio, fim)
    custo_total = 0.0
    for modelo in sorted(set(entrada) | set(saida)):
        pe, ps = PRECOS.get(modelo, (0.0, 0.0))
        e, s = entrada.get(modelo, 0), saida.get(modelo, 0)
        custo = e * pe / 1e6 + s * ps / 1e6
        custo_total += custo
        print(f"{modelo:24s} entrada {e:>11,}  saída {s:>9,}  US$ {custo:.4f}")
    print(f"{'total':24s} US$ {custo_total:.4f}  ({inicio} a {fim})")


if __name__ == "__main__":
    main()
