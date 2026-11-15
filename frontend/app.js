"use strict";

/* ===================================================================================================
   Utilidades
   =================================================================================================== */

const $ = (seletor, raiz = document) => raiz.querySelector(seletor);

// Cria elementos sem usar innerHTML: tudo que vem de usuários, do modelo ou da base entra na página como texto,
// nunca como HTML (os locais cadastrados aparecem para todos os visitantes).
function h(tag, atributos = {}, ...filhos) {
  const el = document.createElement(tag);
  for (const [chave, valor] of Object.entries(atributos)) {
    if (valor === false || valor == null) continue;
    if (chave === "class") el.className = valor;
    else el.setAttribute(chave, valor === true ? "" : String(valor));
  }
  for (const filho of filhos.flat(Infinity)) {
    if (filho == null || filho === false) continue;
    el.append(filho); // strings viram nós de texto
  }
  return el;
}

const NS_SVG = "http://www.w3.org/2000/svg";
function icone(nome, classe = "") {
  const svg = document.createElementNS(NS_SVG, "svg");
  svg.setAttribute("class", `icone ${classe}`.trim());
  svg.setAttribute("aria-hidden", "true");
  const uso = document.createElementNS(NS_SVG, "use");
  uso.setAttribute("href", `#i-${nome}`);
  svg.append(uso);
  return svg;
}

function iconeInfinito() {
  const svg = document.createElementNS(NS_SVG, "svg");
  const uso = document.createElementNS(NS_SVG, "use");
  uso.setAttribute("href", "#i-infinito");
  svg.append(uso);
  return svg;
}

// localStorage pode falhar (navegação privada, bloqueio): a página funciona sem ele.
const guardar = (chave, valor) => { try { localStorage.setItem(chave, valor); } catch (_) { /* ignora */ } };
const ler = (chave) => { try { return localStorage.getItem(chave); } catch (_) { return null; } };

const digitos = (texto) => String(texto).replace(/\D/g, "");
const hrefTel = (numero) => `tel:${digitos(numero)}`;
function hrefZap(numero) {
  let d = digitos(numero);
  if (d.startsWith("0")) d = d.slice(1);
  if (!d.startsWith("55")) d = `55${d}`;
  return `https://wa.me/${d}`;
}
function dataBR(iso) {
  if (!iso) return "";
  const [ano, mes, dia] = iso.split("-");
  return `${dia}/${mes}/${ano}`;
}

function dataHoraBR(iso) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const n2 = (n) => String(n).padStart(2, "0");
  return `${n2(d.getDate())}/${n2(d.getMonth() + 1)}/${d.getFullYear()} ${n2(d.getHours())}:${n2(d.getMinutes())}`;
}

function anunciar(texto) {
  const el = $("#anuncios");
  el.textContent = "";
  setTimeout(() => { el.textContent = texto; }, 60);
}

async function erroDaApi(resposta) {
  let detalhe = "";
  try {
    const corpo = await resposta.json();
    if (typeof corpo.detail === "string") detalhe = corpo.detail;
  } catch (_) { /* corpo sem JSON */ }
  const erro = new Error(detalhe || `O servidor respondeu com erro ${resposta.status}.`);
  erro.status = resposta.status;
  return erro;
}

function mensagemDeErro(erro) {
  if (erro.name === "AbortError") return "A resposta foi cancelada ou demorou mais do que o esperado.";
  if (erro instanceof TypeError) return "Não consegui falar com o servidor. Verifique se o DivergentIA está rodando neste computador.";
  return erro.message;
}

const estaDesativado = (botao) => botao.getAttribute("aria-disabled") === "true";
const MUNICIPIOS_COM_DADOS = ["Vitória", "Serra", "Vila Velha"];

// Rolagem suave só quando a pessoa não pediu menos movimento (modo calmo ou preferência do sistema).
const movimentoReduzido = () => document.documentElement.dataset.calmo === "1"
  || (window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches);
const comportamentoRolagem = () => (movimentoReduzido() ? "auto" : "smooth");

/* ===================================================================================================
   Markdown leve para as respostas da IA
   A IA escreve com **negrito**, listas numeradas e tópicos. Aqui isso vira elementos de verdade (<strong>, <ol>,
   <ul>...), sempre criados nó a nó: o texto nunca entra como HTML, então nada que venha do modelo vira código.
   =================================================================================================== */

const RE_INLINE = new RegExp([
  String.raw`\*\*[^*\n]+?\*\*`,                     // **negrito**
  String.raw`__[^_\n]+?__`,                         // __negrito__
  String.raw`\x60[^\x60\n]+\x60`,                   // `código`
  String.raw`\[[^\]\n]+\]\(https?:\/\/[^\s)]+\)`,    // [texto](https://...)
  String.raw`https?:\/\/[^\s<>()]*[^\s<>().,;:!?"']`, // https://... solto
  String.raw`\(\d{2}\)\s?\d{4,5}-?\d{4}`,           // (27) 3198-3300 -> link para ligar
  String.raw`0800[\s-]?\d{3}[\s-]?\d{4}`,           // 0800 ...
  String.raw`\*[^*\s][^*\n]*?\*`,                   // *itálico*
].join("|"), "g");

function linkSeguro(url, rotulo) {
  if (!/^https?:\/\//i.test(url)) return rotulo;
  return h("a", { href: url, target: "_blank", rel: "noopener noreferrer" }, rotulo,
    h("span", { class: "sr-only" }, " (abre em nova aba)"));
}

function mdInline(texto) {
  const partes = [];
  let ultimo = 0;
  const solto = (t) => t.replace(/\*\*/g, ""); // "**" sem par (resposta cortada) não aparece na tela
  for (const m of texto.matchAll(RE_INLINE)) {
    const t = m[0];
    if (m.index > ultimo) partes.push(solto(texto.slice(ultimo, m.index)));
    if (t.startsWith("**") || t.startsWith("__")) partes.push(h("strong", {}, mdInline(t.slice(2, -2))));
    else if (t.startsWith("`")) partes.push(h("code", {}, t.slice(1, -1)));
    else if (t.startsWith("[")) { const [, rotulo, url] = t.match(/^\[([^\]]+)\]\((.+)\)$/); partes.push(linkSeguro(url, rotulo)); }
    else if (/^https?:/i.test(t)) partes.push(linkSeguro(t, t));
    else if (t.startsWith("*")) partes.push(h("em", {}, t.slice(1, -1)));
    else partes.push(h("a", { href: hrefTel(t), class: "md-fone" }, t, h("span", { class: "sr-only" }, " (ligar)")));
    ultimo = m.index + t.length;
  }
  if (ultimo < texto.length) partes.push(solto(texto.slice(ultimo)));
  return partes;
}

