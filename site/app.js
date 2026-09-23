/* Visualizador do grafo GraphRAG de curriculos Lattes.
   Le os JSON de dados/ (gerados por scripts/exportar_site.py) e desenha com sigma.js.
   Nada aqui chama a Azure: e tudo leitura de arquivo local.

   Tres visoes, como no viewer de modelos do Databricks:
     geral  -> os pesquisadores e as producoes que cada par divide;
     radial -> uma entidade no centro e os vizinhos em caixas por tipo;
     livre  -> o grafo inteiro, com filtros. */

/* ---------------- vocabulario e cores ---------------- */

const TIPOS = {
  PERSON: { nome: "Pessoa", plural: "Pessoas", desc: "Pesquisadores, coautores, orientandos e membros de banca." },
  PUBLICATION: { nome: "Publicação", plural: "Publicações", desc: "Artigos, trabalhos em eventos, livros, capítulos, dissertações e teses." },
  PROJECT: { nome: "Projeto", plural: "Projetos", desc: "Projetos de pesquisa, de extensão e de desenvolvimento." },
  ORGANIZATION: { nome: "Organização", plural: "Organizações", desc: "Universidades, institutos, empresas, agências de fomento e periódicos." },
  EVENT: { nome: "Evento", plural: "Eventos", desc: "Congressos, simpósios, seminários e outras reuniões científicas." },
  KNOWLEDGE_AREA: { nome: "Área do conhecimento", plural: "Áreas do conhecimento", desc: "Grandes áreas, subáreas e palavras-chave de pesquisa." },
  COURSE: { nome: "Curso", plural: "Cursos", desc: "Cursos de graduação e pós-graduação, e disciplinas ministradas." },
  SOFTWARE: { nome: "Software", plural: "Softwares", desc: "Programas registrados ou desenvolvidos." },
  GEO: { nome: "Local", plural: "Locais", desc: "Cidades, estados e países." },
};
// 8 cores validadas = 8 tipos com cor propria; o resto (Local e tipos fora da lista) vira "Outros".
const ORDEM_TIPOS = ["PERSON", "PUBLICATION", "PROJECT", "ORGANIZATION", "EVENT", "KNOWLEDGE_AREA", "COURSE", "SOFTWARE"];
const OUTROS = "OUTROS";

// Paleta categorica validada (scripts/validate_palette.js da skill de dataviz):
// escuro: CVD pior par adjacente 8.4, visao normal 19.3, contraste >= 3:1; claro: 9.1 / 19.6.
// A ordem e o mecanismo de seguranca para daltonismo: nao reordenar.
const PALETA = {
  escuro: ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#008300", "#9085e9", "#e66767"],
  claro: ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"],
};
const NEUTRO = { escuro: "#5f6a79", claro: "#a2acb8" };
const PONTE = { escuro: "#dfe6ee", claro: "#27303c" };   // entidade citada em 2+ curriculos
// No tema claro as linhas precisam de bem mais opacidade: com .28 quase sumiam no branco.
const ARESTA = { escuro: "rgba(150,165,185,.38)", claro: "rgba(52,66,90,.55)" };
const ARESTA_FOCO = { escuro: "rgba(255,106,61,.9)", claro: "rgba(214,72,30,.9)" };

const estado = {
  versoes: [],
  dados: null,
  relatorios: null,
  sigma: null,
  grafo: null,
  caixas: [],
  modo: "geral",
  foco: null,
  visao: null,
  historico: [],
  escalaFixa: false,
  razaoCamera: 1,
  arrastou: false,
  filtros: { tipos: new Set(), grauMin: 0, limite: 1200, isoladas: false, porGrupo: 10, busca: "" },
  corComunidade: new Map(),
  animando: false,
  layout: null,
  pausa: null,
};

const $ = (s) => document.querySelector(s);
const cria = (tag, cls, texto) => {
  const el = document.createElement(tag);
  if (cls) el.className = cls;
  if (texto !== undefined) el.textContent = texto;
  return el;
};
const numero = (n) => (n ?? 0).toLocaleString("pt-BR");
const escapa = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const tema = () => (document.body.dataset.tema === "claro" ? "claro" : "escuro");
const encurta = (s, n) => (s.length > n ? `${s.slice(0, n - 1)}…` : s);
const nomeTipo = (y) => (TIPOS[y] ? TIPOS[y].nome : y.toLowerCase().replace(/_/g, " "));
const SUFIXOS = ["filho", "filha", "junior", "júnior", "neto", "neta", "sobrinho"];
/** "Aloisio Santos Nascimento Filho" -> "Aloisio Nascimento Filho"; "Hugo Saba Pereira Cardoso" -> "Hugo Cardoso". */
const nomeCurto = (nome) => {
  const p = nome.split(" ").filter(Boolean);
  if (p.length <= 2) return nome;
  const ultimo = p[p.length - 1];
  if (SUFIXOS.includes(ultimo.toLowerCase()) && p.length > 3) return `${p[0]} ${p[p.length - 2]} ${ultimo}`;
  return `${p[0]} ${ultimo}`;
};

/* ---------------- cores ---------------- */

function corSlot(k) { return PALETA[tema()][k]; }
function corPesquisador(i) { return i < 8 ? corSlot(i) : NEUTRO[tema()]; }
function grupoDoTipo(y) { return ORDEM_TIPOS.includes(y) ? y : OUTROS; }
function corTipo(y) { const k = ORDEM_TIPOS.indexOf(y); return k >= 0 ? corSlot(k) : NEUTRO[tema()]; }

/**
 * Categoria do no no modo de cor escolhido: chave, rotulo, cor e ordem fixa na legenda.
 * A cor segue a entidade, nunca a posicao no filtro.
 */
function categoria(n) {
  const modo = $("#sel-cor").value;
  const t = tema();
  if (modo === "tipo") {
    const k = ORDEM_TIPOS.indexOf(n.y);
    return k >= 0
      ? { chave: n.y, rotulo: TIPOS[n.y].nome, cor: corSlot(k), ordem: k, explica: TIPOS[n.y].desc }
      : { chave: OUTROS, rotulo: "Outros", cor: NEUTRO[t], ordem: 99, explica: "Locais e tipos fora da lista" };
  }
  if (modo === "comunidade") {
    const k = estado.corComunidade.get(n.c);
    if (k === undefined) {
      return { chave: "outras", rotulo: "Outras comunidades", cor: NEUTRO[t], ordem: 99, explica: "Comunidades menores, sem cor própria" };
    }
    const c = (estado.dados.comunidades || []).find((x) => x.id === n.c && x.n === 0);
    const titulo = c ? c.t : `Comunidade ${n.c}`;
    return { chave: `c${n.c}`, rotulo: encurta(titulo, 34), cor: corSlot(k), ordem: k, explica: titulo };
  }
  if (!n.p || !n.p.length) {
    return { chave: "sem", rotulo: "Sem currículo identificado", cor: NEUTRO[t], ordem: 99, explica: "" };
  }
  if (n.p.length > 1 && estado.dados.pesquisadores.length > 1) {
    return { chave: "ponte", rotulo: "Em 2+ currículos", cor: PONTE[t], ordem: 50,
      explica: "Entidade citada por mais de um pesquisador: uma ponte do grupo" };
  }
  const p = estado.dados.pesquisadores.find((x) => x.i === n.p[0]);
  return { chave: `p${n.p[0]}`, rotulo: p ? nomeCurto(p.nome) : `#${n.p[0]}`, cor: corPesquisador(n.p[0]),
    ordem: n.p[0], explica: p ? p.nome : "" };
}

function corDoNo(n) { return categoria(n).cor; }

/** As 7 maiores comunidades de nivel 0 ganham cor; as demais ficam neutras ("Outras"). */
function prepararCoresComunidade() {
  estado.corComunidade = new Map();
  const nivel0 = (estado.dados.comunidades || []).filter((c) => c.n === 0).sort((a, b) => b.tam - a.tam);
  nivel0.slice(0, 7).forEach((c, k) => estado.corComunidade.set(c.id, k));
}

/* ---------------- carregamento ---------------- */

async function iniciar() {
  preencherGlossario();
  estado.versoes = await (await fetch("dados/versoes.json")).json();
  const sel = $("#sel-versao");
  estado.versoes.forEach((v) => {
    const op = cria("option", null, `${v.versao} — ${numero(v.entidades)} entidades`);
    op.value = v.versao;
    sel.appendChild(op);
  });
  const inicial = estado.versoes.find((v) => v.versao === "v2-npai") || estado.versoes[0];
  sel.value = inicial.versao;
  ligarEventos();
  await carregarVersao(inicial.versao);
}

async function carregarVersao(nome) {
  mostrarCarregando(true, "carregando dados…");
  estado.relatorios = null;
  const dados = await (await fetch(`dados/${nome}.json`)).json();
  estado.dados = dados;
  estado.filtros.tipos = new Set(Object.keys(dados.tipos));
  prepararCoresComunidade();

  $("#versao-descricao").textContent = dados.meta.descricao || "";
  $("#versao-descricao").title = dados.meta.descricao || "";
  desenharMetricas(dados.meta);
  desenharPesquisadores();
  desenharTipos();
  desenharComunidades();
  desenharConsultas(nome);

  const grauMax = Math.min(30, Math.max(...dados.nos.map((n) => n.d)) || 1);
  const slider = $("#grau-min");
  slider.max = String(grauMax);
  slider.value = String(dados.nos.length > 4000 ? 2 : 0);
  $("#valor-grau").textContent = slider.value;
  estado.filtros.grauMin = Number(slider.value);

  estado.historico = [];
  estado.visao = null;
  irParaGeral();
}

