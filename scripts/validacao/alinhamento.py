"""Alinha cada entidade do grafo aos itens do gabarito (registros do XML).

Quatro caminhos:
1. pessoas: compatibilidade de nome com o catalogo (ID do CNPq, grafias e citacoes);
2. demais itens (titulos, instituicoes, eventos, cursos, areas): chave igual ou semelhanca
   aproximada (`rapidfuzz`), com corte minimo de 85;
2b. contencao: um nome e trecho do outro, com pelo menos 2 palavras e 12 letras (90 se o
   trecho cobre metade do nome maior, 86 se menos);
3. texto do registro: a chave de uma entidade que nao e pessoa aparece, como palavras
   inteiras, no texto do registro (titulos, descricoes, resumo).

Cada casamento guarda a pontuacao (0 a 100); as metricas escolhem o limiar depois, o que
permite a analise de sensibilidade sem refazer o alinhamento.
"""

from __future__ import annotations

import bisect
from collections import defaultdict
from dataclasses import dataclass

import numpy as np
from rapidfuzz import fuzz, process

from gabarito import Catalogo, Registro
from normalizacao import PARTICULAS, chave, pontuar_pessoa

CORTE = 85  # abaixo disto nada e registrado
TAMANHO_MINIMO_APROXIMADO = 6  # chaves curtas ("uneb", "ufba") so casam por igualdade


@dataclass(frozen=True)
class Casamento:
    entidade: str
    rid: int
    item: int  # indice do item no registro; -1 = texto livre
    classe: str
    score: float
    via: str  # pessoa, exato, aproximado, texto


def _indices_de_itens(registros: list[Registro]) -> tuple[dict[str, list[tuple[int, int, str]]], dict[str, list[tuple[int, int]]]]:
    """Mapas: chave de item (nao pessoa) -> ocorrencias; pessoa -> ocorrencias."""

    por_chave: dict[str, list[tuple[int, int, str]]] = defaultdict(list)
    por_pessoa: dict[str, list[tuple[int, int]]] = defaultdict(list)
    for reg in registros:
        for i, item in enumerate(reg.itens):
            if item.classe == "pessoa":
                if item.pessoa:
                    por_pessoa[item.pessoa].append((reg.rid, i))
            elif item.chave:
                por_chave[item.chave].append((reg.rid, i, item.classe))
    return por_chave, por_pessoa


def _indice_de_sobrenomes(catalogo: Catalogo) -> dict[str, set[str]]:
    """Palavra de nome (sem particulas, mais de 1 letra) -> pessoas que a usam."""

    indice: dict[str, set[str]] = defaultdict(set)
    for pid, p in catalogo.pessoas.items():
        for nome in p.nomes | p.citacoes:
            for t in nome.split():
                if len(t) > 1 and t not in PARTICULAS:
                    indice[t].add(pid)
    return indice