function renderMarkdown(texto) {
  const raiz = h("div", { class: "md" });
  let paragrafo = null; // <p> aberto (linhas seguidas viram <br>)
  let lista = null;     // <ol>/<ul> de primeiro nível aberta
  let sublista = null;  // lista dentro do último item
  const fecharListas = () => { lista = null; sublista = null; };
  for (const bruta of String(texto || "").replace(/\r\n?/g, "\n").split("\n")) {
    const linha = bruta.replace(/\s+$/, "");
    if (!linha.trim()) { paragrafo = null; continue; } // linha em branco fecha o parágrafo (a lista continua)
    const recuo = linha.match(/^\s*/)[0].length;
    const conteudo = linha.trim();
    const titulo = conteudo.match(/^#{1,6}\s+(.+)$/);
    const topico = conteudo.match(/^[-*•]\s+(.+)$/);
    const numero = conteudo.match(/^(\d{1,3})[.)]\s+(.+)$/);
    if (/^(-{3,}|\*{3,}|_{3,})$/.test(conteudo)) { paragrafo = null; fecharListas(); continue; }
    if (titulo) {
      paragrafo = null; fecharListas();
      raiz.append(h("p", { class: "md__titulo" }, mdInline(titulo[1])));
      continue;
    }
    if (topico || numero) {
      paragrafo = null;
      const tag = numero ? "OL" : "UL";
      const item = h("li", {}, mdInline(numero ? numero[2] : topico[1]));
      if (recuo >= 2 && lista && lista.lastElementChild) {
        if (!sublista || sublista.tagName !== tag) { sublista = h(tag.toLowerCase()); lista.lastElementChild.append(sublista); }
        sublista.append(item);
      } else {
        if (!lista || lista.tagName !== tag) {
          lista = h(tag.toLowerCase(), numero && numero[1] !== "1" ? { start: numero[1] } : {});
          raiz.append(lista);
        }
        sublista = null;
        lista.append(item);
      }
      continue;
    }
    if (lista && recuo >= 2) { // continuação de um item de lista
      ((sublista && sublista.lastElementChild) || lista.lastElementChild).append(h("br"), ...mdInline(conteudo));
      continue;
    }
    fecharListas();
    if (paragrafo) paragrafo.append(h("br"), ...mdInline(conteudo));
    else { paragrafo = h("p", {}, mdInline(conteudo)); raiz.append(paragrafo); }
  }
  return raiz;
}

/* ===================================================================================================
   Estado
   =================================================================================================== */

const estado = {
  historico: [],          // [{ papel: "usuario" | "assistente", conteudo }]
  roteiro: null,          // último roteiro devolvido pelo servidor
  contatos: new Map(),    // id -> contato (cartões vindos da base verificada)
  fontes: [],
  apoio: [],              // ids dos contatos de "Quem pode ajudar agora"
  feitos: new Set(),      // passos marcados como concluídos (chave: fonte|título)
  carregando: false,
  ultimaMensagem: "",
  controle: null,
  visao: "conversa",      // no celular: "conversa" ou "roteiro"
  conversaId: null,       // só existe pra quem está logado (ver GET /chat/conversas)
};

/* ===================================================================================================
   Acessibilidade: tamanho do texto, alto contraste, espaçamento, modo calmo
   =================================================================================================== */

const TAMANHOS = [100, 112.5, 125, 150, 175]; // % do tamanho base do navegador
const PREFS_PADRAO = { tamanho: 1, contraste: false, espaco: false, calmo: false };
let prefs = { ...PREFS_PADRAO };

function carregarPrefs() {
  try {
    const bruto = ler("dv-prefs");
    if (bruto) Object.assign(prefs, JSON.parse(bruto));
    else if (window.matchMedia && window.matchMedia("(prefers-contrast: more)").matches) prefs.contraste = true;
  } catch (_) { /* usa o padrão */ }
  if (!Number.isInteger(prefs.tamanho) || prefs.tamanho < 0 || prefs.tamanho >= TAMANHOS.length) prefs.tamanho = PREFS_PADRAO.tamanho;
}

function aplicarPrefs() {
  const raiz = document.documentElement;
  raiz.style.fontSize = `${TAMANHOS[prefs.tamanho]}%`;
  raiz.dataset.contraste = prefs.contraste ? "alto" : "";
  raiz.dataset.espaco = prefs.espaco ? "1" : "";
  raiz.dataset.calmo = prefs.calmo ? "1" : "";
  for (const atributo of ["contraste", "espaco", "calmo"]) if (!raiz.dataset[atributo]) delete raiz.dataset[atributo];
  $("#a11y-tamanho").textContent = `${TAMANHOS[prefs.tamanho]}%`;
  $("#a11y-menos").setAttribute("aria-disabled", String(prefs.tamanho === 0));
  $("#a11y-mais").setAttribute("aria-disabled", String(prefs.tamanho === TAMANHOS.length - 1));
  $("#sw-contraste").setAttribute("aria-checked", String(prefs.contraste));
  $("#sw-espaco").setAttribute("aria-checked", String(prefs.espaco));
  $("#sw-calmo").setAttribute("aria-checked", String(prefs.calmo));
  guardar("dv-prefs", JSON.stringify(prefs));
}

function alternarMenuA11y(abrir) {
  const menu = $("#menu-a11y");
  const botao = $("#btn-a11y");
  const vaiAbrir = abrir ?? menu.hidden;
  menu.hidden = !vaiAbrir;
  botao.setAttribute("aria-expanded", String(vaiAbrir));
  if (vaiAbrir) $("#a11y-mais").focus();
}

function ligarAcessibilidade() {
  $("#btn-a11y").addEventListener("click", () => alternarMenuA11y());
  $("#a11y-menos").addEventListener("click", () => { if (prefs.tamanho > 0) { prefs.tamanho -= 1; aplicarPrefs(); } });
  $("#a11y-mais").addEventListener("click", () => { if (prefs.tamanho < TAMANHOS.length - 1) { prefs.tamanho += 1; aplicarPrefs(); } });
  for (const [id, chave] of [["#sw-contraste", "contraste"], ["#sw-espaco", "espaco"], ["#sw-calmo", "calmo"]]) {
    $(id).addEventListener("click", () => { prefs[chave] = !prefs[chave]; aplicarPrefs(); });
  }
  $("#a11y-reset").addEventListener("click", () => { prefs = { ...PREFS_PADRAO }; aplicarPrefs(); });
  document.addEventListener("click", (e) => {
    if (!$("#menu-a11y").hidden && !e.target.closest(".a11y")) alternarMenuA11y(false);
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !$("#menu-a11y").hidden) { alternarMenuA11y(false); $("#btn-a11y").focus(); }
  });
}

/* ===================================================================================================
   Contatos: cartões (vindos da base verificada) e diálogo de detalhes
   =================================================================================================== */

function linkExterno(link) {
  return h("li", {}, h("a", { class: "link-ext", href: link.url, target: "_blank", rel: "noopener noreferrer" },
    link.titulo, icone("externo"), h("span", { class: "sr-only" }, " (abre em nova aba)")));
}

function botaoFone(t) {
  return h("a", { class: "btn-fone", href: hrefTel(t.numero) }, icone("fone"),
    h("span", { class: "btn-fone__t" }, h("b", {}, t.numero), t.rotulo ? h("small", {}, t.rotulo) : null),
    h("span", { class: "sr-only" }, " (ligar)"));
}

function unidadesBloco(contato) {
  if (!contato.unidades || !contato.unidades.length) return null;
  const destaque = contato.unidade_destaque;
  const itens = [...contato.unidades].sort((a, b) => (b.nome === destaque) - (a.nome === destaque));
  const lista = h("ul", {}, itens.map((u) => h("li", { class: u.nome === destaque ? "destaque" : "" },
    h("strong", {}, u.nome, u.nome === destaque ? " · seu bairro" : ""),
    u.endereco ? h("small", {}, u.endereco) : null,
    u.bairros ? h("small", {}, `Atende: ${u.bairros}`) : null,
    h("span", {}, u.telefones.map((tel, i) => [i ? " · " : "", h("a", { href: hrefTel(tel) }, tel)])))));
  return h("details", { class: "unidades", open: destaque ? true : null },
    h("summary", {}, `Ver as ${contato.unidades.length} unidades (endereço e telefone)`), lista);
}

