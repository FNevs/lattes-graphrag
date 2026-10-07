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
| 2b | prompts adaptados ao domínio Lattes (V1-tuned) | ✅ | `runs/v1-tuned/` | US$ 1,88 |
| 2c | extrator: um registro por linha (V1-formatoE, diagnóstico) | ✅ | `runs/v1-formatoE/` | US$ 1,71 (com piloto) |
| 3 | 8 XMLs do NPAI (V2) | ✅ | `runs/v2-npai/` | US$ 17,76 |
| 4 | validação cruzada com o banco SIMCC | **BLOQUEADO** (20/09) | — | — |
| 5 | 20–30 currículos do `db.dump` (V3) | **BLOQUEADO** (20/09) | — | — |
| — | página de visualização (`site/`) | ✅ (refinos contínuos) | `site/` + `docs/SITE-VISUALIZADOR.md` | US$ 0,00 |
| — | consultas fixas para o site | ✅ (V2, via validação, 07/10) | `site/dados/v2-npai.consultas.json` | incluído na camada 2 |
| — | consultas avulsas de demonstração (19/09) | ✅ | `runs/*/consultas/` | US$ 0,02 |

**Decisão de 20/09/2026:** tudo que envolve o `db.dump` fica **BLOQUEADO** — não é
próximo passo nem trabalho futuro; o usuário decidirá depois o que fazer com ele, ou
descartá-lo. O trabalho segue com os **8 currículos do `lattesNAPI/`**, até a página de
visualização.

**Gasto acumulado: US$ 27,24 de US$ 100** (US$ 24,79 até 23/09 + US$ 2,45 da camada 2 da validação, 07/10). Falta o custo das consultas fixas do site
(~US$ 9 estimados), o que fecharia em ~US$ 34.

**Estado em 23/09/2026:** V2 indexado (`runs/v2-npai/`) e página de visualização pronta e
refinada — três visões (geral, radial por tipo, livre), nós arrastáveis, cores validadas,
textos completos, colunas redimensionáveis. Detalhes, armadilhas e pendências em
`docs/SITE-VISUALIZADOR.md`.

**Próxima ação (07/10/2026):** validação automática contra o XML, conforme
`docs/PLANO-VALIDACAO-TCC2.md` (camada 1 a custo zero; camada 2, consultas, ~US$ 4 estimados,
confirmar antes). Antes: (1) consultas fixas sobre o V2 (~US$ 9, confirmar antes);
(2) resolução de entidades — a pendência técnica mais relevante (seção 16). Tour guiado,
animação de entrada e painel no estilo Databricks feitos em 23/09/2026.

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
| Chat | `gpt-4.1-mini` v2025-04-14, GlobalStandard, 1.000 unidades = 1M TPM e 1.000 RPM desde 21/09/2026 (antes 200K TPM; cota da assinatura: 5.000); aposenta em 14/04/2027 |
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
| passo 2b, indexação V1-tuned (10:58–11:11 UTC) | 1.967.575 entrada + 644.412 saída + 420.822 embedding → **US$ 1,83** | US$ 1,81 (cache de chat 0%) |
| consultas de demonstração (11h UTC de 19/09; 4 buscas local/basic) | 40.013 entrada + 2.546 saída → **US$ 0,02** | 0 (o log não registra tokens em consulta) |
| piloto de extração do 2c (2 execuções, 00h UTC de 21/09) | 49.814 entrada + 34.616 saída → **US$ 0,08** | — |
| passo 2c, V1-formatoE diagnóstico (00:09–00:23 UTC de 21/09) | 1.704.061 entrada + 590.320 saída → **US$ 1,63** | — |
| passo 3 tentativa 1, abortada por RateLimit (01h–02h UTC de 21/09) | 8.905.419 entrada + 3.448.018 saída → **US$ 9,08** | — |
| passo 3 etapa 1, grafo do V2 (18:50–19:12 UTC) | 2.689.061 entrada + 706.274 saída → **US$ 2,21** | — |
| passo 3 etapa 2, relatórios + embeddings (19:13–19:43 UTC) | 6.512.505 entrada + 2.365.769 saída + 4.073.273 embedding → **US$ 6,47** | — |
| validação, camada 2: piloto de consultas (19:19–19:21 UTC de 07/10) | 473.619 entrada + 30.026 saída → **US$ 0,24** | — |
| validação, camada 2: lote de 17 perguntas (19:22–19:30 UTC de 07/10) | 3.714.968 entrada + 217.692 saída → **US$ 1,85** | — |
| validação, camada 2: juiz `gpt-4.1` (19:38–19:41 UTC de 07/10) | 156.038 entrada + 5.613 saída → **US$ 0,36** | — |
| **total** | **US$ 27,24** | |

As 8 reexecuções de diagnóstico do passo 1 vieram 99,9% do cache e custaram centavos.

---

## 7. Passo 2b — concluído (V1-tuned)

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

**Curadoria feita e aprovada pelo usuário (19/09/2026), custo US$ 0,00** (tudo local):

1. ✅ **Trecho sintético**, não real. Rótulos, ordem dos campos e valores categóricos
   copiados do currículo; só nomes e títulos inventados. Motivos: (a) vazamento de
   exemplo para a saída fica **detectável** — com trecho real do corpus, uma entidade
   copiada do exemplo é indistinguível de uma extraída; (b) sem dado pessoal, o prompt
   pode ir para um apêndice. Os 7 nomes, 7 citações, o periódico e os títulos foram
   buscados no currículo, nos 8 XMLs do NPAI e no `db.dump` inteiro (3,6 mi linhas via
   `pg_restore`): **zero ocorrências** (a citação `MAGALHÃES, C. F.` existia e foi trocada).
   Nomes para a checagem de vazamento pós-indexação: `RODRIGO TAVARES QUINTELA`,
   `HELENA BRAGA DE ALCÂNTARA`, `MARCELO DANTAS ARAGÃO`, `SIMONE PRATES CALDEIRA`,
   `BEATRIZ SAMPAIO LEMOS`, `CAIO FERRAZ VALADARES`, `DENISE ARAÚJO PORTUGAL`,
   `REVISTA NORDESTINA DE ENGENHARIA DE DADOS`.
