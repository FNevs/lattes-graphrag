# Visualizador do grafo (`site/`)

Página local que mostra o grafo do GraphRAG de cada versão do experimento. Custo zero:
não chama a Azure, só lê arquivos. Inspirada no viewer de modelos do Databricks
([lakehouse-industry-data-models](https://github.com/databricks-industry-solutions/lakehouse-industry-data-models)).
Complementa a seção 17 do `REGISTRO-EXECUCAO-TCC2.md`.

---

## 1. Como rodar e como atualizar

```powershell
# servir (fica em primeiro plano; Ctrl+C encerra)
.venv\Scripts\python.exe -m http.server 8777 --directory site
# abrir http://localhost:8777 e dar Ctrl+F5 depois de qualquer mudança no site

# regenerar os dados depois de uma indexação nova (todas as versões de runs/)
.venv\Scripts\python.exe scripts\exportar_site.py
# ou uma versão só (as outras continuam no seletor)
.venv\Scripts\python.exe scripts\exportar_site.py runs\v2-npai
```

`site/dados/` está no `.gitignore`: tem nomes e textos de currículos reais (LGPD).
O código do site e as bibliotecas (`site/vendor/`) são versionados; a página funciona
offline, o que importa para a defesa.

---

## 2. Arquitetura

| camada | o quê | onde |
|---|---|---|
| bruto | XML do Lattes | `lattesNAPI/lattes/*.xml` |
| tratado | um registro por linha, sem dado sensível | `input/*.txt` (`scripts/extract_lattes_text.py`) |
| analítico (gold) | entidades, relações, comunidades, relatórios | `runs/<versao>/output/*.parquet` |
| serviço | JSON compacto para a página | `site/dados/<versao>.json` (`scripts/exportar_site.py`) |

**Por que JSON e não banco:** o site é estático e só lê. O JSON do V2 (8,7 MB) carrega em
~50 ms localmente. Um Postgres ou Neo4j exigiria servidor rodando e uma API entre ele e a
página — mais peças na defesa, nenhum ganho para quem navega. Para SQL existe o DuckDB
sobre os Parquet (`scripts/consultas_grafo.sql`, `scripts/explorar_grafo.py --ui`); para
explorar como banco de grafos, o Neo4j pode importar os mesmos Parquet (notebook oficial
do GraphRAG). Nenhum dos dois é dependência do site.

### Arquivos gerados por versão

- `site/dados/versoes.json` — índice do seletor (o exportador **mescla**, não sobrescreve).
- `site/dados/<versao>.json` — tudo o que a página desenha:
  - `meta`: versão, descrição, data, modelo, custo (do `MANIFEST.json`), contagens;
  - `pesquisadores`: `{i, nome, entidades, grau, no}` — `no` é o índice do nó do titular;
  - `tipos`: contagem por tipo;
  - `nos`: `{t: título, y: tipo, d: grau, f: menções, s: descrição completa, p: [currículos], c: comunidade nível 0}`;
  - `arestas`: `[origem, destino, peso, descrição completa]` (índices de `nos`);
  - `comunidades`: `{id, n: nível, pai, tam, t: título do relatório, s: resumo, nota}`;
  - `coautoria`: `[a, b, n]` — pares de pessoas por produção em comum (≥ 2);
  - `rede_titulares`: `[a, b, n, exemplos]` — só entre os titulares (visão geral).
- `site/dados/<versao>.relatorios.json` — relatórios completos, carregados só ao abrir um.
- `site/dados/<versao>.consultas.json` — **ainda não existe** (ver pendências). Formato
  esperado pela aba Consultas: `[{"pergunta", "metodo", "resposta", "custo"}]`.

### Código

| arquivo | papel |
|---|---|
| `site/index.html` | estrutura, glossário (`<dialog id="conceitos">`) |
| `site/estilos.css` | tema escuro/claro por variáveis, layout em cartões, responsivo |
| `site/app.js` | estado, navegação, três visões, cores, legenda, arrasto, divisores |
| `site/vendor/` | graphology, graphology-library (ForceAtlas2, noverlap), sigma.js v3 |
| `site/icone-*.png`, `favicon.ico` | ícone do projeto (gerado da imagem enviada pelo usuário) |

---

## 3. As três visões

1. **Visão geral** — os 8 pesquisadores num círculo; linha = produções ligadas aos dois
   (Eduardo × Hugo = 161). Ordem no círculo gulosa (pares fortes lado a lado); só linhas com
   ≥ 10 produções levam número. Clique na linha lista as produções; no círculo abre a radial.
2. **Radial** — a entidade no centro e os vizinhos em **caixas por tipo**, os mais ligados
   primeiro ("10 de 350"; o limite é o controle "Itens por caixa"). Duas fileiras, acima e
   abaixo do centro; caixas da esquerda com rótulo à esquerda do nó.
3. **Exploração livre** — o grafo inteiro com filtros (mínimo de conexões, teto de nós,
   isoladas) e ForceAtlas2 num *worker*.

**Navegação:** cada visão é `{tipo, indice?, pesquisador?}`; `navegar()` empilha a atual em
`estado.historico` e o botão **← Voltar** (ou Alt+←) desempilha. Um selo no canto mostra o
foco atual. Clicar num nó da radial o centraliza; clique duplo na livre também.

---

## 4. Cores (regras que não devem ser quebradas)

Paleta categórica **validada** com o validador da skill de dataviz
(`node scripts/validate_palette.js "<hex,...>" --mode dark --surface "#0e1117"`):

| slot | escuro | claro |
|---|---|---|
| 1 | `#3987e5` | `#2a78d6` |
| 2 | `#d95926` | `#eb6834` |
| 3 | `#199e70` | `#1baf7a` |
| 4 | `#c98500` | `#eda100` |
| 5 | `#d55181` | `#e87ba4` |
| 6 | `#008300` | `#008300` |
| 7 | `#9085e9` | `#4a3aa7` |
| 8 | `#e66767` | `#e34948` |

Escuro: CVD pior par adjacente 8,4, visão normal 19,3, contraste ≥ 3:1. Claro: 9,1 / 19,6
(4 slots abaixo de 3:1 — compensado por rótulos visíveis). **A ordem é o mecanismo de
segurança para daltonismo: não reordenar, não gerar uma 9ª cor.**

- **Currículo de origem:** 8 cores = 8 pesquisadores (fixas pelo índice). Entidade em 2+
  currículos → tom neutro claro ("pontes", `PONTE`); sem currículo → cinza.
- **Tipo:** Pessoa, Publicação, Projeto, Organização, Evento, Área do conhecimento, Curso,
  Software; Local e tipos inválidos → "Outros".
- **Comunidade:** as 7 maiores do nível 0 (batem com as linhas de pesquisa de cada titular);
  o resto → "Outras".
- A cor segue a entidade, nunca a posição no filtro. Texto sempre na cor do tema, nunca na
  da série. A legenda mostra só o que está na tela, com contagem.

---

## 5. Decisões de interação

- **Radial em pixels:** `autoRescale: false` + `itemSizesReference: "positions"` — 1 unidade
  = 1 px; linha de 27 px, caixa de 270 px, em qualquer tela. O texto dos rótulos e dos
  títulos das caixas é escalado por `1 / razão da câmera` e some abaixo de 7 px, então
  afastar vira miniatura da mesma cena, sem rótulo invadindo a caixa vizinha. Se não cabe,
  a câmera abre no foco e o resto fica a um arrasto.
- **Caixas acompanham os membros:** os limites são recalculados das posições atuais
  (`limitesDaCaixa`), então arrastar um nó estica a caixa.
- **Arrasto de nós** em todas as visões (`ativarArrasto`); o nó arrastado fica `fixed` para o
  ForceAtlas2; o clique que termina um arrasto é ignorado.
- **Rótulos com fundo ("chip")** desenhados por `desenharRotulo`; encurtados a 30 caracteres
  na radial (texto completo na dica e no painel).
- **Divisores arrastáveis** entre as colunas; larguras em `localStorage`
  (`largura-lateral`, `largura-painel`); clique duplo volta ao padrão.
- **Responsivo:** ≤ 1100 px o painel vira gaveta; ≤ 860 px a lateral também, o seletor de
  cor migra para a lateral e os divisores somem; ≤ 620 px esconde botões secundários.

---

## 6. Armadilhas encontradas (não repetir)

| sintoma | causa | solução |
|---|---|---|
| caixas não apareciam | o sigma renderiza a 1ª vez **dentro do construtor**, antes do `afterRender` ser registrado | chamar `desenharCaixas()` logo após criar |
| grafo não montava com a janela oculta | `requestAnimationFrame` não dispara em aba oculta | `setTimeout` para trabalho que não é animação |
| erro "Container has no width" | contêiner sem largura (aba oculta, painel fechado) | `allowInvalidContainer: true` |
| página congelava ~800 ms a cada filtro | ForceAtlas2 síncrono na thread principal | `FA2Layout` (worker); `noverlap` só até 1.500 nós |
| selo/legenda não sumiam | `display: flex` no CSS anula o atributo `hidden` | regra `[hidden] { display: none }` específica |
| layout não reagia à largura | evento `resize` não dispara em toda mudança | `matchMedia(...).addEventListener("change")` + `ResizeObserver` |
| ForceAtlas2 sem bundle UMD | pacote é só CommonJS | `graphology-library` (inclui `layoutForceAtlas2`, `FA2Layout`, `layoutNoverlap`) |
| exportar uma versão sumia com as outras | `versoes.json` sobrescrito | exportador mescla o índice |
| descrições cortadas no painel | exportador limitava a 400/300 caracteres | exporta o texto completo |
| heredoc longo quebra no Bash do Windows | limite/aspas do shell | gravar o script em arquivo `.py` e executar |

---

## 7. Pendências e ideias

1. **Tour guiado (proposta, aguardando aprovação do usuário).** O **?** vira menu com
   "Tour guiado" e "Conceitos". Destaque com o resto escurecido, balão com Anterior /
   Próximo / Pular, teclado (setas, Esc), abre sozinho só na 1ª visita, sem biblioteca
   externa. Passos: (1) o que é o grafo; (2) métricas do topo; (3) seletor de versão;
   (4) visão geral — "clique numa linha"; (5) um pesquisador → radial, arrastar, Voltar;
   (6) cor + legenda, pontes; (7) painel: detalhes, texto, comunidades, consultas;
   (8) exploração livre; (9) botão ?.
2. **Consultas fixas** (~US$ 9 estimados): rodar uma vez por versão (basic/local, nunca
   `global` ao vivo) e gravar `site/dados/<versao>.consultas.json`. A aba já existe.
3. Arrastar **a caixa inteira** pelo título (hoje só nós).
4. Arrasto por **toque** no celular (hoje só mouse).
5. Refletir a **resolução de entidades** quando existir (variantes de nome: Eduardo tem 15,
   Hugo 10 — ver seção 16 do registro).
6. Legenda clicável para destacar uma categoria.
7. Filtro por pesquisador na exploração livre (hoje a lista navega para a radial).

## 8. Limitações conhecidas

- Com a radial de um titular, a cena é mais larga que a tela: é preciso arrastar.
- O PNG exportado reúne as camadas visíveis (inclui as caixas), mas na escala da tela.
- `site/dados/` precisa ser regenerado a cada indexação nova.
