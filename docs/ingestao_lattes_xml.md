# Ingestão de XML do Lattes

> Atualizado em 2026-09: adicionada a seção "Limitação conhecida" (bug de
> normalização encontrado na auditoria do artefato preliminar) e a seção
> "Fonte alternativa: db.dump", sobre a nova via de ingestão para o
> escalonamento do TCC2. O restante do documento (fluxo, script, parâmetros)
> segue válido.

Este documento descreve como transformar currículos Lattes em XML para texto
limpo na pasta `input/`, preparando os dados para o GraphRAG.

## Objetivo

Padronizar a ingestão dos XMLs com:

- extração de texto de elementos e atributos;
- normalização de caracteres e espaços;
- saída consistente para indexação.

## Fluxo

1. Entrada em `input_xml/*.xml`.
2. Leitura de cada XML com `xml.etree.ElementTree`.
3. Extração de:
   - texto de elementos (`element.text`);
   - atributos (`element.attrib`).
4. Limpeza textual (função `normalizar_texto`, em
   `scripts/extract_lattes_text.py`, ~linha 72):
   - normalização Unicode;
   - remoção de caracteres de controle;
   - compactação de espaços.
5. Gravação de um arquivo por currículo em `input/<nome_arquivo>.txt`.

## Script principal

Arquivo: `scripts/extract_lattes_text.py`

Comando de uso:

```bash
python scripts/extract_lattes_text.py --input-dir input_xml --output-dir input
```

### Parâmetros

- `--input-dir`: pasta com XMLs (padrão: `input_xml`)
- `--output-dir`: pasta de saída (padrão: `input`)
- `--log-level`: nível de log (padrão: `INFO`)

## Estrutura de código

- `scripts/extract_lattes_text.py`: regras de extração, limpeza, I/O e CLI.

## Tratamento de erros

O pipeline levanta exceções específicas para facilitar depuração:

- `FileNotFoundError`: diretório/arquivo inexistente;
- `ValueError`: sem XMLs na pasta ou sem texto válido extraído;
- `xml.etree.ElementTree.ParseError`: XML malformado.

---

## Limitação conhecida (encontrada na auditoria do artefato preliminar)

A normalização usada em `normalizar_texto` é **NFKC**, e isso apaga
indicadores ordinais do português: "70ª Reunião" vira "70A Reunião" (o "ª"
é convertido para "a" simples). Esse defeito se propaga para o grafo — a
entidade final fica gravada como "70A REUNIÃO ANUAL DA SBPC".

**Correção pendente:** trocar `unicodedata.normalize("NFKC", texto)` por
`unicodedata.normalize("NFC", texto)` nesta função, e reindexar. NFC preserva
o "ª"/"º" e ainda resolve os casos de codificação que a NFKC existia para
tratar. Ver `HANDOFF-TCC2.md`, seção 4, item 1, para o detalhamento completo
e outras limitações descobertas na mesma auditoria (grafias divergentes na
fonte, uma alucinação de extração, ausência de resolução de entidades).

---

## Fonte alternativa: `db.dump` (para o escalonamento do TCC2)

Além dos XMLs individuais em `input_xml/`, foi recebido um dump PostgreSQL
(`db.dump`, formato custom, ~263 MB) contendo vários currículos — a fonte
prevista para expandir de 1 para um conjunto reduzido de currículos.

Esse dump **não passa pelo fluxo de XML acima**: é um banco relacional, não
arquivos XML. O caminho recomendado é gerar, a partir das tabelas do banco,
um `.txt` por pesquisador (mesmo formato de saída da etapa 5 acima), já
usando NFC em vez de NFKC na normalização. Passo a passo completo (restaurar
o dump, inspecionar o schema, script de exportação, cuidados de custo e de
LGPD) em `HANDOFF-TCC2.md`, seção 9.

`db.dump` não deve ser versionado neste repositório (dado pessoal sensível).
