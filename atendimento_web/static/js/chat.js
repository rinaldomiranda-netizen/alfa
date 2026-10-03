/* Chat do site (visitante). Sem login: a conversa é identificada por um
   código aleatório guardado só neste navegador. */
"use strict";
(function () {
  const $ = (s) => document.querySelector(s);
  const slug = new URLSearchParams(location.search).get("e") || "";
  const chave = "rmd_chat_" + slug;
  let token = null;
  let ultimo = "";
  let temporizador = null;

  function el(tag, classe, texto) { const e = document.createElement(tag); if (classe) e.className = classe; if (texto !== undefined) e.textContent = texto; return e; }
  function aviso(texto) { const t = el("div", "toast erro", texto); $("#toasts").append(t); setTimeout(() => t.remove(), 6000); }
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
    $("#empresa-nome").textContent = e.empresa_nome || e.nome;
    $("#empresa-sub").textContent = (e.nome_sistema || "Atendimento") + " • online";
    document.title = "Atendimento — " + (e.empresa_nome || e.nome);
    const logo = $("#logo");
    if (e.logo) { const img = el("img", "logo"); img.src = e.logo; img.alt = "Logo"; logo.replaceWith(img); img.id = "logo"; }
    else logo.textContent = (e.empresa_nome || e.nome || "?").split(/\s+/).slice(0, 2).map((p) => p[0]).join("").toUpperCase();
  }
  function hora(iso) { try { return new Date(iso).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" }); } catch (_) { return ""; } }
  function desenhar(estado) {
    const caixa = $("#mensagens");
    caixa.textContent = "";
    estado.mensagens.forEach((m, i) => {
      const b = el("div", "msg " + (m.direcao === "entrada" ? "saida" : "entrada"), m.texto);
      const opcoes = m.payload && m.payload.opcoes;
      if (opcoes && opcoes.length && i === estado.mensagens.length - 1) {
        const linha = el("div", "opcoes-msg");
        opcoes.forEach((o) => { const bt = el("button", "btn pequeno", o); bt.type = "button"; bt.addEventListener("click", () => enviar(o)); linha.append(bt); });
        b.append(linha);
      }
      b.append(el("div", "meta", hora(m.criada_em)));
      caixa.append(b);
    });
    if (estado.status === "resolvido" && estado.avaliacao) caixa.append(el("div", "msg sistema", "Atendimento encerrado. Obrigado!"));
    caixa.scrollTop = caixa.scrollHeight;
    ultimo = JSON.stringify(estado.mensagens.map((m) => m.id));
  }
  async function atualizar() {
    try {
      const estado = await api("/api/publico/conversas/" + encodeURIComponent(token));
      if (JSON.stringify(estado.mensagens.map((m) => m.id)) !== ultimo) desenhar(estado);
    } catch (e) { if (/não encontrada/i.test(e.message)) { try { localStorage.removeItem(chave); } catch (_) { /* ok */ } location.reload(); } }
  }
  function abrirConversa(estado) {
    $("#inicio").hidden = true; $("#conversa").hidden = false;
    desenhar(estado);
    clearInterval(temporizador); temporizador = setInterval(atualizar, 4000);
    $("#texto").focus();
  }
  async function enviar(valor) {
    const campo = $("#texto");
    const texto = (valor || campo.value).trim(); if (!texto) return;
    try { desenhar(await api("/api/publico/conversas/" + encodeURIComponent(token) + "/mensagens", { texto })); campo.value = ""; }
    catch (e) { aviso(e.message); }
  }
  async function comecar() {
    if (!slug) { $("#empresa-nome").textContent = "Link incompleto"; return; }
    try { marca(await api("/api/publico/" + encodeURIComponent(slug) + "/empresa")); }
    catch (e) { $("#empresa-nome").textContent = "Empresa não encontrada"; return; }
    try { token = localStorage.getItem(chave); } catch (_) { token = null; }
    if (token) { try { return abrirConversa(await api("/api/publico/conversas/" + encodeURIComponent(token))); } catch (_) { token = null; } }
    $("#inicio").hidden = false;
  }
  $("#inicio").addEventListener("submit", async (e) => {
    e.preventDefault();
    $("#erro-inicio").textContent = "";
    try {
      const r = await api("/api/publico/" + encodeURIComponent(slug) + "/conversas", { nome: $("#nome").value, telefone: $("#telefone").value, texto: $("#primeira").value });
      token = r.token; try { localStorage.setItem(chave, token); } catch (_) { /* navegador sem armazenamento: a conversa vale até fechar a aba */ }
      abrirConversa(r);
    } catch (x) { $("#erro-inicio").textContent = x.message; }
  });
  $("#enviar").addEventListener("click", () => enviar());
  $("#texto").addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); enviar(); } });
  comecar();
})();
