"""Camada 1 da validacao: o grafo de cada versao contra o XML do Lattes (custo zero).

Uso (na raiz do projeto):
    .venv\\Scripts\\python.exe scripts\\validacao\\validar_grafo.py            # todas as versoes
    .venv\\Scripts\\python.exe scripts\\validacao\\validar_grafo.py runs\\v2-npai

Saidas em runs/<versao>/validacao/ (ignoradas pelo Git): metricas.json, relatorio.md,
casamentos.parquet, sem_fonte.txt. Com mais de uma versao, tambem
runs/_validacao/comparacao.md. Plano e fundamentacao: docs/PLANO-VALIDACAO-TCC2.md.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from alinhamento import alinhar  # noqa: E402
from gabarito import montar_gabarito  # noqa: E402
from metricas import LIMIARES, avaliar, pares_de_titulares, proveniencia  # noqa: E402
from normalizacao import chave  # noqa: E402

RAIZ = Path(__file__).resolve().parents[2]
PASTAS_XML = (RAIZ / "lattesNAPI" / "lattes", RAIZ / "input_xml")


DATA_NO_TEXTO = re.compile(r"data atualizacao[:=] *(\d{8})")
DATA_NO_XML = re.compile(rb'DATA-ATUALIZACAO="(\d{8})"')


def xmls_da_versao(pasta: Path) -> list[Path]:
    """O XML de cada curriculo da versao, na mesma atualizacao que gerou o texto de entrada.

    O mesmo curriculo existe em mais de uma atualizacao (input_xml/ de 06/2025, usado do V0
    ao V1-formatoE; lattesNAPI/ de 03/2026, usado no V2). Validar uma versao contra a
    atualizacao errada contaria como erro o que so mudou no curriculo.
    """

    manifesto = json.loads((pasta / "MANIFEST.json").read_text(encoding="utf-8-sig"))
    ids = sorted({m for c in manifesto["curriculos"] for m in re.findall(r"\d{16}", c)})
    xmls = []
    for cv in ids:
        entrada = next((pasta / "input").glob(f"*{cv}*.txt"), None)
        data = None
        if entrada is not None:
            achada = DATA_NO_TEXTO.search(entrada.read_text(encoding="utf-8", errors="replace")[:5000])
            data = achada.group(1) if achada else None
        candidatos = [p / f"{cv}.xml" for p in PASTAS_XML if (p / f"{cv}.xml").exists()]
        if not candidatos:
            raise FileNotFoundError(f"XML do curriculo {cv} nao encontrado em {PASTAS_XML}")

        def data_do_xml(caminho: Path) -> str | None:
            achada = DATA_NO_XML.search(caminho.read_bytes()[:2000])
            return achada.group(1).decode() if achada else None

        mesma_data = [c for c in candidatos if data and data_do_xml(c) == data]
        if data and not mesma_data:
            print(f"  aviso: nenhum XML de {cv} com data {data}; usando {candidatos[0]}", flush=True)
        xmls.append((mesma_data or candidatos)[0])
    return xmls


def ler_saida(pasta: Path) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, str]]:
    out = pasta / "output"
    ent = pd.read_parquet(out / "entities.parquet")
    rel = pd.read_parquet(out / "relationships.parquet")
    tu = pd.read_parquet(out / "text_units.parquet")
    ent = ent.rename(columns={"name": "title"})
    for df in (ent, rel):
        df["text_unit_ids"] = df["text_unit_ids"].map(lambda v: list(v) if v is not None else [])
    ent["type"] = ent["type"].fillna("").astype(str)
    trechos = {i: chave(t) for i, t in zip(tu["id"], tu["text"])}
    return ent, rel, trechos


def pct(a: int, b: int) -> str:
    return f"{100 * a / b:.1f}%" if b else "—"


def relatorio(versao: str, m: dict, prov: dict, pares: list[dict], n_reg: int, n_pessoas: int,
              conflitos: int) -> str:
    linhas = [f"# Validação contra o XML — {versao}", "",
              f"Registros no gabarito: {n_reg:,} · pessoas no catálogo: {n_pessoas:,}".replace(",", ".")
              + f" · autorias com ID do CNPq de outra pessoa (ignorado): {conflitos}", ""]
    t = prov["entidades_total"]
    lit = prov["relacoes_literais"]
    linhas += ["## Proveniência (a entidade aparece no trecho de onde saiu)", "",
               f"- Entidades com fonte: {prov['entidades_com_fonte']} de {t} ({pct(prov['entidades_com_fonte'], t)}) — "
               f"literal {prov['entidades_literais']} ({pct(prov['entidades_literais'], t)}), "
               f"só as palavras, fora de ordem {prov['entidades_palavras']}",
               f"- Relações com as duas pontas no trecho: {prov['relacoes']['ambas']} de {prov['relacoes_total']} "
               f"({pct(prov['relacoes']['ambas'], prov['relacoes_total'])}); uma ponta: {prov['relacoes']['uma']}; "
               f"nenhuma: {prov['relacoes']['nenhuma']}",
               f"- Só literal: ambas {lit['ambas']} ({pct(lit['ambas'], prov['relacoes_total'])}); "
               f"uma {lit['uma']}; nenhuma {lit['nenhuma']}", ""]
    linhas += ["## Relações contra o XML, por limiar de semelhança", "",
               "| limiar | suportadas | não suportadas | não verificáveis | precisão | cobertura | F1 |",
               "|---|---|---|---|---|---|---|"]
    for lim in LIMIARES:
        r = m["por_limiar"][lim]
        e = r["relacoes"]
        linhas.append(f"| {lim} | {e.get('suportada', 0)} | {e.get('nao_suportada', 0)} | "
                      f"{e.get('nao_verificavel', 0)} | {r['precisao']} | {r['recall']} | {r['f1']} |")
    r90 = m["por_limiar"][90]
    linhas += ["", "## Por família (limiar 90)", "",
               "| família | suportadas | não suportadas | não verificáveis |", "|---|---|---|---|"]
    for fam, c in sorted(r90["por_familia"].items(), key=lambda x: -sum(x[1].values())):
        linhas.append(f"| {fam} | {c.get('suportada', 0)} | {c.get('nao_suportada', 0)} | {c.get('nao_verificavel', 0)} |")
    linhas += ["", "## Cobertura das ligações do XML (limiar 90)", "",
               "| família | classe do item | esperadas | achadas | cobertura |", "|---|---|---|---|---|"]
    for fam, classes in sorted(r90["recall_por_familia"].items()):
        for classe, v in sorted(classes.items()):
            linhas.append(f"| {fam} | {classe} | {v['esperadas']} | {v['achadas']} | {pct(v['achadas'], v['esperadas'])} |")
    linhas += ["", "## Registros que viraram entidade (limiar 90)", "",
               "| família | registros | com entidade | cobertura |", "|---|---|---|---|"]
    for fam, v in sorted(r90["nucleos"].items()):
        linhas.append(f"| {fam} | {v['total']} | {v['cobertos']} | {pct(v['cobertos'], v['total'])} |")
    linhas += ["", f"Entidades por registro coberto: {r90['entidades_por_nucleo_coberto']} · "
               f"registros com mais de uma entidade: {r90['nucleos_com_mais_de_uma_entidade']}", ""]
    linhas += ["## Tipo correto (limiar 90)", "", "| tipo esperado | entidades | corretas | % |", "|---|---|---|---|"]
    for t, v in sorted(r90["tipo_correto"].items()):
        linhas.append(f"| {t} | {v['total']} | {v['corretos']} | {pct(v['corretos'], v['total'])} |")
    linhas += ["", "## Entidades PERSON por titular (fragmentação, limiar 90)", "", "| titular | entidades |", "|---|---|"]
    for nome, n in sorted(r90["entidades_por_titular"].items(), key=lambda x: -x[1]):
        linhas.append(f"| {nome} | {n} |")
    if pares:
        linhas += ["", "## Produções em comum entre titulares: XML × grafo", "",
                   "| par | XML | grafo | diferença |", "|---|---|---|---|"]
        for p in pares:
            linhas.append(f"| {p['a']} × {p['b']} | {p['xml']} | {p['grafo']} | {p['grafo'] - p['xml']:+d} |")
    linhas += ["", f"Entidades sem fonte no próprio trecho: {len(prov['entidades_sem_fonte'])} (lista em sem_fonte.txt)", ""]
    return "\n".join(linhas)


def validar(pasta: Path) -> dict:
    inicio = time.time()
    versao = pasta.name
    xmls = xmls_da_versao(pasta)
    registros, catalogo, titulares = montar_gabarito(xmls)
    ent, rel, trechos = ler_saida(pasta)
    print(f"[{versao}] gabarito: {len(registros)} registros, {len(catalogo.pessoas)} pessoas; "
          f"grafo: {len(ent)} entidades, {len(rel)} relações", flush=True)
    casamentos = alinhar(list(zip(ent["title"], ent["type"])), registros, catalogo)
    print(f"[{versao}] {len(casamentos)} casamentos ({time.time() - inicio:.0f} s)", flush=True)
    prov = proveniencia(ent, rel, trechos)
    m = avaliar(ent, rel, registros, catalogo, titulares, casamentos)
    pares = pares_de_titulares(registros, catalogo, titulares, ent, rel) if len(titulares) > 1 else []

    saida = pasta / "validacao"
    saida.mkdir(exist_ok=True)
    resumo = {"versao": versao, "registros": len(registros), "pessoas": len(catalogo.pessoas),
              "conflitos_de_id": len(catalogo.conflitos_de_id),
              "entidades": len(ent), "relacoes": len(rel),
              "proveniencia": {k: v for k, v in prov.items() if k != "entidades_sem_fonte"},
              "entidades_sem_fonte": len(prov["entidades_sem_fonte"]), "metricas": m, "pares_titulares": pares}
    (saida / "metricas.json").write_text(json.dumps(resumo, ensure_ascii=False, indent=2), encoding="utf-8")
    (saida / "sem_fonte.txt").write_text("\n".join(sorted(prov["entidades_sem_fonte"])), encoding="utf-8")
    pd.DataFrame([c.__dict__ for c in casamentos]).to_parquet(saida / "casamentos.parquet", index=False)
    (saida / "relatorio.md").write_text(relatorio(versao, m, prov, pares, len(registros), len(catalogo.pessoas),
                                                  len(catalogo.conflitos_de_id)), encoding="utf-8")
    print(f"[{versao}] pronto em {time.time() - inicio:.0f} s -> {saida}", flush=True)
    return resumo


def comparar(resumos: list[dict]) -> str:
    linhas = ["# Validação contra o XML — comparação entre versões (limiar 90)", "",
              "| versão | entidades | relações | proveniência (ambas) | precisão | cobertura | F1 | sem fonte |",
              "|---|---|---|---|---|---|---|---|"]
    for r in resumos:
        m = r["metricas"]["por_limiar"][90]
        p = r["proveniencia"]
        linhas.append(f"| {r['versao']} | {r['entidades']} | {r['relacoes']} | {p['pct_relacoes_ambas']}% | "
                      f"{m['precisao']} | {m['recall']} | {m['f1']} | {r['entidades_sem_fonte']} |")
    return "\n".join(linhas) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("versoes", nargs="*", type=Path, help="pastas runs/<versao> (padrao: todas)")
    args = parser.parse_args()
    pastas = args.versoes or sorted(p for p in (RAIZ / "runs").glob("v*") if (p / "MANIFEST.json").exists())
    resumos = [validar(p) for p in pastas]
    if len(resumos) > 1:
        destino = RAIZ / "runs" / "_validacao"
        destino.mkdir(exist_ok=True)
        (destino / "comparacao.md").write_text(comparar(resumos), encoding="utf-8")
        print(f"comparação -> {destino / 'comparacao.md'}")


if __name__ == "__main__":
    main()