2. ✅ Exemplo 1 (publicação): começa no fim da lista de autores de uma produção fora do
   trecho (pessoas extraídas **sem** relação), artigo completo com autores (autor →
   artigo; artigo → periódico; **sem** arestas de coautoria) e termina num cabeçalho sem
   título (nada extraído). Exemplo 2 (projeto): integrantes → projeto (responsável com
   força 9), projeto → produções (artigo e TCC); **nenhuma** pessoa → produção.
3. ✅ Instrução acrescentada no passo 2 de "-Steps-" (em inglês, como o resto do prompt):
   só relações explícitas; autores pertencem à produção **acima** da lista; autores no
   início do trecho ficam sem relação; coautoria só via a produção; integrantes ligam-se
   ao projeto, não às produções do projeto.
4. Convenções: descrições neutras ("Pessoa listada como autora" — o texto não informa
   gênero); periódico como `ORGANIZATION` (convenção do V1: 34/34 periódicos); forças 9
   (autoria, periódico, responsável) e 8 (integrante, produção do projeto); nenhum
   exemplo para `knowledge_area`, `course`, `event`, `geo`.
5. Tamanho: 2.671 tokens (o200k_base), contra 3.606 do prompt gerado pelo LLM e 1.726 do
   padrão. Versão gerada guardada em `runs/_evidencias-sessao-2026-09/passo2b-curadoria/`.
6. ✅ `settings.yaml`: os três prompts apontam para `prompts/lattes/`; `entity_types`
   com os 9 tipos. Validado offline com `load_config` + `format` como o extrator faz.
   Atenção: descrições e relatórios passam a sair em português (V1 saía em inglês).
7. ✅ **Limites de tamanho reinseridos.** Os templates do prompt-tune da 3.1.0 não têm
   `{max_length}` (resumo) nem `{max_report_length}` (relatório); sem eles os
   `max_length: 500` e `2000` do `settings.yaml` ficariam sem efeito — descrições e
   relatórios sem limite, mais caros e uma segunda variável no passo.
   `restaurar_limites` em `scripts/ajustar_prompts.py` os devolve nas mesmas posições
   dos prompts padrão; aplicado aos arquivos atuais sem regerar (versões sem limite
   guardadas como evidência).

**Resultado (V1-tuned, 19/09/2026, US$ 1,83 pelo medidor).** Congelado em
`runs/v1-tuned/` (output, logs, input, settings, cópia de `prompts-lattes/`, MANIFEST).
Comparação completa: `runs/_evidencias-sessao-2026-09/passo2b-curadoria/comparacao_v1nfc_v1tuned.txt`
(`compara_2b.py`) e `inspecao_v1tuned.txt` (`inspeciona_2b.py`).

| | V1-NFC | V1-tuned |
|---|---|---|
| entidades / relações | 1.501 / 1.906 | 1.583 / 1.389 |
| comunidades | 275 | 226 |
| nós / arestas do grafo | 1.389 / 1.824 | 1.300 / 1.357 |
| entidades isoladas | 112 | 283 |
| arestas PERSON–PERSON (coautoria inferida) | 187 | **0** |
| relações com linguagem especulativa | 26 (1,4%) | 7 (0,5%) |
| vazamento dos nomes sintéticos | — | **0** |
| descrições em português | ~0% (inglês) | ~100% |
| palavras por descrição (mediana) / relatório (mediana) | 22 / 572 | 25 / 630 |
| grau do dono do currículo | 45 (23 EVENT, 18 ORG, 4 PERSON) | 42 (13 SOFTWARE, 8 PUBLICATION, 8 ORG, 5 PROJECT…) |

Tipos no V1-tuned: PERSON 622, PUBLICATION 310, ORGANIZATION 176, COURSE 130, EVENT 113,
SOFTWARE 86, PROJECT 66, KNOWLEDGE_AREA 48, GEO 24 — o balde `EVENT` (490, só ~17%
eventos) se desfez. Relações dominantes: PERSON–PUBLICATION 555, PERSON–SOFTWARE 142,
PERSON–PROJECT 111.

Leitura: a curadoria fez o que se propunha — coautoria inventada zerou e a linguagem
especulativa caiu a um terço (3 das 7 restantes são a mesma frase sobre a FAPESB). O
grafo ficou **menos denso e mais fiel**: menos relações, mais isoladas. Das 283 isoladas,
87 são PERSON — 62 delas descritas como autoras, isto é, autores cuja produção não
estava no trecho (sem relação, como a instrução pede) — e 67 são `COURSE` (disciplinas
de ensino que o texto não liga a nada).

Defeitos novos ou que persistem (entrada para iterações futuras):
- 8 entidades com tipo fora da lista: `TRABALHO TECNICO` 4, `PROCESSO OU TÉCNICA` 2,
  `PATENT` 1, `ORG` 1 — o modelo usa a seção do Lattes como tipo.
- Cargos virando `PERSON`: `PROFESSOR`, `COORDENADOR DE PROJETOS DE P&D`,
  `PESQUISADOR DA AGÊNCIA UNEB DE INOVAÇÃO` (enquadramento funcional).
- Variantes: `EDUARDO MANOEL` 2→3, `SABA` 8→10, e títulos quase iguais (`...COM FUNÇÃO
  DÉBITO...` / `...COM FUNÇÃO DE DÉBITO...`) — resolução de entidades segue pendente.

**Achado (19/09/2026): o extrator descarta 62% do XML.** `extract_lattes_text.py:146`
faz `dict.fromkeys(linhas)`, que remove linhas repetidas **no arquivo inteiro**, não só
as vizinhas. No currículo do V1 (medido com `medir_dedup_extrator.py`):

