/* Sobrou+ — painel (empresas parceiras, equipe Sobrou+, instituições). Cada tela aparece só para quem tem permissão. */
"use strict";
const h = S.h;
const P = { cfg: {}, eu: null, empresa: "", empresas: [], tela: "inicio" };
const pode = (r, a) => !!(P.eu && (P.eu.permissoes[r] || []).includes(a));
const ehInst = () => P.eu && P.eu.usuario.papel === "instituicao";
const eid = () => (P.eu.plataforma ? P.empresa : P.eu.usuario.empresa_id) || "";
const comEmpresa = (q = {}) => S.qs({ ...q, empresa_id: P.eu.plataforma ? P.empresa : undefined });

const TELAS = [
  ["Operação"],
  ["inicio", "Visão geral", () => true],
  ["pedidos", "Pedidos", () => pode("pedidos", "ver")],
  ["retirada", "Retirada (código/QR)", () => pode("retirada", "validar")],
  ["ofertas", "Ofertas e estoque", () => pode("ofertas", "ver")],
  ["unidades", "Unidades", () => pode("unidades", "ver")],
  ["Logística"],
  ["dispatch", "Dispatch", () => pode("dispatch", "ver")],
  ["entregadores", "Entregadores", () => pode("entregadores", "ver")],
  ["Dinheiro e impacto"],
  ["financeiro", "Financeiro e repasses", () => pode("financeiro", "ver")],
  ["doacoes", "Doações", () => pode("doacoes", "ver") || ehInst()],
  ["instituicoes", "Instituições", () => pode("instituicoes", "ver")],
  ["impacto", "Impacto", () => pode("impacto", "ver")],
  ["Gestão"],
  ["empresas", "Empresas parceiras", () => pode("empresas", "aprovar")],
  ["usuarios", "Usuários e acessos", () => pode("usuarios", "ver")],
  ["auditoria", "Auditoria", () => pode("auditoria", "ver")],
  ["aparencia", "Aparência e configurações", () => pode("config", "editar") || pode("sistema", "ver")],
  ["integracoes", "Integrações (ativar)", () => pode("sistema", "ver")],
  ["sistema", "Sistema e erros", () => pode("sistema", "ver")],
  ["conta", "Minha conta", () => true],
];

async function iniciar() {
  P.cfg = await S.api("/api/config").catch(() => ({}));
  S.tema(P.cfg.tema);
  const hash = location.hash.slice(1);
  if (hash === "cadastro") return telaCadastroEmpresa();
  if (hash === "instituicao") return telaCadastroInstituicao();
  try { P.eu = await S.api("/api/eu"); } catch (e) { return telaLogin(); }
  if (P.eu.usuario.papel === "cliente") { location.href = S.u("/"); return; }
  if (P.eu.usuario.papel === "entregador") { location.href = S.u("/entregador"); return; }
  S.tema(P.eu.tema);
  if (P.eu.usuario.trocar_senha) return telaTrocaObrigatoria();
  if (P.eu.plataforma && pode("empresas", "ver")) P.empresas = (await S.api("/api/empresas")).itens;
  P.tela = (hash && TELAS.some((t) => t[0] === hash)) ? hash : "inicio";
  montar();
  setInterval(atualizarSino, 20000);
}

// ------------------------------------------------------------------ entrada
function telaLogin() {
  const email = h("input", { type: "email", autocomplete: "email", required: true });
  const senha = h("input", { type: "password", autocomplete: "current-password", required: true });
  S.limpar(document.getElementById("raiz"), h("div", { class: "login" }, h("div", { class: "cartao" },
    S.marca(P.cfg, "Painel Sobrou+", "claro"),
    h("form", { onsubmit: async (e) => { e.preventDefault();
      try { await S.acao(() => S.api("/api/entrar", { corpo: { email: email.value.trim(), senha: senha.value } })); location.reload(); } catch (er) { /* já avisado */ } } },
      h("label", {}, "E-mail"), email, h("label", {}, "Senha"), senha,
      h("button", { class: "btn btn-cta btn-bloco", style: { "margin-top": "1rem" } }, "Entrar")),
    h("p", { class: "mudo", style: { "text-align": "center" } }, h("a", { href: "#cadastro", onclick: () => setTimeout(iniciar) }, "Quero ser parceiro Sobrou+"), " · ",
      h("a", { href: "#instituicao", onclick: () => setTimeout(iniciar) }, "Sou instituição social"), " · ", h("a", { href: S.u("/") }, "Ver ofertas")))));
}

function formulario(campos, botao, aoEnviar) {
  const ctl = {};
  const linhas = campos.map(([nome, rotulo, tipo = "text", extra = {}]) => {
    let el;
    if (tipo === "select") el = h("select", {}, extra.opcoes.map(([v, t]) => h("option", { value: v, selected: extra.valor === v }, t)));
    else if (tipo === "textarea") el = h("textarea", { rows: 3 }, extra.valor || "");
    else el = h("input", { type: tipo, value: extra.valor ?? "", placeholder: extra.placeholder || "", required: !!extra.obrigatorio, step: extra.step, min: extra.min });
    if (tipo === "checkbox") { el.checked = !!extra.valor; el.style.width = "auto"; }
    ctl[nome] = el;
    return h("div", {}, h("label", {}, rotulo), el);
  });
  const valores = () => Object.fromEntries(Object.entries(ctl).map(([k, el]) => [k, el.type === "checkbox" ? el.checked : el.value.trim()]));
  const form = h("form", { onsubmit: async (e) => { e.preventDefault(); const b = form.querySelector("button[type=submit]"); b.disabled = true;
    try { await aoEnviar(valores()); } catch (er) { /* aviso já mostrado */ } finally { b.disabled = false; } } },
    h("div", { class: "form-grade" }, linhas), h("button", { class: "btn btn-cta", type: "submit", style: { "margin-top": "1rem" } }, botao));
  form.ctl = ctl;
  return form;
}

function telaCadastroEmpresa() {
  const tipos = [["restaurante", "Restaurante"], ["lanchonete", "Lanchonete"], ["padaria", "Padaria"], ["mercado", "Mercado"], ["supermercado", "Supermercado"],
    ["hortifruti", "Hortifrúti"], ["cafe", "Café"], ["confeitaria", "Confeitaria"], ["outra", "Outra"]];
  S.limpar(document.getElementById("raiz"), h("div", { class: "login" }, h("div", { class: "cartao", style: { "max-width": "620px" } },
    S.marca(P.cfg, "Seja parceiro Sobrou+", "claro"),
    h("p", {}, "Transforme o que sobra no fim do dia em receita, com retirada no balcão ou entrega. A equipe Sobrou+ confere o cadastro antes de você publicar."),
    formulario([["nome", "Nome da empresa", "text", { obrigatorio: true }], ["tipo", "Tipo", "select", { opcoes: tipos }], ["documento", "CNPJ/CPF"],
      ["telefone", "Telefone"], ["nome_responsavel", "Seu nome", "text", { obrigatorio: true }], ["email_responsavel", "Seu e-mail (login)", "email", { obrigatorio: true }],
      ["senha", "Senha (8+ caracteres, letras e números)", "password", { obrigatorio: true }]], "Enviar cadastro",
    async (v) => { await S.acao(() => S.api("/api/cadastro/empresa", { corpo: v }), "Cadastro enviado!"); location.hash = ""; location.reload(); }),
    h("p", { class: "mudo" }, h("a", { href: "#", onclick: (e) => { e.preventDefault(); location.hash = ""; telaLogin(); } }, "← Voltar")))));
}

function telaCadastroInstituicao() {
  S.limpar(document.getElementById("raiz"), h("div", { class: "login" }, h("div", { class: "cartao", style: { "max-width": "620px" } },
    S.marca(P.cfg, "Instituições sociais", "claro"),
    h("p", {}, "Receba doações de alimentos das lojas parceiras. Toda doação passa por aceite, coleta e confirmação — com registro de quem, quando e quanto."),
    formulario([["nome", "Nome da instituição", "text", { obrigatorio: true }], ["documento", "CNPJ"], ["responsavel", "Responsável", "text", { obrigatorio: true }],
      ["telefone", "Telefone"], ["endereco", "Endereço"], ["cidade", "Cidade"], ["pessoas_atendidas", "Pessoas atendidas por mês", "number"]], "Enviar cadastro",
    async (v) => { const r = await S.acao(() => S.api("/api/cadastro/instituicao", { corpo: v })); S.toast(r.mensagem); setTimeout(() => { location.hash = ""; telaLogin(); }, 2500); }),
    h("p", { class: "mudo" }, h("a", { href: "#", onclick: (e) => { e.preventDefault(); location.hash = ""; telaLogin(); } }, "← Voltar")))));
}

function telaTrocaObrigatoria() {
  S.limpar(document.getElementById("raiz"), h("div", { class: "login" }, h("div", { class: "cartao" },
    S.marca(P.cfg, "Primeiro acesso", "claro"), h("p", {}, `Olá, ${P.eu.usuario.nome}. Por segurança, troque a senha inicial.`),
    formulario([["atual", "Senha atual", "password", { obrigatorio: true }], ["nova", "Nova senha (8+ caracteres, letras e números)", "password", { obrigatorio: true }]], "Salvar e entrar",
      async (v) => { await S.acao(() => S.api("/api/senha", { corpo: v }), "Senha trocada."); location.reload(); }))));
}

// ------------------------------------------------------------------ estrutura
function montar() {
  const nav = h("nav", {});
  let grupo = null;
  TELAS.forEach((t) => {
    if (t.length === 1) { grupo = h("div", { class: "grupo" }, t[0]); return; }
    if (!t[2]()) return;
    if (grupo) { nav.append(grupo); grupo = null; }
    nav.append(h("button", { class: P.tela === t[0] ? "ativo" : "", "data-tela": t[0], onclick: () => irPara(t[0]) }, t[1]));
  });
  const emp = P.eu.empresa;
  const nomeTopo = P.eu.plataforma ? (P.cfg.nome || "Sobrou+") + " — Central" : (emp && (emp.config.nome_exibicao || emp.nome)) || "Sobrou+";
  const lateral = h("aside", { class: "lateral", id: "lateral" }, S.marca(P.cfg, nomeTopo), nav);
  const seletor = P.eu.plataforma ? h("select", { onchange: (e) => { P.empresa = e.target.value; desenhar(); } },
    h("option", { value: "" }, "Todas as empresas"), P.empresas.map((x) => h("option", { value: x.id, selected: P.empresa === x.id }, x.nome + (x.aprovada ? "" : " (em análise)")))) : null;
  const cabeca = h("header", { class: "cabeca" },
    h("button", { class: "btn btn-linha btn-p menu-celular", onclick: () => lateral.classList.toggle("aberta") }, "☰ Menu"),
    h("div", { class: "titulo" }, h("b", { id: "tit" }, ""), h("span", {}, `${P.eu.usuario.nome} · ${P.eu.usuario.papel_nome}${emp ? " · " + emp.nome : ""}`)),
    seletor,
    emp && !emp.aprovada ? S.selo("Empresa em análise pela equipe Sobrou+", "aviso") : null,
    h("button", { class: "sino", id: "sino", onclick: abrirAvisos }, "Avisos"),
    h("button", { class: "btn btn-linha btn-p", onclick: async () => { await S.api("/api/sair", { corpo: {} }); location.href = S.u("/painel"); } }, "Sair"));
  S.limpar(document.getElementById("raiz"), h("div", { class: "painel" }, lateral, h("div", {}, cabeca, h("main", { class: "conteudo", id: "conteudo" }))));
  atualizarSino();
  desenhar();
}

