/* Sobrou+ — painel, parte 2: entrada do Desenvolvedor, links de acesso, modo teste, configurações, financeiro detalhado,
   gráficos, relatórios, avaliações, planos e backups. Carrega depois de painel.js e substitui algumas telas. */
"use strict";

// ------------------------------------------------------------------ menu
(function ajustarMenu() {
  const tira = (id) => { const i = TELAS.findIndex((t) => t[0] === id); if (i >= 0) TELAS.splice(i, 1); };
  ["aparencia", "conta"].forEach(tira);
  const depois = (id, item) => { const i = TELAS.findIndex((t) => t[0] === id); TELAS.splice(i + 1, 0, item); };
  const fin = TELAS.find((t) => t[0] === "financeiro"); fin[1] = "Financeiro";
  depois("financeiro", ["relatorios", "Relatórios (baixar)", () => pode("pedidos", "ver") || pode("financeiro", "ver")]);
  depois("pedidos", ["avaliacoes", "Avaliações", () => pode("pedidos", "ver")]);
  depois("empresas", ["planos", "Planos e mensalidades", () => pode("empresas", "aprovar")]);
  TELAS.push(["Desenvolvedor e conta"]);
  TELAS.push(["teste", "Modo teste (todas as telas)", () => P.eu.eh_dono || P.eu.usuario.papel === "admin_sobrou"]);
  TELAS.push(["config", "Configurações", () => true]);
  const i = TELAS.findIndex((t) => t[0] === "integracoes"); const it = TELAS.splice(i, 1)[0]; TELAS.push(it);
  const j = TELAS.findIndex((t) => t[0] === "sistema"); const st = TELAS.splice(j, 1)[0]; TELAS.push(st);
})();

// ------------------------------------------------------------------ entrada: Desenvolvedor só com senha
// Duas entradas SEPARADAS: /painel = empresa e equipe (e-mail + senha); /rmd = Desenvolvedor RMD (só a senha).
// A empresa nunca vê a entrada do Desenvolvedor.
const AREA_RMD = /\/rmd\/?$/.test(location.pathname);
telaLogin = function () {
  const modo = AREA_RMD ? "criador" : "equipe";
  const email = h("input", { type: "email", autocomplete: "email", required: true });
  const senha = h("input", { type: "password", autocomplete: "current-password", required: true });
  const codigo = h("input", { inputmode: "numeric", maxlength: 6, placeholder: "Código de 6 números" });
  const caixaCodigo = h("div", { class: "oculto" }, h("label", {}, "Código do aplicativo autenticador"), codigo);
  const entrar = async (e) => {
    e.preventDefault();
    const corpo = { senha: senha.value, codigo: codigo.value.trim() || undefined };
    if (modo === "equipe") corpo.email = email.value.trim();
    try { await S.api(modo === "criador" ? "/api/entrar-criador" : "/api/entrar", { corpo }); location.reload(); }
    catch (er) { if (er.dados && er.dados.precisa_codigo) { caixaCodigo.classList.remove("oculto"); codigo.focus(); } S.toast(er.message, true); }
  };
  S.limpar(document.getElementById("raiz"), h("div", { class: "login" }, h("div", { class: "cartao" },
    S.marca(P.cfg, "Painel Sobrou+", "claro"),
    h("h2", { style: { margin: ".6rem 0 .2rem" } }, AREA_RMD ? "Acesso do Desenvolvedor RMD" : "Entrar — empresa e equipe"),
    h("form", { onsubmit: entrar },
      AREA_RMD ? h("p", { class: "mudo" }, "Área restrita de administração do sistema.") : [h("label", {}, "E-mail"), email],
      h("label", {}, "Senha"), senha, caixaCodigo,
      h("button", { class: "btn btn-cta btn-bloco", style: { "margin-top": "1rem" } }, "Entrar")),
    AREA_RMD ? null : [
      h("p", { style: { "text-align": "center", margin: ".6rem 0 0" } }, h("a", { href: "#", onclick: (e) => { e.preventDefault(); S.esqueciSenha(email.value.trim()); } }, "Esqueci minha senha")),
      h("p", { class: "mudo", style: { "text-align": "center" } }, h("a", { href: "#cadastro", onclick: () => setTimeout(iniciar) }, "Quero ser parceiro Sobrou+"), " · ",
        h("a", { href: "#instituicao", onclick: () => setTimeout(iniciar) }, "Sou instituição social"), " · ", h("a", { href: S.u("/") }, "Ver ofertas"))])));
  (AREA_RMD ? senha : email).focus();
};

// aceite dos termos nos cadastros públicos
const caixaAceite = () => {
  const c = h("input", { type: "checkbox", style: { width: "auto" } });
  return { el: h("label", { style: { display: "flex", gap: ".5rem", "align-items": "flex-start", "font-weight": "500" } }, c,
    h("span", {}, "Li e aceito os ", h("a", { href: S.u("/termos"), target: "_blank" }, "Termos de Uso"), " e a ", h("a", { href: S.u("/privacidade"), target: "_blank" }, "Política de Privacidade"), ".")), ctl: c };
};
(function aceiteNosCadastros() {
  const orig1 = telaCadastroEmpresa, orig2 = telaCadastroInstituicao;
  const injetar = (rota) => {
    const form = document.querySelector("#raiz form"); if (!form) return;
    const a = caixaAceite(); form.insertBefore(a.el, form.querySelector("button[type=submit]"));
    form.addEventListener("submit", (e) => { if (!a.ctl.checked) { e.stopImmediatePropagation(); e.preventDefault(); S.toast("Marque o aceite dos Termos e da Privacidade.", true); } }, true);
    const fetchOrig = S.api;
    S.api = (caminho, opc = {}) => (caminho === rota && opc.corpo ? fetchOrig(caminho, { ...opc, corpo: { ...opc.corpo, aceite_termos: a.ctl.checked } }) : fetchOrig(caminho, opc));
  };
  telaCadastroEmpresa = function () { orig1(); injetar("/api/cadastro/empresa"); };
  telaCadastroInstituicao = function () { orig2(); injetar("/api/cadastro/instituicao"); };
})();