function desenharMetricas(meta) {
  const itens = [
    ["Currículos", meta.curriculos, "Currículos Lattes indexados nesta versão"],
    ["Entidades", meta.entidades, "Coisas que o modelo encontrou no texto: pessoas, produções, projetos, instituições…"],
    ["Relações", meta.relacoes, "Ligações que o texto afirma entre duas entidades"],
    ["Comunidades", meta.comunidades, "Grupos de entidades muito ligadas entre si (algoritmo de Leiden), em vários níveis"],
    ["Isoladas", meta.isoladas, "Entidades extraídas que o texto não liga a nada"],
  ];
  const cx = $("#metricas");
  cx.innerHTML = "";
  itens.forEach(([rotulo, valor, explica]) => {
    const d = cria("div");
    d.title = explica;
    d.innerHTML = `<strong>${numero(valor)}</strong> ${rotulo}`;
    cx.appendChild(d);
  });
  if (meta.custo) {
    const d = cria("div");
    d.title = "Custo real desta indexação na Azure (medidor de tokens)";
    d.innerHTML = `<strong>US$ ${meta.custo.toFixed(2).replace(".", ",")}</strong> de indexação`;
    cx.appendChild(d);
  }
}

/* ---------------- listas laterais ---------------- */

function desenharPesquisadores() {
  const ul = $("#lista-pesquisadores");
  const dados = estado.dados;
  ul.innerHTML = "";
  $("#conta-pesquisadores").textContent = dados.pesquisadores.length || "";
  dados.pesquisadores.forEach((p) => {
    const li = cria("li");
    li.dataset.i = p.i;
    li.title = `${p.nome}\n${numero(p.entidades)} entidades extraídas do currículo · ${numero(p.grau)} conexões do nó da pessoa`;
    const ponto = cria("span", "ponto");
    ponto.style.background = corPesquisador(p.i);
    li.append(ponto, cria("span", "nome", p.nome), cria("span", "conta", numero(p.entidades)));
    li.addEventListener("click", () => {
      irParaPesquisador(p.i);
      $("#lateral").classList.remove("aberta");
    });
    ul.appendChild(li);
  });
}

function desenharTipos() {
  const ul = $("#lista-tipos");
  ul.innerHTML = "";
  const tipos = Object.entries(estado.dados.tipos).sort((a, b) => b[1] - a[1]);
  tipos.forEach(([tipo, qtd]) => {
    const li = cria("li");
    li.dataset.tipo = tipo;
    li.title = TIPOS[tipo] ? TIPOS[tipo].desc : "Tipo fora da lista pedida ao modelo (defeito de extração)";
    const ponto = cria("span", "ponto");
    ponto.style.background = corTipo(tipo);
    li.append(ponto, cria("span", "nome", nomeTipo(tipo)), cria("span", "conta", numero(qtd)));
    li.addEventListener("click", (ev) => alternarTipo(tipo, ev, tipos.map((t) => t[0])));
    ul.appendChild(li);
  });
}

/** Clique simples esconde ou mostra; Alt+clique mostra so aquele tipo. */
function alternarTipo(tipo, ev, todos) {
  const conjunto = estado.filtros.tipos;
  if (ev.altKey) {
    conjunto.clear();
    conjunto.add(tipo);
  } else if (conjunto.has(tipo)) {
    conjunto.delete(tipo);
  } else {
    conjunto.add(tipo);
  }
  if (conjunto.size === 0) todos.forEach((t) => conjunto.add(t));
  [...$("#lista-tipos").children].forEach((li) => li.classList.toggle("desmarcado", !conjunto.has(li.dataset.tipo)));
  redesenhar();
}

function marcarPesquisadorAtivo(i) {
  [...$("#lista-pesquisadores").children].forEach((li) => li.classList.toggle("ativo", Number(li.dataset.i) === i));
}

/* ---------------- navegacao ---------------- */

function definirModo(modo) {
  estado.modo = modo;
  document.body.dataset.modo = modo;
  document.querySelectorAll(".modo").forEach((b) => {
    const alvo = b.dataset.modo;
    b.classList.toggle("ativo", alvo === modo || (alvo === "geral" && modo === "radial"));
  });
}

function redesenhar() {
  if (estado.modo === "livre") desenharLivre();
  else if (estado.modo === "radial") desenharRadial(estado.foco);
  else desenharGeral();
}

/**
 * Cada visao e {tipo, indice?, pesquisador?}. Navegar guarda a visao atual no historico;
 * o botao Voltar (ou Alt+seta esquerda) a restaura, como no viewer do Databricks.
 */
function navegar(visao, registrar = true) {
  if (registrar && estado.visao) estado.historico.push(estado.visao);
  if (estado.historico.length > 60) estado.historico.shift();
  estado.visao = visao;
  mostrarVisao(visao);
}

function voltar() {
  const anterior = estado.historico.pop();
  if (!anterior) return;
  estado.visao = anterior;
  mostrarVisao(anterior);
}

function mostrarVisao(v) {
  if (v.tipo === "livre") mostrarLivre();
  else if (v.tipo === "radial") mostrarRadial(v.indice, v.pesquisador);
  else mostrarGeral();
  $("#btn-voltar").hidden = estado.historico.length === 0;
}

function irParaGeral() { navegar({ tipo: "geral" }); }
function irParaLivre() { navegar({ tipo: "livre" }); }

function irParaPesquisador(i) {
  const centro = noDoTitular(i);
  if (centro === null) return;
  navegar({ tipo: "radial", indice: centro, pesquisador: i });
}

/** Centraliza uma entidade na visao radial (se ja for o foco, so atualiza o painel). */
function abrirRadial(indice) {
  if (estado.visao && estado.visao.tipo === "radial" && estado.visao.indice === indice) {
    selecionarNo(indice, false);
    return;
  }
  navegar({ tipo: "radial", indice });
}

/** Visao geral: com um curriculo so, cai direto na rede do titular. */
function mostrarGeral() {
  if (estado.dados.pesquisadores.length <= 1) {
    mostrarRadial(noDoTitular(0));
    return;
  }
  definirModo("geral");
  marcarPesquisadorAtivo(null);
  mostrarFoco(null);
  desenharGeral();
  detalhesGeral();
}

function mostrarRadial(indice, pesquisador) {
  definirModo("radial");
  const titular = estado.dados.pesquisadores.find((p) => p.no === indice);
  marcarPesquisadorAtivo(pesquisador ?? (titular ? titular.i : null));
  estado.foco = indice;
  mostrarFoco(estado.dados.nos[indice]);
  desenharRadial(indice);
  selecionarNo(indice, false);
}

function mostrarLivre() {
  definirModo("livre");
  marcarPesquisadorAtivo(null);
  mostrarFoco(null);
  desenharLivre();
  $("#aba-detalhes").innerHTML = '<p class="vazio">Clique em um nó para ver o que o texto diz sobre ele. ' +
    "Clique duas vezes para centralizá-lo na visão radial. Arraste os nós para reorganizar o espaço.</p>";
}

/** Selo no canto do grafo com a entidade em foco (como o nome da tabela no Databricks). */
function mostrarFoco(n) {
  const el = $("#foco");
  if (!n) { el.hidden = true; return; }
  el.hidden = false;
  el.querySelector("i").style.background = corDoNo(n);
  el.querySelector("span").textContent = n.t;
  el.title = `${n.t} · ${nomeTipo(n.y)}`;
}

/** No da pessoa titular; se o nome nao casar (versoes antigas), a pessoa de maior grau. */
function noDoTitular(i) {
  const p = estado.dados.pesquisadores.find((x) => x.i === i);
  if (p && p.no !== null && p.no !== undefined) return p.no;
  const k = estado.dados.nos.findIndex((n) => n.y === "PERSON");
  return k >= 0 ? k : 0;
}

/* ---------------- sigma: montagem comum ---------------- */

