/* Sobrou+ — painel (empresas parceiras, equipe Sobrou+, instituições). Cada tela aparece só para quem tem permissão. */
"use strict";
const h = S.h;
const P = { cfg: {}, eu: null, empresa: "", empresas: [], recursos: [], tela: "inicio", som: false, dispatchAssinatura: null };
const recursoOn = (key) => !!P.eu?.plataforma || !P.recursos.length || !!P.recursos.find((r) => r.chave === key)?.habilitado;
function tocarAlertaDispatch() { if (!P.som) return; try { const C=window.AudioContext||window.webkitAudioContext; const a=new C(); const o=a.createOscillator(); const g=a.createGain(); o.frequency.value=720; g.gain.value=.12; o.connect(g); g.connect(a.destination); o.start(); o.stop(a.currentTime+.35); } catch(e) {} }
const pode = (r, a) => !!(P.eu && (P.eu.permissoes[r] || []).includes(a));
const ehInst = () => P.eu && P.eu.usuario.papel === "instituicao";
const eid = () => (P.eu.plataforma ? P.empresa : P.eu.usuario.empresa_id) || "";
const comEmpresa = (q = {}) => S.qs({ ...q, empresa_id: P.eu.plataforma ? P.empresa : undefined });

const TELAS = [
  ["Operação"],
  ["inicio", "Visão geral", () => true],
  ["pedidos", "Pedidos", () => pode("pedidos", "ver") && recursoOn("pedidos")],
  ["retirada", "Retirada (código/QR)", () => pode("retirada", "validar") && recursoOn("retirada")],
  ["ofertas", "Ofertas e estoque", () => pode("ofertas", "ver") && recursoOn("ofertas")],
  ["unidades", "Unidades", () => pode("unidades", "ver") && recursoOn("unidades")],
  ["Logística"],
  ["dispatch", "Dispatch", () => pode("dispatch", "ver") && recursoOn("entrega")],
  ["entregadores", "Entregadores", () => pode("entregadores", "ver") && recursoOn("entrega")],
  ["Dinheiro e impacto"],
  ["financeiro", "Financeiro e repasses", () => pode("financeiro", "ver") && recursoOn("financeiro")],
  ["doacoes", "Doações", () => recursoOn("doacoes") && (pode("doacoes", "ver") || ehInst())],
  ["instituicoes", "Instituições", () => pode("instituicoes", "ver") && recursoOn("doacoes")],
  ["impacto", "Impacto", () => pode("impacto", "ver")],
  ["Gestão"],
  ["marketing", "Análise e marketing", () => !!P.eu.plataforma && pode("sistema", "ver")],
  ["empresas", "Empresas parceiras", () => pode("empresas", "aprovar")],
  ["recursos", "Recursos para empresas", () => !!P.eu.plataforma && pode("sistema", "ver")],
  ["usuarios", "Usuários e acessos", () => pode("usuarios", "ver") && recursoOn("usuarios")],
  ["auditoria", "Auditoria", () => pode("auditoria", "ver")],
  ["aparencia", "Aparência e configurações", () => pode("config", "editar") || pode("sistema", "ver")],
  ["integracoes", "Integrações (ativar)", () => pode("sistema", "ver")],
  ["sistema", "Sistema e erros", () => pode("sistema", "ver")],
  ["seguranca", "Segurança RMD", () => !!P.eu?.eh_dono],
  ["manutencao", "Manutenção e atualizações", () => !!P.eu?.eh_dono],
  ["conta", "Minha conta", () => true],
];