function irPara(t) {
  P.tela = t; history.replaceState(null, "", "#" + t);
  document.querySelectorAll(".lateral nav button").forEach((b) => b.classList.toggle("ativo", b.dataset.tela === t));
  document.getElementById("lateral").classList.remove("aberta");
  desenhar();
}

async function atualizarSino() {
  const s = document.getElementById("sino"); if (!s) return;
  try { const r = await S.api("/api/avisos"); S.limpar(s, "Avisos", r.nao_lidos ? h("span", { class: "n" }, String(r.nao_lidos)) : null); } catch (e) { /* sessão */ }
}
async function abrirAvisos() {
  const r = await S.api("/api/avisos");
  S.folha(h("div", {}, h("h2", {}, "Avisos"), r.itens.length ? r.itens.map((a) => h("div", { class: "estado-int" }, h("span", {}, a.texto), h("span", { class: "mudo" }, S.data(a.criada_em))))
    : h("p", { class: "mudo" }, "Nenhum aviso."), h("p", { class: "mudo" }, "WhatsApp e notificação no celular: aguardando contas das integrações (ver Sistema).")));
  await S.api("/api/avisos/lidos", { corpo: {} }); atualizarSino();
}

async function desenhar() {
  const alvo = document.getElementById("conteudo");
  const t = TELAS.find((x) => x[0] === P.tela);
  document.getElementById("tit").textContent = t ? t[1] : "";
  S.limpar(alvo, h("p", { class: "mudo" }, "Carregando…"));
  try { await (FUNCOES[P.tela] || telaInicio)(alvo); }
  catch (e) { S.limpar(alvo, h("div", { class: "cartao" }, h("h3", {}, "Não foi possível abrir esta tela"), h("p", {}, e.message))); }
}
const kpi = (rot, val, cls) => h("div", { class: "kpi " + (cls || "") }, h("span", { class: "mudo" }, rot), h("b", {}, val));
const precisaEmpresa = (alvo, o_que) => { if (P.eu.plataforma && !P.empresa) { S.limpar(alvo, h("div", { class: "cartao" }, h("h3", {}, "Escolha uma empresa"), h("p", {}, `Para ${o_que}, escolha a empresa no seletor do topo.`))); return true; } return false; };

// ------------------------------------------------------------------ visão geral
async function telaInicio(alvo) {
  const blocos = [];
  if (ehInst()) {
    const [d, i] = await Promise.all([S.api("/api/doacoes"), S.api("/api/impacto")]);
    const pend = d.itens.filter((x) => ["proposta", "aceita", "coletada"].includes(x.status));
    blocos.push(h("div", { class: "kpis" }, kpi("Doações para responder", String(d.itens.filter((x) => x.status === "proposta").length), "laranja"),
      kpi("Em andamento", String(pend.length)), kpi("Alimento recebido", S.kg(i.kg_doados), "verde"), kpi("Pessoas beneficiadas", String(i.pessoas_beneficiadas), "verde")));
    blocos.push(h("button", { class: "btn btn-cta", onclick: () => irPara("doacoes") }, "Ver doações"));
    return S.limpar(alvo, blocos);
  }
  const pedidos = pode("pedidos", "ver") ? await S.api("/api/pedidos" + comEmpresa({ status: "ativos" })) : { itens: [] };
  const ofertas = pode("ofertas", "ver") ? await S.api("/api/ofertas" + comEmpresa()) : { itens: [] };
  const imp = pode("impacto", "ver") ? await S.api("/api/impacto" + comEmpresa()) : null;
  const fin = pode("financeiro", "ver") ? await S.api("/api/financeiro" + comEmpresa()) : null;
  const ativas = ofertas.itens.filter((o) => o.status === "ativa");
  blocos.push(h("div", { class: "kpis" },
    kpi("Pedidos em andamento", String(pedidos.itens.length), "laranja"),
    kpi("Para confirmar", String(pedidos.itens.filter((p) => p.status === "pago").length), pedidos.itens.some((p) => p.status === "pago") ? "coral" : ""),
    kpi("Ofertas no ar", String(ativas.length), "verde"),
    kpi("Estoque crítico", String(ativas.filter((o) => o.estoque_baixo).length), "coral"),
    imp ? kpi("Desperdício evitado", S.kg(imp.kg_desperdicio_evitado), "verde") : null,
    fin ? kpi(P.eu.plataforma ? "Receita Sobrou+" : "Receita recuperada", S.dinheiro(P.eu.plataforma ? fin.receita_plataforma_centavos : fin.receita_parceiros_centavos), "verde") : null,
    fin ? kpi("Economia dos clientes", S.dinheiro(fin.economia_clientes_centavos)) : null));
  if (P.eu.empresa && !P.eu.empresa.aprovada) blocos.push(h("div", { class: "cartao", style: { "margin-bottom": "1rem" } }, h("h3", {}, "Seu cadastro está em análise"),
    h("p", {}, "Enquanto isso, cadastre suas unidades e prepare as ofertas (com fotos reais). Assim que a equipe Sobrou+ aprovar, é só publicar.")));
  const urg = pedidos.itens.slice(0, 8);
  blocos.push(h("div", { class: "colunas" },
    h("div", { class: "cartao" }, h("h2", {}, "Pedidos agora"), urg.length ? urg.map((p) => h("div", { class: "estado-int" }, h("span", {}, `#${p.numero} · ${p.resumo || ""}`), S.selo(p.status_nome, S.SELO_PEDIDO[p.status])))
      : h("p", { class: "mudo" }, "Nenhum pedido em andamento."), h("button", { class: "btn btn-linha btn-p", onclick: () => irPara("pedidos") }, "Abrir pedidos")),
    h("div", { class: "cartao" }, h("h2", {}, "Ofertas no ar"), ativas.length ? ativas.slice(0, 8).map((o) => h("div", { class: "estado-int" }, h("span", {}, o.nome),
      h("span", {}, S.selo(`${o.disponivel}/${o.quantidade_total}`, o.estoque_baixo ? "urgente" : "ok"), " ", S.selo("até " + S.hora(o.fim), "aviso"))))
      : h("p", { class: "mudo" }, "Nenhuma oferta publicada."), pode("ofertas", "editar") ? h("button", { class: "btn btn-cta btn-p", onclick: () => { irPara("ofertas"); setTimeout(() => editarOferta(null), 300); } }, "+ Nova oferta") : null)));
  S.limpar(alvo, blocos);
}

// ------------------------------------------------------------------ pedidos
async function telaPedidos(alvo) {
  const filtro = P._filtroPedidos || "ativos";
  const r = await S.api("/api/pedidos" + comEmpresa({ status: filtro === "todos" ? "" : filtro }));
  const sel = h("select", { style: { width: "auto" }, onchange: (e) => { P._filtroPedidos = e.target.value; desenhar(); } },
    [["ativos", "Em andamento"], ["todos", "Todos"], ["pago", "Pagos (confirmar)"], ["aguardando_retirada", "Aguardando retirada"], ["aguardando_entregador", "Aguardando entregador"],
      ["concluido", "Concluídos"], ["nao_retirado", "Não retirados"], ["cancelado", "Cancelados"], ["expirado", "Expirados"]].map(([v, t]) => h("option", { value: v, selected: v === filtro }, t)));
  const botoes = (p) => {
    if (!pode("pedidos", "operar")) return null;
    const b = [];
    const ir = (acao, txt, cls) => b.push(h("button", { class: "btn btn-p " + cls, onclick: async () => { await S.acao(() => S.api(`/api/pedidos/${p.id}/avancar`, { corpo: { acao } }), "Pedido atualizado."); desenhar(); } }, txt));
    if (p.status === "pago") ir("receber", "Confirmar recebimento", "btn-cta");
    if (p.status === "recebido") ir("preparar", "Começar a preparar", "btn-escuro");
    if (p.status === "preparando") ir("pronto", p.modo === "retirada" ? "Pronto para retirada" : "Pronto — chamar entregador", "btn-verde");
    if (p.status === "nao_retirado" && pode("doacoes", "propor")) b.push(h("button", { class: "btn btn-p btn-linha", onclick: () => doarPedido(p) }, "Destinar para doação"));
    if (pode("pedidos", "cancelar") && ["pago", "recebido", "preparando", "aguardando_retirada", "aguardando_entregador", "entregador_designado"].includes(p.status))
      b.push(h("button", { class: "btn btn-p btn-linha", onclick: async () => { const m = prompt("Motivo do cancelamento (o cliente recebe o estorno):"); if (!m) return;
        await S.acao(() => S.api(`/api/pedidos/${p.id}/cancelar`, { corpo: { motivo: m } }), "Pedido cancelado e estornado."); desenhar(); } }, "Cancelar"));
    return h("div", { class: "linha", style: { "margin-top": ".5rem" } }, b);
  };
  S.limpar(alvo, h("div", { class: "barra-acoes" }, h("h1", {}, "Pedidos"), sel, h("button", { class: "btn btn-linha btn-p", onclick: desenhar }, "Atualizar")),
    r.itens.length ? h("div", { class: "grade" }, r.itens.map((p) => h("div", { class: "cartao pedido " + p.status },
      h("div", { class: "linha" }, h("b", {}, `#${p.numero}`), h("span", { style: { "text-align": "right" } }, S.selo(p.status_nome, S.SELO_PEDIDO[p.status]))),
      h("div", {}, p.resumo), h("div", { class: "mudo" }, `${p.cliente} · ${p.modo === "retirada" ? "Retirada " + S.janela(p.janela_inicio, p.janela_fim) : "Entrega"}${P.eu.plataforma ? " · " + p.empresa : ""}`),
      h("div", { class: "linha mudo" }, h("span", {}, S.data(p.criado_em)), h("b", { style: { "text-align": "right" } }, S.dinheiro(p.total_centavos))),
      h("a", { href: "#", class: "mudo", onclick: (e) => { e.preventDefault(); detalhePedido(p.id); } }, "Ver histórico"), botoes(p))))
      : h("p", { class: "mudo" }, "Nenhum pedido neste filtro."));
}

