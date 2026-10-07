"""Camada 2: roda as perguntas de perguntas.json no GraphRAG (gasta tokens).

Metodos por classe de pergunta (docs/PLANO-VALIDACAO-TCC2.md, secao 4):
- dado-local e atividade-local: basic (RAG vetorial puro), local, sem contexto (o modelo
  sozinho, piso de comparacao);
- dado-global e atividade-global: global (nivel de comunidade 1), local, basic.

Cada resposta vai para runs/<versao>/validacao/consultas/respostas/<id>_<metodo>.json. Uma
resposta ja gravada nunca e refeita (o GraphRAG nao usa cache em consultas: refazer custa
de novo). O custo real vem do medidor da Azure, pela janela de horario gravada em
execucoes.jsonl.

Uso:
    .venv\\Scripts\\python.exe scripts\\validacao\\executar_consultas.py runs\\v2-npai            # tudo
    .venv\\Scripts\\python.exe scripts\\validacao\\executar_consultas.py runs\\v2-npai q04 q12    # so estas
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parents[2]
NIVEL_GLOBAL = 1  # ~US$ 0,20 por pergunta no V2 (nivel 2 chega a ~US$ 0,70)
NIVEL_LOCAL = 2  # padrao da CLI
FORMATO_LISTA = ("Lista em português, com um item por linha, cada linha começando com '- ' e trazendo "
                 "primeiro o nome do item; sem introdução nem conclusão")
FORMATO_TEXTO = "Vários parágrafos em português"
METODOS = {
    "dado-local": ("basic", "local", "sem_contexto"),
    "atividade-local": ("basic", "local", "sem_contexto"),
    "dado-global": ("global", "local", "basic"),
    "atividade-global": ("global", "local", "basic"),
}


def agora() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


async def sem_contexto(config, pergunta: str, formato: str) -> tuple[str, dict]:
    """O mesmo modelo, sem grafo nem trechos: o piso da comparacao (Pires et al., 2024)."""

    import litellm

    m = config.completion_models["default_completion_model"]
    resposta = await litellm.acompletion(
        model=f"azure/{m.deployment_name}",
        api_base=m.api_base,
        api_version=m.api_version,
        api_key=os.environ["GRAPHRAG_API_KEY"],
        messages=[
            {"role": "system", "content": f"Responda à pergunta do usuário. Formato da resposta: {formato}."},
            {"role": "user", "content": pergunta},
        ],
    )
    uso = resposta.usage
    return resposta.choices[0].message.content, {"tokens_entrada": uso.prompt_tokens, "tokens_saida": uso.completion_tokens}


async def responder(api, config, dados: dict, metodo: str, pergunta: str, formato: str) -> tuple[str, dict]:
    if metodo == "basic":
        resp, ctx = await api.basic_search(config=config, text_units=dados["text_units"],
                                           response_type=formato, query=pergunta)
    elif metodo == "local":
        resp, ctx = await api.local_search(config=config, entities=dados["entities"], communities=dados["communities"],
                                           community_reports=dados["community_reports"], text_units=dados["text_units"],
                                           relationships=dados["relationships"], covariates=None,
                                           community_level=NIVEL_LOCAL, response_type=formato, query=pergunta)
    elif metodo == "global":
        resp, ctx = await api.global_search(config=config, entities=dados["entities"], communities=dados["communities"],
                                            community_reports=dados["community_reports"], community_level=NIVEL_GLOBAL,
                                            dynamic_community_selection=False, response_type=formato, query=pergunta)
    else:
        return await sem_contexto(config, pergunta, formato)
    tamanhos = {k: len(v) for k, v in ctx.items()} if isinstance(ctx, dict) else {}
    return str(resp), {"contexto": tamanhos}


async def main_async(pasta: Path, escolhidas: set[str]) -> None:
    import graphrag.api as api
    from graphrag.config.load_config import load_config

    saida = (pasta / "output").resolve()
    config = load_config(RAIZ, cli_overrides={"output_storage": {"base_dir": str(saida)},
                                               "vector_store": {"db_uri": str(saida / "lancedb")}})
    dados = {nome: pd.read_parquet(saida / f"{nome}.parquet")
             for nome in ("entities", "communities", "community_reports", "text_units", "relationships")}
    base = pasta / "validacao" / "consultas"
    perguntas = json.loads((base / "perguntas.json").read_text(encoding="utf-8"))
    destino = base / "respostas"
    destino.mkdir(exist_ok=True)
    registro = base / "execucoes.jsonl"

    for p in perguntas:
        if escolhidas and p["id"] not in escolhidas:
            continue
        objetiva = p["classe"].endswith("-local")
        formato = FORMATO_LISTA if objetiva else FORMATO_TEXTO
        for metodo in METODOS[p["classe"]]:
            arquivo = destino / f"{p['id']}_{metodo}.json"
            if arquivo.exists():
                continue
            inicio, t0 = agora(), time.time()
            try:
                texto, extra = await responder(api, config, dados, metodo, p["pergunta"], formato)
                erro = None
            except Exception as e:  # registra e segue: uma falha nao derruba o lote
                texto, extra, erro = "", {}, f"{type(e).__name__}: {e}"
            linha = {"id": p["id"], "metodo": metodo, "inicio": inicio, "fim": agora(),
                     "segundos": round(time.time() - t0, 1), "erro": erro, **extra}
            with registro.open("a", encoding="utf-8") as f:
                f.write(json.dumps(linha, ensure_ascii=False) + "\n")
            if erro:
                print(f"{p['id']} {metodo:12s} ERRO {erro[:120]}", flush=True)
                continue
            arquivo.write_text(json.dumps({"id": p["id"], "metodo": metodo, "pergunta": p["pergunta"],
                                           "formato": formato, "resposta": texto, **linha},
                                          ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"{p['id']} {metodo:12s} {linha['segundos']:6.1f} s  {len(texto):5d} caracteres", flush=True)


def main() -> None:
    pasta = Path(sys.argv[1] if len(sys.argv) > 1 else "runs/v2-npai")
    asyncio.run(main_async(pasta, set(sys.argv[2:])))


if __name__ == "__main__":
    main()
