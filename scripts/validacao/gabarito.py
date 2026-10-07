"""Gabarito da validacao: registros, itens e pessoas extraidos do XML do Lattes.

Cada registro do XML (um artigo, um projeto, uma banca, um vinculo...) vira um
`Registro` com seus itens nomeaveis (titulo, pessoas, instituicoes, evento, curso,
areas, palavras-chave) e o texto livre (descricoes). A definicao de "registro" e a mesma
de `scripts/extract_lattes_text.py`, que gerou o texto lido pelo GraphRAG: cada registro
foi uma linha do texto, entao o que esta no mesmo registro esteve na mesma linha.
"""

from __future__ import annotations

import sys
import xml.etree.ElementTree as et
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from extract_lattes_text import (  # noqa: E402
    ELEMENTOS_OMITIDOS,
    ITENS,
    PESSOAS,
    TAMANHO_TEXTO_LONGO,
    _eh_registro,
    normalizar_texto,
)

from normalizacao import chave, formas_de_citacao, pontuar_pessoa  # noqa: E402

# Classe do item -> tipo de entidade esperado no grafo (9 tipos do dominio Lattes).
TIPO_ESPERADO = {
    "pessoa": "PERSON",
    "organizacao": "ORGANIZATION",
    "evento": "EVENT",
    "curso": "COURSE",
    "area": "KNOWLEDGE_AREA",
    "palavra": "KNOWLEDGE_AREA",
    "local": "GEO",
}
# Familia do registro -> tipo esperado do nucleo (o titulo do registro).
TIPO_NUCLEO = {
    "publicacao": "PUBLICATION",
    "software": "SOFTWARE",
    "projeto": "PROJECT",
}

ATRIBUTOS_PESSOA = (
    "NOME-DO-ORIENTADO",
    "NOME-DO-CANDIDATO",
    "NOME-COMPLETO-DO-ORIENTADOR",
    "NOME-DO-ORIENTADOR",
    "NOME-DO-CO-ORIENTADOR",
    "NOME-COMPLETO-DO-CO-ORIENTADOR",
)
TEXTO_LIVRE = ("DESCRICAO", "RESUMO", "TEXTO", "OUTRAS-INFORMACOES", "INFORMACAO-ADICIONAL")


@dataclass
class Item:
    valor: str
    chave: str
    classe: str  # titulo, pessoa, organizacao, evento, curso, area, palavra, local, veiculo
    pessoa: str | None = None  # identificador da pessoa no catalogo (so para classe pessoa)


@dataclass
class Registro:
    rid: int
    cv: str
    tag: str
    familia: str
    itens: list[Item] = field(default_factory=list)
    texto_livre: str = ""  # chave do texto do registro (descricoes + itens que nao sao pessoa)
    nucleo: int | None = None  # indice do item principal em `itens`
    ano: str = ""


@dataclass
class Pessoa:
    pid: str
    nomes: set[str] = field(default_factory=set)  # chaves de nomes completos
    citacoes: set[str] = field(default_factory=set)  # chaves de formas de citacao
    titular: str | None = None  # id do curriculo, se for um dos titulares