async function detalhePedido(id) {
  const p = await S.api("/api/pedidos/" + id);
  S.folha(h("div", {}, h("h2", {}, `Pedido #${p.numero}`), h("p", {}, `${p.cliente || ""} ${p.cliente_telefone ? "· " + p.cliente_telefone : ""}`),
    p.endereco_entrega ? h("p", {}, "Entregar em: " + p.endereco_entrega) : null,
    p.itens.map((i) => h("div", {}, `${i.quantidade}× ${i.nome} — ${S.dinheiro(i.preco_centavos * i.quantidade)}`)),
    h("p", {}, `Produtos ${S.dinheiro(p.subtotal_centavos)} · Taxa Sobrou+ ${S.dinheiro(p.taxa_centavos)} (${p.taxa_percentual}%) · Repasse ${S.dinheiro(p.repasse_centavos)}`),
    h("h3", {}, "Histórico"), p.historico.map((x) => h("div", { class: "mudo" }, `${S.data(x.quando)} — ${x.para_status.replace(/_/g, " ")}${x.usuario ? " · " + x.usuario : ""}${x.nota ? " · " + x.nota : ""}`))));
}

// ------------------------------------------------------------------ retirada
async function telaRetirada(alvo) {
  if (precisaEmpresa(alvo, "validar retiradas")) return;
  const cod = h("input", { placeholder: "1234-5678", autocomplete: "off", inputmode: "text" });
  const res = h("div", { style: { "margin-top": "1rem" } });
  const validar = async (codigo) => {
    try {
      const p = await S.api("/api/retirada", { corpo: { codigo, empresa_id: eid() } });
      S.limpar(res, h("div", { class: "cartao", style: { "border-left": "6px solid var(--verde-vivo)" } }, h("h2", {}, `✓ Pedido #${p.numero} liberado`),
        p.itens.map((i) => h("div", { style: { "font-size": "1.1rem" } }, `${i.quantidade}× ${i.nome}`)), h("p", { class: "mudo" }, `Cliente: ${p.cliente}. Retirada registrada e estoque baixado.`)));
      cod.value = "";
    } catch (e) { S.limpar(res, h("div", { class: "cartao", style: { "border-left": "6px solid var(--coral)" } }, h("h2", {}, "✗ Não liberar"), h("p", {}, e.message))); }
  };
  const video = h("video", { id: "camera", playsinline: true, muted: true, class: "oculto" });
  const lerQR = async () => {
    if (!("BarcodeDetector" in window)) return S.toast("Este navegador não lê QR pela câmera. Digite o número do pedido e o PIN.", true);
    try {
      const fluxo = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" } });
      video.srcObject = fluxo; video.classList.remove("oculto"); await video.play();
      const det = new BarcodeDetector({ formats: ["qr_code"] });
      const parar = () => { fluxo.getTracks().forEach((t) => t.stop()); video.classList.add("oculto"); };
      const passo = async () => {
        if (video.classList.contains("oculto")) return;
        const achados = await det.detect(video).catch(() => []);
        if (achados.length) { parar(); validar(achados[0].rawValue); } else requestAnimationFrame(passo);
      };
      passo(); setTimeout(parar, 60000);
    } catch (e) { S.toast("Não consegui abrir a câmera.", true); }
  };
  S.limpar(alvo, h("div", { class: "cartao retirada-caixa" }, h("h1", {}, "Retirada no balcão"),
    h("p", { class: "mudo" }, "Peça ao cliente o número do pedido e o PIN de 4 dígitos (ex.: 1023-4821) ou leia o QR do app dele."),
    cod, h("div", { class: "linha", style: { "margin-top": ".7rem" } }, h("button", { class: "btn btn-verde", onclick: () => validar(cod.value.trim()) }, "Validar código"),
      h("button", { class: "btn btn-linha", onclick: lerQR }, "Ler QR com a câmera")), video, res));
  cod.focus();
}

// ------------------------------------------------------------------ ofertas
async function telaOfertas(alvo) {
  const r = await S.api("/api/ofertas" + comEmpresa());
  const selo = { ativa: ["No ar", "ok"], esgotada: ["Esgotada", "urgente"], rascunho: ["Rascunho", ""], pausada: ["Pausada", "aviso"], encerrada: ["Encerrada", ""] };
  S.limpar(alvo, h("div", { class: "barra-acoes" }, h("h1", {}, "Ofertas e estoque"),
    pode("ofertas", "editar") ? h("button", { class: "btn btn-cta", onclick: () => editarOferta(null) }, "+ Nova oferta") : null),
    r.itens.length ? h("div", { class: "cartao rolagem" }, h("table", { class: "tabela" },
      h("thead", {}, h("tr", {}, ["", "Oferta", "Preço", "Estoque", "Venda", "Estado", ""].map((t) => h("th", {}, t)))),
      h("tbody", {}, r.itens.map((o) => h("tr", {},
        h("td", {}, o.miniatura ? h("img", { class: "mini-foto", src: o.miniatura, alt: "" }) : h("div", { class: "sem-mini" }, "sem foto")),
        h("td", {}, h("b", {}, o.nome), h("div", { class: "mudo" }, `${o.tipo_nome} · ${o.unidade}${P.eu.plataforma ? " · " + o.empresa : ""}`)),
        h("td", {}, h("div", { class: "preco", style: { "font-size": "1rem" } }, S.dinheiro(o.preco_centavos)), h("div", { class: "preco-de" }, S.dinheiro(o.preco_normal_centavos)),
          o.regra_preco !== "fixo" ? S.selo("preço automático", "tecnico") : null),
        h("td", {}, h("b", {}, `${o.disponivel} disp.`), h("div", { class: "mudo" }, `${o.vendida} vend. · ${o.reservada} res. · ${o.expirada} sobra · ${o.destinada} doação`)),
        h("td", { class: "mudo" }, `${S.data(o.inicio)} → ${S.hora(o.fim)}`, o.retirada_inicio ? h("div", {}, "Retirada " + S.janela(o.retirada_inicio, o.retirada_fim)) : null),
        h("td", {}, S.selo(...selo[o.status]), o.estoque_baixo ? h("div", {}, S.selo("estoque crítico", "urgente")) : null),
        h("td", {}, h("div", { class: "linha", style: { "flex-wrap": "nowrap" } }, acoesOferta(o)))))))) : h("div", { class: "cartao" }, h("p", {}, "Nenhuma oferta ainda."), h("p", { class: "mudo" }, "Comece cadastrando uma unidade e depois a primeira oferta, com foto real.")));
}

function acoesOferta(o) {
  const b = [];
  const st = async (s, msg) => { await S.acao(() => S.api(`/api/ofertas/${o.id}/status`, { corpo: { status: s } }), msg); desenhar(); };
  if (pode("ofertas", "editar")) {
    if (o.status !== "encerrada") b.push(h("button", { class: "btn btn-p btn-linha", onclick: () => editarOferta(o.id) }, "Editar"));
    if (["rascunho", "pausada"].includes(o.status)) b.push(h("button", { class: "btn btn-p btn-verde", onclick: () => st("ativa", "Oferta publicada!") }, "Publicar"));
    if (o.status === "ativa") b.push(h("button", { class: "btn btn-p btn-linha", onclick: () => st("pausada", "Oferta pausada.") }, "Pausar"));
    if (["ativa", "pausada", "esgotada", "rascunho"].includes(o.status)) b.push(h("button", { class: "btn btn-p btn-linha", onclick: () => { if (confirm("Encerrar a venda agora? O que sobrar fica disponível para doação.")) st("encerrada", "Oferta encerrada."); } }, "Encerrar"));
  }
  if (pode("estoque", "editar") && o.status !== "encerrada") b.push(h("button", { class: "btn btn-p btn-linha", onclick: async () => {
    const d = prompt("Ajuste de estoque (ex.: 3 para somar, -2 para tirar):"); if (!d) return; const m = prompt("Motivo do ajuste:"); if (!m) return;
    await S.acao(() => S.api(`/api/ofertas/${o.id}/estoque`, { corpo: { delta: parseInt(d, 10), motivo: m } }), "Estoque ajustado."); desenhar(); } }, "Estoque"));
  if (pode("doacoes", "propor") && (o.expirada > 0 || (o.status === "ativa" && o.disponivel > 0))) b.push(h("button", { class: "btn btn-p btn-linha", onclick: () => doarOferta(o) }, "Doar"));
  b.push(h("button", { class: "btn btn-p btn-linha", onclick: () => historicoOferta(o.id) }, "Histórico"));
  return b;
}

async function historicoOferta(id) {
  const o = await S.api("/api/ofertas/" + id);
  S.folha(h("div", {}, h("h2", {}, o.nome), h("h3", {}, "Preço"), o.historico_precos.length ? o.historico_precos.map((x) => h("div", { class: "mudo" },
    `${S.data(x.quando)} — ${S.dinheiro(x.de_centavos)} → ${S.dinheiro(x.para_centavos)} (${x.origem === "regra" ? "automático" : "manual"}${x.motivo ? ": " + x.motivo : ""})`)) : h("p", { class: "mudo" }, "Sem mudanças."),
    h("h3", {}, "Estoque"), o.movimentos.map((m) => h("div", { class: "mudo" }, `${S.data(m.quando)} — ${m.tipo} ${m.quantidade}${m.usuario ? " · " + m.usuario : ""}${m.motivo ? " · " + m.motivo : ""}`))));
}