// faixas: senha padrão do Desenvolvedor e modo teste
const montarBase = montar;
montar = function () {
  montarBase();
  const conteudo = document.getElementById("conteudo");
  const faixa = S.faixaTeste(P.eu);
  if (faixa) conteudo.parentNode.insertBefore(faixa, conteudo);
  if (P.eu.senha_padrao) conteudo.parentNode.insertBefore(h("div", { class: "faixa-alerta", style: { margin: "1rem 1.4rem 0" } },
    h("b", {}, "Segurança: "), "sua senha ainda é a inicial padrão. Ela é fácil de adivinhar — troque em ",
    h("a", { href: "#config", onclick: () => setTimeout(() => irPara("config")) }, "Configurações"), " e, se quiser, ligue a verificação em 2 etapas."), conteudo);
};

// ------------------------------------------------------------------ links de acesso
novoUsuario = async function (papel, instituicaoId, empresaId) {
  const insts = P.eu.plataforma ? (await S.api("/api/instituicoes")).itens : [];
  const f = formulario([["nome", "Nome", "text", { obrigatorio: true }], ["email", "E-mail", "email", { obrigatorio: true }], ["telefone", "Celular com DDD (para mandar o link por WhatsApp)"],
    ["papel", "Perfil", "select", { opcoes: PAPEIS_CRIAVEIS(), valor: papel }],
    ...(P.eu.plataforma ? [["empresa_id", "Empresa (vazio = equipe Sobrou+ / rede)", "select", { opcoes: [["", "—"], ...P.empresas.map((e) => [e.id, e.nome])], valor: empresaId || P.empresa }],
      ["instituicao_id", "Instituição (só p/ perfil Instituição)", "select", { opcoes: [["", "—"], ...insts.map((i) => [i.id, i.nome])], valor: instituicaoId || "" }]] : []),
    ["veiculo", "Veículo (entregador)"]], "Cadastrar e gerar link de acesso", async (v) => {
    const r = await S.acao(() => S.api("/api/usuarios", { corpo: v }), "Cadastro feito.");
    folha.fechar(); desenhar(); S.mostrarConvite(r.convite); });
  const folha = S.folha(h("div", {}, h("h2", {}, "Novo acesso"), h("p", { class: "mudo" }, "Depois de cadastrar, o sistema gera o link de acesso para você mandar à pessoa. Ela cria a própria senha."), f));
};

novaEmpresa = async function () {
  const planos = (await S.api("/api/planos")).itens;
  const f = formulario([["nome", "Nome da empresa", "text", { obrigatorio: true }], ["tipo", "Tipo", "select", { opcoes: [["restaurante", "Restaurante"], ["lanchonete", "Lanchonete"], ["padaria", "Padaria"], ["mercado", "Mercado"],
    ["supermercado", "Supermercado"], ["hortifruti", "Hortifrúti"], ["cafe", "Café"], ["confeitaria", "Confeitaria"], ["outra", "Outra"]] }], ["documento", "CNPJ"], ["telefone", "Telefone da empresa"], ["email", "E-mail da empresa"],
    ["plano_id", "Plano", "select", { opcoes: [["", "— sem plano —"], ...planos.map((p) => [p.id, `${p.nome} — ${S.dinheiro(p.mensalidade_centavos)}/mês, taxa ${p.taxa_percentual}%`])] }],
    ["nome_responsavel", "Responsável (nome)", "text", { obrigatorio: true }], ["email_responsavel", "Responsável (e-mail)", "email", { obrigatorio: true }],
    ["telefone_responsavel", "Responsável (celular com DDD)"]], "Cadastrar empresa e gerar link de acesso", async (v) => {
    const r = await S.acao(() => S.api("/api/empresas", { corpo: v }), "Empresa cadastrada.");
    folha.fechar(); P.empresas = (await S.api("/api/empresas")).itens; montar(); if (r.convite) S.mostrarConvite(r.convite); });
  const folha = S.folha(h("div", {}, h("h2", {}, "Nova empresa parceira"), h("p", { class: "mudo" }, "A empresa já entra aprovada. O responsável recebe o link de acesso para criar a senha."), f));
  folha.el.style.maxWidth = "760px";
};

const telaUsuariosBase = telaUsuarios;
telaUsuarios = async function (alvo) {
  await telaUsuariosBase(alvo);
  if (!pode("usuarios", "editar")) return;
  const r = await S.api("/api/usuarios" + comEmpresa());
  alvo.querySelectorAll("tbody tr").forEach((tr, k) => {
    const u = r.itens[k]; if (!u || u.id === P.eu.usuario.id) return;
    const cel = tr.lastElementChild.querySelector(".linha") || tr.lastElementChild;
    cel.append(h("button", { class: "btn btn-p btn-escuro", onclick: async () => S.mostrarConvite(await S.acao(() => S.api(`/api/usuarios/${u.id}/convite`, { corpo: {} }))) }, "Link de acesso"));
  });
};

