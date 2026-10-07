"""Testes de regressao com os dados reais do V2 (rodam so onde runs/ e lattesNAPI/ existem).

Casos conhecidos que a validacao precisa continuar acertando. Rodar depois de
`validar_grafo.py runs/v2-npai`:
    .venv\\Scripts\\python.exe -m unittest discover -s scripts\\validacao\\testes -v
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[3]
V2 = RAIZ / "runs" / "v2-npai"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@unittest.skipUnless((V2 / "validacao" / "metricas.json").exists(), "dados do V2 ausentes nesta maquina")
class RegressaoV2(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import pandas as pd

        cls.metricas = json.loads((V2 / "validacao" / "metricas.json").read_text(encoding="utf-8"))
        cls.sem_fonte = (V2 / "validacao" / "sem_fonte.txt").read_text(encoding="utf-8").splitlines()
        cls.casamentos = pd.read_parquet(V2 / "validacao" / "casamentos.parquet")

    def test_nome_vazado_dos_exemplos_dos_prompts_fica_sem_fonte(self):
        # unico vazamento conhecido dos exemplos sinteticos (MANIFEST do V2)
        self.assertTrue(any(s.startswith("MARCELO DANTAS ARAG") for s in self.sem_fonte))
        vazado = self.casamentos[self.casamentos.entidade.str.startswith("MARCELO DANTAS ARAG")]
        self.assertEqual(len(vazado), 0, "o nome inventado nao pode casar com nada do XML")

    def test_variantes_de_titular_convergem_sem_misturar_coautor(self):
        por_titular = self.metricas["metricas"]["por_limiar"]["90"]["entidades_por_titular"]
        # 16 grafias do mesmo titular no grafo, sem coautores com ID trocado no Lattes
        self.assertGreaterEqual(por_titular["Hugo Saba Pereira Cardoso"], 12)
        self.assertLessEqual(por_titular["Hugo Saba Pereira Cardoso"], 20)
        self.assertGreater(self.metricas["conflitos_de_id"], 0)

    def test_maior_par_de_titulares_bate_com_o_xml(self):
        pares = {(p["a"], p["b"]): p for p in self.metricas["pares_titulares"]}
        par = pares[("Hugo Saba Pereira Cardoso", "Eduardo Manuel de Freitas Jorge")]
        self.assertEqual(par["grafo"], 161)  # o numero mostrado no site
        self.assertLessEqual(abs(par["xml"] - par["grafo"]), 15)

    def test_precisao_estavel(self):
        r = self.metricas["metricas"]["por_limiar"]["90"]
        self.assertGreater(r["precisao"], 0.9)


if __name__ == "__main__":
    unittest.main()
