/* Tour guiado do visualizador, inspirado no onboarding do viewer do Databricks.
   Nao bloqueia a pagina: nada escurece, so um contorno laranja marca a parte explicada e
   um balao ao lado traz o texto, o contador e os botoes. Da para clicar no grafo durante
   o tour. Teclado: setas avancam e voltam, Esc fecha. Abre sozinho so na primeira visita.
   Usa as funcoes e o estado de app.js (scripts classicos compartilham o escopo global). */

const CHAVE_TOUR = "tour-visto";

/**
 * Passos. `alvo` e um seletor (o primeiro visivel vence); `antes` prepara a tela
 * (abre a visao certa, a gaveta no celular). Sem alvo visivel, o balao fica no centro.
 */
const PASSOS_TOUR = [
  {
    alvo: ".palco",
    titulo: "O grafo dos currículos",
    texto: "Tudo aqui foi extraído do texto de 8 currículos Lattes pelo GraphRAG: cada bolinha é uma " +
      "entidade (pessoa, publicação, projeto…) e cada linha é uma relação que o texto afirma.",
    antes: () => { if (estado.modo !== "geral") irParaGeral(); },
  },
  {
    alvo: "#metricas",
    titulo: "Números da versão",
    texto: "Quantos currículos, entidades, relações e comunidades esta indexação produziu, e quanto " +
      "custou na Azure. Passe o mouse sobre cada número para ler o que ele conta.",
  },
  {
    alvo: "#sel-versao",
    painel: ".campo",
    titulo: "Versões do experimento",
    texto: "Cada versão é uma indexação diferente (modelo, prompt, formato do texto, número de " +
      "currículos). Trocar aqui permite comparar o efeito de cada mudança.",
  },
  {
    alvo: "#lista-pesquisadores",
    gaveta: "lateral",
    titulo: "Os pesquisadores",
    texto: "Os currículos indexados, com quantas entidades cada um gerou. Clique em um nome para " +
      "abrir a rede daquela pessoa.",
  },
  {
    alvo: ".palco",
    titulo: "Visão geral",
    texto: "Os 8 pesquisadores em círculo. A espessura da linha é o número de produções ligadas aos " +
      "dois. Clique numa linha para ver quais são; clique num nome para abrir a rede.",
    antes: () => { if (estado.modo !== "geral") irParaGeral(); },
  },
  {
    alvo: ".palco",
    titulo: "A rede de uma pessoa",
    texto: "No centro, a pessoa; em volta, os vizinhos em caixas por tipo. Arraste um nó para mudar " +
      "de lugar, ou pegue a caixa pelo título para levar o grupo inteiro. A roda do mouse aproxima.",
    antes: () => {
      const p = [...estado.dados.pesquisadores].sort((a, b) => b.grau - a.grau)[0];
      if (p && !(estado.modo === "radial" && estado.foco === p.no)) irParaPesquisador(p.i);
    },
  },
  {
    alvo: "#btn-voltar",
    titulo: "Voltar",
    texto: "Cada clique num nó centraliza aquela entidade. O Voltar (ou Alt+←) desfaz o passo e " +
      "devolve a visão anterior.",
  },
  {
    alvo: "#campo-cor",
    gaveta: "lateral",
    titulo: "O que a cor mostra",
    texto: "Por currículo de origem (tons claros são pontes: entidades citadas em 2+ currículos), " +
      "por tipo de entidade ou por comunidade. A legenda no canto do grafo mostra só o que está na tela.",
  },
  {
    alvo: "#lista-tipos",
    gaveta: "lateral",
    titulo: "Filtrar por tipo",
    texto: "Clique num tipo para esconder ou mostrar. Alt+clique deixa só aquele tipo.",
  },
  {
    alvo: "#painel",
    gaveta: "painel",
    titulo: "Painel de detalhes",
    texto: "O que o texto diz sobre a entidade selecionada, as métricas, os vizinhos agrupados por tipo e " +
      "em quais currículos ela aparece. As abas trazem as comunidades (com relatórios) e as consultas.",
  },
  {
    alvo: '.modo[data-modo="livre"]',
    gaveta: "lateral",
    titulo: "Exploração livre",
    texto: "O grafo inteiro, organizado por força (ForceAtlas2), com filtros de conexões mínimas e " +
      "de quantidade de nós.",
  },
  {
    alvo: "#btn-conceitos",
    titulo: "Ajuda",
    texto: "Este botão reabre o tour e o glossário com o significado de cada termo (entidade, grau, " +
      "comunidade, pontes…). Bom proveito!",
  },
];

const tour = {
  passo: -1,
  anel: null,
  balao: null,
  alvoAtual: null,
  quadro: null,
  ultimoRet: "",
};

