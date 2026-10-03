/* Sobrou+ — app do entregador: online/offline, GPS real do celular, aceitar/recusar corrida, coleta e entrega com o código do cliente. */
"use strict";
const h = S.h;
const X = { cfg: {}, eu: null, dados: null, vigia: null, ultimaPos: 0, gps: "GPS desligado" };

async function iniciar() {
  X.cfg = await S.api("/api/config").catch(() => ({}));
  S.tema(X.cfg.tema);
  try { X.eu = await S.api("/api/eu"); } catch (e) { return login(); }
  if (X.eu.usuario.papel !== "entregador") { location.href = X.eu.usuario.papel === "cliente" ? S.u("/") : S.u("/painel"); return; }
  S.tema(X.eu.tema);
  if (X.eu.usuario.trocar_senha) return trocaSenha();
  await carregar();
  setInterval(carregar, 8000);
  setInterval(() => document.querySelectorAll(".contagem[data-ate]").forEach((el) => {
    el.textContent = `${Math.max(0, Math.round((new Date(el.dataset.ate) - Date.now()) / 1000))}s para responder`; }), 1000);
}

function moldura(...conteudo) {
  S.limpar(document.getElementById("raiz"), h("header", {}, S.marca(X.cfg, "Entregador"),
    X.eu ? h("button", { class: "btn btn-p btn-linha", style: { color: "#fff" }, onclick: async () => { await S.api("/api/sair", { corpo: {} }); location.reload(); } }, "Sair") : null),
  h("main", {}, X.eu ? S.faixaTeste(X.eu) : null, conteudo,
    X.eu && X.dados ? h("div", { class: "cartao", style: { "margin-top": "1rem" } }, h("b", {}, "Aviso de corrida com o app fechado"), h("br"), S.botaoAvisos() || h("span", { class: "mudo" }, "Este navegador não aceita avisos (no iPhone, adicione à Tela de Início).")) : null));
}

function login() {
  const email = h("input", { type: "email", autocomplete: "email" }); const senha = h("input", { type: "password", autocomplete: "current-password" });
  moldura(h("div", { class: "cartao" }, h("h1", {}, "Entrar"), h("form", { onsubmit: async (e) => { e.preventDefault();
    try { await S.acao(() => S.api("/api/entrar", { corpo: { email: email.value.trim(), senha: senha.value } })); location.reload(); } catch (er) { /* avisado */ } } },
    h("label", {}, "E-mail"), email, h("label", {}, "Senha"), senha, h("button", { class: "btn btn-cta btn-bloco", style: { "margin-top": "1rem" } }, "Entrar")),
    h("p", { style: { "text-align": "center" } }, h("a", { href: "#", onclick: (e) => { e.preventDefault(); S.esqueciSenha(email.value.trim()); } }, "Esqueci minha senha"))));
}

function trocaSenha() {
  const a = h("input", { type: "password" }); const n = h("input", { type: "password" });
  moldura(h("div", { class: "cartao" }, h("h1", {}, "Primeiro acesso"), h("p", {}, "Troque a senha inicial."), h("label", {}, "Senha atual"), a, h("label", {}, "Nova senha (8+ caracteres, letras e números)"), n,
    h("button", { class: "btn btn-verde btn-bloco", style: { "margin-top": "1rem" }, onclick: async () => { await S.acao(() => S.api("/api/senha", { corpo: { atual: a.value, nova: n.value } }), "Senha trocada."); location.reload(); } }, "Salvar")));
}

async function carregar() {
  try { X.dados = await S.api("/api/entregador"); } catch (e) { if (e.status === 401) return login(); }
  if (X.dados && X.dados.entregador.online) ligarGPS(); else desligarGPS();
  const digitando = document.activeElement && document.activeElement.tagName === "INPUT" && document.activeElement.value;
  const assinatura = X.dados ? JSON.stringify([X.dados.entregador.online, X.dados.ativas.map((c) => [c.id, c.status]), X.dados.ganhos_total_centavos]) : "";
  if (!digitando && assinatura !== X.assinatura) { X.assinatura = assinatura; desenhar(); }
}

