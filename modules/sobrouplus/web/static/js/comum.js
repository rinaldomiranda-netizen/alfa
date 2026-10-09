/* Sobrou+ — funções comuns às três telas (consumidor, painel, entregador). */
"use strict";
// Quando o Sobrou+ é servido dentro de outro endereço (ex.: https://…/sobrou/), tudo é prefixado.
// Cada aplicativo instalável tem o seu endereço (/apps/caixa/, /apps/loja/...): tudo continua dentro dele.
const APP_SOBROU = (location.pathname.match(/\/apps\/(central|loja|caixa|entregador|cliente)(?=\/|$)/) || [])[1] || "";
const BASE_SOBROU = (location.pathname.startsWith("/sobrou") ? "/sobrou" : "") + (APP_SOBROU ? "/apps/" + APP_SOBROU : "");
const S = {
  u(caminho) { return caminho && caminho.startsWith("/") ? BASE_SOBROU + caminho : caminho; },
  async api(caminho, opcoes = {}) {
    caminho = S.u(caminho);
    const o = { method: opcoes.method || (opcoes.corpo ? "POST" : "GET"), headers: {}, credentials: "same-origin" };
    if (opcoes.corpo !== undefined) { o.headers["Content-Type"] = "application/json"; o.body = JSON.stringify(opcoes.corpo); }
    let r;
    try { r = await fetch(caminho, o); } catch (e) { throw new Error("Sem conexão com o servidor."); }
    let dados = {};
    try { dados = await r.json(); } catch (e) { /* resposta vazia */ }
    if (!r.ok) { const err = new Error(dados.erro || `Erro ${r.status}`); err.status = r.status; err.dados = dados; throw err; }
    return dados;
  },
  qs(obj) { const p = new URLSearchParams(); Object.entries(obj || {}).forEach(([k, v]) => { if (v !== undefined && v !== null && v !== "") p.set(k, v); }); const s = p.toString(); return s ? "?" + s : ""; },
  dinheiro(c) { return ((c || 0) / 100).toLocaleString("pt-BR", { style: "currency", currency: "BRL" }); },
  reais(c) { return c === null || c === undefined ? "" : ((c || 0) / 100).toFixed(2).replace(".", ","); },
  hora(iso) { return iso ? new Date(iso).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" }) : "—"; },
  data(iso) { return iso ? new Date(iso).toLocaleString("pt-BR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" }) : "—"; },
  janela(i, f) { return i && f ? `${S.hora(i)}–${S.hora(f)}` : "—"; },
  // valor para <input type="datetime-local"> no horário do aparelho
  paraInput(iso) { if (!iso) return ""; const d = new Date(iso); const z = (n) => String(n).padStart(2, "0");
    return `${d.getFullYear()}-${z(d.getMonth() + 1)}-${z(d.getDate())}T${z(d.getHours())}:${z(d.getMinutes())}`; },
  doInput(v) { return v ? new Date(v).toISOString() : null; },
  kg(n) { return (n || 0).toLocaleString("pt-BR", { maximumFractionDigits: 1 }) + " kg"; },

  /* cria elemento: S.h("div", {class: "x", onclick: fn}, filhos...) — texto sempre como texto (sem HTML injetado) */
  h(tag, attrs, ...filhos) {
    const e = document.createElement(tag);
    Object.entries(attrs || {}).forEach(([k, v]) => {
      if (v === null || v === undefined || v === false) return;
      if (k.startsWith("on")) e.addEventListener(k.slice(2), v);
      else if (k === "class") e.className = v;
      else if (k === "style" && typeof v === "object") Object.entries(v).forEach(([p, val]) => e.style.setProperty(p, val));
      else if (k === "value") e.value = v;
      else if (v === true) e.setAttribute(k, "");
      else e.setAttribute(k, v);
    });
    filhos.flat(Infinity).forEach((f) => { if (f === null || f === undefined || f === false) return; e.append(f instanceof Node ? f : document.createTextNode(String(f))); });
    return e;
  },
  limpar(el, ...filhos) { el.replaceChildren(); filhos.flat(Infinity).forEach((f) => f && el.append(f)); return el; },

  toast(msg, erro) {
    let t = document.getElementById("toast");
    if (!t) { t = S.h("div", { id: "toast" }); document.body.append(t); }
    t.textContent = msg; t.className = erro ? "erro" : ""; t.classList.remove("oculto");
    clearTimeout(S._tt); S._tt = setTimeout(() => t.classList.add("oculto"), erro ? 5000 : 2600);
  },
  async acao(fn, okMsg) {
    try { const r = await fn(); if (okMsg) S.toast(okMsg); return r; }
    catch (e) { S.toast(e.message, true); throw e; }
  },

  tema(t) { document.documentElement.dataset.tema = ["claro", "medio", "escuro"].includes(t) ? t : "claro"; },

  /* logo oficial aprovada (static/img/logo.png). Enquanto o arquivo não chega: espaço marcado "logo oficial pendente". */
  /* logo oficial (static/img). fundo "escuro" = barra verde (versão clara da logo); "claro" = cartão (logo completa com slogan). */
  marca(cfg, nomeExtra, fundo = "escuro") {
    const caixa = S.h("div", { class: "marca" + (fundo === "claro" ? " marca-grande" : "") });
    const temaEscuro = document.documentElement.dataset.tema === "escuro";
    const repetido = nomeExtra && /^sobrou\+?$/i.test(nomeExtra.trim());
    if (cfg && cfg.logo) {
      if (fundo === "claro") {
        caixa.append(S.h("img", { src: temaEscuro ? "static/img/logo-clara.png" : "static/img/logo.png", alt: "Sobrou+ — Boa comida. Mais valor. Menos desperdício." }));
        if (nomeExtra && !repetido) caixa.append(S.h("div", { class: "nome-marca" }, nomeExtra));
        return caixa;
      }
      caixa.append(S.h("img", { src: "static/img/logo-marca-clara.png", alt: "Sobrou+" }));
    } else caixa.append(S.h("div", { class: "logo-pendente" }, "logo oficial", S.h("br"), "pendente"));
    const txt = S.h("div", { style: { "min-width": "0" } });
    if (nomeExtra && !(repetido && cfg && cfg.logo)) txt.append(S.h("div", { class: "nome-marca" }, nomeExtra));
    txt.append(S.h("div", { class: "slogan" }, (cfg && cfg.slogan) || "Boa comida. Mais valor. Menos desperdício."));
    caixa.append(txt);
    return caixa;
  },

  folha(conteudo, aoFechar) {
    const veu = S.h("div", { class: "veu" });
    const f = S.h("div", { class: "folha" }, conteudo);
    veu.append(f);
    const fechar = () => { veu.remove(); if (aoFechar) aoFechar(); };
    veu.addEventListener("click", (e) => { if (e.target === veu) fechar(); });
    document.body.append(veu);
    return { fechar, el: f };
  },

  /* foto: comprime no navegador — principal até 1280 px e miniatura 400 px (JPEG) */
  async comprimir(arquivo) {
    const url = URL.createObjectURL(arquivo);
    try {
      const img = await new Promise((ok, erro) => { const i = new Image(); i.onload = () => ok(i); i.onerror = () => erro(new Error("Não consegui abrir a foto.")); i.src = url; });
      const gerar = (max, q) => { const esc = Math.min(1, max / Math.max(img.width, img.height));
        const c = document.createElement("canvas"); c.width = Math.round(img.width * esc); c.height = Math.round(img.height * esc);
        c.getContext("2d").drawImage(img, 0, 0, c.width, c.height); return c.toDataURL("image/jpeg", q); };
      return { imagem: gerar(1280, 0.82), miniatura: gerar(400, 0.75) };
    } finally { URL.revokeObjectURL(url); }
  },

  qr(texto, tam = 6) { const q = qrcode(0, "M"); q.addData(texto); q.make(); return S.h("img", { src: q.createDataURL(tam, 2), alt: "QR Code do pedido", style: { "image-rendering": "pixelated" } }); },

  posicao() {
    return new Promise((ok, erro) => {
      if (!navigator.geolocation) return erro(new Error("Este aparelho não informa a localização."));
      navigator.geolocation.getCurrentPosition((p) => ok({ lat: p.coords.latitude, lng: p.coords.longitude, precisao: p.coords.accuracy }),
        () => erro(new Error("Localização não permitida. Ative a localização para ver as ofertas por distância.")), { enableHighAccuracy: true, timeout: 12000, maximumAge: 60000 });
    });
  },

  CATEGORIAS: { todos: "Todos", refeicoes: "Refeições", padaria: "Padaria", frutas: "Frutas", verduras: "Verduras", mercado: "Mercado",
    pizza: "Pizza", cafe: "Café", doces: "Doces", sushi: "Sushi", bebidas: "Bebidas", cesta_surpresa: "Cesta surpresa", outros: "Outros" },
  SELO_PEDIDO: { aguardando_pagamento: "aviso", pago: "ok", recebido: "ok", preparando: "oferta", pronto: "ok", aguardando_retirada: "oferta",
    aguardando_entregador: "aviso", entregador_designado: "ok", em_coleta: "oferta", em_rota: "oferta", entregue: "ok", retirado: "ok",
    concluido: "ok", cancelado: "urgente", nao_retirado: "urgente", expirado: "urgente", destinado: "ok" },
  selo(texto, tipo) { return S.h("span", { class: "selo " + (tipo || "") }, texto); },

  /* ---------------- mapas (Leaflet + OpenStreetMap) ---------------- */
  CENTRO_PADRAO: [-10.9111, -37.0717],
  mapa(el, centro, zoom = 14) {
    if (typeof L === "undefined") { el.textContent = "Mapa indisponível."; return null; }
    const m = L.map(el, { scrollWheelZoom: false, attributionControl: true }).setView(centro || S.CENTRO_PADRAO, zoom);
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", { maxZoom: 19, attribution: "© OpenStreetMap", referrerPolicy: "strict-origin-when-cross-origin" }).addTo(m);
    setTimeout(() => m.invalidateSize(), 200);
    return m;
  },
  pino(cor, letra) {
    return L.divIcon({ className: "", iconSize: [30, 38], iconAnchor: [15, 36], popupAnchor: [0, -32],
      html: `<div class="pino" style="--c:${cor}"><span>${letra || ""}</span></div>` });
  },
  marcar(m, lat, lng, cor, letra, texto) {
    if (!m || lat === null || lat === undefined) return null;
    const mk = L.marker([lat, lng], { icon: S.pino(cor, letra) }).addTo(m);
    if (texto) mk.bindPopup(document.createTextNode(texto));
    return mk;
  },
  async desenharRota(m, de, para, cor = "#F57A20") {
    if (!m || !de || !para || de[0] === null || para[0] === null) return null;
    try {
      const r = await S.api(`/api/mapa/rota?de=${de[0]},${de[1]}&para=${para[0]},${para[1]}`);
      if (r.fonte !== "ruas" || !r.linha || !r.linha.length) {
        S.toast("Rota pelas ruas indisponível agora. Abra Google Maps ou Waze para navegar.", true);
        return r;
      }
      L.polyline(r.linha, { color: cor, weight: 5, opacity: .85 }).addTo(m);
      m.fitBounds(L.latLngBounds(r.linha).pad(0.25));
      return r;
    } catch (e) { return null; }
  },
  enquadrar(m, pontos) { const v = pontos.filter((p) => p && p[0] !== null && p[0] !== undefined); if (m && v.length) { if (v.length === 1) m.setView(v[0], 15); else m.fitBounds(L.latLngBounds(v).pad(0.2)); } },
  textoRota(r) { if (!r) return ""; return `${r.km.toLocaleString("pt-BR")} km · ~${r.minutos} min ${r.fonte === "ruas" ? "pelas ruas" : "(estimativa)"}`; },

  /* busca de endereço: campo + lista de resultados; chama aoEscolher({nome, lat, lng}) */
  buscaEndereco(aoEscolher, valor = "") {
    const campo = S.h("input", { placeholder: "Rua, número, bairro, cidade", value: valor });
    const lista = S.h("div", { class: "resultados-end" });
    const buscar = async () => {
      if (campo.value.trim().length < 4) return S.toast("Digite rua e cidade.", true);
      S.limpar(lista, S.h("div", { class: "mudo" }, "Buscando…"));
      try {
        const r = await S.api("/api/mapa/buscar" + S.qs({ q: campo.value.trim() }));
        if (!r.itens.length) return S.limpar(lista, S.h("div", { class: "mudo" }, "Nada encontrado. Tente com o nome da cidade."));
        S.limpar(lista, r.itens.map((it) => S.h("button", { type: "button", class: "item-end", onclick: () => { S.limpar(lista); campo.value = it.nome; aoEscolher(it); } }, it.nome)));
      } catch (e) { S.limpar(lista, S.h("div", { class: "mudo" }, e.message)); }
    };
    campo.addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); buscar(); } });
    return S.h("div", { class: "busca-end" }, S.h("div", { class: "linha" }, campo, S.h("button", { type: "button", class: "btn btn-escuro btn-p", style: { flex: "0 0 auto" }, onclick: buscar }, "Buscar")), lista);
  },
};

