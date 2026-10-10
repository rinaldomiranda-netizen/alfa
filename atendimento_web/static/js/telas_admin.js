/* Administração: Usuários & Permissões, Backup, Plano & Limites, Segurança, Configurações,
   Empresas (ALFA Owner) e Minha área (portal do cliente) */
"use strict";

/* ================================================================ USUÁRIOS */
const NOMES_RECURSOS = { dashboard: "Dashboard", conversas: "Atendimento", contatos: "Nomes", filas: "Filas & Equipes", orcamentos: "Orçamentos", servicos: "Serviços", fluxos: "Fluxos", agenda: "Agenda", whatsapp: "WhatsApp", api: "API & Webhooks", alertas: "Alertas", relatorios: "Relatórios", usuarios: "Usuários", backup: "Backup", plano: "Plano", seguranca: "Segurança", config: "Configurações", empresas: "Empresas", portal: "Portal do cliente", recepcao: "Recepção" };

registrarTela("users", {
  titulo: "Usuários & Permissões", sub: "Perfis com permissões diferentes de verdade — conferidas pelo servidor em cada ação.", icone: "♙",
  async render(el, { acoes }) {
    const [d, filas, contatos] = await Promise.all([api("/api/usuarios"), api("/api/filas"), api("/api/contatos")]);
    const editar = (u) => {
      const form = h("div", { class: "formulario" },
        campo("Nome", entrada("nome", u ? u.nome : "")),
        campo("E-mail (login)", entrada("email", u ? u.email : "", { type: "email", disabled: !!u })),
        campo("Perfil", seletor("perfil", d.perfis.map((p) => [p.id, p.nome]), u ? u.perfil : "atendente")),
        campo("Fila / equipe", seletor("fila_id", [["", "— nenhuma —"], ...filas.map((f) => [f.id, f.nome])], u ? u.fila_id || "" : "")),
        u ? marcador("ativo", u.ativo, "Usuário ativo") : campo("Ligado ao nome (só para perfil Cliente)", seletor("contato_id", [["", "—"], ...contatos.map((c) => [c.id, c.nome])], "")),
        u ? null : campo("Senha inicial (opcional)", entrada("senha", "", { type: "password", autocomplete: "new-password" }), "Vazio = o sistema gera uma senha temporária e pede para trocar no primeiro acesso."));
      const acoesModal = [{ texto: "Cancelar" }];
      if (u) acoesModal.push({ texto: "Gerar senha temporária", fecha: false, acao: async () => {
        if (!(await confirmar(`Gerar uma senha temporária para ${u.nome}? As sessões abertas dele serão encerradas.`))) return false;
        const r = await api(`/api/usuarios/${u.id}/senha`, { dados: {} }); mostrarSegredo("Senha temporária", "Senha", r.senha_temporaria, "Passe para o usuário. Ele vai criar uma senha nova no primeiro acesso.");
      } });
      acoesModal.push({ texto: "Salvar", classe: "primario", acao: async () => {
        const dados = lerFormulario(form);
        if (u) { await api("/api/usuarios/" + u.id, { metodo: "PUT", dados }); toast("Usuário atualizado."); }
        else { const r = await api("/api/usuarios", { dados }); if (r.senha_temporaria) mostrarSegredo("Usuário criado", "Senha temporária", r.senha_temporaria, "Passe para o usuário junto com o e-mail. Ele troca no primeiro acesso."); else toast("Usuário criado."); }
        mostrarTela();
      } });
      modal({ titulo: u ? "Editar usuário" : "Novo usuário", conteudo: form, acoes: acoesModal });
    };
    if (pode("usuarios", "criar")) acoes.append(h("button", { class: "btn primario", type: "button", text: "+ Novo usuário", on: { click: () => editar(null) } }));
    el.append(h("div", { class: "cartao" }, tabela([
      { titulo: "Usuário", valor: (u) => h("div", null, h("b", { text: u.nome }), h("div", { class: "suave", text: u.email })) },
      { titulo: "Perfil", valor: (u) => u.perfil_nome + (u.contato_nome ? ` (${u.contato_nome})` : "") },
      { titulo: "Equipe", valor: (u) => u.fila_nome || (u.perfil === "admin" ? "Todas" : "—") },
      { titulo: "Último acesso", valor: (u) => relativo(u.ultimo_acesso) },
      { titulo: "Status", valor: (u) => selo(u.ativo ? (u.presenca || "ativo") : "inativo", u.ativo ? null : "Desativado") },
    ], d.usuarios, pode("usuarios", "editar") ? editar : null)));
    const perfis = ["admin", "supervisor", "atendente", "cliente"];
    const recursos = Object.keys(NOMES_RECURSOS).filter((r) => r !== "empresas");
    el.append(h("div", { class: "cartao", style: { marginTop: "15px" } }, h("h2", { text: "O que cada perfil pode fazer" }),
      tabela([{ titulo: "Área", valor: (r) => NOMES_RECURSOS[r] }, ...perfis.map((p) => ({ titulo: { admin: "Admin. cliente", supervisor: "Supervisor", atendente: "Atendente", cliente: "Cliente" }[p], valor: (r) => (d.matriz[p][r] || []).join(", ") || "—" }))], recursos)));
  },
});