function ligarGPS() {
  if (X.vigia !== null || !navigator.geolocation) { if (!navigator.geolocation) X.gps = "Este aparelho não informa GPS."; return; }
  X.gps = "Aguardando GPS…";
  X.vigia = navigator.geolocation.watchPosition(async (p) => {
    X.gps = `GPS ok (±${Math.round(p.coords.accuracy)} m) às ${new Date().toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })}`;
    X.pos = [p.coords.latitude, p.coords.longitude];
    const g = document.getElementById("gps-txt"); if (g) g.textContent = X.gps;
    if (Date.now() - X.ultimaPos < 15000) return;
    X.ultimaPos = Date.now();
    try { await S.api("/api/entregador/posicao", { corpo: { lat: p.coords.latitude, lng: p.coords.longitude, precisao: p.coords.accuracy } }); } catch (e) { X.gps = "Falha ao enviar posição: " + e.message; }
  }, () => { X.gps = "GPS não permitido — sem GPS você não recebe corridas. Libere a localização no navegador."; }, { enableHighAccuracy: true, maximumAge: 10000, timeout: 20000 });
}
function desligarGPS() { if (X.vigia !== null) { navigator.geolocation.clearWatch(X.vigia); X.vigia = null; } X.gps = "GPS desligado (offline)"; }

const mapa = (lat, lng) => lat !== null && lat !== undefined ? h("a", { href: `https://www.google.com/maps/dir/?api=1&destination=${lat},${lng}`, target: "_blank", rel: "noopener" }, "Abrir rota no mapa") : null;

