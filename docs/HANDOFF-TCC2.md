# Handoff TCC2 — Projeto GraphRAG sobre Currículos Lattes

Documento de continuidade para retomar o projeto no TCC2. Leia junto com a
monografia parcial (PDF no repositório): a monografia tem o *porquê*; este
documento tem o *estado atual, o que está quebrado e o que fazer*.

Autor: Filipe Neves Silva (UNEB, Sistemas de Informação). Orientador: Eduardo
Manuel de Freitas Jorge. Última atualização: 2026-07.

---

## 1. O que é o projeto

Pipeline que transforma Currículos Lattes em XML num grafo do conhecimento
consultável em linguagem natural, usando o framework **GraphRAG** (Microsoft) com
modelos do **Azure OpenAI**. Objetivo: consulta semântica e relacional sobre
currículos, indo além da busca por palavra-chave. Metodologia: Design Science
Research. A lacuna (validada por revisão sistemática): ninguém fez isso sobre o
Lattes, em português, com o currículo completo e relações explícitas.

---

## 2. Estado atual (run de 25/02/2026, um único currículo)

Executado sobre **um** currículo Lattes real (Eduardo M. F. Jorge). Números lidos
diretamente dos artefatos (não de memória):

| artefato | valor |
|---|---|
| entities.parquet | 1.368 |
| relationships.parquet | 1.403 |
| communities.parquet | 232 |
| community_reports.parquet | 232 |
| text_units.parquet | 105 |
| documents.parquet | 1 |
| graph.graphml | 1.114 nós / 1.401 arestas |

Entidades por tipo: PERSON 580, EVENT 526, ORGANIZATION 204, GEO 52, SOFTWARE 6.
Conta do grafo: 1.368 − 321 isoladas + 67 nós-fantasma = 1.114 nós.
Consultas: 5 executadas (basic/local/global); 38/38 citações conferem com os
artefatos, sem alucinação de fonte.

---

## 3. Arquivos-chave do repositório

- `scripts/extract_lattes_text.py` — pré-processamento do XML (limpeza,
  normalização). **A normalização NFKC está na função `normalizar_texto`, linha 72.**
- `scripts/mapear_grafo.py` — gera estatísticas dos parquet (pandas). Não visualiza.
- `scripts/figura_ego.py` — gera a ego-network (networkx + matplotlib), reprodutível
  com semente fixa. (Confirme que este arquivo veio junto — ele estava só na máquina
  de execução.)
- `settings.yaml` — configuração do GraphRAG.
- `prompts/` — prompts de extração, sumarização e busca.
- `input_xml/` e `input/` — XML-fonte e texto pré-processado.
- `output/` — artefatos (parquet, graph.graphml, LanceDB).

Config atual (settings.yaml): chunk size 1200, overlap 100,
entity_types = [organization, person, geo, event], max_gleanings 1,
max_cluster_size 10, modelo `gpt-4.1-mini`, embeddings `text-embedding-3-small`.

**Mudança de modelo (set/2026).** O TCC1 usou `gpt-4o-mini`. A assinatura antiga
expirou em 01/05/2026; a nova (Azure for Students) só permite as regiões
canadacentral, spaincentral, belgiumcentral, mexicocentral e italynorth, e em
todas elas a cota de `gpt-4o-mini` é zero. Por isso o TCC2 usa `gpt-4.1-mini`
(versão 2025-04-14, aposentadoria prevista para 14/04/2027) no recurso
`lattes-graphrag-tcc`, em spaincentral. Os embeddings não mudaram. Consequência:
os números do TCC1 (1.368 / 1.403 / 232) são baseline de outro modelo — antes de
aplicar a correção NFC, reindexar o mesmo currículo com o modelo novo para
separar o efeito da troca de modelo do efeito da correção.

---

## 4. Limitações conhecidas → correção (o coração do TCC2)

Cada defeito tem uma causa e uma correção diferente. Não tratar tudo como "erro do
LLM" — só um dos casos é do modelo.

1. **Pré-processamento (culpa nossa).** A normalização **NFKC** converte o indicador
   ordinal: "70ª" vira "70A". → **Trocar NFKC por NFC** em
   `extract_lattes_text.py:72` e **reindexar**.