/* ================================================================ BACKUP */
registrarTela("backup", {
  titulo: "Backup", sub: "Cópias de segurança e restauração sem apagar nada.", icone: "⧉",
  async render(el, { acoes }) {
    const lista = await api("/api/backups");
    const ultimo = lista[0];
    acoes.append(h("button", { class: "btn primario", type: "button", text: "Criar backup agora", on: { click: async () => { try { await api("/api/backups", { dados: {} }); toast("Backup criado."); mostrarTela(); } catch (e) { falha(e); } } } }));
    const arquivo = h("input", { type: "file", accept: ".json,application/json" });
    const previa = h("div");
    arquivo.addEventListener("change", async () => {
      limpar(previa);
      const f = arquivo.files[0]; if (!f) return;
      let dados;
      try { dados = JSON.parse(await f.text()); } catch (_) { previa.append(h("div", { class: "aviso", text: "Esse arquivo não é um backup válido." })); return; }
      try {
        const r = await api("/api/backups/previa", { dados });
        previa.append(h("p", { class: "suave", text: r.explicacao }),
          tabela([{ titulo: "Tipo", valor: (x) => x.tabela }, { titulo: "No backup", valor: (x) => x.no_backup, num: true }, { titulo: "Já existem", valor: (x) => x.ja_existem, num: true }, { titulo: "Serão adicionados", valor: (x) => x.serao_adicionados, num: true }], r.resumo),
          h("button", { class: "btn primario", type: "button", style: { marginTop: "10px" }, text: "Restaurar (mesclar)", on: { click: async () => {
            if (!(await confirmar("Restaurar agora? Antes, o sistema faz um backup automático do estado atual."))) return;
            try { const res = await api("/api/backups/restaurar", { dados }); toast("Restaurado: " + Object.entries(res.adicionados).filter(([, n]) => n).map(([t, n]) => `${n} ${t}`).join(", ") || "nada novo"); mostrarTela(); } catch (e) { falha(e); }
          } } }));
      } catch (e) { previa.append(h("div", { class: "aviso", text: e.message })); }
    });
    el.append(h("div", { class: "grade colunas" },
      h("div", { class: "cartao" }, h("h2", { text: "Backups" }),
        ultimo ? h("div", { class: "item" }, h("div", null, h("b", { text: "Último backup" }), h("div", { class: "suave", text: `${dataHora(ultimo.criado_em)} • ${ultimo.tipo}` })), selo("ativo", "Concluído")) : h("div", { class: "aviso", text: "Nenhum backup ainda. Crie o primeiro agora." }),
        h("p", { class: "suave", text: "Um backup automático é feito todo dia (os últimos 30 ficam guardados). Tokens do WhatsApp e chaves de API nunca vão para o backup." }),
        tabela([{ titulo: "Data", valor: (b) => dataHora(b.criado_em) }, { titulo: "Tipo", valor: (b) => b.tipo }, { titulo: "Tamanho", valor: (b) => `${Math.max(1, Math.round(b.tamanho / 1024))} KB`, num: true },
          { titulo: "", valor: (b) => h("a", { class: "btn pequeno", href: `/api/backups/${b.id}/baixar`, text: "⬇ Baixar" }) }], lista)),
      h("div", { class: "cartao" }, h("h2", { text: "Restauração (mesclar)" }),
        h("p", { class: "suave", text: "Prévia antes de restaurar, sem operação destrutiva e só para administradores. Só entram registros que não existem hoje." }),
        campo("Arquivo de backup (.json)", arquivo), previa)));
  },
});