// ------------------------------------------------------------------ modo teste do Desenvolvedor
async function telaTeste(alvo) {
  const perfis = [["cliente", "Cliente (app do celular)", "Ofertas, compra, pagamento, PIN/QR, avaliação."], ["admin_empresa", "Empresa (administrador)", "Ofertas, pedidos, financeiro, configurações."],
    ["operador_empresa", "Balcão / caixa", "Pedidos e retirada por código ou QR."], ["entregador", "Entregador", "Online, corridas, mapa, coleta e entrega."],
    ["financeiro", "Financeiro da empresa", "Vendas, repasses, relatórios."], ["logistica", "Logística da empresa", "Dispatch e entregadores."], ["instituicao", "Instituição", "Aceitar e confirmar doações."]];
  S.limpar(alvo, h("h1", {}, "Modo teste do Desenvolvedor"),
    h("p", {}, "Abra qualquer tela do sistema como cada tipo de usuário, numa ", h("b", {}, "Loja Teste"), " com contas de teste — sem mexer nos dados dos clientes reais. Use para reproduzir um problema que o cliente relatar."),
    h("p", { class: "mudo" }, "Ao entrar num perfil aparece uma faixa amarela com o botão “Voltar ao painel RMD”."),
    h("div", { class: "grade" }, perfis.map(([id, nome, desc]) => h("div", { class: "cartao" }, h("h3", {}, nome), h("p", { class: "mudo" }, desc),
      h("button", { class: "btn btn-cta", onclick: async () => { const r = await S.acao(() => S.api("/api/criador/testar", { corpo: { perfil: id } })); location.href = S.u(r.caminho); } }, "Abrir como " + nome.split(" (")[0])))));
}

