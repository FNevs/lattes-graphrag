"""Camada 2, juiz LLM (gasta tokens): notas Likert e comparacao par a par.

1. Likert 1-5 em cada resposta, nas 4 dimensoes de Jia et al. (2024, DDM-RAG): relevancia,
   acuracia, completude, legibilidade. Para perguntas com gabarito, o juiz recebe a
   referencia tirada do XML, entao a acuracia e julgada contra a fonte, nao contra o que o
   juiz "acha".
2. Par a par nas perguntas globais (Edge et al., 2024; BenchmarkQED/AutoE, Microsoft, 2025):
   abrangencia, diversidade, empoderamento e relevancia, cada par julgado nas duas ordens
   (contrabalanceado); vitoria = 1, empate = 0,5, derrota = 0.

O juiz deve ser outro modelo que nao o gerador (gpt-4.1 julgando gpt-4.1-mini), porque um
modelo tende a preferir o proprio texto. Usar o mesmo modelo e possivel (--juiz
gpt-4.1-mini), com essa limitacao registrada.

Uso:
    .venv\\Scripts\\python.exe scripts\\validacao\\juiz_consultas.py runs\\v2-npai --juiz gpt-4.1
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from collections import defaultdict
from itertools import combinations
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
DIMENSOES = ("relevancia", "acuracia", "completude", "legibilidade")
CRITERIOS = {
    "abrangencia": "Qual resposta cobre mais aspectos relevantes da pergunta, com mais detalhes?",
    "diversidade": "Qual resposta traz perspectivas, exemplos e ângulos mais variados?",
    "empoderamento": "Qual resposta ajuda mais o leitor a entender o tema e a formar um julgamento próprio?",
    "relevancia": "Qual resposta trata mais diretamente do que a pergunta pede, sem desviar?",
}

PROMPT_LIKERT = """Você avalia respostas de um sistema de perguntas sobre currículos Lattes de um grupo de pesquisa.
Dê notas de 1 (péssimo) a 5 (excelente) em quatro dimensões:
- relevancia: a resposta trata do que foi perguntado;
- acuracia: os fatos da resposta estão corretos. {regra_acuracia}
- completude: a resposta cobre os pontos esperados;
- legibilidade: o texto é claro, coerente e bem organizado.

Pergunta: {pergunta}

{referencia}

Resposta avaliada:
<<<
{resposta}
>>>

Responda apenas com JSON: {{"relevancia": n, "acuracia": n, "completude": n, "legibilidade": n, "justificativa": "uma frase"}}"""

PROMPT_PAR = """Você compara duas respostas para a mesma pergunta sobre um grupo de pesquisa (currículos Lattes).

Pergunta: {pergunta}

Resposta 1:
<<<
{r1}
>>>

Resposta 2:
<<<
{r2}
>>>

Para cada critério, diga qual resposta é melhor (1, 2 ou 0 para empate):
{criterios}

