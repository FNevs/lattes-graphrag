# Fundamentação do TCC

> **Este documento está superado.** A fundamentação acadêmica completa — e
> muito mais desenvolvida do que o rascunho abaixo — já foi escrita, revisada
> e entregue como monografia LaTeX, no repositório `tcc-monografia`
> (capítulos: Introdução, Fundamentação Teórica, Trabalhos Relacionados,
> Metodologia, Projeto de Desenvolvimento, Considerações Finais).
>
> **Não editar este arquivo como se fosse a fundamentação real.** Ele fica
> aqui só como referência histórica do rascunho inicial. Para qualquer
> trabalho de escrita acadêmica, abrir o repositório `tcc-monografia` e
> editar os arquivos em `elementos-textuais/`.
>
> Abaixo, só os fatos essenciais, na versão **final e correta** — para
> consulta rápida sem precisar abrir o outro repositório.

---

## Título final

Aplicação de Grafo do Conhecimento com LLM: Um Experimento com Currículos
Lattes de Pesquisadores

## Problema de pesquisa (texto exato da monografia)

> Como conceber um artefato baseado em grafo do conhecimento e modelo de
> linguagem de grande escala que, aplicado a Currículos Lattes em XML,
> permita consultas semânticas e relacionais sobre informações acadêmicas,
> indo além da correspondência por palavra-chave e da similaridade textual
> entre documentos.

## Objetivo geral (texto exato da monografia)

> Conceber um artefato computacional baseado em grafo do conhecimento e
> modelo de linguagem de grande escala para consulta semântica de
> informações extraídas de Currículos Lattes em XML.

## Objetivos específicos (texto exato da monografia)

1. Disponibilizar uma representação relacional de informações acadêmicas
   extraídas de Currículos Lattes em XML.
2. Demonstrar a viabilidade de consultas semânticas sobre dados curriculares
   acadêmicos em formato semi-estruturado.
3. Oferecer uma alternativa semântica e relacional à busca exclusivamente
   baseada em palavra-chave na exploração de perfis acadêmicos.
4. Estruturar uma base experimental que permita a representação de relações
   entre pesquisadores, produções, áreas de atuação e vínculos acadêmicos.

## Metodologia

Design Science Research (Peffers et al., 2007; Dresch, Lacerda e Antunes
Júnior, 2015), **7 etapas** (não 6, como constava na versão antiga deste
documento): identificação do problema → definição dos objetivos do artefato →
concepção → desenvolvimento e refinamento → demonstração → avaliação
preliminar → comunicação dos resultados. O artefato é uma **instanciação**.

## Revisão Sistemática — já concluída

Protocolo PRISMA 2020, bases Scopus / Web of Science / IEEE Xplore
(diferente do plano original deste rascunho, que também listava ACM Digital
Library e Google Scholar — não usados no protocolo final). **17 estudos
incluídos.** Relatório completo e dados extraídos em
`tcc-monografia/docs/revisao-sistematica.pdf` e
`tcc-monografia/docs/resultados-rsl.json`.

## Lacuna assumida

Nenhum dos 17 estudos da RSL trabalha com a Plataforma Lattes nem com dados
curriculares em português; a estrutura específica do currículo Lattes
(orientações, produção, projetos) não é tratada pela literatura; as
iniciativas brasileiras anteriores (Café, 2024) permanecem centradas em
similaridade textual, sem relações explícitas entre entidades.

## Referências fundamentais

Lista completa e definitiva em
`tcc-monografia/elementos-pos-textuais/referencias.bib`.
