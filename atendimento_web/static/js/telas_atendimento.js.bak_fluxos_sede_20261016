/* Principal: Dashboard, Atendimento (caixa de entrada), Nomes, Filas & Equipes */
"use strict";

/* ================================================================ DASHBOARD */
registrarTela("dash", {
  titulo: "Dashboard", sub: "Visão geral do atendimento e da operação.", icone: "◈",
  async render(el) {
    const d = await api("/api/dashboard");
    const c = d.cartoes;
    const variacao = c.variacao_ontem === null ? "sem comparação com ontem" : `${c.variacao_ontem >= 0 ? "▲" : "▼"} ${Math.abs(c.variacao_ontem).toLocaleString("pt-BR")}% vs. ontem`;
    el.append(h("div", { class: "grade estatisticas" },
      cartaoNumero("Atendimentos hoje", c.hoje, variacao, c.variacao_ontem === null ? "neutra" : c.variacao_ontem < 0 ? "ruim" : ""),
      cartaoNumero("Em atendimento", c.em_atendimento, `${c.aguardando} aguardando${c.no_robo ? ` • ${c.no_robo} no robô` : ""}`, c.aguardando ? "" : "neutra"),
      cartaoNumero("SLA cumprido (7 dias)", c.sla === null ? "—" : c.sla + "%", c.sla_variacao === null ? "sem dados suficientes" : `${c.sla_variacao >= 0 ? "+" : ""}${c.sla_variacao} p.p.`, c.sla_variacao === null ? "neutra" : c.sla_variacao < 0 ? "ruim" : ""),
      cartaoNumero("Orçamentos abertos", c.orcamentos_abertos, c.orcamentos_vencendo ? `${c.orcamentos_vencendo} próximos do vencimento` : "nenhum vencendo", c.orcamentos_vencendo ? "ruim" : "neutra"),
      cartaoNumero("CSAT (30 dias)", c.csat === null ? "—" : `${String(c.csat).replace(".", ",")}/5`, c.csat_variacao === null ? "sem avaliações suficientes" : `${c.csat_variacao >= 0 ? "+" : ""}${String(c.csat_variacao).replace(".", ",")} no período`, c.csat_variacao === null ? "neutra" : c.csat_variacao < 0 ? "ruim" : "")));

    const recentes = h("div", { class: "cartao" },
      h("div", { class: "linha-titulo" }, h("div", null, h("h2", { text: "Atendimentos recentes" }), h("span", { class: "suave", text: "Atividade em tempo real" })),
        h("button", { class: "btn", type: "button", text: "Abrir central", on: { click: () => navegar("chat") } })),
      tabela([
        { titulo: "Nome", valor: (x) => x.contato_nome },
        { titulo: "Canal", valor: (x) => CANAIS[x.canal] || x.canal },
        { titulo: "Status", valor: (x) => selo(x.status) },
        { titulo: "Equipe", valor: (x) => x.fila_nome || "—" },
        { titulo: "Responsável", valor: (x) => x.responsavel_nome || "—" },
      ], d.recentes, (x) => navegar("chat", x.id)));
    const fila = h("div", { class: "cartao" },
      h("div", { class: "linha-titulo" }, h("div", null, h("h2", { text: "Fila de prioridade" }), h("span", { class: "suave", text: "Próximos SLAs de primeira resposta" }))),
      d.fila_prioridade.length ? d.fila_prioridade.map((x) => h("div", { class: "item clicavel", on: { click: () => navegar("chat", x.id) } },
        h("div", null, h("b", { text: x.contato_nome }), h("div", { class: "suave", text: x.sla_restante <= 0 ? `SLA vencido há ${mmss(-x.sla_restante)}` : `SLA em ${mmss(x.sla_restante)} • ${x.fila_nome || ""}` })),
        selo(x.prioridade))) : h("div", { class: "vazio", text: "Ninguém esperando. 👍" }));
    el.append(h("div", { class: "grade colunas" }, recentes, fila));
    const t = setInterval(() => { if (App.atual === "dash") mostrarTela(); }, 30000);
    App.limpezaTela = () => clearInterval(t);
  },
});