// ------------------------------------------------------------------ configurações
async function telaConfig(alvo) {
  const blocos = [h("h1", {}, "Configurações")];
  const temaAtual = P.eu.tema;
  const escolherTema = async (t) => {
    if (P.eu.plataforma) await S.acao(() => S.api("/api/config-plataforma", { method: "PUT", corpo: { tema: t } }), "Tema salvo.");
    else if (P.eu.empresa && pode("config", "editar")) await S.acao(() => S.api("/api/empresas/" + P.eu.usuario.empresa_id, { method: "PUT", corpo: { config: { tema: t } } }), "Tema salvo.");
    S.tema(t); P.eu.tema = t; desenhar();
  };
  blocos.push(h("div", { class: "cartao", style: { "margin-bottom": "1rem" } }, h("h2", {}, "Aparência"), h("div", { class: "linha" },
    [["claro", "Claro"], ["medio", "Médio"], ["escuro", "Escuro"]].map(([t, n]) => h("button", { class: "btn " + (temaAtual === t ? "btn-escuro" : "btn-linha"), onclick: () => escolherTema(t) }, n)))));
  if (P.eu.plataforma && pode("sistema", "ver")) {
    const c = await S.api("/api/config-plataforma");
    blocos.push(h("div", { class: "cartao", style: { "margin-bottom": "1rem" } }, h("h2", {}, "Plataforma Sobrou+"), formulario([
      ["nome_exibicao", "Nome exibido", "text", { valor: c.nome_exibicao }], ["taxa_padrao", "Taxa Sobrou+ padrão (%)", "text", { valor: c.taxa_padrao }],
      ["minutos_reserva", "Minutos de reserva para pagar", "number", { valor: c.minutos_reserva }], ["tolerancia_retirada_min", "Tolerância após a janela de retirada (min)", "number", { valor: c.tolerancia_retirada_min }],
      ["email_contato", "E-mail de atendimento (aparece para os clientes)", "email", { valor: c.email_contato }], ["whatsapp_suporte", "WhatsApp de suporte", "text", { valor: c.whatsapp_suporte }]],
    "Salvar", async (v) => { await S.acao(() => S.api("/api/config-plataforma", { method: "PUT", corpo: v }), "Configurações salvas."); }),
    h("p", { class: "mudo" }, "Pagamento, WhatsApp, e-mail e mapas: veja ", h("a", { href: "#integracoes", onclick: () => setTimeout(() => irPara("integracoes")) }, "Integrações"), ". Planos: ",
      h("a", { href: "#planos", onclick: () => setTimeout(() => irPara("planos")) }, "Planos e mensalidades"), ".")));
  }
  if (P.eu.empresa && pode("config", "editar")) {
    const e = P.eu.empresa; const c = e.config;
    blocos.push(h("div", { class: "cartao", style: { "margin-bottom": "1rem" } }, h("h2", {}, "Minha empresa"), formulario([
      ["nome", "Nome da empresa", "text", { valor: e.nome }], ["nome_exibicao", "Nome no topo do painel", "text", { valor: c.nome_exibicao }],
      ["telefone", "Telefone", "text", { valor: e.telefone }], ["email", "E-mail", "text", { valor: e.email }], ["whatsapp_loja", "WhatsApp da loja (para os clientes)", "text", { valor: c.whatsapp_loja }],
      ["aceita_retirada", "Aceita retirada no balcão", "checkbox", { valor: !!c.aceita_retirada }], ["aceita_entrega", "Faz entrega", "checkbox", { valor: !!c.aceita_entrega }],
      ["taxa_entrega", "Taxa de entrega (R$)", "text", { valor: S.reais(c.taxa_entrega_centavos) }], ["raio_entrega_km", "Raio de entrega (km, pelas ruas)", "text", { valor: c.raio_entrega_km }]],
    "Salvar", async (v) => { const r = await S.acao(() => S.api("/api/empresas/" + e.id, { method: "PUT", corpo: { nome: v.nome, telefone: v.telefone, email: v.email,
      config: { nome_exibicao: v.nome_exibicao, whatsapp_loja: v.whatsapp_loja, aceita_retirada: v.aceita_retirada, aceita_entrega: v.aceita_entrega, taxa_entrega_centavos: v.taxa_entrega || "0", raio_entrega_km: v.raio_entrega_km } } }), "Salvo.");
      P.eu.empresa = r; montar(); }),
    h("p", { class: "mudo" }, `Taxa Sobrou+ sobre os produtos: ${e.taxa_efetiva}%.`)));
    blocos.push(h("div", { class: "cartao", style: { "margin-bottom": "1rem" } }, h("h2", {}, "Dados para receber os repasses"),
      h("p", { class: "mudo" }, "É para esta conta que a equipe Sobrou+ transfere o valor das suas vendas. Toda alteração fica registrada na auditoria."),
      formulario([["pix_tipo", "Tipo da chave Pix", "select", { opcoes: [["", "—"], ["cnpj", "CNPJ"], ["cpf", "CPF"], ["email", "E-mail"], ["telefone", "Celular"], ["aleatoria", "Chave aleatória"]], valor: c.pix_tipo || "" }],
        ["pix_chave", "Chave Pix", "text", { valor: c.pix_chave }], ["titular", "Titular da conta", "text", { valor: c.titular }], ["banco", "Banco", "text", { valor: c.banco }]],
      "Salvar dados de repasse", async (v) => { const r = await S.acao(() => S.api("/api/empresas/" + e.id, { method: "PUT", corpo: { config: v } }), "Dados de repasse salvos."); P.eu.empresa = r; })));
  }
  // minha conta: senha, verificação em 2 etapas, aparelhos conectados, avisos no celular
  const senhaForm = formulario([["atual", "Senha atual", "password", { obrigatorio: true }], ["nova", "Nova senha (8+ caracteres, letras e números)", "password", { obrigatorio: true }]],
    "Trocar senha", async (v) => { await S.acao(() => S.api("/api/senha", { corpo: v }), "Senha trocada."); P.eu = await S.api("/api/eu"); montar(); });
  const caixa2fa = h("div");
  const desenhar2fa = () => {
    if (P.eu.tem_2fa) return S.limpar(caixa2fa, h("p", {}, S.selo("Ligada", "ok"), " Ao entrar, o sistema pede o código do aplicativo."),
      h("button", { class: "btn btn-linha btn-p", onclick: async () => { const s = prompt("Para desligar, digite sua senha:"); if (!s) return;
        await S.acao(() => S.api("/api/seguranca/2fa/desligar", { corpo: { senha: s } }), "Verificação em 2 etapas desligada."); P.eu.tem_2fa = false; desenhar2fa(); } }, "Desligar"));
    S.limpar(caixa2fa, h("p", { class: "mudo" }, "Mais proteção: além da senha, um código de 6 números do celular (Google Authenticator, Microsoft Authenticator ou similar)."),
      h("button", { class: "btn btn-escuro btn-p", onclick: async () => {
        const r = await S.acao(() => S.api("/api/seguranca/2fa/iniciar", { corpo: {} }));
        const cod = h("input", { inputmode: "numeric", maxlength: 6, placeholder: "Código de 6 números" });
        S.limpar(caixa2fa, h("p", {}, "1) No aplicativo autenticador, leia este QR Code (ou digite a chave). 2) Digite o código que aparecer."),
          h("div", { style: { background: "#fff", display: "inline-block", padding: "8px", "border-radius": "10px" } }, S.qr(r.endereco, 5)),
          h("div", { class: "copia" }, r.segredo), cod,
          h("button", { class: "btn btn-verde btn-p", style: { "margin-top": ".5rem" }, onclick: async () => {
            await S.acao(() => S.api("/api/seguranca/2fa/confirmar", { corpo: { codigo: cod.value.trim() } }), "Verificação em 2 etapas ligada."); P.eu.tem_2fa = true; desenhar2fa(); } }, "Confirmar"));
      } }, "Ligar verificação em 2 etapas"));
  };
  desenhar2fa();
  const sess = (await S.api("/api/seguranca/sessoes")).itens;
  blocos.push(h("div", { class: "colunas" },
    h("div", { class: "cartao" }, h("h2", {}, "Minha conta"), h("p", {}, `${P.eu.usuario.nome} · ${P.eu.usuario.email} · ${P.eu.usuario.papel_nome}`),
      P.eu.senha_padrao ? h("div", { class: "faixa-alerta" }, "Sua senha ainda é a inicial padrão. Troque por uma senha só sua.") : null, senhaForm),
    h("div", { class: "cartao" }, h("h2", {}, "Segurança"), h("h3", {}, "Verificação em 2 etapas"), caixa2fa,
      h("h3", { style: { "margin-top": "1rem" } }, `Aparelhos conectados (${sess.length})`),
      sess.slice(0, 6).map((x) => h("div", { class: "mudo" }, `${S.data(x.criada_em)} · IP ${x.ip || "?"}`)),
      h("button", { class: "btn btn-linha btn-p", style: { "margin-top": ".5rem" }, onclick: async () => { const r = await S.acao(() => S.api("/api/seguranca/sair-todos", { corpo: {} })); S.toast(`${r.encerradas} aparelho(s) desconectado(s).`); desenhar(); } }, "Sair de todos os outros aparelhos"),
      h("h3", { style: { "margin-top": "1rem" } }, "Avisos no celular"), S.botaoAvisos() || h("p", { class: "mudo" }, "Este navegador não aceita avisos com o app fechado."))));
  S.limpar(alvo, blocos);
}

