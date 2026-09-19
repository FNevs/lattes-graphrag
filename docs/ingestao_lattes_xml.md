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

## Limitação corrigida (encontrada na auditoria do artefato preliminar)

No TCC1, a normalização usada em `normalizar_texto` era **NFKC**, e isso
apagava indicadores ordinais do português: "70ª Reunião" virava "70A Reunião"
(o "ª" é convertido para "a" simples). O defeito se propagava para o grafo — a
entidade final ficava gravada como "70A REUNIÃO ANUAL DA SBPC". A NFKC também
partia tokens com acento solto digitado na fonte ("SUCESU´2005" virava
"SUCESU ́2005"), gerando entidades duplicadas.

**Corrigido em 19/09/2026:** a função usa `unicodedata.normalize("NFC", texto)`.
No currículo do TCC1, a NFC recupera os 11 ordinais (1 "ª", 10 "º") e os acentos
soltos, e altera zero caracteres do XML. Ver `HANDOFF-TCC2.md`, seção 4, item 1,
e as outras limitações descobertas na mesma auditoria (grafias divergentes na
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
