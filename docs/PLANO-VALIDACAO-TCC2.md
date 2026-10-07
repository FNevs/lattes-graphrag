# Plano de validação automática (TCC2)

Proposta de 07/10/2026, ainda em discussão com o orientador. **Camada 1 implementada e
executada em 07/10/2026** (resultados na seção 18 do `REGISTRO-EXECUCAO-TCC2.md`). Substitui a validação manual
por amostra (Seção 4.2.2 da monografia) por uma validação **automática da população
inteira** contra o XML do Lattes, e automatiza a avaliação das consultas (Seções 4.2.3 a
4.2.5). Pontos vão mudar: este arquivo registra a versão atual do raciocínio e as fontes.

---

## 1. Princípio: o XML é o gabarito

O texto que o GraphRAG leu foi gerado do XML por um script determinístico
(`scripts/extract_lattes_text.py`): tudo o que o modelo poderia extrair existe no XML de
forma estruturada. Logo, cada entidade e cada relação do grafo pode ser conferida contra a
fonte — sem amostra e sem avaliador humano.

Registros estruturados nos 8 XMLs do V2 (contagem de 07/10/2026):

| registro no XML | quantidade |
|---|---|
| autores listados em produções (`AUTORES`) | 7.226 (1.487 com `NRO-ID-CNPQ`) |
| artigos / trabalhos em eventos / capítulos / livros | 494 / 325 / 80 / 28 |
| softwares / registros e patentes | 149 / 153 |
| projetos de pesquisa (integrantes) | 136 (932) |
| orientações concluídas (outras / mestrado / doutorado) | 244 / 97 / 65 |
| bancas (mestrado / qualificação / doutorado / graduação) | 128 / 113 / 80 / 80 |
| participações em eventos (congresso / seminário / encontro / simpósio) | 64 / 50 / 47 / 33 |
| vínculos profissionais (`ATUACAO-PROFISSIONAL`) | 133 |
| palavras-chave / áreas de atuação | 1.157 / 36 |

Os números finais da validação são **sobre o grafo inteiro** (8.664 entidades, 18.746
relações), não uma estimativa amostral.

## 2. Variantes de nome (o problema central do alinhamento)

A mesma pessoa aparece de muitas formas, e isso foi medido nos XMLs:

- cada titular declara de 1 a **29** formas de citação (`NOME-EM-CITACOES-BIBLIOGRAFICAS`);
- entre as pessoas identificadas pelo ID do CNPq, **37** aparecem com mais de um nome
  completo escrito, chegando a **10 grafias** para a mesma pessoa;
- só 1.487 das 7.226 autorias (20,6%) trazem o ID do CNPq.

O alinhamento de pessoas usa, nesta ordem: (1) o ID do CNPq, quando existe; (2) o nome
completo e as formas de citação declaradas; (3) a forma "sobrenome + iniciais"; (4)
semelhança aproximada (`rapidfuzz`), restrita a candidatos com o mesmo sobrenome. As
variantes do lado do grafo (Eduardo 15, Aloisio 11, Hugo 10…) são justamente o que a
métrica de fragmentação mede (Seção 3.b).

## 3. Camada 1 — o grafo contra o XML (custo zero)

Código em `scripts/validacao/` (versionado); saídas em `runs/<versao>/validacao/`
(ignoradas pelo Git, LGPD). Roda em todas as versões, de V0 a V2 — a tabela de evolução
mostra o efeito de cada mudança do pipeline com a mesma régua.

**a) Fidelidade ao trecho (proveniência).** Cada relação guarda os trechos de origem
(`text_unit_ids`). Verifica-se se as duas pontas aparecem no trecho: ambas / uma / nenhuma.
Pega entidades inventadas (o vazamento conhecido de um nome dos exemplos sintéticos dos
prompts serve de caso de teste). Corresponde ao *source grounding* que a Microsoft destaca.

**b) Entidades.** Cobertura (registros do XML que viraram entidade), tipo correto (matriz
de confusão: uma entidade que casa com um artigo deve ser `PUBLICATION`) e fragmentação
(quantas entidades casam com o mesmo registro ou a mesma pessoa).

**c) Relações por família — precisão, cobertura (recall) e F1:**

