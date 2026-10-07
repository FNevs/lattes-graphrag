"""Metricas da camada 1: proveniencia, entidades, relacoes por familia e pares de titulares."""

from __future__ import annotations

from collections import Counter, defaultdict

import pandas as pd
from rapidfuzz import fuzz

from alinhamento import Casamento
from gabarito import TIPO_ESPERADO, TIPO_NUCLEO, Catalogo, Registro
from normalizacao import chave, contem

LIMIARES = (100, 95, 90, 85)
PRODUCOES_GRAFO = ("PUBLICATION", "SOFTWARE", "PROJECT")  # mesma definicao do exportar_site.py
FAMILIAS_PRODUCAO = ("publicacao", "software", "producao_tecnica", "projeto")
# Classes de item ligadas ao nucleo do registro cuja ligacao o grafo deveria trazer.
CLASSES_ESPERADAS = ("pessoa", "organizacao", "evento", "curso", "area", "palavra", "veiculo")


def _registros_por_entidade(casamentos: list[Casamento]) -> dict[str, dict[int, float]]:
    """entidade -> {rid: melhor pontuacao}."""

    regs: dict[str, dict[int, float]] = defaultdict(dict)
    for c in casamentos:
        atual = regs[c.entidade].get(c.rid, 0.0)
        if c.score > atual:
            regs[c.entidade][c.rid] = c.score
    return regs


def proveniencia(entidades: pd.DataFrame, relacoes: pd.DataFrame, trechos: dict[str, str]) -> dict:
    """A entidade aparece nos trechos de onde saiu? E as duas pontas de cada relacao?

    `trechos` = {id do text unit: chave do texto}. Primeiro procura as palavras exatas;
    se falhar, aceita semelhanca parcial >= 90 (pega grafias como "SABA, H." no texto).
    """

    cache: dict[tuple[str, tuple[str, ...]], int] = {}

    def nivel(titulo: str, ids: tuple[str, ...]) -> int:
        """2 = literal; 1 = todas as palavras no trecho, fora de ordem; 0 = ausente.

        O nivel 1 existe por causa das pessoas: o modelo escreve "ELAINE G. RODRIGUES"
        quando o trecho diz "Elaine Gomes Rodrigues" ou "RODRIGUES, E. G.".
        """

        chave_cache = (titulo, ids)
        if chave_cache in cache:
            return cache[chave_cache]
        k = chave(titulo)
        textos = [trechos.get(i, "") for i in ids]
        if not k:
            n = 0
        elif any(contem(t, k) for t in textos) or any(fuzz.partial_ratio(k, t) >= 90 for t in textos if t):
            n = 2
        elif any(all(contem(t, w) for w in k.split()) for t in textos):
            n = 1
        else:
            n = 0
        cache[chave_cache] = n
        return n

    niveis = [nivel(r.title, tuple(r.text_unit_ids)) for r in entidades.itertuples()]
    sem_fonte = entidades.loc[[n == 0 for n in niveis], "title"].tolist()
    estados = Counter()
    estados_literais = Counter()
    for r in relacoes.itertuples():
        ids = tuple(r.text_unit_ids)
        a, b = nivel(r.source, ids), nivel(r.target, ids)
        estados[{2: "ambas", 1: "uma", 0: "nenhuma"}[(a > 0) + (b > 0)]] += 1
        estados_literais[{2: "ambas", 1: "uma", 0: "nenhuma"}[(a == 2) + (b == 2)]] += 1
    total = len(relacoes)
    return {
        "entidades_literais": sum(1 for n in niveis if n == 2),
        "entidades_palavras": sum(1 for n in niveis if n == 1),
        "entidades_com_fonte": sum(1 for n in niveis if n > 0),
        "entidades_total": len(entidades),
        "entidades_sem_fonte": sem_fonte,
        "relacoes": {k: estados.get(k, 0) for k in ("ambas", "uma", "nenhuma")},
        "relacoes_literais": {k: estados_literais.get(k, 0) for k in ("ambas", "uma", "nenhuma")},
        "relacoes_total": total,
        "pct_relacoes_ambas": round(100 * estados.get("ambas", 0) / total, 2) if total else None,
    }