/* ================================================================ PLANO */
function barraUso(rotulo, u) {
  const classe = u.percentual >= 100 ? " estourada" : u.percentual >= 80 ? " alerta" : "";
  return h("div", { class: "cartao" }, h("h2", { text: rotulo }), h("div", { class: "valor", text: `${u.usado.toLocaleString("pt-BR")} / ${u.limite.toLocaleString("pt-BR")}` }),
    h("div", { class: "barra" + classe, style: { marginTop: "8px" } }, h("span", { style: { width: Math.min(100, u.percentual) + "%" } })),
    h("div", { class: "tendencia " + (classe ? "ruim" : "neutra"), text: `${u.percentual}% utilizado` }));
}
registrarTela("plan", {
  titulo: "Plano & Limites", sub: "Uso do plano contratado. No limite o sistema avisa — não bloqueia o atendimento.", icone: "◈",
  async render(el) {
    const d = await api("/api/plano");
    el.append(h("div", { class: "grade tres" },
      h("div", { class: "cartao" }, h("h2", { text: "Plano atual" }), h("div", { class: "valor", text: d.plano.nome }), h("p", { class: "suave", text: "Modo de alerta no limite" })),
      barraUso("Uso de nomes", d.nomes), barraUso("WhatsApp — canais ativos", d.canais_whatsapp)));
    el.append(h("div", { class: "grade duas", style: { marginTop: "15px" } }, barraUso("Usuários da equipe", d.usuarios),
      h("div", { class: "cartao" }, h("h2", { text: "Planos disponíveis" }), tabela([{ titulo: "Plano", valor: (p) => p.nome }, { titulo: "Nomes", valor: (p) => p.limite_nomes.toLocaleString("pt-BR"), num: true },
        { titulo: "Canais WhatsApp", valor: (p) => p.limite_canais_whatsapp, num: true }, { titulo: "Usuários", valor: (p) => p.limite_usuarios, num: true }], d.planos),
        h("p", { class: "suave", text: "A mudança de plano é feita pela RMD (ALFA Owner), no menu Empresas." }))));
  },
});

/* ================================================================ SEGURANÇA */
registrarTela("security", {
  titulo: "Segurança", sub: "Sessões, senha, verificação em duas etapas, auditoria e saúde do sistema.", icone: "◉",
  async render(el) {
    const [d, saude] = await Promise.all([api("/api/seguranca"), api("/api/health").catch(() => ({ ok: false }))]);
    el.append(h("div", { class: "grade tres" },
      h("div", { class: "cartao" }, h("h2", { text: "Autenticação" }), h("p", { class: "suave", text: "Senhas com PBKDF2 (200 mil rodadas), sessão em cookie protegido, bloqueio após 5 erros e proteção contra CSRF." }), selo("ativo"),
        h("div", { style: { marginTop: "10px" } }, h("button", { class: "btn", type: "button", text: "Trocar minha senha", on: { click: dialogoSenha } }))),
      h("div", { class: "cartao" }, h("h2", { text: "Auditoria" }), h("p", { class: "suave", text: "Eventos administrativos e operacionais registrados (quem, o quê, quando, de onde)." }), selo(d.auditoria ? "ativo" : "inativo", d.auditoria ? "Ativo" : "Só administradores")),
      h("div", { class: "cartao" }, h("h2", { text: "Saúde do sistema" }), h("p", { class: "suave", text: `Servidor ${d.servidor.endereco}. ${d.servidor.somente_este_computador ? "Aceita conexões só deste computador." : "Aberto para a rede — use HTTPS na frente."}` }),
        selo(saude.ok ? "ativo" : "cancelado", saude.ok ? "OK • versão " + saude.versao : "Com problema"))));
    el.append(h("div", { class: "grade duas", style: { marginTop: "15px" } }, cartaoDoisFatores(d.dois_fatores), d.backup_externo ? cartaoBackupExterno(d.backup_externo) : null));
    el.append(h("div", { class: "cartao", style: { marginTop: "15px" } }, h("h2", { text: "Minhas sessões" }),
      tabela([{ titulo: "Início", valor: (s) => dataHora(s.criada_em) }, { titulo: "Expira", valor: (s) => dataHora(s.expira_em) }, { titulo: "Endereço", valor: (s) => s.ip || "—" },
        { titulo: "Navegador", valor: (s) => (s.navegador || "—").slice(0, 60) },
        { titulo: "", valor: (s) => s.atual ? selo("ativo", "Esta sessão") : h("button", { class: "btn pequeno perigo", type: "button", text: "Encerrar", on: { click: async () => { await api(`/api/seguranca/sessoes/${s.id}/encerrar`, { dados: {} }); toast("Sessão encerrada."); mostrarTela(); } } }) }], d.sessoes)));
    if (d.auditoria) el.append(h("div", { class: "cartao", style: { marginTop: "15px" } }, h("h2", { text: "Auditoria (últimos 100 eventos)" }),
      tabela([{ titulo: "Quando", valor: (a) => dataHora(a.criado_em) }, { titulo: "Quem", valor: (a) => a.usuario_nome || "sistema/visitante" }, { titulo: "Ação", valor: (a) => a.acao }, { titulo: "Endereço", valor: (a) => a.ip || "—" }], d.auditoria)));
  },
});

