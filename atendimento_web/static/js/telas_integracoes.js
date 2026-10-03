/* Integrações: WhatsApp, API & Webhooks, Alertas — e Relatórios */
"use strict";

function copiavel(texto) {
  return h("div", { class: "busca" }, h("code", { text: texto, style: { flex: 1 } }),
    h("button", { class: "btn pequeno", type: "button", text: "Copiar", on: { click: () => navigator.clipboard.writeText(texto).then(() => toast("Copiado.")) } }));
}

/* ================================================================ WHATSAPP */
registrarTela("whatsapp", {
  titulo: "WhatsApp", sub: "WhatsApp oficial da Meta (Cloud API): receber, responder e acompanhar entregas.", icone: "◌",
  async render(el, { acoes }) {
    const d = await api("/api/whatsapp");
    const enderecoWebhook = location.origin + d.endereco_webhook;
    const editar = (c) => {
      const form = h("div", { class: "formulario" },
        campo("Nome do canal", entrada("nome", c ? c.nome : "WhatsApp principal")),
        campo("Número (como aparece para o cliente)", entrada("numero_exibicao", c ? c.numero_exibicao || "" : "", { placeholder: "+55 79 99999-0000" })),
        campo("Phone number ID", entrada("phone_number_id", c ? c.phone_number_id : "", { inputmode: "numeric" }), "Meta for Developers → seu app → WhatsApp → Configuração da API."),
        campo("WhatsApp Business Account ID (opcional)", entrada("waba_id", c ? c.waba_id || "" : "")),
        campo("Token de acesso (access token)", entrada("access_token", "", { type: "password", autocomplete: "off", placeholder: c ? "deixe vazio para manter " + (c.access_token || "") : "" }), "Use um token permanente (usuário do sistema), não o temporário de 24 h.", true),
        campo("App Secret", entrada("app_secret", "", { type: "password", autocomplete: "off", placeholder: c ? "deixe vazio para manter" : "" }), "Configurações do app → Básico → Chave secreta do aplicativo. Serve para conferir que a mensagem veio mesmo da Meta."),
        campo("Versão da API", entrada("versao_api", c ? c.versao_api : "v21.0")),
        marcador("ativo", c ? c.ativo : true, "Canal ativo"));
      modal({ titulo: c ? "Editar canal" : "Conectar número do WhatsApp", conteudo: form, larga: true, acoes: [{ texto: "Cancelar" }, { texto: "Salvar", classe: "primario", acao: async () => {
        await api(c ? "/api/whatsapp/canais/" + c.id : "/api/whatsapp/canais", { metodo: c ? "PUT" : "POST", dados: lerFormulario(form) }); toast("Canal salvo."); mostrarTela();
      } }] });
    };
    const testar = (c) => {
      const form = h("div", { class: "formulario" },
        campo("Número de destino (com DDD)", entrada("numero", "", { inputmode: "tel" }), "No modo de teste da Meta, o número precisa estar na lista de destinatários de teste."),
        campo("Texto (opcional)", entrada("texto", ""), "Vazio = envia o modelo oficial 'hello_world' da Meta (funciona fora da janela de 24 h)."));
      modal({ titulo: "Testar mensagem", conteudo: form, acoes: [{ texto: "Cancelar" }, { texto: "Enviar teste", classe: "primario", acao: async () => {
        const r = await api(`/api/whatsapp/canais/${c.id}/testar`, { dados: lerFormulario(form) });
        if (r.ok) toast("A Meta aceitou a mensagem. ID: " + r.id_meta); else throw new Error("A Meta recusou: " + r.erro);
      } }] });
    };
    if (pode("whatsapp", "configurar")) acoes.append(h("button", { class: "btn primario", type: "button", text: "+ Conectar número", on: { click: () => editar(null) } }));
    const hoje = d.hoje;
    el.append(h("div", { class: "grade estatisticas" },
      cartaoNumero("Recebidas hoje", hoje.recebidas || 0), cartaoNumero("Enviadas hoje", hoje.enviadas || 0),
      cartaoNumero("Entregues", (hoje.delivered || 0) + (hoje.lidas || 0)), cartaoNumero("Lidas", hoje.lidas || 0),
      cartaoNumero("Falhas", hoje.falhas || 0, hoje.falhas ? "veja em Alertas" : null, hoje.falhas ? "ruim" : "")));
    el.append(h("div", { class: "grade colunas" },
      h("div", { class: "cartao" }, h("h2", { text: "Números conectados" }),
        d.canais.length ? d.canais.map((c) => h("div", { class: "item" },
          h("div", null, h("b", { text: `${c.nome} ${c.numero_exibicao ? "• " + c.numero_exibicao : ""}` }),
            h("div", { class: "suave", text: `Phone number ID ${c.phone_number_id} • token ${c.access_token || "—"} • ${c.ultimo_evento_em ? "último evento " + relativo(c.ultimo_evento_em) : "nenhum evento recebido ainda"}` })),
          h("div", { class: "acoes" }, selo(c.ativo ? "ativo" : "inativo"),
            h("button", { class: "btn pequeno", type: "button", text: "Testar", on: { click: () => testar(c) } }),
            h("button", { class: "btn pequeno", type: "button", text: "Editar", on: { click: () => editar(c) } })))) :
          h("div", { class: "vazio", text: "Nenhum número conectado. Clique em “Conectar número” e use os dados da sua conta Meta." }),
        d.canais.length ? h("div", null, h("h3", { text: "Configure o webhook na Meta" }),
          campo("URL de callback", copiavel(enderecoWebhook), "A Meta precisa alcançar este endereço pela internet com HTTPS (veja ao lado)."),
          d.canais.map((c) => campo(`Token de verificação (${c.nome})`, copiavel(c.verify_token))),
          h("p", { class: "suave", text: "Na Meta: WhatsApp → Configuração → Webhook → Editar. Cole a URL e o token, clique em Verificar e salvar, e assine o campo “messages”." })) : null),
      h("div", { class: "cartao" }, h("h2", { text: "Como funciona" }),
        h("div", { class: "aviso info", text: "Para receber mensagens, a Meta precisa chegar até este servidor por um endereço público com HTTPS. No computador do ALFA isso é feito com um túnel (ex.: Cloudflare Tunnel) ou publicando o RMD Atendimento num servidor. Enviar mensagens funciona direto." }),
        h("h3", { text: "Mensagens interativas" }), h("p", { class: "suave", text: "Nos Fluxos, perguntas com até 3 opções viram botões; até 10 viram lista. A opção escolhida volta para o robô." }),
        h("h3", { text: "Janela de 24 horas" }), h("p", { class: "suave", text: "A Meta só permite mensagem livre até 24 h depois da última mensagem do cliente. Fora disso, é preciso um modelo aprovado — o sistema avisa quando a Meta recusar." }),
        h("h3", { text: "Status de entrega" }), h("p", { class: "suave", text: "enviado → entregue → lido, ou falhou (vira alerta)." }))));
  },
});

