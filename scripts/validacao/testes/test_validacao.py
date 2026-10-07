"""Testes de unidade da validacao, com casos construidos (resposta conhecida de antemao).

Rodar na raiz do projeto:
    .venv\\Scripts\\python.exe -m unittest discover -s scripts\\validacao\\testes -v
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from alinhamento import alinhar  # noqa: E402
from gabarito import montar_gabarito  # noqa: E402
from normalizacao import chave, contem, formas_de_citacao, nome_compativel, pontuar_pessoa, semelhanca  # noqa: E402

XML = """<?xml version="1.0" encoding="ISO-8859-1"?>
<CURRICULO-VITAE NUMERO-IDENTIFICADOR="1111222233334444">
  <DADOS-GERAIS NOME-COMPLETO="Ana Beatriz de Souza Lima"
                NOME-EM-CITACOES-BIBLIOGRAFICAS="LIMA, A. B. S.;SOUZA LIMA, Ana Beatriz;LIMA, ANA">
    <FORMACAO-ACADEMICA-TITULACAO>
      <DOUTORADO NOME-INSTITUICAO="Universidade Federal do Exemplo" NOME-CURSO="Ciência de Dados"
                 TITULO-DA-DISSERTACAO-TESE="Redes de coautoria em currículos" ANO-DE-CONCLUSAO="2015"
                 NOME-COMPLETO-DO-ORIENTADOR="Carlos Eduardo Pereira"/>
    </FORMACAO-ACADEMICA-TITULACAO>
  </DADOS-GERAIS>
  <PRODUCAO-BIBLIOGRAFICA>
    <ARTIGOS-PUBLICADOS>
      <ARTIGO-PUBLICADO SEQUENCIA-PRODUCAO="1">
        <DADOS-BASICOS-DO-ARTIGO TITULO-DO-ARTIGO="Grafos de conhecimento em português" ANO-DO-ARTIGO="2021"/>
        <DETALHAMENTO-DO-ARTIGO TITULO-DO-PERIODICO-OU-REVISTA="Revista Exemplar"/>
        <AUTORES NOME-COMPLETO-DO-AUTOR="Ana Beatriz de Souza Lima" NOME-PARA-CITACAO="LIMA, A. B. S."
                 NRO-ID-CNPQ="1111222233334444"/>
        <AUTORES NOME-COMPLETO-DO-AUTOR="Bruno Costa Ramos" NOME-PARA-CITACAO="RAMOS, B. C."/>
        <AUTORES NOME-COMPLETO-DO-AUTOR="Paulo Teixeira Gomes" NOME-PARA-CITACAO="GOMES, P. T."
                 NRO-ID-CNPQ="1111222233334444"/>
        <PALAVRAS-CHAVE PALAVRA-CHAVE-1="Grafos" PALAVRA-CHAVE-2="Lattes"/>
      </ARTIGO-PUBLICADO>
    </ARTIGOS-PUBLICADOS>
  </PRODUCAO-BIBLIOGRAFICA>