def alinhar(entidades: list[tuple[str, str]], registros: list[Registro], catalogo: Catalogo) -> list[Casamento]:
    """`entidades` = [(titulo, tipo)]. Devolve todos os casamentos com pontuacao >= CORTE."""

    por_chave, por_pessoa = _indices_de_itens(registros)
    sobrenomes = _indice_de_sobrenomes(catalogo)
    casamentos: list[Casamento] = []
    chaves_ent = [chave(t) for t, _ in entidades]

    # 1. pessoas (qualquer tipo de entidade: o modelo as vezes tipa pessoa como organizacao)
    for (titulo, _tipo), k in zip(entidades, chaves_ent):
        tokens = [t for t in k.split() if len(t) > 1 and t not in PARTICULAS]
        if not 1 <= len(tokens) <= 7 or any(ch.isdigit() for ch in k):
            continue
        candidatos = set().union(*(sobrenomes.get(t, set()) for t in tokens))
        for pid in candidatos:
            p = catalogo.pessoas[pid]
            s = pontuar_pessoa(k, sorted(p.nomes), sorted(p.citacoes))
            if s >= CORTE:
                for rid, i in por_pessoa.get(pid, []):
                    casamentos.append(Casamento(titulo, rid, i, "pessoa", s, "pessoa"))

    # 2. demais itens: igualdade e semelhanca aproximada em lotes (memoria limitada)
    lista_chaves = list(por_chave)
    ja_casou: set[str] = set()
    for (titulo, _tipo), k in zip(entidades, chaves_ent):
        for rid, i, classe in por_chave.get(k, []):
            casamentos.append(Casamento(titulo, rid, i, classe, 100.0, "exato"))
            ja_casou.add(titulo)
    longas = [j for j, k in enumerate(lista_chaves) if len(k) >= TAMANHO_MINIMO_APROXIMADO]
    alvos = [lista_chaves[j] for j in longas]
    fontes = [(n, k) for n, k in enumerate(chaves_ent) if len(k) >= TAMANHO_MINIMO_APROXIMADO]
    LOTE = 500
    for inicio in range(0, len(fontes), LOTE):
        bloco = fontes[inicio:inicio + LOTE]
        consultas = [k for _, k in bloco]
        m1 = process.cdist(consultas, alvos, scorer=fuzz.ratio, score_cutoff=CORTE, dtype=np.uint8, workers=-1)
        m2 = process.cdist(consultas, alvos, scorer=fuzz.token_sort_ratio, score_cutoff=CORTE, dtype=np.uint8, workers=-1)
        m = np.maximum(m1, m2)
        linhas, colunas = np.nonzero(m)
        for a, b in zip(linhas, colunas):
            n, k = bloco[a]
            alvo = alvos[b]
            if alvo == k:
                continue  # ja contado como exato
            titulo = entidades[n][0]
            for rid, i, classe in por_chave[alvo]:
                casamentos.append(Casamento(titulo, rid, i, classe, float(m[a, b]), "aproximado"))
            ja_casou.add(titulo)

    # 2b. contencao: um nome e trecho do outro ("mestrado interdisciplinar em modelagem
    # computacional" contem o curso "modelagem computacional"; titulo truncado pelo modelo)
    def trechos(k: str) -> set[str]:
        p = k.split()
        return {" ".join(p[i:j]) for i in range(len(p)) for j in range(i + 2, len(p) + 1)
                if len(" ".join(p[i:j])) >= 12}

    longas_chaves = [k for k in lista_chaves if len(k) >= 12 and len(k.split()) >= 2]
    longas_set = set(longas_chaves)
    trecho_de_item: dict[str, list[str]] = defaultdict(list)
    for k in longas_chaves:
        for t in trechos(k):
            if t != k:
                trecho_de_item[t].append(k)
    for (titulo, _tipo), k in zip(entidades, chaves_ent):
        if len(k) < 12 or len(k.split()) < 2:
            continue
        contidos = [t for t in trechos(k) if t in longas_set and t != k]  # item dentro da entidade
        contem_entidade = trecho_de_item.get(k, [])  # entidade dentro do item
        for alvo in set(contidos) | set(contem_entidade):
            curto, longo = sorted((alvo, k), key=len)
            score = 90.0 if len(curto) / len(longo) >= 0.5 else 86.0
            for rid, i, classe in por_chave[alvo]:
                casamentos.append(Casamento(titulo, rid, i, classe, score, "contido"))
            ja_casou.add(titulo)

    # 3. texto do registro (descricoes e titulos): a entidade e mencionada no registro.
    # Pessoas ficam de fora: "maria silva" dentro de "ana maria silva santos" seria outra.
    textos = [(reg.rid, reg.texto_livre) for reg in registros if reg.texto_livre]
    corpo = ""
    inicios: list[int] = []
    rids: list[int] = []
    for rid, texto in textos:
        inicios.append(len(corpo))
        rids.append(rid)
        corpo += f" {texto} |"
    for (titulo, tipo), k in zip(entidades, chaves_ent):
        if tipo == "PERSON" or len(k) < 4:
            continue
        alvo = f" {k} "
        pos = corpo.find(alvo)
        vistos: set[int] = set()
        while pos != -1:
            rid = rids[bisect.bisect_right(inicios, pos) - 1]
            if rid not in vistos:
                vistos.add(rid)
                casamentos.append(Casamento(titulo, rid, -1, "texto", 100.0, "texto"))
            pos = corpo.find(alvo, pos + 1)
    return casamentos
