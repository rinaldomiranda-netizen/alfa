/* Gestão: Orçamentos, Serviços & Preços, Fluxos, Agenda */
"use strict";

/* ================================================================ ORÇAMENTOS */
function paraCentavos(texto) {
  if (texto === "" || texto === null || texto === undefined) return 0;
  let t = String(texto).replace(/R\$\s?/g, "").trim();
  if (t.includes(",")) t = t.replace(/\./g, "").replace(",", ".");
  const n = Number(t);
  return Number.isFinite(n) ? Math.round(n * 100) : NaN;
}
function reais(centavos) { return ((centavos || 0) / 100).toFixed(2).replace(".", ","); }

App.editarOrcamento = async function editarOrcamento(id, inicial = {}, aoSalvar) {
  const [contatos, servicos] = await Promise.all([api("/api/contatos"), api("/api/servicos?ativos=1")]);
  if (!contatos.length) { toast("Cadastre um nome primeiro (menu Nomes).", "erro"); return; }
  const o = id ? await api("/api/orcamentos/" + id) : {
    contato_id: inicial.contato_id || contatos[0].id, conversa_id: inicial.conversa_id || null, descricao: "", itens: [],
    validade: new Date(Date.now() + 7 * 86400000).toISOString().slice(0, 10), desconto_centavos: 0, status: "rascunho",
  };
  const bloqueado = o.status === "aprovado";
  const contato = seletor("contato_id", contatos.map((c) => [c.id, c.nome]), o.contato_id, { disabled: bloqueado });
  const telefoneInfo = h("input", { readonly: true, tabindex: -1 });
  const mostrarTelefone = () => { const c = contatos.find((x) => x.id === contato.value); telefoneInfo.value = c ? telefone(c.whatsapp || c.telefone) : ""; };
  contato.addEventListener("change", mostrarTelefone); mostrarTelefone();
  const itens = h("div");
  const totalEl = h("b", { class: "valor", style: { fontSize: "22px" } });
  const desconto = entrada("desconto", reais(o.desconto_centavos), { inputmode: "decimal", disabled: bloqueado });
  const opcoesServico = [["", "— item livre —"], ...servicos.map((s) => [s.id, `${s.nome} (${moeda(s.preco_centavos)})`])];
  const linhaItem = (it = {}) => {
    const serv = seletor("servico_id", opcoesServico, it.servico_id || "", { disabled: bloqueado });
    const desc = entrada("descricao", it.descricao || "", { placeholder: "Descrição", disabled: bloqueado });
    const qtd = entrada("quantidade", it.quantidade ?? 1, { inputmode: "decimal", disabled: bloqueado });
    const valor = entrada("valor_unit", it.valor_unit_centavos !== undefined ? reais(it.valor_unit_centavos) : "", { inputmode: "decimal", placeholder: "0,00", disabled: bloqueado });
    serv.addEventListener("change", () => { const s = servicos.find((x) => x.id === serv.value); if (s) { desc.value = s.nome; valor.value = reais(s.preco_centavos); } recalcular(); });
    [qtd, valor].forEach((e) => e.addEventListener("input", recalcular));
    const linha = h("div", { class: "formulario item-orc", style: { gridTemplateColumns: "1.3fr 1.5fr .6fr .8fr auto", alignItems: "end", marginBottom: "6px" } },
      campo("Serviço", serv), campo("Descrição", desc), campo("Qtd.", qtd), campo("Valor unit. (R$)", valor),
      bloqueado ? h("span") : h("button", { class: "btn pequeno perigo", type: "button", title: "Remover item", text: "✕", on: { click: () => { linha.remove(); recalcular(); } } }));
    itens.append(linha);
  };
  function lerItens() {
    return [...itens.querySelectorAll(".item-orc")].map((l) => {
      const d = lerFormulario(l);
      return { servico_id: d.servico_id || null, descricao: d.descricao, quantidade: d.quantidade, valor_unit: d.valor_unit };
    });
  }
  function recalcular() {
    const subtotal = lerItens().reduce((s, i) => s + Math.round(Number(String(i.quantidade).replace(",", ".")) * paraCentavos(i.valor_unit)), 0);
    const d = paraCentavos(desconto.value);
    totalEl.textContent = Number.isFinite(subtotal - d) ? moeda(subtotal - d) : "—";
  }
  desconto.addEventListener("input", recalcular);
  (o.itens.length ? o.itens : [{}]).forEach(linhaItem);
  recalcular();
  const form = h("div", { class: "formulario" },
    campo("Nome (cliente)", contato), campo("Telefone", telefoneInfo),
    campo("Validade", entrada("validade", o.validade, { type: "date", disabled: bloqueado })), campo("Situação", h("div", null, selo(o.status))),
    campo("Descrição", areaTexto("descricao", o.descricao || "", { disabled: bloqueado }), null, true));
  const conteudo = h("div", null, form, h("h3", { text: "Itens" }), itens,
    bloqueado ? null : h("button", { class: "btn pequeno", type: "button", text: "+ Adicionar item", on: { click: () => { linhaItem(); recalcular(); } } }),
    h("div", { class: "formulario", style: { marginTop: "12px", alignItems: "end" } }, campo("Desconto (R$)", desconto), campo("Total", totalEl)));
  const salvar = async () => {
    const dados = { ...lerFormulario(form), contato_id: contato.value, conversa_id: o.conversa_id, itens: lerItens(), desconto: desconto.value };
    const r = await api(id ? "/api/orcamentos/" + id : "/api/orcamentos", { metodo: id ? "PUT" : "POST", dados });
    id = r.id; return r;
  };
  const acoes = [{ texto: "Fechar" }];
  if (!bloqueado) acoes.push({ texto: "💾 Salvar", fecha: false, acao: async () => { await salvar(); toast("Orçamento salvo."); if (aoSalvar) aoSalvar(); } });
  acoes.push({ texto: "📄 Gerar PDF", fecha: false, acao: async () => { if (!bloqueado) await salvar(); window.open(`/orcamentos/${id}/imprimir`, "_blank", "noopener"); } });
  if (!["aprovado", "recusado"].includes(o.status)) acoes.push({ texto: "Enviar pelo WhatsApp", classe: "primario", acao: async () => {
    await salvar();
    const r = await api(`/api/orcamentos/${id}/enviar`, { dados: {} });
    if (r.link) { window.open(r.link, "_blank", "noopener"); toast("WhatsApp aberto com o orçamento. Configure o WhatsApp oficial para enviar direto pelo sistema."); }
    else toast("Orçamento enviado pelo WhatsApp.");
    if (aoSalvar) aoSalvar();
  } });
  modal({ titulo: id ? `Orçamento ORC-${o.numero}` : "Novo orçamento", subtitulo: "Os valores são conferidos e calculados pelo servidor.", conteudo, acoes, larga: true });
};