function novoSigma(g, opcoes = {}) {
  pararLayout();
  if (estado.sigma) estado.sigma.kill();
  estado.sigma = null;
  estado.grafo = g;
  estado.escalaFixa = !!opcoes.escalaFixa;
  estado.razaoCamera = 1;
  const t = tema();
  estado.sigma = new Sigma(g, $("#grafo"), {
    renderLabels: true,
    labelFont: '"Segoe UI", system-ui, sans-serif',
    labelSize: 13,
    labelWeight: "500",
    labelDensity: opcoes.densidade ?? 1,
    labelGridCellSize: opcoes.grade ?? 60,
    labelRenderedSizeThreshold: opcoes.limiarRotulo ?? 0,
    renderEdgeLabels: !!opcoes.rotulosAresta,
    edgeLabelSize: 12,
    edgeLabelWeight: "600",
    edgeLabelColor: { color: t === "claro" ? "#121821" : "#eef2f6" },
    defaultEdgeColor: ARESTA[t],
    hideEdgesOnMove: g.size > 3000,
    enableEdgeEvents: true,
    zIndex: true,
    // sem isso o sigma lanca erro quando o conteiner ainda nao tem largura
    // (aba em segundo plano, painel fechado, janela minimizada)
    allowInvalidContainer: true,
    // folga para rotulos compridos nao sairem da tela (a visao geral poe o nome abaixo do no)
    stagePadding: opcoes.folga ?? 48,
    // escala fixa: 1 unidade do grafo = 1 pixel. A visao radial e desenhada em pixels,
    // entao linhas e caixas tem o mesmo tamanho em qualquer tela; o que nao cabe fica
    // a um arrasto de distancia, como no viewer do Databricks.
    autoRescale: !opcoes.escalaFixa,
    // na radial tudo escala junto com o zoom (nos, linhas e, no desenho do rotulo, o texto):
    // afastar vira uma miniatura da mesma cena, sem rotulos invadindo a caixa vizinha
    itemSizesReference: opcoes.escalaFixa ? "positions" : "screen",
    defaultDrawNodeLabel: desenharRotulo,
    defaultDrawNodeHover: desenharRotuloHover,
  });

  prepararCamadaCaixas();
  estado.sigma.on("afterRender", desenharCaixas);
  estado.sigma.on("resize", desenharCaixas);
  estado.sigma.getCamera().on("updated", (c) => { estado.razaoCamera = c.ratio; });
  // o primeiro render acontece dentro do construtor, antes deste listener existir
  desenharCaixas();
  ativarArrasto(g);

  estado.sigma.on("clickNode", ({ node }) => aoClicarNo(node));
  estado.sigma.on("doubleClickNode", ({ node, event }) => {
    const i = g.getNodeAttribute(node, "indice");
    if (i !== undefined) { event.preventSigmaDefault(); abrirRadial(i); }
  });
  estado.sigma.on("clickEdge", ({ edge }) => aoClicarAresta(edge));
  estado.sigma.on("clickStage", () => { if (!estado.arrastou) limparDestaque(); esconderDica(); });
  estado.sigma.on("enterNode", ({ node, event }) => {
    $("#grafo").style.cursor = "pointer";
    const a = g.getNodeAttributes(node);
    mostrarDica(event, a.titulo || a.label, a.subtitulo);
  });
  estado.sigma.on("leaveNode", () => { $("#grafo").style.cursor = "default"; esconderDica(); });
  estado.sigma.on("enterEdge", ({ edge, event }) => {
    const a = g.getEdgeAttributes(edge);
    if (a.dica) mostrarDica(event, a.dicaTitulo, a.dica);
  });
  estado.sigma.on("leaveEdge", esconderDica);
  return estado.sigma;
}

/**
 * Arrastar nos reorganiza o espaco, como no viewer do Databricks. Na radial a caixa do
 * tipo acompanha (os limites sao recalculados a partir dos membros); na exploracao livre
 * o no arrastado fica fixo para o ForceAtlas2 nao desfazer a mudanca.
 */
function ativarArrasto(g) {
  const s = estado.sigma;
  let arrastado = null;
  s.on("downNode", ({ node }) => {
    arrastado = node;
    estado.arrastou = false;
    // sem isto o sigma reenquadra a camera quando o no sai dos limites antigos
    if (!s.getCustomBBox()) s.setCustomBBox(s.getBBox());
  });
  const captor = s.getMouseCaptor();
  captor.on("mousemovebody", (e) => {
    if (!arrastado) return;
    const pos = s.viewportToGraph(e);
    g.setNodeAttribute(arrastado, "x", pos.x);
    g.setNodeAttribute(arrastado, "y", pos.y);
    g.setNodeAttribute(arrastado, "fixed", true);
    estado.arrastou = true;
    esconderDica();
    e.preventSigmaDefault();
    e.original.preventDefault();
    e.original.stopPropagation();
  });
  const soltar = () => {
    if (!arrastado) return;
    arrastado = null;
    // o clique vem logo depois do mouseup: o atraso impede que soltar conte como clique
    setTimeout(() => { estado.arrastou = false; }, 0);
  };
  captor.on("mouseup", soltar);
  captor.on("mouseleave", soltar);
}

/** Rotulo com fundo ("chip"): legivel sobre arestas e em qualquer tema. */
function desenharRotulo(ctx, data, settings) {
  if (!data.label) return;
  // na radial o texto acompanha o zoom; abaixo de ~7 px ja nao se le, entao some
  const escala = estado.escalaFixa ? 1 / estado.razaoCamera : 1;
  const tam = settings.labelSize * escala;
  if (tam < 7) return;
  const peso = data.destaque ? "700" : settings.labelWeight;
  ctx.font = `${peso} ${tam}px ${settings.labelFont}`;
  const largura = ctx.measureText(data.label).width;
  const folga = 4 * escala;
  const vao = 8 * escala;
  let x;
  let y;
  if (data.abaixo) {
    x = data.x - largura / 2;
    y = data.y + data.size + tam + 6 * escala;
  } else if (data.lado === "esq") {
    x = data.x - data.size - vao - largura;
    y = data.y + tam / 3;
  } else {
    x = data.x + data.size + vao;
    y = data.y + tam / 3;
  }
  const claro = tema() === "claro";
  ctx.fillStyle = claro ? "rgba(255,255,255,.92)" : "rgba(14,17,23,.88)";
  ctx.strokeStyle = claro ? "rgba(40,55,80,.18)" : "rgba(160,175,195,.18)";
  ctx.lineWidth = 1;
  caixaArredondada(ctx, x - folga, y - tam + 1 - folga / 2, largura + folga * 2, tam + folga + 2 * escala, 5 * escala);
  ctx.fill();
  ctx.stroke();
  ctx.fillStyle = claro ? "#121821" : "#eef2f6";
  ctx.fillText(data.label, x, y);
}

function desenharRotuloHover(ctx, data, settings) {
  ctx.beginPath();
  ctx.arc(data.x, data.y, data.size + 4, 0, Math.PI * 2);
  ctx.strokeStyle = tema() === "claro" ? "#121821" : "#ffffff";
  ctx.lineWidth = 2;
  ctx.stroke();
  desenharRotulo(ctx, { ...data, label: data.label || encurta(data.titulo || "", 40) }, settings);
}

function caixaArredondada(ctx, x, y, w, h, r) {
  ctx.beginPath();
  if (ctx.roundRect) {
    ctx.roundRect(x, y, w, h, r);
  } else {
    ctx.rect(x, y, w, h);
  }
}

/* ---------------- caixas por tipo (camada abaixo do sigma) ---------------- */

function prepararCamadaCaixas() {
  let camada = $("#camada-caixas");
  if (!camada) {
    camada = document.createElement("canvas");
    camada.id = "camada-caixas";
    camada.style.cssText = "position:absolute;inset:0;pointer-events:none";
  }
  $("#grafo").prepend(camada);
}

function desenharCaixas() {
  const camada = $("#camada-caixas");
  if (!camada || !estado.sigma) return;
  const cont = $("#grafo");
  const dpr = window.devicePixelRatio || 1;
  const w = cont.clientWidth;
  const h = cont.clientHeight;
  if (camada.width !== Math.round(w * dpr) || camada.height !== Math.round(h * dpr)) {
    camada.width = Math.round(w * dpr);
    camada.height = Math.round(h * dpr);
    camada.style.width = `${w}px`;
    camada.style.height = `${h}px`;
  }
  const ctx = camada.getContext("2d");
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, w, h);
  const claro = tema() === "claro";

  const escala = estado.escalaFixa ? 1 / estado.razaoCamera : 1;
  estado.caixas.forEach((caixa) => {
    const c = limitesDaCaixa(caixa);
    const a = estado.sigma.graphToViewport({ x: c.x0, y: c.y0 });
    const b = estado.sigma.graphToViewport({ x: c.x1, y: c.y1 });
    const x = Math.min(a.x, b.x);
    const y = Math.min(a.y, b.y);
    const largura = Math.abs(b.x - a.x);
    const altura = Math.abs(b.y - a.y);
    const cor = caixa.cor;
    ctx.fillStyle = hexComAlfa(cor, claro ? 0.07 : 0.09);
    ctx.strokeStyle = hexComAlfa(cor, claro ? 0.55 : 0.5);
    ctx.lineWidth = 1.2;
    caixaArredondada(ctx, x, y, largura, altura, 12 * escala);
    ctx.fill();
    ctx.stroke();

    // titulo da caixa, no texto do tema (a cor fica no marcador ao lado); escala com o zoom
    const f1 = 12.5 * escala;
    const f2 = 12 * escala;
    if (f1 < 7) return;
    ctx.font = `700 ${f1}px "Segoe UI", system-ui, sans-serif`;
    const titulo = caixa.titulo.toUpperCase();
    const complemento = caixa.complemento ? `  ${caixa.complemento}` : "";
    const lt = ctx.measureText(titulo).width;
    ctx.font = `500 ${f2}px "Segoe UI", system-ui, sans-serif`;
    const lc = ctx.measureText(complemento).width;
    const cx = x + 10 * escala;
    const cy = y - 9 * escala;
    ctx.fillStyle = claro ? "#ffffff" : "#151a23";
    ctx.strokeStyle = hexComAlfa(cor, 0.6);
    caixaArredondada(ctx, cx - 6 * escala, cy - 14 * escala, lt + lc + 30 * escala, 22 * escala, 8 * escala);
    ctx.fill();
    ctx.stroke();
    ctx.fillStyle = cor;
    ctx.beginPath();
    ctx.arc(cx + 4 * escala, cy - 3 * escala, 4.5 * escala, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = claro ? "#121821" : "#eef2f6";
    ctx.font = `700 ${f1}px "Segoe UI", system-ui, sans-serif`;
    ctx.fillText(titulo, cx + 14 * escala, cy + escala);
    ctx.fillStyle = claro ? "#3f4a58" : "#b3bfcc";
    ctx.font = `500 ${f2}px "Segoe UI", system-ui, sans-serif`;
    ctx.fillText(complemento, cx + 14 * escala + lt, cy + escala);
  });
}

