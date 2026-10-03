/* Sobrou+ — app do consumidor. Telas: Início, Ofertas, Pedidos, Favoritos, Perfil (hash). */
"use strict";
const h = S.h;
const E = { cfg: {}, eu: null, local: null, filtros: { categoria: "todos" }, favoritos: [], itens: [] };
const ICONES = {
  inicio: "M3 11l9-8 9 8v10a1 1 0 0 1-1 1h-5v-7h-6v7H4a1 1 0 0 1-1-1z",
  ofertas: "M20.6 13.4l-7.2 7.2a2 2 0 0 1-2.8 0L3 13V3h10l7.6 7.6a2 2 0 0 1 0 2.8zM7.5 8.5a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3z",
  pedidos: "M6 2h12l2 4v15a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V6zm0 4h12M9 10a3 3 0 0 0 6 0",
  favoritos: "M12 21s-7.5-4.6-9.5-9.3C1.2 8.3 3.3 4.5 7 4.5c2 0 3.5 1.1 5 3 1.5-1.9 3-3 5-3 3.7 0 5.8 3.8 4.5 7.2C19.5 16.4 12 21 12 21z",
  perfil: "M12 12a4.5 4.5 0 1 0 0-9 4.5 4.5 0 0 0 0 9zm-8 9c0-4 3.6-6.5 8-6.5s8 2.5 8 6.5",
};
function icone(nome) {
  const ns = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(ns, "svg");
  svg.setAttribute("viewBox", "0 0 24 24"); svg.setAttribute("width", "22"); svg.setAttribute("height", "22");
  svg.setAttribute("fill", "none"); svg.setAttribute("stroke", "currentColor"); svg.setAttribute("stroke-width", "1.8");
  svg.setAttribute("stroke-linejoin", "round"); svg.setAttribute("class", "ic");
  const p = document.createElementNS(ns, "path"); p.setAttribute("d", ICONES[nome]); svg.append(p);
  return svg;
}

async function iniciar() {
  E.cfg = await S.api("/api/config").catch(() => ({}));
  S.tema(E.cfg.tema);
  try { E.eu = await S.api("/api/eu"); S.tema(E.eu.tema); } catch (e) { E.eu = null; }
  if (E.eu && E.eu.usuario.papel !== "cliente") { /* conta de empresa/entregador: mostra o atalho certo */ }
  if (E.eu && E.eu.usuario.papel === "cliente") E.favoritos = (await S.api("/api/favoritos").catch(() => ({ empresas: [] }))).empresas;
  try { E.local = JSON.parse(sessionStorage.getItem("sob_local") || "null"); } catch (e) { E.local = null; }
  desenharTopo(); desenharMenu();
  window.addEventListener("hashchange", rotear);
  rotear();
  setInterval(() => { if (location.hash.startsWith("#pedido/")) rotear(true); }, 15000);
}

function desenharTopo() {
  const busca = h("input", { type: "search", placeholder: "Buscar comida, loja ou bairro", value: E.filtros.busca || "",
    onkeydown: (e) => { if (e.key === "Enter") { E.filtros.busca = e.target.value.trim(); location.hash = "#inicio"; carregarVitrine(); } } });
  const loc = h("button", { class: "loc", onclick: pedirLocal }, E.local ? "Perto ✓" : "Perto de mim");
  S.limpar(document.getElementById("topo"), S.marca(E.cfg, E.cfg.nome || "Sobrou+"), h("div", { class: "busca" }, busca, loc));
}

async function pedirLocal() {
  try {
    E.local = await S.posicao();
    try { sessionStorage.setItem("sob_local", JSON.stringify(E.local)); } catch (e) { /* sem armazenamento */ }
    S.toast("Localização ativada: ofertas por distância.");
    desenharTopo(); carregarVitrine();
  } catch (e) { S.toast(e.message, true); }
}

function desenharMenu() {
  const atual = (location.hash.slice(1).split("/")[0]) || "inicio";
  const itens = [["inicio", "Início"], ["ofertas", "Ofertas"], ["pedidos", "Pedidos"], ["favoritos", "Favoritos"], ["perfil", "Perfil"]];
  S.limpar(document.getElementById("menu"), itens.map(([k, t]) => h("button", { class: atual === k || (atual === "pedido" && k === "pedidos") ? "ativo" : "",
    onclick: () => { location.hash = "#" + k; } }, icone(k), t)));
}

function rotear(silencioso) {
  desenharMenu();
  const [tela, id] = location.hash.slice(1).split("/");
  const alvo = document.getElementById("tela");
  if (!silencioso) window.scrollTo(0, 0);
  if (tela === "pedidos") return telaPedidos(alvo);
  if (tela === "pedido" && id) return telaPedido(alvo, id);
  if (tela === "favoritos") return telaFavoritos(alvo);
  if (tela === "perfil") return telaPerfil(alvo);
  if (tela === "oferta" && id) { telaInicio(alvo, tela); return abrirOferta(id); }
  return telaInicio(alvo, tela || "inicio");
}

