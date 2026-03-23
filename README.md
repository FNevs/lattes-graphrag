# Lattes GraphRAG

Projeto para preparar dados de curriculos Lattes em texto e indexar com
GraphRAG.

## Diagrama de arquitetura

![Diagrama de arquitetura do pipeline](docs/diagramas/diagrama_arquitetura_pipeline.png)

## Estrutura do repositorio

```text
lattes-graphrag/
  input_xml/                  # XMLs brutos do Lattes
  input/                      # TXTs limpos para o GraphRAG
  prompts/                    # Prompts usados no pipeline GraphRAG
  scripts/
    extract_lattes_text.py    # Extracao + limpeza XML -> TXT
  docs/
    fundamentacao_tcc.md      # Fundamentacao academica (objetivo, problema, DSR, PRISMA)
    CONTEXTO_PROJETO.md       # Briefing completo para IAs e modelos
    ingestao_lattes_xml.md    # Documentacao tecnica do pipeline de ingestao
    diagramas/                # Diagramas do projeto (Excalidraw, PNG)
  settings.yaml
  .env
  .env.example
  requirements.txt
```

## Requisitos

- Python 3.10+
- Ambiente virtual ativo
- GraphRAG configurado no `settings.yaml`

Instalacao sugerida:

```bash
pip install -r requirements.txt
```

## Configuracao de ambiente

Crie o arquivo `.env` com base no `.env.example`.

```bash
GRAPHRAG_API_KEY=<sua_chave_azure_openai>
```

## Como gerar os textos a partir do XML

1. Coloque os arquivos XML na pasta `input_xml/`.
2. Execute:

```bash
python scripts/extract_lattes_text.py --input-dir input_xml --output-dir input
```

3. O script cria um `.txt` por XML na pasta `input/`.

## Proximo passo no GraphRAG

Depois da extracao, rode o indexador do GraphRAG para gerar o grafo sobre os
arquivos da pasta `input/`.

## Documentacao adicional

- `docs/CONTEXTO_PROJETO.md` — Briefing completo para transferir contexto a outras IAs/modelos
- `docs/fundamentacao_tcc.md` — Fundamentacao academica (objetivo, pergunta de pesquisa, DSR, PRISMA)
- `docs/ingestao_lattes_xml.md` — Pipeline de ingestao XML
- `docs/diagramas/` — Diagramas de arquitetura e fluxo do projeto
