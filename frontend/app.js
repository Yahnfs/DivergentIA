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
      h("p", { class: "passo__texto" }, p.descricao),
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
      icone("lista"),
      h("h4", {}, "Seu roteiro aparece aqui"),
      h("p", {}, "Conte sua situação na conversa. Quando eu tiver informações suficientes, monto o passo a passo com documentos, links oficiais e telefones, e você vai marcando o que já fez.")));
    return;
  }
  const apoio = estado.apoio.map((id) => estado.contatos.get(id)).filter(Boolean);
  alvo.replaceChildren(
    h("h4", { class: "roteiro__titulo" }, r.titulo),
    r.resumo ? h("p", { class: "roteiro__resumo" }, r.resumo) : null,
    r.passos.length ? h("div", { class: "progresso" },
      h("div", { class: "progresso__texto" }, h("span", { class: "progresso__rotulo" }), h("span", { class: "progresso__pct", "aria-hidden": "true" })),
      h("div", { class: "progresso__trilho", role: "progressbar", "aria-label": "Progresso do roteiro", "aria-valuemin": "0", "aria-valuemax": String(r.passos.length), "aria-valuenow": "0" },
        h("div", { class: "progresso__barra" }))) : null,
    r.aviso ? h("div", { class: "aviso", role: "note" }, icone("alerta"), h("span", {}, r.aviso)) : null,
    r.passos.length ? renderGruposDePassos(r.passos) : null,
    r.direitos.length ? secaoRoteiro("Seus direitos (base legal)", "balanca", renderDireitos(r.direitos)) : null,
    apoio.length ? secaoRoteiro("Quem pode ajudar agora", "fone", h("div", { class: "apoio" }, apoio.map((c) => contatoCard(c)))) : null,
    estado.fontes.length ? renderFontes(estado.fontes) : null,
  );
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
  painel.scrollIntoView({ behavior: "smooth", block: "start" });
  painel.focus({ preventScroll: true });
}

/* ===================================================================================================
   Conversa
   =================================================================================================== */

// Atalhos da conversa: o botão mostra o rótulo curto; ao clicar, a pergunta completa é enviada.
const TEMAS = [
  { rotulo: "Apoio ou mediador na escola", mensagem: "Como pedir mediador ou apoio para meu filho na escola?" },
  { rotulo: "Benefício BPC", mensagem: "Como conseguir o BPC?" },
  { rotulo: "Isenção de impostos (carro)", mensagem: "Como pedir isenção de impostos na compra de um carro?" },
  { rotulo: "Credencial de estacionamento", mensagem: "Como tirar a credencial de estacionamento?" },
  { rotulo: "Carteirinha do autista", mensagem: "Como fazer a carteirinha do autista?" },
  { rotulo: "Passe livre no ônibus", mensagem: "Como conseguir passe livre no ônibus?" },
];

const elConversa = () => $("#conversa");
const rolarParaFim = () => { const c = elConversa(); c.scrollTop = c.scrollHeight; };
const avatar = () => h("span", { class: "msg__avatar", "aria-hidden": "true" }, iconeInfinito());

function msgUsuario(texto) {
  elConversa().append(h("article", { class: "msg msg--eu" },
    h("div", { class: "msg__corpo" }, h("div", { class: "msg__balao" }, h("span", { class: "sr-only" }, "Você: "), texto))));
  rolarParaFim();
}