/* ---------------- app instalável, atualização automática e aviso no celular ---------------- */
S.versao = null;
S.iniciarApp = function () {
  if (S._iniciado) return;
  S._iniciado = true;
  S.barraInstalar();
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register(S.u("/sw.js")).catch(() => null);
  }
  // Atualização automática: quando o servidor tem versão nova, a tela recarrega sozinha (sem perder o que está digitando).
  const conferir = async () => {
    try {
      const r = await fetch(S.u("/api/saude"), { cache: "no-store" }).then((x) => x.json());
      if (S.versao && r.versao !== S.versao) {
        const digitando = document.activeElement && ["INPUT", "TEXTAREA"].includes(document.activeElement.tagName) && document.activeElement.value;
        if (!digitando) { S.toast("Sobrou+ atualizado. Abrindo a versão nova…"); setTimeout(() => location.reload(), 1200); return; }
      }
      S.versao = r.versao;
    } catch (e) { /* sem internet: tenta depois */ }
  };
  conferir(); setInterval(conferir, 5 * 60 * 1000);
  document.addEventListener("visibilitychange", () => { if (!document.hidden) conferir(); });
};
/* ---------------- instalar o aplicativo (cada perfil é um app separado no celular) ---------------- */
S.app = APP_SOBROU;
S.NOMES_APPS = { central: "Sobrou+ Central", loja: "Sobrou+ Loja", caixa: "Sobrou+ Caixa", entregador: "Sobrou+ Entregador", cliente: "Sobrou+ Cliente" };
let pedidoInstalar = null;
window.addEventListener("beforeinstallprompt", (e) => { e.preventDefault(); pedidoInstalar = e; S.barraInstalar(); });
window.addEventListener("appinstalled", () => { pedidoInstalar = null; const b = document.getElementById("barra-instalar"); if (b) b.remove(); S.toast("Instalado! Procure o ícone na tela do celular."); });
S.barraInstalar = function () {
  if (!S.app) return;
  const instalado = window.matchMedia("(display-mode: standalone)").matches || navigator.standalone === true;
  let fechado = false;
  try { fechado = sessionStorage.getItem("sob_instalar_fechado") === "1"; } catch (e) { /* sem armazenamento */ }
  const antiga = document.getElementById("barra-instalar");
  if (antiga) antiga.remove();
  if (instalado || fechado) return;
  const nome = S.NOMES_APPS[S.app];
  const iphone = /iphone|ipad|ipod/i.test(navigator.userAgent) && !window.MSStream;
  const fechar = S.h("button", { class: "btn btn-p", style: { background: "transparent", color: "#fff", border: "2px solid #fff" }, "aria-label": "Fechar", onclick: () => { try { sessionStorage.setItem("sob_instalar_fechado", "1"); } catch (e) {} barra.remove(); } }, "Agora não");
  let acao;
  if (pedidoInstalar) {
    acao = S.h("button", { class: "btn btn-p btn-cta", onclick: async () => { pedidoInstalar.prompt(); try { await pedidoInstalar.userChoice; } catch (e) {} pedidoInstalar = null; } }, "Instalar " + nome);
  } else if (iphone) {
    acao = S.h("span", {}, "No iPhone: toque em ", S.h("b", {}, "Compartilhar"), " (quadrado com seta) e depois em ", S.h("b", {}, "Adicionar à Tela de Início"), ".");
  } else {
    acao = S.h("span", {}, "Para instalar: abra o menu do navegador (⋮) e toque em ", S.h("b", {}, "Instalar app"), " ou ", S.h("b", {}, "Adicionar à tela inicial"), ".");
  }
  const barra = S.h("div", { id: "barra-instalar", role: "region", "aria-label": "Instalar o aplicativo",
    style: { position: "fixed", left: "0", right: "0", bottom: "0", "z-index": "9999", background: "#0A563A", color: "#fff", padding: ".7rem 1rem",
      display: "flex", gap: ".6rem", "align-items": "center", "flex-wrap": "wrap", "box-shadow": "0 -4px 16px rgba(0,0,0,.25)", "font-size": ".95rem" } },
    S.h("img", { src: `static/img/apps/${S.app}-192.png`, alt: "", style: { width: "40px", height: "40px", "border-radius": "10px" } }),
    S.h("div", { style: { flex: "1", "min-width": "180px" } }, S.h("b", {}, nome), S.h("div", {}, acao)), fechar);
  document.body.append(barra);
};