| | no XML | no texto |
|---|---|---|
| linhas | 13.256 | 4.972 |
| `AUTORES \| nome completo` | 1.083 | 400 |
| `INTEGRANTES DO PROJETO \| nome completo` | 148 | 79 |
| `ano do artigo` | 52 | 14 |
| autoria do dono do currículo | 258 | **1** |

Cada coautor aparece só na primeira produção em que figura; anos, naturezas e idiomas
repetidos somem das produções seguintes.

**Formatos simulados (sem LLM, `simula_formatos.py`; tokens o200k_base, chunks de
1.200 com overlap 100).** A estimativa anterior ("corrigir custa ~2,7×") valia só para
remover a deduplicação mantendo uma linha por atributo — 67% dos tokens desse formato são
rótulos repetidos (`DADOS BASICOS DO ARTIGO | titulo do artigo:`).

| formato | currículo V1 (chunks) | 8 do NPAI (chunks) | perde dados? |
|---|---|---|---|
| A — atual (dedup global) | 105 | 708 | sim, 62% das linhas |
| B — sem dedup, 1 linha por atributo | 248 | 1.766 | não |
| C — sem dedup, 1 linha por elemento XML | 165 | 1.185 | não |
| D — C sem códigos, flags, sequências e ids | 129 | 943 | não* |
| **E — uma produção/projeto por linha** (campos + autores/integrantes juntos) | **98** | **744** | não* |

\* descarta só códigos, flags, sequências, ids, DOI/ISSN/ISBN e home page (não viram entidade).

O formato E traz **todos** os autores e anos pelo mesmo custo do formato atual e resolve
também o problema estrutural (o chunk começar no meio de uma lista de autores separada do
título). Linha de artigo: mediana de 156 tokens.

**Onde vai o custo de uma indexação (V1-tuned, `custo_por_etapa.py` sobre o cache):**
extração 50% (US$ 0,91; 210 chamadas = 105 + 105 de *gleaning*), relatórios de
comunidade 38% (US$ 0,69), resumo de descrições 11% (US$ 0,20), embeddings <1%.
O *gleaning* custa US$ 0,39 por indexação (22%) e é o único a trazer 243 das 1.583
entidades finais: 61 PERSON, 42 COURSE, 30 ORGANIZATION… e 31 códigos numéricos
(`000200000993`, `CURSO 90000015`), lixo que o formato E elimina na origem
(`efeito_gleaning.py`). Mantido por ora: desligá-lo perderia ~60 pessoas por currículo.

**Cache de prompt da Azure:** 44% da entrada de chat do V1-tuned (854.400 tokens) veio
com `cached_tokens` (extração 49%, relatórios 50%, resumo 0% — prompt curto demais, o
mínimo é 1.024 tokens). O medidor `ProcessedPromptTokens` conta tudo a preço cheio; se a
Azure cobrar o cache como a OpenAI (1/4 do preço de entrada no gpt-4.1-mini), o custo
faturado do V1-tuned é ~US$ 1,57, não 1,83. **Os custos deste registro são tetos**;
confirmar no Cost Management quando ele sair do atraso de 24–48 h.

---

## 8. Achados técnicos (para citar como limitação ou lição)

| achado | onde está a evidência |
|---|---|
| Deployment GlobalStandard de embeddings: 404 em ~1/25 requisições paralelas; GraphRAG não faz retry em 404 | `runs/_evidencias-sessao-2026-09/azure-404-embeddings/` |
| Bug do prompt tuning 3.1.0: exemplos pareados com o texto errado | `.../prompt-tune-bug/` |
| Template de resumo do prompt-tune pede "enriquecer" com texto inexistente | `graphrag/prompt_tune/template/entity_summarization.py:14` |
| Templates do prompt-tune omitem `{max_length}`/`{max_report_length}` → limites do settings sem efeito | `.../passo2b-curadoria/*.sem-limite.txt` |
| Extrator remove linhas repetidas no arquivo inteiro: 62% do XML descartado; dono do currículo autor 258× no XML, 1× no texto | `.../passo2b-curadoria/medir_dedup_extrator.py` |
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

---

## 14. Arquitetura de dados e visualização do grafo (pesquisa de 20/09/2026)

Pesquisa na documentação oficial do GraphRAG e nas soluções da Microsoft, para decidir
se vale um banco (camadas bronze/silver/gold) antes da indexação e como ver o grafo.

### O que a Microsoft faz