/**
 * Limites da caixa a partir das posicoes atuais dos membros: se o usuario arrasta um no,
 * a caixa cresce para continuar em volta dele. A margem do lado do rotulo e a largura
 * da coluna, para o texto caber dentro.
 */
function limitesDaCaixa(caixa) {
  const g = estado.grafo;
  let minX = Infinity; let maxX = -Infinity; let minY = Infinity; let maxY = -Infinity;
  (caixa.membros || []).forEach((k) => {
    if (!g.hasNode(k)) return;
    const n = g.getNodeAttributes(k);
    minX = Math.min(minX, n.x); maxX = Math.max(maxX, n.x);
    minY = Math.min(minY, n.y); maxY = Math.max(maxY, n.y);
  });
  if (minX === Infinity) return caixa;
  const texto = caixa.largura - caixa.recuo;
  return {
    x0: caixa.lado === "esq" ? minX - texto : minX - caixa.recuo,
    x1: caixa.lado === "esq" ? maxX + caixa.recuo : maxX + texto,
    y0: maxY + caixa.cabecalho,
    y1: minY - caixa.linha - 12,
  };
}

function hexComAlfa(hex, alfa) {
  if (!hex.startsWith("#")) return hex;
  const v = parseInt(hex.slice(1), 16);
  return `rgba(${(v >> 16) & 255},${(v >> 8) & 255},${v & 255},${alfa})`;
}

/* ---------------- visao geral: os pesquisadores ---------------- */

function desenharGeral() {
  const dados = estado.dados;
  const g = new graphology.Graph({ type: "undirected" });
  const total = dados.pesquisadores.length;
  const maxEnt = Math.max(...dados.pesquisadores.map((p) => p.entidades), 1);
  const estreita = ($("#grafo").clientWidth || 900) < 600;
  ordemNoCirculo().forEach((p, k) => {
    const ang = -Math.PI / 2 + (2 * Math.PI * k) / total;
    g.addNode(`p${p.i}`, {
      x: Math.cos(ang) * 10,
      y: Math.sin(ang) * 10,
      size: (estreita ? 8 : 12) + (estreita ? 12 : 18) * Math.sqrt(p.entidades / maxEnt),
      color: corPesquisador(p.i),
      label: estreita ? nomeCurto(p.nome) : p.nome,
      titulo: p.nome,
      subtitulo: `${numero(p.entidades)} entidades extraídas do currículo. Clique para abrir a rede.`,
      abaixo: true,
      pesquisador: p.i,
    });
  });
  const maxPar = Math.max(...dados.rede_titulares.map((r) => r[2]), 1);
  // numero so nas arestas relevantes: com 19 pares, rotular todas empilha numeros no centro
  const corte = Math.max(10, maxPar * 0.06);
  dados.rede_titulares.forEach(([a, b, n], k) => {
    g.addEdge(`p${a}`, `p${b}`, {
      size: 1.5 + 9 * Math.sqrt(n / maxPar),
      color: ARESTA[tema()],
      label: n >= corte ? numero(n) : "",
      par: k,
      dicaTitulo: `${nomeCurto(dados.pesquisadores[a].nome)} × ${nomeCurto(dados.pesquisadores[b].nome)}`,
      dica: `${numero(n)} produções ligadas aos dois. Clique para ver quais.`,
    });
  });
  estado.caixas = [];
  // margem para os nomes abaixo dos nos: generosa no desktop, contida no celular
  const larguraPalco = $("#grafo").clientWidth || 900;
  novoSigma(g, { rotulosAresta: true, folga: Math.round(Math.min(120, Math.max(40, larguraPalco * 0.12))) });
  $("#contador").textContent =
    `${total} pesquisadores · ${dados.rede_titulares.length} pares com produções em comum`;
  desenharLegenda();
  mostrarCarregando(false);
}

/** Ordem gulosa: comeca pelo mais conectado e encadeia o parceiro mais forte ainda livre. */
function ordemNoCirculo() {
  const dados = estado.dados;
  const peso = new Map();
  dados.rede_titulares.forEach(([a, b, n]) => { peso.set(`${a}-${b}`, n); peso.set(`${b}-${a}`, n); });
  const forca = (i) => dados.rede_titulares.reduce((s, [a, b, n]) => s + (a === i || b === i ? n : 0), 0);
  const restantes = new Set(dados.pesquisadores.map((p) => p.i));
  const ordem = [];
  let atual = [...restantes].sort((x, y) => forca(y) - forca(x))[0];
  while (atual !== undefined) {
    ordem.push(atual);
    restantes.delete(atual);
    const proximo = [...restantes].sort((x, y) => (peso.get(`${atual}-${y}`) || 0) - (peso.get(`${atual}-${x}`) || 0) || forca(y) - forca(x))[0];
    atual = proximo;
  }
  return ordem.map((i) => dados.pesquisadores.find((p) => p.i === i));
}

function detalhesGeral() {
  const cx = $("#aba-detalhes");
  const dados = estado.dados;
  cx.innerHTML = "";
  cx.appendChild(cria("h2", "titulo-no", "Rede do grupo"));
  cx.appendChild(cria("p", "explica",
    "Cada círculo é um pesquisador (tamanho = entidades extraídas do currículo). Cada linha conta as " +
    "produções ligadas aos dois — artigos, softwares e projetos em comum. Clique numa linha para ver as " +
    "produções, ou num pesquisador para abrir a rede dele."));
  const bloco = cria("div", "bloco");
  bloco.appendChild(cria("h3", null, "Pares que mais produzem juntos"));
  const ul = cria("ul", "relacoes");
  dados.rede_titulares.slice(0, 12).forEach(([a, b, n], k) => {
    const li = cria("li");
    li.innerHTML = `<span class="alvo">${escapa(nomeCurto(dados.pesquisadores[a].nome))} × ` +
      `${escapa(nomeCurto(dados.pesquisadores[b].nome))}</span>` +
      `<span class="texto">${numero(n)} produções em comum</span>`;
    li.addEventListener("click", () => detalhesPar(k));
    ul.appendChild(li);
  });
  if (!dados.rede_titulares.length) ul.appendChild(cria("li", null, "nenhum par com produções em comum"));
  bloco.appendChild(ul);
  cx.appendChild(bloco);
}

function detalhesPar(k) {
  const [a, b, n, exemplos] = estado.dados.rede_titulares[k];
  const pa = estado.dados.pesquisadores[a];
  const pb = estado.dados.pesquisadores[b];
  abrirPainel("detalhes");
  const cx = $("#aba-detalhes");
  cx.innerHTML = "";
  cx.appendChild(cria("h2", "titulo-no", `${pa.nome} × ${pb.nome}`));
  const etq = cria("div", "etiquetas");
  etq.appendChild(cria("span", "etiqueta forte", `${numero(n)} produções em comum`));
  cx.appendChild(etq);
  cx.appendChild(cria("p", "explica",
    "Produções (artigos, softwares, projetos) que o grafo liga às duas pessoas. A coautoria aparece pela " +
    "produção, não por uma aresta direta entre as pessoas."));
  const botoes = cria("div", "botoes-painel");
  [pa, pb].forEach((p) => {
    const bt = cria("button", null, `Abrir rede de ${nomeCurto(p.nome)}`);
    bt.addEventListener("click", () => irParaPesquisador(p.i));
    botoes.appendChild(bt);
  });
  cx.appendChild(botoes);
  const bloco = cria("div", "bloco");
  bloco.appendChild(cria("h3", null, `Exemplos (${exemplos.length} de ${numero(n)})`));
  const ul = cria("ul", "relacoes");
  exemplos.forEach((titulo) => {
    const li = cria("li");
    li.innerHTML = `<span class="alvo">${escapa(titulo.replace(/^\?|\?$/g, ""))}</span>`;
    const i = estado.dados.nos.findIndex((x) => x.t === titulo);
    if (i >= 0) li.addEventListener("click", () => abrirRadial(i));
    ul.appendChild(li);
  });
  bloco.appendChild(ul);
  cx.appendChild(bloco);
}

/* ---------------- visao radial: foco no centro, vizinhos em caixas ---------------- */

function vizinhosDe(indice) {
  const lista = [];
  estado.dados.arestas.forEach(([a, b, peso, desc], idx) => {
    if (a === indice) lista.push({ outro: b, peso, desc, idx });
    else if (b === indice) lista.push({ outro: a, peso, desc, idx });
  });
  return lista;
}