function iniciarTour() {
  fecharMenuAjuda();
  if (!tour.balao) montarTour();
  document.body.classList.add("em-tour");
  irParaPasso(0);
  document.addEventListener("keydown", teclaTour, true);
  acompanharAlvo();
}

function montarTour() {
  tour.anel = document.createElement("div");
  tour.anel.className = "tour-anel";
  tour.anel.hidden = true;
  tour.balao = document.createElement("div");
  tour.balao.className = "tour-balao";
  tour.balao.setAttribute("role", "dialog");
  tour.balao.setAttribute("aria-live", "polite");
  tour.balao.innerHTML =
    '<h3 class="tour-titulo"></h3><p class="tour-texto"></p>' +
    '<div class="tour-rodape"><span class="tour-conta"></span>' +
    '<button type="button" class="tour-pular">Pular</button>' +
    '<button type="button" class="tour-anterior" aria-label="Passo anterior">‹</button>' +
    '<button type="button" class="tour-proximo">Próximo</button></div>';
  tour.balao.querySelector(".tour-pular").addEventListener("click", () => fecharTour());
  tour.balao.querySelector(".tour-anterior").addEventListener("click", () => irParaPasso(tour.passo - 1));
  tour.balao.querySelector(".tour-proximo").addEventListener("click", () => {
    if (tour.passo >= PASSOS_TOUR.length - 1) fecharTour();
    else irParaPasso(tour.passo + 1);
  });
  document.body.append(tour.anel, tour.balao);
}

function irParaPasso(k) {
  if (k < 0 || k >= PASSOS_TOUR.length) return;
  const p = PASSOS_TOUR[k];
  tour.passo = k;
  try { if (p.antes) p.antes(); } catch (e) { console.warn("tour:", e); }
  abrirGavetaDoPasso(p);

  const b = tour.balao;
  b.querySelector(".tour-titulo").textContent = p.titulo;
  b.querySelector(".tour-texto").textContent = p.texto;
  b.querySelector(".tour-conta").textContent = `${k + 1} / ${PASSOS_TOUR.length}`;
  b.querySelector(".tour-anterior").hidden = k === 0;
  b.querySelector(".tour-proximo").textContent = k === PASSOS_TOUR.length - 1 ? "Concluir" : "Próximo";
  b.classList.remove("tour-entra");
  void b.offsetWidth;
  b.classList.add("tour-entra");
  tour.ultimoRet = "";
  // a visao nova (radial, gaveta) leva um instante para existir e ter tamanho
  setTimeout(() => {
    const el = alvoDoPasso(p);
    // alvo dentro de uma coluna com rolagem: traz para a vista
    if (el && el.closest(".lateral, .painel") && el !== $("#painel")) {
      el.scrollIntoView({ block: "nearest", behavior: "smooth" });
    }
    posicionarTour();
  }, 30);
  b.querySelector(".tour-proximo").focus({ preventScroll: true });
}

/** No celular a lateral e o painel sao gavetas: abre a que tem o alvo e fecha a outra. */
function abrirGavetaDoPasso(p) {
  const lateralGaveta = window.matchMedia("(max-width: 860px)").matches;
  const painelGaveta = window.matchMedia("(max-width: 1100px)").matches;
  if (lateralGaveta) $("#lateral").classList.toggle("aberta", p.gaveta === "lateral");
  if (painelGaveta) $("#painel").classList.toggle("aberto", p.gaveta === "painel");
}

function alvoDoPasso(p) {
  const candidatos = [...document.querySelectorAll(p.alvo)];
  let el = candidatos.find((c) => {
    const r = c.getBoundingClientRect();
    return r.width > 0 && r.height > 0 && !c.closest("[hidden]");
  });
  if (el && p.painel) el = el.closest(p.painel) || el;
  return el || null;
}