</CURRICULO-VITAE>
"""


class Normalizacao(unittest.TestCase):
    def test_chave_ignora_acento_caixa_e_pontuacao(self):
        self.assertEqual(chave("Ciência de Dados: Teoria!"), "ciencia de dados teoria")
        self.assertEqual(chave("GRAFOS DE CONHECIMENTO EM PORTUGUÊS"), chave("Grafos de conhecimento em português"))

    def test_contem_exige_palavras_inteiras(self):
        self.assertTrue(contem("o artigo de ana lima foi", "ana lima"))
        self.assertFalse(contem("mariana limao", "ana lima"))

    def test_formas_de_citacao_invertem_sobrenome(self):
        self.assertEqual(formas_de_citacao("LIMA, A. B. S.;SOUZA LIMA, Ana Beatriz"),
                         ["a b s lima", "ana beatriz souza lima"])
        self.assertEqual(formas_de_citacao("LIMA, A. / RAMOS, B."), ["a lima", "b ramos"])

    def test_semelhanca_nao_casa_parte_generica(self):
        self.assertLess(semelhanca("universidade", "universidade federal do exemplo"), 85)
        self.assertGreaterEqual(semelhanca("redes de coautoria em curriculos", "redes de coautoria em curriculo"), 95)


class NomesDePessoa(unittest.TestCase):
    COMPLETO = chave("Ana Beatriz de Souza Lima")

    def test_formas_abreviadas_compativeis(self):
        for forma in ("Ana Lima", "A. Lima", "A. B. S. Lima", "LIMA, A. B. S.", "Ana Beatriz Souza Lima", "Ana B. Lima"):
            alvo = formas_de_citacao(forma)[0] if "," in forma else chave(forma)
            self.assertTrue(nome_compativel(alvo, self.COMPLETO), forma)

    def test_formas_incompativeis(self):
        for forma in ("Ana Silva", "Lima", "Beatriz Ramos", "B. Lima Souza Costa", "Souza Lima"):
            self.assertFalse(nome_compativel(chave(forma), self.COMPLETO), forma)

    def test_inicial_precisa_ser_do_primeiro_nome(self):
        # "A. Lima" nao pode virar "Carlos Augusto Lima" nem "Rafael Lima Andrade"
        self.assertFalse(nome_compativel("a lima", chave("Carlos Augusto Lima")))
        self.assertFalse(nome_compativel("a lima", chave("Rafael Lima Andrade")))

    def test_citacao_curta_nao_identifica_nome_completo_de_outra_pessoa(self):
        citacoes = formas_de_citacao("LIMA, A.")
        self.assertLess(pontuar_pessoa(chave("Alberto Rocha Lima"), [self.COMPLETO], citacoes), 85.0)
        # o sentido inverso vale para nome completo abreviado no XML
        self.assertEqual(pontuar_pessoa(chave("Bruno Costa Ramos"), [chave("Bruno C. Ramos")], []), 96.0)

    def test_limitacao_conhecida_segundo_nome(self):
        # Sem saber se a 2a palavra e prenome ou sobrenome ("Hugo Saba" e prenome +
        # sobrenome), "ana beatriz" e aceita como forma de "Ana Beatriz de Souza Lima".
        # Limitacao documentada; ela so pesa em homonimos com os dois primeiros nomes iguais.
        self.assertTrue(nome_compativel("ana beatriz", self.COMPLETO))

    def test_pontuacao_de_pessoa(self):
        citacoes = formas_de_citacao("LIMA, A. B. S.;LIMA, ANA")
        self.assertEqual(pontuar_pessoa("a b s lima", [self.COMPLETO], citacoes), 100.0)
        self.assertEqual(pontuar_pessoa("a lima", [self.COMPLETO], citacoes), 96.0)
        self.assertLess(pontuar_pessoa("joao lima", [self.COMPLETO], citacoes), 85.0)


class GabaritoEAlinhamento(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        caminho = Path(cls.tmp.name) / "1111222233334444.xml"
        caminho.write_text(XML, encoding="iso-8859-1")
        cls.registros, cls.catalogo, cls.titulares = montar_gabarito([caminho])

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_registros_e_familias(self):
        familias = sorted(r.familia for r in self.registros)
        self.assertEqual(familias, ["formacao", "publicacao"])
        artigo = next(r for r in self.registros if r.familia == "publicacao")
        self.assertEqual(artigo.itens[artigo.nucleo].valor, "Grafos de conhecimento em português")
        classes = sorted(i.classe for i in artigo.itens)
        self.assertEqual(classes, ["palavra", "palavra", "pessoa", "pessoa", "pessoa", "titulo", "veiculo"])

    def test_id_do_cnpq_com_nome_de_outra_pessoa_e_ignorado(self):
        # erro de vinculo no proprio Lattes: autoria com o ID da titular e outro nome
        titular = self.catalogo.pessoas["id:1111222233334444"]
        self.assertNotIn("paulo teixeira gomes", titular.nomes)
        self.assertIn("nome:paulo teixeira gomes", self.catalogo.pessoas)
        self.assertEqual(len(self.catalogo.conflitos_de_id), 1)

    def test_titular_unifica_grafias_pelo_id(self):
        titular = self.catalogo.pessoas["id:1111222233334444"]
        self.assertEqual(titular.titular, "1111222233334444")
        self.assertIn("a b s lima", titular.citacoes)
        formacao = next(r for r in self.registros if r.familia == "formacao")
        self.assertIn("id:1111222233334444", {i.pessoa for i in formacao.itens})

    def test_alinhamento_de_variantes(self):
        entidades = [("A. B. S. LIMA", "PERSON"), ("ANA LIMA", "PERSON"), ("BRUNO RAMOS", "PERSON"),
                     ("GRAFOS DE CONHECIMENTO EM PORTUGUES", "PUBLICATION"), ("CIENCIA DE DADOS", "COURSE"),
                     ("PESSOA INVENTADA DA SILVA", "PERSON")]
        casou = {c.entidade for c in alinhar(entidades, self.registros, self.catalogo)}
        self.assertEqual(casou, {"A. B. S. LIMA", "ANA LIMA", "BRUNO RAMOS",
                                 "GRAFOS DE CONHECIMENTO EM PORTUGUES", "CIENCIA DE DADOS"})


if __name__ == "__main__":
    unittest.main()