/* ================================================================ API & WEBHOOKS */
registrarTela("api", {
  titulo: "API & Webhooks", sub: "Integração com outros sistemas (ERP, CRM, site).", icone: "⌁",
  async render(el) {
    const d = await api("/api/integracoes");
    const nomesEscopo = Object.fromEntries(d.escopos.map((e) => [e.id, e.nome]));
    const novaChave = () => {
      const form = h("div", null, campo("Nome da chave", entrada("nome", "", { placeholder: "Integração ERP" })),
        h("h3", { text: "Permissões" }), d.escopos.map((e) => marcador("escopo_" + e.id, e.id.endsWith(":read"), `${e.id} — ${e.nome}`)),
        marcador("dry_run", true, "Modo teste (dry-run): simula e responde o que faria, sem gravar nem enviar nada"));
      modal({ titulo: "Nova chave de API", conteudo: form, acoes: [{ texto: "Cancelar" }, { texto: "Criar chave", classe: "primario", acao: async () => {
        const f = lerFormulario(form);
        const r = await api("/api/integracoes/chaves", { dados: { nome: f.nome, dry_run: f.dry_run, escopos: d.escopos.map((e) => e.id).filter((id) => f["escopo_" + id]) } });
        mostrarSegredo("Chave criada", "Chave de API", r.chave, r.aviso); mostrarTela();
      } }] });
    };
    const novoWebhook = () => {
      const form = h("div", null, campo("Endereço (HTTPS)", entrada("url", "", { placeholder: "https://seu-sistema.com/webhook" })),
        h("h3", { text: "Eventos" }), d.eventos.map((e) => marcador("ev_" + e, true, e)), marcador("assinar", true, "Assinar cada envio com HMAC (recomendado)"));
      modal({ titulo: "Novo webhook de saída", conteudo: form, acoes: [{ texto: "Cancelar" }, { texto: "Cadastrar", classe: "primario", acao: async () => {
        const f = lerFormulario(form);
        const r = await api("/api/integracoes/webhooks", { dados: { url: f.url, assinar: f.assinar, eventos: d.eventos.filter((e) => f["ev_" + e]) } });
        if (r.segredo) mostrarSegredo("Webhook cadastrado", "Segredo HMAC", r.segredo, r.aviso); else toast("Webhook cadastrado.");
        mostrarTela();
      } }] });
    };
    const alterar = async (url, dados) => { try { await api(url, { metodo: "PUT", dados }); toast("Atualizado."); mostrarTela(); } catch (e) { falha(e); } };
    const exemplo = `curl -H "Authorization: Bearer SUA_CHAVE" ${location.origin}/api/v1/nomes\n\ncurl -X POST -H "Authorization: Bearer SUA_CHAVE" -H "Content-Type: application/json" \\\n  -d '{"telefone":"79999991111","texto":"Olá!"}' ${location.origin}/api/v1/mensagens`;
    el.append(h("div", { class: "grade colunas" },
      h("div", { class: "cartao" }, h("div", { class: "linha-titulo" }, h("h2", { text: "API pública V1" }), h("button", { class: "btn primario", type: "button", text: "+ Nova chave", on: { click: novaChave } })),
        d.chaves.length ? d.chaves.map((k) => h("div", { class: "item" },
          h("div", null, h("b", { text: k.nome }), h("div", { class: "suave", text: `${k.prefixo}… • ${k.escopos.map((e) => nomesEscopo[e] || e).join(", ")} • ${k.ultimo_uso ? "usada " + relativo(k.ultimo_uso) : "nunca usada"}` })),
          h("div", { class: "acoes" }, k.dry_run ? h("span", { class: "selo s-laranja", text: "Dry-run" }) : h("span", { class: "selo s-verde", text: "Produção" }), selo(k.ativa ? "ativo" : "inativo"),
            h("button", { class: "btn pequeno", type: "button", text: k.dry_run ? "Liberar produção" : "Voltar a dry-run", on: { click: () => alterar("/api/integracoes/chaves/" + k.id, { dry_run: !k.dry_run }) } }),
            h("button", { class: "btn pequeno perigo", type: "button", text: k.ativa ? "Desativar" : "Ativar", on: { click: () => alterar("/api/integracoes/chaves/" + k.id, { ativa: !k.ativa }) } })))) : h("div", { class: "vazio", text: "Nenhuma chave criada." }),
        h("h3", { text: "Exemplo" }), h("pre", { class: "mono", text: exemplo }),
        h("p", { class: "suave", text: "Endpoints: GET /api/v1/nomes (names:read) • POST /api/v1/nomes (names:write) • POST /api/v1/mensagens (messages:write) • GET /api/v1/atendimentos (conversations:read). Limite: 60 chamadas por minuto." })),
      h("div", { class: "cartao" }, h("div", { class: "linha-titulo" }, h("h2", { text: "Webhooks de saída" }), h("button", { class: "btn", type: "button", text: "Cadastrar webhook", on: { click: novoWebhook } })),
        h("p", { class: "suave", text: "HTTPS obrigatório, HMAC opcional, destinos locais bloqueados e auditoria de cada entrega." }),
        d.webhooks.length ? d.webhooks.map((w) => h("div", { class: "etapa" },
          h("div", { class: "cab" }, h("b", { text: w.url, style: { wordBreak: "break-all" } }), h("span", { style: { marginLeft: "auto" } }), selo(w.ativo ? "ativo" : "inativo")),
          h("div", { class: "suave", text: `Eventos: ${w.eventos.join(", ")} • ${w.assinado ? "assinado (HMAC)" : "sem assinatura"}` }),
          h("div", { class: "acoes", style: { margin: "8px 0" } },
            h("button", { class: "btn pequeno", type: "button", text: "Enviar teste", on: { click: async () => { try { const r = await api(`/api/integracoes/webhooks/${w.id}/testar`, { dados: {} }); r.ok ? toast("Entregue (HTTP " + r.codigo_http + ").") : falha(new Error(r.erro)); mostrarTela(); } catch (e) { falha(e); } } } }),
            h("button", { class: "btn pequeno perigo", type: "button", text: w.ativo ? "Desativar" : "Ativar", on: { click: () => alterar("/api/integracoes/webhooks/" + w.id, { ativo: !w.ativo }) } })),
          w.entregas.length ? tabela([{ titulo: "Evento", valor: (e) => e.evento }, { titulo: "Resultado", valor: (e) => selo(e.ok ? "ativo" : "cancelado", e.ok ? "OK " + (e.codigo_http || "") : "Falhou") },
            { titulo: "Detalhe", valor: (e) => e.erro || "—" }, { titulo: "Quando", valor: (e) => relativo(e.criada_em) }], w.entregas) : h("div", { class: "suave", text: "Nenhuma entrega ainda." }))) :
          h("div", { class: "vazio", text: "Nenhum webhook cadastrado." }))));
  },
});