def familia_do_registro(tag: str) -> str:
    """Agrupa os registros do Lattes nas familias de relacao do plano de validacao."""

    if "BANCA" in tag:
        return "banca"
    if "ORIENTAC" in tag:
        return "orientacao"
    if tag == "PROJETO-DE-PESQUISA":
        return "projeto"
    if tag in ("SOFTWARE", "PATENTE", "PRODUTO-TECNOLOGICO", "PROCESSOS-OU-TECNICAS", "DESENHO-INDUSTRIAL", "MARCA", "TOPOGRAFIA-DE-CIRCUITO-INTEGRADO", "CULTIVAR-REGISTRADA", "CULTIVAR-PROTEGIDA"):
        return "software" if tag == "SOFTWARE" else "producao_tecnica"
    if tag.startswith("PARTICIPACAO-EM-") or tag in ("ORGANIZACAO-DE-EVENTO", "APRESENTACAO-DE-TRABALHO"):
        return "evento"
    if tag in ("ARTIGO-PUBLICADO", "ARTIGO-ACEITO-PARA-PUBLICACAO", "TRABALHO-EM-EVENTOS", "LIVRO-PUBLICADO-OU-ORGANIZADO", "CAPITULO-DE-LIVRO-PUBLICADO", "TEXTO-EM-JORNAL-OU-REVISTA", "OUTRA-PRODUCAO-BIBLIOGRAFICA", "PREFACIO-POSFACIO", "TRADUCAO"):
        return "publicacao"
    if tag in ("GRADUACAO", "ESPECIALIZACAO", "MESTRADO", "MESTRADO-PROFISSIONALIZANTE", "DOUTORADO", "POS-DOUTORADO", "LIVRE-DOCENCIA", "CURSO-TECNICO-PROFISSIONALIZANTE", "ENSINO-FUNDAMENTAL-PRIMEIRO-GRAU", "ENSINO-MEDIO-SEGUNDO-GRAU", "APERFEICOAMENTO", "RESIDENCIA-MEDICA") or tag.startswith("FORMACAO-COMPLEMENTAR"):
        return "formacao"
    if tag in ("VINCULOS", "ENSINO", "PESQUISA-E-DESENVOLVIMENTO", "CONSELHO-COMISSAO-E-CONSULTORIA", "DIRECAO-E-ADMINISTRACAO", "SERVICO-TECNICO-ESPECIALIZADO", "EXTENSAO-UNIVERSITARIA", "TREINAMENTO-MINISTRADO", "OUTRA-ATIVIDADE-TECNICO-CIENTIFICA", "PARTICIPACAO-EM-PROJETO", "ESTAGIO") or tag.startswith("ATIVIDADES-DE-"):
        return "vinculo"
    if "PREMIO" in tag:
        return "premio"
    return "producao_tecnica"


def classe_do_atributo(atributo: str) -> str | None:
    """Classe do item para um atributo do XML, ou None se nao nomeia nada util."""

    if atributo in ATRIBUTOS_PESSOA:
        return "pessoa"
    if "PERIODICO" in atributo or "ANAIS" in atributo or "REVISTA" in atributo or "JORNAL" in atributo:
        return "veiculo"
    if "LINHA-DE-PESQUISA" in atributo:
        return "area"
    if atributo.startswith("TITULO") or atributo == "NOME-DO-PROJETO" or atributo == "NOME-DO-SOFTWARE":
        return "titulo"
    if atributo == "NOME-DO-EVENTO":
        return "evento"
    if atributo in ("NOME-CURSO", "NOME-DO-CURSO", "NOME-CURSO-INGLES") or atributo.startswith("NOME-DO-CURSO"):
        return "curso"
    if "AREA" in atributo and atributo.startswith("NOME") or atributo == "NOME-DA-ESPECIALIDADE":
        return "area"
    if atributo.startswith("PALAVRA-CHAVE"):
        return "palavra"
    if any(p in atributo for p in ("INSTITUICAO", "ORGAO", "AGENCIA", "EDITORA", "EMPRESA", "UNIVERSIDADE", "UNIDADE")):
        return "organizacao"
    if atributo.startswith(("CIDADE", "PAIS", "LOCAL")):
        return "local"
    return None