registrarTela("quotes", {
  titulo: "Orçamentos", sub: "Propostas, envio e negociação.", icone: "▣",
  async render(el, { acoes }) {
    const filtro = seletor("status", [["", "Todas as situações"], ["rascunho", "Rascunho"], ["enviado", "Enviado"], ["em_analise", "Em análise"], ["aprovado", "Aprovado"], ["recusado", "Recusado"], ["vencido", "Vencido"]], "");
    const area = h("div");
    const recarregar = async () => {
      const itens = await api("/api/orcamentos?status=" + filtro.value);
      limpar(area).append(tabela([
        { titulo: "Nº", valor: (o) => "ORC-" + o.numero },
        { titulo: "Nome", valor: (o) => o.contato_nome },
        { titulo: "Serviço", valor: (o) => o.servicos || "—" },
        { titulo: "Total", valor: (o) => moeda(o.total_centavos), num: true },
        { titulo: "Validade", valor: (o) => data(o.validade) },
        { titulo: "Status", valor: (o) => selo(o.status) },
        { titulo: "", valor: (o) => acoesStatus(o) },
      ], itens, (o) => App.editarOrcamento(o.id, {}, recarregar)));
    };
    const acoesStatus = (o) => {
      const caixa = h("div", { class: "acoes", on: { click: (e) => e.stopPropagation() } });
      const muda = (status, texto) => caixa.append(h("button", { class: "btn pequeno", type: "button", text: texto, on: { click: async () => { try { await api(`/api/orcamentos/${o.id}/status`, { dados: { status } }); toast("Situação atualizada."); recarregar(); } catch (e) { falha(e); } } } }));
      if (o.status === "enviado") { muda("em_analise", "Em análise"); muda("aprovado", "Aprovado"); muda("recusado", "Recusado"); }
      if (o.status === "em_analise") { muda("aprovado", "Aprovado"); muda("recusado", "Recusado"); }
      if (["vencido", "recusado"].includes(o.status)) muda("rascunho", "Reabrir");
      return caixa;
    };
    filtro.addEventListener("change", recarregar);
    App.aposOrcamento = recarregar;
    if (pode("orcamentos", "criar")) acoes.append(h("button", { class: "btn primario", type: "button", text: "+ Novo orçamento", on: { click: () => App.editarOrcamento(null, {}, recarregar) } }));
    el.append(h("div", { class: "cartao" }, h("div", { class: "linha-titulo" }, h("div", { style: { width: "240px" } }, filtro)), area));
    await recarregar();
  },
});