function desenharRadial(centro) {
  const dados = estado.dados;
  const nc = dados.nos[centro];
  const porGrupo = estado.filtros.porGrupo;

  // agrupa os vizinhos por tipo, na ordem fixa dos tipos
  const grupos = new Map();
  vizinhosDe(centro).forEach((v) => {
    const n = dados.nos[v.outro];
    if (!estado.filtros.tipos.has(n.y)) return;
    const chave = grupoDoTipo(n.y);
    if (!grupos.has(chave)) grupos.set(chave, []);
    grupos.get(chave).push(v);
  });
  const ordem = [...ORDEM_TIPOS, OUTROS].filter((k) => grupos.has(k));
  ordem.forEach((k) => grupos.get(k).sort((x, y) => y.peso - x.peso || dados.nos[y.outro].d - dados.nos[x.outro].d));

  const g = new graphology.Graph({ type: "undirected" });
  g.addNode(String(centro), {
    x: 0, y: 0, size: 22, color: corDoNo(nc), label: encurta(nc.t, 44), titulo: nc.t,
    subtitulo: `${nomeTipo(nc.y)} · ${numero(nc.d)} conexões`, indice: centro, destaque: true, abaixo: true, zIndex: 2,
  });

  // geometria em unidades do grafo: colunas largas o bastante para o rotulo caber
  // geometria em pixels (ver autoRescale em novoSigma)
  const W = 270;
  const H = 27;
  const CAB = 38;
  const FOLGA = 44;
  const BANDA = 90;
  const RECUO = 20;
  estado.caixas = [];

  const itensDe = (k) => grupos.get(k).slice(0, porGrupo);
  const alturaDe = (k) => CAB + itensDe(k).length * H + 12;

  const posicionarGrupo = (k, x0, yTopo, lado) => {
    const itens = itensDe(k);
    const cor = k === OUTROS ? NEUTRO[tema()] : corTipo(k);
    const membros = [];
    itens.forEach((v, j) => {
      const n = dados.nos[v.outro];
      const chave = String(v.outro);
      if (g.hasNode(chave)) return;
      membros.push(chave);
      g.addNode(chave, {
        x: lado === "esq" ? x0 + W - RECUO : x0 + RECUO,
        y: yTopo - CAB - j * H,
        size: Math.max(5, Math.min(10, 4 + Math.sqrt(n.d) * 0.8)),
        color: corDoNo(n),
        label: encurta(n.t, 30),
        titulo: n.t,
        subtitulo: `${nomeTipo(n.y)} · ${numero(n.d)} conexões`,
        indice: v.outro,
        lado,
      });
      g.addEdge(String(centro), chave, {
        size: 1.2, color: ARESTA[tema()], indice: v.idx,
        dicaTitulo: `${encurta(nc.t, 40)} — ${encurta(n.t, 40)}`,
        dica: v.desc || "sem descrição",
      });
    });
    const total = grupos.get(k).length;
    estado.caixas.push({
      x0, x1: x0 + W, y0: yTopo, y1: yTopo - alturaDe(k), cor,
      membros, lado, largura: W, recuo: RECUO, cabecalho: CAB, linha: H,
      titulo: k === OUTROS ? "Outros" : TIPOS[k].plural,
      complemento: total > itens.length ? `${itens.length} de ${numero(total)}` : `${total}`,
    });
  };

  // duas fileiras (acima e abaixo do centro); caixas da esquerda com rotulo para a esquerda
  const cima = ordem.slice(0, Math.ceil(ordem.length / 2));
  const baixo = ordem.slice(cima.length);
  const fileira = (lista, acima) => {
    const larguraTotal = lista.length * W + (lista.length - 1) * FOLGA;
    let x = -larguraTotal / 2;
    lista.forEach((k) => {
      const lado = x + W / 2 < -1 ? "esq" : "dir";
      const alto = alturaDe(k);
      const yTopo = acima ? BANDA + alto : -BANDA;
      posicionarGrupo(k, x, yTopo, lado);
      x += W + FOLGA;
    });
  };
  fileira(cima, true);
  fileira(baixo, false);

  novoSigma(g, { densidade: 1, grade: 20, escalaFixa: true, folga: 30 });
  const aproximou = enquadrarLegivel(String(centro));
  const mostrados = g.order - 1;
  const totalViz = [...grupos.values()].reduce((s, l) => s + l.length, 0);
  $("#contador").textContent = mostrados < totalViz
    ? `${numero(mostrados)} de ${numero(totalViz)} vizinhos (os mais ligados de cada tipo)`
    : `${numero(totalViz)} vizinhos`;
  if (aproximou) $("#contador").textContent += " · arraste para ver as demais caixas";
  if (!totalViz) $("#contador").textContent = "entidade isolada: o texto não a liga a nada";
  desenharLegenda();
  mostrarCarregando(false);
}

/**
 * A visao radial e lida em escala 1:1: afastar a camera aproxima as caixas mas nao
 * encolhe os rotulos (que tem tamanho fixo em pixels), e eles invadem a caixa vizinha.
 * Se tudo cabe, o sigma ja centraliza; se nao, a camera abre no foco e o resto fica a um
 * arrasto (o botao de enquadrar mostra tudo). Devolve se ficou algo fora da tela.
 */
function enquadrarLegivel(chaveCentro) {
  const cont = $("#grafo");
  let x0 = Infinity; let x1 = -Infinity; let y0 = Infinity; let y1 = -Infinity;
  estado.caixas.map(limitesDaCaixa).forEach((c) => {
    x0 = Math.min(x0, c.x0); x1 = Math.max(x1, c.x1);
    y0 = Math.min(y0, c.y0, c.y1); y1 = Math.max(y1, c.y0, c.y1) + 30;
  });
  if (!estado.caixas.length || !cont.clientWidth) return false;
  const cabe = x1 - x0 + 60 <= cont.clientWidth && y1 - y0 + 60 <= cont.clientHeight;
  if (cabe) return false;
  const centro = estado.sigma.getNodeDisplayData(chaveCentro);
  estado.sigma.getCamera().setState({ x: centro.x, y: centro.y, ratio: 1, angle: 0 });
  return true;
}

/* ---------------- exploracao livre: o grafo inteiro ---------------- */

function nosVisiveis() {
  const { tipos, grauMin, limite, isoladas } = estado.filtros;
  const selecionados = [];
  estado.dados.nos.forEach((n, i) => {
    if (!tipos.has(n.y)) return;
    if (n.d < grauMin) return;
    if (!isoladas && n.d === 0) return;
    selecionados.push(i);
  });
  selecionados.sort((a, b) => estado.dados.nos[b].d - estado.dados.nos[a].d);
  return new Set(selecionados.slice(0, limite));
}

function desenharLivre() {
  if (!estado.dados) return;
  mostrarCarregando(true, "montando grafo…");
  pararLayout();
  // setTimeout (e nao requestAnimationFrame): da tempo de pintar o "carregando" e
  // continua funcionando com a janela oculta, quando o rAF nao dispara.
  setTimeout(() => {
    const visiveis = nosVisiveis();
    const g = new graphology.Graph({ type: "undirected", multi: false });
    visiveis.forEach((i) => {
      const n = estado.dados.nos[i];
      g.addNode(String(i), {
        label: encurta(n.t, 34),
        titulo: n.t,
        subtitulo: `${nomeTipo(n.y)} · ${numero(n.d)} conexões`,
        size: Math.max(2.5, Math.min(18, 2.5 + Math.sqrt(n.d) * 1.6)),
        color: corDoNo(n),
        x: Math.random(),
        y: Math.random(),
        indice: i,
      });
    });
    let arestas = 0;
    estado.dados.arestas.forEach(([a, b, peso, desc], idx) => {
      if (!visiveis.has(a) || !visiveis.has(b)) return;
      const ca = String(a);
      const cb = String(b);
      if (g.hasEdge(ca, cb)) return;
      g.addEdge(ca, cb, {
        size: Math.max(0.4, Math.min(3, peso / 4)), color: ARESTA[tema()], indice: idx,
        dicaTitulo: `${encurta(estado.dados.nos[a].t, 36)} — ${encurta(estado.dados.nos[b].t, 36)}`,
        dica: desc || "sem descrição",
      });
      arestas += 1;
    });
    arranjoInicial(g);
    estado.caixas = [];
    novoSigma(g, { densidade: 0.35, grade: 110, limiarRotulo: g.order > 1200 ? 10 : 7 });
    iniciarLayout(g);
    $("#contador").textContent =
      `${numero(g.order)} de ${numero(estado.dados.nos.length)} nós · ${numero(arestas)} de ${numero(estado.dados.arestas.length)} relações`;
    desenharLegenda();
    mostrarCarregando(false);
  }, 16);
}

/** Arranjo inicial barato: um anel por cor, so para ter algo na tela na hora. */
function arranjoInicial(g) {
  const grupos = new Map();
  g.forEachNode((no, attr) => {
    if (!grupos.has(attr.color)) grupos.set(attr.color, []);
    grupos.get(attr.color).push(no);
  });
  const total = grupos.size || 1;
  let k = 0;
  grupos.forEach((nos) => {
    const ang = (2 * Math.PI * k) / total;
    const cx = Math.cos(ang) * 10;
    const cy = Math.sin(ang) * 10;
    nos.forEach((no, j) => {
      const a = (2 * Math.PI * j) / nos.length;
      const r = 1 + Math.sqrt(nos.length) / 8;
      g.setNodeAttribute(no, "x", cx + Math.cos(a) * r);
      g.setNodeAttribute(no, "y", cy + Math.sin(a) * r);
    });
    k += 1;
  });
}

