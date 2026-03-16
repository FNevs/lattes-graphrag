# Fundamentação do TCC

> **Título:** Aplicação grafo do conhecimento com LLM: Um experimento currículo
> Lattes de pesquisadores

---

## 1. Contexto

A **Plataforma Lattes** (CNPq) é o principal repositório de currículos
acadêmicos do Brasil, contendo informações detalhadas sobre produção científica,
formação, orientações, projetos e vínculos institucionais de pesquisadores. Os
dados estão disponíveis em formato XML semi-estruturado — rico em informação,
porém difícil de navegar, cruzar e analisar de forma relacional.

Paralelamente, os avanços em **Large Language Models (LLMs)** e em técnicas de
**Retrieval-Augmented Generation (RAG)** abriram novas possibilidades para
organizar e consultar informações não estruturadas. O **GraphRAG** (Microsoft,
2024) é uma abordagem que combina **grafos do conhecimento** com RAG, permitindo
que LLMs respondam a perguntas com consciência das relações entre entidades
extraídas dos dados.

Apesar do potencial, ainda há uma lacuna na aplicação dessas técnicas ao domínio
específico de dados curriculares acadêmicos brasileiros.

---

## 2. Problema

- Os currículos Lattes estão em XML semi-estruturado, o que dificulta buscas
  relacionais e análises transversais (ex: redes de colaboração, mapeamento de
  expertise por área).
- As ferramentas de busca tradicionais da plataforma Lattes são limitadas a
  buscas por palavra-chave, sem compreensão semântica ou relacional.
- Não há, na literatura, uma aplicação consolidada de grafos do conhecimento
  potencializados por LLMs para o domínio específico do Currículo Lattes.
- A extração manual de insights (quem colabora com quem, quais áreas estão em
  crescimento, quais pesquisadores possuem perfil complementar) é trabalhosa e
  não escalável.

---

## 3. Pergunta de Pesquisa

> **Como a construção de um grafo do conhecimento, potencializado por modelos de
> linguagem de grande escala (LLMs), pode viabilizar a descoberta e a análise
> semântica de informações contidas em currículos Lattes de pesquisadores?**

Subperguntas possíveis (opcionais, para refinar o escopo):

- Quais tipos de entidades e relações podem ser extraídos automaticamente dos
  currículos Lattes por um pipeline GraphRAG?
- Em que medida as respostas geradas via consulta ao grafo superam buscas
  tradicionais por palavra-chave em termos de relevância e completude?

---

## 4. Objetivo

### 4.1 Objetivo Geral

Desenvolver e avaliar um artefato baseado em grafo do conhecimento,
potencializado por LLMs (GraphRAG), para extração, estruturação e consulta
semântica de informações contidas em currículos Lattes de pesquisadores.

### 4.2 Objetivos Específicos

1. Realizar uma Revisão Sistemática da Literatura sobre aplicações de grafos do
   conhecimento e LLMs no domínio acadêmico/curricular.
2. Projetar e implementar um pipeline de ingestão que transforme dados XML do
   Lattes em texto limpo para indexação.
3. Configurar e executar o framework GraphRAG (Microsoft) para construção do
   grafo do conhecimento a partir dos dados tratados.
4. Avaliar a qualidade do grafo gerado e das respostas obtidas em consultas
   semânticas (local search, global search, drift search).
5. Discutir as limitações, contribuições e possibilidades de extensão do artefato
   proposto.

---

## 5. Metodologia — Design Science Research (DSR)

A metodologia adotada é a **Design Science Research (DSR)**, conforme o framework
de Peffers et al. (2007), por se tratar de um trabalho centrado no **projeto e
avaliação de um artefato** (o pipeline GraphRAG aplicado ao Lattes).

| Etapa DSR | Aplicação no TCC |
| --- | --- |
| **1. Identificação do problema e motivação** | Dificuldade de análise relacional e semântica dos dados do Lattes; ausência de soluções baseadas em KG+LLM para esse domínio. |
| **2. Definição dos objetivos da solução** | Construir um artefato que possibilite consultas semânticas sobre currículos Lattes via grafo do conhecimento + LLM. |
| **3. Design e desenvolvimento** | (a) Pipeline de extração XML→TXT; (b) Configuração do GraphRAG (indexação, extração de entidades/relações, embeddings, comunidades); (c) Prompts customizados. |
| **4. Demonstração** | Execução do pipeline com um conjunto de currículos Lattes reais; realização de consultas exemplares (local, global, drift search). |
| **5. Avaliação** | Análise qualitativa das respostas geradas; avaliação do grafo (entidades, relações, comunidades extraídas); comparação com busca convencional. |
| **6. Comunicação** | Escrita do TCC e possível publicação dos resultados. |