/* ================================================================ ALERTAS */
registrarTela("alerts", {
  titulo: "Central de alertas", sub: "Operação, SLA, WhatsApp, plano e backup.", icone: "⚠",
  async render(el, { acoes }) {
    const d = await api("/api/alertas");
    acoes.append(h("button", { class: "btn", type: "button", text: "Marcar todos como lidos", disabled: !d.nao_lidos, on: { click: async () => { await api("/api/alertas/lidos", { dados: {} }); toast("Tudo marcado como lido."); atualizarContadores(); mostrarTela(); } } }));
    const destino = { sla: "chat", whatsapp: "chat", orcamento: "quotes", agenda: "agenda", quota: "plan", backup: "backup" };
    el.append(h("div", { class: "cartao" }, d.itens.length ? d.itens.map((a) => h("div", { class: "item clicavel", style: { opacity: a.lido ? 0.6 : 1 }, on: { click: async () => {
      if (!a.lido) { await api(`/api/alertas/${a.id}/lido`, { dados: {} }); atualizarContadores(); }
      const tela = destino[a.tipo]; if (tela) navegar(tela, tela === "chat" ? a.referencia : null);
    } } }, h("div", null, h("b", { text: a.titulo }), h("div", { class: "suave", text: `${a.texto} • ${relativo(a.criado_em)}` })), selo(a.nivel))) :
      h("div", { class: "vazio", text: "Nenhum alerta. Tudo em ordem." })));
  },
});

