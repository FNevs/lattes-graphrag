"""Camada 2: concordância entre a avaliação humana e o avaliador gpt-4.1 (sem tokens).

Lê as notas preenchidas em runs/<versao>/validacao/concordancia/avaliacao_humana.xlsx e a
chave da amostra (chave_amostra.json, com o método e as notas do avaliador de cada linha),
e calcula, por dimensão: kappa de Cohen com peso quadrático (escala ordinal de 1 a 5),
concordância exata e concordância com diferença de até 1 ponto.

Uso:
    python scripts\\validacao\\concordancia.py runs\\v2-npai
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from openpyxl import load_workbook

DIMENSOES = ("relevancia", "acuracia", "completude", "legibilidade")
COLUNAS = {"relevancia": 6, "acuracia": 7, "completude": 8, "legibilidade": 9}  # F a I


def kappa_quadratico(a: list[int], b: list[int], k: int = 5) -> float | None:
    n = len(a)
    if n == 0:
        return None
    obs = [[0.0] * k for _ in range(k)]
    for x, y in zip(a, b):
        obs[x - 1][y - 1] += 1
    pa = [sum(obs[i]) / n for i in range(k)]
    pb = [sum(obs[i][j] for i in range(k)) / n for j in range(k)]
    peso = lambda i, j: (i - j) ** 2 / (k - 1) ** 2  # noqa: E731
    o = sum(peso(i, j) * obs[i][j] / n for i in range(k) for j in range(k))
    e = sum(peso(i, j) * pa[i] * pb[j] for i in range(k) for j in range(k))
    return None if e == 0 else 1 - o / e  # e == 0: sem variação nas notas, kappa indefinido


def main() -> None:
    pasta = Path(sys.argv[1] if len(sys.argv) > 1 else "runs/v2-npai") / "validacao" / "concordancia"
    chave = json.loads((pasta / "chave_amostra.json").read_text(encoding="utf-8"))
    ws = load_workbook(pasta / "avaliacao_humana.xlsx", data_only=True)["Avaliacao"]
    resultado, faltando = {}, []
    for d in DIMENSOES:
        humano, juiz = [], []
        for c in chave:
            h = ws.cell(row=c["n"] + 1, column=COLUNAS[d]).value
            if not isinstance(h, (int, float)):
                faltando.append(f"linha {c['n']} {d}")
                continue
            humano.append(int(h))
            juiz.append(int(c["juiz"][d]))
        n = len(humano)
        resultado[d] = {
            "n": n,
            "kappa_quadratico": round(k, 3) if (k := kappa_quadratico(humano, juiz)) is not None else None,
            "concordancia_exata": round(sum(h == j for h, j in zip(humano, juiz)) / n, 3) if n else None,
            "concordancia_1_ponto": round(sum(abs(h - j) <= 1 for h, j in zip(humano, juiz)) / n, 3) if n else None,
            "media_humano": round(sum(humano) / n, 2) if n else None,
            "media_juiz": round(sum(juiz) / n, 2) if n else None,
        }
    (pasta / "concordancia.json").write_text(json.dumps({"faltando": faltando, "por_dimensao": resultado},
                                                        ensure_ascii=False, indent=2), encoding="utf-8")
    if faltando:
        print(f"aviso: {len(faltando)} notas em branco: {', '.join(faltando[:8])}")
    for d, r in resultado.items():
        print(f"{d:13s} n={r['n']:2d} kappa={r['kappa_quadratico']} exata={r['concordancia_exata']} "
              f"±1={r['concordancia_1_ponto']} média humano={r['media_humano']} juiz={r['media_juiz']}")


if __name__ == "__main__":
    main()
