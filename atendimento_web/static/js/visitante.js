/* Cartão do visitante / pedido de oração (página pública, sem login). */
"use strict";
(function () {
  const $ = (s) => document.querySelector(s);
  const slug = new URLSearchParams(location.search).get("e") || "";
  const unidade = new URLSearchParams(location.search).get("u") || "";
  async function api(caminho, dados) {
    const cfg = { method: dados ? "POST" : "GET", headers: { "X-RMD": "1" } };
    if (dados) { cfg.headers["Content-Type"] = "application/json"; cfg.body = JSON.stringify(dados); }
    const r = await fetch(caminho, cfg);
    const corpo = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(corpo.erro || "Erro " + r.status);
    return corpo;
  }
  function marca(e) {
    document.documentElement.dataset.tema = e.tema || "alfa";
    if (e.cor_destaque && e.tema !== "contraste") document.documentElement.style.setProperty("--primaria", e.cor_destaque);
    const nome = e.empresa_nome || "Igreja";
    $("#igreja").textContent = nome;
    document.title = "Bem-vindo — " + nome;
    const logo = $("#logo");
    if (e.logo) { const img = document.createElement("img"); img.className = "logo"; img.src = e.logo; img.alt = "Logo"; logo.replaceWith(img); }
    else logo.textContent = nome.split(/\s+/).filter(Boolean).slice(0, 2).map((p) => p[0]).join("").toUpperCase();
  }
  function aba(qual) {
    document.querySelectorAll("[data-aba]").forEach((b) => { const sim = b.dataset.aba === qual; b.classList.toggle("ativo", sim); b.setAttribute("aria-selected", String(sim)); });
    $("#f-visitante").hidden = qual !== "visitante"; $("#f-oracao").hidden = qual !== "oracao"; $("#obrigado").hidden = true;
    document.querySelector(".vis-abas").hidden = false;
  }
  function ler(form) {
    const d = { tipo: form.dataset.tipo };
    if (unidade) d.unidade = unidade;
    form.querySelectorAll("input[name],select[name],textarea[name]").forEach((el) => { if (!el.disabled) d[el.name] = el.type === "checkbox" ? el.checked : el.value.trim(); });
    return d;
  }
  /* Cartão configurado pelo RMD Desenvolvedor: abas, textos e cada campo (ligado, nome, obrigatório). */
  let CONF = null;
  function aplicarCartao(c) {
    if (!c) return;
    CONF = c;
    const t = c.textos || {};
    const abaV = document.querySelector('[data-aba="visitante"]'), abaO = document.querySelector('[data-aba="oracao"]');
    if (t.aba_visitante) abaV.textContent = t.aba_visitante;
    if (t.aba_oracao) abaO.textContent = t.aba_oracao;
    if (t.texto_visitante) $("#f-visitante p.suave").textContent = t.texto_visitante;
    if (t.texto_oracao) $("#f-oracao p.suave").textContent = t.texto_oracao;
    if (t.subtitulo && !unidade) $("#sub").textContent = t.subtitulo;
    abaV.hidden = !c.visitante; abaO.hidden = !c.oracao;
    if (!c.visitante || !c.oracao) document.querySelector(".vis-abas").classList.add("uma-aba");
    for (const [form, lista] of [["#f-visitante", c.campos_visitante || []], ["#f-oracao", c.campos_oracao || []]]) {
      const f = $(form), ligados = Object.fromEntries(lista.map((x) => [x.campo, x]));
      f.querySelectorAll("input[name],select[name],textarea[name]").forEach((el) => {
        if (el.name === "consentimento") return;
        const caixa = el.closest(".campo, .opcao-check"), cfg = ligados[el.name];
        if (!cfg) { if (caixa) caixa.hidden = true; el.disabled = true; el.required = false; return; }
        el.required = !!cfg.obrigatorio;
        if (caixa && caixa.classList.contains("campo")) { const l = caixa.querySelector("label"); if (l) l.textContent = cfg.rotulo + (cfg.obrigatorio ? " *" : ""); }
        else if (caixa) { caixa.lastChild.textContent = " " + cfg.rotulo; }
      });
    }
    if (!c.visitante && c.oracao) aba("oracao");
  }
  function faltando(form, d) {
    const lista = CONF ? (d.tipo === "oracao" ? CONF.campos_oracao : CONF.campos_visitante) : null;
    if (!lista) return d.tipo === "visitante" ? ((!d.nome || !d.telefone) && "Preencha seu nome e WhatsApp.") : (!d.pedido && "Escreva o seu pedido.");
    const f = lista.find((x) => x.obrigatorio && !(d[x.campo] === true || String(d[x.campo] || "").trim()));
    return f ? "Preencha: " + f.rotulo + "." : "";
  }
  async function enviar(ev) {
    ev.preventDefault();
    const form = ev.currentTarget, erro = form.querySelector("[data-erro]"), botao = form.querySelector("button[type=submit]");
    erro.textContent = "";
    const d = ler(form);
    const falta = faltando(form, d);
    if (falta) { erro.textContent = falta; return; }
    if (!d.consentimento) { erro.textContent = "Marque a autorização para enviar."; return; }
    botao.disabled = true;
    try {
      const r = await api("/api/publico/" + encodeURIComponent(slug) + "/cartao", d);
      form.reset(); form.hidden = true; document.querySelector(".vis-abas").hidden = true;
      $("#obrigado-titulo").textContent = d.tipo === "oracao" ? "Pedido recebido 🙏" : "Seja muito bem-vindo! 👋";
      $("#obrigado-texto").textContent = r.mensagem || "Obrigado!";
      $("#obrigado").hidden = false;
      $("#de-novo").onclick = () => aba(CONF && !CONF.visitante ? "oracao" : "visitante");
    } catch (e) { erro.textContent = e.message; }
    finally { botao.disabled = false; }
  }
  document.querySelectorAll("[data-aba]").forEach((b) => b.addEventListener("click", () => aba(b.dataset.aba)));
  document.querySelectorAll(".vis-form").forEach((f) => f.addEventListener("submit", enviar));
  $("#de-novo").addEventListener("click", () => aba("visitante"));
  if (new URLSearchParams(location.search).get("aba") === "oracao") aba("oracao");
  if (!slug) { $("#igreja").textContent = "Link incompleto"; $("#principal").hidden = true; return; }
  if (unidade) api("/api/publico/" + encodeURIComponent(slug) + "/unidade/" + encodeURIComponent(unidade))
    .then((u) => { $("#sub").textContent = u.nome + " • Que alegria ter você aqui!"; }).catch(() => {});
  api("/api/publico/" + encodeURIComponent(slug) + "/empresa").then((e) => { marca(e); aplicarCartao(e.cartao); }).catch(() => { $("#igreja").textContent = "Igreja não encontrada"; $("#principal").hidden = true; });
})();