// ------------------------------------------------------------------ início / ofertas
async function telaInicio(alvo, tela) {
  const chips = h("div", { class: "chips" }, Object.entries(S.CATEGORIAS).map(([k, t]) =>
    h("button", { class: "chip" + ((E.filtros.categoria || "todos") === k ? " ativo" : ""), onclick: () => { E.filtros.categoria = k; telaInicio(alvo, tela); } }, t)));
  const sel = (nome, opcoes) => h("select", { onchange: (e) => { E.filtros[nome] = e.target.value; carregarVitrine(); } },
    opcoes.map(([v, t]) => h("option", { value: v, selected: (E.filtros[nome] || "") === v }, t)));
  const filtros = h("div", { class: "filtros" },
    sel("modo", [["", "Retirada ou entrega"], ["retirada", "Só retirada"], ["entrega", "Só entrega"]]),
    sel("desconto_min", [["", "Qualquer desconto"], ["30", "30% ou mais"], ["50", "50% ou mais"], ["70", "70% ou mais"]]),
    sel("tipo", [["", "Todos os tipos"], ["produto", "Produto"], ["cesta", "Cesta surpresa"], ["kit", "Kit"]]),
    sel("raio_km", [["", "Qualquer distância"], ["2", "Até 2 km"], ["5", "Até 5 km"], ["10", "Até 10 km"]]),
    sel("ordem", tela === "ofertas" ? [["desconto", "Maior desconto"], ["preco", "Menor preço"], ["distancia", "Mais perto"], ["urgencia", "Acaba primeiro"]]
      : [["", "Recomendadas"], ["distancia", "Mais perto"], ["desconto", "Maior desconto"], ["preco", "Menor preço"], ["urgencia", "Acaba primeiro"]]));
  if (tela === "ofertas" && !E.filtros.ordem) E.filtros.ordem = "desconto";
  const faixa = h("div", { class: "faixa-impacto", id: "faixa" });
  const alternar = h("div", { class: "modos", style: { "margin-bottom": ".8rem" } },
    h("button", { class: "btn btn-linha btn-p" + (E.verMapa ? "" : " ativo"), onclick: () => { E.verMapa = false; telaInicio(alvo, tela); } }, "Lista"),
    h("button", { class: "btn btn-linha btn-p" + (E.verMapa ? " ativo" : ""), onclick: () => { E.verMapa = true; telaInicio(alvo, tela); } }, "Mapa"));
  S.limpar(alvo, tela === "inicio" ? faixa : h("h1", {}, "Ofertas de hoje"), chips, filtros, alternar,
    E.verMapa ? h("div", { class: "mapa alto", id: "mapa-vitrine", style: { "margin-bottom": "1rem" } }) : null,
    h("div", { id: "lista", class: "ofertas" }, h("div", { class: "vazio" }, "Carregando ofertas…")));
  if (tela === "inicio") S.api("/api/impacto/publico").then((i) => S.limpar(faixa,
    h("div", {}, "Desperdício evitado", h("b", {}, S.kg(i.kg_desperdicio_evitado))),
    h("div", {}, "Clientes economizaram", h("b", {}, S.dinheiro(i.economia_clientes_centavos))),
    h("div", {}, "Pessoas beneficiadas", h("b", {}, String(i.pessoas_beneficiadas))))).catch(() => faixa.remove());
  carregarVitrine();
}

async function carregarVitrine() {
  const lista = document.getElementById("lista");
  if (!lista) return;
  const f = { ...E.filtros };
  if (f.categoria === "todos") delete f.categoria;
  if (E.local) { f.lat = E.local.lat; f.lng = E.local.lng; }
  try {
    const r = await S.api("/api/vitrine" + S.qs(f));
    E.itens = r.itens;
    if (!r.itens.length) return S.limpar(lista, h("div", { class: "vazio" }, h("h3", {}, "Nenhuma oferta agora com esses filtros."), "As lojas publicam as sobras ao longo do dia. Volte mais tarde ou mude os filtros."));
    S.limpar(lista, r.itens.map(cartaoOferta));
    const caixaMapa = document.getElementById("mapa-vitrine");
    if (caixaMapa) {
      const m = S.mapa(caixaMapa, E.local ? [E.local.lat, E.local.lng] : null, 13);
      const lojas = {};
      r.itens.forEach((o) => { if (o.lat === null || o.lat === undefined) return; (lojas[o.unidade_id] = lojas[o.unidade_id] || []).push(o); });
      const pontos = [];
      Object.values(lojas).forEach((ofs) => {
        const o = ofs[0]; pontos.push([o.lat, o.lng]);
        const mk = S.marcar(m, o.lat, o.lng, "#F57A20", String(ofs.length));
        const pop = h("div", {}, h("b", {}, o.empresa), h("div", {}, o.unidade), ofs.map((x) => h("div", {}, h("a", { href: "#oferta/" + x.id }, `${x.nome} — ${S.dinheiro(x.preco_centavos)} (-${x.desconto_pct}%)`))));
        mk.bindPopup(pop);
      });
      if (E.local) { S.marcar(m, E.local.lat, E.local.lng, "#2563EB", "•", "Você"); pontos.push([E.local.lat, E.local.lng]); }
      S.enquadrar(m, pontos);
    }
  } catch (e) { S.limpar(lista, h("div", { class: "vazio" }, e.message)); }
}

function fotoOferta(o, grande) {
  const src = grande ? o.foto : o.miniatura || o.foto;
  return h("div", { class: "foto" },
    src ? h("img", { src, alt: o.nome, loading: "lazy" }) : h("div", { class: "sem-foto" }, "Foto real do alimento pendente (enviada pela loja)"),
    h("span", { class: "desconto" }, `-${o.desconto_pct}%`),
    o.tipo !== "produto" ? h("span", { class: "tipo" }, o.tipo_nome) : null);
}