// ------------------------------------------------------------------ financeiro detalhado
const PERIODOS = [["hoje", "Hoje", 0], ["7", "7 dias", 6], ["30", "30 dias", 29], ["mes", "Este mês", null], ["90", "90 dias", 89]];
function intervalo(sel) {
  const hoje = new Date(); const z = (n) => String(n).padStart(2, "0"); const d = (x) => `${x.getFullYear()}-${z(x.getMonth() + 1)}-${z(x.getDate())}`;
  if (sel.de) return { de: sel.de, ate: sel.ate || d(hoje) };
  if (sel.p === "mes") return { de: d(new Date(hoje.getFullYear(), hoje.getMonth(), 1)), ate: d(hoje) };
  const dias = (PERIODOS.find((p) => p[0] === sel.p) || PERIODOS[2])[2];
  return { de: d(new Date(hoje.getTime() - dias * 86400000)), ate: d(hoje) };
}
function seletorPeriodo(estado, aoMudar) {
  const de = h("input", { type: "date", value: estado.de || "" }), ate = h("input", { type: "date", value: estado.ate || "" });
  return h("div", { class: "periodos" }, PERIODOS.map(([id, nome]) => h("button", { class: "btn btn-linha btn-p" + (!estado.de && estado.p === id ? " ativo" : ""), onclick: () => aoMudar({ p: id }) }, nome)),
    h("span", { class: "mudo" }, "ou de"), de, h("span", { class: "mudo" }, "até"), ate, h("button", { class: "btn btn-escuro btn-p", onclick: () => de.value && aoMudar({ de: de.value, ate: ate.value }) }, "Ver"));
}
P.periodoFin = { p: "30" };
telaFinanceiro = async function (alvo) {
  const iv = intervalo(P.periodoFin);
  const q = { ...iv, teste: P.finTeste === undefined ? undefined : (P.finTeste ? 1 : 0) };
  const [f, rep, conc, fat] = await Promise.all([S.api("/api/financeiro/detalhado" + comEmpresa(q)), S.api("/api/repasses" + comEmpresa()),
    S.api("/api/conciliacao" + comEmpresa()), S.api("/api/faturas" + comEmpresa()).catch(() => ({ itens: [] }))]);
  const plat = f.visao === "plataforma";
  const D = S.dinheiro;
  const blocos = [h("div", { class: "barra-acoes" }, h("h1", {}, plat ? "Financeiro da plataforma" : "Financeiro da empresa"),
    h("a", { class: "btn btn-linha btn-p", href: S.u("/api/relatorios/pedidos.csv" + comEmpresa(iv)) }, "Baixar pedidos (Excel)"),
    pode("financeiro", "ver") ? h("a", { class: "btn btn-linha btn-p", href: S.u("/api/relatorios/repasses.csv" + comEmpresa(iv)) }, "Baixar repasses (Excel)") : null),
    seletorPeriodo(P.periodoFin, (n) => { P.periodoFin = n; desenhar(); })];
  if (f.aviso) blocos.push(h("div", { class: "selo aviso", style: { display: "block", padding: ".5rem .8rem", "border-radius": "10px", "margin-bottom": "1rem" } }, f.aviso));
  if (plat) blocos.push(h("label", { style: { display: "flex", gap: ".5rem", "align-items": "center", "font-weight": "500", "margin-bottom": "1rem" } },
    h("input", { type: "checkbox", style: { width: "auto" }, checked: f.incluindo_teste, onchange: (e) => { P.finTeste = e.target.checked; desenhar(); } }), "Incluir lojas de teste/demonstração"));
  if (plat) blocos.push(h("div", { class: "kpis" },
    kpi("Receita Sobrou+ (taxas + mensalidades)", D(f.receita_plataforma_centavos), "verde"), kpi("Taxas sobre vendas", D(f.taxa_centavos), "verde"),
    kpi("Mensalidades recebidas", D(f.mensalidades_pagas_centavos)), kpi("Mensalidades em aberto", D(f.mensalidades_abertas_centavos), f.mensalidades_abertas_centavos ? "coral" : ""),
    kpi("Vendas totais (GMV)", D(f.gmv_centavos)), kpi("Pedidos", String(f.pedidos)), kpi("Ticket médio", D(f.ticket_medio_centavos)),
    kpi("A repassar às lojas", D(f.a_repassar_centavos), f.a_repassar_centavos ? "laranja" : ""), kpi("Repassado no período", D(f.repassado_no_periodo_centavos)),
    kpi("Entregas (valor)", `${D(f.entrega_centavos)} · ${f.entregas}`), kpi("Estornos", `${f.estornos.n} · ${D(f.estornos.v)}`, f.estornos.n ? "coral" : ""),
    kpi("Cancelados / não retirados", `${f.cancelados} / ${f.nao_retirados}`)));
  else blocos.push(h("div", { class: "kpis" },
    kpi("Vendas (bruto)", D(f.vendas_produtos_centavos), "verde"), kpi("Você recebe (líquido)", D(f.repasse_centavos), "verde"), kpi(`Taxa Sobrou+ (${f.empresa.taxa_percentual}%)`, D(f.taxa_centavos)),
    kpi("A receber", D(f.a_repassar_centavos), f.a_repassar_centavos ? "laranja" : ""), kpi("Recebido no período", D(f.repassado_no_periodo_centavos)),
    kpi("Pedidos", String(f.pedidos)), kpi("Ticket médio", D(f.ticket_medio_centavos)), kpi("Retiradas / entregas", `${f.retiradas} / ${f.entregas}`),
    kpi("Cancelados / não retirados", `${f.cancelados} / ${f.nao_retirados}`), kpi("Economia dos seus clientes", D(f.economia_clientes_centavos)), kpi("Comida salva", S.kg(f.kg), "verde"),
    kpi("Plano", f.empresa.plano ? `${f.empresa.plano} · ${D(f.empresa.mensalidade_centavos)}/mês` : "sem plano")));
  // gráfico por dia
  const mapa = Object.fromEntries(f.por_dia.map((d) => [d.dia, d]));
  const serie = []; const d0 = new Date(iv.de + "T12:00:00"), d1 = new Date(iv.ate + "T12:00:00");
  for (let d = new Date(d0); d <= d1 && serie.length < 120; d = new Date(d.getTime() + 86400000)) {
    const k = d.toISOString().slice(0, 10); const x = mapa[k] || {};
    serie.push({ rotulo: `${k.slice(8, 10)}/${k.slice(5, 7)}`, barra: (x.vendas || 0) / 100, linha: plat ? (x.taxa || 0) / 100 : (x.repasse || 0) / 100 });
  }
  const fmt = (v) => "R$ " + Math.round(v).toLocaleString("pt-BR");
  blocos.push(h("div", { class: "cartao", style: { "margin-bottom": "1rem" } }, h("h2", {}, "Vendas por dia"),
    S.grafico(serie, { nomeBarra: "Vendas", nomeLinha: plat ? "Receita Sobrou+ (taxas)" : "Você recebe", fmtBarra: fmt, fmtLinha: fmt })));
  if (plat && f.empresas.length) blocos.push(h("div", { class: "cartao rolagem", style: { "margin-bottom": "1rem" } }, h("h2", {}, "Por empresa"),
    h("table", { class: "tabela" }, h("thead", {}, h("tr", {}, ["Empresa", "Plano", "Pedidos", "Vendas", "Taxa", "Repasse", "A repassar", "Mensalidade aberta", "Pix para repasse", ""].map((t) => h("th", {}, t)))),
      h("tbody", {}, f.empresas.map((e) => h("tr", {}, h("td", {}, e.nome, e.demonstracao ? h("div", {}, S.selo("teste", "aviso")) : null), h("td", {}, e.plano || "—"), h("td", {}, String(e.pedidos)),
        h("td", {}, D(e.vendas)), h("td", {}, D(e.taxa)), h("td", {}, D(e.repasse)), h("td", {}, h("b", {}, D(e.a_repassar))), h("td", {}, D(e.mensalidade_aberta)),
        h("td", { class: "mudo" }, e.pix_chave ? `${e.pix_tipo || ""} ${e.pix_chave}${e.titular ? " · " + e.titular : ""}` : S.selo("sem chave", "urgente")),
        h("td", {}, pode("financeiro", "repassar") && e.a_repassar > 0 ? h("button", { class: "btn btn-p btn-escuro", onclick: async () => {
          await S.acao(() => S.api("/api/repasses", { corpo: { empresa_id: e.id } }), "Repasse calculado."); desenhar(); } }, "Calcular repasse") : null)))))));
  if (f.produtos.length) blocos.push(h("div", { class: "cartao", style: { "margin-bottom": "1rem" } }, h("h2", {}, "Mais vendidos"),
    f.produtos.map((p) => h("div", { class: "estado-int" }, h("span", {}, p.nome), h("span", {}, `${p.unidades} un. · ${D(p.vendas)}`)))));
  blocos.push(h("div", { class: "cartao rolagem", style: { "margin-bottom": "1rem" } }, h("h2", {}, "Repasses"), rep.itens.length ? h("table", { class: "tabela" },
    h("thead", {}, h("tr", {}, ["Criado", "Empresa", "Pedidos", "Bruto", "Taxa", "Valor", "Estado", ""].map((t) => h("th", {}, t)))),
    h("tbody", {}, rep.itens.map((r) => h("tr", {}, h("td", {}, S.data(r.criado_em)), h("td", {}, r.empresa), h("td", {}, String(r.pedidos)), h("td", {}, D(r.bruto_centavos)),
      h("td", {}, D(r.taxa_centavos)), h("td", {}, h("b", {}, D(r.valor_centavos))), h("td", {}, r.status === "pago" ? S.selo("pago " + S.data(r.pago_em), "ok") : S.selo("a pagar", "aviso"), r.referencia ? h("div", { class: "mudo" }, r.referencia) : null),
      h("td", {}, r.status !== "pago" && pode("financeiro", "repassar") ? h("button", { class: "btn btn-p btn-verde", onclick: async () => {
        const ref = prompt("Comprovante/identificação da transferência feita ao parceiro:"); if (!ref) return;
        await S.acao(() => S.api(`/api/repasses/${r.id}/pago`, { corpo: { referencia: ref } }), "Repasse marcado como pago."); desenhar(); } }, "Marcar pago") : null)))))
    : h("p", { class: "mudo" }, "Nenhum repasse calculado.")));
  blocos.push(h("div", { class: "cartao rolagem", style: { "margin-bottom": "1rem" } }, h("h2", {}, "Mensalidades do plano"), fat.itens.length ? h("table", { class: "tabela" },
    h("thead", {}, h("tr", {}, ["Mês", "Empresa", "Plano", "Valor", "Vence", "Estado", ""].map((t) => h("th", {}, t)))),
    h("tbody", {}, fat.itens.map((x) => h("tr", {}, h("td", {}, x.competencia), h("td", {}, x.empresa), h("td", {}, x.plano || "—"), h("td", {}, D(x.valor_centavos)), h("td", {}, x.vence_em || "—"),
      h("td", {}, x.status === "paga" ? S.selo("paga", "ok") : S.selo("em aberto", "aviso")),
      h("td", {}, x.status !== "paga" && pode("financeiro", "repassar") ? h("button", { class: "btn btn-p btn-verde", onclick: async () => {
        const ref = prompt("Comprovante do pagamento da mensalidade:"); if (!ref) return; await S.acao(() => S.api(`/api/faturas/${x.id}/paga`, { corpo: { referencia: ref } }), "Mensalidade paga."); desenhar(); } }, "Marcar paga") : null)))))
    : h("p", { class: "mudo" }, "Nenhuma mensalidade gerada (geradas no dia 1º de cada mês para empresas com plano pago).")));
  blocos.push(h("div", { class: "cartao" }, h("h2", {}, "Conciliação"), h("p", {}, conc.fecha ? S.selo("✓ Fecha: recebido = distribuído", "ok") : S.selo("✗ Há divergências", "urgente"),
    ` Recebido ${D(conc.recebido_centavos)} · distribuído (taxa + repasse + entrega) ${D(conc.distribuido_centavos)}`),
    conc.divergencias.map((d) => h("div", { class: "estado-int" }, h("span", {}, d.numero ? `Pedido #${d.numero}` : "Repasse"), h("span", {}, d.problema))), h("p", { class: "mudo" }, conc.aviso)));
  S.limpar(alvo, blocos);
};