function contatoCard(c, opcoes = {}) {
  const dados = [];
  if (c.endereco) dados.push(["pino", "Endereço", c.endereco]);
  if (c.horario) dados.push(["relogio", "Horário", c.horario]);
  if (c.email) dados.push(["email", "E-mail", h("a", { href: `mailto:${c.email}` }, c.email)]);
  if (c.site) {
    dados.push(["globo", "Site", h("a", { href: c.site, target: "_blank", rel: "noopener noreferrer" },
      "Página oficial", h("span", { class: "sr-only" }, " (abre em nova aba)"))]);
  }
  const destaque = c.unidade_destaque && c.unidades.find((u) => u.nome === c.unidade_destaque);
  return h("article", { class: "contato" },
    opcoes.semTitulo ? null : h("div", { class: "contato__cabeca" }, h("h5", {}, c.nome)),
    h("div", { class: "contato__acoes" },
      c.telefones.map(botaoFone),
      c.whatsapp.map((w) => h("a", { class: "btn-zap", href: hrefZap(w.numero), target: "_blank", rel: "noopener noreferrer" },
        icone("chat"), h("span", { class: "btn-fone__t" }, h("b", {}, `WhatsApp ${w.numero}`), w.rotulo ? h("small", {}, w.rotulo) : null),
        h("span", { class: "sr-only" }, " (abre em nova aba)")))),
    destaque ? h("div", { class: "unidade-destaque" }, h("strong", {}, `Pelo seu bairro: ${destaque.nome}`),
      destaque.endereco || "", destaque.telefones.length ? ` · ${destaque.telefones.join(" · ")}` : "") : null,
    dados.length ? h("dl", { class: "contato__dados" }, dados.map(([ic, rotulo, valor]) => h("div", {},
      h("dt", {}, icone(ic), h("span", { class: "sr-only" }, rotulo)), h("dd", {}, valor)))) : null,
    unidadesBloco(c),
    c.observacao ? h("p", { class: "contato__obs" }, c.observacao) : null,
    h("p", { class: "verificado" }, `Conferido em ${dataBR(c.verificado_em)}`,
      c.fonte_url ? [" · ", h("a", { href: c.fonte_url, target: "_blank", rel: "noopener noreferrer" }, "fonte oficial",
        h("span", { class: "sr-only" }, " (abre em nova aba)"))] : null));
}

function pilulaContato(c) {
  if (!c) return null;
  const nome = h("button", { type: "button", class: "pilula__nome", "aria-haspopup": "dialog" }, c.nome);
  nome.addEventListener("click", () => abrirContato(c));
  const primeiro = c.telefones[0];
  return h("span", { class: "pilula" }, nome,
    primeiro ? h("a", { class: "pilula__fone", href: hrefTel(primeiro.numero) }, icone("fone"), primeiro.numero,
      h("span", { class: "sr-only" }, ` (ligar para ${c.nome})`)) : null);
}

function abrirContato(c) {
  $("#dlg-contato-titulo").textContent = c.nome;
  $("#dlg-contato-corpo").replaceChildren(contatoCard(c, { semTitulo: true }));
  $("#dlg-contato").showModal();
}

/* ===================================================================================================
   Roteiro (a lista de tarefas ao lado da conversa)
   =================================================================================================== */

const chavePasso = (p) => `${p.fonte_id || ""}|${p.titulo}`;

function secaoRoteiro(titulo, nomeIcone, conteudo) {
  return h("section", { class: "secao-roteiro" }, h("h4", {}, icone(nomeIcone), titulo), conteudo);
}

function renderPasso(p) {
  const marcador = h("input", { type: "checkbox", id: `feito-${p.ordem}` });
  marcador.checked = estado.feitos.has(chavePasso(p));
  const item = h("li", { class: `passo${marcador.checked ? " passo--feito" : ""}` },
    h("span", { class: "passo__num", "aria-hidden": "true" }, marcador.checked ? icone("ok") : String(p.ordem)),
    h("div", { class: "passo__corpo" },
      h("h6", { class: "passo__titulo" }, h("span", { class: "sr-only" }, `Passo ${p.ordem}: `), p.titulo),
      p.descricao ? h("p", { class: "passo__texto" }, mdInline(p.descricao)) : null,
      p.documentos.length ? h("div", { class: "bloco" },
        h("div", { class: "bloco__titulo" }, icone("arquivo"), "Documentos para reunir"),
        h("ul", {}, p.documentos.map((d) => h("li", {}, d)))) : null,
      p.contato_ids.length ? h("div", { class: "pilulas" }, p.contato_ids.map((id) => pilulaContato(estado.contatos.get(id)))) : null,
      p.links.length ? h("div", { class: "bloco" },
        h("div", { class: "bloco__titulo" }, icone("livro"), "Saiba mais nos sites oficiais"),
        h("ul", { class: "links" }, p.links.map(linkExterno))) : null,
      p.atencao ? h("div", { class: "atencao", role: "note" }, icone("alerta"), h("span", {}, p.atencao)) : null,
      h("div", { class: "passo__marcar" }, marcador, h("label", { for: marcador.id }, "Já fiz este passo"))));
  marcador.addEventListener("change", () => {
    if (marcador.checked) estado.feitos.add(chavePasso(p)); else estado.feitos.delete(chavePasso(p));
    item.classList.toggle("passo--feito", marcador.checked);
    item.querySelector(".passo__num").replaceChildren(marcador.checked ? icone("ok") : String(p.ordem));
    atualizarProgresso();
  });
  return item;
}

// Passos agrupados por serviço. Com mais de um assunto no roteiro, cada grupo ganha um título.
function renderGruposDePassos(passos) {
  const grupos = [];
  for (const p of passos) {
    const ultimo = grupos[grupos.length - 1];
    if (ultimo && ultimo.fonte === p.fonte_id) ultimo.passos.push(p);
    else grupos.push({ fonte: p.fonte_id, titulo: p.fonte_titulo, passos: [p] });
  }
  const varios = grupos.length > 1;
  return h("div", { class: "grupos" }, grupos.map((g) => h("section", { class: "grupo" },
    varios ? h("h5", { class: "grupo__titulo" }, icone("lista"), g.titulo || "Passos") : null,
    h("ol", { class: "passos", start: String(g.passos[0].ordem) }, g.passos.map(renderPasso)))));
}

function atualizarProgresso() {
  const passos = estado.roteiro ? estado.roteiro.passos : [];
  const trilho = $(".progresso__trilho");
  if (!passos.length || !trilho) return;
  const feitos = passos.filter((p) => estado.feitos.has(chavePasso(p))).length;
  const pct = Math.round((feitos / passos.length) * 100);
  $(".progresso__barra").style.width = `${pct}%`;
  trilho.setAttribute("aria-valuenow", String(feitos));
  const texto = `${feitos} de ${passos.length} passos concluídos`;
  $(".progresso__rotulo").textContent = texto;
  $(".progresso__pct").textContent = `${pct}%`;
  anunciar(texto);
}

function renderDireitos(direitos) {
  return h("div", { class: "direitos" }, direitos.map((d) => h("article", { class: "direito" },
    h("h5", {}, d.numero || d.titulo, d.projeto ? h("span", { class: "tag tag--projeto" }, "projeto de lei") : null),
    d.numero ? h("p", { class: "dica" }, d.titulo) : null,
    d.trechos.map((t) => h("blockquote", {}, t)),
    d.links.length ? h("ul", { class: "links" }, d.links.map(linkExterno)) : null)));
}

function renderFontes(fontes) {
  const rotuloTipo = { lei: "Lei", servico: "Serviço", projeto: "Projeto de lei" };
  const ordenadas = [...fontes].sort((a, b) => Number(b.citada) - Number(a.citada));
  return h("details", { class: "fontes secao-roteiro" },
    h("summary", {}, `Fontes consultadas (${fontes.length}): links para você se aprofundar`),
    h("ul", {}, ordenadas.map((f) => h("li", {},
      h("strong", {}, f.titulo),
      h("span", {}, h("span", { class: "tag" }, rotuloTipo[f.tipo] || f.tipo), " ",
        f.citada ? h("span", { class: "tag tag--usada" }, "usada neste roteiro") : null, " ",
        f.verificado_em ? h("small", {}, `conferida em ${dataBR(f.verificado_em)}`) : null),
      f.links.length ? h("ul", { class: "links" }, f.links.map(linkExterno)) : null))));
}