async function editarOferta(id) {
  const o = id ? await S.api("/api/ofertas/" + id) : null;
  const uni = (await S.api("/api/unidades" + comEmpresa())).itens.filter((u) => u.ativa);
  if (!uni.length) { S.toast(P.eu.plataforma && !P.empresa ? "Escolha a empresa no topo primeiro." : "Cadastre uma unidade antes da oferta.", true); return; }
  const agora = new Date(); const mais = (min) => new Date(agora.getTime() + min * 60000).toISOString();
  const v = o || { tipo: "produto", categoria: "refeicoes", quantidade_total: 5, limite_por_cliente: 3, estoque_critico: 2, peso_kg_unidade: 0.5,
    inicio: agora.toISOString(), fim: mais(180), retirada_inicio: mais(60), retirada_fim: mais(180), permite_retirada: 1, permite_entrega: 0, regra_preco: "fixo", prioridade: 0 };
  const est = { foto_id: v.foto_id || null, fotos: (o && o.fotos ? o.fotos.map((f) => f.split("/").pop()) : []) };
  const fotoPrev = h("div", { class: "linha" });
  const desenharFotos = () => S.limpar(fotoPrev, est.fotos.length ? est.fotos.map((f) => h("img", { class: "mini-foto", src: `fotos/${f}/mini`, alt: "" })) : h("div", { class: "sem-mini" }, "sem foto"));
  desenharFotos();
  const entrada = h("input", { type: "file", accept: "image/*", capture: "environment", multiple: true, onchange: async (e) => {
    for (const arq of e.target.files) {
      try { const c = await S.comprimir(arq); const r = await S.api("/api/fotos", { corpo: { ...c, empresa_id: eid() } }); est.fotos.push(r.id); if (!est.foto_id) est.foto_id = r.id; desenharFotos(); }
      catch (er) { S.toast(er.message, true); }
    } } });
  const cats = Object.entries(S.CATEGORIAS).filter(([k]) => k !== "todos");
  const f = formulario([
    ["unidade_id", "Unidade", "select", { opcoes: uni.map((u) => [u.id, u.nome]), valor: v.unidade_id }],
    ["tipo", "Tipo de oferta", "select", { opcoes: [["produto", "Produto específico"], ["cesta", "Cesta surpresa"], ["kit", "Kit de excedentes"]], valor: v.tipo }],
    ["nome", "Nome", "text", { valor: v.nome, obrigatorio: true, placeholder: "Ex.: Marmita Executiva" }],
    ["categoria", "Categoria", "select", { opcoes: cats, valor: v.categoria }],
    ["descricao", "Descrição", "textarea", { valor: v.descricao }],
    ["preco_normal", "Preço normal (R$)", "text", { valor: S.reais(v.preco_normal_centavos), obrigatorio: true, placeholder: "24,90" }],
    ["preco", "Preço Sobrou+ (R$)", "text", { valor: S.reais(v.preco_base_centavos ?? v.preco_centavos), obrigatorio: true, placeholder: "12,50" }],
    ["preco_minimo", "Preço mínimo (piso do automático)", "text", { valor: S.reais(v.preco_minimo_centavos) }],
    ["valor_estimado_min", "Cesta: vale no mínimo (R$)", "text", { valor: S.reais(v.valor_estimado_min_centavos) }],
    ["valor_estimado_max", "Cesta: vale no máximo (R$)", "text", { valor: S.reais(v.valor_estimado_max_centavos) }],
    ["quantidade_total", "Quantidade", "number", { valor: v.quantidade_total, min: 1 }],
    ["limite_por_cliente", "Limite por cliente", "number", { valor: v.limite_por_cliente, min: 1 }],
    ["estoque_critico", "Avisar estoque crítico com", "number", { valor: v.estoque_critico, min: 0 }],
    ["peso_kg_unidade", "Peso por unidade (kg, para o impacto)", "text", { valor: String(v.peso_kg_unidade).replace(".", ",") }],
    ["inicio", "Início da venda", "datetime-local", { valor: S.paraInput(v.inicio) }],
    ["fim", "Fim da venda", "datetime-local", { valor: S.paraInput(v.fim) }],
    ["retirada_inicio", "Retirada a partir de", "datetime-local", { valor: S.paraInput(v.retirada_inicio) }],
    ["retirada_fim", "Retirada até", "datetime-local", { valor: S.paraInput(v.retirada_fim) }],
    ["validade", "Consumir até (validade)", "datetime-local", { valor: S.paraInput(v.validade) }],
    ["permite_retirada", "Aceita retirada", "checkbox", { valor: !!v.permite_retirada }],
    ["permite_entrega", "Aceita entrega", "checkbox", { valor: !!v.permite_entrega }],
    ["prioridade", "Destaque (0 a 10)", "number", { valor: v.prioridade, min: 0 }],
    ["regra_preco", "Preço", "select", { opcoes: [["fixo", "Fixo"], ["progressivo", "Automático: baixa perto do fim"], ["estoque", "Automático: baixa quando sobra pouco"]], valor: v.regra_preco }],
  ], id ? "Salvar oferta" : "Criar oferta (fica como rascunho)", async (val) => {
    const dados = { ...val, peso_kg_unidade: val.peso_kg_unidade.replace(",", "."), inicio: S.doInput(val.inicio), fim: S.doInput(val.fim),
      retirada_inicio: S.doInput(val.retirada_inicio), retirada_fim: S.doInput(val.retirada_fim), validade: S.doInput(val.validade),
      foto_id: est.fotos[0] || null, fotos: est.fotos, regra_preco_dados: degraus(), empresa_id: eid() };
    await S.acao(() => S.api(id ? "/api/ofertas/" + id : "/api/ofertas", { method: id ? "PUT" : "POST", corpo: dados }), "Oferta salva.");
    folha.fechar(); desenhar();
  });
  // degraus do preço automático
  const caixaDegraus = h("div");
  const lista = (v.regra_preco_dados || []).map((d) => ({ gatilho: d.minutos_antes_fim ?? d.restante_ate, preco: S.reais(d.preco_centavos) }));
  const degraus = () => f.ctl.regra_preco.value === "fixo" ? [] : lista.filter((d) => d.gatilho !== "" && d.preco !== "").map((d) =>
    f.ctl.regra_preco.value === "progressivo" ? { minutos_antes_fim: parseInt(d.gatilho, 10), preco: d.preco } : { restante_ate: parseInt(d.gatilho, 10), preco: d.preco });
  const desenharDegraus = () => {
    const r = f.ctl.regra_preco.value;
    if (r === "fixo") return S.limpar(caixaDegraus, h("p", { class: "mudo" }, "O preço só muda quando você alterar. Toda mudança fica no histórico."));
    if (!lista.length) lista.push({ gatilho: r === "progressivo" ? 60 : 3, preco: "" });
    S.limpar(caixaDegraus, h("p", { class: "mudo" }, r === "progressivo" ? "Quando faltar X minutos para o fim da venda, o preço vai para…" : "Quando restar X unidades ou menos, o preço vai para…",
      " Nunca abaixo do preço mínimo. Cada mudança é registrada."),
      lista.map((d, i) => h("div", { class: "degrau" },
        h("div", {}, h("label", {}, r === "progressivo" ? "Faltando (min)" : "Restando (un.)"), h("input", { type: "number", value: d.gatilho, oninput: (e) => { d.gatilho = e.target.value; } })),
        h("div", {}, h("label", {}, "Preço (R$)"), h("input", { value: d.preco, oninput: (e) => { d.preco = e.target.value; } })),
        h("button", { type: "button", class: "btn btn-p btn-linha", onclick: () => { lista.splice(i, 1); desenharDegraus(); } }, "Tirar"))),
      h("button", { type: "button", class: "btn btn-p btn-linha", style: { "margin-top": ".5rem" }, onclick: () => { lista.push({ gatilho: "", preco: "" }); desenharDegraus(); } }, "+ degrau"));
  };
  f.ctl.regra_preco.addEventListener("change", () => { lista.length = 0; desenharDegraus(); });
  f.insertBefore(h("div", {}, h("label", {}, "Regra do preço automático"), caixaDegraus), f.lastChild);
  desenharDegraus();
  const folha = S.folha(h("div", {}, h("h2", {}, id ? "Editar oferta" : "Nova oferta"),
    h("label", {}, "Fotos reais do alimento (a primeira é a principal)"), fotoPrev, entrada,
    h("p", { class: "mudo" }, "A foto é comprimida no aparelho antes de enviar. Sem foto, a oferta não pode ser publicada."), f));
  folha.el.style.maxWidth = "820px";
}

// ------------------------------------------------------------------ unidades
async function telaUnidades(alvo) {
  const r = await S.api("/api/unidades" + comEmpresa());
  S.limpar(alvo, h("div", { class: "barra-acoes" }, h("h1", {}, "Unidades"), pode("unidades", "editar") ? h("button", { class: "btn btn-cta", onclick: () => editarUnidade(null) }, "+ Nova unidade") : null),
    r.itens.length ? h("div", { class: "grade" }, r.itens.map((u) => h("div", { class: "cartao" }, h("b", {}, u.nome), u.empresa ? h("div", { class: "mudo" }, u.empresa) : null,
      h("div", { class: "mudo" }, [u.endereco, u.bairro, u.cidade].filter(Boolean).join(", ") || "Endereço não informado"),
      h("div", {}, u.lat !== null ? S.selo("localização definida", "ok") : S.selo("sem localização — distância e entrega não calculam", "aviso"), " ", u.ativa ? S.selo("ativa", "ok") : S.selo("inativa")),
      pode("unidades", "editar") ? h("button", { class: "btn btn-p btn-linha", style: { "margin-top": ".5rem" }, onclick: () => editarUnidade(u) }, "Editar") : null)))
      : h("p", { class: "mudo" }, "Nenhuma unidade. Cadastre o endereço onde o cliente retira."));
}

