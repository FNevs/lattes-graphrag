"""Camada 2, parte deterministica (custo zero): respostas contra o gabarito do XML.

Perguntas objetivas (dado-local, atividade-local):
- cobertura (recall): itens do gabarito citados na resposta;
- cada item citado pela resposta e classificado como em Pires et al. (2024):
  correto (esta no gabarito), parcialmente incorreto (entidade real do XML, mas nao e
  resposta desta pergunta), alucinado (nao existe no XML) — e "sem resposta" quando o
  sistema diz que nao sabe;
- precisao = corretos / itens citados; F1.
Perguntas dado-global: cobertura das assercoes (itens mais frequentes no XML).
As perguntas atividade-global nao tem gabarito: so o juiz LLM as avalia.

Uso: .venv\\Scripts\\python.exe scripts\\validacao\\avaliar_consultas.py runs\\v2-npai
"""

from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gabarito import montar_gabarito  # noqa: E402
from normalizacao import chave, contem, pontuar_pessoa, semelhanca  # noqa: E402
from validar_grafo import xmls_da_versao  # noqa: E402

CITACAO = re.compile(r"\[(?:Data|Dados):[^\]]*\]", re.IGNORECASE)
MARCADOR = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s+")
SEM_RESPOSTA = ("nao sei", "nao ha informac", "nao foi possivel", "nao encontr", "nao consta",
                "nao dispon", "i don t know", "no information", "sem informac", "nao possuo")


def limpar(texto: str) -> str:
    return CITACAO.sub("", texto).replace("**", "").replace("__", "")


def itens_da_resposta(texto: str) -> list[tuple[str, str]]:
    """Linhas de lista ('- item', '1. item') -> (nome, linha inteira).

    O nome e o que vem antes de ':' ou ' — ', sem parenteses ("Paulo Roberto dos Santos
    (em andamento)"); a linha inteira tambem conta, porque o titulo do XML pode ter ':'
    ("SRMS: Software para la Evaluacion...").
    """

    itens = []
    for linha in limpar(texto).splitlines():
        if not MARCADOR.match(linha):
            continue
        corpo = MARCADOR.sub("", linha).strip()
        cabeca = re.split(r"\s[—–-]\s|:\s", corpo, maxsplit=1)[0]
        cabeca = re.sub(r"\([^)]*\)", "", cabeca).strip(" .;\"'“”")
        if cabeca:
            itens.append((cabeca, corpo))
    return itens


def casa_item(texto_chave: str, gab: dict) -> bool:
    """O texto (chave) menciona o item do gabarito?"""

    if gab["classe"] in ("pessoa", "par"):
        if gab["classe"] == "par":
            return all(contem(texto_chave, chave(m)) for m in gab.get("membros", []))
        return any(contem(texto_chave, k) for k in gab["chaves"] if len(k.split()) >= 2) or \
            pontuar_pessoa(texto_chave, gab["chaves"], []) >= 90
    k = gab["chaves"][0]
    return contem(texto_chave, k) or (len(texto_chave) >= 6 and semelhanca(texto_chave, k) >= 88)


def avaliar_objetiva(resposta: str, gabarito: list[dict], universo: dict[str, list[str]], classe: str) -> dict:
    texto_k = chave(limpar(resposta))
    citados = itens_da_resposta(resposta)
    if not citados and any(m in texto_k for m in SEM_RESPOSTA):
        return {"sem_resposta": True, "citados": 0, "corretos": 0, "parciais": 0, "alucinados": 0,
                "cobertura": 0.0, "precisao": None, "f1": 0.0, "achados": 0, "esperados": len(gabarito)}
    achados = sum(1 for g in gabarito if casa_item(texto_k, g))
    corretos = parciais = alucinados = 0
    detalhes = []
    for c, corpo in citados:
        ck, corpo_k = chave(c), chave(corpo)
        if any(casa_item(ck, g) or casa_item(corpo_k, g) or (len(ck) >= 6 and any(contem(k, ck) for k in g["chaves"]))
               or (len(ck) >= 3 and g["classe"] != "pessoa" and g["chaves"][0].startswith(ck + " "))  # sigla
               for g in gabarito):
            corretos += 1
            rotulo = "correto"
        elif existe_no_xml(ck, universo, classe):
            parciais += 1
            rotulo = "parcial"
        else:
            alucinados += 1
            rotulo = "alucinado"
        detalhes.append({"item": c, "rotulo": rotulo})
    cobertura = achados / len(gabarito) if gabarito else None
    precisao = corretos / len(citados) if citados else None
    f1 = (2 * precisao * cobertura / (precisao + cobertura)) if precisao and cobertura else 0.0
    return {"sem_resposta": False, "citados": len(citados), "corretos": corretos, "parciais": parciais,
            "alucinados": alucinados, "cobertura": cobertura, "precisao": precisao, "f1": f1,
            "achados": achados, "esperados": len(gabarito), "itens": detalhes}