function renderRoteiro() {
  const alvo = $("#roteiro");
  const r = estado.roteiro;
  $("#btn-pdf").hidden = !r;
  $("#btn-imprimir").hidden = !r;
  if (!r) {
    alvo.replaceChildren(h("div", { class: "roteiro__vazio" },
      h("span", { class: "roteiro__vazio-icone" }, icone("lista")),
      h("h4", {}, "Seu roteiro aparece aqui"),
      h("p", {}, "Conte sua situação na conversa. Assim que eu tiver informações suficientes, monto aqui um passo a passo que você vai marcando conforme avança."),
      h("ul", { class: "roteiro__vazio-lista" },
        h("li", {}, icone("arquivo"), "Documentos para separar"),
        h("li", {}, icone("fone"), "Telefones conferidos de quem atende"),
        h("li", {}, icone("globo"), "Links das páginas oficiais"),
        h("li", {}, icone("imprimir"), "Tudo em PDF para levar ao atendimento"))));
    return;
  }
  const apoio = estado.apoio.map((id) => estado.contatos.get(id)).filter(Boolean);
  // replaceChildren(null) escreveria o texto "null" na tela: as partes que faltam são filtradas antes.
  alvo.replaceChildren(...[
    h("div", { class: "roteiro__topo" },
      h("h4", { class: "roteiro__titulo" }, r.titulo),
      r.resumo ? h("p", { class: "roteiro__resumo" }, r.resumo) : null,
      r.passos.length ? h("div", { class: "progresso" },
        h("div", { class: "progresso__texto" }, h("span", { class: "progresso__rotulo" }), h("span", { class: "progresso__pct", "aria-hidden": "true" })),
        h("div", { class: "progresso__trilho", role: "progressbar", "aria-label": "Progresso do roteiro", "aria-valuemin": "0", "aria-valuemax": String(r.passos.length), "aria-valuenow": "0" },
          h("div", { class: "progresso__barra" }))) : null),
    r.aviso ? h("div", { class: "aviso", role: "note" }, icone("alerta"), h("span", {}, r.aviso)) : null,
    r.passos.length ? renderGruposDePassos(r.passos) : null,
    r.direitos.length ? secaoRoteiro("Seus direitos (base legal)", "balanca", renderDireitos(r.direitos)) : null,
    apoio.length ? secaoRoteiro("Quem pode ajudar agora", "fone", h("div", { class: "apoio" }, apoio.map((c) => contatoCard(c)))) : null,
    estado.fontes.length ? renderFontes(estado.fontes) : null,
  ].filter(Boolean));
  if (r.passos.length) {
    const feitos = r.passos.filter((p) => estado.feitos.has(chavePasso(p))).length;
    const pct = Math.round((feitos / r.passos.length) * 100);
    $(".progresso__barra").style.width = `${pct}%`;
    $(".progresso__trilho").setAttribute("aria-valuenow", String(feitos));
    $(".progresso__rotulo").textContent = `${feitos} de ${r.passos.length} passos concluídos`;
    $(".progresso__pct").textContent = `${pct}%`;
  }
}

async function baixarPdf() {
  const botao = $("#btn-pdf");
  const status = $("#status-pdf");
  if (!estado.roteiro || estaDesativado(botao)) return;
  botao.setAttribute("aria-disabled", "true");
  status.textContent = "Gerando o PDF…";
  try {
    const ids = new Set([...estado.apoio, ...estado.roteiro.passos.flatMap((p) => p.contato_ids)]);
    const resposta = await fetch("/roteiro/pdf", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        roteiro: estado.roteiro,
        contatos: [...ids].map((id) => estado.contatos.get(id)).filter(Boolean),
        contatos_de_apoio: estado.apoio,
        fontes: estado.fontes,
      }),
    });
    if (!resposta.ok) throw await erroDaApi(resposta);
    const url = URL.createObjectURL(await resposta.blob());
    const link = h("a", { href: url, download: "roteiro_acessibilidade.pdf" });
    document.body.append(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 10000);
    status.textContent = "PDF gerado. Procure o arquivo na sua pasta de downloads.";
  } catch (erro) {
    status.textContent = `Não foi possível gerar o PDF. ${mensagemDeErro(erro)}`;
  } finally {
    botao.setAttribute("aria-disabled", "false");
  }
}

/* ===================================================================================================
   Visão no celular: conversa ou roteiro
   =================================================================================================== */

const telaGrande = window.matchMedia("(min-width: 1000px)");

function aplicarVisao() {
  const grande = telaGrande.matches;
  $("#painel-conversa").hidden = !grande && estado.visao !== "conversa";
  $("#painel-roteiro").hidden = !grande && estado.visao !== "roteiro";
  $("#ver-conversa").setAttribute("aria-pressed", String(estado.visao === "conversa"));
  $("#ver-roteiro").setAttribute("aria-pressed", String(estado.visao === "roteiro"));
}

function irParaRoteiro() {
  estado.visao = "roteiro";
  aplicarVisao();
  $("#selo-roteiro").hidden = true;
  const painel = $("#painel-roteiro");
  if (!telaGrande.matches) painel.scrollIntoView({ behavior: comportamentoRolagem(), block: "start" });
  $("#roteiro").scrollTo({ top: 0, behavior: comportamentoRolagem() });
  destacarRoteiro();
  painel.focus({ preventScroll: true });
}

// Um brilho rápido na borda do roteiro para mostrar onde a novidade apareceu (desligado no modo calmo).
function destacarRoteiro() {
  const painel = $("#painel-roteiro");
  painel.classList.remove("painel--novidade");
  void painel.offsetWidth; // reinicia a animação
  painel.classList.add("painel--novidade");
}

/* ===================================================================================================
   Navegação: menu lateral e páginas (Início, Assistente, Locais acessíveis, Como funciona)
   Cada página é uma "vista" deste mesmo HTML, escolhida pelo endereço (#assistente, #locais...): dá para usar o
   botão Voltar do navegador e salvar o link, e a conversa e o roteiro continuam lá quando a pessoa visita outra
   página e volta (com arquivos HTML separados, tudo seria apagado a cada troca).
   =================================================================================================== */

const PAGINAS = { inicio: "Início", assistente: "Assistente", locais: "Locais acessíveis", "como-funciona": "Como funciona" };
let paginaAtual = null;
let menuRecolhido = ler("dv-menu") === "recolhido";

