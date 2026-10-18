"use strict";

document.addEventListener("DOMContentLoaded", async () => {
  iniciarComum();
  await carregarOpcoesConta();
  montarCaptcha("captcha-recuperar");

  $("#form-recuperar").addEventListener("submit", async (evento) => {
    evento.preventDefault();
    const botao = $("#btn-recuperar");
    const status = $("#status-recuperar");
    if (estaDesativado(botao)) return;
    botao.setAttribute("aria-disabled", "true");
    status.textContent = "Enviando…";
    try {
      const resposta = await fetch("/auth/recuperar-senha", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: $("#email").value.trim(), captcha_token: tokenCaptcha() }),
      });
      if (!resposta.ok) throw await erroDaApi(resposta);
      const dados = await resposta.json();
      status.textContent = dados.mensagem;
      $("#form-recuperar").querySelectorAll("input, button[type=submit]").forEach((el) => { el.disabled = true; });
    } catch (erro) {
      status.textContent = mensagemDeErro(erro);
      botao.setAttribute("aria-disabled", "false");
    }
  });
});