function carregarQr() {
  if (window.qrcode) return Promise.resolve(window.qrcode);
  return new Promise((ok, erro) => { const sc = document.createElement("script"); sc.src = "/static/js/qrcode.js"; sc.onload = () => ok(window.qrcode); sc.onerror = erro; document.head.append(sc); });
}
function cartaoDoisFatores(ativo) {
  const cartao = h("div", { class: "cartao" }, h("h2", { text: "Verificação em duas etapas" }),
    h("p", { class: "suave", text: ativo
      ? "Ligada. Para entrar, além da senha, é pedido o código de 6 números do aplicativo autenticador do seu celular."
      : "Mais proteção: além da senha, o login pede um código de 6 números que muda a cada 30 segundos no seu celular (Google Authenticator, Microsoft Authenticator ou similar). Mesmo que alguém descubra a senha, não entra sem o celular." }),
    selo(ativo ? "ativo" : "inativo", ativo ? "Ligada" : "Desligada"),
    h("div", { style: { marginTop: "10px" } }, ativo
      ? h("button", { class: "btn perigo", type: "button", text: "Desligar", on: { click: desligarDoisFatores } })
      : h("button", { class: "btn primario", type: "button", text: "Ligar verificação", on: { click: () => ligarDoisFatores().catch(falha) } })));
  return cartao;
}
async function ligarDoisFatores() {
  const dados = await api("/api/seguranca/2fa/iniciar", { dados: {} });
  const qrLugar = h("div", { style: { textAlign: "center", margin: "10px 0" } });
  carregarQr().then((qrcode) => {
    const qr = qrcode(0, "M"); qr.addData(dados.endereco); qr.make();
    qrLugar.append(h("img", { src: qr.createDataURL(5, 8), alt: "Código QR para o aplicativo autenticador", style: { background: "#fff", borderRadius: "10px", maxWidth: "100%" } }));
  }).catch(() => {});
  const form = h("form", null,
    h("p", { class: "suave", text: "1) No celular, abra o aplicativo autenticador e toque em adicionar conta." }),
    h("p", { class: "suave", text: "2) Leia o código QR abaixo com a câmera do aplicativo. Se estiver usando o próprio celular, toque em \"Abrir no aplicativo\" ou copie a chave." }),
    qrLugar,
    h("div", { style: { display: "flex", gap: "8px", flexWrap: "wrap", justifyContent: "center" } },
      h("a", { class: "btn", href: dados.endereco, text: "Abrir no aplicativo" }),
      h("button", { class: "btn", type: "button", text: "Copiar chave", on: { click: () => navigator.clipboard.writeText(dados.segredo).then(() => toast("Chave copiada.")) } })),
    h("pre", { class: "mono", style: { textAlign: "center", whiteSpace: "pre-wrap", wordBreak: "break-all" }, text: dados.segredo.replace(/(.{4})/g, "$1 ").trim() }),
    campo("3) Digite o código de 6 números que apareceu", entrada("codigo", "", { inputmode: "numeric", autocomplete: "one-time-code", maxlength: "6", required: true })));
  modal({ titulo: "Ligar verificação em duas etapas", conteudo: form, acoes: [{ texto: "Cancelar" }, { texto: "Confirmar e ligar", classe: "primario", acao: async () => {
    await api("/api/seguranca/2fa/ativar", { dados: { codigo: lerFormulario(form).codigo } });
    toast("Verificação em duas etapas ligada."); mostrarTela();
  } }] });
}
function desligarDoisFatores() {
  const form = h("form", null, h("p", { class: "suave", text: "Para desligar, confirme a sua senha." }),
    campo("Senha", entrada("senha", "", { type: "password", required: true, autocomplete: "current-password" })));
  modal({ titulo: "Desligar verificação em duas etapas", conteudo: form, acoes: [{ texto: "Cancelar" }, { texto: "Desligar", classe: "perigo", acao: async () => {
    await api("/api/seguranca/2fa/desativar", { dados: lerFormulario(form) });
    toast("Verificação em duas etapas desligada."); mostrarTela();
  } }] });
}
function cartaoBackupExterno(b) {
  let texto, status, rotulo;
  if (!b.configurado) { texto = "Este servidor guarda backups só no próprio disco (menu Backup). A cópia fora do servidor é ligada na versão da internet."; status = "inativo"; rotulo = "Não configurado"; }
  else if (b.ultimo_ok) { texto = `Todo dia uma cópia completa é enviada para um armazenamento privado separado (últimos 30 dias). Última cópia: ${dataHora(b.ultimo_ok)}.` + (b.ultimo_erro ? ` Última tentativa falhou (${b.ultimo_erro}); tenta de novo a cada hora.` : ""); status = b.ultimo_erro ? "atencao" : "ativo"; rotulo = b.ultimo_erro ? "Atenção" : "Em dia"; }
  else { texto = "Configurado. A primeira cópia é enviada em poucos minutos." + (b.ultimo_erro ? ` Última tentativa falhou (${b.ultimo_erro}); tenta de novo a cada hora.` : ""); status = "atencao"; rotulo = "Aguardando"; }
  return h("div", { class: "cartao" }, h("h2", { text: "Cópia fora do servidor" }), h("p", { class: "suave", text: texto }), selo(status, rotulo));
}