function seloCobertura(cobertura) {
  const mapa = {
    completa: ["completa", "ok", "Resposta baseada nas fontes"],
    parcial: ["parcial", "alerta", "Resposta parcial: confirme com os contatos"],
    nenhuma: ["nenhuma", "info", "Não tenho essa informação na base"],
  };
  const [classe, nomeIcone, texto] = mapa[cobertura] || mapa.parcial;
  return h("span", { class: `selo-cobertura selo-cobertura--${classe}` }, icone(nomeIcone), texto);
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

function blocoSugestoes(sugestoes) {
  return h("div", { class: "sugestoes", role: "group", "aria-label": "Sugestões de perguntas" },
    sugestoes.map((s) => {
      const item = typeof s === "string" ? { rotulo: s, mensagem: s } : s; // o servidor manda texto; os temas iniciais têm rótulo curto
      const botao = h("button", { type: "button", class: "chip" }, item.rotulo);
      botao.addEventListener("click", () => enviar(item.mensagem));
      return botao;
    }));
}

function cartaoRoteiro(roteiro) {
  const partes = [];
  if (roteiro.passos.length) partes.push(`${roteiro.passos.length} passos`);
  if (roteiro.direitos.length) partes.push(`${roteiro.direitos.length} direito(s) em lei`);
  const botao = h("button", { type: "button", class: "cartao-roteiro" }, icone("lista"),
    h("div", {}, h("strong", {}, "Roteiro atualizado"), h("span", {}, `${partes.join(" · ")} · toque para ver`)));
  botao.addEventListener("click", irParaRoteiro);
  return botao;
}

function msgAssistente(d, opcoes = {}) {
  const extras = [];
  const mostrarSelo = d.roteiro || (d.fontes && d.fontes.length) || d.cobertura !== "completa";
  if (mostrarSelo && !opcoes.semSelo) extras.push(h("div", {}, seloCobertura(d.cobertura)));
  if (d.roteiro) extras.push(cartaoRoteiro(d.roteiro));
  if (!d.roteiro && d.contatos_de_apoio && d.contatos_de_apoio.length) {
    const cartoes = d.contatos_de_apoio.map((id) => estado.contatos.get(id)).filter(Boolean).map((c) => contatoCard(c));
    extras.push(h("div", { class: "apoio" }, h("p", { class: "pergunta__texto" }, "Quem pode ajudar agora"), cartoes));
  }
  (d.perguntas || []).forEach((p) => extras.push(blocoPergunta(p)));
  if (d.sugestoes && d.sugestoes.length) extras.push(blocoSugestoes(d.sugestoes));

  elConversa().append(h("article", { class: "msg msg--bot" }, avatar(),
    h("div", { class: "msg__corpo" },
      h("div", { class: "msg__balao" }, h("span", { class: "sr-only" }, "Assistente: "), h("p", {}, d.mensagem)),
      extras.length ? h("div", { class: "msg__extra" }, extras) : null)));
  rolarParaFim();
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
  const texto = h("span", { class: "digitando__texto" }, "Consultando a base de fontes oficiais… ", tempo);
  const cancelar = h("button", { type: "button", class: "btn btn--texto" }, "Cancelar");
  cancelar.addEventListener("click", () => { if (estado.controle) estado.controle.abort(); });
  elConversa().append(h("div", { id: "digitando", class: "msg msg--bot", role: "status" }, avatar(),
    h("div", { class: "digitando" },
      h("span", { class: "digitando__pontos", "aria-hidden": "true" }, h("i"), h("i"), h("i")), texto, cancelar)));
  rolarParaFim();
  cronometro = setInterval(() => {
    const s = Math.round((Date.now() - inicio) / 1000);
    tempo.textContent = `${s} s`;
    if (s === 6) texto.firstChild.textContent = "Montando o roteiro… ";
    if (s === 25) texto.firstChild.textContent = "Ainda trabalhando: a IA roda neste computador e pode levar um pouco mais… ";
  }, 1000);
}

function aplicarResposta(d) {
  d.contatos.forEach((c) => estado.contatos.set(c.id, c));
  if (d.roteiro) {
    estado.roteiro = d.roteiro;
    estado.fontes = d.fontes || [];
    estado.apoio = d.contatos_de_apoio || [];
    renderRoteiro();
    const n = d.roteiro.passos.length;
    anunciar(n ? `Roteiro atualizado com ${n} passos.` : "Roteiro atualizado com seus direitos.");
    if (!telaGrande.matches && estado.visao !== "roteiro") $("#selo-roteiro").hidden = false;
  }
  msgAssistente(d);
  estado.historico.push({ papel: "assistente", conteudo: d.mensagem });
  if (d.municipio_detectado && MUNICIPIOS_COM_DADOS.includes(d.municipio_detectado) && !$("#municipio").value) {
    $("#municipio").value = d.municipio_detectado;
  }
}

function atualizarBotaoEnviar() {
  const botao = $("#btn-enviar");
  botao.setAttribute("aria-disabled", String(estado.carregando));
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
      }),
      signal: estado.controle.signal,
    });
    if (!resposta.ok) throw await erroDaApi(resposta);
    const dados = await resposta.json();
    mostrarDigitando(false);
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
  campo.style.height = `${Math.min(campo.scrollHeight, 144)}px`;
}