/** ForceAtlas2 em worker: a pagina continua respondendo enquanto o grafo se organiza. */
function iniciarLayout(g) {
  pararLayout();
  const fa2 = graphologyLibrary.layoutForceAtlas2;
  const settings = {
    ...fa2.inferSettings(g),
    barnesHutOptimize: g.order > 500,
    gravity: 1.2,
    scalingRatio: 12,
    slowDown: 3,
  };
  estado.layout = new graphologyLibrary.FA2Layout(g, { settings });
  estado.layout.start();
  $("#estado-layout").textContent = "organizando…";
  if (!estado.animando) {
    const duracao = g.order > 2000 ? 5000 : g.order > 900 ? 3500 : 2500;
    estado.pausa = setTimeout(() => pararLayout(true), duracao);
  }
}

/** Para o worker; com `separar`, afasta os nos sobrepostos para os rotulos ficarem legiveis. */
function pararLayout(separar) {
  clearTimeout(estado.pausa);
  estado.pausa = null;
  if (estado.layout) {
    estado.layout.kill();
    estado.layout = null;
  }
  const g = estado.grafo;
  // o noverlap e sincrono: acima de ~1500 nos trava a interface por meio segundo,
  // e nessa escala os rotulos ja nao aparecem, entao nao compensa.
  if (separar && g && estado.modo === "livre" && g.order <= 1500 && graphologyLibrary.layoutNoverlap) {
    graphologyLibrary.layoutNoverlap.assign(g, { maxIterations: 30, settings: { margin: 2, ratio: 1.2, gridSize: 20 } });
  }
  $("#estado-layout").textContent = "";
}

/* ---------------- legenda ---------------- */

function desenharLegenda() {
  const cx = $("#legenda");
  cx.innerHTML = "";
  const g = estado.grafo;
  if (!g) return;
  const contagem = new Map();
  g.forEachNode((_, a) => {
    let cat;
    if (a.pesquisador !== undefined) {
      const p = estado.dados.pesquisadores.find((x) => x.i === a.pesquisador);
      cat = { chave: `p${a.pesquisador}`, rotulo: nomeCurto(p.nome), cor: corPesquisador(a.pesquisador), ordem: a.pesquisador, explica: p.nome };
    } else if (a.indice !== undefined) {
      cat = categoria(estado.dados.nos[a.indice]);
    } else {
      return;
    }
    const atual = contagem.get(cat.chave);
    if (atual) atual.n += 1;
    else contagem.set(cat.chave, { ...cat, n: 1 });
  });
  const mostrarContagem = estado.modo !== "geral";
  [...contagem.values()].sort((x, y) => x.ordem - y.ordem).forEach((c) => {
    const s = cria("span");
    s.title = c.explica ? `${c.explica} · ${numero(c.n)} na tela` : `${numero(c.n)} na tela`;
    const i = cria("i");
    i.style.background = c.cor;
    s.append(i, document.createTextNode(c.rotulo));
    if (mostrarContagem) s.appendChild(cria("b", null, numero(c.n)));
    cx.appendChild(s);
  });
}

/* ---------------- selecao e detalhes ---------------- */

function aoClicarNo(chave) {
  if (estado.arrastou) return;
  const a = estado.grafo.getNodeAttributes(chave);
  if (a.pesquisador !== undefined) {
    irParaPesquisador(a.pesquisador);
    return;
  }
  if (a.indice === undefined) return;
  if (estado.modo === "radial") {
    if (a.indice !== estado.foco) abrirRadial(a.indice);
    else selecionarNo(a.indice, false);
    return;
  }
  selecionarNo(a.indice, true);
}

function aoClicarAresta(chave) {
  const a = estado.grafo.getEdgeAttributes(chave);
  if (a.par !== undefined) detalhesPar(a.par);
  else if (a.indice !== undefined) selecionarAresta(a.indice);
}

function selecionarNo(indice, destacarNoGrafo) {
  const dados = estado.dados;
  const n = dados.nos[indice];
  if (destacarNoGrafo) destacar(indice);
  abrirPainel("detalhes");

  const cx = $("#aba-detalhes");
  cx.innerHTML = "";
  cx.appendChild(cria("h2", "titulo-no", n.t));

  const etq = cria("div", "etiquetas");
  const tipo = cria("span", "etiqueta forte", nomeTipo(n.y));
  tipo.title = TIPOS[n.y] ? TIPOS[n.y].desc : "Tipo fora da lista pedida ao modelo";
  etq.appendChild(tipo);
  const cnx = cria("span", "etiqueta", `${numero(n.d)} conexões`);
  cnx.title = "Grau: quantas relações a entidade tem no grafo";
  etq.appendChild(cnx);
  const men = cria("span", "etiqueta", `${numero(n.f)} menções`);
  men.title = "Em quantos trechos do texto a entidade apareceu";
  etq.appendChild(men);
  if (n.c !== undefined) {
    const com = (dados.comunidades || []).find((c) => c.id === n.c && c.n === 0);
    const b = cria("span", "etiqueta clicavel", `comunidade: ${encurta(com ? com.t : String(n.c), 30)}`);
    b.title = "Grupo de entidades muito ligadas entre si. Clique para ler o relatório.";
    b.addEventListener("click", () => abrirComunidade(n.c));
    etq.appendChild(b);
  }
  cx.appendChild(etq);

  if (estado.modo !== "radial" || estado.foco !== indice) {
    const botoes = cria("div", "botoes-painel");
    const bt = cria("button", null, "Centralizar na visão radial");
    bt.addEventListener("click", () => abrirRadial(indice));
    botoes.appendChild(bt);
    cx.appendChild(botoes);
  }

  if (n.p && n.p.length && dados.pesquisadores.length > 1) {
    const bloco = cria("div", "bloco");
    bloco.appendChild(cria("h3", null, n.p.length > 1 ? `Citada em ${n.p.length} currículos` : "Citada no currículo de"));
    const et = cria("div", "etiquetas");
    n.p.forEach((i) => {
      const p = dados.pesquisadores.find((x) => x.i === i);
      const s = cria("span", "etiqueta clicavel", p ? p.nome : `#${i}`);
      s.style.borderColor = corPesquisador(i);
      s.title = "Abrir a rede desta pessoa";
      s.addEventListener("click", () => irParaPesquisador(i));
      et.appendChild(s);
    });
    bloco.appendChild(et);
    cx.appendChild(bloco);
  }

  if (n.s) {
    const bloco = cria("div", "bloco");
    bloco.appendChild(cria("h3", null, "O que o texto diz"));
    bloco.appendChild(cria("p", "descricao", n.s));
    cx.appendChild(bloco);
  }

  const viz = vizinhosDe(indice).sort((x, y) => y.peso - x.peso);
  const bloco = cria("div", "bloco");
  bloco.appendChild(cria("h3", null, `Relações (${numero(viz.length)})`));
  const ul = cria("ul", "relacoes");
  viz.slice(0, 50).forEach((v) => {
    const alvo = dados.nos[v.outro];
    const li = cria("li");
    li.style.borderLeftColor = corDoNo(alvo);
    li.innerHTML = `<span class="alvo">${escapa(alvo.t)}</span><span class="tipo">${escapa(nomeTipo(alvo.y))}</span>` +
      (v.desc ? `<span class="texto">${escapa(v.desc)}</span>` : "");
    li.title = "Centralizar esta entidade";
    li.addEventListener("click", () => abrirRadial(v.outro));
    ul.appendChild(li);
  });
  if (viz.length > 50) ul.appendChild(cria("li", null, `… e mais ${numero(viz.length - 50)} relações`));
  if (!viz.length) ul.appendChild(cria("li", null, "entidade isolada: o texto não a liga a nada"));
  bloco.appendChild(ul);
  cx.appendChild(bloco);
}

function selecionarAresta(idx) {
  const [a, b, peso, desc] = estado.dados.arestas[idx];
  const na = estado.dados.nos[a];
  const nb = estado.dados.nos[b];
  abrirPainel("detalhes");
  const cx = $("#aba-detalhes");
  cx.innerHTML = "";
  cx.appendChild(cria("h2", "titulo-no", "Relação"));
  const etq = cria("div", "etiquetas");
  const f = cria("span", "etiqueta forte", `força ${peso}`);
  f.title = "Nota de 1 a 10 que o modelo deu à relação: quão direta e forte ela é no texto";
  etq.appendChild(f);
  cx.appendChild(etq);
  const bloco1 = cria("div", "bloco");
  bloco1.appendChild(cria("h3", null, "O que o texto diz"));
  bloco1.appendChild(cria("p", "descricao", desc || "sem descrição"));
  cx.appendChild(bloco1);
  const bloco = cria("div", "bloco");
  bloco.appendChild(cria("h3", null, "Entre"));
  const ul = cria("ul", "relacoes");
  [[a, na], [b, nb]].forEach(([i, n]) => {
    const li = cria("li");
    li.style.borderLeftColor = corDoNo(n);
    li.innerHTML = `<span class="alvo">${escapa(n.t)}</span><span class="tipo">${escapa(nomeTipo(n.y))}</span>`;
    li.addEventListener("click", () => abrirRadial(i));
    ul.appendChild(li);
  });
  bloco.appendChild(ul);
  cx.appendChild(bloco);
}