/* ================================================================ ATENDIMENTO */
registrarTela("chat", {
  titulo: "Atendimento", sub: "Central de conversas: WhatsApp, site e portal do cliente.", icone: "◉",
  async render(el, { acoes, parametro }) {
    const estado = { filtro: "abertas", busca: "", atual: parametro, dados: null, equipe: null, filas: null };
    const central = h("div", { class: "cartao central" });
    const lista = h("div", { class: "itens-conversa" });
    const busca = entrada("busca", "", { placeholder: "Pesquisar nome ou número…", type: "search" });
    const abas = h("div", { class: "abas" });
    const FILTROS = [["abertas", "Abertas"], ["minhas", "Minhas"], ["aguardando", "Aguardando"], ["resolvido", "Resolvidas"]];
    FILTROS.forEach(([v, t]) => abas.append(h("button", { type: "button", class: v === estado.filtro ? "ativo" : null, text: t, on: { click: (e) => { estado.filtro = v; abas.querySelectorAll("button").forEach((b) => b.classList.remove("ativo")); e.target.classList.add("ativo"); carregarLista(); } } })));
    let atrasoBusca;
    busca.addEventListener("input", () => { clearTimeout(atrasoBusca); atrasoBusca = setTimeout(() => { estado.busca = busca.value.trim(); carregarLista(); }, 300); });
    const painel = h("div", { class: "painel-conversa" });
    const info = h("div", { class: "info-conversa" });
    central.append(h("div", { class: "lista-conversas" }, h("div", { class: "topo" }, busca, abas), lista), painel, info);
    el.append(central);
    acoes.append(h("button", { class: "btn", type: "button", text: "+ Nova conversa", on: { click: novaConversa } }));

    async function carregarLista() {
      const q = new URLSearchParams();
      if (estado.filtro === "minhas") { q.set("minhas", "1"); q.set("status", "abertas"); } else q.set("status", estado.filtro);
      if (estado.busca) q.set("busca", estado.busca);
      try {
        const itens = await api("/api/conversas?" + q);
        limpar(lista);
        if (!itens.length) lista.append(h("div", { class: "vazio", style: { margin: "12px" }, text: "Nenhum atendimento aqui." }));
        itens.forEach((x) => lista.append(h("div", { class: "item-conversa" + (x.id === estado.atual ? " ativo" : ""), on: { click: () => abrir(x.id) } },
          h("div", { class: "l1" }, h("b", { text: x.contato_nome }), h("span", { class: "suave", text: relativo(x.atualizada_em) })),
          h("div", { class: "previa", text: x.ultima_mensagem || "—" }),
          h("div", { class: "l1", style: { marginTop: "4px" } }, h("span", { class: "suave", text: `#${x.numero} • ${CANAIS[x.canal] || x.canal}` }),
            x.prioridade !== "normal" ? selo(x.prioridade) : selo(x.status)))));
      } catch (e) { falha(e); }
    }

    function balao(m) {
      if (m.direcao === "sistema") return h("div", { class: "msg sistema", text: m.texto });
      const classe = m.direcao === "entrada" ? "entrada" : m.autor_tipo === "robo" ? "robo" : "saida";
      const opcoes = m.payload && m.payload.opcoes && m.payload.opcoes.length ? h("div", { class: "opcoes-msg" }, m.payload.opcoes.map((o) => h("span", { class: "selo s-azul", text: o }))) : null;
      const entrega = m.direcao === "saida" && m.status_entrega ? ` • ${({ enviado: "enviado", entregue: "entregue", lido: "lido ✓✓", falhou: "FALHOU" })[m.status_entrega] || m.status_entrega}` : "";
      return h("div", { class: "msg " + classe, title: m.erro || "" }, m.texto, opcoes,
        h("div", { class: "meta", text: `${m.autor_tipo === "robo" ? "Robô • " : ""}${hora(m.criada_em)}${entrega}` }));
    }

    async function abrir(id) {
      estado.atual = id;
      central.classList.add("com-conversa");
      history.replaceState(null, "", "#/chat/" + id);
      lista.querySelectorAll(".item-conversa").forEach((i) => i.classList.remove("ativo"));
      try { estado.dados = await api("/api/conversas/" + id); } catch (e) { falha(e); return; }
      desenharConversa();
    }

    function desenharConversa() {
      const c = estado.dados;
      limpar(painel); limpar(info);
      if (!c) { painel.append(h("div", { class: "vazio", style: { margin: "auto" }, text: "Escolha um atendimento na lista." })); return; }
      const botoes = h("div", { class: "acoes" },
        h("button", { class: "btn pequeno botao-menu", type: "button", text: "← Lista", on: { click: () => { central.classList.remove("com-conversa"); } } }));
      if (c.status !== "resolvido") {
        if (c.responsavel_id !== App.sessao.usuario.id) botoes.append(h("button", { class: "btn pequeno", type: "button", text: "Assumir", on: { click: () => acao("assumir") } }));
        botoes.append(h("button", { class: "btn pequeno", type: "button", title: "Transferir", text: "↗ Transferir", on: { click: transferir } }));
        botoes.append(h("button", { class: "btn pequeno sucesso", type: "button", text: "✓ Resolver", on: { click: async () => { if (await confirmar("Marcar este atendimento como resolvido?", "Resolver", "sucesso")) acao("resolver"); } } }));
      }
      if (pode("orcamentos", "criar")) botoes.append(h("button", { class: "btn pequeno", type: "button", text: "▣ Orçamento", on: { click: () => App.editarOrcamento(null, { contato_id: c.contato_id, conversa_id: c.id }) } }));
      painel.append(h("div", { class: "cabeca-conversa" },
        h("div", null, h("b", { text: c.contato ? c.contato.nome : "—" }), " ", selo(c.status),
          h("div", { class: "suave", text: `${CANAIS[c.canal] || c.canal} • Atendimento #${c.numero} • ${c.fila_nome || "sem fila"}${c.responsavel_nome ? " • " + c.responsavel_nome : ""}` })),
        botoes));
      const mensagens = h("div", { class: "mensagens" }, c.mensagens.map(balao));
      painel.append(mensagens);
      const texto = areaTexto("texto", "", { placeholder: c.status === "resolvido" ? "Atendimento resolvido." : "Digite uma mensagem…", title: "Enter envia • Shift+Enter quebra a linha", rows: 1, disabled: c.status === "resolvido" });
      const enviar = async () => {
        const t = texto.value.trim(); if (!t) return;
        texto.disabled = true;
        try { estado.dados = await api(`/api/conversas/${c.id}/responder`, { dados: { texto: t } }); texto.value = ""; desenharConversa(); carregarLista(); }
        catch (e) { falha(e); texto.disabled = false; }
      };
      texto.addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); enviar(); } });
      painel.append(h("div", { class: "compositor" }, texto, h("button", { class: "btn primario", type: "button", text: "Enviar", disabled: c.status === "resolvido", on: { click: enviar } })));
      setTimeout(() => { mensagens.scrollTop = mensagens.scrollHeight; if (!texto.disabled) texto.focus(); }, 0);
      const ct = c.contato || {};
      const memoria = Object.entries(c.memoria_robo || {}).filter(([k]) => !["nome", "empresa"].includes(k));
      info.append(h("h3", { text: "Cliente" }), h("dl", null,
        h("dt", { text: "Nome" }), h("dd", { text: ct.nome || "—" }),
        h("dt", { text: "WhatsApp / telefone" }), h("dd", { text: telefone(ct.whatsapp || ct.telefone) }),
        h("dt", { text: "E-mail" }), h("dd", { text: ct.email || "—" }),
        h("dt", { text: "Etiquetas" }), h("dd", null, (ct.tags || []).length ? ct.tags.map((t) => h("span", { class: "selo s-azul", style: { marginRight: "4px" }, text: t })) : "—"),
        h("dt", { text: "SLA de primeira resposta" }), h("dd", { text: c.primeira_resposta_em ? `respondido ${dataHora(c.primeira_resposta_em)}` : c.sla_vence_em ? `vence ${dataHora(c.sla_vence_em)}` : "—" }),
        c.avaliacao ? [h("dt", { text: "Avaliação" }), h("dd", { text: "★".repeat(c.avaliacao) + "☆".repeat(5 - c.avaliacao) })] : null,
        memoria.length ? [h("dt", { text: "Respostas ao robô" }), h("dd", null, memoria.map(([k, v]) => h("div", { text: `${k}: ${v}` })))] : null),
        h("button", { class: "btn pequeno", type: "button", style: { marginTop: "12px" }, text: "Abrir cadastro", on: { click: () => App.abrirContato && App.abrirContato(c.contato_id) } }));
    }

    async function acao(nome) {
      try { estado.dados = await api(`/api/conversas/${estado.atual}/${nome}`, { dados: {} }); desenharConversa(); carregarLista(); toast("Feito."); }
      catch (e) { falha(e); }
    }

    async function transferir() {
      const [filas, equipe] = await Promise.all([api("/api/filas"), api("/api/equipe")]);
      const form = h("div", { class: "formulario" },
        campo("Para a fila", seletor("fila_id", [["", "— manter —"], ...filas.filter((f) => f.ativa).map((f) => [f.id, `${f.nome} (${f.aguardando} aguardando)`])], "")),
        campo("Para o atendente", seletor("responsavel_id", [["", "— quem estiver livre —"], ...equipe.map((u) => [u.id, `${u.nome} • ${u.presenca}`])], "")));
      modal({ titulo: "Transferir atendimento", conteudo: form, acoes: [{ texto: "Cancelar" }, { texto: "Transferir", classe: "primario", acao: async () => {
        estado.dados = await api(`/api/conversas/${estado.atual}/transferir`, { dados: lerFormulario(form) });
        desenharConversa(); carregarLista(); toast("Transferido.");
      } }] });
    }

    async function novaConversa() {
      const contatos = await api("/api/contatos");
      if (!contatos.length) { toast("Cadastre um nome primeiro (menu Nomes).", "erro"); return; }
      const form = h("div", { class: "formulario" },
        campo("Nome", seletor("contato_id", contatos.map((c) => [c.id, `${c.nome} ${c.whatsapp ? "• " + telefone(c.whatsapp) : ""}`]), contatos[0].id), null, true),
        campo("Mensagem", areaTexto("texto", ""), "Se houver WhatsApp configurado e o nome tiver número, a mensagem vai pelo WhatsApp.", true));
      modal({ titulo: "Nova conversa", conteudo: form, acoes: [{ texto: "Cancelar" }, { texto: "Enviar", classe: "primario", acao: async () => {
        const c = await api("/api/conversas/nova", { dados: lerFormulario(form) });
        await carregarLista(); abrir(c.id);
      } }] });
    }

    await carregarLista();
    if (estado.atual) await abrir(estado.atual); else desenharConversa();
    const t = setInterval(async () => {
      if (App.atual !== "chat") return;
      await carregarLista();
      if (estado.atual && document.activeElement && document.activeElement.name !== "texto") {
        try { const novo = await api("/api/conversas/" + estado.atual); if (novo.mensagens.length !== estado.dados.mensagens.length || novo.status !== estado.dados.status) { estado.dados = novo; desenharConversa(); } } catch (_) { /* ignora */ }
      }
    }, 6000);
    App.limpezaTela = () => clearInterval(t);
  },
});