// ------------------------------------------------------------------ impacto com gráfico
const telaImpactoBase = telaImpacto;
telaImpacto = async function (alvo) {
  await telaImpactoBase(alvo);
  if (ehInst()) return;
  const g = await S.api("/api/graficos" + comEmpresa({ dias: 30 })).catch(() => null);
  if (!g) return;
  const serie = g.serie.map((d) => ({ rotulo: `${d.dia.slice(8, 10)}/${d.dia.slice(5, 7)}`, barra: d.pedidos, linha: d.kg }));
  const caixa = h("div", { class: "cartao", style: { "margin-bottom": "1rem" } }, h("h2", {}, "Últimos 30 dias"),
    S.grafico(serie, { nomeBarra: "Pedidos concluídos", nomeLinha: "Kg de comida salva", fmtLinha: (v) => v.toLocaleString("pt-BR", { maximumFractionDigits: 1 }) + " kg" }),
    g.categorias.length ? h("div", { style: { "margin-top": ".8rem" } }, g.categorias.map((c) => h("div", { class: "estado-int" }, h("span", {}, S.CATEGORIAS[c.categoria] || c.categoria), h("span", {}, `${c.unidades} un. · ${S.kg(c.kg)}`)))) : null);
  alvo.insertBefore(caixa, alvo.children[2] || null);
};

