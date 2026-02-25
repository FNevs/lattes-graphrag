# Lattes GraphRAG

Projeto para preparar dados de curriculos Lattes em texto e indexar com
GraphRAG.

## Estrutura recomendada

```text
lattes-graphrag/
  input_xml/                  # XMLs brutos do Lattes
  input/                      # TXTs limpos para o GraphRAG
  prompts/                    # Prompts usados no pipeline GraphRAG
  scripts/
    extract_lattes_text.py    # Extracao + limpeza XML -> TXT
  settings.yaml
  .env
  .env.example
  docs/
    ingestao_lattes_xml.md
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

Detalhes de design e boas praticas deste pipeline:

- `docs/ingestao_lattes_xml.md`