- **Entrada:** o GraphRAG aceita `.txt`, `.csv`, `.json`, `.jsonl`, `.parquet` e
  MarkItDown; tudo vira um DataFrame de documentos (`id`, `text`, `title`,
  `creation_date`, `raw_data`). **Não há banco antes da indexação**, e a documentação
  ainda oferece passar um DataFrame direto pela API, pulando o carregamento de arquivos
  ([Inputs](https://microsoft.github.io/graphrag/index/inputs/)).
- **Saída:** tabelas **Parquet** (`entities`, `relationships`, `communities`,
  `community_reports`, `text_units`, `documents`) mais os embeddings no vector store
  configurado. O armazenamento pode ser `file`, `memory`, `blob` ou `cosmosdb`
  ([Configuração](https://microsoft.github.io/graphrag/config/yaml/)).
- **Nas soluções em nuvem** (GraphRAG Accelerator, CosmosAIGraph) a Microsoft usa Azure
  Storage para os arquivos, Cosmos DB (Gremlin) para entidades e relações e AI Search
  para os vetores. É a mesma separação em camadas, com serviços pagos — não é requisito
  do framework ([graphrag-accelerator](https://github.com/Azure-Samples/graphrag-accelerator),
  [CosmosAIGraph](https://learn.microsoft.com/en-us/azure/cosmos-db/gen-ai/cosmos-ai-graph)).
- **Visualização:** o guia oficial usa o `graph.graphml` (habilitado por
  `snapshots.graphml: true`, que já está ligado) aberto no **Gephi**, com plugin do
  Leiden, cor por cluster, tamanho por grau e layouts OpenORD + ForceAtlas2
  ([Visualization Guide](https://microsoft.github.io/graphrag/visualization_guide/)).
- **Banco de grafos:** o próprio repositório do GraphRAG traz um notebook da comunidade
  que importa os Parquet para o **Neo4j** via Cypher
  ([notebook](https://github.com/microsoft/graphrag/blob/main/examples_notebooks/community_contrib/neo4j/graphrag_import_neo4j_cypher.ipynb),
  [artigo do Neo4j](https://neo4j.com/blog/developer/microsoft-graphrag-neo4j/)).

### Decisão para este TCC (menor custo)

As camadas já existem como arquivos; um Postgres para 8 currículos acrescentaria
infraestrutura sem responder nenhuma pergunta nova:

| camada | o que é | onde está |
|---|---|---|
| bronze (bruto) | XML do Lattes | `lattesNAPI/lattes/*.xml` |
| silver (tratado) | um registro por linha, sem dado sensível | `input/*.txt` + `MANIFEST.json` |
| gold (grafo) | entidades, relações, comunidades, relatórios | `runs/<versao>/output/*.parquet` |
| índice vetorial | só `id` + vetor de 1536 dimensões | `runs/<versao>/output/lancedb/` |

O **LanceDB não guarda o grafo nem texto**: conferido no V1-tuned, as três tabelas
(`entity_description`, `community_full_content`, `text_unit_text`) têm apenas `id`,
`vector` e datas (12 MB). Ele serve à busca por similaridade; o conteúdo legível está
nos Parquet.

Para *ver* o grafo, em ordem de custo:

1. **Gephi + `graph.graphml`** — caminho oficial, gratuito, gera as figuras da monografia.
2. **DuckDB sobre os Parquet** — SQL na camada gold sem servidor nem carga
   (`SELECT * FROM 'runs/v1-tuned/output/entities.parquet'`).
3. **Neo4j Community local (Docker)** — banco de grafos de verdade, Cypher e navegador
   para explorar; importação pelo notebook oficial. Gratuito, só custo de máquina.
4. **Cosmos DB Gremlin** — o que a Microsoft usa na nuvem; **descartado** por custo.

### Achado aproveitável: `chunking.prepend_metadata`

O GraphRAG pode repetir metadados do documento no topo de **cada chunk**
(`chunking.prepend_metadata`, presente na 3.1.0). Com o `title` do documento levando o
nome do titular, todo chunk passa a dizer de quem é o currículo — hoje um chunk no meio
do arquivo não sabe. Custo estimado: ~10 tokens por chunk (~US$ 0,01 por indexação dos 8).

### Ferramenta de consulta ao grafo (20/09/2026, custo zero)

`duckdb` 1.5.5 instalado no venv. Dois artefatos versionados:

- `scripts/consultas_grafo.sql` — 13 consultas sobre os `.parquet` de uma versão, com
  views (`entidades`, `relacoes`, `comunidades`, `relatorios`, `trechos`). Para trocar de
  versão, muda-se a pasta nas cinco linhas de `CREATE VIEW`. Serve também no **DBeaver
  Community**: conexão DuckDB, banco `:memory:` (o driver Parquet nativo do DBeaver é
  pago; o DuckDB contorna de graça).
- `scripts/explorar_grafo.py [pasta] [--consulta N] [--ui]` — roda as consultas no
  terminal; `--ui` abre a interface web local do DuckDB (extensão `ui`, disponível).

Destaque: a consulta 6 monta a **rede de coautoria por caminho de dois passos** (pessoas
que dividem a mesma produção). Como o prompt curado não cria aresta pessoa–pessoa, é
assim que a colaboração é medida — e ela aparece: no V1-tuned, Márcio Luís Valença Araújo
e Thiago Barros Murari dividem 13 produções; o titular divide 9 com Márcio.

---

## 15. Passo 2c — extrator com um registro por linha (V1-formatoE)

Mesmo currículo e mesmos tipos do V1-tuned; muda o **formato do texto de entrada** e,
com ele, os exemplos do prompt de extração. Congelado em `runs/v1-formatoE/`.
Execução **diagnóstica**: `settings.workflows` reduzido, sem `create_community_reports`
(38% do custo numa execução completa) e sem `generate_text_embeddings` — logo **esta
versão não responde busca local/basic**, só serve para medir a extração.

**Piloto antes de pagar a indexação** (`piloto_extracao.py`, 5 chunks, US$ 0,08 com a
repetição por um erro meu de código): 130 entidades e 128 relações, **zero** tipos fora da
lista, **zero** relações especulativas, **zero** vazamento dos exemplos e 2 relações
pessoa–pessoa, ambas orientações reais. Foi o que autorizou seguir.

| | V1-tuned | V1-formatoE |
|---|---|---|
| formato do texto | uma linha por campo, linhas repetidas removidas no arquivo todo | um registro por linha, sem deduplicação global |
| chunks | 105 | 91 |
| entidades | 1.583 | 1.422 |
| relações | 1.389 | **2.719** |
| comunidades | 226 | 349 |
| entidades isoladas | 283 | **91** |
| tipos fora da lista | 8 | **0** |
| relações especulativas | 4 | 1 |
| arestas pessoa–produção | 680 | **1.358** |
| **produções do titular** | **19** | **299** |
| grau do titular | 42 | 597 |
| pares de coautores (2 passos) | 954 | 2.137 |
| arestas pessoa–pessoa diretas | 0 | 63 |
| vazamento dos exemplos sintéticos | 0 | 0 |

Leitura: a correção do extrator era o gargalo real. Com o mesmo modelo, o mesmo currículo
e menos chunks, o grafo ganhou **96% mais relações** e o titular passou de 19 para **299**
produções próprias — porque o texto antigo apagava a linha de autoria dele em todas as
produções a partir da segunda. As isoladas caíram de 283 para 91, e os tipos inventados
(`TRABALHO TECNICO`, `PATENT`, `ORG`…) desapareceram, porque os códigos e rótulos que os
geravam saíram do texto.

A rede de coautoria mudou de figura: antes o titular dividia 9 produções com o
colaborador mais frequente; agora divide **43 com Hugo Saba Pereira Cardoso**, 34 com
Peterson Albuquerque Lobato e 24 com Márcio Luís Valença Araújo. A fragmentação de nomes
segue pendente e agora é visível no próprio resultado: `HUGO SABA PEREIRA CARDOSO` (43) e
`HUGO SABA` (42) são a mesma pessoa.

Defeito residual: das 63 arestas pessoa–pessoa, **56 são orientações** (a exceção
autorizada na instrução) e **7 são "participaram da mesma banca"** — que a instrução
proíbe, por ser relação entre pessoas da mesma lista. São 7 em 2.719 (0,3%); anotado
para a próxima iteração do prompt.

**Custo (medidor da Azure, hora 00 UTC de 21/09, descontados os pilotos):**
1.704.061 tokens de entrada + 590.320 de saída = **US$ 1,63**. Ficou acima da estimativa
de US$ 0,95 porque o texto novo é mais denso: a saída por chunk quase dobrou (mais
entidades e relações por chunk), e a saída custa 4× a entrada.

---

## 16. Passo 3 — V2: os 8 currículos do `lattesNAPI/`

Formato E (um registro por linha), prompts do V1-formatoE, 9 tipos e, pela primeira vez,
`chunking.prepend_metadata: [title]`: os arquivos de `input/` se chamam
`<titular> - <id lattes>.txt` (opção `--nomear-por-titular` do extrator), e o GraphRAG
repete esse `title` no topo de cada chunk — com 8 currículos no mesmo índice, um chunk do
meio de um arquivo passa a dizer de quem é o currículo. 681.933 tokens, 622 chunks.

Estimativa antes de rodar (taxa medida no 2c): **US$ 18,40 no teto**, ~US$ 16,50 com o
desconto de cache de prompt. Metade disso é extração; o resto, relatórios de comunidade.

### Tentativa 1 (21/09, 01:48–02:36 UTC) — falhou

A extração abortou com `litellm.RateLimitError` (**337 erros 429**) depois de 48 min.
Causa: o modelo de chat estava **sem `rate_limit`** no `settings.yaml`, e o GraphRAG
dispara requisições em paralelo sem freio; com 91–105 chunks cabia nos 200 mil
tokens/min do deployment, com 622 não. O GraphRAG imprimiu `Pipeline complete` e saiu
com **código 0 mesmo tendo falhado** — só `documents` e `text_units` foram gravados.

- Custo (medidor, horas 01 e 02 UTC): 8.905.419 entrada + 3.448.018 saída = **US$ 9,08**.
- **Não foi perdido:** 1.210 das 1.244 chamadas de extração ficaram no `cache/`
  (2.500 de 2.534 tentativas deram certo) e são reaproveitadas de graça.
- Saída parcial guardada em `runs/_evidencias-sessao-2026-09/passo3-v2/tentativa1-falhou/`.

Correções (sem custo):

1. `rate_limit` (janela deslizante) e `max_retries: 10` no modelo de chat.
2. Deployment `gpt-4.1-mini` de **200 para 1.000 unidades** (1 M tokens e 1.000
   requisições por minuto) — a assinatura tinha 5.000 disponíveis e, no GlobalStandard,
   capacidade não custa: paga-se por token. O `rate_limit` usa 80% disso.
3. Retomada em duas etapas, para não arriscar os relatórios num pipeline que ainda não
   tinha ido até o fim: (1) só o grafo, (2) relatórios e embeddings.

Armadilha anotada: **não usar `$` em comentários do `settings.yaml`** — o GraphRAG passa
o arquivo por `string.Template.substitute`, e "US$ 9" virou placeholder inválido.

### Tentativa 2 (21/09, em duas etapas) — concluída

| etapa | o quê | duração | custo (medidor) |
|---|---|---|---|
| 1 | grafo: extração, resumo de descrições, comunidades | 18:50–19:12 UTC (22 min) | US$ 2,21 |
| 2 | relatórios de comunidade + embeddings | 19:13–19:43 UTC (30 min) | US$ 6,47 |
| — | tentativa 1 (abortada, encheu o cache) | 48 min | US$ 9,08 |
| | **V2 total** | | **US$ 17,76** |

Zero `RateLimitError` nas duas etapas. A etapa 1 custou US$ 2,21 em vez dos ~US$ 11 de
uma extração do zero, porque 1.210 das 1.244 chamadas vieram do cache da tentativa 1 —
o dinheiro da falha não se perdeu. A estimativa prévia (US$ 18,40 no teto) ficou 3,6%
acima do real.

Congelado em `runs/v2-npai/` (93 MB de output).

| | V1-formatoE (1 currículo) | **V2 (8 currículos)** |
|---|---|---|
| chunks | 91 | 622 |
| entidades | 1.422 | 8.664 |
| relações | 2.719 | 18.746 |
| comunidades / relatórios | 349 | 1.961 / 1.961 |
| entidades isoladas | 91 | 644 (7,4%) |
| relações especulativas | 1 | 28 (0,1%) |
| tipos fora da lista | 0 | 4 |

Pares de tipos mais frequentes: PERSON–PUBLICATION 7.146, EVENT–PERSON 1.413,
PERSON–PROJECT 1.137, ORGANIZATION–PUBLICATION 911, PERSON–SOFTWARE 886,
KNOWLEDGE_AREA–PUBLICATION 779, PERSON–PERSON 623 (orientações e bancas).

**A rede de colaboração entre os 8 apareceu** (coautoria por caminho de dois passos,
produções em comum) — 19 dos 28 pares possíveis se conectam:

| par | produções em comum |
|---|---|
| Eduardo Manuel de Freitas Jorge / Hugo Saba Pereira Cardoso | 161 |
| Aloisio Santos Nascimento Filho / Hugo Saba Pereira Cardoso | 102 |
| Aloisio Santos Nascimento Filho / Eduardo Manuel de Freitas Jorge | 45 |
| Hugo Saba Pereira Cardoso / José Garcia Vivas Miranda | 45 |
| José Garcia Vivas Miranda / Raphael Silva do Rosário | 42 |
| Eduardo Manuel de Freitas Jorge / José Garcia Vivas Miranda | 17 |

Grau dos titulares: Maria Fernanda Rios Grassi 1.120, Hugo Saba 825, Eduardo Jorge 810,
José Garcia Vivas Miranda 692, Aloisio Santos Nascimento Filho 437, Mayara Almeida 258,
Raphael do Rosário 156, Paulo Jorge Silveira Ferreira 14 (currículo com 14 linhas).

**Fragmentação de nomes, agora quantificada nos 8 titulares** (variantes da mesma
pessoa como entidades distintas): Eduardo 15, Aloisio 11, José Garcia 10, Hugo Saba 10,
Maria Fernanda 8, Raphael 7, Paulo Jorge 6, Mayara 2. É a principal ameaça à validade
das métricas de rede e o argumento mais forte para uma etapa de resolução de entidades.

**Vazamento dos exemplos sintéticos: 1 em 8.664** — `MARCELO DANTAS ARAGÃO` entrou como
entidade **isolada** (grau 0, frequência 1, sem nenhuma relação). Os demais alertas da
busca eram homônimos reais de sobrenome (Alcântara, Aragão, Caldeira, Quintela,
Valadares existem entre os coautores). Ou seja: a escolha de nomes sintéticos cumpriu o
papel — o vazamento é detectável e mensurável, e não teria como sê-lo com trecho real.

---

## 17. Página de visualização (`site/`)

Custo zero: lê os JSON gerados por `scripts/exportar_site.py` a partir dos Parquet
(camada gold → camada de serviço). Bibliotecas do grafo em `site/vendor/` (funciona
offline). `site/dados/` fora do Git (dado pessoal). Servir com
`python -m http.server 8777 --directory site`.

**Três visões, inspiradas no viewer do Databricks** (a visão do todo, lá e aqui, é difícil
de ler; o que funciona são as visões focadas):

- **Visão geral:** os 8 pesquisadores; cada linha conta as produções ligadas aos dois
  (Eduardo × Hugo 161). Ordem no círculo gulosa, para os pares fortes ficarem vizinhos;
  só as arestas com ≥ 10 produções levam número. Clique na linha lista as produções.
- **Radial:** a entidade no centro e os vizinhos em **caixas por tipo** (Pessoas,
  Publicações, Projetos…), os mais ligados primeiro ("10 de 350"). Desenhada em pixels
  (`autoRescale: false`): linhas de 27 px e caixas de 270 px em qualquer tela; o que não
  cabe fica a um arrasto. Clicar num vizinho o centraliza; o caminho fica no topo.
- **Exploração livre:** o grafo inteiro com filtros, ForceAtlas2 em *worker*.

**Cores** (paleta categórica validada pela skill de dataviz: CVD ≥ 8,4 e visão normal ≥
19,3 no escuro; ordem fixa, nunca em ciclo): **8 cores = 8 pesquisadores**. Entidade
citada em 2+ currículos ganha cor neutra clara — são as **pontes** do grupo, e na
exploração livre formam o miolo do grafo. Por tipo: os 8 tipos principais com cor própria,
Local e tipos inválidos em "Outros". Por comunidade: as 7 maiores do nível 0 (que
correspondem às linhas de pesquisa de cada titular) e o resto em "Outras". Antes, a paleta
de 10 cores repetia em ciclo e uma entidade compartilhada herdava a cor do primeiro
pesquisador em ordem alfabética.

**Refinos de 23/09/2026** (detalhe em `docs/SITE-VISUALIZADOR.md`): texto completo das
descrições (o exportador cortava 31% das de entidade e 11% das de relação), nós arrastáveis,
radial em escala 1:1 que encolhe por inteiro no zoom, botão Voltar no lugar do caminho,
legenda só com o que está na tela, colunas redimensionáveis, layout em cartões arredondados,
linhas mais escuras no tema claro e ícone do projeto.

**Legibilidade:** rótulos com fundo ("chip") e 13 px, fontes-base maiores, nomes de tipo em
português, glossário ("?") com todos os termos (entidade, relação, grau, menções,
comunidade, nível, relatório, pontes, variantes de nome) e dicas ao passar o mouse.

---

## 18. Validação — camada 1: o grafo contra o XML (07/10/2026, custo zero)

Plano e fundamentação em `docs/PLANO-VALIDACAO-TCC2.md`. Código em `scripts/validacao/`;
saídas em `runs/<versao>/validacao/` e `runs/_validacao/comparacao.md` (ignoradas pelo Git).

```powershell
.venv\Scripts\python.exe scripts\validacao\validar_grafo.py              # todas as versões (~25 s)
.venv\Scripts\python.exe -m unittest discover -s scripts\validacao\testes -v
```

**Critério.** Uma relação é *suportada* quando as duas entidades casam com itens (ou com o
texto) do **mesmo registro** do XML — o registro foi uma linha do texto lido pelo modelo.
*Não suportada*: as duas pontas existem no XML, mas nunca no mesmo registro. *Não
verificável*: alguma ponta não casa com nada do XML. Precisão = suportadas / (suportadas +
não suportadas). Cobertura = ligações núcleo–item do XML (autor–artigo, integrante–projeto,
orientador–orientando...) que o grafo traz.

### Comparação entre versões (limiar de semelhança 90)

| versão | entidades | relações | proveniência (2 pontas no trecho) | precisão | cobertura | F1 | sem fonte |
|---|---|---|---|---|---|---|---|
| V0 (TCC1) | 1.368 | 1.403 | 93,2% | 0,545 | 0,085 | 0,147 | 44 |
| V1-base (NFKC) | 1.501 | 1.890 | 96,9% | 0,790 | 0,187 | 0,303 | 18 |
| V1-NFC | 1.501 | 1.906 | 97,5% | 0,737 | 0,151 | 0,250 | 27 |
| V1-tuned | 1.583 | 1.389 | 99,4% | 0,837 | 0,366 | 0,510 | 10 |
| V1-formatoE | 1.422 | 2.719 | 96,8% | 0,955 | 0,763 | 0,849 | 32 |
| **V2 (8 currículos)** | 8.664 | 18.746 | 98,5% | **0,969** | 0,602 | 0,743 | 156 |

Leitura: o **formato E** (um registro por linha) é a mudança decisiva — a precisão sai de
0,74–0,84 para 0,94 e a cobertura quintuplica. No formato antigo cada registro se espalhava
por várias linhas e o modelo ligava itens de registros diferentes (amostra do V0: pessoa
ligada ao livro errado, participante atribuído ao projeto errado). O V2 mantém a precisão
com 6× mais texto. A cobertura do V2 é menor que a do formatoE porque as ligações com
palavras-chave e áreas quase não viram relação (cobertura de 4–20% nessas classes, contra
86–98% para pessoas em publicações, softwares e orientações).

### V2 em detalhe

- **Sensibilidade ao limiar**: precisão 0,954 (exato) / 0,968 (95) / 0,969 (90) / 0,969
  (85); F1 de 0,685 a 0,758. A conclusão não depende do limiar.
- **Proveniência**: 98,2% das entidades aparecem no trecho de onde saíram (88,0% literais;
  o resto com as palavras fora de ordem, quase sempre nomes abreviados); 98,5% das relações
  têm as duas pontas no trecho. 156 entidades sem fonte (lista em `sem_fonte.txt`).
- **Tipo correto**: PERSON 99,9%, PUBLICATION 98,8%, EVENT 97,2%, COURSE 92,1%,
  ORGANIZATION 91,9%, SOFTWARE 90,1%, KNOWLEDGE_AREA 87,3%, GEO 85,6%, PROJECT 83,2%.
- **Registros que viraram entidade**: projetos, softwares e formação 100%, vínculos 99,7%,
  orientações 98,0%, eventos 94,2%, publicações 93,5%, bancas 85,0%, produção técnica 82,5%.
- **Fragmentação dos titulares** (entidades PERSON distintas para a mesma pessoa): Aloisio
  27, Hugo 20, Eduardo 14, José Garcia 13, Raphael 11, Maria Fernanda 8, Paulo Jorge 4,
  Mayara 2. Substitui a contagem da seção 16 (15/11/10…), que só via grafias próximas.
- **Pares de titulares, XML × grafo**: Hugo × Eduardo 162 × 161; Hugo × Aloisio 145 × 102
  (o grafo perde 43 — fragmentação do Aloisio); José Garcia × Raphael 27 × 42 (o grafo
  conta a mais).
- **Não suportadas (538)**: a amostra é de inferência além da fonte ("a UESC fica na
  Bahia", "o LDLS roda no Windows"), ligações entre registros vizinhos e troca de pessoa
  (um software do Aloisio Santos Nascimento Filho atribuído a "Aloisio Machado da Silva
  Filho", embora a própria descrição da relação cite o nome certo).
- O nome inventado que vazou dos exemplos dos prompts aparece como sem fonte e sem
  correspondente no XML (teste de regressão).

### Armadilhas (não repetir)

| sintoma | causa | solução |
|---|---|---|
| coautores fundidos com um titular ("PAULO FERREIRA" virou Hugo Saba) | **22 autorias** no Lattes trazem o ID do CNPq de uma pessoa e o nome de outra | titulares registrados primeiro; ID só une grafias se o nome for compatível (conflitos contados no relatório) |
| V0–V1 com precisão um pouco mais baixa que a real | validados contra o XML de 03/2026, mas indexados do de **06/2025** (`input_xml/`) | cada versão usa o XML com a mesma `DATA-ATUALIZACAO` do texto de entrada |
| "A. Nascimento" casava com "Marcelo Antônio do Nascimento" | inicial comparada com qualquer palavra; citação curta usada ao contrário | o prenome (ou a inicial) casa com o primeiro nome; o sentido inverso só para nomes completos |
| "Matheus Guimarães Andrade Tanure" não casava com "Matheus G. A. Tanure" | compatibilidade só num sentido | nomes completos comparados nos dois sentidos |
| entidades citadas no título do registro ("Bahia", "HTLV") sem suporte | busca só no texto livre | o texto do registro inclui títulos e demais itens (menos pessoas) |
| entidades da área de atuação e do resumo "não verificáveis" | o gabarito só lia registros com dados básicos, mas o extrator também escreve linhas de perfil | elementos com atributos úteis viram registros de "perfil" (só para a precisão, fora da cobertura) |
| códigos numéricos ("029100000000") e "Brasil" como instituição | atributos `CODIGO-INSTITUICAO`, `PAIS-...` classificados pelo nome | mesmos prefixos ignorados do extrator; valor sem letra é descartado; país e cidade antes de instituição |

---

## 19. Validação — camada 2: as consultas (07/10/2026)

Código em `scripts/validacao/` (`gerar_perguntas.py`, `executar_consultas.py`,
`avaliar_consultas.py`, `juiz_consultas.py`, `medir_custo.py`); perguntas, respostas e
avaliações em `runs/v2-npai/validacao/consultas/` (ignorado pelo Git).

**Perguntas (19, geradas do XML, com gabarito):** 8 dado-local (softwares, projetos,
orientador do doutorado, vínculos, orientandos), 3 atividade-local (parceiros no grupo,
coautores em comum), 4 dado-global (áreas, instituições, palavras-chave e pares mais
frequentes — "asserções") e 4 atividade-global (parcerias, evolução, oportunidades,
parecer — sem gabarito, só para o juiz). Classes do BenchmarkQED (Microsoft, 2025).

**Métodos:** objetivas em `basic`, `local` (nível 2) e **sem contexto** (o modelo sozinho,
piso de comparação); globais em `global` (nível 1), `local` e `basic`. Respostas objetivas
pedidas em lista (`response_type`), o que permite conferir cada item sem outro LLM.

**Custo real (medidor, conferido com o medidor estabilizado):** respostas (`gpt-4.1-mini`,
piloto + lote, 19:19–19:30 UTC) 4.218.308 + 251.490 tokens = **US$ 2,09**; juiz (`gpt-4.1`,
19:38–19:41 UTC) 156.038 + 5.613 = **US$ 0,36** — igual ao que a API devolveu. **Camada 2:
US$ 2,45** (estimativa do plano: ~US$ 4,00 com margem). 57 respostas, 0 erros.

### Avaliação determinística contra o XML (custo zero)

| classe | método | cobertura | precisão | F1 | itens citados | corretos | parciais | alucinados |
|---|---|---|---|---|---|---|---|---|
| dado-local (8) | basic | 0,676 | 0,814 | 0,731 | 62 | 48 | 13 | 1 |
| dado-local (8) | local | 0,414 | 0,571 | 0,443 | 34 | 24 | 9 | 1 |
| dado-local (8) | sem contexto | 0,000 | 0,000 | 0,000 | 27 | 0 | 4 | 23 |
| atividade-local (3) | basic | 0,246 | 0,166 | 0,137 | 55 | 8 | 47 | 0 |
| atividade-local (3) | local | 0,135 | 0,333 | 0,164 | 15 | 5 | 10 | 0 |
| atividade-local (3) | sem contexto | 0,024 | 0,000 | 0,000 | 29 | 0 | 3 | 26 |

| dado-global (4): asserções do XML citadas | global | local | basic |
|---|---|---|---|
| cobertura média | **0,675** | 0,383 | 0,342 |

Categorias de Pires et al. (2024): *correto* (está no gabarito), *parcial* (entidade real
dos currículos que não responde à pergunta), *alucinado* (não existe em nenhum currículo).

Leitura:
- **Sem contexto o modelo inventa**: 49 de 56 itens não existem em nenhum currículo
  (ex.: o orientador de doutorado de uma titular). Com o GraphRAG, 2 alucinados em 96 itens
  das perguntas objetivas — a recuperação ancora a resposta.
- **Para listar fatos de um pesquisador, `basic` supera `local`** (F1 0,73 × 0,44): a busca
  local monta o contexto pelas 10 entidades mais próximas e devolve listas curtas.
- **Para perguntas sobre o grupo inteiro, `global` cobre quase o dobro das asserções**
  (0,68 × 0,38 e 0,34), o resultado esperado por Edge et al. (2024).
- **"Pesquisadores do grupo" não existe no grafo**: nas perguntas de parceiros, os métodos
  listam coautores frequentes de fora do grupo (47 "parciais" no basic). O grafo não marca
  quem são os 8 titulares — limitação a registrar (e candidata a melhoria: um atributo ou
  comunidade "titular").

### Armadilhas (não repetir)

| sintoma | causa | solução |
|---|---|---|
| `graphrag query --data` lia o índice vetorial errado | `--data` só troca `output_storage`; o LanceDB vem de `vector_store.db_uri` | API Python com `cli_overrides` para os dois |
| siglas de software ("SRMS") contadas como alucinadas | o título no XML é "SRMS: Software para…" e o avaliador cortava no ':' | compara também a linha inteira e aceita sigla no início do título |

### Juiz LLM (`gpt-4.1`, deployment criado em 07/10 com autorização do usuário)

Likert 1–5 nas 4 dimensões de Jia et al. (2024); nas perguntas com gabarito, o juiz recebe a
referência do XML. Juiz diferente do gerador (`gpt-4.1` julgando `gpt-4.1-mini`).

| método | respostas | relevância | acurácia | completude | legibilidade |
|---|---|---|---|---|---|
| global | 8 | 4,75 | 4,50 | 4,75 | 5,00 |
| basic | 19 | 4,47 | 3,58 | 3,63 | 4,79 |
| local | 19 | 4,32 | 2,95 | 3,16 | 4,74 |
| sem contexto | 11 | 2,18 | 1,00 | 1,00 | 4,73 |

Separando as perguntas: nas objetivas, acurácia basic 3,27 × local 2,36 × sem contexto 1,00;
nas globais, global 4,50 × basic 4,00 × local 3,75.

Par a par nas 8 perguntas globais (3 pares × 2 ordens; taxa de vitória):

| método | abrangência | diversidade | empoderamento | relevância |
|---|---|---|---|---|
| global | **1,00** | **1,00** | **0,94** | **0,72** |
| basic | 0,31 | 0,31 | 0,34 | 0,58 |
| local | 0,19 | 0,19 | 0,22 | 0,20 |

Leitura: o juiz concorda com a avaliação determinística — basic é melhor que local para
listar fatos, global vence nas perguntas sobre o grupo (todas as comparações de abrangência e
diversidade, como em Edge et al., 2024), e sem contexto tira 1 em acurácia em todas. A
legibilidade alta do "sem contexto" (4,73) com acurácia 1,00 mostra por que legibilidade
sozinha não mede qualidade: o texto inventado é fluente.