// visão geral com gráfico
const telaInicioBase = telaInicio;
telaInicio = async function (alvo) {
  await telaInicioBase(alvo);
  if (ehInst() || !pode("impacto", "ver")) return;
  const g = await S.api("/api/graficos" + comEmpresa({ dias: 14 })).catch(() => null);
  if (!g) return;
  const serie = g.serie.map((d) => ({ rotulo: `${d.dia.slice(8, 10)}/${d.dia.slice(5, 7)}`, barra: d.vendas_centavos / 100, linha: d.kg }));
  alvo.append(h("div", { class: "cartao", style: { "margin-top": "1rem" } }, h("h2", {}, "Vendas e impacto — 14 dias"),
    S.grafico(serie, { nomeBarra: "Vendas (R$)", nomeLinha: "Kg recuperados", fmtBarra: (v) => "R$ " + Math.round(v).toLocaleString("pt-BR"), fmtLinha: (v) => v.toLocaleString("pt-BR", { maximumFractionDigits: 1 }) + " kg" })));
};

// ------------------------------------------------------------------ relatórios
async function telaRelatorios(alvo) {
  const iv = intervalo(P.periodoFin);
  const tipos = [["pedidos", "Pedidos", "Todos os pedidos com valores, taxa, repasse e peso."], ["ofertas", "Ofertas e estoque", "Quantidade, vendido, sobra e doado por oferta."],
    ["doacoes", "Doações", "Cada doação com instituição, coleta e destinação."], ["repasses", "Repasses", "Repasses calculados e pagos."], ["avaliacoes", "Avaliações", "Notas e comentários dos clientes."]];
  S.limpar(alvo, h("h1", {}, "Relatórios"), h("p", { class: "mudo" }, "Arquivos CSV que abrem direto no Excel (separados por ponto e vírgula)."),
    seletorPeriodo(P.periodoFin, (n) => { P.periodoFin = n; desenhar(); }),
    h("div", { class: "grade" }, tipos.map(([id, nome, desc]) => h("div", { class: "cartao" }, h("h3", {}, nome), h("p", { class: "mudo" }, desc),
      h("a", { class: "btn btn-cta btn-p", href: S.u(`/api/relatorios/${id}.csv` + comEmpresa(iv)) }, "Baixar")))));
}

// ------------------------------------------------------------------ avaliações
async function telaAvaliacoes(alvo) {
  const r = await S.api("/api/avaliacoes" + comEmpresa());
  const est = (n) => h("span", { class: "estrelas" }, "★".repeat(n) + "☆".repeat(5 - n));
  S.limpar(alvo, h("h1", {}, "Avaliações dos clientes"),
    h("div", { class: "kpis" }, kpi("Nota média", r.media ? `${r.media.toLocaleString("pt-BR")} ★` : "—", "laranja"), kpi("Avaliações", String(r.total))),
    r.itens.length ? h("div", { class: "grade" }, r.itens.map((a) => h("div", { class: "cartao" },
      h("div", { class: "linha" }, est(a.nota), h("span", { class: "mudo", style: { "text-align": "right" } }, `#${a.numero} · ${S.data(a.criada_em)}`)),
      P.eu.plataforma ? h("div", { class: "mudo" }, a.loja) : null, h("p", {}, a.comentario || h("span", { class: "mudo" }, "(sem comentário)")), h("div", { class: "mudo" }, a.cliente),
      a.resposta ? h("p", {}, h("b", {}, "Resposta da loja: "), a.resposta) : (pode("pedidos", "operar") ? h("button", { class: "btn btn-p btn-linha", onclick: async () => {
        const t = prompt("Resposta para o cliente:"); if (!t) return; await S.acao(() => S.api(`/api/avaliacoes/${a.id}/responder`, { corpo: { resposta: t } }), "Resposta enviada."); desenhar(); } }, "Responder") : null))))
      : h("p", { class: "mudo" }, "Nenhuma avaliação ainda. O cliente avalia depois que o pedido é concluído."));
}