S.avisosSuportados = () => "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;
S.ligarAvisos = async function () {
  if (!S.avisosSuportados()) throw new Error("Este aparelho/navegador não aceita aviso com o app fechado. No iPhone, primeiro adicione o Sobrou+ à Tela de Início.");
  const { chave } = await S.api("/api/push/chave");
  if (!chave) throw new Error("Aviso no celular ainda não está disponível neste servidor.");
  const perm = await Notification.requestPermission();
  if (perm !== "granted") throw new Error("Permissão de notificação negada. Libere nas configurações do navegador.");
  const reg = await navigator.serviceWorker.ready;
  const bin = Uint8Array.from(atob(chave.replace(/-/g, "+").replace(/_/g, "/") + "=".repeat((4 - chave.length % 4) % 4)), (c) => c.charCodeAt(0));
  const sub = await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: bin });
  await S.api("/api/push/inscrever", { corpo: sub.toJSON() });
  return true;
};
S.botaoAvisos = function () {
  if (!S.avisosSuportados()) return null;
  const b = S.h("button", { class: "btn btn-linha btn-p", onclick: async () => {
    try { await S.ligarAvisos(); S.toast("Pronto! Você vai receber os avisos no celular."); b.textContent = "Avisos no celular ligados ✓"; } catch (e) { S.toast(e.message, true); } } },
    Notification.permission === "granted" ? "Avisos no celular ligados ✓" : "Ligar avisos no celular");
  return b;
};

