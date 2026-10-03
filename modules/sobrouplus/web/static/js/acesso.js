/* Sobrou+ — primeiro acesso pelo link que o desenvolvedor/empresa enviou: a pessoa cria a própria senha e já entra na área dela. */
"use strict";
(async function () {
  const h = S.h, tela = document.getElementById("tela");
  const token = new URLSearchParams(location.search).get("c") || "";
  const destino = (papel) => papel === "cliente" ? "./" : papel === "entregador" ? "entregador" : "painel";
  let c;
  try { c = await S.api("/api/convite/" + encodeURIComponent(token)); } catch (e) {
    S.limpar(tela, h("div", { class: "cartao" }, h("h1", {}, "Link de acesso"), h("p", {}, e.message), h("a", { class: "btn btn-linha", href: "./" }, "Ir para o Sobrou+")));
    return;
  }
  const s1 = h("input", { type: "password", autocomplete: "new-password", minlength: "8", required: true });
  const s2 = h("input", { type: "password", autocomplete: "new-password", minlength: "8", required: true });
  const aceite = h("input", { type: "checkbox" });
  const botao = h("button", { class: "btn btn-cta", type: "submit", style: { width: "100%" } }, "Criar senha e entrar");
  const form = h("form", { onsubmit: async (ev) => {
    ev.preventDefault();
    if (s1.value !== s2.value) { S.toast("As duas senhas não são iguais.", true); return; }
    if (!aceite.checked) { S.toast("Marque que leu e aceita os Termos e a Política de Privacidade.", true); return; }
    botao.disabled = true;
    try {
      const r = await S.api("/api/convite/" + encodeURIComponent(token), { corpo: { senha: s1.value, aceite_termos: true } });
      S.toast("Tudo certo! Abrindo a sua área…");
      setTimeout(() => location.replace(destino(r.usuario.papel)), 800);
    } catch (e) { S.toast(e.message, true); botao.disabled = false; }
  } },
    h("label", {}, "Crie sua senha (mínimo 8 caracteres, com letras e números)", s1),
    h("label", {}, "Repita a senha", s2),
    h("label", { class: "aceite" }, aceite, h("span", {}, "Li e aceito os ", h("a", { href: "termos", target: "_blank" }, "Termos de Uso"), " e a ",
      h("a", { href: "privacidade", target: "_blank" }, "Política de Privacidade"), ".")),
    botao);
  S.limpar(tela, h("div", { class: "cartao" },
    h("h1", {}, `Olá, ${c.nome.split(" ")[0]}!`),
    h("p", {}, "Você foi cadastrado(a) no Sobrou+ como ", h("b", {}, c.papel_nome || "usuário"), c.empresa ? [" em ", h("b", {}, c.empresa)] : "", "."),
    h("p", { class: "mudo" }, `Seu login é o e-mail ${c.email}. Agora é só criar a sua senha.`), form));
  S.iniciarApp();
})();