/* ================================================================ NOMES */
App.abrirContato = async function abrirContato(id, aoSalvar) {
  const novo = !id;
  const c = novo ? { nome: "", telefone: "", email: "", tags: [], observacoes: "", status: "novo" } : await api("/api/contatos/" + id);
  const form = h("div", { class: "formulario" },
    campo("Nome", entrada("nome", c.nome, { required: true })),
    campo("Status", seletor("status", [["novo", "Novo"], ["ativo", "Ativo"], ["inativo", "Inativo"]], c.status)),
    campo("Telefone / WhatsApp (com DDD)", entrada("telefone", c.whatsapp || c.telefone || "", { inputmode: "tel", placeholder: "(79) 99999-1111" })),
    campo("E-mail", entrada("email", c.email || "", { type: "email" })),
    campo("Etiquetas (separe por vírgula)", entrada("tags", (c.tags || []).join(", "), { placeholder: "VIP, orçamento" }), null, true),
    campo("Observações", areaTexto("observacoes", c.observacoes || ""), null, true));
  const extra = h("div");
  if (!novo) {
    extra.append(h("h3", { text: "Histórico" }),
      h("div", { class: "grade duas" },
        h("div", null, h("div", { class: "rotulo", text: "Atendimentos" }), c.conversas.length ? c.conversas.map((x) => h("div", { class: "item clicavel", on: { click: () => { document.querySelector(".modal").remove(); navegar("chat", x.id); } } }, h("span", { text: `#${x.numero} • ${CANAIS[x.canal] || x.canal} • ${data(x.criada_em)}` }), selo(x.status))) : h("div", { class: "vazio", text: "Sem atendimentos." })),
        h("div", null, h("div", { class: "rotulo", text: "Orçamentos" }), c.orcamentos.length ? c.orcamentos.map((o) => h("div", { class: "item" }, h("span", { text: `${sigla()}-${o.numero}` + (comValores() ? ` • ${moeda(o.total_centavos)}` : "") }), selo(o.status))) : h("div", { class: "vazio", text: "Sem orçamentos." }))));
  }
  const acoesModal = [{ texto: "Fechar" }];
  if (!novo && pode("contatos", "excluir")) acoesModal.unshift({ texto: "Remover dados (LGPD)", classe: "perigo", fecha: false, acao: async (fechar) => {
    if (!(await confirmar("Apagar os dados pessoais deste nome? O histórico numérico fica, mas nome, telefone, e-mail e mensagens são apagados. Não dá para desfazer.", "Apagar dados", "perigo"))) return false;
    await api(`/api/contatos/${id}/anonimizar`, { dados: {} }); toast("Dados pessoais removidos."); fechar(); if (aoSalvar) aoSalvar();
  } });
  if (!novo && pode("conversas", "responder")) acoesModal.push({ texto: "Iniciar conversa", acao: async () => {
    const texto = areaTexto("texto", "");
    modal({ titulo: "Mensagem para " + c.nome, conteudo: campo("Mensagem", texto, "Vai pelo WhatsApp quando houver número configurado.", true), acoes: [{ texto: "Cancelar" }, { texto: "Enviar", classe: "primario", acao: async () => {
      const r = await api("/api/conversas/nova", { dados: { contato_id: id, texto: texto.value } }); navegar("chat", r.id);
    } }] });
  } });
  acoesModal.push({ texto: novo ? "Cadastrar" : "Salvar", classe: "primario", acao: async () => {
    const d = lerFormulario(form);
    await api(novo ? "/api/contatos" : "/api/contatos/" + id, { metodo: novo ? "POST" : "PUT", dados: d });
    toast(novo ? "Nome cadastrado." : "Alterações salvas."); if (aoSalvar) aoSalvar();
  } });
  modal({ titulo: novo ? "Novo nome" : c.nome, subtitulo: novo ? "Cadastro, etiquetas e histórico" : `Cadastrado em ${data(c.criado_em)}`, conteudo: h("div", null, form, extra), acoes: acoesModal, larga: !novo });
};