/* ---------------- esqueci minha senha (código de 6 números) ---------------- */
S.esqueciSenha = function (emailInicial = "") {
  const email = S.h("input", { type: "email", value: emailInicial, autocomplete: "email" });
  const codigo = S.h("input", { inputmode: "numeric", maxlength: 6, placeholder: "6 números" });
  const nova = S.h("input", { type: "password", autocomplete: "new-password" });
  const passo2 = S.h("div", { class: "oculto" }, S.h("label", {}, "Código recebido"), codigo, S.h("label", {}, "Nova senha (8+ caracteres, letras e números)"), nova,
    S.h("button", { class: "btn btn-verde btn-bloco", style: { "margin-top": ".8rem" }, onclick: async () => {
      await S.acao(() => S.api("/api/senha/codigo", { corpo: { email: email.value.trim(), codigo: codigo.value.trim(), nova: nova.value } }), "Senha trocada! Entre com a nova senha.");
      f.fechar(); } }, "Salvar nova senha"));
  const f = S.folha(S.h("div", {}, S.h("h2", {}, "Esqueci minha senha"), S.h("p", { class: "mudo" }, "Vamos mandar um código para o seu e-mail (ou WhatsApp cadastrado)."),
    S.h("label", {}, "E-mail da conta"), email,
    S.h("button", { class: "btn btn-cta btn-bloco", style: { "margin-top": ".8rem" }, onclick: async () => {
      const r = await S.acao(() => S.api("/api/senha/esqueci", { corpo: { email: email.value.trim() } }));
      S.toast(r.mensagem, !r.ok); if (r.ok) passo2.classList.remove("oculto"); } }, "Enviar código"), passo2));
};

