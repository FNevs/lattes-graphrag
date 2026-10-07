"""Gera runs/<versao>/validacao/consultas/perguntas.json a partir do XML (custo zero).

Uso: .venv\\Scripts\\python.exe scripts\\validacao\\gerar_perguntas.py runs\\v2-npai
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gabarito import montar_gabarito  # noqa: E402
from perguntas import montar_perguntas  # noqa: E402
from validar_grafo import xmls_da_versao  # noqa: E402


def main() -> None:
    pasta = Path(sys.argv[1] if len(sys.argv) > 1 else "runs/v2-npai")
    registros, catalogo, titulares = montar_gabarito(xmls_da_versao(pasta))
    perguntas = montar_perguntas(registros, catalogo, titulares)
    destino = pasta / "validacao" / "consultas"
    destino.mkdir(parents=True, exist_ok=True)
    (destino / "perguntas.json").write_text(json.dumps(perguntas, ensure_ascii=False, indent=2), encoding="utf-8")
    for p in perguntas:
        print(f"{p['id']} [{p['classe']}/{p['tipo']}] {len(p['gabarito']):2d} itens | {p['pergunta']}")
    print(f"{len(perguntas)} perguntas -> {destino / 'perguntas.json'}")


if __name__ == "__main__":
    main()