/* ================================================================ RELATÓRIOS */
registrarTela("reports", {
  titulo: "Relatórios", sub: "Desempenho da equipe, canais, orçamentos e satisfação.", icone: "▤",
  async render(el, { acoes, parametro }) {
    const dias = Number(parametro) || 30;
    const periodo = seletor("dias", [["1", "Hoje"], ["7", "Últimos 7 dias"], ["30", "Últimos 30 dias"], ["90", "Últimos 90 dias"], ["365", "Último ano"]], String(dias));
    periodo.addEventListener("change", () => navegar("reports", periodo.value));
    acoes.append(h("div", { style: { width: "200px" } }, periodo));
    const r = await api("/api/relatorios?dias=" + dias);
    const k = r.kpis;
    el.append(h("div", { class: "grade estatisticas" },
      cartaoNumero("Resolvidos", k.resolvidos, `${k.atendimentos} atendimentos no período`, "neutra"),
      cartaoNumero("Conversão de orçamentos", k.conversao === null ? "—" : k.conversao + "%", "aprovados ÷ enviados", "neutra"),
      cartaoNumero("Satisfação", k.csat === null ? "—" : String(k.csat).replace(".", ",") + "/5", null),
      cartaoNumero("Tempo médio 1ª resposta", k.tempo_primeira_resposta, "minutos:segundos", "neutra"),
      cartaoNumero("Mensagens", k.mensagens.toLocaleString("pt-BR"))));
    const exportar = (tipo) => h("a", { class: "btn pequeno", href: `/api/relatorios/${tipo}.csv?dias=${dias}`, download: "", text: "⬇ CSV" });
    const maxCsat = Math.max(1, ...r.csat.map((c) => c.quantidade));
    el.append(h("div", { class: "grade duas" },
      h("div", { class: "cartao" }, h("div", { class: "linha-titulo" }, h("h2", { text: "Desempenho da equipe" }), exportar("equipe")),
        tabela([{ titulo: "Atendente", valor: (x) => x.nome }, { titulo: "Atendimentos", valor: (x) => x.atendimentos, num: true }, { titulo: "Resolvidos", valor: (x) => x.resolvidos, num: true },
          { titulo: "1ª resposta", valor: (x) => x.tempo_primeira_resposta, num: true }, { titulo: "CSAT", valor: (x) => (x.csat ? String(x.csat).replace(".", ",") : "—"), num: true }], r.equipe)),
      h("div", { class: "cartao" }, h("div", { class: "linha-titulo" }, h("h2", { text: "Atendimento por canal" }), exportar("canais")),
        tabela([{ titulo: "Canal", valor: (x) => CANAIS[x.canal] || x.canal }, { titulo: "Atendimentos", valor: (x) => x.atendimentos, num: true }, { titulo: "Resolvidos", valor: (x) => x.resolvidos, num: true }], r.canais)),
      h("div", { class: "cartao" }, h("div", { class: "linha-titulo" }, h("h2", { text: "Orçamentos e conversão" }), exportar("orcamentos")),
        tabela([{ titulo: "Situação", valor: (x) => selo(x.status) }, { titulo: "Quantidade", valor: (x) => x.quantidade, num: true }, { titulo: "Valor", valor: (x) => moeda(x.valor), num: true }], r.orcamentos)),
      h("div", { class: "cartao" }, h("div", { class: "linha-titulo" }, h("h2", { text: "Satisfação (CSAT)" }), exportar("csat")),
        h("div", { class: "barras" }, r.csat.map((c) => h("div", { class: "linha-barra" }, h("span", { text: "★".repeat(c.nota) }),
          h("div", { class: "barra" }, h("span", { style: { width: `${Math.round(100 * c.quantidade / maxCsat)}%` } })), h("span", { class: "suave", text: String(c.quantidade) })))))));
  },
});