| família | o grafo afirma | fonte no XML |
|---|---|---|
| autoria | pessoa – publicação / software / patente | `AUTORES` |
| projeto | pessoa – projeto; projeto – financiador | `INTEGRANTES-DO-PROJETO`, `FINANCIADOR-DO-PROJETO` |
| orientação | orientador – orientando | `ORIENTACOES-*`, `OUTRAS-ORIENTACOES-*` |
| banca | titular – participantes | `PARTICIPACAO-EM-BANCA-*` |
| evento | pessoa – evento; trabalho – evento | `PARTICIPACAO-EM-*`, `TRABALHO-EM-EVENTOS` |
| vínculo e formação | pessoa – organização / curso | `ATUACAO-PROFISSIONAL`, `FORMACAO-ACADEMICA-TITULACAO` |
| área | pessoa / produção – área | `AREA-DE-ATUACAO`, `PALAVRAS-CHAVE` |

Relações que nenhuma família cobre (inferidas pelo modelo sem correspondente estruturado)
são reportadas como **não verificáveis**, à parte — não contam como erro nem como acerto.

**d) Pares de titulares.** Produções em comum segundo o XML × segundo o grafo, para os 19
pares conectados (ex.: os 161 do maior par).

**e) Estrutura (frente 1).** Mantida: tipos, graus, modularidade (Leiden), comunidades.

**Erro do próprio alinhamento.** Sem conferência humana, o risco é o casamento errar.
Mitigação: (1) análise de sensibilidade — métricas reportadas com limiares 85, 90 e 95;
(2) limite inferior conservador só com casamento exato após normalização.

**Dois níveis de teste.** A validação em si (os números do TCC) roda sempre sobre os XMLs e
o grafo reais. O código que a produz é testado em dois níveis:

1. **Testes de unidade, com casos construídos** (versionados): conferem normalização,
   casamento de nomes e contagem. Os casos são montados de propósito para cobrir cada
   situação difícil — acento, iniciais, ordem invertida, homônimos, sobrenome composto,
   título com pontuação diferente — com a resposta certa conhecida de antemão. Dados reais
   não garantem que todos esses casos apareçam, e o teste não pode quebrar se um XML for
   atualizado. A escolha é técnica, não de sigilo: os currículos Lattes são públicos.
2. **Testes de regressão, com dados reais** (rodam localmente): casos conhecidos dos 8
   currículos — o nome que vazou dos exemplos dos prompts precisa ser apontado como sem
   fonte; as variantes de nome de um titular precisam convergir para a mesma pessoa; a
   contagem de produções em comum do maior par precisa bater com o XML.

## 4. Camada 2 — as consultas (gasta tokens; confirmar antes)

Perguntas organizadas pelas quatro classes do BenchmarkQED (Microsoft, 2025):

| classe | exemplo no Lattes | avaliação |
|---|---|---|
| dado-local | "Quais softwares o pesquisador X registrou?" | gabarito do XML: P/R/F1 dos itens |
| atividade-local | "Com quem a pesquisadora Y mais colabora?" | gabarito do XML (contagem de coautoria) |
| dado-global | "Quais são as linhas de pesquisa do grupo?" | asserções derivadas do XML (áreas, palavras-chave) |
| atividade-global | "Que parcerias o grupo poderia formar?" | LLM como juiz, comparação par a par |

- **Perguntas objetivas** geradas por modelo a partir do XML (já nascem com resposta).
  `--response-type` pede resposta em lista, o que permite conferir os itens sem outro LLM.
- **Alucinações (frente 4)**: cada item citado é procurado no XML e classificado nas
  categorias de Pires et al. (2024) — correto / entidade real com detalhe errado /
  inventado / sem resposta — automaticamente.
- **Likert (frente 3)**: LLM avaliador nas 4 dimensões de Jia et al. (2024) — relevância,
  acurácia, completude, legibilidade. Para as perguntas globais, comparação par a par
  (Edge et al., 2024; BenchmarkQED): abrangência, diversidade, *empowerment*, relevância,
  com ordem invertida. O juiz deve ser um modelo diferente do gerador (`gpt-4.1` julgando
  respostas do `gpt-4.1-mini`), e a limitação de mesma família é registrada.
- **Baseline (frente 5)**: `--method basic` (RAG vetorial puro, condição "SS" de Edge et
  al.) e o modelo **sem contexto** como piso (Pires et al.: 55% com KG × 12,5% sem).
- As mesmas respostas alimentam a aba **Consultas** do site (uma execução serve às duas).

## 5. Estimativa de custo (07/10/2026)