def avaliar(entidades: pd.DataFrame, relacoes: pd.DataFrame, registros: list[Registro],
            catalogo: Catalogo, titulares: dict[str, str], casamentos: list[Casamento]) -> dict:
    """Todas as metricas de entidade e relacao, para cada limiar de `LIMIARES`."""

    regs = _registros_por_entidade(casamentos)
    tipos = dict(zip(entidades["title"], entidades["type"]))
    por_reg_item: dict[tuple[int, int], dict[str, float]] = defaultdict(dict)
    for c in casamentos:
        if c.item >= 0:
            atual = por_reg_item[(c.rid, c.item)].get(c.entidade, 0.0)
            por_reg_item[(c.rid, c.item)][c.entidade] = max(atual, c.score)
    arestas = {frozenset((s, t)) for s, t in zip(relacoes["source"], relacoes["target"])}
    reg_por_id = {r.rid: r for r in registros}
    # pessoa do catalogo -> {entidade PERSON: melhor pontuacao}
    entidades_da_pessoa: dict[str, dict[str, float]] = defaultdict(dict)
    for c in casamentos:
        if c.via == "pessoa" and tipos.get(c.entidade) == "PERSON":
            pid = reg_por_id[c.rid].itens[c.item].pessoa
            atual = entidades_da_pessoa[pid].get(c.entidade, 0.0)
            entidades_da_pessoa[pid][c.entidade] = max(atual, c.score)

    resultado: dict = {"por_limiar": {}}
    for lim in LIMIARES:
        ok = lambda s: s >= lim  # noqa: E731

        # --- relacoes: suportada (mesmo registro), nao suportada, nao verificavel
        estados = Counter()
        por_familia = defaultdict(Counter)
        for s, t in zip(relacoes["source"], relacoes["target"]):
            rs = {rid for rid, sc in regs.get(s, {}).items() if ok(sc)}
            rt = {rid for rid, sc in regs.get(t, {}).items() if ok(sc)}
            if not rs or not rt:
                estados["nao_verificavel"] += 1
                familia = "sem_correspondente"
                estado = "nao_verificavel"
            elif rs & rt:
                estados["suportada"] += 1
                familia = Counter(reg_por_id[r].familia for r in rs & rt).most_common(1)[0][0]
                estado = "suportada"
            else:
                estados["nao_suportada"] += 1
                familia = Counter(reg_por_id[r].familia for r in rs | rt).most_common(1)[0][0]
                estado = "nao_suportada"
            por_familia[familia][estado] += 1
        verificaveis = estados["suportada"] + estados["nao_suportada"]
        precisao = estados["suportada"] / verificaveis if verificaveis else None

        # --- cobertura: ligacoes nucleo-item do XML que o grafo traz
        esperadas = Counter()
        achadas = Counter()
        for reg in registros:
            if reg.nucleo is None:
                continue
            ents_nucleo = {e for e, sc in por_reg_item.get((reg.rid, reg.nucleo), {}).items() if ok(sc)}
            for i, item in enumerate(reg.itens):
                if i == reg.nucleo or item.classe not in CLASSES_ESPERADAS:
                    continue
                chave_fam = (reg.familia, item.classe)
                esperadas[chave_fam] += 1
                ents_item = {e for e, sc in por_reg_item.get((reg.rid, i), {}).items() if ok(sc)}
                if any(frozenset((a, b)) in arestas for a in ents_nucleo for b in ents_item if a != b):
                    achadas[chave_fam] += 1
        recall_familia = {}
        for (fam, classe), n in sorted(esperadas.items()):
            recall_familia.setdefault(fam, {})[classe] = {"esperadas": n, "achadas": achadas[(fam, classe)]}
        total_esp = sum(esperadas.values())
        recall = sum(achadas.values()) / total_esp if total_esp else None
        f1 = (2 * precisao * recall / (precisao + recall)) if precisao and recall else None

        # --- entidades: nucleos cobertos, fragmentacao e tipo
        nucleos = Counter()
        nucleos_cobertos = Counter()
        fragmentos = []
        for reg in registros:
            if reg.nucleo is None:
                continue
            nucleos[reg.familia] += 1
            ents = [e for e, sc in por_reg_item.get((reg.rid, reg.nucleo), {}).items() if ok(sc)]
            if ents:
                nucleos_cobertos[reg.familia] += 1
                fragmentos.append(len(ents))
        tipo_ok = Counter()
        tipo_total = Counter()
        confusao = defaultdict(Counter)
        melhor: dict[str, tuple[float, str]] = {}
        for c in casamentos:
            if c.item < 0 or not ok(c.score):
                continue
            reg = reg_por_id[c.rid]
            if c.classe == "titulo":
                esperado = TIPO_NUCLEO.get(reg.familia) if c.item == reg.nucleo else None
            else:
                esperado = TIPO_ESPERADO.get(c.classe)
            if esperado and c.score > melhor.get(c.entidade, (0.0, ""))[0]:
                melhor[c.entidade] = (c.score, esperado)
        for ent, (_, esperado) in melhor.items():
            tipo = tipos.get(ent, "?")
            tipo_total[esperado] += 1
            tipo_ok[esperado] += tipo == esperado
            confusao[esperado][tipo] += 1

        # --- pessoas: quantas entidades distintas casam com cada titular
        fragmentacao_titulares = {}
        for cv, nome in titulares.items():
            ents = entidades_da_pessoa.get(f"id:{cv}", {})
            fragmentacao_titulares[nome] = sum(1 for sc in ents.values() if ok(sc))

        resultado["por_limiar"][lim] = {
            "relacoes": dict(estados),
            "precisao": round(precisao, 4) if precisao is not None else None,
            "recall": round(recall, 4) if recall is not None else None,
            "f1": round(f1, 4) if f1 is not None else None,
            "por_familia": {f: dict(c) for f, c in por_familia.items()},
            "recall_por_familia": recall_familia,
            "nucleos": {f: {"total": nucleos[f], "cobertos": nucleos_cobertos[f]} for f in nucleos},
            "entidades_por_nucleo_coberto": round(sum(fragmentos) / len(fragmentos), 3) if fragmentos else None,
            "nucleos_com_mais_de_uma_entidade": sum(1 for x in fragmentos if x > 1),
            "tipo_correto": {t: {"total": tipo_total[t], "corretos": tipo_ok[t]} for t in tipo_total},
            "confusao_de_tipo": {t: dict(c) for t, c in confusao.items()},
            "entidades_por_titular": fragmentacao_titulares,
            "entidades_alinhadas": sum(1 for e in regs if any(ok(s) for s in regs[e].values())),
        }
    return resultado