/* ================================================================ SERVIÇOS */
registrarTela("services", {
  titulo: "Serviços & Preços", sub: "Catálogo comercial usado nos orçamentos.", icone: "◆",
  async render(el, { acoes }) {
    const itens = await api("/api/servicos");
    const editar = (s) => {
      const form = h("div", { class: "formulario" },
        campo("Serviço", entrada("nome", s ? s.nome : "")), campo("Categoria", entrada("categoria", s ? s.categoria || "" : "")),
        campo("Preço (R$)", entrada("preco", s ? reais(s.preco_centavos) : "", { inputmode: "decimal", placeholder: "0,00" })),
        campo("Prazo / SLA (horas)", entrada("sla_horas", s && s.sla_horas ? s.sla_horas : "", { type: "number", min: 1 })),
        campo("Descrição", areaTexto("descricao", s ? s.descricao || "" : ""), null, true), marcador("ativo", s ? s.ativo : true, "Ativo (aparece nos orçamentos)"));
      modal({ titulo: s ? "Editar serviço" : "Novo serviço", conteudo: form, acoes: [{ texto: "Cancelar" }, { texto: "Salvar", classe: "primario", acao: async () => {
        await api(s ? "/api/servicos/" + s.id : "/api/servicos", { metodo: s ? "PUT" : "POST", dados: lerFormulario(form) }); toast("Serviço salvo."); mostrarTela();
      } }] });
    };
    if (pode("servicos", "criar")) acoes.append(h("button", { class: "btn primario", type: "button", text: "+ Novo serviço", on: { click: () => editar(null) } }));
    el.append(h("div", { class: "cartao" }, tabela([
      { titulo: "Serviço", valor: (s) => s.nome }, { titulo: "Categoria", valor: (s) => s.categoria || "—" },
      { titulo: "Preço", valor: (s) => moeda(s.preco_centavos), num: true }, { titulo: "SLA", valor: (s) => (s.sla_horas ? s.sla_horas + "h" : "—") },
      { titulo: "Status", valor: (s) => selo(s.ativo ? "ativo" : "inativo") },
    ], itens, pode("servicos", "editar") ? editar : null)));
  },
});

/* ================================================================ FLUXOS */
const TIPOS_ETAPA = { mensagem: "Mensagem", pergunta: "Pergunta", memoria: "Memória", tag: "Etiqueta", condicao: "Condição", handoff: "Passar para humano", encerrar: "Encerrar" };