function paginaDoEndereco() {
  const pagina = window.location.hash.replace(/^#\/?/, "");
  return Object.prototype.hasOwnProperty.call(PAGINAS, pagina) ? pagina : null;
}

function mostrarPagina(pagina, { foco = true } = {}) {
  paginaAtual = pagina;
  document.querySelectorAll(".vista").forEach((vista) => { vista.hidden = vista.dataset.vista !== pagina; });
  document.querySelectorAll(".menu__nav .menu__link").forEach((link) => {
    if (link.dataset.vista === pagina) link.setAttribute("aria-current", "page");
    else link.removeAttribute("aria-current");
  });
  $("#titulo-pagina").textContent = PAGINAS[pagina];
  document.title = pagina === "inicio" ? "DivergentIA – seus direitos, do papel para a prática" : `${PAGINAS[pagina]} · DivergentIA`;
  document.body.dataset.pagina = pagina;
  window.scrollTo(0, 0);
  fecharMenuMovel(false);
  if (pagina === "assistente") aplicarVisao();
  if (!foco) return;
  // Leitor de tela: o foco vai para o título da página nova. No Assistente (computador), direto para o campo.
  if (pagina === "assistente" && telaGrande.matches) $("#mensagem").focus({ preventScroll: true });
  else $("#titulo-pagina").focus({ preventScroll: true });
}

// Computador: menu expandido (ícone + nome) ou recolhido (trilho estreito). A escolha fica salva no navegador.
function aplicarMenu() {
  const menu = $("#menu");
  const recolher = telaGrande.matches && menuRecolhido;
  menu.classList.toggle("menu--recolhido", recolher);
  const botao = $("#btn-recolher");
  const rotulo = recolher ? "Expandir o menu" : "Recolher o menu";
  botao.setAttribute("aria-expanded", String(!recolher));
  botao.setAttribute("aria-label", rotulo);
  botao.title = rotulo;
  if (telaGrande.matches) { fecharMenuMovel(false); menu.inert = false; }
  else menu.inert = !menu.classList.contains("menu--aberto"); // gaveta fechada: links fora do alcance do Tab
}

// Celular: o menu é uma gaveta. Aberta, o resto da página fica inerte (o foco não escapa para trás dela).
function abrirMenuMovel() {
  const menu = $("#menu");
  menu.classList.add("menu--aberto");
  menu.inert = false;
  $("#menu-fundo").hidden = false;
  $(".principal").inert = true;
  $("#btn-menu").setAttribute("aria-expanded", "true");
  (menu.querySelector('[aria-current="page"]') || menu.querySelector(".menu__link")).focus();
}

function fecharMenuMovel(devolverFoco = true) {
  const menu = $("#menu");
  if (!menu.classList.contains("menu--aberto")) return;
  menu.classList.remove("menu--aberto");
  if (!telaGrande.matches) menu.inert = true;
  $("#menu-fundo").hidden = true;
  $(".principal").inert = false;
  $("#btn-menu").setAttribute("aria-expanded", "false");
  if (devolverFoco) $("#btn-menu").focus();
}

function iniciarNavegacao() {
  aplicarMenu();
  $("#btn-recolher").addEventListener("click", () => {
    menuRecolhido = !menuRecolhido;
    guardar("dv-menu", menuRecolhido ? "recolhido" : "expandido");
    aplicarMenu();
  });
  $("#btn-menu").addEventListener("click", abrirMenuMovel);
  $("#btn-fechar-menu").addEventListener("click", () => fecharMenuMovel());
  $("#menu-fundo").addEventListener("click", () => fecharMenuMovel());
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && $("#menu").classList.contains("menu--aberto")) fecharMenuMovel();
  });
  // Clicar na página em que já se está não muda o endereço: só fecha a gaveta.
  document.querySelectorAll(".menu__link[data-vista]").forEach((link) => link.addEventListener("click", () => {
    if (link.dataset.vista === paginaAtual) fecharMenuMovel(false);
  }));
  telaGrande.addEventListener("change", aplicarMenu);
  window.addEventListener("hashchange", () => { const pagina = paginaDoEndereco(); if (pagina) mostrarPagina(pagina); });
  // "Pular para o conteúdo" sem mexer no endereço (senão a página atual se perderia).
  $(".pular").addEventListener("click", (e) => {
    e.preventDefault();
    (paginaAtual === "assistente" ? $("#mensagem") : $("#conteudo")).focus();
  });
  mostrarPagina(paginaDoEndereco() || "inicio", { foco: false });
}

/* ===================================================================================================
   Conversa
   =================================================================================================== */

const elConversa = () => $("#conversa");
const avatar = () => h("span", { class: "msg__avatar", "aria-hidden": "true" }, iconeInfinito());
const distanciaDoFim = () => { const c = elConversa(); return c.scrollHeight - c.scrollTop - c.clientHeight; };

function rolarParaFim(comportamento = comportamentoRolagem()) {
  const c = elConversa();
  c.scrollTo({ top: c.scrollHeight, behavior: comportamento });
}

// Resposta nova: em vez de pular para o FIM dela (e a pessoa ter que subir para achar o começo), a conversa para
// com a pergunta da pessoa no topo e o começo da resposta logo abaixo, como nos chats de IA conhecidos.
function rolarParaResposta(artigo) {
  const c = elConversa();
  const pergunta = artigo.previousElementSibling && artigo.previousElementSibling.classList.contains("msg--eu")
    ? artigo.previousElementSibling : artigo;
  const alvo = pergunta.offsetTop - 12;
  c.scrollTo({ top: Math.max(0, alvo), behavior: comportamentoRolagem() });
}

function atualizarBotaoFim() {
  $("#btn-fim").hidden = distanciaDoFim() < 240;
}

function msgUsuario(texto) {
  elConversa().append(h("article", { class: "msg msg--eu" },
    h("div", { class: "msg__corpo" }, h("div", { class: "msg__balao" }, h("span", { class: "sr-only" }, "Você: "), texto))));
  rolarParaFim();
}

function seloCobertura(cobertura) {
  const mapa = {
    completa: ["completa", "ok", "Baseada nas fontes oficiais"],
    parcial: ["parcial", "alerta", "Confirme os detalhes com os contatos"],
    nenhuma: ["nenhuma", "info", "Fora da minha base de informações"],
  };
  const [classe, nomeIcone, texto] = mapa[cobertura] || mapa.parcial;
  return h("span", { class: `selo-cobertura selo-cobertura--${classe}` }, icone(nomeIcone), texto);
}

function botaoCopiar(alvo) {
  const rotulo = h("span", {}, "Copiar");
  const botao = h("button", { type: "button", class: "acao" }, icone("copiar"), rotulo);
  let volta = null;
  botao.addEventListener("click", async () => {
    clearTimeout(volta);
    try {
      await navigator.clipboard.writeText(alvo.innerText.trim());
      rotulo.textContent = "Copiado";
      botao.firstElementChild.replaceWith(icone("ok"));
      anunciar("Resposta copiada.");
    } catch (_) {
      rotulo.textContent = "Não deu para copiar";
    }
    volta = setTimeout(() => {
      rotulo.textContent = "Copiar";
      botao.firstElementChild.replaceWith(icone("copiar"));
    }, 2200);
  });
  return botao;
}

function definirMunicipioPorRotulo(rotulo) {
  if (MUNICIPIOS_COM_DADOS.includes(rotulo)) $("#municipio").value = rotulo;
}

function blocoPergunta(p) {
  const idTexto = `pergunta-${p.id}-${Date.now()}`;
  const botoes = p.opcoes.map((o) => h("button", { type: "button", class: "chip", "aria-pressed": "false" }, o.rotulo));
  botoes.forEach((botao, i) => botao.addEventListener("click", () => {
    botoes.forEach((b) => { b.disabled = true; });
    botao.setAttribute("aria-pressed", "true");
    if (p.id === "municipio") definirMunicipioPorRotulo(p.opcoes[i].rotulo);
    enviar(p.opcoes[i].mensagem);
  }));
  return h("div", { class: "pergunta", role: "group", "aria-labelledby": idTexto },
    h("p", { class: "pergunta__texto", id: idTexto }, p.pergunta), h("div", { class: "pergunta__opcoes" }, botoes));
}