Base: preço de tabela do `gpt-4.1-mini` (US$ 0,40 / 1 M entrada, US$ 1,60 / 1 M saída) —
confere com o medidor (4 consultas local/basic de 19/09: 40.013 + 2.546 tokens = US$ 0,02).
Juiz `gpt-4.1`: US$ 2,00 / 8,00 por 1 M (tabela; confirmar no medidor).

**Global no V2**, medido sobre os relatórios reais (`community_reports.parquet`, tokens
`o200k_base`), lotes de 12 mil tokens de contexto:

| nível de comunidade | relatórios | tokens | chamadas *map* | custo por pergunta |
|---|---|---|---|---|
| ≤ 0 | 42 | 54.420 | 5 | ~US$ 0,04 |
| ≤ 1 | 295 | 373.286 | 34 | ~US$ 0,20 |
| ≤ 2 (padrão da CLI) | 1.227 | 1.319.316 | 120 | ~US$ 0,70 (teto) |

**Cenário recomendado** (20 perguntas):

| item | cálculo | custo |
|---|---|---|
| 12 objetivas × {basic, local, sem contexto} | 36 × ~US$ 0,005 | US$ 0,18 |
| 8 globais × {global nível 1, local, basic} | 8 × ~US$ 0,21 | US$ 1,68 |
| juiz Likert (`gpt-4.1`) em todas as respostas | 60 × ~US$ 0,0065 | US$ 0,39 |
| juiz par a par nas 8 globais (3 pares × 2 ordens, 4 critérios por chamada) | 48 × ~US$ 0,012 | US$ 0,58 |
| piloto com 2 perguntas, antes do lote | — | ~US$ 0,30 |
| **subtotal** | | **~US$ 3,10** |
| **com margem de 30%** | | **~US$ 4,00** |

Variante com global no nível 2: + 8 × ~US$ 0,50 → **~US$ 8,00** com margem.
Acumulado hoje: US$ 24,79 de US$ 100. O custo real de cada etapa vem do medidor da Azure.

## 6. O que muda na Seção 4.2 da monografia

| frente | antes | proposta | apoio |
|---|---|---|---|
| 4.2.1 estrutura | métricas do grafo | igual | Abu-Rasheed et al. (2025); Zhang et al. (2024, OAG-Bench) |
| 4.2.2 amostra manual | 95 + 96 itens, 1 avaliador (Cochran) | população inteira contra o XML: P/R/F1 por família, proveniência, tipo, fragmentação | Tang et al. (2025, DOM-AKG); Yamamoto et al. (2025); OAG-Bench (desambiguação de autores) |
| 4.2.3 Likert | humana | LLM avaliador, 4 dimensões + par a par | Jia et al. (2024, DDM-RAG, usaram o Claude como avaliador); Edge et al. (2024); BenchmarkQED |
| 4.2.4 alucinações | contagem manual | contagem automática contra o XML | Pires et al. (2024); fidelidade (SelfCheckGPT no blog da Microsoft) |
| 4.2.5 baseline | lexical + vetorial | `basic` + modelo sem contexto | Xie e Liang (2025, GYWI); Pires et al. (2024) |

Argumento: Chen et al. (2025, paper2lkg) e a Microsoft recorrem a LLM como juiz porque não
têm gabarito; aqui ele existe, e por isso a maior parte da validação é determinística.

## 7. Como os trabalhos da RSL validaram (o que se aproveita)

