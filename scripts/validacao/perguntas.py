"""Conjunto de perguntas da camada 2, gerado do XML (cada pergunta ja nasce com gabarito).

Segue as quatro classes do BenchmarkQED (Microsoft, 2025):
- dado-local / atividade-local: perguntas objetivas sobre um pesquisador ou um par, com a
  lista de itens corretos tirada do XML (softwares, projetos, orientador, vinculos...);
- dado-global: perguntas sobre o grupo inteiro, com "assercoes" tiradas do XML (areas,
  instituicoes e pares mais frequentes) que uma boa resposta deveria mencionar;
- atividade-global: perguntas abertas (parcerias, oportunidades), sem gabarito, para o
  juiz LLM.

A escolha de pesquisadores e deterministica (ordem fixa, limites de tamanho de lista), e o
arquivo gerado fica em runs/<versao>/validacao/consultas/perguntas.json (tem nomes reais).
"""

from __future__ import annotations

from collections import Counter, defaultdict

from gabarito import Catalogo, Registro
from normalizacao import chave

FAMILIAS_PRODUCAO = ("publicacao", "software", "producao_tecnica", "projeto")


def _item_gabarito(valor: str, classe: str, chaves: set[str] | None = None) -> dict:
    return {"valor": valor, "classe": classe, "chaves": sorted({chave(valor)} | (chaves or set()))}


def _pessoa_gabarito(catalogo: Catalogo, pid: str, valor: str) -> dict:
    p = catalogo.pessoas.get(pid)
    formas = (p.nomes | p.citacoes) if p else set()
    return _item_gabarito(valor, "pessoa", formas)


def _por_cv(registros: list[Registro]) -> dict[str, list[Registro]]:
    d: dict[str, list[Registro]] = defaultdict(list)
    for r in registros:
        d[r.cv].append(r)
    return d


def _dedup(itens: list[dict]) -> list[dict]:
    vistos, saida = set(), []
    for it in itens:
        k = it["chaves"][0] if it["classe"] != "pessoa" else tuple(it["chaves"])
        if k not in vistos:
            vistos.add(k)
            saida.append(it)
    return saida