function destacar(indice) {
  const g = estado.grafo;
  if (!g || !g.hasNode(String(indice))) return;
  const foco = String(indice);
  const perto = new Set([foco, ...g.neighbors(foco)]);
  const apagado = tema() === "claro" ? "rgba(150,160,175,.35)" : "rgba(95,106,121,.28)";
  g.forEachNode((no, attr) => {
    if (!attr.corBase) g.setNodeAttribute(no, "corBase", attr.color);
    g.setNodeAttribute(no, "color", perto.has(no) ? attr.corBase || attr.color : apagado);
    g.setNodeAttribute(no, "forceLabel", perto.has(no));
  });
  g.forEachEdge((aresta, attr, o, d) => {
    g.setEdgeAttribute(aresta, "color", o === foco || d === foco ? ARESTA_FOCO[tema()] : "rgba(140,155,175,.06)");
  });
  estado.sigma.getCamera().animate({ ...estado.sigma.getNodeDisplayData(foco), ratio: 0.5 }, { duration: 450 });
}

function limparDestaque() {
  const g = estado.grafo;
  if (!g || estado.modo !== "livre") return;
  g.forEachNode((no, attr) => {
    if (attr.corBase) g.setNodeAttribute(no, "color", attr.corBase);
    g.setNodeAttribute(no, "forceLabel", false);
  });
  g.forEachEdge((a) => g.setEdgeAttribute(a, "color", ARESTA[tema()]));
}

/* ---------------- dica flutuante ---------------- */

function mostrarDica(evento, titulo, texto) {
  const dica = $("#dica");
  if (!titulo && !texto) return;
  dica.innerHTML = `${titulo ? `<strong>${escapa(titulo)}</strong>` : ""}${texto ? `<span>${escapa(texto)}</span>` : ""}`;
  dica.hidden = false;
  const palco = $(".palco").getBoundingClientRect();
  const topo = 0;
  let x = evento.x + 16;
  let y = evento.y + topo + 16;
  const w = dica.offsetWidth;
  const h = dica.offsetHeight;
  if (x + w > palco.width - 8) x = evento.x - w - 16;
  if (y + h > palco.height - 8) y = evento.y + topo - h - 12;
  dica.style.left = `${Math.max(8, x)}px`;
  dica.style.top = `${Math.max(topo + 4, y)}px`;
}

function esconderDica() { $("#dica").hidden = true; }

/* ---------------- comunidades ---------------- */

function desenharComunidades() {
  const cx = $("#aba-comunidades");
  cx.innerHTML = "";
  const coms = estado.dados.comunidades || [];
  if (!coms.length) {
    cx.appendChild(cria("p", "vazio", "Esta versão não tem comunidades calculadas."));
    return;
  }
  cx.appendChild(cria("p", "explica",
    "Grupos de entidades mais ligadas entre si do que com o resto (algoritmo de Leiden). O nível 0 tem os " +
    "grupos maiores; níveis maiores os dividem em partes mais específicas."));
  const niveis = [...new Set(coms.map((c) => c.n))].sort((a, b) => a - b);
  const barra = cria("div", "filtro-nivel");
  let nivel = niveis[0];
  const lista = cria("ul", "lista-comunidades");

  const pintar = () => {
    lista.innerHTML = "";
    coms.filter((c) => c.n === nivel).sort((a, b) => b.tam - a.tam).slice(0, 120).forEach((c) => {
      const li = cria("li");
      const k = nivel === 0 ? estado.corComunidade.get(c.id) : undefined;
      if (k !== undefined) li.style.boxShadow = `inset 3px 0 0 ${corSlot(k)}`;
      li.appendChild(cria("h4", null, c.t || `Comunidade ${c.id}`));
      li.appendChild(cria("p", null, `${numero(c.tam)} entidades${c.nota ? ` · relevância ${c.nota.toFixed(1)}` : ""}`));
      if (c.s) li.appendChild(cria("p", null, encurta(c.s, 170)));
      li.addEventListener("click", () => abrirComunidade(c.id));
      lista.appendChild(li);
    });
  };

  niveis.forEach((n) => {
    const b = cria("button", n === nivel ? "ativo" : null, `nível ${n}`);
    b.addEventListener("click", () => {
      nivel = n;
      [...barra.children].forEach((x) => x.classList.remove("ativo"));
      b.classList.add("ativo");
      pintar();
    });
    barra.appendChild(b);
  });
  cx.append(barra, lista);
  pintar();
}

async function abrirComunidade(id) {
  abrirPainel("comunidades");
  const cx = $("#aba-comunidades");
  if (!estado.dados.meta.relatorios) {
    cx.innerHTML = '<p class="vazio">Esta versão não gerou relatórios de comunidade.</p>';
    return;
  }
  if (!estado.relatorios) {
    cx.innerHTML = '<p class="vazio">carregando relatórios…</p>';
    estado.relatorios = await (await fetch(`dados/${estado.dados.meta.versao}.relatorios.json`)).json();
  }
  const r = estado.relatorios[String(id)];
  cx.innerHTML = "";
  const voltar = cria("button", "botao-largo", "← todas as comunidades");
  voltar.addEventListener("click", desenharComunidades);
  cx.appendChild(voltar);
  if (!r) {
    cx.appendChild(cria("p", "vazio", `Sem relatório para a comunidade ${id}.`));
    return;
  }
  cx.appendChild(cria("h2", "titulo-no", r.t));
  const etq = cria("div", "etiquetas");
  etq.appendChild(cria("span", "etiqueta forte", `nível ${r.n}`));
  if (r.nota) {
    const nt = cria("span", "etiqueta", `relevância ${r.nota.toFixed(1)}`);
    nt.title = "Nota de 0 a 10 que o modelo deu à importância da comunidade";
    etq.appendChild(nt);
  }
  cx.appendChild(etq);
  const corpo = cria("div", "relatorio");
  corpo.innerHTML = `<p>${escapa(r.c)
    .replace(/^#+\s*(.+)$/gm, "</p><h3>$1</h3><p>")
    .replace(/\n{2,}/g, "</p><p>")}</p>`;
  cx.appendChild(corpo);
}

/* ---------------- consultas salvas ---------------- */

async function desenharConsultas(versao) {
  const cx = $("#aba-consultas");
  cx.innerHTML = '<p class="vazio">carregando…</p>';
  try {
    const r = await fetch(`dados/${versao}.consultas.json`);
    if (!r.ok) throw new Error("sem arquivo");
    const consultas = await r.json();
    cx.innerHTML = "";
    consultas.forEach((c) => {
      const bloco = cria("div", "bloco");
      bloco.appendChild(cria("h3", null, `${c.metodo}${c.custo ? ` · US$ ${c.custo}` : ""}`));
      bloco.appendChild(cria("h2", "titulo-no", c.pergunta));
      const corpo = cria("div", "relatorio");
      corpo.innerHTML = `<p>${escapa(c.resposta).replace(/\n{2,}/g, "</p><p>")}</p>`;
      bloco.appendChild(corpo);
      cx.appendChild(bloco);
    });
  } catch {
    cx.innerHTML = '<p class="vazio">As consultas fixas ainda não foram executadas para esta versão. ' +
      "Elas são geradas uma vez, salvas em arquivo e exibidas aqui — consultar ao vivo custaria tokens a " +
      "cada pergunta.</p>";
  }
}

/* ---------------- glossario ---------------- */

function preencherGlossario() {
  const dl = $("#glossario-tipos");
  dl.innerHTML = "";
  Object.entries(TIPOS).forEach(([chave, t]) => {
    const dt = cria("dt");
    const i = cria("i");
    i.style.background = corTipo(chave);
    dt.append(i, document.createTextNode(t.nome));
    dl.append(dt, cria("dd", null, t.desc));
  });
  const dt = cria("dt");
  const i = cria("i");
  i.style.background = NEUTRO[tema()];
  dt.append(i, document.createTextNode("Outros"));
  dl.append(dt, cria("dd", null, "Locais e tipos que o modelo inventou fora da lista pedida (defeito de extração, raro)."));
}

/* ---------------- interface ---------------- */

function abrirPainel(aba) {
  document.querySelectorAll(".aba").forEach((b) => b.classList.toggle("ativa", b.dataset.aba === aba));
  document.querySelectorAll(".aba-conteudo").forEach((c) => c.classList.toggle("ativa", c.id === `aba-${aba}`));
  if (window.matchMedia("(max-width: 1100px)").matches) $("#painel").classList.add("aberto");
}

function mostrarCarregando(ativo, texto) {
  $("#carregando").classList.toggle("ativo", ativo);
  if (texto) $("#texto-carregando").textContent = texto;
}

/** Em tela estreita a barra superior nao cabe: o seletor de cor vai para a lateral. */
function ajustarLayout() {
  const campo = $("#campo-cor");
  const estreito = window.matchMedia("(max-width: 860px)").matches;
  const destino = estreito
    ? document.querySelector(`.grupo.${estado.modo === "livre" ? "so-livre" : "so-radial"} .extras-lateral`)
    : $(".controles");
  if (!destino || campo.parentElement === destino) return;
  if (estreito) destino.appendChild(campo);
  else destino.insertBefore(campo, $(".botoes"));
}