function infosOferta(o) {
  const urg = o.retirada_fim && (new Date(o.retirada_fim) - Date.now()) < 3600e3;
  return h("div", { class: "infos" },
    o.estoque_baixo ? S.selo(`Últimas ${o.disponivel}!`, "urgente") : S.selo(`${o.disponivel} disponíveis`, "ok"),
    o.retirada_inicio ? S.selo(`Retirada ${S.janela(o.retirada_inicio, o.retirada_fim)}`, urg ? "urgente" : "aviso") : null,
    o.permite_entrega && o.aceita_entrega ? S.selo("Entrega", "oferta") : null,
    o.distancia_km !== null && o.distancia_km !== undefined ? S.selo(`${o.distancia_km.toLocaleString("pt-BR")} km`) : null);
}

function estrelas(n) { const r = Math.round(n || 0); return h("span", { class: "estrelas" }, "★".repeat(r) + "☆".repeat(5 - r)); }

function cartaoOferta(o) {
  return h("article", { class: "card", onclick: () => { location.hash = "#oferta/" + o.id; } },
    fotoOferta(o),
    h("div", { class: "corpo" },
      h("div", { class: "loja" }, `${o.empresa} · ${o.unidade}${o.bairro ? " · " + o.bairro : ""}`),
      h("div", { class: "nome" }, o.nome),
      o.nota && o.nota.total ? h("div", { class: "mudo" }, estrelas(o.nota.media), ` ${o.nota.media.toLocaleString("pt-BR")} (${o.nota.total})`) : null,
      o.tipo === "cesta" && o.valor_estimado_min_centavos ? h("div", { class: "mudo" }, `Vale de ${S.dinheiro(o.valor_estimado_min_centavos)} a ${S.dinheiro(o.valor_estimado_max_centavos)}`) : null,
      infosOferta(o),
      h("div", { class: "precos" }, h("span", { class: "preco" }, S.dinheiro(o.preco_centavos)), h("span", { class: "preco-de" }, S.dinheiro(o.preco_normal_centavos)))));
}