function saudacaoInicial() {
  elConversa().replaceChildren();
  msgAssistente({
    mensagem: "Olá! Sou o assistente do DivergentIA. Posso te orientar sobre direitos, benefícios e serviços para pessoas com deficiência e neurodivergentes na Grande Vitória, e montar um passo a passo com documentos, links oficiais e telefones. Sobre o que você quer falar?",
    cobertura: "completa", fontes: [], perguntas: [], sugestoes: TEMAS, contatos_de_apoio: [], roteiro: null,
  }, { semSelo: true });
  elConversa().scrollTop = 0; // a 1ª mensagem precisa ficar visível (no celular a área é pequena)
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
  $("#municipio").value = "";
  $("#status-pdf").textContent = "";
  saudacaoInicial();
  renderRoteiro();
  anunciar("Conversa reiniciada.");
}

/* ===================================================================================================
   Locais acessíveis (mapa colaborativo)
   =================================================================================================== */

const MUNICIPIOS_GV = ["Cariacica", "Fundão", "Guarapari", "Serra", "Viana", "Vila Velha", "Vitória"];
const TIPOS = { comercio: "Comércio", saude: "Saúde", educacao: "Educação", lazer: "Lazer e cultura", orgao_publico: "Órgão público", outro: "Outro" };
const RECURSOS = {
  rampa: "Rampa", banheiro_adaptado: "Banheiro adaptado", braille: "Sinalização em Braille",
  cardapio_acessivel: "Cardápio acessível", baixo_estimulo_sensorial: "Baixo estímulo sensorial",
  atendimento_preferencial: "Atendimento preferencial real",
};

function preencherOpcoes() {
  const municipios = MUNICIPIOS_GV.map((m) => h("option", { value: m }, m));
  const tipos = Object.entries(TIPOS).map(([valor, rotulo]) => h("option", { value: valor }, rotulo));
  const selecione = () => h("option", { value: "", disabled: true, selected: true }, "Selecione…");
  $("#f-municipio").append(h("option", { value: "" }, "Todos os municípios"), ...municipios.map((o) => o.cloneNode(true)));
  $("#f-tipo").append(h("option", { value: "" }, "Todos os tipos"), ...tipos.map((o) => o.cloneNode(true)));
  $("#l-municipio").append(selecione(), ...municipios);
  $("#l-tipo").append(selecione(), ...tipos);
  Object.entries(RECURSOS).forEach(([valor, rotulo], i) => {
    $("#l-recursos").append(h("div", { class: "check" },
      h("input", { type: "checkbox", id: `recurso-${i}`, name: "recursos", value: valor }),
      h("label", { for: `recurso-${i}` }, rotulo)));
  });
}

async function carregarLocais() {
  const parametros = new URLSearchParams();
  if ($("#f-municipio").value) parametros.set("municipio", $("#f-municipio").value);
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
    h("p", { class: "local__meta" }, `${TIPOS[local.tipo] || local.tipo} · ${local.municipio}`),
    h("p", {}, local.endereco),
    local.recursos_acessibilidade && local.recursos_acessibilidade.length
      ? h("ul", { class: "tags", "aria-label": "Recursos de acessibilidade" },
          local.recursos_acessibilidade.map((r) => h("li", { class: "tag" }, RECURSOS[r] || r)))
      : null,
    local.observacoes ? h("p", { class: "local__obs" }, local.observacoes) : null)));
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
        nome: texto("nome"), municipio: texto("municipio"), endereco: texto("endereco"), tipo: texto("tipo"),
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
  campo.addEventListener("input", ajustarCampo);
  campo.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); formChat.requestSubmit(); }
  });
  $("#btn-nova").addEventListener("click", novaConversa);
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
  if (!rotulo) return;
  link.textContent = `Sair (${rotulo})`;
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
  aplicarVisao();
  carregarBase();
  carregarLocais();
  verificarConta();
  if (new URLSearchParams(window.location.search).get("conta") === "criada") {
    anunciar("Conta criada! Você já está conectado.");
    window.history.replaceState({}, "", window.location.pathname);
  }
});