def existe_no_xml(k: str, universo: dict[str, list[str]], classe: str) -> bool:
    """O item citado existe em algum lugar dos curriculos (mesmo que nao responda a pergunta)?"""

    if not k:
        return False
    if classe == "pessoa":
        return any(pontuar_pessoa(k, [n], []) >= 90 for n in universo["pessoa"])
    if k in universo["_conjunto"]:
        return True
    return any(contem(t, k) for t in universo["textos"]) if len(k) >= 8 else False


def montar_universo(pasta: Path) -> dict:
    registros, catalogo, _ = montar_gabarito(xmls_da_versao(pasta))
    nomes = sorted({n for p in catalogo.pessoas.values() for n in p.nomes})
    chaves = {i.chave for r in registros for i in r.itens if i.classe != "pessoa"}
    textos = [r.texto_livre for r in registros if r.texto_livre]
    return {"pessoa": nomes, "_conjunto": chaves, "textos": textos}


def classe_dos_itens(p: dict) -> str:
    classes = {g["classe"] for g in p["gabarito"]}
    return "pessoa" if classes <= {"pessoa"} else "outro"


def main() -> None:
    pasta = Path(sys.argv[1] if len(sys.argv) > 1 else "runs/v2-npai")
    base = pasta / "validacao" / "consultas"
    perguntas = {p["id"]: p for p in json.loads((base / "perguntas.json").read_text(encoding="utf-8"))}
    universo = montar_universo(pasta)
    resultados = []
    for arq in sorted((base / "respostas").glob("*.json")):
        r = json.loads(arq.read_text(encoding="utf-8"))
        p = perguntas[r["id"]]
        linha = {"id": r["id"], "classe": p["classe"], "tipo": p["tipo"], "metodo": r["metodo"]}
        if p["classe"].endswith("-local"):
            linha.update(avaliar_objetiva(r["resposta"], p["gabarito"], universo, classe_dos_itens(p)))
        elif p["gabarito"]:
            texto_k = chave(limpar(r["resposta"]))
            achadas = [g["valor"] for g in p["gabarito"] if casa_item(texto_k, g)]
            linha.update({"assercoes": len(p["gabarito"]), "assercoes_citadas": len(achadas),
                          "cobertura": len(achadas) / len(p["gabarito"]), "citadas": achadas})
        resultados.append(linha)
    (base / "avaliacao_deterministica.json").write_text(json.dumps(resultados, ensure_ascii=False, indent=2),
                                                         encoding="utf-8")

    # resumo por classe e metodo
    agrupado = defaultdict(list)
    for r in resultados:
        agrupado[(r["classe"], r["metodo"])].append(r)
    linhas = ["# Camada 2 — avaliação determinística contra o XML", "",
              "| classe | método | perguntas | cobertura | precisão | F1 | citados | corretos | parciais | alucinados | sem resposta |",
              "|---|---|---|---|---|---|---|---|---|---|---|"]
    media = lambda xs: f"{sum(xs) / len(xs):.3f}" if xs else "—"  # noqa: E731
    for (classe, metodo), rs in sorted(agrupado.items()):
        if classe.endswith("-local"):
            linhas.append(
                f"| {classe} | {metodo} | {len(rs)} | {media([r['cobertura'] for r in rs if r['cobertura'] is not None])} | "
                f"{media([r['precisao'] for r in rs if r['precisao'] is not None])} | {media([r['f1'] for r in rs])} | "
                f"{sum(r['citados'] for r in rs)} | {sum(r['corretos'] for r in rs)} | {sum(r['parciais'] for r in rs)} | "
                f"{sum(r['alucinados'] for r in rs)} | {sum(r['sem_resposta'] for r in rs)} |")
        elif any("assercoes" in r for r in rs):
            linhas.append(f"| {classe} | {metodo} | {len(rs)} | {media([r['cobertura'] for r in rs if 'cobertura' in r])} "
                          f"| — | — | — | — | — | — | — |")
    linhas += ["", "Cobertura em dado-global = asserções do XML (itens mais frequentes) citadas na resposta.",
               "Precisão = itens corretos / itens citados; parciais = entidade real do XML que não responde à pergunta;",
               "alucinados = item que não existe em nenhum dos currículos.", ""]
    (base / "avaliacao_deterministica.md").write_text("\n".join(linhas), encoding="utf-8")
    print("\n".join(linhas))


if __name__ == "__main__":
    main()
