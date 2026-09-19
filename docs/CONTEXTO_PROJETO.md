# Contexto do Projeto — Briefing para IAs e Modelos

> **Use este documento como contexto inicial ao interagir com qualquer IA sobre
> este projeto.** Atualizado em 2026-09 — substitui a versão anterior, que
> descrevia um estágio de planejamento já ultrapassado (RSL "a fazer", DSR de
> 6 etapas, objetivos com verbos de processo). Leia também `HANDOFF-TCC2.md`,
> nesta mesma pasta, para o estado técnico detalhado do pipeline.

---

## Identidade do projeto

| Campo | Valor |
| --- | --- |
| **Título do TCC** | Aplicação de Grafo do Conhecimento com LLM: Um Experimento com Currículos Lattes de Pesquisadores |
| **Aluno** | Filipe Neves Silva |
| **Orientador** | Eduardo Manuel de Freitas Jorge |
| **Instituição** | UNEB — Departamento de Ciências Exatas e da Terra |
| **Etapa atual** | **TCC2** — TCC1 (monografia parcial) já entregue e aprovada pelo orientador |
| **Tipo de trabalho** | Trabalho de Conclusão de Curso (TCC) — graduação |
| **Repositório deste código** | `lattes-graphrag/` (este repositório) |
| **Repositório da monografia** | `tcc-monografia` (separado — texto LaTeX completo, já com 6 capítulos escritos) |
| **Linguagem do código** | Python 3.10+ |
| **Framework principal** | Microsoft GraphRAG |
| **LLM utilizado** | `gpt-4o-mini` no TCC1; `gpt-4.1-mini` no TCC2 (Azure OpenAI, spaincentral — ver `HANDOFF-TCC2.md`, seção 3) |
| **Modelo de embedding** | `text-embedding-3-small` (Azure OpenAI) |
| **Vector store** | LanceDB (local) |

> **Importante:** a redação acadêmica completa (introdução, fundamentação
> teórica, trabalhos correlatos, metodologia, projeto, resultados parciais)
> já está escrita e entregue no repositório `tcc-monografia` — não redigir
> fundamentação aqui. Este repositório é só o código/pipeline.

---

## O que este projeto faz

Constrói um **grafo do conhecimento** a partir de **currículos Lattes** de
pesquisadores brasileiros, usando o framework **GraphRAG** (Microsoft), para
possibilitar **consultas semânticas** sobre os dados acadêmicos via LLM.

### Pipeline implementado (já em execução, não só planejado)

```
XML Lattes (CNPq)
    │
    ▼
[scripts/extract_lattes_text.py]  ← extração + limpeza
    │                                (normalização NFC desde 19/09/2026; era NFKC no TCC1)
    ▼
TXT limpo (1 arquivo por currículo, em input/)
    │
    ▼
[GraphRAG indexer]  ← chunking (1200 tokens, overlap 100)
    │                  extração de entidades: [organization, person, geo, event]
    │                  summarização de descrições
    │                  clustering de comunidades (max_cluster_size 10)
    │                  community reports
    │                  embeddings
    ▼
output/*.parquet + output/graph.graphml + LanceDB
    │
    ▼
[Consultas]  ← basic_search, local_search, global_search, drift_search
```

### Estrutura de pastas

```
lattes-graphrag/
  input_xml/                  # XMLs brutos baixados do Lattes
  input/                      # TXTs limpos gerados pelo script
  output/                     # Saída do GraphRAG (grafo, embeddings, reports)
  output/lancedb/             # Vector store local (embeddings)
  prompts/                    # Prompts customizados do pipeline GraphRAG
  scripts/
    extract_lattes_text.py    # Extração XML → TXT (normalizar_texto, ~linha 72)
    mapear_grafo.py           # Estatísticas dos parquet (pandas)
    figura_ego.py             # Visualização de ego-network (networkx + matplotlib)
  docs/
    CONTEXTO_PROJETO.md        # Este arquivo
    HANDOFF-TCC2.md            # Estado técnico, limitações e plano de tarefas
    fundamentacao_tcc.md       # Histórico — ver nota no topo do arquivo
    ingestao_lattes_xml.md     # Documentação do pipeline de ingestão
    diagramas/                 # Diagramas do projeto
  settings.yaml                # Configuração do GraphRAG
  .env                         # Chave da API (não versionado)
  requirements.txt
```

> `db.dump` (dump PostgreSQL com vários currículos, para a etapa de
> escalonamento) foi recebido mas **não faz parte deste repositório** — é
> dado pessoal sensível (LGPD), mantido só local. Ver `HANDOFF-TCC2.md`,
> seção 9, para como restaurá-lo e usá-lo.

---

## Decisões acadêmicas — versão final, já entregue no TCC1

### Problema de pesquisa (texto exato da monografia)

> Como conceber um artefato baseado em grafo do conhecimento e modelo de
> linguagem de grande escala que, aplicado a Currículos Lattes em XML,
> permita consultas semânticas e relacionais sobre informações acadêmicas,
> indo além da correspondência por palavra-chave e da similaridade textual
> entre documentos.

### Objetivo geral (texto exato da monografia)

> Conceber um artefato computacional baseado em grafo do conhecimento e
> modelo de linguagem de grande escala para consulta semântica de
> informações extraídas de Currículos Lattes em XML.

### Objetivos específicos (texto exato da monografia)