function desenhar() {
  if (!X.dados) return;
  const d = X.dados; const e = d.entregador;
  const corridas = d.ativas.map((c) => {
    const faltam = c.oferta_expira_em ? Math.max(0, Math.round((new Date(c.oferta_expira_em) - Date.now()) / 1000)) : 0;
    const acoes = [];
    const ir = async (url, corpo, msg) => { X.dados = await S.acao(() => S.api(url, { corpo }), msg); desenhar(); };
    if (c.status === "ofertada") {
      acoes.push(h("div", { class: "contagem", "data-ate": c.oferta_expira_em }, `${faltam}s para responder`),
        h("div", { class: "linha" }, h("button", { class: "btn btn-verde", onclick: () => ir(`/api/entregador/corridas/${c.id}/responder`, { aceitar: true }, "Corrida aceita!") }, "Aceitar"),
          h("button", { class: "btn btn-linha", onclick: () => ir(`/api/entregador/corridas/${c.id}/responder`, { aceitar: false }, "Corrida recusada.") }, "Recusar")));
    } else if (c.status === "aceita") acoes.push(h("button", { class: "btn btn-escuro btn-bloco", onclick: () => ir(`/api/entregador/corridas/${c.id}/avancar`, { acao: "cheguei_loja" }, "Chegada registrada.") }, "Cheguei na loja"));
    else if (c.status === "em_coleta") acoes.push(h("button", { class: "btn btn-cta btn-bloco", onclick: () => ir(`/api/entregador/corridas/${c.id}/avancar`, { acao: "coletei" }, "Coleta confirmada. Boa entrega!") }, "Peguei o pedido"));
    else if (c.status === "em_rota") {
      const cod = h("input", { inputmode: "numeric", maxlength: 4, placeholder: "Código do cliente (4 dígitos)", style: { "font-size": "1.3rem", "text-align": "center" } });
      acoes.push(cod, h("button", { class: "btn btn-verde btn-bloco", style: { "margin-top": ".5rem" }, onclick: () => ir(`/api/entregador/corridas/${c.id}/avancar`, { acao: "entreguei", codigo: cod.value.trim() }, "Entrega confirmada!") }, "Confirmar entrega"));
    }
    return h("div", { class: "cartao corrida " + c.status },
      h("div", { class: "linha" }, h("h2", { style: { margin: 0 } }, `Pedido #${c.numero}`), h("span", { style: { "text-align": "right" } }, S.selo(S.dinheiro(c.ganho_centavos), "ok"))),
      h("div", { class: "mudo" }, c.resumo),
      h("div", { class: "passo" }, h("b", {}, "Coleta"), h("div", {}, `${c.empresa} — ${c.loja}`, h("div", { class: "mudo" }, c.loja_endereco || ""), mapa(c.loja_lat, c.loja_lng))),
      h("div", { class: "passo" }, h("b", {}, "Entrega"), h("div", {}, c.endereco_entrega || "—", h("div", { class: "mudo" }, `${c.cliente}${c.status !== "ofertada" && c.cliente_telefone ? " · " + c.cliente_telefone : ""}`), c.status === "em_rota" ? mapa(c.entrega_lat, c.entrega_lng) : null)),
      h("div", { class: "mapa", "data-corrida": c.id, style: { height: "220px", margin: ".6rem 0" } }),
      h("div", { class: "mudo" }, `${c.distancia_km !== null ? c.distancia_km + " km da loja até o cliente · " : ""}${c.eta_min ? "~" + c.eta_min + " min" : ""}${c.janela_fim ? " · prazo " + S.hora(c.janela_fim) : ""}`),
      h("div", { style: { "margin-top": ".7rem" } }, acoes));
  });
  moldura(
    h("div", { class: "cartao" }, h("div", { class: "interruptor" }, h("div", {}, h("h2", { style: { margin: 0 } }, X.eu.usuario.nome), e.online ? S.selo("Online — recebendo corridas", "ok") : S.selo("Offline", "")),
      h("button", { class: "btn " + (e.online ? "btn-linha" : "btn-verde"), onclick: async () => { X.dados = await S.acao(() => S.api("/api/entregador/online", { corpo: { online: !e.online } })); carregar(); } }, e.online ? "Ficar offline" : "Ficar online")),
      h("div", { class: "gps mudo", id: "gps-txt", style: { "margin-top": ".5rem" } }, X.gps)),
    h("div", { class: "kpis", style: { "margin-top": "1rem" } }, h("div", { class: "kpi verde" }, h("span", { class: "mudo" }, "Ganhos hoje"), h("b", {}, S.dinheiro(d.ganhos_hoje_centavos))),
      h("div", { class: "kpi" }, h("span", { class: "mudo" }, "Total"), h("b", {}, S.dinheiro(d.ganhos_total_centavos)))),
    corridas.length ? corridas : h("p", { class: "mudo", style: { "text-align": "center", margin: "2rem 0" } }, e.online ? "Aguardando corridas perto de você…" : "Fique online para receber corridas."),
    d.historico.length ? h("div", { class: "cartao", style: { "margin-top": "1rem" } }, h("h3", {}, "Últimas entregas"), d.historico.map((x) => h("div", { class: "linha mudo" }, h("span", {}, `#${x.numero} · ${x.empresa}`), h("span", { style: { "text-align": "right" } }, S.dinheiro(x.ganho_centavos))))) : null,
    h("p", { class: "mudo", style: { "margin-top": "1rem" } }, "Suporte: fale com a logística da loja ou com a equipe Sobrou+."));
  d.ativas.forEach((c) => {
    const el = document.querySelector(`[data-corrida="${c.id}"]`); if (!el) return;
    const m = S.mapa(el, [c.loja_lat || S.CENTRO_PADRAO[0], c.loja_lng || S.CENTRO_PADRAO[1]], 14);
    S.marcar(m, c.loja_lat, c.loja_lng, "#0A563A", "L", "Coleta: " + c.loja);
    S.marcar(m, c.entrega_lat, c.entrega_lng, "#F57A20", "C", "Entrega");
    const eu = X.pos || (e.lat !== null ? [e.lat, e.lng] : null);
    if (eu) S.marcar(m, eu[0], eu[1], "#2563EB", "•", "Você");
    const indoParaCliente = c.status === "em_rota";
    const origem = indoParaCliente ? (eu || [c.loja_lat, c.loja_lng]) : eu;
    const destino = indoParaCliente ? [c.entrega_lat, c.entrega_lng] : [c.loja_lat, c.loja_lng];
    if (origem) S.desenharRota(m, origem, destino, indoParaCliente ? "#F57A20" : "#2563EB");
    else S.enquadrar(m, [[c.loja_lat, c.loja_lng], [c.entrega_lat, c.entrega_lng]]);
  });
}

S.iniciarApp();
iniciar();