function posicionarTour() {
  if (tour.passo < 0) return;
  const p = PASSOS_TOUR[tour.passo];
  const el = alvoDoPasso(p);
  tour.alvoAtual = el;
  const vw = window.innerWidth;
  const vh = window.innerHeight;
  const b = tour.balao;
  const bw = b.offsetWidth;
  const bh = b.offsetHeight;
  const M = 12;
  let x;
  let y;

  const r = el ? el.getBoundingClientRect() : null;
  const visivel = r && r.bottom > 0 && r.right > 0 && r.top < vh && r.left < vw;
  if (!visivel) {
    tour.anel.hidden = true;
    x = (vw - bw) / 2;
    y = vh - bh - 24;
  } else {
    const raio = parseFloat(getComputedStyle(el).borderTopLeftRadius) || 8;
    if (tour.anel.hidden) tour.anel.style.transition = "none";
    Object.assign(tour.anel.style, {
      left: `${r.left - 4}px`, top: `${r.top - 4}px`,
      width: `${r.width + 8}px`, height: `${r.height + 8}px`,
      borderRadius: `${raio + 4}px`,
    });
    tour.anel.hidden = false;
    if (tour.anel.style.transition) { void tour.anel.offsetWidth; tour.anel.style.transition = ""; }
    if (r.width > vw * 0.45 && r.height > vh * 0.45) {
      // alvo grande (o palco): o balao fica dentro dele, no canto, como no Databricks
      x = r.left + 18;
      y = r.top + 18;
    } else if (el.closest(".barra")) {
      // cabecalho: abaixo do alvo, para nao cobrir os outros controles
      x = r.left;
      y = r.bottom + M + 4;
    } else if (r.right + M + bw <= vw) {
      x = r.right + M; y = r.top;
    } else if (r.left - M - bw >= 0) {
      x = r.left - M - bw; y = r.top;
    } else if (r.bottom + M + bh <= vh) {
      x = r.left; y = r.bottom + M;
    } else {
      x = r.left; y = r.top - M - bh;
    }
  }
  x = Math.max(M, Math.min(x, vw - bw - M));
  y = Math.max(M, Math.min(y, vh - bh - M));
  // na primeira vez o balao esta fora da tela: aparece no lugar, sem deslizar ate ele
  const primeira = !b.style.left || b.style.left === "-9999px";
  if (primeira) b.style.transition = "none";
  b.style.left = `${Math.round(x)}px`;
  b.style.top = `${Math.round(y)}px`;
  if (primeira) { void b.offsetWidth; b.style.transition = ""; }
}

/** O alvo pode mudar de lugar (gaveta abrindo, divisor arrastado, janela redimensionada). */
function acompanharAlvo() {
  cancelAnimationFrame(tour.quadro);
  const laco = () => {
    if (tour.passo < 0) return;
    const el = tour.alvoAtual;
    const r = el ? el.getBoundingClientRect() : null;
    const chave = r ? `${r.left|0},${r.top|0},${r.width|0},${r.height|0},${innerWidth},${innerHeight}` : `-${innerWidth}`;
    if (chave !== tour.ultimoRet || (el && !el.isConnected)) {
      tour.ultimoRet = chave;
      posicionarTour();
    }
    tour.quadro = requestAnimationFrame(laco);
  };
  tour.quadro = requestAnimationFrame(laco);
}

function teclaTour(e) {
  if (tour.passo < 0) return;
  const campo = e.target.closest && e.target.closest("input, select, textarea");
  if (e.key === "Escape") { e.preventDefault(); fecharTour(); return; }
  if (campo || e.altKey || e.ctrlKey || e.metaKey) return;
  if (e.key === "ArrowRight") {
    e.preventDefault();
    if (tour.passo < PASSOS_TOUR.length - 1) irParaPasso(tour.passo + 1);
  } else if (e.key === "ArrowLeft") {
    e.preventDefault();
    irParaPasso(tour.passo - 1);
  }
}

function fecharTour() {
  if (tour.passo < 0) return;
  tour.passo = -1;
  cancelAnimationFrame(tour.quadro);
  tour.anel.hidden = true;
  tour.balao.classList.remove("tour-entra");
  tour.balao.style.left = "-9999px";
  document.body.classList.remove("em-tour");
  document.removeEventListener("keydown", teclaTour, true);
  if (window.matchMedia("(max-width: 1100px)").matches) $("#painel").classList.remove("aberto");
  if (window.matchMedia("(max-width: 860px)").matches) $("#lateral").classList.remove("aberta");
  try { localStorage.setItem(CHAVE_TOUR, "1"); } catch (e) { /* navegador sem armazenamento */ }
}

/* ---------------- menu do botao "?" ---------------- */

function ligarMenuAjuda() {
  const botao = $("#btn-conceitos");
  const menu = $("#menu-ajuda");
  botao.addEventListener("click", (e) => {
    e.stopPropagation();
    const abrir = menu.hidden;
    menu.hidden = !abrir;
    botao.setAttribute("aria-expanded", String(abrir));
    if (abrir) menu.querySelector("button").focus({ preventScroll: true });
  });
  $("#menu-tour").addEventListener("click", iniciarTour);
  $("#menu-conceitos").addEventListener("click", () => { fecharMenuAjuda(); $("#conceitos").showModal(); });
  document.addEventListener("click", (e) => { if (!e.target.closest("#menu-ajuda")) fecharMenuAjuda(); });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") fecharMenuAjuda(); });
}

function fecharMenuAjuda() {
  const menu = $("#menu-ajuda");
  if (!menu || menu.hidden) return;
  menu.hidden = true;
  $("#btn-conceitos").setAttribute("aria-expanded", "false");
}

/** Chamado por app.js depois que a primeira versao carrega. */
function talvezIniciarTour() {
  let visto = false;
  try { visto = localStorage.getItem(CHAVE_TOUR) === "1"; } catch (e) { visto = false; }
  if (!visto) setTimeout(iniciarTour, 900);
}