def montar_perguntas(registros: list[Registro], catalogo: Catalogo, titulares: dict[str, str]) -> list[dict]:
    regs_cv = _por_cv(registros)
    titular_pid = {cv: f"id:{cv}" for cv in titulares}
    # ordem fixa: do curriculo com mais registros para o com menos
    ordem = sorted(titulares, key=lambda cv: (-len(regs_cv[cv]), titulares[cv]))

    def nucleos(cv: str, familias: tuple[str, ...] | None = None, tags: tuple[str, ...] | None = None,
                com_titular: bool = False) -> list[dict]:
        itens = []
        for r in regs_cv[cv]:
            if r.nucleo is None or (familias and r.familia not in familias) or (tags and r.tag not in tags):
                continue
            if com_titular and not any(i.pessoa == titular_pid[cv] for i in r.itens):
                continue
            if r.itens[r.nucleo].classe != "titulo" or r.itens[r.nucleo].chave in ("projeto de pesquisa", "projeto"):
                continue  # registro sem nome proprio (so financiador, ou titulo generico)
            itens.append(_item_gabarito(r.itens[r.nucleo].valor, "titulo"))
        return _dedup(itens)

    def pessoas_em(cv: str, tags: tuple[str, ...]) -> list[dict]:
        itens = []
        for r in regs_cv[cv]:
            if r.tag in tags:
                for i in r.itens:
                    if i.classe == "pessoa" and i.pessoa != titular_pid[cv]:
                        itens.append(_pessoa_gabarito(catalogo, i.pessoa, i.valor))
        return _dedup(itens)

    def organizacoes_em(cv: str, tags: tuple[str, ...]) -> list[dict]:
        return _dedup([_item_gabarito(i.valor, "organizacao") for r in regs_cv[cv] if r.tag in tags
                       for i in r.itens if i.classe == "organizacao"])

    modelos = [
        ("dado-local", "softwares", "Quais softwares {t} registrou? Liste os nomes dos softwares.",
         lambda cv: nucleos(cv, familias=("software",), com_titular=True), (3, 25), 2),
        ("dado-local", "projetos", "De quais projetos de pesquisa {t} participou? Liste os nomes dos projetos.",
         lambda cv: nucleos(cv, tags=("PROJETO-DE-PESQUISA",)), (3, 20), 2),
        ("dado-local", "orientador", "Quem orientou o doutorado de {t}?",
         lambda cv: pessoas_em(cv, ("DOUTORADO",)), (1, 3), 2),
        ("dado-local", "vinculos", "Em quais instituições {t} teve vínculo profissional? Liste as instituições.",
         lambda cv: organizacoes_em(cv, ("VINCULOS",)), (2, 15), 2),
        ("dado-local", "orientandos", "Quais orientações de doutorado {t} concluiu? Liste os nomes dos orientandos.",
         lambda cv: pessoas_em(cv, ("ORIENTACOES-CONCLUIDAS-PARA-DOUTORADO",)), (2, 15), 1),
    ]
    perguntas: list[dict] = []
    usados = Counter()
    for classe, tipo, texto, gabarito_de, (minimo, maximo), quantas in modelos:
        escolhidos = 0
        for cv in sorted(ordem, key=lambda c: usados[c]):  # espalha entre os pesquisadores
            gab = gabarito_de(cv)
            if minimo <= len(gab) <= maximo:
                perguntas.append({"classe": classe, "tipo": tipo, "pergunta": texto.format(t=titulares[cv]),
                                  "sujeito": titulares[cv], "gabarito": gab})
                usados[cv] += 1
                escolhidos += 1
                if escolhidos == quantas:
                    break

    # --- atividade-local: parceiros no grupo e coautores em comum
    titular_de = {pid: p.titular for pid, p in catalogo.pessoas.items() if p.titular}
    producoes_do_par: dict[tuple[str, str], set] = defaultdict(set)
    pessoas_por_titular: dict[str, set[str]] = defaultdict(set)
    nome_de: dict[str, str] = {}
    for r in registros:
        if r.familia not in FAMILIAS_PRODUCAO or r.nucleo is None:
            continue
        pessoas = [i for i in r.itens if i.classe == "pessoa" and i.pessoa]
        tits = sorted({titular_de[i.pessoa] for i in pessoas if i.pessoa in titular_de})
        ident = (r.itens[r.nucleo].chave, r.ano)
        for a in tits:
            for b in tits:
                if a < b:
                    producoes_do_par[(a, b)].add(ident)
            for i in pessoas:
                if i.pessoa not in titular_de:
                    pessoas_por_titular[a].add(i.pessoa)
                    nome_de.setdefault(i.pessoa, i.valor)
    for cv in ordem[:2]:
        parceiros = Counter()
        for (a, b), prods in producoes_do_par.items():
            if cv in (a, b):
                parceiros[b if a == cv else a] = len(prods)
        gab = [dict(_item_gabarito(titulares[o], "pessoa", catalogo.pessoas[f"id:{o}"].nomes
                                   | catalogo.pessoas[f"id:{o}"].citacoes), peso=n)
               for o, n in parceiros.most_common()]
        if gab:
            perguntas.append({"classe": "atividade-local", "tipo": "parceiros",
                              "pergunta": f"Com quais pesquisadores do grupo {titulares[cv]} mais compartilha "
                                          f"produções? Liste em ordem, do que mais compartilha para o que menos.",
                              "sujeito": titulares[cv], "gabarito": gab})
    pares = sorted(producoes_do_par, key=lambda p: -len(producoes_do_par[p]))
    for a, b in pares:
        comuns = pessoas_por_titular[a] & pessoas_por_titular[b]
        if 5 <= len(comuns) <= 30:
            gab = _dedup([_pessoa_gabarito(catalogo, pid, nome_de[pid]) for pid in sorted(comuns)])
            perguntas.append({"classe": "atividade-local", "tipo": "coautores_em_comum",
                              "pergunta": f"Quais coautores {titulares[a]} e {titulares[b]} têm em comum?",
                              "sujeito": f"{titulares[a]} × {titulares[b]}", "gabarito": gab})
            break

    # --- dado-global: assercoes do XML sobre o grupo
    def mais_frequentes(classe: str, tags: tuple[str, ...] | None, n: int) -> list[dict]:
        cont: Counter = Counter()
        valor: dict[str, str] = {}
        for r in registros:
            if tags and r.tag not in tags:
                continue
            for i in r.itens:
                if i.classe == classe and len(i.chave) > 3:
                    cont[i.chave] += 1
                    valor.setdefault(i.chave, i.valor)
        return [dict(_item_gabarito(valor[k], classe), peso=c) for k, c in cont.most_common(n)]

    perguntas += [
        {"classe": "dado-global", "tipo": "areas",
         "pergunta": "Quais são as principais áreas de atuação e linhas de pesquisa do grupo de pesquisadores?",
         "sujeito": "grupo", "gabarito": mais_frequentes("area", ("AREA-DE-ATUACAO",), 12)},
        {"classe": "dado-global", "tipo": "instituicoes",
         "pergunta": "Quais instituições aparecem com mais frequência na trajetória dos pesquisadores do grupo?",
         "sujeito": "grupo", "gabarito": mais_frequentes("organizacao", None, 10)},
        {"classe": "dado-global", "tipo": "temas_compartilhados",
         "pergunta": "Quais temas de pesquisa (palavras-chave) aparecem com mais frequência nas produções do grupo?",
         "sujeito": "grupo", "gabarito": mais_frequentes("palavra", None, 12)},
        {"classe": "dado-global", "tipo": "pares",
         "pergunta": "Quais pares de pesquisadores do grupo mais colaboram entre si em produções?",
         "sujeito": "grupo",
         "gabarito": [dict(_item_gabarito(f"{titulares[a]} e {titulares[b]}", "par",
                                          {chave(titulares[a]), chave(titulares[b])}),
                           peso=len(producoes_do_par[(a, b)]), membros=[titulares[a], titulares[b]])
                      for a, b in pares[:5]]},
    ]
    # --- atividade-global: abertas, sem gabarito (juiz LLM)
    for tipo, texto in (
        ("novas_parcerias", "Que novas parcerias entre pesquisadores do grupo seriam promissoras, e por quê?"),
        ("evolucao", "Como o perfil de produção do grupo evoluiu ao longo do tempo?"),
        ("oportunidades", "Que lacunas ou oportunidades de pesquisa o grupo poderia explorar a partir do que já faz?"),
        ("parecer", "Resuma o perfil do grupo para um avaliador de uma agência de fomento."),
    ):
        perguntas.append({"classe": "atividade-global", "tipo": tipo, "pergunta": texto, "sujeito": "grupo",
                          "gabarito": []})
    for n, p in enumerate(perguntas, 1):
        p["id"] = f"q{n:02d}"
    return perguntas
