"use strict";

function ligarOlhoSenha() {
  document.querySelectorAll(".campo__olho").forEach((botao) => {
    botao.addEventListener("click", () => {
      const campo = $(`#${botao.dataset.alvo}`);
      const mostrando = campo.type === "text";
      campo.type = mostrando ? "password" : "text";
      botao.textContent = mostrando ? "Mostrar" : "Ocultar";
    });
  });
}

document.addEventListener("DOMContentLoaded", () => {
  iniciarComum();
  ligarOlhoSenha();

  const token = new URLSearchParams(window.location.search).get("token");
  const status = $("#status-redefinir");
  if (!token) {
    status.textContent = "Link inválido: falta o código de redefinição. Peça um novo link em “Esqueci minha senha”.";
    $("#form-redefinir").querySelectorAll("input, button").forEach((el) => { el.disabled = true; });
    return;
  }

  $("#form-redefinir").addEventListener("submit", async (evento) => {
    evento.preventDefault();
    const botao = $("#btn-redefinir");
    if (estaDesativado(botao)) return;
    if ($("#nova-senha").value !== $("#confirmar-senha").value) {
      status.textContent = "As duas senhas precisam ser iguais.";
      $("#confirmar-senha").focus();
      return;
    }
    botao.setAttribute("aria-disabled", "true");
    status.textContent = "Salvando…";
    try {
      const resposta = await fetch("/auth/redefinir-senha", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token, nova_senha: $("#nova-senha").value }),
      });
      if (!resposta.ok) throw await erroDaApi(resposta);
      status.textContent = "Senha redefinida! Você já pode entrar com a nova senha.";
      $("#form-redefinir").querySelectorAll("input, button").forEach((el) => { el.disabled = true; });
    } catch (erro) {
      status.textContent = mensagemDeErro(erro);
      botao.setAttribute("aria-disabled", "false");
    }
  });
});