2. **Fonte (culpa do dado).** O Lattes traz grafias divergentes ("Manuel"/"Manoel",
   "Semp Toshiba"/"SempToshiba"). A extração reproduz fielmente. → mitigável na etapa
   de resolução de entidades (item abaixo).
3. **Modelo (alucinação de extração).** Entidade "FIUSCRUZ" não existe na fonte (lá é
   "Fiocruz"). → revisar prompt de extração / validação pós-extração.
4. **Sem resolução de entidades.** Um mesmo pesquisador vira até 7 variantes (ex.:
   "Hugo Saba", "Hugo Saba Pereira Cardoso"...). → **adicionar etapa de deduplicação/
   entity resolution** ao pipeline.
5. **Diluição do sujeito.** Só 10 dos 232 community reports citam o pesquisador
   nominalmente; por isso a busca global sem o nome se perde. → revisar
   `max_cluster_size` e/ou a estratégia de consulta ao escalar.
6. **Ruído estrutural.** 321 entidades isoladas (saem do grafo) e 67 nós-fantasma
   (só como ponta de relação); tipo `SOFTWARE` aparece sem estar em `entity_types`
   (vazou por gleaning). → limpar na modelagem específica do domínio.

---

## 5. Tarefas do TCC2 (em ordem sugerida)

1. **Corrigir e reindexar**: NFKC → NFC; conferir que "70ª" e afins sobrevivem.
2. **Escalar**: expandir de 1 para um conjunto reduzido de currículos Lattes.
3. **Resolução de entidades**: unir variantes do mesmo nome antes/depois da extração.
4. **Executar o plano de validação** (5 frentes, ver seção 6).
5. **Analisar e redigir** os resultados na versão final da monografia.

---

## 6. Plano de validação (as 5 frentes)

Abordagem mista, por consulta, registrada em planilha:
1. **Estrutura do grafo**: entidades por tipo, nº de relações, centralidade de grau,
   modularidade (Leiden), nº e tamanho médio de comunidades, distribuição de graus.
2. **Validação manual de amostra**: conferir amostra de entidades/relações contra o
   XML-fonte; calcular precisão amostral.
3. **Escala Likert (1–5)**: Relevância, Acurácia, Completude, Legibilidade das
   respostas.
4. **Contagem de alucinações**: corretas / parcialmente incorretas / alucinadas /
   sem resposta.
5. **Comparação com baseline**: busca lexical + vetorial pura (sem grafo), nas
   mesmas consultas.

Desenho para separar efeito de método x âncora: N perguntas × {anafórica, nominal}
× {basic, local, global}, com saída **redirecionada para arquivo** (ver armadilha 4).

---

## 7. Armadilhas (lições já aprendidas — não repetir)

1. **Nunca reporte número de memória.** Leia sempre dos `.parquet`. Os números
   antigos da monografia (1.493 / 648 / 243) eram fabricação — não vinham de run
   nenhum. Os corretos são 1.368 / 1.403 / 232.
2. **venv quebrado entre máquinas.** O `.venv` foi criado com Python 3.12; máquinas
   com 3.13 não leem os pacotes. Para ler parquet sem o venv: `pyarrow`
   (`pq.ParquetFile(x).metadata.num_rows`).
3. **Modularidade: não confundir duas partições.** O 0,857 do Gephi é uma partição
   Leiden NOVA rodada por cima do grafo. A partição real que o GraphRAG usou nos
   community reports tem Q ≈ 0,656 (nível 0), porque `max_cluster_size=10` força
   comunidades pequenas. Ao reportar modularidade, diga QUAL das duas.
4. **Salve as respostas de consulta em arquivo.** O registro anterior corrompeu ao
   copiar do console (streaming repintou linhas). Use
   `graphrag query ... > resposta.md 2>&1`.
5. **Azure OpenAI é obrigatório** para indexar e consultar. Sem ele, dá só para
   auditar artefatos offline, não gerar novos.

---

## 8. Cronograma TCC2 (jul–dez 2026)