// ------------------------------------------------------------------ detalhe + checkout
async function abrirOferta(id) {
  let o;
  try { o = await S.api("/api/vitrine/" + id); } catch (e) { S.toast(e.message, true); location.hash = "#inicio"; return; }
  const est = { q: 1, modo: o.permite_retirada ? "retirada" : "entrega", endereco: "", lat: E.local && E.local.lat, lng: E.local && E.local.lng };
  const max = Math.min(o.disponivel, o.limite_por_cliente);
  const caixaTotal = h("div", { class: "resumo-total" });
  const caixaEnd = h("div");
  const qtd = h("b", {}, "1");
  const folha = S.folha(h("div", {}), () => { if (location.hash.startsWith("#oferta/")) history.replaceState(null, "", "#inicio"); });
  const fav = E.favoritos.includes(o.empresa_id);

  async function recalcular() {
    qtd.textContent = String(est.q);
    if (!E.eu || E.eu.usuario.papel !== "cliente") {
      S.limpar(caixaTotal, h("div", {}, h("span", {}, "Total"), h("span", { class: "total" }, S.dinheiro(o.preco_centavos * est.q))));
      return;
    }
    try {
      const c = await S.api("/api/cotar", { corpo: corpoPedido() });
      S.limpar(caixaTotal,
        h("div", {}, h("span", {}, "Produtos"), h("span", {}, S.dinheiro(c.subtotal_centavos))),
        c.entrega_centavos ? h("div", {}, h("span", {}, "Entrega"), h("span", {}, S.dinheiro(c.entrega_centavos))) : null,
        c.distancia_km !== null && c.distancia_km !== undefined ? h("div", { class: "mudo" }, h("span", {}, "Distância"),
          h("span", {}, S.textoRota({ km: c.distancia_km, minutos: c.tempo_min, fonte: c.distancia_fonte }))) : null,
        h("div", { class: "economia" }, h("span", {}, "Você economiza"), h("span", {}, S.dinheiro(c.economia_centavos))),
        h("div", {}, h("span", {}, "Total"), h("span", { class: "total" }, S.dinheiro(c.total_centavos))));
    } catch (e) { S.limpar(caixaTotal, h("div", { class: "mudo" }, e.message)); }
  }
  function montarEndereco() { est.endereco = [est.base, est.complemento].filter(Boolean).join(" — "); }
  function corpoPedido() { return { itens: [{ oferta_id: o.id, quantidade: est.q }], modo: est.modo, endereco: est.endereco, lat: est.lat, lng: est.lng }; }
  function desenharEndereco() {
    if (est.modo !== "entrega") return S.limpar(caixaEnd);
    const complemento = h("input", { value: est.complemento || "", placeholder: "Número, apartamento, referência", oninput: (e) => { est.complemento = e.target.value; montarEndereco(); } });
    S.limpar(caixaEnd, h("label", {}, "Endereço de entrega"),
      S.buscaEndereco((it) => { est.base = it.nome; est.lat = it.lat; est.lng = it.lng; montarEndereco(); desenharEndereco(); recalcular(); }, est.base || ""),
      h("label", {}, "Complemento"), complemento,
      h("div", { class: "linha", style: { "margin-top": ".4rem" } },
        h("button", { type: "button", class: "btn btn-linha btn-p", onclick: async () => { try { const p = await S.posicao(); est.lat = p.lat; est.lng = p.lng;
          if (!est.base) est.base = "Minha localização atual"; montarEndereco(); desenharEndereco(); recalcular(); } catch (er) { S.toast(er.message, true); } } }, "Usar minha localização")),
      est.lat ? h("div", { class: "mapa", id: "mapa-entrega", style: { "margin-top": ".6rem", height: "200px" } }) : h("div", { class: "mudo" }, "Busque o endereço ou use a localização para calcular a entrega pelas ruas."));
    if (est.lat) {
      const m = S.mapa(document.getElementById("mapa-entrega"));
      S.marcar(m, o.lat, o.lng, "#0A563A", "L", o.empresa);
      S.marcar(m, est.lat, est.lng, "#F57A20", "C", "Entrega");
      S.desenharRota(m, [o.lat, o.lng], [est.lat, est.lng]);
    }
  }
  const botaoModo = (m, t) => h("button", { class: "btn btn-linha" + (est.modo === m ? " ativo" : ""), onclick: (e) => {
    est.modo = m; e.target.parentNode.querySelectorAll("button").forEach((b) => b.classList.remove("ativo")); e.target.classList.add("ativo"); desenharEndereco(); recalcular(); } }, t);

  async function comprar(btn) {
    if (!E.eu) { folha.fechar(); location.hash = "#perfil"; S.toast("Entre ou crie sua conta para comprar."); return; }
    if (E.eu.usuario.papel !== "cliente") { S.toast("Você está com uma conta de empresa. Saia e entre como cliente para comprar.", true); return; }
    btn.disabled = true;
    try {
      const p = await S.acao(() => S.api("/api/pedidos", { corpo: corpoPedido() }));
      folha.fechar(); location.hash = "#pedido/" + p.id;
    } catch (e) { btn.disabled = false; }
  }

  S.limpar(folha.el,
    h("div", { style: { margin: "-1.2rem -1.2rem 1rem" } }, fotoOferta(o, true)),
    o.fotos.length > 1 ? h("div", { class: "galeria" }, o.fotos.map((f) => h("img", { src: f + "/mini", alt: "" }))) : null,
    h("div", { class: "mudo" }, `${o.empresa} · ${o.unidade}`),
    h("h2", {}, o.nome),
    o.descricao ? h("p", {}, o.descricao) : null,
    o.tipo === "cesta" ? h("p", { class: "mudo" }, `Cesta surpresa: a loja monta com o que sobrou do dia (${S.CATEGORIAS[o.categoria] || o.categoria}). Vale de ${S.dinheiro(o.valor_estimado_min_centavos)} a ${S.dinheiro(o.valor_estimado_max_centavos)}.`) : null,
    infosOferta(o),
    o.endereco ? h("p", { class: "mudo" }, `Retirar em: ${o.endereco}${o.bairro ? ", " + o.bairro : ""}${o.cidade ? " — " + o.cidade : ""}${o.instrucoes_retirada ? ". " + o.instrucoes_retirada : ""}`) : null,
    o.validade ? h("p", { class: "mudo" }, `Consumir até ${S.data(o.validade)}`) : null,
    o.lat !== null && o.lat !== undefined ? h("div", { class: "mapa", id: "mapa-oferta", style: { height: "180px", margin: ".4rem 0" } }) : null,
    h("div", { class: "precos", style: { display: "flex", gap: ".6rem", "align-items": "baseline", margin: ".6rem 0" } },
      h("span", { class: "preco" }, S.dinheiro(o.preco_centavos)), h("span", { class: "preco-de" }, S.dinheiro(o.preco_normal_centavos)), S.selo(`-${o.desconto_pct}%`, "urgente")),
    h("div", { class: "linha" },
      h("div", { class: "qtd" }, h("button", { onclick: () => { if (est.q > 1) { est.q--; recalcular(); } } }, "−"), qtd,
        h("button", { onclick: () => { if (est.q < max) { est.q++; recalcular(); } else S.toast(`Máximo ${max} por cliente.`); } }, "+")),
      E.eu && E.eu.usuario.papel === "cliente" ? h("button", { class: "btn btn-linha btn-p", style: { flex: "0 0 auto" }, onclick: async (e) => {
        const r = await S.acao(() => S.api("/api/favoritos/" + o.empresa_id, { corpo: {} }));
        E.favoritos = r.favorito ? [...E.favoritos, o.empresa_id] : E.favoritos.filter((x) => x !== o.empresa_id);
        e.target.textContent = r.favorito ? "♥ Loja favorita" : "♡ Favoritar loja"; } }, fav ? "♥ Loja favorita" : "♡ Favoritar loja") : null),
    o.permite_retirada && o.permite_entrega && o.aceita_entrega ? h("div", { class: "modos", style: { "margin-top": ".8rem" } }, botaoModo("retirada", "Retirar na loja"), botaoModo("entrega", "Receber em casa")) : null,
    caixaEnd, caixaTotal,
    h("button", { class: "btn btn-cta btn-bloco", style: { "margin-top": "1rem" }, onclick: (e) => comprar(e.currentTarget) }, E.eu ? "Reservar e ir para o pagamento" : "Entrar para comprar"));
  desenharEndereco(); recalcular();
  if (o.lat !== null && o.lat !== undefined) {
    const m = S.mapa(document.getElementById("mapa-oferta"), [o.lat, o.lng], 15);
    S.marcar(m, o.lat, o.lng, "#0A563A", "L", `${o.empresa} — ${o.unidade}`);
    if (E.local) { S.marcar(m, E.local.lat, E.local.lng, "#2563EB", "•", "Você"); S.desenharRota(m, [E.local.lat, E.local.lng], [o.lat, o.lng], "#1FA361"); }
  }
}

