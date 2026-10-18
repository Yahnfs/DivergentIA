"use strict";

document.addEventListener("DOMContentLoaded", async () => {
  iniciarComum();
  const alvo = $("#resultado");
  const token = new URLSearchParams(window.location.search).get("token");
  if (!token) {
    alvo.className = "auth__resultado auth__resultado--erro";
    alvo.replaceChildren(icone("alerta"), h("h1", {}, "Link incompleto"), h("p", {}, "Falta o código de confirmação neste link."));
    return;
  }
  try {
    const resposta = await fetch(`/auth/verificar-email?token=${encodeURIComponent(token)}`);
    if (!resposta.ok) throw await erroDaApi(resposta);
    alvo.className = "auth__resultado auth__resultado--ok";
    alvo.replaceChildren(icone("ok"), h("h1", {}, "E-mail confirmado!"), h("p", {}, "Sua conta no DivergentIA está pronta."));
  } catch (erro) {
    alvo.className = "auth__resultado auth__resultado--erro";
    alvo.replaceChildren(icone("alerta"), h("h1", {}, "Não foi possível confirmar"), h("p", {}, mensagemDeErro(erro)));
  }
});