- Jul–Ago: expansão do artefato para conjunto reduzido de currículos.
- Ago–Set: execução das consultas representativas.
- Set–Out: aplicação do protocolo de validação.
- Out–Nov: análise dos resultados e redação final.
- Dez: defesa.

A etapa de maior risco técnico (montar o pipeline ponta a ponta) já está vencida.

---

## 9. Usar o `db.dump` (base com vários currículos) para escalar

O arquivo `db.dump` (~263 MB) é um **dump do PostgreSQL em formato custom**
(assinatura `PGDMP`). Contém vários currículos — é a fonte para a etapa de
escalonamento (tarefa 2). Atenção: o pipeline atual lê **XML**; este dump é um
**banco relacional**. É preciso uma ponte.

### 9.1 Restaurar o dump
Requer PostgreSQL instalado (client + server). Como é formato custom, use
`pg_restore` (NÃO `psql < arquivo`).

```
# 1) inspecione o conteúdo SEM restaurar (lista as tabelas/objetos):
pg_restore -l db.dump

# 2) crie o banco e restaure:
createdb simcc
pg_restore -d simcc --no-owner --no-privileges db.dump
```
`--no-owner --no-privileges` evita erros de role ao restaurar em outra máquina.

### 9.2 Explorar o schema
```
psql -d simcc -c "\dt"          # lista as tabelas
psql -d simcc -c "\d researchers"   # colunas de uma tabela (ajuste o nome)
```
Procure tabelas de pesquisadores e de produção (na linhagem SIMCC/Café havia
`researchers` e `bibliographic_production`). Anote os nomes reais — o script
abaixo depende deles.

### 9.3 Ponte para o GraphRAG (recomendado: exportar 1 texto por pesquisador)
O GraphRAG indexa a pasta de entrada (`input/`), um documento por arquivo. Em vez
de reconstruir XML, o caminho mais simples é gerar **um `.txt` limpo por
pesquisador** direto do banco e apontar o GraphRAG para essa pasta. Template
(ajuste nomes de tabela/coluna após o `\d`):

```python
# scripts/exportar_do_banco.py  (TEMPLATE — ajuste após inspecionar o schema)
import psycopg2, unicodedata, re
from pathlib import Path

conn = psycopg2.connect(dbname="simcc", user="postgres", host="localhost")
cur = conn.cursor()
cur.execute("SELECT id, nome FROM researchers")          # ajuste
Path("input").mkdir(exist_ok=True)
for rid, nome in cur.fetchall():
    p = conn.cursor()
    p.execute("SELECT title, abstract FROM bibliographic_production WHERE researcher_id=%s", (rid,))  # ajuste
    partes = [nome] + [f"{t}. {a}" for t, a in p.fetchall()]
    texto = unicodedata.normalize("NFC", " ".join(filter(None, partes)))  # NFC, não NFKC!
    texto = re.sub(r"\s+", " ", texto).strip()
    Path(f"input/{rid}.txt").write_text(texto, encoding="utf-8")
```
Depois é o fluxo normal: `graphrag index ...` sobre `input/`.

### 9.4 Cuidados importantes
- **Comece pequeno.** Cada documento custa tokens de Azure na indexação (1 currículo
  já gerou 1.368 entidades). Selecione um **conjunto reduzido** (ex.: um mesmo grupo/
  NPAI) — não indexe os 263 MB de uma vez. Estime custo antes.
- **Escolha currículos que se conectam.** O ganho de escalar é ver relações ENTRE
  pesquisadores (coautoria, mesma instituição). Selecionar um grupo coeso faz o grafo
  ter arestas cruzadas reais — que é a tese do trabalho.
- **Use NFC, não NFKC** já na exportação (mesma correção da limitação 1).
- **Documente a mudança de fonte** na monografia do TCC2: o Estágio 1 da arquitetura
  passa a ter, além do XML, a entrada via banco relacional.
- **Dado pessoal (LGPD).** São currículos reais de pessoas. NÃO suba o `db.dump` nem
  os `.txt` gerados para repositório público. Mantenha local/privado.
- Não sei o schema exato daqui — rode o `pg_restore -l` e o `\d` primeiro; o script
  acima é template e depende dos nomes reais das tabelas.