/* ---------------- link de acesso (convite) ---------------- */
S.mostrarConvite = async function (c) {
  let cfg = {};
  try { cfg = await S.api("/api/config"); } catch (e) {}
  // A URL atual do servidor tem prioridade; convites antigos podem conter endereço obsoleto.
  const origem = (cfg.url_acesso || c.url_acesso || location.origin || "").replace(/\/+$/, "");
  const caminho = String(c.caminho || "").startsWith("/") ? c.caminho : "/" + String(c.caminho || "");
  const link = origem + caminho;
  const msg = link;
  const token = new URL(c.caminho || "", location.origin).searchParams.get("c") || "";
  const tel = (c.telefone || "").replace(/\D/g, "");
  const telIntl = tel ? (tel.startsWith("55") ? tel : (tel.length === 10 || tel.length === 11 ? "55" + tel : tel)) : "";
  const wa = "https://wa.me/" + telIntl + "?text=" + encodeURIComponent(msg);
  const email = `mailto:${encodeURIComponent(c.email || "")}?subject=${encodeURIComponent("Seu acesso ao Sobrou+")}&body=${encodeURIComponent(msg)}`;

  const whatsapp = S.h("button", { class: "btn btn-verde", onclick: async () => {
    try {
      const r = await S.api(`/api/usuarios/${encodeURIComponent(c.usuario_id || "")}/convite/whatsapp`, { corpo: { token, url_acesso: origem } });
      S.toast(r.mensagem || "Link enviado pelo WhatsApp.");
    } catch (e) {
      const janela = window.open(wa, "_blank", "noopener,noreferrer");
      if (!janela) location.href = wa;
      S.toast("WhatsApp aberto com a mensagem pronta. Confira o destinatário e toque em Enviar.");
    }
  } }, "Enviar por WhatsApp");

  const emailBotao = S.h("button", { class: "btn btn-linha", onclick: async () => {
    try {
      const r = await S.api(`/api/usuarios/${encodeURIComponent(c.usuario_id || "")}/convite/email`, { corpo: { token, url_acesso: origem } });
      S.toast(r.mensagem || "E-mail enviado.");
    } catch (e) {
      location.href = email;
      S.toast("Seu aplicativo de e-mail foi aberto com o link pronto para envio.");
    }
  } }, "Enviar por e-mail");

  S.folha(S.h("div", {}, S.h("h2", {}, "Link de acesso pronto"),
    S.h("p", {}, `Envie para ${c.nome} (${c.papel_nome}). A pessoa abre, cria a própria senha e já entra. O link vale ${c.validade_dias} dias e só funciona uma vez.`),
    S.h("a", { class: "copia", href: link, target: "_blank", rel: "noopener noreferrer", title: "Abrir link de acesso" }, link),
    S.h("div", { class: "linha", style: { "margin-top": ".8rem" } },
      S.h("button", { class: "btn btn-escuro", onclick: async () => {
        try { await navigator.clipboard.writeText(msg); S.toast("Mensagem com o link copiada."); }
        catch (e) { S.toast("Selecione e copie o link acima.", true); }
      } }, "Copiar mensagem"),
      whatsapp,
      emailBotao
    )));
};