/* ================================================================ CONFIGURAÇÕES */
const AMOSTRAS = { alfa: ["#07131f", "#14304a", "#28d7d1"], claro: ["#eef5f7", "#ffffff", "#087f82"], medio: ["#2a323c", "#38424f", "#5fd0d6"], escuro: ["#0e1014", "#171b22", "#4f9dff"], contraste: ["#000000", "#0a0a0a", "#ffd60a"] };
registrarTela("settings", {
  titulo: "Configurações", sub: "Nome, logo, tema da tela e mensagens da empresa.", icone: "⚙",
  async render(el) {
    const c = await api("/api/config");
    let logo = c.logo || "";
    let tema = c.tema;
    const previaLogo = h("div", { class: "empresa", style: { display: "flex", gap: "12px", alignItems: "center" } });
    const desenharLogo = () => { limpar(previaLogo).append(logo ? h("img", { class: "logo", src: logo, alt: "Logo", style: { width: "64px", height: "64px", borderRadius: "12px", objectFit: "contain", border: "1px solid var(--borda)", background: "var(--superficie)" } }) : h("div", { class: "avatar", style: { width: "64px", height: "64px", fontSize: "20px" }, text: iniciais(c.empresa_nome) }),
      ...(logo ? [h("button", { class: "btn pequeno perigo", type: "button", text: "Remover logo", on: { click: () => { logo = ""; desenharLogo(); } } })] : [])); };
    desenharLogo();
    const arquivo = h("input", { type: "file", accept: "image/png,image/jpeg,image/webp" });
    arquivo.addEventListener("change", () => {
      const f = arquivo.files[0]; if (!f) return;
      if (f.size > 300 * 1024) { toast("Use uma imagem de até 300 KB.", "erro"); return; }
      const leitor = new FileReader(); leitor.onload = () => { logo = String(leitor.result); desenharLogo(); }; leitor.readAsDataURL(f);
    });
    const temas = h("div", { class: "temas" });
    const desenharTemas = () => { limpar(temas); Object.entries(App.sessao.temas).forEach(([id, nome]) => temas.append(h("div", { class: "tema-opcao" + (id === tema ? " ativo" : ""), role: "button", tabindex: 0, on: { click: () => { tema = id; desenharTemas(); document.documentElement.dataset.tema = id; } } },
      h("div", { class: "amostra" }, AMOSTRAS[id].map((cor) => h("span", { style: { background: cor } }))), nome))); };
    desenharTemas();
    const cor = h("input", { type: "color", name: "cor", value: c.cor_destaque || AMOSTRAS[tema][2] });
    let usarCor = !!c.cor_destaque;
    cor.addEventListener("input", () => { usarCor = true; document.documentElement.style.setProperty("--primaria", cor.value); });
    const geral = h("div", { class: "formulario" },
      campo("Nome do sistema", entrada("nome_sistema", c.nome_sistema)),
      campo("Nome da empresa (aparece no cabeçalho)", entrada("empresa_nome", c.empresa_nome)),
      campo("Fuso horário", seletor("fuso", [["America/Maceio", "America/Maceio (UTC-3)"], ["America/Sao_Paulo", "America/Sao_Paulo (UTC-3)"], ["America/Bahia", "America/Bahia (UTC-3)"], ["America/Fortaleza", "America/Fortaleza (UTC-3)"], ["America/Recife", "America/Recife (UTC-3)"], ["America/Belem", "America/Belem (UTC-3)"], ["America/Manaus", "America/Manaus (UTC-4)"], ["America/Cuiaba", "America/Cuiaba (UTC-4)"], ["America/Rio_Branco", "America/Rio_Branco (UTC-5)"], ["America/Noronha", "America/Noronha (UTC-2)"]], c.fuso)),
      campo("Mensagem inicial", areaTexto("mensagem_inicial", c.mensagem_inicial), "Enviada quando alguém chama e não há fluxo publicado.", true),
      marcador("atribuicao_automatica", c.atribuicao_automatica, "Distribuir automaticamente para o atendente online com menos conversas"),
      marcador("pedir_avaliacao", c.pedir_avaliacao, "Pedir avaliação (1 a 5) ao resolver o atendimento"));
    const salvar = h("button", { class: "btn primario", type: "button", text: "Salvar configurações", on: { click: async () => {
      try {
        App.sessao = await api("/api/config", { metodo: "PUT", dados: { ...lerFormulario(geral), logo: logo || null, tema, cor_destaque: usarCor ? cor.value : null } });
        toast("Configurações salvas."); montarAplicacao(); navegar("settings");
      } catch (e) { falha(e); }
    } } });
    const linkChat = `${location.origin}/chat?e=${c.empresa_slug}`;
    el.append(h("div", { class: "grade colunas" },
      h("div", { class: "cartao" }, h("h2", { text: "Configurações gerais" }), geral),
      h("div", { class: "cartao" }, h("h2", { text: "Identidade visual" }), campo("Logo da empresa", h("div", null, previaLogo, h("div", { style: { marginTop: "8px" } }, arquivo)), "PNG, JPG ou WEBP, até 300 KB."),
        h("h3", { text: "Tema da tela" }), temas, h("p", { class: "suave", text: "Padrão da empresa. Cada pessoa ainda pode escolher o próprio tema no menu do usuário (canto superior direito)." }),
        campo("Cor de destaque", h("div", { class: "busca" }, cor, h("button", { class: "btn pequeno", type: "button", text: "Usar a cor do tema", on: { click: () => { usarCor = false; document.documentElement.style.removeProperty("--primaria"); } } }))))));
    el.append(h("div", { class: "grade duas", style: { marginTop: "15px" } },
      h("div", { class: "cartao" }, h("h2", { text: "Organização" }), h("div", { class: "item" }, h("b", { text: c.empresa_nome }), c.demonstracao ? h("span", { class: "selo s-demo", text: "DEMONSTRAÇÃO" }) : selo("ativo", "Ativa")),
        h("div", { class: "suave", text: "Arquitetura multiempresa: os dados desta empresa ficam isolados das outras." })),
      h("div", { class: "cartao" }, h("h2", { text: "Chat do site" }), h("p", { class: "suave", text: "Coloque este link no seu site ou redes sociais. Quem clicar conversa com a sua equipe (e com o robô, se houver fluxo publicado)." }), copiavel(linkChat))));
    el.append(h("div", { class: "acoes", style: { marginTop: "15px", justifyContent: "flex-end" } }, salvar));
    App.limpezaTela = () => aplicarTema();
  },
});