function editarUnidade(u) {
  if (!u && precisaEmpresa(document.getElementById("conteudo"), "cadastrar unidades")) return;
  const v = u || {};
  const f = formulario([["nome", "Nome da unidade", "text", { valor: v.nome, obrigatorio: true }], ["endereco", "Endereço", "text", { valor: v.endereco }],
    ["bairro", "Bairro", "text", { valor: v.bairro }], ["cidade", "Cidade", "text", { valor: v.cidade }], ["telefone", "Telefone", "text", { valor: v.telefone }],
    ["instrucoes_retirada", "Instruções de retirada", "text", { valor: v.instrucoes_retirada, placeholder: "Ex.: balcão lateral, falar com o caixa" }],
    ["lat", "Latitude", "text", { valor: v.lat ?? "" }], ["lng", "Longitude", "text", { valor: v.lng ?? "" }], ["ativa", "Unidade ativa", "checkbox", { valor: u ? !!u.ativa : true }]],
  "Salvar unidade", async (val) => {
    await S.acao(() => S.api(u ? "/api/unidades/" + u.id : "/api/unidades", { method: u ? "PUT" : "POST", corpo: { ...val, ativa: val.ativa ? 1 : 0, empresa_id: eid() } }), "Unidade salva.");
    folha.fechar(); desenhar();
  });
  const caixaMapa = h("div", { class: "mapa", style: { margin: ".6rem 0" } });
  let mapa = null; let pino = null;
  const posicionar = (lat, lng, centralizar = true) => {
    f.ctl.lat.value = Number(lat).toFixed(6); f.ctl.lng.value = Number(lng).toFixed(6);
    if (!mapa) return;
    if (!pino) { pino = L.marker([lat, lng], { draggable: true, icon: S.pino("#0A563A", "L") }).addTo(mapa);
      pino.on("dragend", () => { const p = pino.getLatLng(); f.ctl.lat.value = p.lat.toFixed(6); f.ctl.lng.value = p.lng.toFixed(6); }); }
    else pino.setLatLng([lat, lng]);
    if (centralizar) mapa.setView([lat, lng], 17);
  };
  const folha = S.folha(h("div", {}, h("h2", {}, u ? "Editar unidade" : "Nova unidade"),
    h("label", {}, "Buscar o endereço no mapa"),
    S.buscaEndereco((it) => { posicionar(it.lat, it.lng); if (!f.ctl.endereco.value) f.ctl.endereco.value = it.nome.split(",").slice(0, 2).join(","); }),
    h("div", { class: "linha", style: { "margin-top": ".4rem" } },
      h("button", { class: "btn btn-p btn-linha", onclick: async () => { try { const p = await S.posicao(); posicionar(p.lat, p.lng); S.toast("Localização preenchida."); } catch (e) { S.toast(e.message, true); } } }, "Estou na loja: usar minha localização")),
    caixaMapa, h("p", { class: "mudo" }, "Arraste o pino até a porta da loja ou toque no mapa. É esse ponto que conta para a distância e para o entregador."), f));
  folha.el.style.maxWidth = "720px";
  mapa = S.mapa(caixaMapa, v.lat !== null && v.lat !== undefined ? [v.lat, v.lng] : null, v.lat ? 17 : 13);
  if (mapa) mapa.on("click", (e) => posicionar(e.latlng.lat, e.latlng.lng, false));
  if (v.lat !== null && v.lat !== undefined) posicionar(v.lat, v.lng);
}

// ------------------------------------------------------------------ dispatch e entregadores
async function telaDispatch(alvo) {
  const r = await S.api("/api/dispatch" + comEmpresa());
  const online = r.entregadores.filter((e) => e.online);
  S.limpar(alvo, h("div", { class: "barra-acoes" }, h("h1", {}, "Dispatch"), h("button", { class: "btn btn-linha btn-p", onclick: desenhar }, "Atualizar")),
    h("div", { class: "kpis" }, kpi("Sem entregador", String(r.sem_entregador), r.sem_entregador ? "coral" : ""), kpi("Entregadores online", String(online.length), "verde"),
      kpi("Em rota", String(r.entregas.filter((e) => ["aceita", "em_coleta", "em_rota"].includes(e.status)).length), "laranja")),
    h("div", { class: "mapa alto", id: "mapa-dispatch", style: { "margin-bottom": "1rem" } }),
    h("p", { class: "mudo" }, "Ordem de prioridade: janela/validade mais curta primeiro. Escolha do entregador: distância pelas ruas até a loja (GPS dos últimos 10 min), capacidade, preferência pelo entregador próprio da loja. Recusa ou 90 s sem resposta → próximo entregador."),
    h("div", { class: "cartao rolagem" }, h("table", { class: "tabela" }, h("thead", {}, h("tr", {}, ["Pedido", "Loja", "Destino", "Prazo", "Entregador", "Estado", ""].map((t) => h("th", {}, t)))),
      h("tbody", {}, r.entregas.map((e) => h("tr", {}, h("td", {}, `#${e.numero}`), h("td", {}, e.loja), h("td", {}, e.endereco_entrega || "—", e.distancia_km !== null ? h("div", { class: "mudo" }, `${e.distancia_km} km`) : null),
        h("td", {}, e.janela_fim ? S.hora(e.janela_fim) : "—"), h("td", {}, e.entregador || "—", e.eta_min ? h("div", { class: "mudo" }, `~${e.eta_min} min`) : null),
        h("td", {}, S.selo(e.status.replace(/_/g, " "), { aguardando: "urgente", ofertada: "aviso", entregue: "ok", falhou: "urgente" }[e.status] || "oferta")),
        h("td", {}, pode("dispatch", "operar") && ["aguardando", "ofertada"].includes(e.status) ? h("select", { style: { width: "auto" }, onchange: async (ev) => {
          if (!ev.target.value) return; await S.acao(() => S.api(`/api/dispatch/${e.id}/designar`, { corpo: { entregador_id: ev.target.value } }), "Corrida enviada ao entregador."); desenhar(); } },
          h("option", { value: "" }, "Designar…"), r.entregadores.map((x) => h("option", { value: x.id }, `${x.nome}${x.online ? " (online)" : ""}`))) : null)))))));
  mapaDispatch(r);
}

function mapaDispatch(r) {
  const el = document.getElementById("mapa-dispatch"); if (!el) return;
  const m = S.mapa(el, null, 13); const pontos = [];
  r.entregas.filter((e) => !["entregue", "falhou"].includes(e.status)).forEach((e) => {
    if (e.loja_lat !== null) { S.marcar(m, e.loja_lat, e.loja_lng, "#0A563A", "L", `#${e.numero} — coleta: ${e.loja}`); pontos.push([e.loja_lat, e.loja_lng]); }
    if (e.entrega_lat !== null) { S.marcar(m, e.entrega_lat, e.entrega_lng, e.status === "aguardando" ? "#E74A3B" : "#F57A20", "C", `#${e.numero} — entrega: ${e.endereco_entrega || ""}`); pontos.push([e.entrega_lat, e.entrega_lng]); }
    if (e.loja_lat !== null && e.entrega_lat !== null) L.polyline([[e.loja_lat, e.loja_lng], [e.entrega_lat, e.entrega_lng]], { color: "#F57A20", weight: 2, dashArray: "4 6" }).addTo(m);
  });
  r.entregadores.filter((x) => x.online && x.lat !== null).forEach((x) => { S.marcar(m, x.lat, x.lng, "#2563EB", "E", `${x.nome} (GPS ${S.hora(x.posicao_em)})`); pontos.push([x.lat, x.lng]); });
  S.enquadrar(m, pontos);
}

async function telaEntregadores(alvo) {
  const r = await S.api("/api/dispatch" + comEmpresa());
  S.limpar(alvo, h("div", { class: "barra-acoes" }, h("h1", {}, "Entregadores"), pode("usuarios", "editar") ? h("button", { class: "btn btn-cta", onclick: () => novoUsuario("entregador") }, "+ Novo entregador") : null),
    h("p", { class: "mudo" }, "O entregador entra pelo celular em /entregador, fica online e o GPS do aparelho envia a posição. Senha inicial padrão, com troca no primeiro acesso."),
    r.entregadores.length ? h("div", { class: "grade" }, r.entregadores.map((e) => h("div", { class: "cartao" }, h("b", {}, e.nome),
      h("div", { class: "mudo" }, `${e.empresa_id ? "Próprio da loja" : "Rede Sobrou+"}${e.veiculo ? " · " + e.veiculo : ""} · capacidade ${e.capacidade}`),
      h("div", {}, e.online ? S.selo("online", "ok") : S.selo("offline"), " ", e.posicao_em ? S.selo("GPS " + S.hora(e.posicao_em), "tecnico") : S.selo("sem GPS", "aviso")))))
      : h("p", { class: "mudo" }, "Nenhum entregador cadastrado."));
}

// ------------------------------------------------------------------ financeiro
async function telaFinanceiro(alvo) {
  const [f, rep, conc] = await Promise.all([S.api("/api/financeiro" + comEmpresa()), S.api("/api/repasses" + comEmpresa()), S.api("/api/conciliacao" + comEmpresa())]);
  const blocos = [h("h1", {}, "Financeiro e repasses"), h("div", { class: "aviso-teste selo aviso", style: { margin: "0 0 1rem", padding: ".5rem .8rem", "border-radius": "10px", display: "block" } }, f.aviso),
    h("div", { class: "kpis" }, kpi("Vendas (GMV)", S.dinheiro(f.gmv_centavos)), kpi("Economia dos clientes", S.dinheiro(f.economia_clientes_centavos), "verde"),
      kpi("Receita recuperada dos parceiros", S.dinheiro(f.receita_parceiros_centavos), "verde"), kpi("Receita Sobrou+ (taxa)", S.dinheiro(f.receita_plataforma_centavos), "laranja"),
      kpi("Entregas", S.dinheiro(f.custo_entrega_centavos)), kpi("A repassar", S.dinheiro(f.a_repassar_centavos), f.a_repassar_centavos ? "coral" : ""),
      kpi("Em andamento", `${f.em_andamento.n} · ${S.dinheiro(f.em_andamento.v)}`))];
  if (f.por_empresa.length > 1 || P.eu.plataforma) blocos.push(h("div", { class: "cartao rolagem", style: { "margin-bottom": "1rem" } }, h("h2", {}, "Por empresa"),
    h("table", { class: "tabela" }, h("thead", {}, h("tr", {}, ["Empresa", "Pedidos", "Produtos", "Taxa", "Repasse", ""].map((t) => h("th", {}, t)))),
      h("tbody", {}, f.por_empresa.map((e) => h("tr", {}, h("td", {}, e.nome), h("td", {}, String(e.pedidos)), h("td", {}, S.dinheiro(e.produtos)), h("td", {}, S.dinheiro(e.taxa)), h("td", {}, S.dinheiro(e.repasse)),
        h("td", {}, pode("financeiro", "repassar") ? h("button", { class: "btn btn-p btn-escuro", onclick: async () => {
          await S.acao(() => S.api("/api/repasses", { corpo: { empresa_id: e.id } }), "Repasse calculado."); desenhar(); } }, "Calcular repasse") : null)))))));
  blocos.push(h("div", { class: "cartao rolagem", style: { "margin-bottom": "1rem" } }, h("h2", {}, "Repasses"), rep.itens.length ? h("table", { class: "tabela" },
    h("thead", {}, h("tr", {}, ["Criado", "Empresa", "Pedidos", "Bruto", "Taxa", "Valor", "Estado", ""].map((t) => h("th", {}, t)))),
    h("tbody", {}, rep.itens.map((r) => h("tr", {}, h("td", {}, S.data(r.criado_em)), h("td", {}, r.empresa), h("td", {}, String(r.pedidos)), h("td", {}, S.dinheiro(r.bruto_centavos)),
      h("td", {}, S.dinheiro(r.taxa_centavos)), h("td", {}, h("b", {}, S.dinheiro(r.valor_centavos))), h("td", {}, r.status === "pago" ? S.selo("pago " + S.data(r.pago_em), "ok") : S.selo("a pagar", "aviso"), r.referencia ? h("div", { class: "mudo" }, r.referencia) : null),
      h("td", {}, r.status !== "pago" && pode("financeiro", "repassar") ? h("button", { class: "btn btn-p btn-verde", onclick: async () => {
        const ref = prompt("Comprovante/identificação da transferência feita ao parceiro:"); if (!ref) return;
        await S.acao(() => S.api(`/api/repasses/${r.id}/pago`, { corpo: { referencia: ref } }), "Repasse marcado como pago."); desenhar(); } }, "Marcar pago") : null)))))
    : h("p", { class: "mudo" }, "Nenhum repasse calculado.")));
  blocos.push(h("div", { class: "cartao" }, h("h2", {}, "Conciliação"), h("p", {}, conc.fecha ? S.selo("✓ Fecha: recebido = distribuído", "ok") : S.selo("✗ Há divergências", "urgente"),
    ` Recebido ${S.dinheiro(conc.recebido_centavos)} · distribuído (taxa + repasse + entrega) ${S.dinheiro(conc.distribuido_centavos)}`),
    conc.divergencias.map((d) => h("div", { class: "estado-int" }, h("span", {}, d.numero ? `Pedido #${d.numero}` : "Repasse"), h("span", {}, d.problema))), h("p", { class: "mudo" }, conc.aviso)));
  S.limpar(alvo, blocos);
}