/* ---------------- modo teste do Desenvolvedor ---------------- */
S.faixaTeste = function (eu) {
  if (!eu || !eu.conta_teste) return null;
  return S.h("div", { class: "faixa-teste" }, S.h("b", {}, "MODO TESTE RMD"), " Você está vendo como ", eu.usuario.papel_nome, ". Dados de teste, nada é real. ",
    eu.pode_voltar_criador ? S.h("button", { class: "btn btn-p btn-cta", onclick: async () => { await S.acao(() => S.api("/api/criador/voltar", { corpo: {} })); location.href = S.u("/rmd#teste"); } }, "Voltar ao painel RMD") : null);
};

/* ---------------- gráfico simples (barras = pedidos/vendas, linha = kg ou receita) ---------------- */
S.grafico = function (serie, opc = {}) {
  const ns = "http://www.w3.org/2000/svg";
  const L = 720, A = 230, m = { e: 46, d: 46, t: 14, b: 34 };
  const svg = document.createElementNS(ns, "svg");
  svg.setAttribute("viewBox", `0 0 ${L} ${A}`); svg.setAttribute("class", "grafico"); svg.setAttribute("role", "img");
  svg.setAttribute("aria-label", opc.titulo || "Gráfico");
  const el = (t, a) => { const x = document.createElementNS(ns, t); Object.entries(a).forEach(([k, v]) => x.setAttribute(k, v)); svg.append(x); return x; };
  const n = serie.length || 1, w = (L - m.e - m.d) / n;
  const maxB = Math.max(1, ...serie.map((s) => s.barra || 0)), maxL = Math.max(1, ...serie.map((s) => s.linha || 0));
  for (let k = 0; k <= 4; k++) { const y = m.t + (A - m.t - m.b) * k / 4; el("line", { x1: m.e, x2: L - m.d, y1: y, y2: y, class: "g-grade" }); }
  serie.forEach((s, i) => {
    const hB = (A - m.t - m.b) * (s.barra || 0) / maxB;
    const r = el("rect", { x: m.e + i * w + w * 0.18, y: A - m.b - hB, width: w * 0.64, height: Math.max(0, hB), rx: 3, class: "g-barra" });
    const t = document.createElementNS(ns, "title"); t.textContent = `${s.rotulo}: ${opc.fmtBarra ? opc.fmtBarra(s.barra) : s.barra} · ${opc.fmtLinha ? opc.fmtLinha(s.linha) : s.linha}`; r.append(t);
    if (n <= 16 || i % Math.ceil(n / 12) === 0) { const tx = el("text", { x: m.e + i * w + w / 2, y: A - 12, class: "g-eixo", "text-anchor": "middle" }); tx.textContent = s.rotulo; }
  });
  const pts = serie.map((s, i) => `${m.e + i * w + w / 2},${A - m.b - (A - m.t - m.b) * (s.linha || 0) / maxL}`).join(" ");
  el("polyline", { points: pts, class: "g-linha" });
  serie.forEach((s, i) => el("circle", { cx: m.e + i * w + w / 2, cy: A - m.b - (A - m.t - m.b) * (s.linha || 0) / maxL, r: 3.5, class: "g-ponto" }));
  const tb = el("text", { x: 4, y: m.t + 4, class: "g-eixo" }); tb.textContent = opc.fmtBarra ? opc.fmtBarra(maxB) : String(maxB);
  const tl = el("text", { x: L - 4, y: m.t + 4, class: "g-eixo", "text-anchor": "end" }); tl.textContent = opc.fmtLinha ? opc.fmtLinha(maxL) : String(maxL);
  return S.h("div", { class: "grafico-caixa" }, svg,
    S.h("div", { class: "g-legenda" }, S.h("span", { class: "g-leg-barra" }, opc.nomeBarra || "Barras"), S.h("span", { class: "g-leg-linha" }, opc.nomeLinha || "Linha")));
};