// ------------------------------------------------------------------ pedidos
function exigirLogin(alvo) {
  if (E.eu && E.eu.usuario.papel === "cliente") return true;
  S.limpar(alvo, h("div", { class: "vazio" }, h("h3", {}, "Entre para ver seus pedidos."), h("button", { class: "btn btn-cta", onclick: () => { location.hash = "#perfil"; } }, "Entrar ou criar conta")));
  return false;
}

async function telaPedidos(alvo) {
  if (!exigirLogin(alvo)) return;
  const r = await S.api("/api/pedidos").catch((e) => ({ itens: [], erro: e.message }));
  S.limpar(alvo, h("h1", {}, "Meus pedidos"), r.itens.length ? r.itens.map((p) => h("div", { class: "cartao", style: { "margin-bottom": ".7rem", cursor: "pointer" }, onclick: () => { location.hash = "#pedido/" + p.id; } },
    h("div", { class: "linha" }, h("b", {}, `#${p.numero} · ${p.empresa}`), h("span", { style: { flex: "0 0 auto" } }, S.selo(p.status_nome, S.SELO_PEDIDO[p.status]))),
    h("div", { class: "mudo" }, p.resumo), h("div", { class: "linha mudo" }, h("span", {}, S.data(p.criado_em)), h("b", { style: { "text-align": "right" } }, S.dinheiro(p.total_centavos)))))
    : h("div", { class: "vazio" }, "Você ainda não fez pedidos. Que tal salvar uma comida hoje?"));
}

let vigiaPagamento = null;
async function caixaPagamento(p) {
  const meios = await S.api("/api/meios-pagamento").catch(() => ({ teste: true }));
  const fim = new Date(p.reserva_expira_em);
  const caixa = h("div", { class: "cartao", style: { margin: "1rem 0" } });
  const area = h("div");
  const pendente = (p.pagamentos || []).find((g) => g.status === "pendente");
  const vigiar = () => {
    clearInterval(vigiaPagamento);
    vigiaPagamento = setInterval(async () => {
      if (!location.hash.startsWith("#pedido/" + p.id)) return clearInterval(vigiaPagamento);
      try { const r = await S.api(`/api/pedidos/${p.id}/pagamento`); if (r.status !== "aguardando_pagamento") { clearInterval(vigiaPagamento); S.toast("Pagamento confirmado!"); rotear(); } } catch (e) { /* tenta de novo */ }
    }, 4000);
  };
  const mostrarPix = (g) => {
    const copia = h("div", { class: "copia" }, g.qr_code || "");
    S.limpar(area, h("div", { style: { "text-align": "center" } },
      g.qr_base64 ? h("img", { class: "pix-qr", src: "data:image/png;base64," + g.qr_base64, alt: "QR Code Pix" }) : null,
      h("p", {}, "Abra o app do seu banco → Pix → ler QR Code, ou use o Pix copia e cola:"), copia,
      h("button", { class: "btn btn-verde btn-p", style: { "margin-top": ".5rem" }, onclick: async () => { try { await navigator.clipboard.writeText(g.qr_code); S.toast("Código Pix copiado."); } catch (e) { S.toast("Selecione e copie o código acima.", true); } } }, "Copiar código Pix"),
      h("p", { class: "mudo" }, "Assim que o banco confirmar, esta tela atualiza sozinha.")));
    vigiar();
  };
  const iniciar = async (meio) => {
    const r = await S.acao(() => S.api(`/api/pedidos/${p.id}/pagar`, { corpo: { meio } }));
    if (meio === "teste") { S.toast("Pagamento de teste aprovado!"); return rotear(); }
    const g = r.pagamento_iniciado;
    if (meio === "pix") mostrarPix(g);
    else if (g.link_pagamento) { S.limpar(area, h("a", { class: "btn btn-cta btn-bloco", href: g.link_pagamento, target: "_blank", rel: "noopener" }, "Abrir pagamento com cartão (Mercado Pago)"),
      h("p", { class: "mudo" }, "Depois de pagar, volte aqui: a tela atualiza sozinha.")); vigiar(); }
  };
  const botoes = [];
  if (meios.pix) botoes.push(h("button", { class: "btn btn-cta btn-bloco", onclick: () => iniciar("pix") }, `Pagar ${S.dinheiro(p.total_centavos)} com Pix`));
  if (meios.cartao) botoes.push(h("button", { class: "btn btn-escuro btn-bloco", style: { "margin-top": ".5rem" }, onclick: () => iniciar("cartao") }, "Pagar com cartão"));
  if (meios.teste) botoes.push(h("div", { class: "aviso-teste" }, meios.pix ? "Pagamento de teste liberado pela equipe Sobrou+." :
    "MODO TESTE: Pix e cartão reais ainda não foram ativados. Este botão simula um pagamento aprovado — nenhum dinheiro é cobrado."),
    h("button", { class: "btn btn-linha btn-bloco", onclick: () => iniciar("teste") }, `Pagar ${S.dinheiro(p.total_centavos)} (teste)`));
  S.limpar(caixa, h("h2", {}, "Pagamento"), h("p", {}, `Reservamos para você até ${S.hora(p.reserva_expira_em)} (${Math.max(0, Math.round((fim - Date.now()) / 60000))} min).`), botoes, area);
  if (pendente && pendente.meio === "pix" && pendente.qr_code) mostrarPix(pendente);
  return caixa;
}

