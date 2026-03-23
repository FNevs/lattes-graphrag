# Contexto do Projeto — Briefing para IAs e Modelos

> **Use este documento como contexto inicial ao interagir com qualquer IA ou
> modelo sobre este projeto.** Ele resume todas as decisões já tomadas, o estado
> atual da implementação e, principalmente, o protocolo da revisão sistemática.

---

## Identidade do projeto

| Campo | Valor |
| --- | --- |
| **Título do TCC** | Aplicação grafo do conhecimento com LLM: um experimento currículo Lattes de pesquisadores |
| **Tipo de trabalho** | Trabalho de Conclusão de Curso (TCC) — graduação |
| **Repositório** | `lattes-graphrag/` |
| **Linguagem do código** | Python 3.10+ |
| **Framework principal** | Microsoft GraphRAG |
| **LLM utilizado** | GPT-4o-mini (Azure OpenAI) |
| **Modelo de embedding** | text-embedding-3-small (Azure OpenAI, 1536 dims) |
| **Vector store** | LanceDB (local) |

---

## O que este projeto faz

Constrói um **grafo do conhecimento** a partir de **currículos Lattes** de
pesquisadores brasileiros, usando o framework **GraphRAG** (Microsoft), para
possibilitar **consultas semânticas** sobre os dados acadêmicos via LLM.

### Pipeline implementado

```
XML Lattes (CNPq)
    │
    ▼
[extract_lattes_text.py]  ← extração + limpeza (Unicode NFKC, remoção de
    │                        controle, dedup, atributos como chave-valor)
    ▼
TXT limpo (1 arquivo por currículo)
    │
    ▼
[GraphRAG indexer]  ← chunking (1200 tokens, overlap 100)
    │                  extração de entidades: [organization, person, geo, event]
    │                  summarização de descrições
    │                  clustering de comunidades (max 10)
    │                  community reports
    │                  embeddings
    ▼
Grafo do conhecimento + LanceDB
    │
    ▼
[Consultas]  ← local_search, global_search, drift_search, basic_search
```

### Diagrama de arquitetura

![Diagrama de arquitetura do pipeline](diagramas/diagrama_arquitetura_pipeline.png)

### Estrutura de pastas

```
lattes-graphrag/              # Raiz do repositório
  input_xml/                  # XMLs brutos baixados do Lattes
  input/                      # TXTs limpos gerados pelo script
  output/                     # Saída do GraphRAG (grafo, embeddings, reports)
  output/lancedb/             # Vector store local (embeddings)
  prompts/                    # Prompts customizados do pipeline GraphRAG
  scripts/
    extract_lattes_text.py    # Script de extração XML → TXT
  docs/
    fundamentacao_tcc.md      # Fundamentação acadêmica completa
    CONTEXTO_PROJETO.md       # Este arquivo (briefing para IAs)
    ingestao_lattes_xml.md    # Documentação técnica do pipeline de ingestão
    diagramas/                # Diagramas do projeto (Excalidraw, PNG)
  settings.yaml               # Configuração do GraphRAG
  .env                        # Chave da API (não versionado)
  .env.example
  requirements.txt
```

---

## Decisões acadêmicas já tomadas

### Pergunta de pesquisa

> Como a construção de um grafo do conhecimento, potencializado por modelos de
> linguagem de grande escala (LLMs), pode viabilizar a descoberta e a análise
> semântica de informações contidas em currículos Lattes de pesquisadores?

### Objetivo geral

Desenvolver e avaliar um artefato baseado em grafo do conhecimento,
potencializado por LLMs (GraphRAG), para extração, estruturação e consulta
semântica de informações contidas em currículos Lattes de pesquisadores.

### Objetivos específicos

1. Realizar uma Revisão Sistemática da Literatura (RSL) sobre grafos do
   conhecimento e LLMs no domínio acadêmico/curricular.
2. Projetar e implementar o pipeline de ingestão XML → TXT.
3. Configurar e executar o GraphRAG para construção do grafo.
4. Avaliar a qualidade do grafo e das respostas em consultas semânticas.
5. Discutir limitações, contribuições e extensões possíveis.

### Metodologia

**Design Science Research (DSR)** — Peffers et al. (2007), com 6 etapas:

1. Identificação do problema e motivação
2. Definição dos objetivos da solução
3. Design e desenvolvimento (o pipeline e o grafo)
4. Demonstração (execução com Lattes reais)
5. Avaliação (qualidade do grafo + respostas)
6. Comunicação (TCC)

O artefato é classificado como **instanciação** (sistema funcional).

---

## Revisão Sistemática — Protocolo completo (PRISMA 2020)

> **Esta seção é a mais importante para tarefas de pesquisa.** Siga este
> protocolo ao buscar, filtrar ou analisar artigos.

### Bases de dados

- Scopus
- Web of Science
- IEEE Xplore
- ACM Digital Library
- Google Scholar (complementar)

### Período

2020–2026 (foco nos avanços recentes com LLMs e grafos do conhecimento).