1. Disponibilizar uma representação relacional de informações acadêmicas
   extraídas de Currículos Lattes em XML.
2. Demonstrar a viabilidade de consultas semânticas sobre dados curriculares
   acadêmicos em formato semi-estruturado.
3. Oferecer uma alternativa semântica e relacional à busca exclusivamente
   baseada em palavra-chave na exploração de perfis acadêmicos.
4. Estruturar uma base experimental que permita a representação de relações
   entre pesquisadores, produções, áreas de atuação e vínculos acadêmicos.

> Note que os verbos são de **entrega** (disponibilizar, demonstrar,
> oferecer, estruturar), não de processo (não usar "estudar", "implementar",
> "avaliar", "investigar" como objetivo específico).

### Metodologia — Design Science Research, **7 etapas** (não 6)

Adaptado de Peffers et al. (2007):

1. Identificação do problema
2. Definição dos objetivos do artefato
3. Concepção do artefato
4. Desenvolvimento e refinamento do artefato
5. Demonstração
6. Avaliação preliminar
7. Comunicação dos resultados

**Onde o projeto está:** entre as etapas 4 e 5 — o artefato preliminar já foi
desenvolvido e demonstrado sobre um currículo real; a expansão para um
conjunto reduzido de currículos (etapa 4, continuação) e a avaliação
preliminar (etapa 6) são o foco do TCC2. Ver tarefas detalhadas em
`HANDOFF-TCC2.md`.

O artefato é classificado como **instanciação** (sistema funcional).

---

## Revisão Sistemática — já concluída (protocolo PRISMA 2020)

A RSL **não é mais uma etapa pendente** — foi executada e está integralmente
descrita no repositório `tcc-monografia` (capítulo "Trabalhos Relacionados").

- **Bases usadas**: Scopus, Web of Science, IEEE Xplore (não Google Scholar
  nem ACM Digital Library — esses estavam no plano original mas não entraram
  no protocolo final).
- **17 estudos incluídos**, em três frentes: consulta semântica (KG+LLM+RAG);
  extração de grafos/taxonomias; recomendação e descoberta de especialistas.
- **Lacuna identificada**: nenhum dos 17 estudos trabalha com a Plataforma
  Lattes ou dados curriculares em português; as iniciativas brasileiras
  anteriores (Café, 2024) seguem centradas em similaridade textual, sem
  relações explícitas.
- **Artefatos completos**: `tcc-monografia/docs/revisao-sistematica.pdf`
  (relatório da RSL) e `tcc-monografia/docs/resultados-rsl.json` (extração
  estruturada dos 17 estudos, 10 perguntas cada).

Não repetir a busca nem redefinir as strings — o protocolo já está fechado e
os resultados já sustentam a monografia entregue.

---

## Estado atual do projeto (2026-09)

- [x] Revisão Sistemática de Literatura — concluída, 17 estudos incluídos
- [x] Pipeline de extração XML → TXT — implementado
- [x] GraphRAG configurado e **executado** sobre 1 currículo real
- [x] Números do artefato preliminar auditados e corrigidos (ver
      `HANDOFF-TCC2.md`, seção 2)
- [x] Monografia parcial (TCC1) escrita, entregue, assinada pelo orientador,
      comentários do professor da disciplina endereçados
- [x] Apresentação de banca do TCC1 pronta e ensaiada
- [x] `db.dump` (vários currículos) recebido, para a etapa de escalonamento
- [x] Corrigir normalização NFKC → NFC no pré-processamento (19/09/2026)
- [ ] Restaurar `db.dump` e extrair conjunto reduzido de currículos coeso
- [ ] Escalonar o pipeline para esse conjunto
- [ ] Adicionar etapa de resolução de entidades (deduplicação)
- [ ] Executar o plano de validação (5 frentes)
- [ ] Redação final da monografia (TCC2) e defesa

Detalhamento de cada item pendente, com ordem sugerida e causa técnica de
cada limitação: ver `HANDOFF-TCC2.md`.

---

## Referências-chave

Lista completa e definitiva em
`tcc-monografia/elementos-pos-textuais/referencias.bib`. Núcleo metodológico:

| Ref. | Uso |
| --- | --- |
| Peffers et al. (2007) | Framework metodológico (DSR) |
| Dresch, Lacerda e Antunes Júnior (2015) | DSR — fundamentação complementar |
| Page et al. (2021) | Protocolo PRISMA 2020 (RSL) |
| Edge et al. (2024) | Base técnica do GraphRAG |
| Pan et al. (2024) | Referencial teórico KG+LLM |
| Furnas et al. (1987) | Problema do vocabulário |
| Lewis et al. (2020) | RAG |

Nunca inventar uma referência nova sem validar a fonte primeiro.

---

## Como usar este documento

1. Ao iniciar uma nova conversa com uma IA sobre este projeto, anexe este
   arquivo **e** `HANDOFF-TCC2.md` como contexto inicial.
2. Para tarefas de código: respeitar a stack (Python 3.10+) e a estrutura de
   pastas existente; ver `HANDOFF-TCC2.md` para armadilhas já conhecidas
   (venv com versão de Python incompatível entre máquinas, números que devem
   sempre ser lidos dos `.parquet` e nunca de memória, a diferença entre a
   modularidade recalculada e a partição real do GraphRAG).
3. Para tarefas de escrita acadêmica: a monografia já está escrita — mudanças
   de conteúdo acadêmico vão no repositório `tcc-monografia`, não aqui.