async function editarFluxo(fluxo) {
  const filas = await api("/api/filas");
  const etapas = JSON.parse(JSON.stringify(fluxo ? fluxo.etapas : [{ tipo: "mensagem", texto: "Olá, {{nome}}! Bem-vindo à {{empresa}}." }]));
  const cab = h("div", { class: "formulario" },
    campo("Nome do fluxo", entrada("nome", fluxo ? fluxo.nome : "")),
    campo("Quando começa", seletor("gatilho_tipo", [["sempre", "Sempre que alguém chama"], ["palavra_chave", "Quando a mensagem tem uma palavra-chave"], ["manual", "Manual (não começa sozinho)"]], fluxo ? fluxo.gatilho_tipo : "sempre")),
    campo("Palavra-chave", entrada("gatilho_valor", fluxo ? fluxo.gatilho_valor || "" : "", { placeholder: "orçamento" }), "Só para o gatilho de palavra-chave."));
  const lista = h("div");
  const resultado = h("div", { class: "simulacao" }, h("div", { class: "suave", text: "Escreva as respostas do cliente (uma por linha) e clique em Simular." }));
  const entradas = areaTexto("entradas", "Orçamento", { rows: 3 });
  function desenhar() {
    limpar(lista);
    etapas.forEach((e, i) => {
      const f = (chave, el) => { el.addEventListener("input", () => { e[chave] = el.type === "number" ? (el.value ? Number(el.value) : null) : el.value; }); return el; };
      const corpo = h("div", { class: "formulario" });
      if (["mensagem", "pergunta"].includes(e.tipo)) corpo.append(campo("Texto", f("texto", areaTexto("t", e.texto || "", { rows: 2 })), "Use {{nome}}, {{empresa}} ou {{memória}}.", true));
      if (["pergunta", "memoria", "condicao"].includes(e.tipo)) corpo.append(campo("Guardar em / ler da memória", f("variavel", entrada("v", e.variavel || "", { placeholder: "assunto" }))));
      if (e.tipo === "pergunta") { const op = entrada("o", (e.opcoes || []).join(", "), { placeholder: "Orçamento, Suporte" }); op.addEventListener("input", () => { e.opcoes = op.value.split(",").map((x) => x.trim()).filter(Boolean); }); corpo.append(campo("Opções (separe por vírgula)", op, "Até 3 viram botões no WhatsApp; até 10 viram lista.")); }
      if (e.tipo === "memoria") corpo.append(campo("Valor", f("valor", entrada("va", e.valor || ""))));
      if (e.tipo === "tag") corpo.append(campo("Etiqueta", f("tag", entrada("tg", e.tag || ""))));
      if (e.tipo === "condicao") {
        const op = seletor("op", [["igual", "é igual a"], ["contem", "contém"], ["existe", "foi respondida"]], e.operador || "igual"); op.addEventListener("change", () => { e.operador = op.value; }); e.operador = op.value;
        corpo.append(campo("Condição", op), campo("Valor", f("valor", entrada("cv", e.valor || ""))),
          campo("Se sim, ir para a etapa", f("ir_para", entrada("ip", e.ir_para || "", { type: "number", min: 1 }))),
          campo("Se não, ir para a etapa", f("senao_ir_para", entrada("sp", e.senao_ir_para || "", { type: "number", min: 1 })), "Vazio = segue para a próxima."));
      }
      if (e.tipo === "handoff") {
        const fl = seletor("fila", [["", "— escolha —"], ...filas.map((x) => [x.id, x.nome])], e.fila || ""); fl.addEventListener("change", () => { e.fila = fl.value; });
        corpo.append(campo("Fila de destino", fl), campo("Mensagem antes de passar (opcional)", f("texto", entrada("ht", e.texto || ""))));
      }
      if (e.tipo === "encerrar") corpo.append(campo("Mensagem de encerramento (opcional)", f("texto", entrada("et", e.texto || "")), null, true));
      const mover = (d) => { const j = i + d; if (j < 0 || j >= etapas.length) return; [etapas[i], etapas[j]] = [etapas[j], etapas[i]]; desenhar(); };
      lista.append(h("div", { class: "etapa" }, h("div", { class: "cab" }, h("span", { class: "n", text: String(i + 1) }), h("b", { text: TIPOS_ETAPA[e.tipo] }),
        h("span", { style: { marginLeft: "auto" } }), h("button", { class: "btn pequeno", type: "button", title: "Subir", text: "↑", on: { click: () => mover(-1) } }),
        h("button", { class: "btn pequeno", type: "button", title: "Descer", text: "↓", on: { click: () => mover(1) } }),
        h("button", { class: "btn pequeno perigo", type: "button", title: "Remover", text: "✕", on: { click: () => { etapas.splice(i, 1); desenhar(); } } })), corpo));
    });
  }
  const tipoNovo = seletor("novo", Object.entries(TIPOS_ETAPA), "pergunta");
  desenhar();
  async function simular() {
    const r = await api("/api/fluxos/simular", { dados: { etapas, entradas: entradas.value.split("\n").map((x) => x.trim()).filter(Boolean) } });
    limpar(resultado);
    if (r.erros.length) resultado.append(h("div", { class: "aviso", text: r.erros.join(" ") }));
    r.conversa.forEach((m) => resultado.append(h("div", { class: "msg " + (m.de === "cliente" ? "entrada" : m.de === "robo" ? "robo" : "sistema") }, m.texto,
      m.opcoes && m.opcoes.length ? h("div", { class: "opcoes-msg" }, m.opcoes.map((o) => h("span", { class: "selo s-azul", text: o }))) : null)));
    resultado.append(h("div", { class: "suave", style: { marginTop: "8px" }, text: `Resultado: ${r.final || "—"}` }));
    return r;
  }
  const conteudo = h("div", null, cab, h("h3", { text: "Etapas" }), lista,
    h("div", { class: "acoes" }, h("div", { style: { width: "220px" } }, tipoNovo), h("button", { class: "btn", type: "button", text: "+ Adicionar etapa", on: { click: () => { etapas.push({ tipo: tipoNovo.value }); desenhar(); } } })),
    h("h3", { text: "Simulação segura (nada é enviado a ninguém)" }), h("div", { class: "grade duas" }, campo("Respostas do cliente", entradas), resultado),
    h("button", { class: "btn", type: "button", style: { marginTop: "8px" }, text: "▶ Simular", on: { click: () => simular().catch(falha) } }));
  let id = fluxo ? fluxo.id : null;
  const salvar = async () => { const r = await api(id ? "/api/fluxos/" + id : "/api/fluxos", { metodo: id ? "PUT" : "POST", dados: { ...lerFormulario(cab), etapas } }); id = r.id; return r; };
  const acoes = [{ texto: "Fechar" }, { texto: "Salvar rascunho", fecha: false, acao: async () => { await salvar(); toast("Fluxo salvo."); } }];
  if (pode("fluxos", "publicar")) acoes.push({ texto: "Simular e publicar", classe: "primario", acao: async () => {
    await salvar();
    const r = await api(`/api/fluxos/${id}/simular`, { dados: { entradas: entradas.value.split("\n").map((x) => x.trim()).filter(Boolean) } });
    if (!r.ok) { await simular(); throw new Error("A simulação encontrou problemas: " + r.erros.join(" ")); }
    await api(`/api/fluxos/${id}/publicar`, { dados: { publicar: true } }); toast("Fluxo publicado."); mostrarTela();
  } });
  modal({ titulo: fluxo ? fluxo.nome : "Novo fluxo", subtitulo: "O robô segue as etapas exatamente nesta ordem — sem inventar respostas.", conteudo, acoes, larga: true, aoFechar: () => { if (App.atual === "flows") mostrarTela(); } });
}