class Catalogo:
    """Pessoas do gabarito: une grafias pelo ID do CNPq e pelo nome completo."""

    def __init__(self) -> None:
        self.pessoas: dict[str, Pessoa] = {}
        self._por_nome: dict[str, str] = {}
        # autorias com o ID do CNPq de uma pessoa e o nome de outra (erro de vinculo no
        # proprio Lattes): o ID e ignorado e a autoria fica com o nome escrito
        self.conflitos_de_id: list[tuple[str, str]] = []

    def _id_confiavel(self, id_cnpq: str, k: str, citacao: str | None) -> bool:
        p = self.pessoas.get(f"id:{id_cnpq}")
        if p is None or not p.nomes or not k:
            return True
        nomes, cits = sorted(p.nomes), sorted(p.citacoes)
        if pontuar_pessoa(k, nomes, cits) >= 85:
            return True
        return any(pontuar_pessoa(c, nomes, cits) >= 85 for c in formas_de_citacao(citacao))

    def registrar(self, nome: str, citacao: str | None = None, id_cnpq: str | None = None,
                  titular: str | None = None) -> str:
        k = chave(nome)
        if id_cnpq and not titular and not self._id_confiavel(id_cnpq, k, citacao):
            self.conflitos_de_id.append((id_cnpq, nome))
            id_cnpq = None
        if id_cnpq:
            pid = f"id:{id_cnpq}"
        elif k:
            pid = self._por_nome.get(k, f"nome:{k}")
        else:
            cit = formas_de_citacao(citacao)
            pid = f"cit:{cit[0]}" if cit else "desconhecida"
        p = self.pessoas.setdefault(pid, Pessoa(pid))
        if k:
            antigo = self._por_nome.get(k)
            # o mesmo nome completo visto antes sem ID passa a ser a pessoa com ID
            if antigo and antigo != pid and antigo.startswith("nome:") and pid.startswith("id:"):
                self._fundir(antigo, pid)
            p.nomes.add(k)
            if antigo is None or pid.startswith("id:"):
                self._por_nome[k] = pid
        p.citacoes.update(formas_de_citacao(citacao))
        if titular:
            p.titular = titular
        return pid

    def _fundir(self, de: str, para: str) -> None:
        origem = self.pessoas.pop(de, None)
        if not origem:
            return
        destino = self.pessoas[para]
        destino.nomes |= origem.nomes
        destino.citacoes |= origem.citacoes
        destino.titular = destino.titular or origem.titular
        for k, v in list(self._por_nome.items()):
            if v == de:
                self._por_nome[k] = para


def ler_curriculo(xml_path: Path, catalogo: Catalogo, registros: list[Registro]) -> str:
    """Le um XML e acrescenta seus registros a `registros`. Devolve o id do curriculo."""

    raiz = et.parse(xml_path).getroot()
    cv = raiz.get("NUMERO-IDENTIFICADOR") or xml_path.stem
    dg = raiz.find("DADOS-GERAIS")
    titular_nome = normalizar_texto(dg.get("NOME-COMPLETO", "")) if dg is not None else ""
    titular_pid = catalogo.registrar(
        titular_nome, dg.get("NOME-EM-CITACOES-BIBLIOGRAFICAS") if dg is not None else None,
        id_cnpq=cv, titular=cv,
    )
    titular_item = Item(titular_nome, chave(titular_nome), "pessoa", titular_pid)

    def visitar(elemento: et.Element, pai: et.Element | None, contexto: list[Item]) -> None:
        if elemento.tag in ELEMENTOS_OMITIDOS:
            return
        if _eh_registro(elemento, pai):
            reg = Registro(len(registros), cv, elemento.tag, familia_do_registro(elemento.tag))
            registros.append(reg)
            livres: list[str] = []
            aninhados: list[tuple[et.Element, et.Element]] = []
            coletar(elemento, reg, livres, aninhados, basicos=True)
            # contexto que o extrator escreveu na linha: titular (formacao, atuacao,
            # orientacoes) e a instituicao de uma atuacao profissional
            ctx = list(contexto)
            if "ORIENTAC" in elemento.tag and not any(i.pessoa == titular_pid for i in ctx):
                ctx.append(titular_item)
            for item in ctx:
                if not any(i.chave == item.chave and i.classe == item.classe for i in reg.itens):
                    reg.itens.append(item)
            # texto do registro para busca: descricoes e todos os itens que nao sao pessoa
            # (o titulo "Transmissao vertical do HTLV-1 na Bahia" menciona "Bahia")
            reg.texto_livre = chave(" ".join(livres + [i.valor for i in reg.itens if i.classe != "pessoa"]))
            definir_nucleo(reg)
            for filho, pai_filho in aninhados:
                visitar(filho, pai_filho, contexto)
            return
        novo = list(contexto)
        if elemento.tag == "DADOS-GERAIS" and titular_nome:
            novo.append(titular_item)
        if elemento.tag == "ATUACAO-PROFISSIONAL":
            inst = normalizar_texto(elemento.get("NOME-INSTITUICAO", ""))
            if inst:
                novo = [i for i in novo if i.classe != "organizacao"] + [Item(inst, chave(inst), "organizacao")]
        for filho in elemento:
            visitar(filho, elemento, novo)

    def coletar(no: et.Element, reg: Registro, livres: list[str],
                aninhados: list[tuple[et.Element, et.Element]], basicos: bool) -> None:
        atributos(no, reg, livres, basicos)
        for filho in no:
            if filho.tag in ELEMENTOS_OMITIDOS:
                continue
            if _eh_registro(filho, no):
                aninhados.append((filho, no))
            elif filho.tag in PESSOAS:
                _, attr_nome, attr_cit = PESSOAS[filho.tag]
                nome = normalizar_texto(filho.get(attr_nome, ""))
                pid = catalogo.registrar(nome, filho.get(attr_cit), filho.get("NRO-ID-CNPQ") or None)
                if nome:
                    reg.itens.append(Item(nome, chave(nome), "pessoa", pid))
            elif filho.tag in ITENS:
                _, principal, _ = ITENS[filho.tag]
                valor = normalizar_texto(filho.get(principal, ""))
                if valor:
                    classe = "organizacao" if filho.tag == "FINANCIADOR-DO-PROJETO" else "titulo"
                    reg.itens.append(Item(valor, chave(valor), classe))
            else:
                coletar(filho, reg, livres, aninhados, filho.tag.startswith("DADOS-BASICOS"))

    def atributos(no: et.Element, reg: Registro, livres: list[str], basicos: bool) -> None:
        for attr, bruto in no.attrib.items():
            valor = normalizar_texto(bruto)
            if not valor or attr.endswith(("-INGLES", "-EN")):
                continue
            if attr.startswith("ANO") and not reg.ano and valor[:4].isdigit():
                reg.ano = valor[:4]
            if len(valor) > TAMANHO_TEXTO_LONGO or attr.startswith(TEXTO_LIVRE):
                livres.append(valor)
                continue
            classe = classe_do_atributo(attr)
            if classe is None:
                continue
            item = Item(valor, chave(valor), classe)
            if classe == "pessoa":
                item.pessoa = catalogo.registrar(valor)
            # o titulo dos dados basicos e o nucleo; titulos de detalhamento entram depois
            if classe == "titulo" and basicos:
                reg.itens.insert(0, item)
            else:
                reg.itens.append(item)
        texto = normalizar_texto(no.text or "")
        if texto:
            livres.append(texto)

    visitar(raiz, None, [])
    return cv


