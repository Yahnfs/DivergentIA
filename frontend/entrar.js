"use strict";

function ligarOlhoSenha() {
  document.querySelectorAll(".campo__olho").forEach((botao) => {
    botao.addEventListener("click", () => {
      const campo = $(`#${botao.dataset.alvo}`);
      const mostrando = campo.type === "text";
      campo.type = mostrando ? "password" : "text";
      botao.textContent = mostrando ? "Mostrar" : "Ocultar";
      botao.setAttribute("aria-label", mostrando ? "Mostrar senha" : "Ocultar senha");
    });
  });
}

async function entrarComCredencial(payload) {
  const status = $("#status-entrar");
  status.textContent = "Entrando…";
  const resposta = await fetch("/auth/login", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
  if (!resposta.ok) throw await erroDaApi(resposta);
  window.location.href = "/";
}

async function entrarComGoogle(credential) {
  const status = $("#status-entrar");
  status.textContent = "Entrando com o Google…";
  try {
    const resposta = await fetch("/auth/login/google", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ credential }) });
    if (!resposta.ok) throw await erroDaApi(resposta);
    window.location.href = "/";
  } catch (erro) {
    status.textContent = `Não foi possível entrar com o Google. ${mensagemDeErro(erro)}`;
  }
}

document.addEventListener("DOMContentLoaded", async () => {
  iniciarComum();
  ligarOlhoSenha();
  await carregarOpcoesConta();
  montarBotaoGoogle("google-btn", entrarComGoogle);
  if (window.__opcoesConta && window.__opcoesConta.google_client_id) $("#divisor-google").hidden = false;
  montarCaptcha("captcha-entrar");

  $("#form-entrar").addEventListener("submit", async (evento) => {
    evento.preventDefault();
    const botao = $("#btn-entrar");
    const status = $("#status-entrar");
    botao.setAttribute("aria-disabled", "true");
    try {
      await entrarComCredencial({
        email: $("#email").value.trim(), senha: $("#senha").value, captcha_token: tokenCaptcha(),
      });
    } catch (erro) {
      status.textContent = mensagemDeErro(erro);
      botao.setAttribute("aria-disabled", "false");
    }
  });
});