async function telaPedido(alvo, id) {
  if (!exigirLogin(alvo)) return;
  let p;
  try { p = await S.api("/api/pedidos/" + id); } catch (e) { return S.limpar(alvo, h("div", { class: "vazio" }, e.message)); }
  const blocos = [h("a", { href: "#pedidos", class: "mudo" }, "← Meus pedidos"),
    h("div", { class: "linha", style: { margin: ".5rem 0" } }, h("h1", { style: { margin: 0 } }, `Pedido #${p.numero}`), h("span", { style: { flex: "0 0 auto" } }, S.selo(p.status_nome, S.SELO_PEDIDO[p.status]))),
    h("div", { class: "mudo" }, `${p.empresa} · ${p.unidade.nome}`)];
  if (p.status === "aguardando_pagamento") {
    blocos.push(await caixaPagamento(p));
  }
  if (["pago", "recebido", "preparando", "pronto", "aguardando_retirada", "aguardando_entregador", "entregador_designado", "em_coleta", "em_rota"].includes(p.status)) {
    blocos.push(h("div", { class: "codigo", style: { margin: "1rem 0" } },
      h("div", { class: "mudo" }, p.modo === "retirada" ? "Mostre na loja para retirar" : "Informe ao entregador na entrega"),
      h("div", { class: "pin" }, p.codigo_retirada), h("div", { class: "mudo" }, `Pedido #${p.numero}`),
      p.modo === "retirada" ? S.qr(p.token_retirada) : null,
      p.modo === "retirada" ? h("p", {}, `Janela de retirada: ${S.janela(p.janela_inicio, p.janela_fim)}`) : null,
      p.unidade.endereco ? h("p", { class: "mudo" }, `${p.unidade.endereco}${p.unidade.instrucoes_retirada ? " — " + p.unidade.instrucoes_retirada : ""}`) : null));
  }
  const temMapa = p.unidade.lat !== null && p.unidade.lat !== undefined && !["concluido", "cancelado", "expirado"].includes(p.status);
  if (temMapa) blocos.push(h("div", { class: "mapa", id: "mapa-pedido", style: { "margin-bottom": "1rem" } }));
  if (p.entrega && p.entrega.entregador) blocos.push(h("div", { class: "cartao", style: { "margin-bottom": "1rem" } },
    h("b", {}, `Entregador: ${p.entrega.entregador}`), p.entrega.eta_min ? h("div", { class: "mudo" }, `Previsão: ~${p.entrega.eta_min} min`) : null,
    p.entrega.posicao_em ? h("div", { class: "mudo" }, `Última posição recebida às ${S.hora(p.entrega.posicao_em)}`) : null));
  if (p.status === "entregue") blocos.push(h("button", { class: "btn btn-verde btn-bloco", style: { margin: "1rem 0" }, onclick: async () => { await S.acao(() => S.api(`/api/pedidos/${p.id}/confirmar`, { corpo: {} }), "Obrigado! Pedido concluído."); rotear(); } }, "Recebi meu pedido"));
  if (p.status === "concluido") blocos.push(caixaAvaliacao(p));
  blocos.push(h("div", { class: "cartao" },
    p.itens.map((i) => h("div", { class: "linha" }, h("span", {}, `${i.quantidade}× ${i.nome}`), h("span", { style: { "text-align": "right" } }, S.dinheiro(i.preco_centavos * i.quantidade)))),
    h("div", { class: "resumo-total" },
      p.entrega_centavos ? h("div", {}, h("span", {}, "Entrega"), h("span", {}, S.dinheiro(p.entrega_centavos))) : null,
      h("div", { class: "economia" }, h("span", {}, "Você economizou"), h("span", {}, S.dinheiro(p.economia_centavos))),
      h("div", {}, h("span", {}, "Total"), h("span", { class: "total" }, S.dinheiro(p.total_centavos))))));
  blocos.push(h("h3", { style: { "margin-top": "1rem" } }, "Andamento"), h("ul", { class: "linha-tempo" }, p.historico.map((x) => h("li", {}, `${S.hora(x.quando)} — ${(x.para_status || "").replace(/_/g, " ")}${x.nota ? " (" + x.nota + ")" : ""}`))));
  if (["criado", "aguardando_pagamento", "pago"].includes(p.status)) blocos.push(h("button", { class: "btn btn-linha btn-bloco", onclick: async () => {
    if (!confirm("Cancelar este pedido?")) return; await S.acao(() => S.api(`/api/pedidos/${p.id}/cancelar`, { corpo: {} }), "Pedido cancelado."); rotear(); } }, "Cancelar pedido"));
  S.limpar(alvo, blocos);
  if (temMapa) {
    const m = S.mapa(document.getElementById("mapa-pedido"), [p.unidade.lat, p.unidade.lng], 15);
    S.marcar(m, p.unidade.lat, p.unidade.lng, "#0A563A", "L", `${p.empresa} — ${p.unidade.nome}`);
    if (p.modo === "entrega" && p.entrega_lat !== null) {
      S.marcar(m, p.entrega_lat, p.entrega_lng, "#F57A20", "C", "Entrega");
      const ent = p.entrega || {};
      if (ent.entregador_lat !== null && ent.entregador_lat !== undefined && ["entregador_designado", "em_coleta", "em_rota"].includes(p.status)) {
        S.marcar(m, ent.entregador_lat, ent.entregador_lng, "#2563EB", "E", `Entregador ${ent.entregador || ""}`);
        S.desenharRota(m, [ent.entregador_lat, ent.entregador_lng], p.status === "em_rota" ? [p.entrega_lat, p.entrega_lng] : [p.unidade.lat, p.unidade.lng], "#2563EB");
      } else S.desenharRota(m, [p.unidade.lat, p.unidade.lng], [p.entrega_lat, p.entrega_lng]);
    } else if (E.local) {
      S.marcar(m, E.local.lat, E.local.lng, "#2563EB", "•", "Você");
      S.desenharRota(m, [E.local.lat, E.local.lng], [p.unidade.lat, p.unidade.lng], "#1FA361");
    }
  }
}