function cartaoRoteiro(roteiro) {
  const partes = [];
  if (roteiro.passos.length) partes.push(`${roteiro.passos.length} passos`);
  if (roteiro.direitos.length) partes.push(roteiro.direitos.length === 1 ? "1 direito em lei" : `${roteiro.direitos.length} direitos em lei`);
  const onde = telaGrande.matches ? "ver no painel ao lado" : "toque para ver";
  const botao = h("button", { type: "button", class: "cartao-roteiro" },
    h("span", { class: "cartao-roteiro__icone" }, icone("lista")),
    h("span", { class: "cartao-roteiro__texto" }, h("strong", {}, roteiro.titulo || "Roteiro atualizado"),
      h("span", {}, `Roteiro atualizado · ${partes.join(" · ")} · ${onde}`)));
  botao.addEventListener("click", irParaRoteiro);
  return botao;
}

// A resposta da IA aparece como texto corrido (sem balão), com largura confortável de leitura; embaixo ficam o
// roteiro, os contatos, as perguntas de triagem e uma linha discreta com o selo de cobertura e "Copiar".
function msgAssistente(d, opcoes = {}) {
  const extras = [];
  if (d.roteiro) extras.push(cartaoRoteiro(d.roteiro));
  if (!d.roteiro && d.contatos_de_apoio && d.contatos_de_apoio.length) {
    const cartoes = d.contatos_de_apoio.map((id) => estado.contatos.get(id)).filter(Boolean).map((c) => contatoCard(c));
    extras.push(h("div", { class: "apoio" }, h("p", { class: "apoio__titulo" }, icone("fone"), "Quem pode ajudar agora"), cartoes));
  }
  (d.perguntas || []).forEach((p) => extras.push(blocoPergunta(p)));

  const texto = renderMarkdown(d.mensagem);
  const mostrarSelo = !opcoes.semSelo && (d.roteiro || (d.fontes && d.fontes.length) || d.cobertura !== "completa");
  const acoes = opcoes.semAcoes ? null
    : h("div", { class: "msg__acoes" }, mostrarSelo ? seloCobertura(d.cobertura) : null, botaoCopiar(texto));

  const artigo = h("article", { class: "msg msg--bot" }, avatar(),
    h("div", { class: "msg__corpo" },
      h("div", { class: "msg__texto" }, h("span", { class: "sr-only" }, "Assistente: "), texto),
      extras.length ? h("div", { class: "msg__extra" }, extras) : null,
      acoes));
  elConversa().append(artigo);
  return artigo;
}

function msgErro(texto) {
  const tentar = h("button", { type: "button", class: "btn btn--suave" }, icone("recomecar"), "Tentar de novo");
  tentar.addEventListener("click", () => { article.remove(); enviar(estado.ultimaMensagem, { reenvio: true }); });
  const article = h("article", { class: "msg msg--bot msg--erro", role: "alert" }, avatar(),
    h("div", { class: "msg__corpo" },
      h("div", { class: "msg__balao" }, h("strong", {}, "Não consegui responder. "), texto),
      h("div", { class: "msg__extra" }, tentar)));
  elConversa().append(article);
  rolarParaFim();
}

let cronometro = null;

function mostrarDigitando(ativo) {
  clearInterval(cronometro);
  const antigo = $("#digitando");
  if (antigo) antigo.remove();
  if (!ativo) return;
  const inicio = Date.now();
  const tempo = h("span", { "aria-hidden": "true" }, "0 s");
  const texto = h("span", { class: "digitando__texto" }, "Lendo a sua mensagem e consultando as fontes oficiais… ", tempo);
  const cancelar = h("button", { type: "button", class: "btn btn--texto" }, "Cancelar");
  cancelar.addEventListener("click", () => { if (estado.controle) estado.controle.abort(); });
  elConversa().append(h("div", { id: "digitando", class: "msg msg--bot msg--digitando", role: "status" }, avatar(),
    h("div", { class: "digitando" },
      h("span", { class: "digitando__pontos", "aria-hidden": "true" }, h("i"), h("i"), h("i")), texto, cancelar)));
  rolarParaFim();
  cronometro = setInterval(() => {
    const s = Math.round((Date.now() - inicio) / 1000);
    tempo.textContent = `${s} s`;
    if (s === 5) texto.firstChild.textContent = "Escrevendo a resposta… ";
    if (s === 20) texto.firstChild.textContent = "Ainda escrevendo, é uma resposta mais completa… ";
  }, 1000);
}

function aplicarResposta(d) {
  d.contatos.forEach((c) => estado.contatos.set(c.id, c));
  if (d.roteiro) {
    estado.roteiro = d.roteiro;
    estado.fontes = d.fontes || [];
    estado.apoio = d.contatos_de_apoio || [];
    renderRoteiro();
    destacarRoteiro();
    const n = d.roteiro.passos.length;
    anunciar(n ? `Roteiro atualizado com ${n} passos.` : "Roteiro atualizado com seus direitos.");
    if (!telaGrande.matches && estado.visao !== "roteiro") $("#selo-roteiro").hidden = false;
  }
  rolarParaResposta(msgAssistente(d));
  estado.historico.push({ papel: "assistente", conteudo: d.mensagem });
  if (d.municipio_detectado && MUNICIPIOS_COM_DADOS.includes(d.municipio_detectado) && !$("#municipio").value) {
    $("#municipio").value = d.municipio_detectado;
  }
}

// "Enviar" fica com cara de desativado enquanto o campo está vazio ou a resposta ainda não chegou.
function atualizarBotaoEnviar() {
  const vazio = !$("#mensagem").value.trim();
  $("#btn-enviar").setAttribute("aria-disabled", String(estado.carregando || vazio));
}

async function enviar(texto, opcoes = {}) {
  texto = String(texto).trim();
  if (!texto || estado.carregando) return;
  estado.ultimaMensagem = texto;
  const historicoEnviado = estado.historico.slice(-12);
  if (!opcoes.reenvio) msgUsuario(texto);
  estado.historico.push({ papel: "usuario", conteudo: texto });

  const campo = $("#mensagem");
  campo.value = "";
  ajustarCampo();
  estado.carregando = true;
  atualizarBotaoEnviar();
  mostrarDigitando(true);
  estado.controle = new AbortController();
  const limite = setTimeout(() => estado.controle.abort(), 5 * 60 * 1000);
  try {
    const resposta = await fetch("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        mensagem: texto,
        municipio: $("#municipio").value || null,
        historico: historicoEnviado,
        roteiro_atual: estado.roteiro,
        conversa_id: estado.conversaId,
      }),
      signal: estado.controle.signal,
    });
    if (!resposta.ok) throw await erroDaApi(resposta);
    const dados = await resposta.json();
    mostrarDigitando(false);
    if (dados.conversa_id) estado.conversaId = dados.conversa_id;
    aplicarResposta(dados);
  } catch (erro) {
    mostrarDigitando(false);
    estado.historico.pop(); // a pergunta sem resposta não entra no histórico; "tentar de novo" a reenvia
    msgErro(mensagemDeErro(erro));
  } finally {
    clearTimeout(limite);
    estado.carregando = false;
    atualizarBotaoEnviar();
    campo.focus({ preventScroll: true });
  }
}

function ajustarCampo() {
  const campo = $("#mensagem");
  campo.style.height = "auto";
  campo.style.height = `${Math.min(campo.scrollHeight, 200)}px`;
  atualizarBotaoEnviar();
}

function saudacaoInicial() {
  elConversa().replaceChildren();
  msgAssistente({
    mensagem: "Olá! Sou o assistente do **DivergentIA**. Posso te orientar sobre direitos, benefícios e serviços para pessoas com deficiência e neurodivergentes na Grande Vitória, e montar um passo a passo com documentos, links oficiais e telefones.\n\nMe conte com as suas palavras o que você precisa. Pode ser algo bem do dia a dia, como uma dúvida sobre a escola, um benefício, um documento ou uma situação que te incomodou.",
    cobertura: "completa", fontes: [], perguntas: [], contatos_de_apoio: [], roteiro: null,
  }, { semSelo: true, semAcoes: true });
  elConversa().scrollTop = 0; // a 1ª mensagem precisa ficar visível (no celular a área é pequena)
  atualizarBotaoFim();
}