/* ================================================================ EMPRESAS (ALFA OWNER) */
registrarTela("companies", {
  titulo: "Empresas", sub: "Plataforma ALFA: empresas clientes do RMD Atendimento.", icone: "▦",
  async render(el, { acoes }) {
    const lista = await api("/api/empresas");
    const planos = [["essencial", "Essencial"], ["business", "Business"], ["enterprise", "Enterprise"]];
    const nova = () => {
      const form = h("div", { class: "formulario" }, campo("Nome da empresa", entrada("nome", "")), campo("Plano", seletor("plano", planos, "essencial")),
        campo("Nome do administrador", entrada("admin_nome", "")), campo("E-mail do administrador", entrada("admin_email", "", { type: "email" }), "Recebe uma senha temporária."));
      modal({ titulo: "Nova empresa", conteudo: form, acoes: [{ texto: "Cancelar" }, { texto: "Criar", classe: "primario", acao: async () => {
        const r = await api("/api/empresas", { dados: lerFormulario(form) });
        if (r.admin && r.admin.senha_temporaria) mostrarSegredo("Empresa criada", `Senha temporária de ${r.admin.usuario.email}`, r.admin.senha_temporaria, "Passe para o administrador da empresa.");
        else toast("Empresa criada."); mostrarTela();
      } }] });
    };
    const editar = (e) => {
      const form = h("div", { class: "formulario" }, campo("Nome", entrada("nome", e.nome)), campo("Plano", seletor("plano", planos, e.plano)), marcador("ativa", e.ativa, "Empresa ativa (desativar bloqueia o acesso dela)"));
      modal({ titulo: e.nome, conteudo: form, acoes: [{ texto: "Cancelar" }, { texto: "Salvar", classe: "primario", acao: async () => { await api("/api/empresas/" + e.id, { metodo: "PUT", dados: lerFormulario(form) }); toast("Empresa atualizada."); mostrarTela(); } }] });
    };
    const entrar = async (e) => { App.sessao = await api("/api/empresa-ativa", { dados: { empresa_id: e.id } }); toast("Agora você está em " + e.nome + "."); montarAplicacao(); navegar("dash"); };
    acoes.append(h("button", { class: "btn primario", type: "button", text: "+ Nova empresa", on: { click: nova } }));
    el.append(h("div", { class: "cartao" }, tabela([
      { titulo: "Empresa", valor: (e) => h("div", null, h("b", { text: e.nome }), " ", e.demonstracao ? h("span", { class: "selo s-demo", text: "DEMO" }) : null, h("div", { class: "suave", text: e.slug })) },
      { titulo: "Plano", valor: (e) => e.plano_nome }, { titulo: "Usuários", valor: (e) => e.usuarios, num: true }, { titulo: "Nomes", valor: (e) => e.nomes, num: true },
      { titulo: "Status", valor: (e) => selo(e.ativa ? "ativo" : "inativo") },
      { titulo: "", valor: (e) => h("div", { class: "acoes", on: { click: (ev) => ev.stopPropagation() } },
        h("button", { class: "btn pequeno", type: "button", text: App.sessao.empresa && App.sessao.empresa.empresa_slug === e.slug ? "Você está aqui" : "Entrar", disabled: App.sessao.empresa && App.sessao.empresa.empresa_slug === e.slug, on: { click: () => entrar(e).catch(falha) } }),
        h("button", { class: "btn pequeno", type: "button", text: "Editar", on: { click: () => editar(e) } })) },
    ], lista)));
  },
});