### Idiomas aceitos

Inglês e Português.

### Strings de busca

Foram definidas duas strings. Ambas podem ser usadas em paralelo nas bases.

**String A — Foco direto em GraphRAG + domínio acadêmico:**

```
("knowledge graph" OR "graph-based RAG" OR "GraphRAG")
AND ("LLM" OR "large language model")
AND ("curriculum" OR "academic" OR "researcher" OR "scholarly")
```

Captura trabalhos que explicitamente combinam grafos do conhecimento com LLMs no
contexto acadêmico. Mais restritiva; tende a retornar poucos resultados dado que
"GraphRAG" é um termo recente (2024).

**String B — Foco em extração de informação + perfis de pesquisadores:**

```
("knowledge graph" OR "ontology" OR "entity extraction")
AND ("natural language processing" OR "NLP" OR "large language model" OR "LLM"
     OR "retrieval-augmented generation" OR "RAG")
AND ("researcher profile" OR "academic CV" OR "scientific production"
     OR "scholarly data" OR "Lattes" OR "ORCID" OR "DBLP")
```

Mais ampla. Inclui trabalhos sobre ontologias, extração de entidades e NLP
aplicados a perfis acadêmicos (Lattes, ORCID, DBLP), mesmo que não usem o termo
"GraphRAG" especificamente. Essencial para mapear o estado da arte no domínio.

### Critérios de inclusão

- Artigos em periódicos, conferências ou pré-prints
- Tema: aplicação de grafos do conhecimento e/ou LLM a dados
  acadêmicos/curriculares
- Texto completo acessível

### Critérios de exclusão

- Livros, editoriais, resumos expandidos
- Aplicações puramente biomédicas ou industriais sem relação com o domínio
  acadêmico
- Apenas resumo disponível (sem texto completo)

### Dados a extrair de cada artigo incluído

Para cada estudo selecionado após triagem, extrair:

| Campo | Descrição |
| --- | --- |
| **Referência** | Autores, ano, título, venue |
| **Objetivo** | Objetivo e pergunta de pesquisa do estudo |
| **Tipo de grafo** | Knowledge graph, ontologia, grafo de citações, etc. |
| **LLM/NLP** | Modelo usado (GPT-4, BERT, etc.) e como foi aplicado |
| **Domínio** | Lattes, ORCID, DBLP, Scopus, dados acadêmicos genéricos, etc. |
| **Metodologia de avaliação** | Métricas, benchmarks, avaliação qualitativa, etc. |
| **Resultados principais** | Achados mais relevantes |
| **Limitações** | Limitações declaradas pelos autores |

### Fluxo PRISMA esperado

```
Registros identificados nas bases (String A + String B)
         │
         ▼
Remoção de duplicatas
         │
         ▼
Triagem por título e abstract
  ├── Excluídos (com motivo)
         │
         ▼
Leitura do texto completo
  ├── Excluídos com justificativa
         │
         ▼
Estudos incluídos na síntese qualitativa
```

Os números (n = ?) serão preenchidos durante a execução da revisão.

---

## Referências-chave do projeto

Estas são as referências fundamentais que embasam as escolhas metodológicas:

| Ref. | Uso no TCC |
| --- | --- |
| Peffers et al. (2007) — DSR Methodology for IS Research | Framework metodológico (DSR) |
| Page et al. (2021) — PRISMA 2020 statement | Protocolo da revisão sistemática |
| Edge et al. (2024) — From Local to Global: A Graph RAG Approach | Base técnica do GraphRAG |
| Pan et al. (2024) — Unifying LLMs and Knowledge Graphs: A Roadmap | Referencial teórico sobre KG+LLM |

---

## Estado atual do projeto (atualizar conforme progresso)

- [x] Pipeline de extração XML → TXT implementado e documentado
- [x] Configuração do GraphRAG (settings.yaml) definida
- [x] Prompts do pipeline GraphRAG gerados
- [x] Fundamentação acadêmica definida (objetivo, problema, DSR, PRISMA)
- [x] Diagrama de arquitetura do pipeline criado (Excalidraw)
- [ ] Execução da Revisão Sistemática (busca nas bases, triagem, síntese)
- [ ] Execução do indexador GraphRAG com dados reais
- [ ] Avaliação do grafo e das consultas
- [ ] Escrita final do TCC

---

## Como usar este documento

1. **Ao iniciar uma nova conversa com uma IA**, cole ou anexe este arquivo como
   contexto inicial.
2. **Para tarefas de código**, a IA deve respeitar a stack (Python 3.10+, Ruff,
   type hints, docstrings NumPy em português) e a estrutura de pastas existente.
3. **Para tarefas de pesquisa/revisão**, a IA deve seguir rigorosamente o
   protocolo PRISMA descrito acima, incluindo as strings de busca, os critérios
   de elegibilidade e a tabela de extração de dados.
4. **Para tarefas de escrita acadêmica**, o tom deve ser formal, em português,
   seguindo normas ABNT quando aplicável.