let temporizadorNova = null;
function novaConversa() {
  const botao = $("#btn-nova");
  const rotulo = botao.querySelector("span");
  if (rotulo.textContent === "Nova conversa") {
    rotulo.textContent = "Apagar tudo?";
    temporizadorNova = setTimeout(() => { rotulo.textContent = "Nova conversa"; }, 4000);
    return;
  }
  clearTimeout(temporizadorNova);
  rotulo.textContent = "Nova conversa";
  if (estado.controle) estado.controle.abort();
  estado.historico = [];
  estado.roteiro = null;
  estado.fontes = [];
  estado.apoio = [];
  estado.feitos.clear();
  estado.conversaId = null;
  $("#municipio").value = "";
  $("#status-pdf").textContent = "";
  saudacaoInicial();
  renderRoteiro();
  anunciar("Conversa reiniciada.");
}

// Histórico (só para quem está logado com conta de usuário — ver verificarConta()).
async function abrirHistorico() {
  const dialogo = $("#dlg-historico");
  const lista = $("#lista-historico");
  const status = $("#status-historico");
  status.textContent = "Carregando…";
  lista.replaceChildren();
  dialogo.showModal();
  try {
    const resposta = await fetch("/chat/conversas");
    if (!resposta.ok) throw await erroDaApi(resposta);
    const conversas = await resposta.json();
    status.textContent = conversas.length ? "" : "Você ainda não tem conversas salvas.";
    lista.replaceChildren(...conversas.map((c) => {
      const abrir = h("button", { type: "button", class: "btn btn--texto" },
        h("span", { class: "historico__titulo" }, c.titulo),
        h("span", { class: "historico__data" }, dataHoraBR(c.atualizada_em)));
      abrir.addEventListener("click", () => carregarConversa(c.id));
      const excluir = h("button", {
        type: "button", class: "btn btn--icone historico__excluir",
        "aria-label": `Excluir a conversa "${c.titulo}"`,
      }, icone("fechar"));
      excluir.addEventListener("click", () => excluirConversa(c.id));
      return h("li", { class: "historico__item" }, abrir, excluir);
    }));
  } catch (erro) {
    status.textContent = `Não foi possível carregar o histórico. ${mensagemDeErro(erro)}`;
  }
}

async function carregarConversa(id) {
  const status = $("#status-historico");
  status.textContent = "Abrindo conversa…";
  try {
    const resposta = await fetch(`/chat/conversas/${id}`);
    if (!resposta.ok) throw await erroDaApi(resposta);
    const conversa = await resposta.json();
    if (estado.controle) estado.controle.abort();
    estado.historico = conversa.mensagens.map((m) => ({ papel: m.papel, conteudo: m.conteudo }));
    estado.roteiro = conversa.roteiro_final;
    estado.conversaId = conversa.id;
    estado.fontes = [];
    estado.apoio = [];
    estado.feitos.clear();
    elConversa().replaceChildren();
    conversa.mensagens.forEach((m) => {
      if (m.papel === "usuario") msgUsuario(m.conteudo);
      else msgAssistente({
        mensagem: m.conteudo, cobertura: "completa", fontes: [], perguntas: [],
        contatos_de_apoio: [], roteiro: null,
      }, { semSelo: true });
    });
    rolarParaFim("auto");
    renderRoteiro();
    $("#dlg-historico").close();
    anunciar("Conversa carregada do seu histórico.");
  } catch (erro) {
    status.textContent = `Não foi possível abrir essa conversa. ${mensagemDeErro(erro)}`;
  }
}

async function excluirConversa(id) {
  const status = $("#status-historico");
  try {
    const resposta = await fetch(`/chat/conversas/${id}`, { method: "DELETE" });
    if (!resposta.ok) throw await erroDaApi(resposta);
    if (estado.conversaId === id) estado.conversaId = null;
    await abrirHistorico();
  } catch (erro) {
    status.textContent = `Não foi possível excluir essa conversa. ${mensagemDeErro(erro)}`;
  }
}

/* ===================================================================================================
   Locais acessíveis (mapa colaborativo)
   =================================================================================================== */

const MUNICIPIO_LOCAIS = "Vitória"; // única cidade com base de dados por enquanto
const TIPOS = {
  comercio: "Comércio", saude: "Saúde", educacao: "Educação", lazer: "Lazer e cultura",
  orgao_publico: "Órgão público", apoio_especializado: "Apoio especializado", outro: "Outro",
};
const RECURSOS = {
  rampa: "Rampa", banheiro_adaptado: "Banheiro adaptado", braille: "Sinalização em Braille",
  cardapio_acessivel: "Cardápio acessível", baixo_estimulo_sensorial: "Baixo estímulo sensorial",
  atendimento_preferencial: "Atendimento preferencial real", libras: "Atendimento em Libras",
  cadeira_anfibia: "Cadeira anfíbia (banho de mar)", brinquedos_adaptados: "Brinquedos adaptados",
  vaga_exclusiva: "Vaga de estacionamento exclusiva", tecnologia_assistiva: "Tecnologia assistiva",
  estrutura_sensorial: "Estrutura de estímulo sensorial", piso_tatil: "Piso tátil",
  alto_contraste: "Sinalização de alto contraste",
};

function preencherOpcoes() {
  const tipos = Object.entries(TIPOS).map(([valor, rotulo]) => h("option", { value: valor }, rotulo));
  const selecione = () => h("option", { value: "", disabled: true, selected: true }, "Selecione…");
  $("#f-tipo").append(h("option", { value: "" }, "Todos os tipos"), ...tipos.map((o) => o.cloneNode(true)));
  $("#l-tipo").append(selecione(), ...tipos);
  Object.entries(RECURSOS).forEach(([valor, rotulo], i) => {
    $("#l-recursos").append(h("div", { class: "check" },
      h("input", { type: "checkbox", id: `recurso-${i}`, name: "recursos", value: valor }),
      h("label", { for: `recurso-${i}` }, rotulo)));
  });
}

async function carregarLocais() {
  const parametros = new URLSearchParams({ municipio: MUNICIPIO_LOCAIS });
  if ($("#f-tipo").value) parametros.set("tipo", $("#f-tipo").value);
  if ($("#f-verificados").checked) parametros.set("apenas_verificados", "true");
  const status = $("#status-locais");
  try {
    const resposta = await fetch(`/locais?${parametros}`);
    if (!resposta.ok) throw await erroDaApi(resposta);
    const locais = await resposta.json();
    renderLocais(locais);
    status.textContent = locais.length === 1 ? "1 local encontrado." : `${locais.length} locais encontrados.`;
  } catch (erro) {
    status.textContent = "";
    $("#lista-locais").replaceChildren(h("li", { class: "erro-caixa" }, `Não foi possível carregar os locais. ${mensagemDeErro(erro)}`));
  }
}

