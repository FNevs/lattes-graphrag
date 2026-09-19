# Registro de execução do TCC2

Diário técnico da fase de melhoria do pipeline (a partir de 18/09/2026). Complementa
`HANDOFF-TCC2.md` (o *porquê* e o plano) com o *que foi feito, quanto custou, o que
se descobriu e onde parou*. Todos os números abaixo foram lidos dos artefatos ou do
medidor da Azure — nenhum é de memória.

Evidências brutas (scripts de diagnóstico, logs, simulações): `runs/_evidencias-sessao-2026-09/`
(ignorado pelo Git por conter trechos de currículos; tem um `README.md` próprio).

---

## 1. Onde paramos (resumo em uma tela)

| passo | o quê | estado | pasta | custo real (Azure) |
|---|---|---|---|---|
| 0 | congelar o artefato do TCC1 (V0) | ✅ | `runs/v0-tcc1/` | US$ 0,00 |
| 1 | mesmo currículo e texto (NFKC), modelo novo | ✅ | `runs/v1-base-nfkc/` | US$ 1,83 |
| 2 | correção NFKC → NFC e reindexação | ✅ | `runs/v1-nfc/` | US$ 1,60 |
| 2b | prompts adaptados ao domínio Lattes | ⏳ **em andamento** | `prompts/lattes/` | US$ 0,05 até aqui |
| 3 | 8 XMLs do NPAI (V2) | pendente | — | ~US$ 11 (est.) |
| 4 | validação cruzada com o banco SIMCC | pendente | — | US$ 0 |
| 5 | 20–30 currículos do `db.dump` (V3) | pendente | — | ~US$ 15–20 (est.) |
| — | consultas fixas para o site | pendente | — | ~US$ 9 (est.) |

**Gasto acumulado: US$ 3,48 de US$ 100.** Projeção total com reserva: ~US$ 70–75.

**Próxima ação:** passo 2b, opção B (curadoria dos exemplos) — ver seção 7.

---

## 2. Infraestrutura Azure (nova)

A assinatura antiga expirou em **01/05/2026** (crédito gratuito esgotado; a Microsoft
excluiu assinatura e recursos). Em 18/09/2026 foi ativado o **Azure for Students**:
US$ 100 de crédito, válido até **18/09/2027**, sem cartão.

| item | valor |
|---|---|
| Assinatura | Azure for Students — tenant "Diretório Padrão" `6bc88188-5c7f-4a63-bb18-6eeb53697f98` |
| Login na CLI | `az login --tenant 6bc88188-5c7f-4a63-bb18-6eeb53697f98` (o `az login` puro falha: MFA por tenant) |
| Regiões permitidas (política da assinatura) | canadacentral, spaincentral, belgiumcentral, mexicocentral, italynorth |
| Cota de `gpt-4o-mini` nessas regiões | **zero em todas** → impossível manter o modelo do TCC1 |
| Resource group / recurso | `rg-lattes-graphrag` / `lattes-graphrag-tcc` (spaincentral) |
| Endpoint | `https://lattes-graphrag-tcc.openai.azure.com` |
| Chat | `gpt-4.1-mini` v2025-04-14, GlobalStandard, 200K TPM (aposenta em 14/04/2027) |
| Embeddings | `text-embedding-3-small` v1, GlobalStandard, 1000K TPM (igual ao TCC1) |
| Orçamento | `alerta-tcc`: US$ 10/mês, alertas em 50% e 90% para o Owner |
| Chave | `.env` → `GRAPHRAG_API_KEY` (ASCII, sem BOM) |

### Como medir custo (usar sempre a Azure, não o log)

O log do GraphRAG **subconta ~5%** em relação ao medidor da Azure. A página "Educação"
e o Gerenciamento de Custos atrasam 24–48 h (em 19/09 ainda estavam vazios). As
**métricas de tokens do recurso** saem em minutos:

- Portal: recurso `lattes-graphrag-tcc` → Monitoramento → Métricas →
  *Processed Prompt Tokens* e *Generated Tokens*, agregação Soma, dividir por
  *ModelDeploymentName*.
- CLI (PowerShell), por hora:

```powershell
$id = (az cognitiveservices account show -n lattes-graphrag-tcc -g rg-lattes-graphrag --query id -o tsv).Trim()
az monitor metrics list --resource $id --metric ProcessedPromptTokens --start-time 2026-09-19T00:00:00Z `
  --end-time 2026-09-19T12:00:00Z --interval PT1H --aggregation Total --filter "ModelDeploymentName eq '*'"
```

Preço usado na conversão (o mesmo que o `litellm` aplica): gpt-4.1-mini US$ 0,40 por
1M tokens de entrada e US$ 1,60 por 1M de saída; embedding US$ 0,02 por 1M.

---

## 3. Ambiente

- **GraphRAG 3.1.0** (antes 3.0.4). A 3.1.1 e a 3.1.2 exigem `litellm==1.92.0`, que no
  Windows só instala compilando em Rust; a 3.1.0 instala limpo (`litellm` 1.86.2,
  `pip check` sem conflitos). Rollback: `pip install -r runs/v0-tcc1/pip-freeze-graphrag-3.0.4.txt`.
- A 3.0.6+ traz `filter_orphan_relationships` (`graphrag/index/operations/extract_graph/utils.py`):
  descarta relações cuja ponta não é entidade registrada — elimina os "nós-fantasma"
  do TCC1.
- **Correção de embeddings no `settings.yaml`** (commit `6c50d74`): o deployment
  GlobalStandard de embeddings responde `404 DeploymentNotFound` para ~1 em 25
  requisições paralelas, e o `graphrag_llm` não tenta de novo nesse erro. O retry do
  embedding usa a lista padrão de `exceptions_to_skip` **sem** `NotFoundError`.
  Diagnóstico completo em `runs/_evidencias-sessao-2026-09/README.md`.
- O venv do projeto não tem `matplotlib` nem `igraph`; `scripts/figura_ego.py` e o
  Leiden de `scripts/metricas_grafo.py` rodam com o Python do Anaconda.

---

## 4. Método das versões (regras que valem para os próximos passos)

1. **Uma variável por passo.** Cada versão muda uma coisa em relação à anterior.
2. **Congelar antes de reindexar.** `graphrag index` não tem opção de pasta de saída e
   sobrescreve `output/`. Antes de cada passo, **mover** `output/` e `logs/` para
   `runs/<versao>/`, copiar `input/` e `settings.yaml`, e gravar um `MANIFEST.json`
   (modelo, versão, custo, md5 do input). Assim cada passo começa com log zerado.
3. **Não limpar o `cache/`.** A chave do cache (`graphrag_llm/cache/create_cache_key.py`)
   é o hash de todos os argumentos da chamada, **incluindo modelo e texto do prompt**.
   Trocar modelo ou texto já invalida as entradas afetadas; o resto é reaproveitado.
   Um cache compartilhado entre versões economiza (o currículo do TCC1 dentro do V2
   reaproveita a extração) e remove ruído do LLM em entradas idênticas.
4. **Resposta vinda do cache repõe as métricas antigas** — o custo logado de uma
   reexecução é fictício. Custo real ≈ custo logado × (1 − cache_hit_rate), e o valor
   de referência é o medidor da Azure.
5. **Consultas:** `graphrag query ... --no-streaming > resposta.md 2>&1`. Com streaming
   o GraphRAG não registra tokens (por isso as consultas basic/local de fev/2026
   aparecem com 0) e a saída do console corrompe (armadilha 4 do HANDOFF).
6. **Efeito de mudanças no texto de entrada** (como o NFC) se mede por checagem
   dirigida das strings afetadas, não pelo total de entidades: mudar poucos tokens
   desloca as fronteiras dos chunks e gera ruído nos agregados.

---

## 5. Resultados

### 5.1 Contagens

"V0 filtrada" é a V0 com o mesmo filtro de relações órfãs da 3.0.6+, aplicado offline
— é a base justa de comparação.

| | V0 (TCC1) | V0 filtrada | V1-base | V1-NFC |
|---|---|---|---|---|
| modelo / GraphRAG / normalização | 4o-mini / 3.0.4 / NFKC | — | 4.1-mini / 3.1.0 / NFKC | 4.1-mini / 3.1.0 / NFC |
| entidades | 1.368 | 1.368 | 1.501 | 1.501 |
| relações | 1.403 | 1.290 | 1.890 | 1.906 |
| comunidades | 232 | — | 289 | 275 |
| text_units | 105 | 105 | 105 | 105 |
| nós / arestas do grafo | 1.114 / 1.401 | 1.015 / — | 1.389 / 1.837 | 1.389 / 1.824 |
| relações órfãs | 113 | 0 | 0 | 0 |
| entidades isoladas | 321 | 353 | 112 | 112 |

Tipos de entidade:

| | PERSON | EVENT | ORGANIZATION | GEO | fora de `entity_types` |
|---|---|---|---|---|---|
| V0 | 580 | 526 | 204 | 52 | SOFTWARE 6 |
| V1-base | 640 | 482 | 325 | 52 | PROJECT 1, ORG 1 |
| V1-NFC | 668 | 490 | 286 | 56 | PROJECT 1 |

Leitura: o gpt-4.1-mini gera um grafo bem mais denso (+47% de relações frente à V0
filtrada; isoladas caem de 353 para 112). Custa mais porque escreve mais: 599 mil
tokens de saída no passo 1 contra 377 mil do gpt-4o-mini em fevereiro.

### 5.2 Defeitos da auditoria do TCC1, por causa

| defeito | causa | V0 | V1-base | V1-NFC |
|---|---|---|---|---|
| nome de tipo virou entidade (`EVENT`) | modelo | 1 | 0 | 0 |
| verbo virou entidade (`HOLDS`) | modelo | 1 | 0 | 0 |
| vazamento de delimitador `<\|...\|>` | modelo | 2 | 0 | 0 |
| `FIUSCRUZ` (inventado; a fonte só tem Fiocruz) | modelo | 1 | 0 | 0 |
| `EDUARDO MANOEL` (grafia da fonte) | fonte | 2 | 2 | 2 |
| `70A REUNIÃO` (ordinal destruído) | NFKC | 1 | 1 | **0** |
| variantes de "Hugo Saba" | falta resolução de entidades | 7 | 10 | 8 |

Defeitos do modelo sumiram; os da fonte e do pré-processamento só saem com a correção
da camada certa. A fragmentação de nomes **piorou** com o modelo mais detalhista —
reforça a etapa de resolução de entidades.

### 5.3 Efeito do NFC (checagem dirigida)

| | V0 | V1-base | V1-NFC |
|---|---|---|---|
| nomes de entidade com ordinal (º/ª) | 0 | 0 | **7** |
| ordinais nas descrições | 0 | 0 | **13** |
| `70A` corrompido | 1 | 1 | **0** |

Exemplos recuperados: `70ª REUNIÃO ANUAL DA SBPC`, `3º ONTOBRAS`, `2º SEMINÁRIO
INTERNACIONAL DE INOVAÇÃO EM EDUCAÇÃO SUPERIOR`, `EDITAL Nº 0001/2023`. O NFC altera
zero caracteres do XML-fonte. Sobra para a resolução de entidades: `70ª REUNIÃO...`
aparece em duas formas (curta e com o nome da SBPC por extenso) e `SUCESU´2005` —
erro de digitação da própria fonte — ainda gera 3 variantes.

### 5.4 O tipo `EVENT` é um balde (base para o passo 2b)

Das 490 entidades `EVENT` do V1-NFC, classificadas por palavra-chave:

| conteúdo real | qtd |
|---|---|
| eventos de fato (congresso, simpósio, seminário...) | 81 |
| sistemas e software | 65 |
| cursos, formação, disciplinas | 35 |
| projetos | 19 |
| banca, prêmio, edital | 9 |
| títulos de publicação e áreas de conhecimento (`BANCO DE DADOS`, `DATA WAREHOUSE`...) | 281 |

Só ~17% são eventos. Com quatro tipos genéricos, o modelo empurra para `EVENT` tudo o
que não é pessoa, organização ou lugar.

---

## 6. Custos detalhados

| execução | medidor da Azure | log do GraphRAG |
|---|---|---|
| passo 1 (01h–02h UTC de 19/09, inclui diagnóstico do bug) | 1.965.985 entrada + 638.366 saída → **US$ 1,83** | US$ 1,73 |
| passo 2 (03h UTC de 19/09) | 1.701.431 entrada + 569.282 saída → **US$ 1,60** | US$ 1,54 (cache 9,6%) |
| geração de prompts do 2b (2 execuções, 09h UTC) | 91.054 + 10.402 → **US$ 0,05** | — |
| **total** | **US$ 3,48** | |

As 8 reexecuções de diagnóstico do passo 1 vieram 99,9% do cache e custaram centavos.

---

## 7. Passo 2b — em andamento

**Objetivo:** prompts de extração, resumo e relatório adaptados ao domínio Lattes, em
português, com tipos de entidade fixos.

**Feito:**

- `scripts/ajustar_prompts.py` gera os três prompts chamando os geradores internos do
  GraphRAG. A linha de comando (`graphrag prompt-tune`) não serve: ou o LLM **inventa**
  os tipos (`--discover-entity-types`), ou gera um prompt **sem tipos**. Além disso, a
  saída padrão dela é `prompts/`, que **sobrescreveria** os prompts originais.
- Tipos fixados (seção 5.4 + seções do XML Lattes + objetivo específico 4):
  `person, organization, geo, event, publication, software, project, knowledge_area, course`.
- Amostra: 15 chunks de 400 tokens, sorteio com semente 42; domínio e idioma
  (Portuguese) explícitos. Procedência em `prompts/lattes/procedencia.json`.
- **Bug do GraphRAG 3.1.0 encontrado e contornado:** `generate_entity_relationship_examples`
  reusa um único `CompletionMessagesBuilder`; `build()` devolve a mesma lista, então as
  5 chamadas recebem todos os chunks empilhados e todo exemplo sai pareado com o texto
  errado. O script gera cada exemplo em conversa própria (`gerar_exemplos`). A primeira
  geração, com o bug, ficou guardada como evidência.
- **Frase removida** do prompt de resumo: *"Enrich it as much as you can with relevant
  information from the nearby text"*. Vem do template do prompt-tune
  (`entity_summarization.py:14`), não existe no prompt padrão e pede informação de um
  texto que o modelo não recebe.
- `settings.yaml` **ainda não foi alterado** — os prompts gerados não estão em uso.

**Achado que motivou a opção B:** mesmo com o bug corrigido, os exemplos escritos pelo
LLM ensinam relações especulativas:

1. ligam uma lista de autores ao item seguinte do XML (o chunk começa no meio dos
   autores de uma produção anterior);
2. criam coautoria entre todos os pares de autores com frases que não estão no texto;
3. deduzem autoria a partir de participação em projeto ("provável autora").

**Decisão (19/09/2026): opção B — curadoria dos exemplos.**

**Próximos passos do 2b:**

1. Escrever 2 exemplos curados para `prompts/lattes/extract_graph.txt`: um de
   publicação com autores, outro de projeto com integrantes e produções. As saídas
   afirmam só o que o texto diz (autor ↔ a própria produção; projeto → produção;
   pessoa → projeto como integrante).
2. Acrescentar em "-Steps-" uma instrução como: *"Extraia apenas relações declaradas
   explicitamente no texto; não deduza autoria, participação ou colaboração."*
3. **Decisão em aberto:** trecho **real** do currículo (mais fiel, mas o arquivo passa a
   conter dado pessoal e não pode ir ao Git — hoje `prompts/lattes/` está ignorado) ou
   trecho **sintético** no formato exato do Lattes (pode ser versionado; os exemplos
   padrão do GraphRAG também são fictícios). Recomendação: sintético fiel ao formato.
4. O usuário revisa os exemplos **antes** de indexar.
5. `settings.yaml`: `extract_graph.prompt`, `summarize_descriptions.prompt` e
   `community_reports.graph_prompt` apontando para `prompts/lattes/`; `entity_types`
   com os 9 tipos. Atenção: com idioma português, descrições e relatórios passam a sair
   em português (V1 saía em inglês) — mudança visível, registrar.
6. `output/` e `logs/` já estão vazios (o V1-NFC foi movido para `runs/v1-nfc/`).
   Indexar em segundo plano, medir o custo pela Azure (~US$ 1,8), comparar com
   `compara_versoes.py` (acrescentar a versão nova em `VERS`) e congelar em
   `runs/v1-tuned/`.

**Observação para uma iteração futura:** o problema de fundo é estrutural. O extrator
escreve o título de uma produção antes da lista de autores, e os chunks de 1.200 tokens
às vezes começam no meio dessa lista. Solução real: o `extract_lattes_text.py` emitir
cada produção em uma linha só (título, ano, tipo e autores juntos).

---

## 8. Achados técnicos (para citar como limitação ou lição)

| achado | onde está a evidência |
|---|---|
| Deployment GlobalStandard de embeddings: 404 em ~1/25 requisições paralelas; GraphRAG não faz retry em 404 | `runs/_evidencias-sessao-2026-09/azure-404-embeddings/` |
| Bug do prompt tuning 3.1.0: exemplos pareados com o texto errado | `.../prompt-tune-bug/` |
| Template de resumo do prompt-tune pede "enriquecer" com texto inexistente | `graphrag/prompt_tune/template/entity_summarization.py:14` |
| Log do GraphRAG subconta ~5% o uso real | seção 6 |
| Cache repõe métricas → custo logado de rerun é fictício (explica o "US$ 0,50" do run 2 de fev/2026) | `graphrag_llm/middleware/with_cache.py:86` |
| `--dry-run` imprime traceback de logging na 3.1.0 (só cosmético; exit 0) | corrigido na 3.1.1 ("Fix logging bug") |
| O GraphRAG silencia os logs do `litellm` (`LITELLM_LOG=DEBUG` não tem efeito) | interceptação via `espiao_index.py` |
| PowerShell 5.1: `*>` grava UTF-16; aspas de `python -c` são comidas; usar arquivos `.py` | — |

---

## 9. Plano do site (decidido)

Inspirado no viewer do [Lakehouse Industry Data Models](https://github.com/databricks-industry-solutions/lakehouse-industry-data-models)
(ainda não analisado): seletor de versão, grafo, painel de detalhes.

- Versões: **V0** (grafo do TCC1, custo zero), **V1** (currículo único corrigido),
  **V2** (8 do NPAI), **V3** (recorte do `db.dump`).
- Grafo, detalhes de nó/aresta e relatórios de comunidade saem dos `.parquet` — custo
  zero, nenhum LLM envolvido.
- **Perguntas fixas** (basic/local/global) executadas **uma vez por versão**, salvas em
  arquivo e exibidas estaticamente. O GraphRAG não usa cache em consultas: repetir
  pergunta custa de novo.
- **Chat ao vivo só no notebook, durante a defesa**, limitado a local/basic. Nunca
  `global` ao vivo (V1 ~US$ 0,07 por pergunta; V2 ~US$ 0,45; V3 >US$ 1) e **nunca a
  chave da Azure no front-end** (site estático não guarda segredo).
- Não existe "resposta original" do V1: o `teste.txt` do TCC1 está corrompido e as
  consultas 4 e 5 nunca foram salvas.
- V2 e V3 mostram dados de pessoas reais: site privado ou só local (LGPD).

---

## 10. Validação: o que os artigos acrescentam

- **Edge et al. (2024, v2)** — critérios do GraphRAG: *comprehensiveness*, *diversity*,
  *empowerment* e *directness* (controle). LLM como juiz em comparação par a par, cada
  par repetido 5 vezes; perguntas geradas por personas × tarefas (125 por dataset). A
  v2 acrescenta métricas por *claims*. O `--method basic` do GraphRAG **é** o RAG
  vetorial (condição SS do artigo) → a frente 5 (baseline) sai do mesmo índice. Usar o
  mesmo modelo como gerador e juiz favorece as próprias respostas: a escala Likert
  humana (frente 3) continua como âncora.
- **Manakul et al. (2023) — SelfCheckGPT**: detecção de alucinação por consistência
  entre N amostras, sem fonte externa. Aqui há ground truth (XML e banco), então a
  verificação contra a fonte é mais forte; citar o SelfCheckGPT como o método usado pela
  Microsoft e justificar a escolha.
- **Traag et al. (2019) — Leiden**: garante comunidades conexas (o Louvain gera até 25%
  mal conectadas e 16% desconexas). Base da frente 1.

Referências conferidas na fonte em 18/09/2026 (colar no `referencias.bib` da monografia):

```bibtex
@article{traag2019leiden,
  author  = {Traag, Vincent A. and Waltman, Ludo and van Eck, Nees Jan},
  title   = {From {Louvain} to {Leiden}: guaranteeing well-connected communities},
  journal = {Scientific Reports}, volume = {9}, pages = {5233}, year = {2019},
  doi     = {10.1038/s41598-019-41695-z}, note = {arXiv:1810.08473}
}
@inproceedings{manakul2023selfcheckgpt,
  author    = {Manakul, Potsawee and Liusie, Adian and Gales, Mark J. F.},
  title     = {{SelfCheckGPT}: Zero-Resource Black-Box Hallucination Detection for Generative Large Language Models},
  booktitle = {Proceedings of the 2023 Conference on Empirical Methods in Natural Language Processing (EMNLP)},
  year      = {2023}, note = {arXiv:2303.08896}
}
@misc{edge2024graphrag,
  author = {Edge, Darren and Trinh, Ha and Cheng, Newman and Bradley, Joshua and Chao, Alex and Mody, Apurva and Truitt, Steven and Metropolitansky, Dasha and Ness, Robert Osazuwa and Larson, Jonathan},
  title  = {From Local to Global: A {Graph RAG} Approach to Query-Focused Summarization},
  year   = {2024}, eprint = {2404.16130}, archivePrefix = {arXiv}, note = {Versão 2, 19 fev. 2025}
}
@misc{larson2024graphragblog,
  author = {Larson, Jonathan and Truitt, Steven},
  title  = {{GraphRAG}: Unlocking {LLM} discovery on narrative private data},
  howpublished = {Microsoft Research Blog}, year = {2024}, note = {Publicado em 13 fev. 2024},
  url    = {https://www.microsoft.com/en-us/research/blog/graphrag-unlocking-llm-discovery-on-narrative-private-data/}
}
```

---

## 11. O `db.dump` (fonte do V3)

Banco **SIMCC** (PostgreSQL 17.10), 198 tabelas em 5 schemas. Dá para ler sem
restaurar nem subir servidor: `pg_restore -a -n <schema> -t <tabela> -f - db.dump`
(PostgreSQL 18 em `C:\Program Files\PostgreSQL\18\bin\`).

| tabela (public) | linhas |
|---|---|
| researcher | 12.065 (11.746 com resumo do Lattes; `abstract_ai` vazio) |
| bibliographic_production | 627.323 (mediana 31 por pesquisador; p90 134) |
| participation_events | 524.707 |
| research_project | 454.834 |
| guidance | 417.928 |
| education | 10.850 |
| graduate_program_researcher / research_group_researcher | **0 / 0** |

- **7 dos 8 currículos do NPAI estão no banco** (por `lattes_id`); falta só o de 5 KB
  (Universidade de Évora). Mesmas pessoas em duas fontes → validação cruzada
  XML × banco (precisão/recall reais) no passo 4.
- As tabelas de vínculo estão vazias: não dá para escolher grupo coeso por programa ou
  grupo de pesquisa. Coautoria (`authors`) e orientação (`oriented`) são texto livre —
  o banco não elimina a resolução de entidades, mas fornece 12.065 nomes canônicos para
  resolver contra.
- O currículo do TCC1 tem 141 produções (acima do p90): o currículo típico é menor.
  Indexar o banco inteiro custaria milhares de dólares; o recorte é de dezenas.

---

## 12. Pendências menores

- Figura d2 (`docs/diagramas/ego/ego_jorge_d2`) ainda com a legenda antiga; a d1 tem a
  legenda em blocos (configurado × artefato de extração).
- `requirements.txt` só lista `graphrag`; faltam `matplotlib` e `igraph`/`leidenalg`
  para os scripts de figura e métricas.
- `scripts/mapear_grafo.py`, `metricas_grafo.py` e `figura_ego.py` usam `output/` por
  padrão, que agora fica vazio entre passos: passar `--output-dir runs/<versao>/output`.
- Conferir a fatura da Azure (página "Educação") quando os dados aparecerem e comparar
  com a seção 6.

## 13. Auditorias anteriores (jul/2026, fora do repositório)

Em `C:\Users\felip\Documents\00 - TCC\`:

- `auditoria-consultas-graphrag.md` — histórico real das consultas de fev/2026,
  rastreabilidade das citações (38/38), diluição do sujeito nos community reports.
- `figura-d1-e-artefatos-de-extracao.md` — números da nota de limitação (tipos fora de
  `entity_types`, nós-fantasma, quase-duplicatas).