// ------------------------------------------------------------------ planos
async function telaPlanos(alvo) {
  const [r, emps] = await Promise.all([S.api("/api/planos"), S.api("/api/empresas")]);
  const editar = (pl) => {
    const v = pl || {};
    const f = formulario([["nome", "Nome", "text", { valor: v.nome, obrigatorio: true }], ["descricao", "Descrição", "text", { valor: v.descricao }],
      ["mensalidade", "Mensalidade (R$)", "text", { valor: S.reais(v.mensalidade_centavos ?? 0) }], ["taxa_percentual", "Taxa sobre vendas (%)", "text", { valor: v.taxa_percentual ?? 12 }],
      ["limite_ofertas", "Ofertas no ar ao mesmo tempo (vazio = sem limite)", "number", { valor: v.limite_ofertas ?? "" }], ["destaque", "Lojas aparecem primeiro no app", "checkbox", { valor: !!v.destaque }],
      ["ativo", "Plano ativo", "checkbox", { valor: pl ? !!pl.ativo : true }]], "Salvar plano", async (val) => {
      await S.acao(() => S.api(pl ? "/api/planos/" + pl.id : "/api/planos", { method: pl ? "PUT" : "POST", corpo: { ...val, ativo: val.ativo ? 1 : 0 } }), "Plano salvo."); folha.fechar(); telaPlanos(alvo); });
    const folha = S.folha(h("div", {}, h("h2", {}, pl ? "Editar plano" : "Novo plano"), f));
  };
  S.limpar(alvo, h("div", { class: "barra-acoes" }, h("h1", {}, "Planos e mensalidades"), h("button", { class: "btn btn-cta", onclick: () => editar(null) }, "+ Novo plano")),
    h("p", { class: "mudo" }, "A taxa do plano vale para a empresa que não tem taxa própria. A mensalidade é cobrada todo dia 1º (aparece em Financeiro → Mensalidades)."),
    h("div", { class: "grade" }, r.itens.map((pl) => h("div", { class: "cartao" }, h("h2", {}, pl.nome), h("p", { class: "mudo" }, pl.descricao || ""),
      h("div", { class: "preco" }, S.dinheiro(pl.mensalidade_centavos), h("span", { class: "mudo", style: { "font-size": ".85rem" } }, " /mês")),
      h("p", {}, `Taxa ${pl.taxa_percentual}% · ${pl.limite_ofertas ? pl.limite_ofertas + " ofertas no ar" : "ofertas sem limite"}${pl.destaque ? " · destaque no app" : ""}`),
      h("p", { class: "mudo" }, `${pl.empresas} empresa(s)`), pl.ativo ? null : S.selo("inativo"),
      h("button", { class: "btn btn-p btn-linha", onclick: () => editar(pl) }, "Editar")))),
    h("div", { class: "cartao rolagem", style: { "margin-top": "1rem" } }, h("h2", {}, "Plano de cada empresa"), h("table", { class: "tabela" }, h("tbody", {}, emps.itens.map((e) => h("tr", {},
      h("td", {}, e.nome), h("td", {}, h("select", { style: { width: "auto" }, onchange: async (ev) => {
        await S.acao(() => S.api(`/api/empresas/${e.id}/plano`, { corpo: { plano_id: ev.target.value } }), "Plano alterado."); } },
        h("option", { value: "" }, "— sem plano —"), r.itens.map((pl) => h("option", { value: pl.id, selected: e.plano_id === pl.id }, pl.nome))))))))));
}

// ------------------------------------------------------------------ sistema com backups
const telaSistemaBase = telaSistema;
telaSistema = async function (alvo) {
  await telaSistemaBase(alvo);
  const b = await S.api("/api/sistema/backups").catch(() => ({ itens: [] }));
  alvo.append(h("div", { class: "cartao", style: { "margin-top": "1rem" } }, h("div", { class: "linha" }, h("h2", { style: { margin: 0 } }, "Cópias de segurança"),
    h("button", { class: "btn btn-escuro btn-p", style: { flex: "0 0 auto" }, onclick: async () => { await S.acao(() => S.api("/api/sistema/backups", { corpo: {} }), "Cópia feita."); desenhar(); } }, "Fazer cópia agora")),
    h("p", { class: "mudo" }, "Automática todo dia; o sistema guarda as últimas 14."),
    b.itens.length ? b.itens.map((x) => h("div", { class: "estado-int" }, h("span", {}, x.nome), h("a", { href: S.u("/api/sistema/backups/" + x.nome) }, `Baixar (${Math.round(x.bytes / 1024)} KB)`)))
      : h("p", { class: "mudo" }, "Nenhuma cópia ainda.")));
};

Object.assign(FUNCOES, { teste: telaTeste, config: telaConfig, financeiro: telaFinanceiro, relatorios: telaRelatorios, avaliacoes: telaAvaliacoes,
  planos: telaPlanos, sistema: telaSistema, usuarios: telaUsuarios, impacto: telaImpacto, inicio: telaInicio });

S.iniciarApp();
iniciar();