// ------------------------------------------------------------------ doações e instituições
async function doarOferta(o) {
  const inst = (await S.api("/api/instituicoes?autorizadas=1")).itens.filter((i) => i.autorizada);
  if (!inst.length) return S.toast("Nenhuma instituição autorizada ainda. A equipe Sobrou+ precisa autorizar uma.", true);
  const max = o.status === "encerrada" ? o.expirada : o.disponivel;
  const f = formulario([["instituicao_id", "Instituição (autorizada)", "select", { opcoes: inst.map((i) => [i.id, `${i.nome}${i.cidade ? " — " + i.cidade : ""}`]) }],
    ["quantidade", `Quantidade (até ${max})`, "number", { valor: max, min: 1 }], ["nota", "Observação (horário de coleta, cuidados)", "text"]], "Oferecer doação", async (v) => {
    await S.acao(() => S.api("/api/doacoes", { corpo: { ...v, oferta_id: o.id } }), "Doação oferecida. A instituição precisa aceitar."); folha.fechar(); desenhar(); });
  const folha = S.folha(h("div", {}, h("h2", {}, `Doar: ${o.nome}`), h("p", { class: "mudo" }, "A doação só conta no impacto depois de: aceite da instituição → coleta (com nome de quem retirou) → confirmação da destinação."), f));
}
async function doarPedido(p) {
  const inst = (await S.api("/api/instituicoes?autorizadas=1")).itens.filter((i) => i.autorizada);
  if (!inst.length) return S.toast("Nenhuma instituição autorizada ainda.", true);
  const f = formulario([["instituicao_id", "Instituição (autorizada)", "select", { opcoes: inst.map((i) => [i.id, i.nome]) }], ["nota", "Observação", "text"]], "Oferecer doação", async (v) => {
    await S.acao(() => S.api("/api/doacoes", { corpo: { ...v, pedido_id: p.id } }), "Doação oferecida."); folha.fechar(); desenhar(); });
  const folha = S.folha(h("div", {}, h("h2", {}, `Pedido #${p.numero} não retirado`), f));
}

async function telaDoacoes(alvo) {
  const r = await S.api("/api/doacoes" + (ehInst() ? "" : comEmpresa()));
  const passo = (d) => {
    const b = [];
    const ir = async (acao, dados, msg) => { await S.acao(() => S.api(`/api/doacoes/${d.id}/${acao}`, { corpo: dados || {} }), msg); desenhar(); };
    if (ehInst() && d.status === "proposta") { b.push(h("button", { class: "btn btn-p btn-verde", onclick: () => ir("aceitar", {}, "Doação aceita.") }, "Aceitar"));
      b.push(h("button", { class: "btn btn-p btn-linha", onclick: () => { const m = prompt("Motivo da recusa:"); if (m !== null) ir("recusar", { motivo: m }, "Doação recusada."); } }, "Recusar")); }
    if (d.status === "aceita") b.push(h("button", { class: "btn btn-p btn-escuro", onclick: () => { const n = prompt("Nome de quem retirou a doação:"); if (n) ir("coletar", { responsavel: n }, "Coleta registrada."); } }, "Registrar coleta"));
    if (ehInst() && d.status === "coletada") b.push(h("button", { class: "btn btn-p btn-verde", onclick: () => { const n = prompt("Quantas pessoas foram beneficiadas?"); if (n) ir("confirmar", { pessoas_beneficiadas: parseInt(n, 10) }, "Destinação confirmada."); } }, "Confirmar destinação"));
    if (!ehInst() && ["proposta", "aceita"].includes(d.status) && pode("doacoes", "propor")) b.push(h("button", { class: "btn btn-p btn-linha", onclick: () => { const m = prompt("Motivo do cancelamento:"); if (m !== null) ir("cancelar", { motivo: m }, "Doação cancelada."); } }, "Cancelar"));
    return b;
  };
  const etapa = (rot, quem, quando, extra) => h("div", { class: "mudo" }, quando ? `✓ ${rot}: ${S.data(quando)}${extra ? " · " + extra : ""}` : `○ ${rot}`);
  S.limpar(alvo, h("h1", {}, "Doações"), r.itens.length ? h("div", { class: "grade" }, r.itens.map((d) => h("div", { class: "cartao" },
    h("div", { class: "linha" }, h("b", {}, d.descricao || "Doação"), h("span", { style: { "text-align": "right" } }, S.selo(d.status_nome, { proposta: "aviso", aceita: "oferta", coletada: "oferta", destinada: "ok", recusada: "urgente", cancelada: "urgente" }[d.status]))),
    h("div", { class: "mudo" }, `${d.empresa} → ${d.instituicao} · ${d.quantidade} un. · ${S.kg(d.peso_kg)}`),
    etapa("Proposta", d.proposta_por, d.proposta_em), etapa("Aceite", d.aceita_por, d.aceita_em), etapa("Coleta", d.coleta_por, d.coleta_em, d.coleta_responsavel),
    etapa("Destinação", d.destinada_por, d.destinada_em, d.pessoas_beneficiadas ? `${d.pessoas_beneficiadas} pessoas` : ""), d.nota ? h("div", { class: "mudo" }, d.nota) : null,
    h("div", { class: "linha", style: { "margin-top": ".5rem" } }, passo(d))))) : h("p", { class: "mudo" }, ehInst() ? "Nenhuma doação oferecida ainda." : "Nenhuma doação. Ofertas encerradas com sobra e pedidos não retirados podem ser doados."));
}

async function telaInstituicoes(alvo) {
  const r = await S.api("/api/instituicoes");
  const plataforma = pode("instituicoes", "autorizar");
  S.limpar(alvo, h("div", { class: "barra-acoes" }, h("h1", {}, "Instituições"), plataforma ? h("button", { class: "btn btn-cta", onclick: () => editarInst(null) }, "+ Nova instituição") : null),
    !plataforma ? h("p", { class: "mudo" }, "Só aparecem as instituições autorizadas pela equipe Sobrou+.") : null,
    h("div", { class: "grade" }, r.itens.map((i) => h("div", { class: "cartao" }, h("b", {}, i.nome), h("div", { class: "mudo" }, `${i.responsavel || ""}${i.cidade ? " · " + i.cidade : ""}${i.pessoas_atendidas ? " · " + i.pessoas_atendidas + " pessoas/mês" : ""}`),
      i.autorizada ? S.selo("autorizada", "ok") : S.selo("aguardando autorização", "aviso"),
      plataforma ? h("div", { class: "linha", style: { "margin-top": ".5rem" } },
        h("button", { class: "btn btn-p " + (i.autorizada ? "btn-linha" : "btn-verde"), onclick: async () => { await S.acao(() => S.api(`/api/instituicoes/${i.id}/autorizar`, { corpo: { autorizada: !i.autorizada } }), "Atualizado."); desenhar(); } }, i.autorizada ? "Suspender" : "Autorizar"),
        h("button", { class: "btn btn-p btn-linha", onclick: () => editarInst(i) }, "Editar"),
        h("button", { class: "btn btn-p btn-linha", onclick: () => novoUsuario("instituicao", i.id) }, "Criar acesso")) : null))));
}
function editarInst(i) {
  const v = i || {};
  const f = formulario([["nome", "Nome", "text", { valor: v.nome, obrigatorio: true }], ["documento", "CNPJ", "text", { valor: v.documento }], ["responsavel", "Responsável", "text", { valor: v.responsavel, obrigatorio: true }],
    ["telefone", "Telefone", "text", { valor: v.telefone }], ["endereco", "Endereço", "text", { valor: v.endereco }], ["cidade", "Cidade", "text", { valor: v.cidade }],
    ["pessoas_atendidas", "Pessoas atendidas/mês", "number", { valor: v.pessoas_atendidas }]], "Salvar", async (val) => {
    await S.acao(() => S.api(i ? "/api/instituicoes/" + i.id : "/api/instituicoes", { method: i ? "PUT" : "POST", corpo: val }), "Instituição salva."); folha.fechar(); desenhar(); });
  const folha = S.folha(h("div", {}, h("h2", {}, i ? "Editar instituição" : "Nova instituição"), f));
}

