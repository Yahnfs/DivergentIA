"use strict";

const SEXO = ["Feminino", "Masculino", "Prefiro não informar"];

const ETNIA = ["Branca", "Preta", "Parda", "Amarela", "Indígena", "Prefiro não informar"];

const ESCOLARIDADE = [
  "Não alfabetizado(a)", "Fundamental incompleto", "Fundamental completo", "Médio incompleto",
  "Médio completo", "Superior incompleto", "Superior completo", "Pós-graduação", "Prefiro não informar",
];

const FAIXAS_RENDA = [
  "Sem renda própria", "Até 1 salário mínimo", "De 1 a 2 salários mínimos", "De 2 a 3 salários mínimos",
  "De 3 a 5 salários mínimos", "De 5 a 10 salários mínimos", "Mais de 10 salários mínimos", "Prefiro não informar",
];

const UFS = [
  ["AC", "Acre"], ["AL", "Alagoas"], ["AP", "Amapá"], ["AM", "Amazonas"], ["BA", "Bahia"], ["CE", "Ceará"],
  ["DF", "Distrito Federal"], ["ES", "Espírito Santo"], ["GO", "Goiás"], ["MA", "Maranhão"], ["MT", "Mato Grosso"],
  ["MS", "Mato Grosso do Sul"], ["MG", "Minas Gerais"], ["PA", "Pará"], ["PB", "Paraíba"], ["PR", "Paraná"],
  ["PE", "Pernambuco"], ["PI", "Piauí"], ["RJ", "Rio de Janeiro"], ["RN", "Rio Grande do Norte"],
  ["RS", "Rio Grande do Sul"], ["RO", "Rondônia"], ["RR", "Roraima"], ["SC", "Santa Catarina"],
  ["SP", "São Paulo"], ["SE", "Sergipe"], ["TO", "Tocantins"],
];

// Categorias oficiais de deficiência/condição, para a análise de dados da extensão.
const CONDICOES = {
  deficiencia_fisica: "Deficiência física (ex.: cadeirante, amputação, limitação motora, nanismo)",
  deficiencia_visual: "Deficiência visual (cegueira total ou baixa visão)",
  deficiencia_auditiva: "Deficiência auditiva (surdez total, parcial ou limitação severa de audição)",
  deficiencia_intelectual: "Deficiência intelectual (limitação no funcionamento intelectual e comportamento adaptativo)",
  deficiencia_mental_psicossocial: "Deficiência mental/psicossocial (ex.: esquizofrenia)",
  tea: "Transtorno do Espectro Autista (TEA)",
  deficiencia_multipla: "Deficiência múltipla (associação de duas ou mais deficiências)",
  nenhuma: "Nenhuma / não se aplica (ex.: sou cuidador(a) ou familiar)",
  prefiro_nao_informar: "Prefiro não informar",
};

function preencherSelect(id, opcoes, { comPlaceholder = true } = {}) {
  const select = $(`#${id}`);
  if (comPlaceholder) select.append(h("option", { value: "", selected: true }, "Selecione…"));
  for (const opcao of opcoes) {
    const [valor, rotulo] = Array.isArray(opcao) ? opcao : [opcao, opcao];
    select.append(h("option", { value: valor }, rotulo));
  }
}

function preencherFormulario() {
  preencherSelect("sexo", SEXO);
  preencherSelect("etnia", ETNIA);
  preencherSelect("escolaridade", ESCOLARIDADE);
  preencherSelect("renda", FAIXAS_RENDA);
  preencherSelect("renda-familiar", FAIXAS_RENDA);
  preencherSelect("estado", UFS);
  const fieldset = $("#condicoes");
  Object.entries(CONDICOES).forEach(([valor, rotulo], i) => {
    fieldset.append(h("div", { class: "check" },
      h("input", { type: "checkbox", id: `cond-${i}`, name: "condicoes", value: valor }),
      h("label", { for: `cond-${i}` }, rotulo)));
  });
}

async function carregarTermo() {
  const alvo = $("#termo-lgpd");
  try {
    const resposta = await fetch("/auth/termo-lgpd");
    if (!resposta.ok) throw await erroDaApi(resposta);
    const dados = await resposta.json();
    alvo.textContent = dados.texto;
    alvo.dataset.versao = dados.versao;
  } catch (_) {
    alvo.textContent = "Não foi possível carregar o termo agora. Recarregue a página antes de continuar.";
  }
}

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

async function enviarCadastro(evento) {
  evento.preventDefault();
  const status = $("#status-cadastro");
  const botao = $("#btn-cadastrar");
  if (estaDesativado(botao)) return;

  if ($("#senha").value !== $("#confirmar-senha").value) {
    status.textContent = "As duas senhas precisam ser iguais.";
    $("#confirmar-senha").focus();
    return;
  }
  if (!$("#aceite-lgpd").checked) {
    status.textContent = "É preciso aceitar o termo de consentimento para criar a conta.";
    $("#aceite-lgpd").focus();
    return;
  }

  const dados = new FormData(evento.currentTarget);
  const texto = (campo) => String(dados.get(campo) || "").trim();
  const numero = (campo) => (dados.get(campo) ? Number(dados.get(campo)) : null);

  botao.setAttribute("aria-disabled", "true");
  status.textContent = "Criando sua conta…";
  try {
    const resposta = await fetch("/auth/cadastro", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email: texto("email"), senha: dados.get("senha"), captcha_token: tokenCaptcha(),
        nome_completo: texto("nome_completo"), ano_nascimento: numero("ano_nascimento"),
        sexo: texto("sexo") || null, etnia: texto("etnia") || null, cpf_rg: texto("cpf_rg") || null,
        estado: texto("estado") || null, cidade: texto("cidade") || null, endereco: texto("endereco") || null,
        grau_escolaridade: texto("grau_escolaridade") || null, integrantes_familia: numero("integrantes_familia"),
        renda_faixa: texto("renda_faixa") || null, renda_familiar_faixa: texto("renda_familiar_faixa") || null,
        condicoes_acessibilidade: dados.getAll("condicoes"),
        aceite_lgpd: $("#aceite-lgpd").checked,
      }),
    });
    if (!resposta.ok) throw await erroDaApi(resposta);
    window.location.href = "/?conta=criada";
  } catch (erro) {
    status.textContent = mensagemDeErro(erro);
    botao.setAttribute("aria-disabled", "false");
  }
}

document.addEventListener("DOMContentLoaded", async () => {
  iniciarComum();
  preencherFormulario();
  ligarOlhoSenha();
  carregarTermo();
  await carregarOpcoesConta();
  montarBotaoGoogle("google-btn", (credential) => {
    // Cadastro rápido com Google: a conta é criada no login (sem senha); os campos do formulário
    // continuam disponíveis depois, no perfil, para quem quiser completá-los.
    fetch("/auth/login/google", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ credential }) })
      .then(async (resposta) => { if (!resposta.ok) throw await erroDaApi(resposta); window.location.href = "/?conta=criada"; })
      .catch((erro) => { $("#status-cadastro").textContent = mensagemDeErro(erro); });
  });
  if (window.__opcoesConta && window.__opcoesConta.google_client_id) $("#divisor-google").hidden = false;
  montarCaptcha("captcha-cadastro");
  $("#form-cadastro").addEventListener("submit", enviarCadastro);
});