function ligarEventos() {
  $("#sel-versao").addEventListener("change", (e) => carregarVersao(e.target.value));
  $("#sel-cor").addEventListener("change", redesenhar);

  document.querySelectorAll(".modo").forEach((b) => b.addEventListener("click", () => {
    if (b.dataset.modo === "livre") irParaLivre();
    else irParaGeral();
    ajustarLayout();
  }));

  $("#por-grupo").addEventListener("input", (e) => { $("#valor-grupo").textContent = e.target.value; });
  $("#por-grupo").addEventListener("change", (e) => {
    estado.filtros.porGrupo = Number(e.target.value);
    if (estado.modo === "radial") desenharRadial(estado.foco);
  });

  $("#chk-animar").addEventListener("change", (e) => {
    estado.animando = e.target.checked;
    if (estado.modo !== "livre") return;
    if (estado.animando) iniciarLayout(estado.grafo);
    else pararLayout(true);
  });

  $("#grau-min").addEventListener("input", (e) => {
    $("#valor-grau").textContent = e.target.value;
    estado.filtros.grauMin = Number(e.target.value);
  });
  $("#grau-min").addEventListener("change", desenharLivre);
  $("#limite").addEventListener("input", (e) => {
    $("#valor-limite").textContent = e.target.value;
    estado.filtros.limite = Number(e.target.value);
  });
  $("#limite").addEventListener("change", desenharLivre);
  $("#chk-isoladas").addEventListener("change", (e) => {
    estado.filtros.isoladas = e.target.checked;
    desenharLivre();
  });

  $("#btn-limpar").addEventListener("click", () => {
    estado.filtros.tipos = new Set(Object.keys(estado.dados.tipos));
    $("#chk-isoladas").checked = false;
    estado.filtros.isoladas = false;
    document.querySelectorAll("#lista-tipos li").forEach((li) => li.classList.remove("desmarcado"));
    redesenhar();
  });

  const busca = $("#busca");
  let temporizador = null;
  busca.addEventListener("input", () => {
    clearTimeout(temporizador);
    temporizador = setTimeout(() => sugerir(busca.value), 160);
  });
  busca.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      const primeiro = $("#sugestoes li");
      if (primeiro) primeiro.click();
    }
    if (e.key === "Escape") $("#sugestoes").hidden = true;
  });
  document.addEventListener("click", (e) => {
    if (!e.target.closest(".busca")) $("#sugestoes").hidden = true;
  });

  const camera = () => estado.sigma.getCamera();
  $("#btn-mais").addEventListener("click", () => camera().animatedZoom({ duration: 250 }));
  $("#btn-menos").addEventListener("click", () => camera().animatedUnzoom({ duration: 250 }));
  $("#btn-ajustar").addEventListener("click", () => { limparDestaque(); camera().animatedReset({ duration: 350 }); });
  $("#btn-png").addEventListener("click", baixarImagem);

  $("#btn-tema").addEventListener("click", () => {
    document.body.dataset.tema = tema() === "claro" ? "escuro" : "claro";
    desenharPesquisadores();
    desenharTipos();
    preencherGlossario();
    redesenhar();
  });

  const legenda = $("#legenda");
  const botaoLegenda = $("#btn-legenda");
  const abrirLegenda = (aberta) => {
    legenda.classList.toggle("fechada", !aberta);
    botaoLegenda.setAttribute("aria-expanded", String(aberta));
  };
  // em tela baixa ou estreita a legenda cobriria o grafo: comeca fechada
  abrirLegenda(window.innerHeight > 620 && window.innerWidth > 900);
  botaoLegenda.addEventListener("click", () => abrirLegenda(legenda.classList.contains("fechada")));

  $("#btn-voltar").addEventListener("click", voltar);
  document.addEventListener("keydown", (e) => {
    if (e.altKey && e.key === "ArrowLeft") { e.preventDefault(); voltar(); }
  });
  ligarDivisores();

  $("#btn-conceitos").addEventListener("click", () => $("#conceitos").showModal());
  $("#btn-fechar-conceitos").addEventListener("click", () => $("#conceitos").close());
  $("#conceitos").addEventListener("click", (e) => { if (e.target.id === "conceitos") $("#conceitos").close(); });

  document.querySelectorAll(".aba").forEach((b) => {
    if (b.dataset.aba) b.addEventListener("click", () => abrirPainel(b.dataset.aba));
  });
  $("#btn-menu").addEventListener("click", () => $("#lateral").classList.toggle("aberta"));
  $("#btn-painel").addEventListener("click", () => $("#painel").classList.toggle("aberto"));
  $("#btn-fechar-painel").addEventListener("click", () => $("#painel").classList.remove("aberto"));

  let redimensionar = null;
  window.addEventListener("resize", () => {
    ajustarLayout();
    clearTimeout(redimensionar);
    // a visao radial escolhe fileiras ou coluna pela largura: refaz ao redimensionar
    redimensionar = setTimeout(() => {
      if (estado.modo === "radial") desenharRadial(estado.foco);
      else if (estado.sigma) estado.sigma.refresh();
    }, 200);
  });
  // o evento resize nao dispara em toda mudanca de largura (emulacao, rotacao):
  // a media query avisa sempre que cruza o limite.
  window.matchMedia("(max-width: 860px)").addEventListener("change", ajustarLayout);
  ajustarLayout();
}

/**
 * Divisores entre as colunas: arrastar ajusta a largura (o grafo acompanha); clique duplo
 * volta ao padrao. A largura escolhida fica guardada so neste navegador.
 */
function ligarDivisores() {
  const raiz = document.documentElement;
  const limites = {
    lateral: () => [200, Math.min(560, window.innerWidth * 0.4)],
    painel: () => [280, window.innerWidth * 0.7],
  };
  const guardar = (lado, valor) => {
    try {
      if (valor === null) localStorage.removeItem(`largura-${lado}`);
      else localStorage.setItem(`largura-${lado}`, String(valor));
    } catch { /* armazenamento indisponivel: segue sem lembrar */ }
  };
  ["lateral", "painel"].forEach((lado) => {
    try {
      const salvo = Number(localStorage.getItem(`largura-${lado}`));
      if (salvo) raiz.style.setProperty(`--${lado}`, `${salvo}px`);
    } catch { /* idem */ }
  });

  document.querySelectorAll(".divisor").forEach((div) => {
    const lado = div.dataset.lado;
    div.addEventListener("pointerdown", (ev) => {
      ev.preventDefault();
      div.setPointerCapture(ev.pointerId);
      div.classList.add("ativo");
      document.body.classList.add("redimensionando");
      const corpo = $(".corpo").getBoundingClientRect();
      let largura = null;
      const mover = (e) => {
        const [min, max] = limites[lado]();
        const bruto = lado === "lateral" ? e.clientX - corpo.left - 8 : corpo.right - 8 - e.clientX;
        largura = Math.round(Math.max(min, Math.min(max, bruto)));
        raiz.style.setProperty(`--${lado}`, `${largura}px`);
      };
      const parar = () => {
        div.classList.remove("ativo");
        document.body.classList.remove("redimensionando");
        div.removeEventListener("pointermove", mover);
        div.removeEventListener("pointerup", parar);
        div.removeEventListener("pointercancel", parar);
        if (largura !== null) guardar(lado, largura);
      };
      div.addEventListener("pointermove", mover);
      div.addEventListener("pointerup", parar);
      div.addEventListener("pointercancel", parar);
    });
    div.addEventListener("dblclick", () => {
      raiz.style.removeProperty(`--${lado}`);
      guardar(lado, null);
    });
  });

  // o grafo acompanha qualquer mudanca de tamanho do palco (divisor, painel, janela)
  if (window.ResizeObserver) {
    new ResizeObserver(() => {
      if (!estado.sigma) return;
      estado.sigma.resize();
      estado.sigma.refresh();
    }).observe($("#grafo"));
  }
}

function sugerir(texto) {
  const ul = $("#sugestoes");
  const termo = texto.trim().toLowerCase();
  ul.innerHTML = "";
  if (termo.length < 2) { ul.hidden = true; return; }
  const achados = [];
  for (let i = 0; i < estado.dados.nos.length && achados.length < 40; i += 1) {
    if (estado.dados.nos[i].t.toLowerCase().includes(termo)) achados.push(i);
  }
  achados.sort((a, b) => estado.dados.nos[b].d - estado.dados.nos[a].d);
  achados.slice(0, 12).forEach((i) => {
    const n = estado.dados.nos[i];
    const li = cria("li");
    li.innerHTML = `${escapa(n.t)} <small>${escapa(nomeTipo(n.y))} · ${numero(n.d)} conexões</small>`;
    li.addEventListener("click", () => {
      ul.hidden = true;
      $("#lateral").classList.remove("aberta");
      if (estado.modo === "livre" && estado.grafo && estado.grafo.hasNode(String(i))) selecionarNo(i, true);
      else abrirRadial(i);
    });
    ul.appendChild(li);
  });
  ul.hidden = achados.length === 0;
}

function baixarImagem() {
  const canvases = [...$("#grafo").querySelectorAll("canvas")];
  if (!canvases.length) return;
  const base = canvases.find((c) => c.width > 0) || canvases[0];
  const saida = document.createElement("canvas");
  saida.width = base.width;
  saida.height = base.height;
  const ctx = saida.getContext("2d");
  ctx.fillStyle = getComputedStyle(document.body).getPropertyValue("--fundo");
  ctx.fillRect(0, 0, saida.width, saida.height);
  canvases.forEach((c) => ctx.drawImage(c, 0, 0, saida.width, saida.height));
  const link = document.createElement("a");
  link.download = `grafo-${estado.dados.meta.versao}-${estado.modo}.png`;
  link.href = saida.toDataURL("image/png");
  link.click();
}

iniciar().catch((e) => {
  mostrarCarregando(false);
  $("#grafo").innerHTML = `<p style="padding:24px;color:#e66767">Falha ao carregar: ${escapa(e.message)}.
    Rode <code>python scripts/exportar_site.py</code> e sirva a pasta com <code>python -m http.server</code>.</p>`;
});