| trabalho (chave BibTeX) | como validou | o que se aproveita |
|---|---|---|
| Tang et al., DOM-AKG (`Tang2025DOMAKG`) | P/R/F1 e BERTScore em 200 pares pergunta-resposta anotados; QASPER | P/R/F1; perguntas com resposta conhecida (aqui vindas do XML) |
| Yamamoto et al. (`Yamamoto2025`) | P/R/F1 de triplas contra gabarito, equivalência semântica julgada à mão; cita GraphJudge (LLM juiz de triplas) | P/R/F1 contra gabarito, com o casamento automatizado |
| Chen et al., paper2lkg (`Chen2025paper2lkg`) | sem gabarito: engenharia reversa (KG→texto, cosseno) e "avaliação por aplicação" (LLM professor gera perguntas, outro LLM responde) | modelos diferentes para gerar e julgar |
| Jia et al., DDM-RAG (`Jia2024DDM`) | Likert 1–5 em 4 dimensões por 2 humanos + Claude | as 4 dimensões, com LLM avaliador |
| Pires et al., GPTscholar (`kdir24`) | especialistas contam publicações corretas / alucinadas; com e sem KG | categorias de alucinação; baseline sem contexto |
| Xie e Liang, GYWI (`Xie2025`) | acurácia em múltipla escolha + nota por LLM + humanos; ablação RAG × GraphRAG | perguntas objetivas; ablação basic × local × global |
| Abu-Rasheed et al. (`AbuRasheed2025`) | P/R/F1, modularidade, especialistas | métricas estruturais |
| Zhang et al., OAG-Bench (`Zhang2024OAGBench`) | benchmark com tarefa de desambiguação de nomes de autores | fragmentação de nomes como métrica |
| Sankaradas et al., TalentScout (`Sankaradas2025`) | Precision@5, Recall@5, nDCG@5, MRR em busca de especialistas | P@k para perguntas "quem pesquisa X?" |
| Pan et al., Curriculum UIE (`llm_uie_curriculum2025`) | P/R/F1 de extração + validação humana | P/R/F1 por tipo |

## 8. Limitações (para o texto)

- O alinhamento erra: por isso a análise de sensibilidade e o limite inferior exato.
- "Correto" significa "está no XML": relação verdadeira que o XML não estrutura vira
  "não verificável".
- Juiz LLM tem viés (inclusive pela própria família de modelo): as métricas
  determinísticas são a âncora.
- A fragmentação de nomes atrapalha o alinhamento: é medida, não escondida, e motiva a
  resolução de entidades.

## 9. Fontes consultadas (07/10/2026)

- Microsoft Research Blog — *GraphRAG: Unlocking LLM discovery on narrative private data*
  (Larson; Truitt, 13 fev. 2024):
  https://www.microsoft.com/en-us/research/blog/graphrag-unlocking-llm-discovery-on-narrative-private-data/
  Avaliação descrita: juiz LLM par a par em *comprehensiveness*, *human enfranchisement* e
  *diversity*; SelfCheckGPT para fidelidade; proveniência (*source grounding*) das respostas;
  dataset VIINA.
- Microsoft Research Blog — *BenchmarkQED: Automated benchmarking of RAG systems*
  (Edge; Trinh; Morales Esquivel; Larson, 5 jun. 2025):
  https://www.microsoft.com/en-us/research/blog/benchmarkqed-automated-benchmarking-of-rag-systems/
  AutoQ (4 classes de pergunta: data-local, activity-local, data-global, activity-global),
  AutoE (juiz par a par em comprehensiveness, diversity, empowerment, relevance; ordem
  contrabalançada; 6 tentativas; *win rate*; pontuação por asserções), AutoD.
- Repositório: https://github.com/microsoft/benchmark-qed
- Os 17 trabalhos da RSL, em `tcc-monografia/papers-aceitos/` (chaves na Seção 7).

BibTeX das fontes novas (as da RSL já estão no `referencias.bib` da monografia;
`edge2024graphrag`, `larson2024graphragblog`, `manakul2023selfcheckgpt` e `traag2019leiden`
estão na Seção 10 do `REGISTRO-EXECUCAO-TCC2.md`):

```bibtex
@misc{edge2025benchmarkqed,
  author       = {Edge, Darren and Trinh, Ha and Morales Esquivel, Andres and Larson, Jonathan},
  title        = {{BenchmarkQED}: Automated benchmarking of {RAG} systems},
  howpublished = {Microsoft Research Blog},
  year         = {2025},
  note         = {Publicado em 5 jun. 2025. Acesso em: 7 out. 2026},
  url          = {https://www.microsoft.com/en-us/research/blog/benchmarkqed-automated-benchmarking-of-rag-systems/}
}
@misc{microsoft2025benchmarkqedrepo,
  author       = {{Microsoft}},
  title        = {benchmark-qed: Automated benchmarking of Retrieval-Augmented Generation ({RAG}) systems},
  howpublished = {GitHub},
  year         = {2025},
  note         = {Acesso em: 7 out. 2026},
  url          = {https://github.com/microsoft/benchmark-qed}
}
```

Observação: no `referencias.bib` da monografia, a entrada `MicrosoftGraphRAG2024` tem o
título do blog, mas aponta para `https://microsoft.github.io/graphrag/` (o site da
biblioteca). Para citar o blog, usar `larson2024graphragblog` (URL do blog).