def definir_nucleo(reg: Registro) -> None:
    """O item que nomeia o registro: titulo, senao evento, curso ou instituicao."""

    for classe in ("titulo", "evento", "curso", "organizacao"):
        for i, item in enumerate(reg.itens):
            if item.classe == classe and item.chave:
                reg.nucleo = i
                return


def montar_gabarito(xmls: list[Path]) -> tuple[list[Registro], Catalogo, dict[str, str]]:
    """Le todos os XMLs. Devolve registros, catalogo de pessoas e {id do cv: nome do titular}."""

    catalogo = Catalogo()
    registros: list[Registro] = []
    titulares: dict[str, str] = {}
    # titulares primeiro: o nome e as citacoes declaradas sao a referencia de cada ID,
    # antes que uma autoria com ID trocado em outro curriculo o registre com nome errado
    for xml in xmls:
        raiz = et.parse(xml).getroot()
        cv = raiz.get("NUMERO-IDENTIFICADOR") or xml.stem
        dg = raiz.find("DADOS-GERAIS")
        titulares[cv] = normalizar_texto(dg.get("NOME-COMPLETO", "")) if dg is not None else cv
        catalogo.registrar(titulares[cv], dg.get("NOME-EM-CITACOES-BIBLIOGRAFICAS") if dg is not None else None,
                           id_cnpq=cv, titular=cv)
    for xml in xmls:
        ler_curriculo(xml, catalogo, registros)
    # registros apontam para pessoas que podem ter sido fundidas depois
    for reg in registros:
        for item in reg.itens:
            if item.classe == "pessoa" and item.pessoa not in catalogo.pessoas:
                item.pessoa = catalogo._por_nome.get(item.chave, item.pessoa)
    return registros, catalogo, titulares