registrarTela("names", {
  titulo: "Nomes", sub: "Cadastro, etiquetas e histórico de quem fala com a empresa.", icone: "◎",
  async render(el, { acoes }) {
    const busca = entrada("busca", "", { type: "search", placeholder: "Nome, telefone, e-mail ou etiqueta…" });
    const area = h("div");
    const recarregar = async () => {
      const itens = await api("/api/contatos?busca=" + encodeURIComponent(busca.value.trim()));
      limpar(area).append(tabela([
        { titulo: "Nome", valor: (c) => c.nome },
        { titulo: "Telefone", valor: (c) => telefone(c.whatsapp || c.telefone) },
        { titulo: "Etiquetas", valor: (c) => (c.tags || []).join(" • ") || "—" },
        { titulo: "Último contato", valor: (c) => relativo(c.ultimo_contato) },
        { titulo: "Status", valor: (c) => selo(c.status) },
      ], itens, (c) => App.abrirContato(c.id, recarregar)));
    };
    let atraso; busca.addEventListener("input", () => { clearTimeout(atraso); atraso = setTimeout(recarregar, 300); });
    if (pode("contatos", "criar")) acoes.append(h("button", { class: "btn primario", type: "button", text: "+ Novo nome", on: { click: () => App.abrirContato(null, recarregar) } }));
    el.append(h("div", { class: "cartao" }, h("div", { class: "linha-titulo" }, h("div", { class: "busca", style: { flex: 1 } }, busca)), area));
    await recarregar();
  },
});

