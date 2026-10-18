"use strict";

/* ===================================================================================================
   Utilidades e menu de acessibilidade, compartilhados pelas telas de conta (entrar, cadastro,
   recuperar/redefinir senha, verificar e-mail). A página principal (index.html) tem sua própria cópia
   em app.js — mantidas separadas de propósito, para esta peça nova não arriscar o que já funciona lá.
   =================================================================================================== */

const $ = (seletor, raiz = document) => raiz.querySelector(seletor);

// Cria elementos sem usar innerHTML: nada que venha de um formulário entra na página como HTML.
function h(tag, atributos = {}, ...filhos) {
  const el = document.createElement(tag);
  for (const [chave, valor] of Object.entries(atributos)) {
    if (valor === false || valor == null) continue;
    if (chave === "class") el.className = valor;
    else el.setAttribute(chave, valor === true ? "" : String(valor));
  }
  for (const filho of filhos.flat(Infinity)) {
    if (filho == null || filho === false) continue;
    el.append(filho);
  }
  return el;
}

function icone(nome, classe = "") {
  const NS = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(NS, "svg");
  svg.setAttribute("class", `icone ${classe}`.trim());
  svg.setAttribute("aria-hidden", "true");
  const uso = document.createElementNS(NS, "use");
  uso.setAttribute("href", `#i-${nome}`);
  svg.append(uso);
  return svg;
}

const guardar = (chave, valor) => { try { localStorage.setItem(chave, valor); } catch (_) { /* ignora */ } };
const ler = (chave) => { try { return localStorage.getItem(chave); } catch (_) { return null; } };

async function erroDaApi(resposta) {
  let detalhe = "";
  try {
    const corpo = await resposta.json();
    if (typeof corpo.detail === "string") detalhe = corpo.detail;
    else if (Array.isArray(corpo.detail) && corpo.detail[0]) detalhe = corpo.detail[0].msg || "";
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

/* ---------- Acessibilidade: tamanho do texto, alto contraste, espaçamento, modo calmo ---------- */

const TAMANHOS = [100, 112.5, 125, 150, 175];
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

// Chamado por cada tela de conta assim que a página carrega.
function iniciarComum() {
  carregarPrefs();
  ligarAcessibilidade();
  aplicarPrefs();
}

/* ---------- Captcha (reCAPTCHA v2): carrega só se o servidor tiver a chave configurada ---------- */

let _captchaPronto = null;

function captchaDisponivel() {
  return !!(window.__opcoesConta && window.__opcoesConta.recaptcha_site_key);
}

function montarCaptcha(containerId) {
  if (!captchaDisponivel()) return;
  const alvo = $(`#${containerId}`);
  if (!alvo) return;
  alvo.hidden = false;
  const render = () => { window.grecaptcha.render(alvo, { sitekey: window.__opcoesConta.recaptcha_site_key }); };
  if (window.grecaptcha && window.grecaptcha.render) { render(); return; }
  const script = document.createElement("script");
  script.src = "https://www.google.com/recaptcha/api.js?onload=__dvCaptchaCarregado&render=explicit";
  script.async = true;
  script.defer = true;
  window.__dvCaptchaCarregado = render;
  document.head.append(script);
}

function tokenCaptcha() {
  if (!captchaDisponivel() || !window.grecaptcha) return null;
  try { return window.grecaptcha.getResponse() || null; } catch (_) { return null; }
}

/* ---------- Botão "Entrar com Google": carrega só se o servidor tiver o client_id configurado ---------- */

function montarBotaoGoogle(containerId, aoReceberCredencial) {
  const alvo = $(`#${containerId}`);
  if (!alvo || !window.__opcoesConta || !window.__opcoesConta.google_client_id) return;
  alvo.hidden = false;
  const iniciar = () => {
    window.google.accounts.id.initialize({
      client_id: window.__opcoesConta.google_client_id,
      callback: (resposta) => aoReceberCredencial(resposta.credential),
    });
    window.google.accounts.id.renderButton(alvo, { theme: "outline", size: "large", text: "continue_with", locale: "pt-BR", width: 320 });
  };
  if (window.google && window.google.accounts) { iniciar(); return; }
  const script = document.createElement("script");
  script.src = "https://accounts.google.com/gsi/client";
  script.async = true;
  script.defer = true;
  script.onload = iniciar;
  document.head.append(script);
}

// Busca, uma vez por página, se o Google/captcha estão configurados neste servidor.
async function carregarOpcoesConta() {
  try {
    const resposta = await fetch("/auth/opcoes");
    window.__opcoesConta = resposta.ok ? await resposta.json() : {};
  } catch (_) {
    window.__opcoesConta = {};
  }
  return window.__opcoesConta;
}