def pares_de_titulares(registros: list[Registro], catalogo: Catalogo, titulares: dict[str, str],
                       entidades: pd.DataFrame, relacoes: pd.DataFrame) -> list[dict]:
    """Producoes em comum de cada par de titulares: XML x grafo.

    No XML, uma producao (artigo, software, projeto...) conta para o par se os dois
    titulares estao entre as pessoas do registro; a mesma producao registrada nos dois
    curriculos conta uma vez (titulo + ano). No grafo, a contagem e a do site: producoes
    ligadas as entidades com o nome exato dos dois titulares.
    """

    titular_de = {pid: p.titular for pid, p in catalogo.pessoas.items() if p.titular}
    xml_pares: dict[tuple[str, str], set[tuple[str, str]]] = defaultdict(set)
    for reg in registros:
        if reg.familia not in FAMILIAS_PRODUCAO or reg.nucleo is None:
            continue
        presentes = sorted({titular_de[i.pessoa] for i in reg.itens if i.classe == "pessoa" and i.pessoa in titular_de})
        ident = (reg.itens[reg.nucleo].chave, reg.ano)
        for a in range(len(presentes)):
            for b in range(a + 1, len(presentes)):
                xml_pares[(presentes[a], presentes[b])].add(ident)

    tipo = dict(zip(entidades["title"], entidades["type"]))
    vizinhos: dict[str, set[str]] = defaultdict(set)
    for s, t in zip(relacoes["source"], relacoes["target"]):
        if tipo.get(t) in PRODUCOES_GRAFO:
            vizinhos[s].add(t)
        if tipo.get(s) in PRODUCOES_GRAFO:
            vizinhos[t].add(s)
    titulo_titular = {}
    for cv, nome in titulares.items():
        k = chave(nome)
        achados = [e for e in entidades["title"] if chave(e) == k]
        titulo_titular[cv] = achados[0] if achados else None

    linhas = []
    ids = sorted(titulares)
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            a, b = ids[i], ids[j]
            n_xml = len(xml_pares.get((a, b), set()) | xml_pares.get((b, a), set()))
            ta, tb = titulo_titular[a], titulo_titular[b]
            n_grafo = len(vizinhos[ta] & vizinhos[tb]) if ta and tb else 0
            if n_xml or n_grafo:
                linhas.append({"a": titulares[a], "b": titulares[b], "xml": n_xml, "grafo": n_grafo})
    return sorted(linhas, key=lambda x: -x["xml"])