Ignore o tamanho por si só e as marcas de citação [Data: ...]. Responda apenas com JSON:
{{"abrangencia": n, "diversidade": n, "empoderamento": n, "relevancia": n}}"""


def referencia(p: dict) -> tuple[str, str]:
    if not p["gabarito"]:
        return ("Não há gabarito: julgue a acurácia pela coerência interna e pela ausência de afirmações "
                "implausíveis.", "Não há referência para esta pergunta.")
    itens = "\n".join(f"- {g['valor']}" for g in p["gabarito"])
    if p["classe"].endswith("-local"):
        return ("Compare com a referência abaixo, extraída do XML dos currículos: itens que não estão nela "
                "devem baixar a nota.", f"Referência (lista correta, extraída do XML):\n{itens}")
    return ("Compare com a referência abaixo (itens mais frequentes nos currículos); afirmações que a "
            "contradizem devem baixar a nota.", f"Referência (itens mais frequentes no XML):\n{itens}")


async def chamar(modelo: str, prompt: str, config) -> tuple[dict, dict]:
    import litellm

    m = config.completion_models["default_completion_model"]
    r = await litellm.acompletion(model=f"azure/{modelo}", api_base=m.api_base, api_version=m.api_version,
                                  api_key=os.environ["GRAPHRAG_API_KEY"], temperature=0,
                                  response_format={"type": "json_object"},
                                  messages=[{"role": "user", "content": prompt}])
    uso = {"tokens_entrada": r.usage.prompt_tokens, "tokens_saida": r.usage.completion_tokens}
    return json.loads(r.choices[0].message.content), uso


async def main_async(pasta: Path, modelo: str) -> None:
    from graphrag.config.load_config import load_config

    config = load_config(RAIZ)  # so para o endpoint e a chave do .env
    base = pasta / "validacao" / "consultas"
    perguntas = {p["id"]: p for p in json.loads((base / "perguntas.json").read_text(encoding="utf-8"))}
    respostas = defaultdict(dict)
    for arq in sorted((base / "respostas").glob("*.json")):
        r = json.loads(arq.read_text(encoding="utf-8"))
        respostas[r["id"]][r["metodo"]] = r["resposta"]
    destino = base / f"juiz_{modelo}.json"
    feito = json.loads(destino.read_text(encoding="utf-8")) if destino.exists() else {"likert": {}, "pares": {}}

    def salvar() -> None:
        destino.write_text(json.dumps(feito, ensure_ascii=False, indent=2), encoding="utf-8")

    for qid, por_metodo in respostas.items():
        p = perguntas[qid]
        regra, ref = referencia(p)
        for metodo, texto in por_metodo.items():
            chave_l = f"{qid}|{metodo}"
            if chave_l in feito["likert"]:
                continue
            nota, uso = await chamar(modelo, PROMPT_LIKERT.format(regra_acuracia=regra, pergunta=p["pergunta"],
                                                                  referencia=ref, resposta=texto), config)
            feito["likert"][chave_l] = {**nota, **uso}
            salvar()
            print(f"likert {chave_l:24s} {[nota.get(d) for d in DIMENSOES]}", flush=True)
        if p["classe"].endswith("-global"):
            for a, b in combinations(sorted(por_metodo), 2):
                for ordem in ((a, b), (b, a)):
                    chave_p = f"{qid}|{ordem[0]}|{ordem[1]}"
                    if chave_p in feito["pares"]:
                        continue
                    criterios = "\n".join(f"- {k}: {v}" for k, v in CRITERIOS.items())
                    voto, uso = await chamar(modelo, PROMPT_PAR.format(pergunta=p["pergunta"], r1=por_metodo[ordem[0]],
                                                                       r2=por_metodo[ordem[1]], criterios=criterios), config)
                    feito["pares"][chave_p] = {**voto, **uso}
                    salvar()
                    print(f"par    {chave_p:32s} {voto}", flush=True)
    resumir(feito, destino.with_suffix(".md"), modelo)


def resumir(feito: dict, saida: Path, modelo: str) -> None:
    notas = defaultdict(lambda: defaultdict(list))
    for chave_l, v in feito["likert"].items():
        _, metodo = chave_l.split("|")
        for d in DIMENSOES:
            if isinstance(v.get(d), (int, float)):
                notas[metodo][d].append(v[d])
    vitorias = defaultdict(lambda: defaultdict(float))
    jogos = defaultdict(lambda: defaultdict(int))
    for chave_p, v in feito["pares"].items():
        _, m1, m2 = chave_p.split("|")
        for c in CRITERIOS:
            voto = v.get(c)
            for m in (m1, m2):
                jogos[m][c] += 1
            if voto == 1:
                vitorias[m1][c] += 1
            elif voto == 2:
                vitorias[m2][c] += 1
            else:
                vitorias[m1][c] += 0.5
                vitorias[m2][c] += 0.5
    linhas = [f"# Camada 2 — juiz LLM ({modelo})", "", "## Likert (média, 1 a 5)", "",
              "| método | n | " + " | ".join(DIMENSOES) + " |", "|---|---|" + "---|" * len(DIMENSOES)]
    for metodo, ds in sorted(notas.items()):
        n = len(next(iter(ds.values()), []))
        linhas.append(f"| {metodo} | {n} | " + " | ".join(f"{sum(ds[d]) / len(ds[d]):.2f}" for d in DIMENSOES) + " |")
    if jogos:
        linhas += ["", "## Par a par nas perguntas globais (taxa de vitória)", "",
                   "| método | " + " | ".join(CRITERIOS) + " |", "|---|" + "---|" * len(CRITERIOS)]
        for metodo in sorted(jogos):
            linhas.append(f"| {metodo} | " + " | ".join(f"{vitorias[metodo][c] / jogos[metodo][c]:.2f}"
                                                        for c in CRITERIOS) + " |")
    entrada = sum(v.get("tokens_entrada", 0) for g in feito.values() for v in g.values())
    saida_t = sum(v.get("tokens_saida", 0) for g in feito.values() for v in g.values())
    linhas += ["", f"Tokens do juiz (pela resposta da API): {entrada:,} entrada, {saida_t:,} saída. "
                   "O custo de referência é o medidor da Azure.", ""]
    saida.write_text("\n".join(linhas), encoding="utf-8")
    print("\n".join(linhas))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("pasta", type=Path)
    parser.add_argument("--juiz", default="gpt-4.1", help="nome do deployment do modelo juiz")
    args = parser.parse_args()
    asyncio.run(main_async(args.pasta, args.juiz))


if __name__ == "__main__":
    main()