**Tipo de artefato DSR:** Instanciação (sistema funcional — pipeline de
software).

---

## 6. Revisão Sistemática — Protocolo PRISMA

Para a Revisão Sistemática da Literatura (RSL), será seguido o protocolo
**PRISMA 2020** (Page et al., 2021).

### 6.1 Estratégia de busca

| Item | Definição |
| --- | --- |
| **Bases de dados** | Scopus, Web of Science, IEEE Xplore, ACM Digital Library, Google Scholar (complementar) |
| **Período** | 2020–2026 (foco em avanços recentes com LLMs) |
| **Idioma** | Inglês e Português |

### 6.2 Strings de busca

**Opção A — Foco em GraphRAG e domínio acadêmico:**

```
("knowledge graph" OR "graph-based RAG" OR "GraphRAG")
AND ("LLM" OR "large language model")
AND ("curriculum" OR "academic" OR "researcher" OR "scholarly")
```

Justificativa: busca direta pela intersecção entre grafos do conhecimento
potencializados por LLMs e o contexto acadêmico/curricular.

**Opção B — Foco em extração de informação e perfis de pesquisadores:**

```
("knowledge graph" OR "ontology" OR "entity extraction")
AND ("natural language processing" OR "NLP" OR "large language model" OR "LLM"
     OR "retrieval-augmented generation" OR "RAG")
AND ("researcher profile" OR "academic CV" OR "scientific production"
     OR "scholarly data" OR "Lattes" OR "ORCID" OR "DBLP")
```

Justificativa: amplia o escopo para incluir trabalhos que tratam de construção de
grafos ou ontologias sobre dados de pesquisadores, mesmo que não usem
especificamente o termo "GraphRAG". Isso captura estudos sobre extração de
entidades e relações a partir de perfis acadêmicos (Lattes, ORCID, DBLP),
permitindo encontrar trabalhos correlatos que abordam o mesmo domínio com
técnicas variadas de NLP/LLM.

### 6.3 Critérios de elegibilidade

| Critério | Inclusão | Exclusão |
| --- | --- | --- |
| Tipo de publicação | Artigos em periódicos, conferências e pré-prints | Livros, editoriais, resumos expandidos |
| Tema | Aplicação de KG e/ou LLM a dados acadêmicos/curriculares | Aplicações puramente biomédicas ou industriais sem relação com o domínio acadêmico |
| Disponibilidade | Texto completo acessível | Apenas resumo disponível |

### 6.4 Fluxo PRISMA (a ser preenchido após execução)

```
Registros identificados nas bases (n = ?)
         │
         ▼
Registros após remoção de duplicatas (n = ?)
         │
         ▼
Registros triados por título/abstract (n = ?)
  ├── Excluídos (n = ?)
         │
         ▼
Artigos avaliados em texto completo (n = ?)
  ├── Excluídos com justificativa (n = ?)
         │
         ▼
Estudos incluídos na síntese (n = ?)
```

### 6.5 Extração e síntese de dados

Para cada estudo incluído, extrair:

- Objetivo e pergunta de pesquisa
- Tipo de grafo do conhecimento utilizado
- LLM empregado (modelo, versão)
- Domínio de aplicação
- Metodologia de avaliação
- Principais resultados e limitações

---

## 7. Referências fundamentais

- **Peffers, K., Tuunanen, T., Rothenberger, M. A., & Chatterjee, S.** (2007).
  A Design Science Research Methodology for Information Systems Research.
  *Journal of Management Information Systems*, 24(3), 45–77.
- **Page, M. J., McKenzie, J. E., Bossuyt, P. M., et al.** (2021). The PRISMA
  2020 statement: an updated guideline for reporting systematic reviews. *BMJ*,
  372, n71.
- **Edge, D., Trinh, H., Cheng, N., et al.** (2024). From Local to Global: A
  Graph RAG Approach to Query-Focused Summarization. *Microsoft Research*.
  arXiv:2404.16130.
- **Pan, S., Luo, L., Wang, Y., et al.** (2024). Unifying Large Language Models
  and Knowledge Graphs: A Roadmap. *IEEE Transactions on Knowledge and Data
  Engineering*.
