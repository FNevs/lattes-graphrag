# Ingestao de XML do Lattes

Este documento descreve como transformar curriculos Lattes em XML para texto
limpo na pasta `input/`, preparando os dados para o GraphRAG.

## Objetivo

Padronizar a ingestao dos XMLs com:

- extracao de texto de elementos e atributos;
- normalizacao de caracteres e espacos;
- saida consistente para indexacao.

## Fluxo

1. Entrada em `input_xml/*.xml`.
2. Leitura de cada XML com `xml.etree.ElementTree`.
3. Extracao de:
   - texto de elementos (`element.text`);
   - atributos (`element.attrib`).
4. Limpeza textual:
   - normalizacao Unicode (`NFKC`);
   - remocao de caracteres de controle;
   - compactacao de espacos.
5. Gravacao de um arquivo por curriculo em `input/<nome_arquivo>.txt`.

## Script principal

Arquivo: `scripts/extract_lattes_text.py`

Comando de uso:

```bash
python scripts/extract_lattes_text.py --input-dir input_xml --output-dir input
```

### Parametros

- `--input-dir`: pasta com XMLs (padrao: `input_xml`)
- `--output-dir`: pasta de saida (padrao: `input`)
- `--log-level`: nivel de log (padrao: `INFO`)

## Estrutura de codigo

- `scripts/extract_lattes_text.py`: regras de extracao, limpeza, I/O e CLI.

## Tratamento de erros

O pipeline levanta excecoes especificas para facilitar depuracao:

- `FileNotFoundError`: diretorio/arquivo inexistente;
- `ValueError`: sem XMLs na pasta ou sem texto valido extraido;
- `xml.etree.ElementTree.ParseError`: XML malformado.

