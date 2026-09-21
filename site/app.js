/* Visualizador do grafo GraphRAG de currículos Lattes.
   Lê os JSON de dados/ (gerados por scripts/exportar_site.py) e desenha com sigma.js.
   Nada aqui chama a Azure: é tudo leitura de arquivo local. */

const PALETA = [
  "#ff6b4a", "#58a6ff", "#3fb950", "#d2a8ff", "#f2cc60",
  "#79c0ff", "#ff7b72", "#56d4dd", "#e3b341", "#a5d6ff",
];
const COR_TIPO = {
  PERSON: "#58a6ff", PUBLICATION: "#ff6b4a", ORGANIZATION: "#3fb950", PROJECT: "#d2a8ff",
  EVENT: "#f2cc60", SOFTWARE: "#56d4dd", KNOWLEDGE_AREA: "#ff7b72", COURSE: "#a5d6ff",
  GEO: "#8b949e",
};
const COR_PADRAO = "#6e7681";

const estado = {
  versoes: [],
  dados: null,
  relatorios: null,
  grafo: null,
  sigma: null,
  filtros: { pesquisadores: new Set(), tipos: new Set(), grauMin: 0, limite: 1200, isoladas: false, busca: "" },
  selecao: null,
  animando: false,
  quadro: null,
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

/* ---------------- carregamento ---------------- */

async function iniciar() {
  estado.versoes = await (await fetch("dados/versoes.json")).json();
  const sel = $("#sel-versao");
  estado.versoes.forEach((v) => {
    const op = cria("option", null, `${v.versao} — ${numero(v.entidades)} entidades`);
    op.value = v.versao;
    sel.appendChild(op);
  });
  const inicial = estado.versoes.find((v) => v.versao === "v2-npai") || estado.versoes[0];
  sel.value = inicial.versao;
  await carregarVersao(inicial.versao);
  ligarEventos();
}

async function carregarVersao(nome) {
  mostrarCarregando(true, "carregando dados…");
  estado.relatorios = null;
  estado.selecao = null;
  const dados = await (await fetch(`dados/${nome}.json`)).json();
  estado.dados = dados;

  estado.filtros.pesquisadores = new Set(dados.pesquisadores.map((p) => p.i));
  estado.filtros.tipos = new Set(Object.keys(dados.tipos));
  estado.filtros.busca = "";
  $("#busca").value = "";

  $("#versao-descricao").textContent = dados.meta.descricao || "";
  desenharMetricas(dados.meta);
  desenharPesquisadores(dados);
  desenharTipos(dados);
  desenharComunidades();
  desenharConsultas(nome);
  $("#aba-detalhes").innerHTML = '<p class="vazio">Clique em um nó ou em uma aresta para ver os detalhes.</p>';

  const grauMax = Math.min(30, Math.max(...dados.nos.map((n) => n.d)) || 1);
  const slider = $("#grau-min");
  slider.max = String(grauMax);
  slider.value = String(dados.nos.length > 4000 ? 2 : 0);
  $("#valor-grau").textContent = slider.value;
  estado.filtros.grauMin = Number(slider.value);

  atualizarGrafo();
}

function desenharMetricas(meta) {
  const itens = [
    ["Currículos", meta.curriculos],
    ["Entidades", meta.entidades],
    ["Relações", meta.relacoes],
    ["Comunidades", meta.comunidades],
    ["Isoladas", meta.isoladas],
  ];
  const cx = $("#metricas");
  cx.innerHTML = "";
  itens.forEach(([rotulo, valor]) => {
    const d = cria("div");
    d.innerHTML = `<strong>${numero(valor)}</strong> ${rotulo}`;
    cx.appendChild(d);
  });
  if (meta.custo) {
    const d = cria("div");
    d.innerHTML = `<strong>US$ ${meta.custo.toFixed(2)}</strong> de indexação`;
    cx.appendChild(d);
  }
}

/* ---------------- listas laterais ---------------- */

function corDoPesquisador(i) { return PALETA[i % PALETA.length]; }

function desenharPesquisadores(dados) {
  const ul = $("#lista-pesquisadores");
  ul.innerHTML = "";
  $("#conta-pesquisadores").textContent = dados.pesquisadores.length || "";
  if (!dados.pesquisadores.length) {
    ul.appendChild(cria("li", "conta", "versão com um currículo só"));
    return;
  }
  dados.pesquisadores.forEach((p) => {
    const li = cria("li");
    li.dataset.i = p.i;
    li.title = `${p.nome}: ${numero(p.entidades)} entidades, grau ${numero(p.grau)}`;
    const ponto = cria("span", "ponto");
    ponto.style.background = corDoPesquisador(p.i);
    li.append(ponto, cria("span", "nome", p.nome), cria("span", "conta", numero(p.entidades)));
    li.addEventListener("click", (ev) => alternarFiltro(estado.filtros.pesquisadores, p.i, li, ev, ul, dados.pesquisadores.map((x) => x.i)));
    ul.appendChild(li);
  });
}

function desenharTipos(dados) {
  const ul = $("#lista-tipos");
  ul.innerHTML = "";
  const tipos = Object.entries(dados.tipos).sort((a, b) => b[1] - a[1]);
  tipos.forEach(([tipo, qtd]) => {
    const li = cria("li");
    li.dataset.tipo = tipo;
    const ponto = cria("span", "ponto");
    ponto.style.background = COR_TIPO[tipo] || COR_PADRAO;
    li.append(ponto, cria("span", "nome", tipo.toLowerCase().replace(/_/g, " ")), cria("span", "conta", numero(qtd)));
    li.addEventListener("click", (ev) => alternarFiltro(estado.filtros.tipos, tipo, li, ev, ul, tipos.map((t) => t[0])));
    ul.appendChild(li);
  });
}

/** Clique simples alterna um item; clique com Alt isola apenas ele. */
function alternarFiltro(conjunto, valor, li, ev, ul, todos) {
  if (ev.altKey || (conjunto.size === todos.length && ev.detail === 2)) {
    conjunto.clear();
    conjunto.add(valor);
  } else if (conjunto.has(valor)) {
    conjunto.delete(valor);
  } else {
    conjunto.add(valor);
  }
  if (conjunto.size === 0) todos.forEach((t) => conjunto.add(t));
  [...ul.children].forEach((item) => {
    const chave = item.dataset.tipo ?? Number(item.dataset.i);
    item.classList.toggle("desmarcado", !conjunto.has(chave));
  });
  atualizarGrafo();
}

/* ---------------- montagem do grafo ---------------- */

function nosVisiveis() {
  const { pesquisadores, tipos, grauMin, limite, isoladas, busca } = estado.filtros;
  const temPesquisadores = estado.dados.pesquisadores.length > 0;
  const termo = busca.trim().toLowerCase();
  const selecionados = [];
  estado.dados.nos.forEach((n, i) => {
    if (!tipos.has(n.y)) return;
    if (n.d < grauMin) return;
    if (!isoladas && n.d === 0) return;
    if (temPesquisadores && n.p.length && !n.p.some((p) => pesquisadores.has(p))) return;
    if (termo && !n.t.toLowerCase().includes(termo)) return;
    selecionados.push(i);
  });
  selecionados.sort((a, b) => estado.dados.nos[b].d - estado.dados.nos[a].d);
  return new Set(selecionados.slice(0, limite));
}

function corDoNo(n) {
  const modo = $("#sel-cor").value;
  if (modo === "tipo") return COR_TIPO[n.y] || COR_PADRAO;
  if (modo === "comunidade") return n.c === undefined ? COR_PADRAO : PALETA[n.c % PALETA.length];
  if (!n.p || !n.p.length) return COR_PADRAO;
  return corDoPesquisador(n.p[0]);
}

function atualizarGrafo() {
  if (!estado.dados) return;
  mostrarCarregando(true, "montando grafo…");
  pararAnimacao();

  // setTimeout (e nao requestAnimationFrame): da tempo de pintar o "carregando" e
  // continua funcionando com a janela oculta, quando o rAF nao dispara.
  setTimeout(() => {
    const visiveis = nosVisiveis();
    const g = new graphology.Graph({ type: "undirected", multi: false });

    visiveis.forEach((i) => {
      const n = estado.dados.nos[i];
      g.addNode(String(i), {
        label: n.t.length > 46 ? `${n.t.slice(0, 44)}…` : n.t,
        size: Math.max(2.5, Math.min(18, 2.5 + Math.sqrt(n.d) * 1.6)),
        color: corDoNo(n),
        x: Math.random(), y: Math.random(),
        indice: i,
      });
    });

    let arestas = 0;
    estado.dados.arestas.forEach(([a, b, peso], idx) => {
      if (!visiveis.has(a) || !visiveis.has(b)) return;
      const ca = String(a), cb = String(b);
      if (g.hasEdge(ca, cb)) return;
      g.addEdge(ca, cb, { size: Math.max(.4, Math.min(3, peso / 4)), color: "rgba(140,155,175,.28)", indice: idx });
      arestas += 1;
    });

    estado.grafo = g;
    posicionar(g);
    renderizar(g);
    $("#contador").textContent =
      `${numero(g.order)} de ${numero(estado.dados.nos.length)} nós · ${numero(arestas)} de ${numero(estado.dados.arestas.length)} relações`;
    desenharLegenda();
    mostrarCarregando(false);
  }, 16);
}

/** Layout inicial: círculo por grupo + ForceAtlas2 em iterações proporcionais ao tamanho. */
function posicionar(g) {
  const grupos = new Map();
  g.forEachNode((no, attr) => {
    const chave = attr.color;
    if (!grupos.has(chave)) grupos.set(chave, []);
    grupos.get(chave).push(no);
  });
  const total = grupos.size || 1;
  let k = 0;
  grupos.forEach((nos) => {
    const ang = (2 * Math.PI * k) / total;
    const cx = Math.cos(ang) * 10, cy = Math.sin(ang) * 10;
    nos.forEach((no, j) => {
      const a = (2 * Math.PI * j) / nos.length;
      const r = 1 + Math.sqrt(nos.length) / 8;
      g.setNodeAttribute(no, "x", cx + Math.cos(a) * r);
      g.setNodeAttribute(no, "y", cy + Math.sin(a) * r);
    });
    k += 1;
  });

  const iteracoes = g.order > 2500 ? 60 : g.order > 1200 ? 120 : 220;
  const fa2 = graphologyLibrary.layoutForceAtlas2;
  fa2.assign(g, { iterations: iteracoes, settings: { ...fa2.inferSettings(g), barnesHutOptimize: g.order > 800, gravity: 1.2, scalingRatio: 12, slowDown: 3 } });

  // separa os nos que ficaram sobrepostos, para os rotulos serem legiveis
  if (g.order <= 2500 && graphologyLibrary.layoutNoverlap) {
    graphologyLibrary.layoutNoverlap.assign(g, {
      maxIterations: 40,
      settings: { margin: 2, ratio: 1.2, gridSize: 20 },
    });
  }
}

function renderizar(g) {
  if (estado.sigma) estado.sigma.kill();
  estado.sigma = new Sigma(g, $("#grafo"), {
    renderLabels: true,
    labelDensity: .25,
    labelGridCellSize: 140,
    labelRenderedSizeThreshold: g.order > 1200 ? 9 : 6,
    labelFont: '"Segoe UI", system-ui, sans-serif',
    labelColor: { color: corDoTema() },
    defaultEdgeColor: "rgba(140,155,175,.28)",
    hideEdgesOnMove: g.order > 900,
    enableEdgeEvents: true,
    zIndex: true,
  });

  estado.sigma.on("clickNode", ({ node }) => selecionarNo(Number(g.getNodeAttribute(node, "indice"))));
  estado.sigma.on("clickEdge", ({ edge }) => selecionarAresta(Number(g.getEdgeAttribute(edge, "indice"))));
  estado.sigma.on("clickStage", () => limparDestaque());
  estado.sigma.on("enterNode", () => { $("#grafo").style.cursor = "pointer"; });
  estado.sigma.on("leaveNode", () => { $("#grafo").style.cursor = "default"; });
}

function corDoTema() {
  return document.body.dataset.tema === "claro" ? "#18202b" : "#c9d3de";
}

function desenharLegenda() {
  const modo = $("#sel-cor").value;
  const cx = $("#legenda");
  cx.innerHTML = "";
  let itens = [];
  if (modo === "tipo") {
    itens = Object.entries(estado.dados.tipos).sort((a, b) => b[1] - a[1]).slice(0, 9)
      .map(([t]) => [t.toLowerCase().replace(/_/g, " "), COR_TIPO[t] || COR_PADRAO]);
  } else if (modo === "pesquisador") {
    itens = estado.dados.pesquisadores.map((p) => [p.nome.split(" ").slice(0, 2).join(" "), corDoPesquisador(p.i)]);
  }
  itens.forEach(([rotulo, cor]) => {
    const s = cria("span");
    const i = cria("i");
    i.style.background = cor;
    s.append(i, document.createTextNode(rotulo));
    cx.appendChild(s);
  });
}

/* ---------------- seleção e detalhes ---------------- */

function vizinhos(indice) {
  const lista = [];
  estado.dados.arestas.forEach(([a, b, peso, desc], idx) => {
    if (a === indice) lista.push({ outro: b, peso, desc, idx });
    else if (b === indice) lista.push({ outro: a, peso, desc, idx });
  });
  return lista.sort((x, y) => y.peso - x.peso);
}

function selecionarNo(indice) {
  const n = estado.dados.nos[indice];
  estado.selecao = { tipo: "no", indice };
  destacar(indice);
  abrirPainel("detalhes");

  const cx = $("#aba-detalhes");
  cx.innerHTML = "";
  cx.appendChild(cria("h2", "titulo-no", n.t));

  const etq = cria("div", "etiquetas");
  etq.appendChild(cria("span", "etiqueta forte", n.y.toLowerCase().replace(/_/g, " ")));
  etq.appendChild(cria("span", "etiqueta", `${numero(n.d)} conexões`));
  etq.appendChild(cria("span", "etiqueta", `${numero(n.f)} menções`));
  if (n.c !== undefined) {
    const b = cria("span", "etiqueta", `comunidade ${n.c}`);
    b.style.cursor = "pointer";
    b.addEventListener("click", () => abrirComunidade(n.c));
    etq.appendChild(b);
  }
  cx.appendChild(etq);

  if (n.p && n.p.length && estado.dados.pesquisadores.length) {
    const bloco = cria("div", "bloco");
    bloco.appendChild(cria("h3", null, "Aparece nos currículos"));
    const et = cria("div", "etiquetas");
    n.p.forEach((i) => {
      const nome = estado.dados.pesquisadores.find((p) => p.i === i)?.nome ?? `#${i}`;
      const s = cria("span", "etiqueta", nome);
      s.style.borderColor = corDoPesquisador(i);
      et.appendChild(s);
    });
    bloco.appendChild(et);
    cx.appendChild(bloco);
  }

  if (n.s) cx.appendChild(cria("p", "descricao", n.s));

  const viz = vizinhos(indice);
  const bloco = cria("div", "bloco");
  bloco.appendChild(cria("h3", null, `Relações (${numero(viz.length)})`));
  const ul = cria("ul", "relacoes");
  viz.slice(0, 40).forEach((v) => {
    const alvo = estado.dados.nos[v.outro];
    const li = cria("li");
    li.innerHTML = `<span class="alvo">${escapa(alvo.t)}</span> <span class="etiqueta">${escapa(alvo.y.toLowerCase())}</span>` +
      (v.desc ? `<span class="texto">${escapa(v.desc)}</span>` : "");
    li.addEventListener("click", () => selecionarNo(v.outro));
    ul.appendChild(li);
  });
  if (!viz.length) ul.appendChild(cria("li", null, "entidade isolada: o texto não a liga a nada"));
  bloco.appendChild(ul);
  cx.appendChild(bloco);
}

function selecionarAresta(idx) {
  const [a, b, peso, desc] = estado.dados.arestas[idx];
  const na = estado.dados.nos[a], nb = estado.dados.nos[b];
  estado.selecao = { tipo: "aresta", indice: idx };
  abrirPainel("detalhes");
  const cx = $("#aba-detalhes");
  cx.innerHTML = "";
  cx.appendChild(cria("h2", "titulo-no", `${na.t} → ${nb.t}`));
  const etq = cria("div", "etiquetas");
  etq.appendChild(cria("span", "etiqueta forte", `força ${peso}`));
  cx.appendChild(etq);
  cx.appendChild(cria("p", "descricao", desc || "sem descrição"));
  const bloco = cria("div", "bloco");
  bloco.appendChild(cria("h3", null, "Extremos"));
  const ul = cria("ul", "relacoes");
  [[a, na], [b, nb]].forEach(([i, n]) => {
    const li = cria("li");
    li.innerHTML = `<span class="alvo">${escapa(n.t)}</span> <span class="etiqueta">${escapa(n.y.toLowerCase())}</span>`;
    li.addEventListener("click", () => selecionarNo(i));
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
  g.forEachNode((no, attr) => {
    g.setNodeAttribute(no, "highlighted", no === foco);
    g.setNodeAttribute(no, "color", perto.has(no) ? (attr.corBase || attr.color) : "rgba(110,118,129,.22)");
    if (!attr.corBase) g.setNodeAttribute(no, "corBase", attr.color);
  });
  g.forEachEdge((aresta, attr, o, d) => {
    g.setEdgeAttribute(aresta, "color", o === foco || d === foco ? "rgba(255,90,54,.85)" : "rgba(140,155,175,.08)");
  });
  estado.sigma.getCamera().animate({ ...estado.sigma.getNodeDisplayData(foco), ratio: .45 }, { duration: 450 });
}

function limparDestaque() {
  const g = estado.grafo;
  if (!g) return;
  g.forEachNode((no, attr) => {
    g.setNodeAttribute(no, "highlighted", false);
    if (attr.corBase) g.setNodeAttribute(no, "color", attr.corBase);
  });
  g.forEachEdge((a) => g.setEdgeAttribute(a, "color", "rgba(140,155,175,.28)"));
}

/* ---------------- comunidades ---------------- */

function desenharComunidades() {
  const cx = $("#aba-comunidades");
  cx.innerHTML = "";
  const coms = estado.dados.comunidades || [];
  if (!coms.length) {
    cx.appendChild(cria("p", "vazio", "esta versão não tem comunidades calculadas"));
    return;
  }
  const niveis = [...new Set(coms.map((c) => c.n))].sort((a, b) => a - b);
  const barra = cria("div", "filtro-nivel");
  let nivel = niveis[0];
  const lista = cria("ul", "lista-comunidades");

  const pintar = () => {
    lista.innerHTML = "";
    coms.filter((c) => c.n === nivel).sort((a, b) => b.tam - a.tam).slice(0, 120).forEach((c) => {
      const li = cria("li");
      li.appendChild(cria("h4", null, c.t || `Comunidade ${c.id}`));
      li.appendChild(cria("p", null, `${numero(c.tam)} entidades${c.nota ? ` · nota ${c.nota.toFixed(1)}` : ""}`));
      if (c.s) li.appendChild(cria("p", null, `${c.s.slice(0, 160)}…`));
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
    cx.appendChild(cria("p", "vazio", `sem relatório para a comunidade ${id}`));
    return;
  }
  cx.appendChild(cria("h2", "titulo-no", r.t));
  const etq = cria("div", "etiquetas");
  etq.appendChild(cria("span", "etiqueta forte", `nível ${r.n}`));
  if (r.nota) etq.appendChild(cria("span", "etiqueta", `nota ${r.nota.toFixed(1)}`));
  cx.appendChild(etq);
  const corpo = cria("div", "relatorio");
  corpo.innerHTML = escapa(r.c)
    .replace(/^#+\s*(.+)$/gm, "<h3>$1</h3>")
    .replace(/\n{2,}/g, "</p><p>")
    .replace(/^/, "<p>") + "</p>";
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
      bloco.appendChild(cria("h3", null, `${c.metodo} · ${c.custo ? `US$ ${c.custo}` : ""}`));
      bloco.appendChild(cria("h2", "titulo-no", c.pergunta));
      const corpo = cria("div", "relatorio");
      corpo.innerHTML = escapa(c.resposta).replace(/\n{2,}/g, "</p><p>").replace(/^/, "<p>") + "</p>";
      bloco.appendChild(corpo);
      cx.appendChild(bloco);
    });
  } catch {
    cx.innerHTML = '<p class="vazio">As consultas fixas ainda não foram executadas para esta versão. ' +
      'Elas são geradas uma vez, salvas em arquivo e exibidas aqui — consultar ao vivo custaria tokens a cada pergunta.</p>';
  }
}

/* ---------------- interface ---------------- */

function abrirPainel(aba) {
  document.querySelectorAll(".aba").forEach((b) => b.classList.toggle("ativa", b.dataset.aba === aba));
  document.querySelectorAll(".aba-conteudo").forEach((c) => c.classList.toggle("ativa", c.id === `aba-${aba}`));
  if (window.matchMedia("(max-width: 1100px)").matches) $("#painel").classList.add("aberto");
}

function mostrarCarregando(ativo, texto) {
  const el = $("#carregando");
  el.classList.toggle("ativo", ativo);
  if (texto) el.lastChild.textContent = ` ${texto}`;
}

function pararAnimacao() {
  estado.animando = false;
  if (estado.quadro) cancelAnimationFrame(estado.quadro);
  estado.quadro = null;
  $("#estado-layout").textContent = "";
}

function animar() {
  const fa2 = graphologyLibrary.layoutForceAtlas2;
  const config = { ...fa2.inferSettings(estado.grafo), barnesHutOptimize: estado.grafo.order > 800, gravity: 1.2, scalingRatio: 12, slowDown: 3 };
  const passo = () => {
    if (!estado.animando) return;
    fa2.assign(estado.grafo, { iterations: 2, settings: config });
    estado.quadro = requestAnimationFrame(passo);
  };
  $("#estado-layout").textContent = "layout em movimento";
  estado.quadro = requestAnimationFrame(passo);
}

function ligarEventos() {
  $("#sel-versao").addEventListener("change", (e) => carregarVersao(e.target.value));
  $("#sel-cor").addEventListener("change", atualizarGrafo);

  $("#chk-animar").addEventListener("change", (e) => {
    estado.animando = e.target.checked;
    if (estado.animando) animar(); else pararAnimacao();
  });

  $("#grau-min").addEventListener("input", (e) => {
    $("#valor-grau").textContent = e.target.value;
    estado.filtros.grauMin = Number(e.target.value);
  });
  $("#grau-min").addEventListener("change", atualizarGrafo);

  $("#limite").addEventListener("input", (e) => {
    $("#valor-limite").textContent = e.target.value;
    estado.filtros.limite = Number(e.target.value);
  });
  $("#limite").addEventListener("change", atualizarGrafo);

  $("#chk-isoladas").addEventListener("change", (e) => {
    estado.filtros.isoladas = e.target.checked;
    atualizarGrafo();
  });

  $("#btn-limpar").addEventListener("click", () => {
    estado.filtros.pesquisadores = new Set(estado.dados.pesquisadores.map((p) => p.i));
    estado.filtros.tipos = new Set(Object.keys(estado.dados.tipos));
    estado.filtros.busca = "";
    $("#busca").value = "";
    $("#chk-isoladas").checked = false;
    estado.filtros.isoladas = false;
    document.querySelectorAll(".lista li").forEach((li) => li.classList.remove("desmarcado"));
    atualizarGrafo();
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
    if (e.key === "Escape") { $("#sugestoes").hidden = true; }
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
    const claro = document.body.dataset.tema === "claro";
    document.body.dataset.tema = claro ? "escuro" : "claro";
    if (estado.sigma) {
      estado.sigma.setSetting("labelColor", { color: corDoTema() });
      estado.sigma.refresh();
    }
  });

  document.querySelectorAll(".aba").forEach((b) => {
    if (b.dataset.aba) b.addEventListener("click", () => abrirPainel(b.dataset.aba));
  });
  $("#btn-menu").addEventListener("click", () => $("#lateral").classList.toggle("aberta"));
  $("#btn-painel").addEventListener("click", () => $("#painel").classList.toggle("aberto"));
  $("#btn-fechar-painel").addEventListener("click", () => $("#painel").classList.remove("aberto"));

  window.addEventListener("resize", () => {
    ajustarLayout();
    if (estado.sigma) estado.sigma.refresh();
  });
  // o evento resize nao dispara em toda mudanca de largura (emulacao, rotacao):
  // a media query avisa sempre que cruza o limite.
  window.matchMedia("(max-width: 860px)").addEventListener("change", ajustarLayout);
  ajustarLayout();
}

/** Em tela estreita a barra superior nao cabe: o seletor de cor vai para a lateral. */
function ajustarLayout() {
  const campo = $("#campo-cor");
  const estreito = window.matchMedia("(max-width: 860px)").matches;
  const destino = estreito ? $("#extras-lateral") : $(".controles");
  if (campo.parentElement === destino) return;
  if (estreito) destino.appendChild(campo);
  else destino.insertBefore(campo, $(".alternar"));
}


function sugerir(texto) {
  const ul = $("#sugestoes");
  const termo = texto.trim().toLowerCase();
  ul.innerHTML = "";
  if (termo.length < 2) { ul.hidden = true; return; }
  const achados = [];
  for (let i = 0; i < estado.dados.nos.length && achados.length < 30; i += 1) {
    if (estado.dados.nos[i].t.toLowerCase().includes(termo)) achados.push(i);
  }
  achados.sort((a, b) => estado.dados.nos[b].d - estado.dados.nos[a].d);
  achados.slice(0, 12).forEach((i) => {
    const n = estado.dados.nos[i];
    const li = cria("li");
    li.innerHTML = `${escapa(n.t)} <small>${escapa(n.y.toLowerCase())} · ${numero(n.d)}</small>`;
    li.addEventListener("click", () => {
      ul.hidden = true;
      if (!estado.grafo.hasNode(String(i))) {
        estado.filtros.busca = n.t;
        atualizarGrafo();
        setTimeout(() => selecionarNo(i), 400);
      } else {
        selecionarNo(i);
      }
    });
    ul.appendChild(li);
  });
  ul.hidden = achados.length === 0;
}

function baixarImagem() {
  const tela = $("#grafo").querySelector("canvas.sigma-nodes");
  if (!tela) return;
  const canvases = [...$("#grafo").querySelectorAll("canvas")];
  const saida = document.createElement("canvas");
  saida.width = tela.width;
  saida.height = tela.height;
  const ctx = saida.getContext("2d");
  ctx.fillStyle = getComputedStyle(document.body).getPropertyValue("--fundo");
  ctx.fillRect(0, 0, saida.width, saida.height);
  canvases.forEach((c) => ctx.drawImage(c, 0, 0, saida.width, saida.height));
  const link = document.createElement("a");
  link.download = `grafo-${estado.dados.meta.versao}.png`;
  link.href = saida.toDataURL("image/png");
  link.click();
}

iniciar().catch((e) => {
  mostrarCarregando(false);
  $("#grafo").innerHTML = `<p style="padding:24px;color:#ff7b72">Falha ao carregar: ${escapa(e.message)}.
    Rode <code>python scripts/exportar_site.py</code> e sirva a pasta com <code>python -m http.server</code>.</p>`;
});