registrarTela("flows", {
  titulo: "Fluxos", sub: "Robô de atendimento com etapas fixas e simulação antes de publicar.", icone: "⌘",
  async render(el, { acoes }) {
    const fluxos = await api("/api/fluxos");
    if (pode("fluxos", "criar")) acoes.append(h("button", { class: "btn primario", type: "button", text: "+ Novo fluxo", on: { click: () => editarFluxo(null) } }));
    const GATILHOS = { sempre: "sempre", palavra_chave: "palavra-chave", manual: "manual" };
    el.append(h("div", { class: "grade tres" },
      h("div", { class: "cartao" }, h("h2", { text: "Fluxos" }), fluxos.length ? fluxos.map((f) => h("div", { class: "item clicavel", on: { click: () => editarFluxo(f) } },
        h("div", null, h("b", { text: f.nome }), h("div", { class: "suave", text: `${f.status === "publicado" ? "publicado" : "rascunho"} • ${GATILHOS[f.gatilho_tipo]}${f.gatilho_valor ? ": " + f.gatilho_valor : ""} • ${f.etapas.length} etapas` })),
        f.status === "publicado" ? selo("publicado") : selo("rascunho"))) : h("div", { class: "vazio", text: "Sem fluxos. Sem fluxo publicado, toda conversa vai direto para a fila." })),
      h("div", { class: "cartao" }, h("h2", { text: "Etapas suportadas" }), h("p", { class: "suave", text: "Mensagem • Pergunta • Memória • Etiqueta • Condição • Passar para humano • Encerramento" }),
        h("p", { class: "suave", text: "Quando mais de um fluxo está publicado, vale primeiro o de palavra-chave; depois o de “sempre”." })),
      h("div", { class: "cartao" }, h("h2", { text: "Governança" }), h("p", { class: "suave", text: "Todo fluxo só é publicado depois de uma simulação sem erros. Qualquer mudança volta o fluxo para rascunho." }),
        pode("recepcao", "usar") ? h("div", null, h("h3", { text: "Recepção por roteiro (protocolo ALFA)" }), h("p", { class: "suave", text: "O roteiro de recepção/entrevista que já existia no ALFA continua disponível para totem e balcão." }),
          h("a", { class: "btn", href: "/recepcao", target: "_blank", rel: "noopener", text: "Abrir recepção" })) : null)));
  },
});