async function telaImpacto(alvo) {
  const i = await S.api("/api/impacto" + (ehInst() ? "" : comEmpresa()));
  S.limpar(alvo, h("h1", {}, "Impacto"), h("p", { class: "mudo" }, "Só conta o que foi confirmado: pedido concluído (retirado ou entregue) e doação com destinação confirmada pela instituição."),
    h("div", { class: "kpis" }, kpi("Desperdício evitado", S.kg(i.kg_desperdicio_evitado), "verde"), kpi("Vendido (kg)", S.kg(i.kg_vendidos), "verde"), kpi("Unidades vendidas", String(i.unidades_vendidas)),
      kpi("Pedidos concluídos", String(i.pedidos)), kpi("Economia dos clientes", S.dinheiro(i.economia_clientes_centavos), "laranja"), kpi("Receita recuperada", S.dinheiro(i.receita_parceiros_centavos), "laranja"),
      kpi("Doado (kg)", S.kg(i.kg_doados), "verde"), kpi("Doações confirmadas", String(i.doacoes)), kpi("Instituições atendidas", String(i.instituicoes_atendidas)),
      kpi("Pessoas beneficiadas", String(i.pessoas_beneficiadas), "verde"), kpi("Ofertas recuperadas", String(i.ofertas_recuperadas))),
    h("div", { class: "cartao" }, h("h3", {}, "Mapa do impacto"), h("p", { class: "mudo" }, "BLOQUEADO POR DEPENDÊNCIA: precisa de um provedor de mapas. Os números acima já são reais (do banco).")));
}

// ------------------------------------------------------------------ gestão
async function telaEmpresas(alvo) {
  const r = await S.api("/api/empresas");
  P.empresas = r.itens;
  S.limpar(alvo, h("div", { class: "barra-acoes" }, h("h1", {}, "Empresas parceiras"), h("button", { class: "btn btn-cta", onclick: novaEmpresa }, "+ Nova empresa")),
    h("div", { class: "cartao rolagem" }, h("table", { class: "tabela" }, h("thead", {}, h("tr", {}, ["Empresa", "Tipo", "Unidades", "Ofertas no ar", "Taxa", "Estado", ""].map((t) => h("th", {}, t)))),
      h("tbody", {}, r.itens.map((e) => h("tr", {}, h("td", {}, h("b", {}, e.nome), h("div", { class: "mudo" }, e.email || "")), h("td", {}, e.tipo), h("td", {}, String(e.unidades)), h("td", {}, String(e.ofertas_ativas)),
        h("td", {}, e.taxa_percentual !== null ? e.taxa_percentual + "%" : "padrão"),
        h("td", {}, e.aprovada ? S.selo("aprovada", "ok") : S.selo("em análise", "aviso"), " ", e.ativa ? null : S.selo("bloqueada", "urgente")),
        h("td", {}, h("div", { class: "linha", style: { "flex-wrap": "nowrap" } },
          h("button", { class: "btn btn-p " + (e.aprovada ? "btn-linha" : "btn-verde"), onclick: async () => { await S.acao(() => S.api(`/api/empresas/${e.id}/aprovar`, { corpo: { aprovada: !e.aprovada } }), "Atualizado."); desenhar(); } }, e.aprovada ? "Voltar p/ análise" : "Aprovar"),
          h("button", { class: "btn btn-p btn-linha", onclick: async () => { await S.acao(() => S.api(`/api/empresas/${e.id}/aprovar`, { corpo: { aprovada: !!e.aprovada, ativa: !e.ativa } }), "Atualizado."); desenhar(); } }, e.ativa ? "Bloquear" : "Desbloquear"),
          h("button", { class: "btn btn-p btn-linha", onclick: async () => { const t = prompt("Taxa Sobrou+ desta empresa (%), vazio = padrão:", e.taxa_percentual ?? ""); if (t === null) return;
            await S.acao(() => S.api(`/api/empresas/${e.id}`, { method: "PUT", corpo: { taxa_percentual: t } }), "Taxa salva."); desenhar(); } }, "Taxa"),
          h("button", { class: "btn btn-p btn-linha", onclick: () => novoUsuario("admin_empresa", null, e.id) }, "Criar acesso")))))))));
}
function novaEmpresa() {
  const f = formulario([["nome", "Nome", "text", { obrigatorio: true }], ["tipo", "Tipo", "select", { opcoes: [["restaurante", "Restaurante"], ["lanchonete", "Lanchonete"], ["padaria", "Padaria"], ["mercado", "Mercado"],
    ["supermercado", "Supermercado"], ["hortifruti", "Hortifrúti"], ["cafe", "Café"], ["confeitaria", "Confeitaria"], ["outra", "Outra"]] }], ["documento", "CNPJ"], ["telefone", "Telefone"], ["email", "E-mail"],
    ["taxa_percentual", "Taxa Sobrou+ (%) — vazio = padrão"]], "Criar empresa (já aprovada)", async (v) => {
    await S.acao(() => S.api("/api/empresas", { corpo: v }), "Empresa criada."); folha.fechar(); P.empresas = (await S.api("/api/empresas")).itens; montar(); });
  const folha = S.folha(h("div", {}, h("h2", {}, "Nova empresa parceira"), f));
}

const PAPEIS_CRIAVEIS = () => P.eu.plataforma
  ? [["admin_empresa", "Administrador da empresa"], ["operador_empresa", "Operador da empresa"], ["financeiro", "Financeiro"], ["logistica", "Logística"], ["entregador", "Entregador"],
    ["operador_sobrou", "Operador Sobrou+"], ["admin_sobrou", "Administrador Sobrou+"], ["instituicao", "Instituição"]]
  : [["operador_empresa", "Operador da empresa"], ["admin_empresa", "Administrador da empresa"], ["financeiro", "Financeiro"], ["logistica", "Logística"], ["entregador", "Entregador próprio"]];
async function novoUsuario(papel, instituicaoId, empresaId) {
  const insts = P.eu.plataforma ? (await S.api("/api/instituicoes")).itens : [];
  const f = formulario([["nome", "Nome", "text", { obrigatorio: true }], ["email", "E-mail (login)", "email", { obrigatorio: true }], ["telefone", "Telefone"],
    ["papel", "Perfil", "select", { opcoes: PAPEIS_CRIAVEIS(), valor: papel }],
    ...(P.eu.plataforma ? [["empresa_id", "Empresa (vazio = equipe Sobrou+ / rede)", "select", { opcoes: [["", "—"], ...P.empresas.map((e) => [e.id, e.nome])], valor: empresaId || P.empresa }],
      ["instituicao_id", "Instituição (só p/ perfil Instituição)", "select", { opcoes: [["", "—"], ...insts.map((i) => [i.id, i.nome])], valor: instituicaoId || "" }]] : []),
    ["veiculo", "Veículo (entregador)"]], "Criar acesso", async (v) => {
    await S.acao(() => S.api("/api/usuarios", { corpo: v }), "Acesso criado. Senha inicial padrão, com troca obrigatória no primeiro acesso."); folha.fechar(); desenhar(); });
  const folha = S.folha(h("div", {}, h("h2", {}, "Novo acesso"), f));
}

async function telaUsuarios(alvo) {
  const r = await S.api("/api/usuarios" + comEmpresa());
  S.limpar(alvo, h("div", { class: "barra-acoes" }, h("h1", {}, "Usuários e acessos"), pode("usuarios", "editar") ? h("button", { class: "btn btn-cta", onclick: () => novoUsuario("operador_empresa") }, "+ Novo acesso") : null),
    h("div", { class: "cartao rolagem" }, h("table", { class: "tabela" }, h("thead", {}, h("tr", {}, ["Nome", "E-mail", "Perfil", "Último acesso", "Estado", ""].map((t) => h("th", {}, t)))),
      h("tbody", {}, r.itens.map((u) => h("tr", {}, h("td", {}, u.nome), h("td", {}, u.email), h("td", {}, u.papel_nome), h("td", {}, S.data(u.ultimo_acesso)),
        h("td", {}, u.ativo ? S.selo("ativo", "ok") : S.selo("desativado", "urgente"), u.trocar_senha ? S.selo("1º acesso pendente", "aviso") : null),
        h("td", {}, pode("usuarios", "editar") && u.id !== P.eu.usuario.id ? h("div", { class: "linha", style: { "flex-wrap": "nowrap" } },
          h("button", { class: "btn btn-p btn-linha", onclick: async () => { await S.acao(() => S.api(`/api/usuarios/${u.id}/ativo`, { corpo: { ativo: !u.ativo } }), "Atualizado."); desenhar(); } }, u.ativo ? "Desativar" : "Ativar"),
          h("button", { class: "btn btn-p btn-linha", onclick: async () => { if (!confirm("Voltar a senha para a inicial padrão? A pessoa troca no próximo acesso.")) return;
            await S.acao(() => S.api(`/api/usuarios/${u.id}/redefinir`, { corpo: {} }), "Senha redefinida."); } }, "Redefinir senha")) : null)))))));
}

async function telaAuditoria(alvo) {
  const r = await S.api("/api/auditoria" + comEmpresa());
  S.limpar(alvo, h("h1", {}, "Auditoria"), h("p", { class: "mudo" }, "Registro de preço, estoque, pedidos, cancelamentos, ofertas, repasses, doações, permissões, usuários e configurações."),
    h("div", { class: "cartao rolagem" }, h("table", { class: "tabela" }, h("thead", {}, h("tr", {}, ["Quando", "Quem", "Ação", "Detalhe"].map((t) => h("th", {}, t)))),
      h("tbody", {}, r.itens.map((a) => h("tr", {}, h("td", {}, S.data(a.quando)), h("td", {}, a.usuario || "rotina automática"), h("td", {}, a.acao), h("td", { class: "mudo" }, a.detalhe || "")))))));
}