function renderLocais(locais) {
  const lista = $("#lista-locais");
  if (!locais.length) {
    lista.replaceChildren(h("li", { class: "vazio" }, "Nenhum local encontrado com esses filtros. Que tal cadastrar o primeiro?"));
    return;
  }
  lista.replaceChildren(...[...locais].reverse().map((local) => h("li", { class: "cartao local" },
    local.verificado
      ? h("span", { class: "selo selo--ok" }, icone("ok"), "Verificado por parceiros")
      : h("span", { class: "selo selo--pendente" }, icone("relogio"), "Aguardando verificação"),
    h("h3", {}, local.nome),
    h("p", { class: "local__meta" }, `${TIPOS[local.tipo] || local.tipo} · ${local.bairro ? local.bairro + ", " : ""}${local.municipio}`),
    h("p", {}, local.endereco),
    local.horario_funcionamento ? h("p", { class: "local__horario" }, icone("relogio"), " ", local.horario_funcionamento) : null,
    local.telefones && local.telefones.length
      ? h("p", { class: "local__telefones" },
          local.telefones.map((tel, i) => [i ? " · " : "", h("a", { href: hrefTel(tel) }, tel)]))
      : null,
    local.recursos_acessibilidade && local.recursos_acessibilidade.length
      ? h("ul", { class: "tags", "aria-label": "Recursos de acessibilidade" },
          local.recursos_acessibilidade.map((r) => h("li", { class: "tag" }, RECURSOS[r] || r)))
      : null,
    local.observacoes ? h("p", { class: "local__obs" }, local.observacoes) : null,
    local.fonte_url
      ? h("p", { class: "local__fonte" },
          h("a", { href: local.fonte_url, target: "_blank", rel: "noopener" }, "Fonte ", icone("externo")),
          local.verificado_em ? ` · conferido em ${dataBR(local.verificado_em)}` : "")
      : null)));
}

async function cadastrarLocal(evento) {
  evento.preventDefault();
  const botao = $("#btn-salvar-local");
  if (estaDesativado(botao)) return;
  const form = evento.currentTarget;
  const dados = new FormData(form);
  const texto = (campo) => String(dados.get(campo) || "").trim();
  const status = $("#status-cadastro");
  botao.setAttribute("aria-disabled", "true");
  status.textContent = "Enviando…";
  try {
    const resposta = await fetch("/locais", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        nome: texto("nome"), municipio: MUNICIPIO_LOCAIS, endereco: texto("endereco"), tipo: texto("tipo"),
        recursos_acessibilidade: dados.getAll("recursos"),
        observacoes: texto("observacoes") || null, reportado_por: texto("reportado_por") || null,
      }),
    });
    if (!resposta.ok) throw await erroDaApi(resposta);
    form.reset();
    $("#dlg-local").close();
    await carregarLocais();
    $("#status-locais").textContent = "Local cadastrado e já está visível no mapa.";
  } catch (erro) {
    status.textContent = `Não foi possível cadastrar o local. ${mensagemDeErro(erro)}`;
  } finally {
    botao.setAttribute("aria-disabled", "false");
  }
}

/* ===================================================================================================
   Informações da base e ajuda imediata (rodapé)
   =================================================================================================== */

async function carregarBase() {
  try {
    const resposta = await fetch("/base/resumo");
    if (!resposta.ok) throw new Error("base indisponível");
    const d = await resposta.json();
    $("#info-base").textContent = `Base com ${d.fontes} fontes e ${d.contatos} contatos, conferida em ${dataBR(d.verificado_em)}`;
    $("#lista-ajuda").replaceChildren(...(d.ajuda_imediata || []).map((c) => h("li", {},
      h("strong", {}, c.nome),
      c.horario ? h("small", {}, c.horario) : null,
      c.telefones.slice(0, 1).map(botaoFone))));
  } catch (_) {
    $("#info-base").textContent = "Não foi possível carregar as informações da base.";
  }
}

/* ===================================================================================================
   Ligações e início
   =================================================================================================== */

function ligarEventos() {
  const formChat = $("#form-chat");
  const campo = $("#mensagem");
  formChat.addEventListener("submit", (e) => { e.preventDefault(); enviar(campo.value); });
  // No celular o exemplo longo ocupa 3 linhas do campo: lá vai um texto curto.
  const telaPequena = window.matchMedia("(max-width: 560px)");
  const exemplo = campo.getAttribute("placeholder");
  const ajustarExemplo = () => { campo.placeholder = telaPequena.matches ? "Escreva sua mensagem…" : exemplo; };
  ajustarExemplo();
  telaPequena.addEventListener("change", ajustarExemplo);
  campo.addEventListener("input", ajustarCampo);
  campo.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); formChat.requestSubmit(); }
  });
  elConversa().addEventListener("scroll", atualizarBotaoFim, { passive: true });
  $("#btn-fim").addEventListener("click", () => rolarParaFim());
  $("#btn-nova").addEventListener("click", novaConversa);
  $("#btn-historico").addEventListener("click", abrirHistorico);
  $("#btn-pdf").addEventListener("click", baixarPdf);
  $("#btn-imprimir").addEventListener("click", () => window.print());

  $("#ver-conversa").addEventListener("click", () => { estado.visao = "conversa"; aplicarVisao(); });
  $("#ver-roteiro").addEventListener("click", () => { estado.visao = "roteiro"; $("#selo-roteiro").hidden = true; aplicarVisao(); });
  telaGrande.addEventListener("change", aplicarVisao);

  $("#filtros-locais").addEventListener("change", carregarLocais);
  $("#filtros-locais").addEventListener("submit", (e) => e.preventDefault());
  $("#btn-cadastrar").addEventListener("click", () => { $("#status-cadastro").textContent = ""; $("#dlg-local").showModal(); });
  $("#form-local").addEventListener("submit", cadastrarLocal);

  document.querySelectorAll("dialog").forEach((dialogo) => {
    dialogo.addEventListener("click", (e) => { if (e.target === dialogo) dialogo.close(); });
    dialogo.querySelectorAll("[data-fechar]").forEach((b) => b.addEventListener("click", () => dialogo.close()));
  });
  ligarAcessibilidade();
}

// Conta (opcional): troca "Entrar" por "Sair" quando já existe uma sessão, sem exigir login para o chat.
// Também decide se o botão "Cadastrar um local" aparece (só para quem entrou como admin).
async function verificarConta() {
  const link = $("#link-conta");
  const botaoCadastrar = $("#btn-cadastrar");
  const botaoHistorico = $("#btn-historico");
  let rotulo = null;
  let ehAdmin = false;
  try {
    const resposta = await fetch("/auth/eu");
    if (resposta.ok) rotulo = (await resposta.json()).nome_completo.split(" ")[0];
  } catch (_) { /* servidor de contas indisponível: mantém "Entrar" */ }
  if (!rotulo) {
    try {
      const respostaAdmin = await fetch("/auth/admin-eu");
      ehAdmin = respostaAdmin.ok;
      if (ehAdmin) rotulo = "admin";
    } catch (_) { /* ignora */ }
  }
  if (botaoCadastrar) botaoCadastrar.hidden = !ehAdmin;
  if (botaoHistorico) botaoHistorico.hidden = !rotulo || ehAdmin; // histórico é só de conta de usuário, não do admin
  if (!rotulo) return;
  link.querySelector(".menu__rotulo").textContent = `Sair (${rotulo})`;
  link.title = `Sair da conta (${rotulo})`;
  link.removeAttribute("href");
  link.tabIndex = 0;
  link.setAttribute("role", "button");
  link.addEventListener("click", async (e) => {
    e.preventDefault();
    await fetch("/auth/logout", { method: "POST" });
    window.location.reload();
  });
}

document.addEventListener("DOMContentLoaded", () => {
  carregarPrefs();
  ligarEventos();
  aplicarPrefs();
  preencherOpcoes();
  saudacaoInicial();
  renderRoteiro();
  iniciarNavegacao();
  aplicarVisao();
  carregarBase();
  carregarLocais();
  verificarConta();
  if (new URLSearchParams(window.location.search).get("conta") === "criada") {
    anunciar("Conta criada! Você já está conectado.");
    window.history.replaceState({}, "", window.location.pathname);
  }
});
