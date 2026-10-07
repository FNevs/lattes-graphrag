"""Exporta as respostas da camada 2 da validacao para a aba Consultas do site (custo zero).

Le runs/<versao>/validacao/consultas/ (perguntas, respostas, avaliacao deterministica e
juiz) e grava site/dados/<versao>.consultas.json, ignorado pelo Git (tem nomes reais).
Nada e consultado de novo: o site so mostra o que ja foi gerado e pago.

Uso: .venv\\Scripts\\python.exe scripts\\exportar_consultas_site.py runs\\v2-npai
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
NOME_METODO = {"global": "Global", "local": "Local", "basic": "Basic (RAG vetorial)",
               "sem_contexto": "Sem contexto (modelo sozinho)"}
NOME_CLASSE = {"dado-local": "Sobre um pesquisador", "atividade-local": "Colaboração",
               "dado-global": "Sobre o grupo", "atividade-global": "Análise aberta"}
ORDEM = ("global", "local", "basic", "sem_contexto")


def main() -> None:
    pasta = Path(sys.argv[1] if len(sys.argv) > 1 else "runs/v2-npai")
    base = pasta / "validacao" / "consultas"
    perguntas = json.loads((base / "perguntas.json").read_text(encoding="utf-8"))
    avaliacao = {(a["id"], a["metodo"]): a for a in
                 json.loads((base / "avaliacao_deterministica.json").read_text(encoding="utf-8"))}
    juiz_arq = next(base.glob("juiz_*.json"), None)
    juiz = json.loads(juiz_arq.read_text(encoding="utf-8"))["likert"] if juiz_arq else {}

    saida = []
    for p in perguntas:
        for metodo in ORDEM:
            arq = base / "respostas" / f"{p['id']}_{metodo}.json"
            if not arq.exists():
                continue
            r = json.loads(arq.read_text(encoding="utf-8"))
            item = {"id": p["id"], "classe": NOME_CLASSE.get(p["classe"], p["classe"]),
                    "pergunta": p["pergunta"], "metodo": NOME_METODO.get(metodo, metodo),
                    "resposta": r["resposta"]}
            a = avaliacao.get((p["id"], metodo), {})
            if a.get("cobertura") is not None:
                item["cobertura"] = round(a["cobertura"], 2)
            if a.get("alucinados") is not None:
                item["alucinados"] = a["alucinados"]
            nota = juiz.get(f"{p['id']}|{metodo}")
            if nota:
                item["nota"] = {k: nota[k] for k in ("relevancia", "acuracia", "completude", "legibilidade") if k in nota}
            saida.append(item)
    destino = RAIZ / "site" / "dados" / f"{pasta.name}.consultas.json"
    destino.write_text(json.dumps(saida, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(saida)} respostas de {len(perguntas)} perguntas -> {destino}")


if __name__ == "__main__":
    main()