/* ================================================================ MINHA ÁREA (CLIENTE) */
registrarTela("portal", {
  titulo: "Minha área", sub: "Suas conversas, orçamentos e agendamentos.", icone: "☺",
  async render(el) {
    const d = await api("/api/portal");
    const aberta = d.conversas.find((c) => c.canal === "portal" && c.status !== "resolvido") || d.conversas.find((c) => c.status !== "resolvido");
    const conversa = aberta ? await api("/api/portal/conversas/" + aberta.id) : null;
    const outras = d.conversas.filter((c) => !aberta || c.id !== aberta.id);
    const mensagens = h("div", { class: "mensagens", style: { minHeight: "280px", maxHeight: "50vh", borderRadius: "12px" } });
    const desenhar = (c) => { limpar(mensagens); (c ? c.mensagens : []).forEach((m) => mensagens.append(h("div", { class: "msg " + (m.direcao === "entrada" ? "saida" : "entrada") }, m.texto,
      m.payload && m.payload.opcoes ? h("div", { class: "opcoes-msg" }, m.payload.opcoes.map((o) => h("button", { class: "btn pequeno", type: "button", text: o, on: { click: () => enviar(o) } }))) : null,
      h("div", { class: "meta", text: hora(m.criada_em) }))));
      if (!c || !c.mensagens.length) mensagens.append(h("div", { class: "vazio", text: "Escreva abaixo para falar com a empresa." }));
      mensagens.scrollTop = mensagens.scrollHeight; };
    const texto = areaTexto("texto", "", { rows: 1, placeholder: "Escreva sua mensagem…" });
    async function enviar(valor) { const t = (valor || texto.value).trim(); if (!t) return; try { desenhar(await api("/api/portal/mensagens", { dados: { texto: t } })); texto.value = ""; } catch (e) { falha(e); } }
    texto.addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); enviar(); } });
    desenhar(conversa);
    const decidir = async (o, aprovar) => { if (!(await confirmar(aprovar ? `Aprovar o orçamento ${sigla()}-${o.numero}${comValores() ? " de " + moeda(o.total_centavos) : ""}?` : `Recusar o orçamento ${sigla()}-${o.numero}?`, aprovar ? "Aprovar" : "Recusar", aprovar ? "sucesso" : "perigo"))) return;
      try { await api(`/api/portal/orcamentos/${o.id}/decisao`, { dados: { aprovar } }); toast(aprovar ? "Orçamento aprovado. A empresa foi avisada." : "Orçamento recusado."); mostrarTela(); } catch (e) { falha(e); } };
    el.append(h("div", { class: "grade colunas" },
      h("div", { class: "cartao" }, h("h2", { text: "Conversa com a empresa" }), mensagens, h("div", { class: "compositor", style: { padding: "12px 0 0", borderTop: 0 } }, texto, h("button", { class: "btn primario", type: "button", text: "Enviar", on: { click: () => enviar() } })),
        outras.length ? h("div", null, h("h3", { text: "Atendimentos anteriores" }), outras.map((c) => h("div", { class: "item" }, h("span", { text: `#${c.numero} • ${CANAIS[c.canal] || c.canal} • ${data(c.criada_em)}` }), selo(c.status)))) : null),
      h("div", null,
        h("div", { class: "cartao" }, h("h2", { text: "Meus orçamentos" }), d.orcamentos.length ? d.orcamentos.map((o) => h("div", { class: "item" },
          h("div", null, h("b", { text: `${sigla()}-${o.numero}` + (comValores() ? ` • ${moeda(o.total_centavos)}` : "") }), h("div", { class: "suave", text: `Validade ${data(o.validade)}${o.descricao ? " • " + o.descricao.slice(0, 60) : ""}` })),
          h("div", { class: "acoes" }, selo(o.status), h("a", { class: "btn pequeno", href: `/orcamentos/${o.id}/imprimir`, target: "_blank", rel: "noopener", text: "Ver" }),
            ["enviado", "em_analise"].includes(o.status) ? [h("button", { class: "btn pequeno sucesso", type: "button", text: "Aprovar", on: { click: () => decidir(o, true) } }), h("button", { class: "btn pequeno perigo", type: "button", text: "Recusar", on: { click: () => decidir(o, false) } })] : null))) : h("div", { class: "vazio", text: "Nenhum orçamento." })),
        h("div", { class: "cartao", style: { marginTop: "15px" } }, h("h2", { text: "Meus agendamentos" }), d.agenda.length ? d.agenda.map((a) => h("div", { class: "item" }, h("div", null, h("b", { text: a.titulo }), h("div", { class: "suave", text: dataHora(a.inicio) })), selo(a.status))) : h("div", { class: "vazio", text: "Nenhum agendamento." })))));
    const t = setInterval(async () => { if (App.atual !== "portal" || document.activeElement === texto) return; try { const r = await api("/api/portal"); const ab = r.conversas.find((c) => c.status !== "resolvido") || r.conversas[0]; if (ab) desenhar(await api("/api/portal/conversas/" + ab.id)); } catch (_) { /* ignora */ } }, 8000);
    App.limpezaTela = () => clearInterval(t);
  },
});