function caixaAvaliacao(p) {
  if (p.avaliacao) return h("div", { class: "cartao", style: { "margin-bottom": "1rem" } }, h("b", {}, "Sua avaliação: "), estrelas(p.avaliacao.nota),
    p.avaliacao.comentario ? h("p", {}, p.avaliacao.comentario) : null,
    p.avaliacao.resposta ? h("p", { class: "mudo" }, `Resposta da loja: ${p.avaliacao.resposta}`) : null);
  let nota = 0;
  const botoes = [1, 2, 3, 4, 5].map((n) => h("button", { type: "button", "aria-label": `${n} estrela(s)`, onclick: () => { nota = n; botoes.forEach((b, i) => b.classList.toggle("on", i < n)); } }, "★"));
  const coment = h("textarea", { rows: 2, maxlength: 500, placeholder: "Conte como foi (opcional)" });
  return h("div", { class: "cartao", style: { "margin-bottom": "1rem" } }, h("h3", { style: { margin: 0 } }, "Como foi o seu pedido?"),
    h("div", { class: "estrelas-escolha" }, botoes), coment,
    h("button", { class: "btn btn-verde", style: { "margin-top": ".6rem" }, onclick: async () => {
      if (!nota) { S.toast("Toque nas estrelas para dar a nota.", true); return; }
      await S.acao(() => S.api(`/api/pedidos/${p.id}/avaliar`, { corpo: { nota, comentario: coment.value.trim() } }), "Obrigado pela avaliação!"); rotear(); } }, "Enviar avaliação"));
}

// ------------------------------------------------------------------ favoritos e perfil
async function telaFavoritos(alvo) {
  if (!exigirLogin(alvo)) return;
  const r = await S.api("/api/vitrine").catch(() => ({ itens: [] }));
  const itens = r.itens.filter((o) => E.favoritos.includes(o.empresa_id));
  S.limpar(alvo, h("h1", {}, "Lojas favoritas"), itens.length ? h("div", { class: "ofertas" }, itens.map(cartaoOferta))
    : h("div", { class: "vazio" }, "Nenhuma oferta das suas lojas favoritas agora. Abra uma oferta e toque em “Favoritar loja”."));
}