/* ================================================================ AGENDA */
registrarTela("agenda", {
  titulo: "Agenda", sub: "Disponibilidade, conflitos de horário e lembretes.", icone: "◷",
  async render(el, { acoes }) {
    const hoje = new Date(); hoje.setHours(0, 0, 0, 0);
    const [itens, contatos, filas, equipe] = await Promise.all([
      api("/api/agenda?de=" + encodeURIComponent(new Date(hoje.getTime() - 86400000).toISOString())),
      api("/api/contatos"), api("/api/filas"), api("/api/equipe")]);
    const editar = (a) => {
      const inicio = a ? new Date(a.inicio) : new Date(Date.now() + 3600000);
      const local = (d) => new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
      const duracao = a ? Math.round((new Date(a.fim) - new Date(a.inicio)) / 60000) : 60;
      const form = h("div", { class: "formulario" },
        campo("Título", entrada("titulo", a ? a.titulo : "", { placeholder: "Visita técnica" })),
        campo("Data e hora", entrada("inicio_local", local(inicio), { type: "datetime-local" })),
        campo("Duração (minutos)", entrada("duracao_minutos", duracao, { type: "number", min: 5 })),
        campo("Status", seletor("status", [["agendado", "Agendado"], ["confirmado", "Confirmado"], ["aguardando", "Aguardando"], ["concluido", "Concluído"], ["cancelado", "Cancelado"]], a ? a.status : "agendado")),
        campo("Nome", seletor("contato_id", [["", "—"], ...contatos.map((c) => [c.id, c.nome])], a ? a.contato_id || "" : "")),
        campo("Equipe", seletor("fila_id", [["", "—"], ...filas.map((f) => [f.id, f.nome])], a ? a.fila_id || "" : "")),
        campo("Responsável", seletor("responsavel_id", [["", "—"], ...equipe.map((u) => [u.id, u.nome])], a ? a.responsavel_id || "" : ""), "Usado para avisar conflito de horário."),
        campo("Lembrete (minutos antes)", entrada("lembrete_minutos", a ? a.lembrete_minutos : 60, { type: "number", min: 0 })),
        campo("Observação", areaTexto("observacao", a ? a.observacao || "" : ""), null, true));
      const enviar = async (forcar) => {
        const d = lerFormulario(form);
        d.inicio = new Date(d.inicio_local).toISOString(); d.fim = new Date(new Date(d.inicio_local).getTime() + Number(d.duracao_minutos || 60) * 60000).toISOString();
        delete d.inicio_local; d.forcar = forcar;
        return api(a ? "/api/agenda/" + a.id : "/api/agenda", { metodo: a ? "PUT" : "POST", dados: d });
      };
      modal({ titulo: a ? "Editar agendamento" : "Novo agendamento", conteudo: form, acoes: [{ texto: "Cancelar" }, { texto: "Salvar", classe: "primario", acao: async () => {
        try { await enviar(false); }
        catch (e) { if (e.status !== 409) throw e; if (!(await confirmar(e.message, "Agendar mesmo assim"))) return false; await enviar(true); }
        toast("Agendamento salvo."); mostrarTela();
      } }] });
    };
    if (pode("agenda", "criar")) acoes.append(h("button", { class: "btn primario", type: "button", text: "+ Novo agendamento", on: { click: () => editar(null) } }));
    const porDia = {};
    itens.forEach((a) => { const d = new Date(a.inicio).toLocaleDateString("pt-BR", { timeZone: fuso(), weekday: "long", day: "2-digit", month: "2-digit" }); (porDia[d] = porDia[d] || []).push(a); });
    const cartao = h("div", { class: "cartao" });
    if (!itens.length) cartao.append(h("div", { class: "vazio", text: "Nenhum agendamento a partir de ontem." }));
    Object.entries(porDia).forEach(([dia, lista]) => {
      cartao.append(h("h3", { text: dia.charAt(0).toUpperCase() + dia.slice(1) }), tabela([
        { titulo: "Horário", valor: (a) => `${hora(a.inicio)}–${hora(a.fim)}` }, { titulo: "Título", valor: (a) => a.titulo },
        { titulo: "Nome", valor: (a) => a.contato_nome || "—" }, { titulo: "Equipe", valor: (a) => a.fila_nome || "—" },
        { titulo: "Responsável", valor: (a) => a.responsavel_nome || "—" }, { titulo: "Status", valor: (a) => selo(a.status) },
        { titulo: "Observação", valor: (a) => a.observacao || "—" },
      ], lista, pode("agenda", "editar") ? editar : null));
    });
    el.append(cartao);
  },
});