async function telaAparencia(alvo) {
  const blocos = [h("h1", {}, "Aparência e configurações")];
  const temaAtual = P.eu.tema;
  const escolher = async (t) => {
    if (P.eu.plataforma) await S.acao(() => S.api("/api/config-plataforma", { method: "PUT", corpo: { tema: t } }), "Tema salvo.");
    else await S.acao(() => S.api("/api/empresas/" + P.eu.usuario.empresa_id, { method: "PUT", corpo: { config: { tema: t } } }), "Tema salvo.");
    S.tema(t); P.eu.tema = t; desenhar();
  };
  blocos.push(h("div", { class: "cartao", style: { "margin-bottom": "1rem" } }, h("h2", {}, "Tema"), h("div", { class: "linha" },
    [["claro", "Claro"], ["medio", "Médio"], ["escuro", "Escuro"]].map(([t, n]) => h("button", { class: "btn " + (temaAtual === t ? "btn-escuro" : "btn-linha"), onclick: () => escolher(t) }, n)))));
  if (P.eu.plataforma && pode("sistema", "ver")) {
    const c = await S.api("/api/config-plataforma");
    blocos.push(h("div", { class: "cartao" }, h("h2", {}, "Plataforma"), formulario([["nome_exibicao", "Nome exibido", "text", { valor: c.nome_exibicao }], ["taxa_padrao", "Taxa Sobrou+ padrão (%)", "text", { valor: c.taxa_padrao }],
      ["minutos_reserva", "Minutos de reserva para pagar", "number", { valor: c.minutos_reserva }], ["tolerancia_retirada_min", "Tolerância após a janela de retirada (min)", "number", { valor: c.tolerancia_retirada_min }]],
    "Salvar", async (v) => { await S.acao(() => S.api("/api/config-plataforma", { method: "PUT", corpo: v }), "Configurações salvas."); })));
  } else if (P.eu.empresa) {
    const e = P.eu.empresa; const c = e.config;
    blocos.push(h("div", { class: "cartao" }, h("h2", {}, "Empresa"), formulario([["nome", "Nome da empresa", "text", { valor: e.nome }], ["nome_exibicao", "Nome no topo do painel", "text", { valor: c.nome_exibicao }],
      ["telefone", "Telefone", "text", { valor: e.telefone }], ["email", "E-mail", "text", { valor: e.email }],
      ["aceita_retirada", "Aceita retirada", "checkbox", { valor: !!c.aceita_retirada }], ["aceita_entrega", "Faz entrega", "checkbox", { valor: !!c.aceita_entrega }],
      ["taxa_entrega", "Taxa de entrega (R$)", "text", { valor: S.reais(c.taxa_entrega_centavos) }], ["raio_entrega_km", "Raio de entrega (km)", "text", { valor: c.raio_entrega_km }]],
    "Salvar", async (v) => { const r = await S.acao(() => S.api("/api/empresas/" + e.id, { method: "PUT", corpo: { nome: v.nome, telefone: v.telefone, email: v.email,
      config: { nome_exibicao: v.nome_exibicao, aceita_retirada: v.aceita_retirada, aceita_entrega: v.aceita_entrega, taxa_entrega_centavos: v.taxa_entrega || "0", raio_entrega_km: v.raio_entrega_km } } }), "Salvo.");
      P.eu.empresa = r; montar(); }),
    h("p", { class: "mudo" }, `Taxa Sobrou+ sobre os produtos: ${e.taxa_efetiva}% (definida pela equipe Sobrou+).`)));
  }
  S.limpar(alvo, blocos);
}

async function telaSistema(alvo) {
  const s = await S.api("/api/sistema");
  S.limpar(alvo, h("h1", {}, "Sistema e integrações"), h("div", { class: "kpis" }, kpi("Versão", s.versao), kpi("Empresas", String(s.empresas)), kpi("Em análise", String(s.aguardando_aprovacao), s.aguardando_aprovacao ? "laranja" : ""),
    kpi("Clientes", String(s.clientes)), kpi("Entregadores online", String(s.entregadores_online)), kpi("Instituições pendentes", String(s.instituicoes_pendentes))),
    h("div", { class: "cartao", style: { "margin-bottom": "1rem" } }, h("h2", {}, "Integrações (regra de verdade)"), s.integracoes.map((i) => h("div", { class: "estado-int" },
      h("div", {}, h("b", {}, i.nome), h("div", { class: "mudo" }, i.detalhe)), h("span", {}, S.selo(i.estado, i.estado.startsWith("IMPLEMENTADO E") ? "ok" : i.estado.startsWith("BLOQUEADO") ? "urgente" : "tecnico"))))),
    h("div", { class: "cartao rolagem" }, h("h2", {}, "Erros recentes"), s.erros.length ? h("table", { class: "tabela" }, h("tbody", {}, s.erros.map((e) => h("tr", {}, h("td", {}, S.data(e.quando)), h("td", {}, `${e.metodo} ${e.rota}`), h("td", {}, e.tipo), h("td", { class: "mudo" }, e.mensagem)))))
      : h("p", { class: "mudo" }, "Nenhum erro registrado.")));
}

function telaConta(alvo) {
  S.limpar(alvo, h("h1", {}, "Minha conta"), h("div", { class: "cartao", style: { "max-width": "520px" } }, h("p", {}, `${P.eu.usuario.nome} · ${P.eu.usuario.email} · ${P.eu.usuario.papel_nome}`),
    h("h3", {}, "Trocar senha"), formulario([["atual", "Senha atual", "password", { obrigatorio: true }], ["nova", "Nova senha (8+ caracteres, letras e números)", "password", { obrigatorio: true }]], "Salvar nova senha",
      async (v) => { await S.acao(() => S.api("/api/senha", { corpo: v }), "Senha trocada."); desenhar(); })));
}

async function telaIntegracoes(alvo) {
  const r = await S.api("/api/integracoes");
  const cartao = (nome, titulo, explicacao, campos, extra) => {
    const c = r[nome];
    const f = formulario(campos.map(([k, rot, tipo = "text", ex = {}]) => [k, rot, tipo, { valor: c[k] ?? ex.padrao ?? "", placeholder: ex.placeholder }]), "Salvar",
      async (v) => { await S.acao(() => S.api("/api/integracoes/" + nome, { method: "PUT", corpo: v }), "Integração salva."); desenhar(); });
    const resultado = h("div", { class: "mudo", style: { "margin-top": ".5rem" } });
    return h("div", { class: "cartao", style: { "margin-bottom": "1rem" } },
      h("div", { class: "linha" }, h("h2", { style: { margin: 0 } }, titulo), h("span", { style: { "text-align": "right" } }, c.configurado && c.ligado !== false ? S.selo("LIGADO", "ok") : S.selo("PRONTO PARA ATIVAR", "aviso"))),
      h("div", { class: "mudo", style: { margin: ".4rem 0" } }, explicacao), f,
      h("div", { class: "linha", style: { "margin-top": ".6rem" } }, h("button", { class: "btn btn-linha btn-p", onclick: async () => {
        S.limpar(resultado, "Testando…");
        try { const t = await S.api(`/api/integracoes/${nome}/testar`, { corpo: extra ? { telefone: prompt("Celular para receber a mensagem de teste (com DDD) — ou deixe vazio só para conferir a conexão:") || "" } : {} });
          S.limpar(resultado, S.selo(t.ok ? "OK" : "FALHOU", t.ok ? "ok" : "urgente"), " ", t.mensagem); } catch (e) { S.limpar(resultado, e.message); } } }, "Testar conexão")), resultado);
  };
  S.limpar(alvo, h("h1", {}, "Integrações"),
    h("p", { class: "mudo" }, "Tudo já está programado. Para ativar, basta colocar aqui as credenciais das contas e marcar “Ligado”. Os campos de chave nunca mostram o valor guardado (aparecem como ••••)."),
    cartao("mercadopago", "Pagamento — Pix e cartão (Mercado Pago)",
      h("div", {}, "1) Crie/entre na conta Mercado Pago → Seu negócio → Configurações → Credenciais. 2) Copie o Access Token (comece pelo de TESTE: “TEST-…”). ",
        "3) Em Webhooks, cadastre o endereço abaixo, evento “Pagamentos”, e copie a assinatura secreta. 4) Cole aqui e ligue.",
        h("div", { class: "copia", style: { "margin-top": ".4rem" } }, r.url_webhook)),
      [["ligado", "Ligado", "checkbox"], ["access_token", "Access Token", "password", { placeholder: "TEST-… ou APP_USR-…" }], ["webhook_secret", "Assinatura secreta do webhook", "password"],
        ["url_publica", "Endereço público do site (opcional)", "text", { placeholder: "https://…" }], ["permitir_teste", "Manter também o pagamento de teste", "checkbox"]]),
    cartao("whatsapp", "WhatsApp — avisos de pedido (API oficial da Meta)",
      "1) Meta for Developers → criar app “Business” → produto WhatsApp. 2) Copie o Phone Number ID e gere um token permanente (usuário do sistema). 3) Para falar com o cliente a qualquer hora, aprove um modelo de mensagem com 1 variável no corpo e escreva o nome dele aqui. Sem modelo, só funciona até 24 h depois do cliente mandar mensagem.",
      [["ligado", "Ligado", "checkbox"], ["token", "Token de acesso", "password"], ["phone_number_id", "Phone Number ID"], ["template", "Nome do modelo aprovado (opcional)"],
        ["idioma", "Idioma do modelo", "text", { padrao: "pt_BR" }], ["api_versao", "Versão da API", "text", { padrao: "v21.0" }]], true),
    cartao("mapas", "Mapa e rotas pelas ruas (OpenStreetMap)",
      "Já vem ligado com os serviços gratuitos do OpenStreetMap (OSRM para rotas, Nominatim para endereços). Para muito movimento, troque pelos endereços de um servidor próprio ou provedor pago.",
      [["ligado", "Ligado", "checkbox"], ["rotas_url", "Servidor de rotas (OSRM)", "text", { placeholder: "https://router.project-osrm.org" }],
        ["enderecos_url", "Servidor de endereços (Nominatim)", "text", { placeholder: "https://nominatim.openstreetmap.org" }]]),
    cartao("email", "E-mail — código de “Esqueci minha senha” e avisos",
      "Use qualquer e-mail com SMTP (ex.: Gmail com “senha de app”, Outlook, Zoho, Brevo grátis). O teste manda uma mensagem para o seu próprio e-mail. Sem e-mail ligado, quem esquecer a senha pede um novo link de acesso a quem o cadastrou.",
      [["ligado", "Ligado", "checkbox"], ["servidor", "Servidor SMTP", "text", { placeholder: "smtp.gmail.com" }], ["porta", "Porta", "text", { padrao: "587" }],
        ["usuario", "Usuário"], ["senha", "Senha (ou senha de app)", "password"], ["remetente", "Remetente", "text", { placeholder: "Sobrou+ <nao-responda@seudominio>" }]]),
    h("div", { class: "cartao" }, h("h2", {}, "Mensagens de WhatsApp"), h("p", {}, Object.entries(r.mensagens.contagem).map(([k, n]) => `${k}: ${n}`).join(" · ") || "Nenhuma ainda."),
      r.mensagens.ultimas.map((m) => h("div", { class: "estado-int" }, h("span", {}, `${m.telefone} — ${m.texto}`), S.selo(m.status, m.status === "enviada" ? "ok" : m.status === "falhou" ? "urgente" : "aviso")))));
}

const FUNCOES = { integracoes: telaIntegracoes, inicio: telaInicio, pedidos: telaPedidos, retirada: telaRetirada, ofertas: telaOfertas, unidades: telaUnidades, dispatch: telaDispatch, entregadores: telaEntregadores,
  financeiro: telaFinanceiro, doacoes: telaDoacoes, instituicoes: telaInstituicoes, impacto: telaImpacto, empresas: telaEmpresas, usuarios: telaUsuarios, auditoria: telaAuditoria,
  aparencia: telaAparencia, sistema: telaSistema, conta: telaConta };