async function telaPerfil(alvo) {
  if (E.eu) {
    const u = E.eu.usuario;
    const blocos = [S.faixaTeste(E.eu), h("h1", {}, `Olá, ${u.nome.split(" ")[0]}`), h("div", { class: "mudo" }, u.email)];
    if (u.papel === "cliente") {
      const i = await S.api("/api/meu-impacto").catch(() => null);
      if (i) blocos.push(h("div", { class: "faixa-impacto", style: { "margin-top": "1rem" } },
        h("div", {}, "Comida que você salvou", h("b", {}, S.kg(i.kg_vendidos))), h("div", {}, "Você economizou", h("b", {}, S.dinheiro(i.economia_clientes_centavos))),
        h("div", {}, "Pedidos", h("b", {}, String(i.pedidos)))));
    } else {
      blocos.push(h("p", {}, "Esta conta é de ", h("b", {}, u.papel_nome), ". ", h("a", { href: u.papel === "entregador" ? S.u("/entregador") : S.u("/painel") }, "Abrir a minha área")));
    }
    if (u.trocar_senha) blocos.push(formSenha());
    blocos.push(h("div", { class: "cartao", style: { "margin-top": "1rem" } }, h("h3", {}, "Aparência"), h("div", { class: "linha" },
      ["claro", "medio", "escuro"].map((t) => h("button", { class: "btn btn-linha btn-p", onclick: () => S.tema(t) }, { claro: "Claro", medio: "Médio", escuro: "Escuro" }[t])))));
    const av = S.botaoAvisos();
    blocos.push(h("div", { class: "cartao", style: { "margin-top": "1rem" } }, h("h3", {}, "Avisos no celular"),
      h("p", { class: "mudo" }, "Receba “pedido pronto”, “entregador a caminho” e novidades mesmo com o app fechado."),
      av || h("p", { class: "mudo" }, "Este navegador não aceita avisos. No iPhone, adicione o Sobrou+ à Tela de Início primeiro.")));
    blocos.push(h("div", { class: "cartao", style: { "margin-top": "1rem" } }, h("h3", {}, "Seus dados (LGPD)"),
      h("div", { class: "linha", style: { "flex-wrap": "wrap", gap: ".5rem" } },
        h("a", { class: "btn btn-linha btn-p", href: S.u("/api/meus-dados") }, "Baixar meus dados"),
        h("button", { class: "btn btn-linha btn-p", onclick: async () => {
          const senha = prompt("Para excluir sua conta, digite sua senha. Seus pedidos ficam guardados sem seu nome (exigência fiscal).");
          if (!senha) return;
          await S.acao(() => S.api("/api/excluir-conta", { corpo: { senha } }), "Conta excluída.");
          E.eu = null; E.favoritos = []; location.hash = "#inicio"; } }, "Excluir minha conta")),
      h("p", { class: "mudo", style: { "margin-bottom": 0 } }, h("a", { href: "termos" }, "Termos de Uso"), " · ", h("a", { href: "privacidade" }, "Política de Privacidade"))));
    blocos.push(h("button", { class: "btn btn-linha btn-bloco", style: { "margin-top": "1rem" }, onclick: async () => { await S.api("/api/sair", { corpo: {} }); E.eu = null; E.favoritos = []; telaPerfil(alvo); } }, "Sair"));
    blocos.push(h("p", { class: "mudo", style: { "margin-top": "1.5rem" } }, "Tem restaurante, padaria ou mercado? ", h("a", { href: S.u("/painel#cadastro") }, "Seja parceiro Sobrou+"), " · Instituição social? ", h("a", { href: S.u("/painel#instituicao") }, "Cadastre-se para receber doações")));
    return S.limpar(alvo, blocos);
  }
  const modo = { cadastro: false };
  const desenhar = () => {
    const campos = {};
    const campo = (nome, rotulo, tipo = "text", extra = {}) => [h("label", {}, rotulo), campos[nome] = h("input", { type: tipo, ...extra })];
    const enviar = async (e) => {
      e.preventDefault();
      const dados = Object.fromEntries(Object.entries(campos).filter(([k]) => k !== "aceite").map(([k, v]) => [k, v.value.trim()]));
      if (modo.cadastro) { if (!campos.aceite.checked) { S.toast("Marque que leu e aceita os Termos e a Política de Privacidade.", true); return; } dados.aceite_termos = true; }
      try {
        await S.acao(() => S.api(modo.cadastro ? "/api/cadastro/cliente" : "/api/entrar", { corpo: dados }), modo.cadastro ? "Conta criada!" : "Bem-vindo de volta!");
        E.eu = await S.api("/api/eu"); S.tema(E.eu.tema);
        if (E.eu.usuario.papel !== "cliente" && !E.eu.usuario.trocar_senha) { location.href = E.eu.usuario.papel === "entregador" ? S.u("/entregador") : S.u("/painel"); return; }
        E.favoritos = (await S.api("/api/favoritos").catch(() => ({ empresas: [] }))).empresas || [];
        location.hash = "#inicio";
      } catch (er) { /* aviso já mostrado */ }
    };
    S.limpar(alvo, h("div", { class: "cartao", style: { "max-width": "440px", margin: "0 auto" } },
      h("h1", {}, modo.cadastro ? "Criar conta" : "Entrar"),
      h("form", { onsubmit: enviar },
        modo.cadastro ? campo("nome", "Seu nome", "text", { required: true, autocomplete: "name" }) : null,
        campo("email", "E-mail", "email", { required: true, autocomplete: "email" }),
        modo.cadastro ? campo("telefone", "Celular (opcional)", "tel", { autocomplete: "tel" }) : null,
        campo("senha", "Senha", "password", { required: true, autocomplete: modo.cadastro ? "new-password" : "current-password" }),
        modo.cadastro ? h("div", { class: "mudo" }, "Mínimo 8 caracteres, com letras e números.") : null,
        modo.cadastro ? h("label", { style: { display: "flex", gap: ".5rem", "align-items": "flex-start", "margin-top": ".8rem" } },
          campos.aceite = h("input", { type: "checkbox", style: { width: "auto", "margin-top": ".25rem" } }),
          h("span", {}, "Li e aceito os ", h("a", { href: "termos", target: "_blank" }, "Termos de Uso"), " e a ", h("a", { href: "privacidade", target: "_blank" }, "Política de Privacidade"), ".")) : null,
        h("button", { class: "btn btn-cta btn-bloco", style: { "margin-top": "1rem" } }, modo.cadastro ? "Criar conta" : "Entrar")),
      h("p", { style: { "text-align": "center" } }, h("a", { href: "#", onclick: (e) => { e.preventDefault(); modo.cadastro = !modo.cadastro; desenhar(); } }, modo.cadastro ? "Já tenho conta" : "Ainda não tenho conta"),
        modo.cadastro ? null : [" · ", h("a", { href: "#", onclick: (e) => { e.preventDefault(); S.esqueciSenha(campos.email.value.trim()); } }, "Esqueci minha senha")])));
  };
  desenhar();
}

function formSenha() {
  const atual = h("input", { type: "password", autocomplete: "current-password" });
  const nova = h("input", { type: "password", autocomplete: "new-password" });
  return h("div", { class: "cartao", style: { "margin-top": "1rem" } }, h("h3", {}, "Troque a senha inicial"),
    h("label", {}, "Senha atual"), atual, h("label", {}, "Nova senha (8+ caracteres, letras e números)"), nova,
    h("button", { class: "btn btn-verde", style: { "margin-top": ".7rem" }, onclick: async () => {
      await S.acao(() => S.api("/api/senha", { corpo: { atual: atual.value, nova: nova.value } }), "Senha trocada.");
      E.eu = await S.api("/api/eu"); telaPerfil(document.getElementById("tela")); } }, "Salvar nova senha"));
}

S.iniciarApp();
iniciar();