/* ================================================================ FILAS & EQUIPES */
registrarTela("queues", {
  titulo: "Filas & Equipes", sub: "Setores, prazos de resposta (SLA) e quem está online.", icone: "≡",
  async render(el, { acoes }) {
    const [filas, equipe] = await Promise.all([api("/api/filas"), api("/api/equipe")]);
    const editar = (f) => {
      const form = h("div", { class: "formulario" },
        campo("Nome da fila", entrada("nome", f ? f.nome : "", { placeholder: "Comercial" })),
        campo("SLA de primeira resposta (minutos)", entrada("sla_minutos", f ? f.sla_minutos : 15, { type: "number", min: 1 })),
        marcador("ativa", f ? f.ativa : true, "Fila ativa"));
      modal({ titulo: f ? "Editar fila" : "Nova fila", conteudo: form, acoes: [{ texto: "Cancelar" }, { texto: "Salvar", classe: "primario", acao: async () => {
        await api(f ? "/api/filas/" + f.id : "/api/filas", { metodo: f ? "PUT" : "POST", dados: lerFormulario(form) }); toast("Fila salva."); mostrarTela();
      } }] });
    };
    if (pode("filas", "criar")) acoes.append(h("button", { class: "btn primario", type: "button", text: "+ Nova fila", on: { click: () => editar(null) } }));
    el.append(h("div", { class: "grade colunas" },
      h("div", { class: "cartao" }, h("h2", { text: "Filas" }),
        filas.length ? filas.map((f) => h("div", { class: "item" + (pode("filas", "editar") ? " clicavel" : ""), on: pode("filas", "editar") ? { click: () => editar(f) } : null },
          h("div", null, h("b", { text: f.nome }), " ", f.ativa ? null : selo("inativo"), h("div", { class: "suave", text: `${f.aguardando} aguardando • ${f.em_atendimento} em atendimento • SLA ${f.sla_minutos} min` })),
          h("span", { class: "selo s-azul", text: `${f.agentes} agente${f.agentes === 1 ? "" : "s"} • ${f.online} online` }))) : h("div", { class: "vazio", text: "Nenhuma fila." })),
      h("div", { class: "cartao" }, h("h2", { text: "Equipe" }),
        equipe.length ? equipe.map((u) => h("div", { class: "item" }, h("div", null, h("b", { text: u.nome }), h("div", { class: "suave", text: `${u.fila_nome || "sem fila"} • ${u.em_atendimento} em atendimento` })), selo(u.presenca))) : h("div", { class: "vazio", text: "Cadastre a equipe em Usuários & Permissões." }))));
  },
});
