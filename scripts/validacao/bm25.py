"""Baseline lexical da camada 2: BM25 sobre os mesmos trechos do GraphRAG (sem tokens na busca).

Espelha o metodo basic do GraphRAG 3.1.0 em tudo, menos na recuperacao: os mesmos text_units,
os mesmos k = 10 trechos, o mesmo limite de 12.000 tokens de contexto (o200k_base), o mesmo
prompt (prompts/basic_search_system_prompt.txt), o mesmo formato de contexto (id|text) e o
mesmo modelo gerador. So a escolha dos trechos muda: BM25 (Robertson e Zaragoza, 2009) em
vez da similaridade de embeddings. Assim a comparacao basic x bm25 isola o tipo de busca.
"""

from __future__ import annotations

import math
import os
from collections import Counter
from pathlib import Path

import pandas as pd

from normalizacao import chave

K = 10  # basic_search.k, padrao do GraphRAG 3.1.0
MAX_CONTEXTO = 12_000  # basic_search.max_context_tokens, padrao do GraphRAG 3.1.0
K1, B = 1.5, 0.75  # parametros usuais do BM25 Okapi


def termos(texto: str) -> list[str]:
    return chave(texto).split()


class BM25:
    def __init__(self, documentos: list[str]) -> None:
        self.docs = [Counter(termos(d)) for d in documentos]
        self.tamanhos = [sum(d.values()) for d in self.docs]
        self.media = sum(self.tamanhos) / len(self.docs)
        df = Counter(t for d in self.docs for t in d)
        n = len(self.docs)
        self.idf = {t: math.log((n - f + 0.5) / (f + 0.5) + 1) for t, f in df.items()}

    def pontuar(self, consulta: str) -> list[float]:
        q = termos(consulta)
        notas = []
        for d, tam in zip(self.docs, self.tamanhos):
            s = 0.0
            for t in q:
                f = d.get(t, 0)
                if f:
                    s += self.idf[t] * f * (K1 + 1) / (f + K1 * (1 - B + B * tam / self.media))
            notas.append(s)
        return notas


def montar_contexto(text_units: pd.DataFrame, indice: BM25, pergunta: str) -> tuple[str, int]:
    """Mesmo formato e mesmo corte do BasicSearchContext do GraphRAG."""

    import tiktoken

    enc = tiktoken.get_encoding("o200k_base")
    notas = indice.pontuar(pergunta)
    melhores = set(sorted(range(len(notas)), key=lambda i: -notas[i])[:K])
    # como no basic: os trechos escolhidos entram na ordem da tabela, nao na da nota
    linhas = ["id|text"]
    usados = len(enc.encode("id|text\n"))
    for i, (hid, texto) in enumerate(zip(text_units["human_readable_id"], text_units["text"])):
        if i not in melhores:
            continue
        linha = f"{hid}|{texto}"
        n = len(enc.encode(linha + "\n"))
        if usados + n > MAX_CONTEXTO:
            break
        usados += n
        linhas.append(linha)
    return "\n".join(linhas) + "\n", len(linhas) - 1


async def responder_bm25(config, text_units: pd.DataFrame, indice: BM25, raiz: Path, pergunta: str,
                         formato: str) -> tuple[str, dict]:
    import litellm

    contexto, n_trechos = montar_contexto(text_units, indice, pergunta)
    prompt = (raiz / "prompts" / "basic_search_system_prompt.txt").read_text(encoding="utf-8")
    sistema = prompt.format(context_data=contexto, response_type=formato)
    m = config.completion_models["default_completion_model"]
    resposta = await litellm.acompletion(
        model=f"azure/{m.deployment_name}",
        api_base=m.api_base,
        api_version=m.api_version,
        api_key=os.environ["GRAPHRAG_API_KEY"],
        messages=[{"role": "system", "content": sistema}, {"role": "user", "content": pergunta}],
    )
    uso = resposta.usage
    return resposta.choices[0].message.content, {"contexto": {"sources": n_trechos},
                                                 "tokens_entrada": uso.prompt_tokens,
                                                 "tokens_saida": uso.completion_tokens}