async function iniciar() {
  P.som = localStorage.getItem("sobrou_dispatch_som") === "1";
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
  if (P.eu.plataforma || P.eu.usuario.empresa_id) P.recursos = (await S.api("/api/recursos")).itens || [];
  if (P.eu.plataforma && pode("empresas", "ver")) P.empresas = (await S.api("/api/empresas")).itens;
  P.tela = (hash && TELAS.some((t) => t[0] === hash && t[2] && t[2]())) ? hash : "inicio";
  montar();
  setInterval(atualizarSino, 20000);
  setInterval(async () => {
    if (P.tela !== "dispatch" || !P.eu) return;
    try {
      const r = await S.api("/api/dispatch" + comEmpresa());
      const sig = JSON.stringify(r.entregas.map((x) => [x.id, x.status]));
      if (P.dispatchAssinatura !== null && sig !== P.dispatchAssinatura) await desenhar();
    } catch (e) { /* próxima atualização */ }
  }, 12000);
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

async function telaObrigatoria2FA() {
  const raiz = document.getElementById("raiz");
  let config;
  try { config = await S.api("/api/seguranca/2fa/iniciar", { corpo: {} }); }
  catch (e) { return S.limpar(raiz, h("div", { class: "login" }, h("div", { class: "cartao" }, h("h2", {}, "Ative a verificação em duas etapas"), h("p", {}, e.message)))); }
  const codigo = h("input", { type: "text", inputMode: "numeric", autocomplete: "one-time-code", maxLength: 6, placeholder: "000000" });
  S.limpar(raiz, h("div", { class: "login" }, h("div", { class: "cartao" },
    S.marca(P.cfg, "Proteja sua conta", "claro"),
    h("h2", {}, "Ative a verificação em duas etapas"),
    h("p", {}, "Administradores precisam confirmar o acesso com um aplicativo autenticador."),
    h("ol", {}, h("li", {}, "Abra Google Authenticator, Microsoft Authenticator ou outro aplicativo TOTP."),
      h("li", {}, "Escolha adicionar uma conta e leia o QR Code abaixo. Se preferir, use a chave manual."),
      h("li", {}, h("code", {}, config.segredo)),
      h("li", {}, "Depois de adicionar a conta, digite aqui o código de 6 números que o aplicativo estiver mostrando agora.")),
    h("div", { class: "cartao", style: { "text-align": "center", "margin": "1rem 0", "background": "var(--fundo)" } },
      h("div", { class: "mudo" }, "QR Code para configurar o autenticador"),
      (typeof qrcode === "function" && config.endereco) ? S.qr(config.endereco, 7) : null,
      h("p", { class: "mudo" }, "O QR Code configura a conta. Ele não é o código de 6 números usado para confirmar.")),
    h("label", {}, "Código de 6 números do aplicativo"), codigo,
    h("button", { class: "btn btn-cta btn-bloco", onclick: async () => {
      await S.acao(() => S.api("/api/seguranca/2fa/confirmar", { corpo: { codigo: codigo.value.trim() } }), "Verificação ativada.");
      location.reload();
    } }, "Confirmar e proteger a conta"),
    h("p", { class: "mudo" }, "Guarde o código de configuração em local seguro. Ele não será mostrado novamente."))));
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

function avaliacaoClienteNoPedido(p) {
  if (p.status !== "concluido" || !pode("pedidos", "operar")) return null;
  if (p.avaliacao_cliente) return h("div", { class: "cartao" }, h("b", {}, "Sua avaliação do cliente: "),
    h("span", { class: "estrelas" }, "★".repeat(p.avaliacao_cliente.nota) + "☆".repeat(5 - p.avaliacao_cliente.nota)),
    p.avaliacao_cliente.comentario ? h("p", {}, p.avaliacao_cliente.comentario) : null);
  let nota = 0;
  const botoes = [1, 2, 3, 4, 5].map((n) => h("button", { type: "button", class: "estrela-botao", "aria-label": `${n} estrelas`,
    onclick: () => { nota = n; botoes.forEach((b, i) => b.classList.toggle("on", i < n)); } }, "★"));
  const comentario = h("textarea", { rows: 2, maxlength: 500, placeholder: "Atendimento, respeito à retirada ou entrega (opcional)" });
  return h("div", { class: "cartao" }, h("h3", {}, "Avalie este cliente"),
    h("p", { class: "mudo" }, "Avalie somente o que ocorreu neste pedido concluído. A nota não altera benefícios nem pontos do cliente."),
    h("div", { class: "estrelas-escolha" }, botoes), comentario,
    h("button", { class: "btn btn-verde", style: { "margin-top": ".5rem" }, onclick: async () => {
      if (!nota) return S.toast("Escolha de 1 a 5 estrelas.", true);
      await S.acao(() => S.api(`/api/pedidos/${p.id}/avaliar-cliente`, { corpo: { nota, comentario: comentario.value.trim() } }), "Avaliação do cliente registrada.");
      location.hash = "#avaliacoes"; desenhar();
    } }, "Enviar avaliação"));
}

async function detalhePedido(id) {
  const p = await S.api("/api/pedidos/" + id);
  S.folha(h("div", {}, h("h2", {}, `Pedido #${p.numero}`), h("p", {}, `${p.cliente || ""} ${p.cliente_telefone ? "· " + p.cliente_telefone : ""}`),
    p.endereco_entrega ? h("p", {}, "Entregar em: " + p.endereco_entrega) : null,
    p.itens.map((i) => h("div", {}, `${i.quantidade}× ${i.nome} — ${S.dinheiro(i.preco_centavos * i.quantidade)}`)),
    h("p", {}, `Produtos ${S.dinheiro(p.subtotal_centavos)} · Taxa Sobrou+ ${S.dinheiro(p.taxa_centavos)} (${p.taxa_percentual}%) · Repasse ${S.dinheiro(p.repasse_centavos)}`),
    h("h3", {}, "Histórico"), p.historico.map((x) => h("div", { class: "mudo" }, `${S.data(x.quando)} — ${x.para_status.replace(/_/g, " ")}${x.usuario ? " · " + x.usuario : ""}${x.nota ? " · " + x.nota : ""}`)),
    avaliacaoClienteNoPedido(p)));
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
  const assinatura = JSON.stringify(r.entregas.map((x) => [x.id, x.status]));
  if (P.dispatchAssinatura !== null && P.dispatchAssinatura !== assinatura &&
      r.entregas.some((x) => x.status === "falhou" && !(P.falhasVistas || new Set()).has(x.id))) tocarAlertaDispatch();
  P.falhasVistas = new Set(r.entregas.filter((x) => x.status === "falhou").map((x) => x.id));
  P.dispatchAssinatura = assinatura;
  S.limpar(alvo, h("div", { class: "barra-acoes" }, h("h1", {}, "Dispatch"),
    h("button", { class: "btn btn-linha btn-p", onclick: () => { P.som=true; localStorage.setItem("sobrou_dispatch_som","1"); tocarAlertaDispatch(); S.toast("Alertas sonoros ativados neste aparelho."); } }, "Ativar som"),
    h("button", { class: "btn btn-linha btn-p", onclick: desenhar }, "Atualizar")),
    h("div", { class: "kpis" }, kpi("Sem entregador", String(r.sem_entregador), r.sem_entregador ? "coral" : ""), kpi("Entregadores online", String(online.length), "verde"),
      kpi("Em rota", String(r.entregas.filter((e) => ["aceita", "em_coleta", "em_rota"].includes(e.status)).length), "laranja")),
    h("div", { class: "mapa alto", id: "mapa-dispatch", style: { "margin-bottom": "1rem" } }),
    h("p", { class: "mudo" }, "Ordem de prioridade: janela/validade mais curta primeiro. Entre entregadores disponíveis, primeiro o menor trajeto pelas ruas até a loja (GPS dos últimos 10 min); capacidade e vínculo com a loja definem elegibilidade. Recusa ou 60 s sem resposta → próximo."),
    h("div", { class: "cartao rolagem" }, h("table", { class: "tabela" }, h("thead", {}, h("tr", {}, ["Pedido", "Loja", "Destino", "Prazo", "Entregador", "Estado", ""].map((t) => h("th", {}, t)))),
      h("tbody", {}, r.entregas.map((e) => h("tr", {}, h("td", {}, `#${e.numero}`), h("td", {}, e.loja), h("td", {}, e.endereco_entrega || "—", e.distancia_km !== null ? h("div", { class: "mudo" }, `${e.distancia_km} km`) : null),
        h("td", {}, e.janela_fim ? S.hora(e.janela_fim) : "—"), h("td", {}, e.entregador || "—", e.eta_min ? h("div", { class: "mudo" }, `~${e.eta_min} min`) : null),
        h("td", {}, S.selo(e.status.replace(/_/g, " "), { aguardando: "urgente", ofertada: "aviso", entregue: "ok", falhou: "urgente" }[e.status] || "oferta")),
        h("td", {}, e.status === "falhou" && pode("dispatch", "operar") ? h("button", { class: "btn btn-cta btn-p", onclick: async () => { await S.acao(() => S.api("/api/dispatch/" + e.id + "/buscar", { corpo: {} }), "Nova busca iniciada."); desenhar(); } }, "Buscar novamente") : e.status === "aguardando" ? S.selo("Busca automática ativa", "aviso") : e.status === "ofertada" ? S.selo("Aguardando aceite", "aviso") : null)))))));
  mapaDispatch(r);
}

function mapaDispatch(r) {
  const el = document.getElementById("mapa-dispatch"); if (!el) return;
  const m = S.mapa(el, null, 13); const pontos = [];
  r.entregas.filter((e) => !["entregue", "falhou"].includes(e.status)).forEach((e) => {
    if (e.loja_lat !== null) { S.marcar(m, e.loja_lat, e.loja_lng, "#0A563A", "L", `#${e.numero} — coleta: ${e.loja}`); pontos.push([e.loja_lat, e.loja_lng]); }
    if (e.entrega_lat !== null) { S.marcar(m, e.entrega_lat, e.entrega_lng, e.status === "aguardando" ? "#E74A3B" : "#F57A20", "C", `#${e.numero} — entrega: ${e.endereco_entrega || ""}`); pontos.push([e.entrega_lat, e.entrega_lng]); }
    if (e.loja_lat !== null && e.entrega_lat !== null) S.desenharRota(m, [e.loja_lat, e.loja_lng], [e.entrega_lat, e.entrega_lng], "#F57A20");
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

async function telaManutencao(alvo) {
  if (!P.eu?.eh_dono) throw new Error("Área exclusiva do desenvolvedor RMD.");
  const r = await S.api("/api/manutencao/painel");
  const b = r.backup || {};
  const integ = r.integridade || {};
  const banco = integ.banco === "ok";
  const arquivos = integ.arquivos || {};
  const alterados = arquivos.alterados_desde_ultima_verificacao || [];
  const faltantes = arquivos.faltantes || [];
  const status = (ok, sim = "OK", nao = "ATENÇÃO") => S.selo(ok ? sim : nao, ok ? "ok" : "urgente");
  S.limpar(alvo,
    h("h1", {}, "Manutenção e atualizações"),
    h("p", { class: "mudo" }, "Área exclusiva do Desenvolvedor RMD. As programações e testes devem ser feitos no ambiente de desenvolvimento, separado do sistema oficial."),
    h("div", { class: "kpis" },
      kpi("Ambiente atual", r.ambiente === "producao" ? "PRODUÇÃO" : "DESENVOLVIMENTO", r.ambiente === "producao" ? "verde" : "laranja"),
      kpi("Porta", String(r.porta)),
      kpi("Banco", status(banco)),
      kpi("Backup", status(!!b.ok && b.restore_testado, "TESTADO", "ATENÇÃO"))),
    h("div", { class: "cartao" },
      h("h2", {}, "Como funciona"),
      h("p", {}, "1. O desenvolvedor trabalha em um ambiente separado de desenvolvimento."),
      h("p", {}, "2. As alterações são testadas lá, sem mexer diretamente no sistema oficial."),
      h("p", {}, "3. Antes de uma atualização, pode ser feita uma cópia de segurança do sistema oficial."),
      h("p", {}, "4. A integridade do banco e dos arquivos principais pode ser conferida antes da publicação.")),
    h("div", { class: "cartao" },
      h("h2", {}, "Ambientes"),
      h("div", { class: "estado-int" }, h("span", {}, "Sistema oficial"), h("span", {}, "Produção · dados\\ · porta 8095")),
      h("div", { class: "estado-int" }, h("span", {}, "Área de desenvolvimento"), h("span", {}, "data_desenvolvimento\\ · porta 8096")),
      h("p", { class: "mudo" }, "O ambiente de desenvolvimento é separado para permitir testes sem alterar diretamente os dados do sistema oficial.")),
    h("div", { class: "cartao" },
      h("h2", {}, "Manutenção"),
      h("div", { class: "linha" },
        h("button", { class: "btn btn-cta", onclick: async () => { const x = await S.acao(() => S.api("/api/manutencao/backup", { method: "POST", corpo: {} }), "Backup criado e testado."); if (x) desenhar(); } }, "Fazer backup e testar"),
        h("button", { class: "btn btn-linha btn-p", onclick: async () => { await S.acao(() => S.api("/api/manutencao/integridade", { method: "POST", corpo: {} }), "Integridade verificada."); desenhar(); } }, "Verificar integridade")),
      h("p", { class: "mudo" }, "Essas ações não publicam código nem alteram regras do sistema; elas cuidam da segurança operacional antes das modificações.")),
    h("div", { class: "cartao" },
      h("h2", {}, "Último backup"),
      h("p", {}, r.ultimo_backup || "Nenhum backup encontrado."),
      h("p", { class: "mudo" }, "Banco de dados: ", String(r.dados))),
    (alterados.length || faltantes.length) ? h("div", { class: "cartao" }, h("h2", {}, "Atenção"),
      alterados.length ? h("p", {}, "Arquivos principais alterados: ", alterados.join(", ")) : null,
      faltantes.length ? h("p", {}, "Arquivos principais ausentes: ", faltantes.join(", ")) : null) : null
  );
}

async function telaSeguranca(alvo) {
  if (!P.eu?.eh_dono) throw new Error("Área exclusiva do proprietário RMD.");
  const s = await S.api("/api/seguranca/painel");
  const nomes = {
    sessao_horas: "Sessão máxima", csrf_json: "Proteção de origem/CSRF", isolamento_empresas: "Isolamento entre empresas",
    auditoria: "Auditoria de segurança", limpeza_sessoes_expiradas: "Limpeza automática de sessões",
    rate_limit_login: "Limite de tentativas", upload_imagens_validado: "Validação de uploads",
    lgpd: "Proteção de dados/LGPD", backup_automatico: "Backup automático", totp: "2FA",
    financeiro_producao: "Financeiro em produção"
  };
  const protecoes = Object.entries(s.protecao || {}).map(([k, v]) => {
    const adiado = String(v).startsWith("adiado");
    const valor = typeof v === "number" ? v + " h" : S.selo(adiado ? "ADIADO" : "ATIVO", adiado ? "aviso" : "ok");
    return h("div", { class: "estado-int" }, h("span", {}, nomes[k] || k), h("span", {}, valor));
  });
  const falhas = s.contas_com_falhas || [];
  const eventos = s.eventos_seguranca || [];
  const linhasFalhas = falhas.map((x) => h("tr", {},
    h("td", {}, x.nome + " · " + x.email),
    h("td", {}, x.papel),
    h("td", {}, String(x.tentativas_falhas || 0)),
    h("td", {}, x.bloqueado_ate ? S.data(x.bloqueado_ate) : "—")
  ));
  const blocoFalhas = falhas.length ? h("div", { class: "cartao rolagem" },
    h("h2", {}, "Contas com tentativas/bloqueios"),
    h("table", { class: "tabela" },
      h("thead", {}, h("tr", {}, ["Usuário", "Perfil", "Tentativas", "Bloqueado até"].map((x) => h("th", {}, x)))),
      h("tbody", {}, linhasFalhas)
    )
  ) : null;

  const linhasSessoes = (s.sessoes_ativas || []).map((x) => h("tr", {},
    h("td", {}, x.usuario + " · " + x.email),
    h("td", {}, x.papel),
    h("td", {}, x.empresa_id || "Plataforma"),
    h("td", {}, x.ip || "—"),
    h("td", {}, S.data(x.criada_em)),
    h("td", {}, S.data(x.expira_em))
  ));
  const blocoSessoes = h("div", { class: "cartao rolagem" },
    h("h2", {}, "Sessões ativas"),
    linhasSessoes.length ? h("table", { class: "tabela" },
      h("thead", {}, h("tr", {}, ["Usuário", "Perfil", "Empresa", "IP", "Criada", "Expira"].map((x) => h("th", {}, x)))),
      h("tbody", {}, linhasSessoes)
    ) : h("p", { class: "mudo" }, "Nenhuma sessão ativa.")
  );

  const linhasEventos = eventos.map((x) => h("tr", {},
    h("td", {}, S.data(x.quando)),
    h("td", {}, x.usuario || "rotina"),
    h("td", {}, x.acao),
    h("td", { class: "mudo" }, x.detalhe || "—"),
    h("td", {}, x.ip || "—")
  ));
  const blocoEventos = h("div", { class: "cartao rolagem" },
    h("h2", {}, "Eventos de segurança"),
    linhasEventos.length ? h("table", { class: "tabela" },
      h("thead", {}, h("tr", {}, ["Quando", "Usuário", "Ação", "Detalhe", "IP"].map((x) => h("th", {}, x)))),
      h("tbody", {}, linhasEventos)
    ) : h("p", { class: "mudo" }, "Nenhum evento de segurança registrado.")
  );
  S.limpar(alvo,
    h("h1", {}, "Segurança RMD"),
    h("p", { class: "mudo" }, "Área exclusiva do proprietário do sistema RMD. Os dados abaixo não são exibidos aos administradores das empresas."),
    h("div", { class: "kpis" },
      kpi("Sessões ativas", String(s.total_sessoes_ativas)),
      kpi("Contas com tentativas", String(falhas.length), falhas.length ? "coral" : "verde"),
      kpi("Backup", s.backup_ok ? "OK" : "ATENÇÃO", s.backup_ok ? "verde" : "coral"),
      kpi("Último backup", s.ultimo_backup ? S.data(s.ultimo_backup) : "Nunca", s.ultimo_backup ? "" : "coral")),
    h("div", { class: "cartao" }, h("h2", {}, "Proteções ativas"), protecoes),
    blocoFalhas, blocoSessoes, blocoEventos
  );
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
    if (nome === "mercadopago") return h("div", { class: "cartao", style: { "margin-bottom": "1rem" } },
      h("div", { class: "linha" }, h("h2", { style: { margin: 0 } }, titulo), S.selo(c.configurado ? "CONFIGURADO" : "DESLIGADO", c.configurado ? "ok" : "aviso")),
      h("p", { class: "mudo" }, "Access Token, chave pública e segredo do webhook são lidos somente do ambiente do servidor. Nunca são gravados no banco nem enviados ao navegador."),
      h("p", {}, "Provedor: ", c.provedor || "não definido", " · Ambiente: ", c.ambiente || "sandbox"),
      h("p", {}, "Pix: ", c.configurado ? "disponível" : "aguardando configuração", " · Cartão e boleto: Checkout Pro (meios habilitados pela conta) · Parcelas máximas: ", String(c.parcelas_maximas || "—")),
      h("p", { class: "mudo" }, "Webhook HTTPS: ", c.webhook_url || "não configurado"),
      h("p", { class: "mudo" }, "Public Key: ", c.public_key || "não configurada", " · Access Token: ", c.access_token_configurado ? "configurado" : "ausente", " · Secret webhook: ", c.webhook_secret_configurado ? "configurado" : "ausente"),
      h("p", {}, "Configure as variáveis de ambiente documentadas em PAGAMENTOS.md e reinicie o serviço. O ambiente de teste exige credenciais TEST-; produção rejeita credenciais TEST-."));
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
    h("p", { class: "mudo" }, "WhatsApp, mapas e e-mail podem ser configurados aqui. Credenciais de pagamento ficam exclusivamente nas variáveis protegidas do servidor."),
    cartao("mercadopago", "Pagamento online (Mercado Pago)",
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

async function telaRecursos(alvo) {
  if (!P.eu.plataforma || !pode("sistema", "ver")) throw new Error("Acesso restrito à equipe Sobrou+.");
  const padrao = await S.api("/api/recursos");
  const itens = padrao.itens || [];
  const formularioPadrao = formulario(itens.map((x) => ["r_" + x.chave, x.nome, "checkbox", { valor: x.habilitado }]),
    "Salvar padrão da plataforma", async (v) => {
      const recursos = Object.fromEntries(itens.map((x) => [x.chave, !!v["r_" + x.chave]]));
      const salvo = await S.acao(() => S.api("/api/recursos", { method: "PUT", corpo: { recursos } }), "Padrões salvos.");
      P.recursos = salvo.itens;
      desenhar();
    });
  const blocos = [h("h1", {}, "Recursos para empresas"),
    h("p", { class: "mudo" }, "Defina o padrão para novas liberações e, se necessário, ajuste uma empresa. As mudanças são registradas na auditoria e bloqueadas também pela API. Como o checkout online é o único meio ativo hoje, desativar pagamentos também bloqueia a criação de pedidos.")];
  blocos.push(h("div", { class: "cartao" }, h("h2", {}, "Padrão da plataforma"), formularioPadrao));
  if (P.empresa) {
    const porEmpresa = await S.api("/api/empresas/" + P.empresa + "/recursos");
    const formularioEmpresa = formulario(porEmpresa.itens.map((x) => ["r_" + x.chave, x.nome, "select", {
      valor: x.sobrescrito === null ? "herdar" : x.sobrescrito ? "liberado" : "bloqueado",
      opcoes: [["herdar", "Usar padrão (" + (x.padrao ? "liberado" : "bloqueado") + ")"],
        ["liberado", "Liberado nesta empresa"], ["bloqueado", "Bloqueado nesta empresa"]]
    }]), "Salvar recursos da empresa", async (v) => {
      const recursos = Object.fromEntries(porEmpresa.itens.map((x) => {
        const valor = v["r_" + x.chave];
        return [x.chave, valor === "herdar" ? null : valor === "liberado"];
      }));
      await S.acao(() => S.api("/api/empresas/" + P.empresa + "/recursos", { method: "PUT", corpo: { recursos } }), "Acesso da empresa atualizado.");
      desenhar();
    });
    blocos.push(h("div", { class: "cartao" }, h("h2", {}, "Empresa: " + porEmpresa.empresa), formularioEmpresa));
  } else {
    blocos.push(h("div", { class: "cartao" }, h("h2", {}, "Configuração individual"), h("p", {}, "Escolha uma empresa no seletor do cabeçalho para substituir o padrão ou voltar a herdar as opções globais.")));
  }
  S.limpar(alvo, blocos);
}

async function telaMarketing(alvo) {
  if (!P.eu.plataforma || !pode("sistema", "ver")) throw new Error("Acesso restrito.");
  const r = await S.api("/api/marketing" + comEmpresa({ dias: 30 }));
  const cabecalho = h("div", { class: "kpis" },
    kpi("Entradas no app", String(r.acessos_web)),
    kpi("Visitas a empresas", String(r.visitas)),
    kpi("Pedidos", String(r.pedidos), "verde"),
    kpi("Conversão", r.conversao_pct === null ? "—" : r.conversao_pct + "%", "laranja"));
  const maxDia = Math.max(1, ...r.serie.map((x) => x.visitantes));
  const grafico = h("div", { class: "cartao" }, h("h2", {}, "Acessos por dia"),
    r.serie.length ? h("div", { style: { display: "flex", "align-items": "end", overflow: "auto", height: "130px" } },
      r.serie.map((x) => h("div", { title: x.dia + " · " + x.visitantes + " visitantes · " + x.pedidos + " pedidos",
        style: { height: Math.max(4, x.visitantes / maxDia * 95) + "px", width: "18px", margin: "0 2px", background: "#1FA361", "border-radius": "4px 4px 0 0", "align-self": "end" } })))
      : h("p", { class: "mudo" }, "Sem acessos registrados."));
  const linhas = r.por_empresa.map((x) => h("tr", {},
    h("td", {}, x.empresa), h("td", {}, String(x.visitas || 0)),
    h("td", {}, String(x.interesse || 0)), h("td", {}, String(x.checkouts || 0)),
    h("td", {}, String(x.pedidos || 0)),
    h("td", {}, x.conversao_pct === null ? "—" : x.conversao_pct + "%"),
    h("td", {}, String(x.desistencia_checkout || 0))));
  const tabela = h("div", { class: "cartao rolagem" }, h("h2", {}, "Por empresa"),
    r.por_empresa.length ? h("table", { class: "tabela" },
      h("thead", {}, h("tr", {}, ["Empresa", "Visitas", "Ofertas", "Checkouts", "Pedidos", "Conversão", "Desistências"].map((x) => h("th", {}, x)))),
      h("tbody", {}, linhas))
      : h("p", { class: "mudo" }, "Nenhum evento neste período."));
  S.limpar(alvo, h("h1", {}, "Análise e marketing"),
    h("p", { class: "mudo" }, "Eventos reais dos últimos 30 dias; sem dados anteriores ou fictícios."),
    cabecalho, grafico, tabela,
    h("div", { class: "cartao" }, h("h2", {}, "Recomendações"),
      r.sugestoes.map((x) => h("p", {}, x)), h("p", { class: "mudo" }, r.nota)));
}

const FUNCOES = { marketing: telaMarketing, recursos: telaRecursos, integracoes: telaIntegracoes, inicio: telaInicio, pedidos: telaPedidos, retirada: telaRetirada, ofertas: telaOfertas, unidades: telaUnidades, dispatch: telaDispatch, entregadores: telaEntregadores,
  financeiro: telaFinanceiro, doacoes: telaDoacoes, instituicoes: telaInstituicoes, impacto: telaImpacto, empresas: telaEmpresas, usuarios: telaUsuarios, auditoria: telaAuditoria,
  aparencia: telaAparencia, sistema: telaSistema, seguranca: telaSeguranca, manutencao: telaManutencao, conta: telaConta };
