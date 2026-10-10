/* Central de Pesquisas — modernização (10/10/2026)
 * - funciona sem internet: entrevistas ficam guardadas no aparelho e são enviadas sozinhas quando a internet volta
 * - registra onde (GPS, se a pessoa permitir) e quando (hora do aparelho) a entrevista foi feita
 * - exportar resultados para Excel
 * - gráficos por região, congregação, intenção e dia
 * - lixeira (excluir não apaga na hora; volta em até 30 dias)
 * - troca obrigatória do código inicial no primeiro acesso
 * - instalar como aplicativo no celular
 */
const CP_VERSAO = "2026.10.10";
const CP_CODIGO_INICIAL = "1234";
const CP_FILA = "cp_fila_entrevistas";
const CP_INTENCOES = { yes: "Votaria no candidato", no: "Não votaria", other: "Outro", undecided: "Indeciso" };
const CP_CORES = { yes: "#16a34a", no: "#dc2626", other: "#f59e0b", undecided: "#64748b" };

/* ---------------- utilidades ---------------- */
function cpLer(k, padrao) { try { const v = localStorage.getItem(k); return v ? JSON.parse(v) : padrao; } catch (e) { return padrao; } }
function cpGravar(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); return true; } catch (e) { return false; } }
function cpNovoId() {
  if (window.crypto?.randomUUID) return crypto.randomUUID();
  return "10000000-1000-4000-8000-100000000000".replace(/[018]/g, c => (c ^ (crypto.getRandomValues(new Uint8Array(1))[0] & (15 >> (c / 4)))).toString(16));
}
function cpEhGestor() { return ["admin", "coordinator"].includes(String(state.profile?.role || "").toLowerCase()); }
function cpEhErroDeRede(e) {
  const m = String(e?.message || e || "");
  return !navigator.onLine || e instanceof TypeError || /Failed to fetch|NetworkError|Load failed|network|fetch/i.test(m);
}
async function cpErroFuncao(error) {
  try { const j = await error?.context?.json?.(); if (j?.error) return j.error; } catch (e) { /* sem corpo */ }
  if (cpEhErroDeRede(error)) return "Sem internet no momento. Tente de novo quando a conexão voltar.";
  return error?.message || "Não foi possível concluir.";
}
async function cpFuncao(body) {
  const { data, error } = await sb.functions.invoke("admin-users", { body });
  if (error) throw new Error(await cpErroFuncao(error));
  if (!data?.success) throw new Error(data?.error || "Não foi possível concluir.");
  return data;
}
function cpDataHora(v) { if (!v) return ""; const d = new Date(v); return isNaN(d) ? "" : d.toLocaleString("pt-BR"); }

/* ---------------- onde e quando ---------------- */
function cpLocalizacao() {
  return new Promise(resolve => {
    if (!navigator.geolocation) return resolve({ latitude: null, longitude: null, precisao: null, status: "indisponivel" });
    let feito = false;
    const fim = r => { if (!feito) { feito = true; resolve(r); } };
    setTimeout(() => fim({ latitude: null, longitude: null, precisao: null, status: "sem_sinal" }), 12000);
    navigator.geolocation.getCurrentPosition(
      p => fim({ latitude: p.coords.latitude, longitude: p.coords.longitude, precisao: Math.round(p.coords.accuracy || 0), status: "ok" }),
      e => fim({ latitude: null, longitude: null, precisao: null, status: e.code === 1 ? "negado" : "sem_sinal" }),
      { enableHighAccuracy: true, timeout: 10000, maximumAge: 60000 }
    );
  });
}
const CP_LOCAL_TEXTO = { ok: "Registrada", negado: "Pessoa não permitiu", sem_sinal: "Sem sinal de GPS", indisponivel: "Aparelho sem GPS" };

/* ---------------- envio com e sem internet ---------------- */
async function cpInserir(reg) {
  const { error } = await sb.from("interviews").insert(reg);
  if (!error) return "ok";
  if (error.code === "23505") return "ok"; // já tinha chegado antes (mesmo número da entrevista)
  throw error;
}
async function cpEnviarEntrevista(reg) {
  if (!navigator.onLine) { cpGuardarNaFila(reg); return "fila"; }
  try { return await cpInserir(reg); }
  catch (e) { if (cpEhErroDeRede(e)) { cpGuardarNaFila(reg); return "fila"; } throw e; }
}
function cpFila() { return cpLer(CP_FILA, []).filter(x => x && x.client_uuid); }
function cpGuardarNaFila(reg) {
  const f = cpFila(); f.push({ ...reg, synced_offline: true, _usuario: reg.interviewer_id });
  if (!cpGravar(CP_FILA, f)) throw new Error("O aparelho está sem espaço para guardar a entrevista.");
  cpAtualizarSelo();
}
let cpSincronizando = false;
async function cpSincronizar(avisar) {
  if (cpSincronizando || !navigator.onLine || !state.user) return;
  const fila = cpFila(); if (!fila.length) return;
  cpSincronizando = true; let enviados = 0, problemas = 0;
  try {
    for (const item of fila) {
      if (item._usuario && item._usuario !== state.user.id) continue; // só envia o que este usuário fez
      const { _usuario, _erro, ...reg } = item;
      try {
        await cpInserir(reg);
        cpGravar(CP_FILA, cpFila().filter(x => x.client_uuid !== item.client_uuid)); enviados++;
      } catch (e) {
        if (cpEhErroDeRede(e)) break;
        problemas++;
        cpGravar(CP_FILA, cpFila().map(x => x.client_uuid === item.client_uuid ? { ...x, _erro: e.message || "recusada" } : x));
      }
    }
  } finally { cpSincronizando = false; cpAtualizarSelo(); }
  if (enviados) { try { await loadSurveyData(); render(); } catch (e) { /* tela atualiza depois */ } }
  if (avisar || enviados) cpAviso(enviados ? `✅ ${enviados} entrevista(s) guardada(s) no aparelho foram enviadas.` : (problemas ? "⚠️ Algumas entrevistas guardadas foram recusadas pelo servidor. Fale com o administrador." : "Nada para enviar."));
}
function cpAviso(txt) {
  let el = document.getElementById("cpAviso");
  if (!el) { el = document.createElement("div"); el.id = "cpAviso"; el.className = "cp-aviso"; document.body.appendChild(el); }
  el.textContent = txt; el.classList.add("on");
  clearTimeout(el._t); el._t = setTimeout(() => el.classList.remove("on"), 5000);
}
function cpAtualizarSelo() {
  const topo = document.querySelector(".topbar"); if (!topo) return;
  let selo = topo.querySelector(".cp-selo");
  if (!selo) { selo = document.createElement("button"); selo.type = "button"; selo.className = "cp-selo"; selo.onclick = () => cpSincronizar(true); topo.insertBefore(selo, topo.lastElementChild); }
  const n = state.user ? cpFila().filter(x => !x._usuario || x._usuario === state.user.id).length : 0;
  const on = navigator.onLine;
  selo.classList.toggle("off", !on);
  selo.textContent = (on ? "🟢 Online" : "📴 Sem internet") + (n ? ` • ${n} a enviar` : "");
  selo.title = n ? "Entrevistas guardadas neste aparelho. Toque para enviar agora." : (on ? "Conectado" : "As entrevistas ficam guardadas e são enviadas quando a internet voltar.");
}
window.addEventListener("online", () => { cpAtualizarSelo(); cpSincronizar(false); });
window.addEventListener("offline", cpAtualizarSelo);
setInterval(() => cpSincronizar(false), 60000);

/* ---------------- dados guardados para usar sem internet ---------------- */
function cpChaveCache() { return state.user ? "cp_cache_" + state.user.id : null; }
(function () {
  const carregarOriginal = loadSurveyData;
  loadSurveyData = async function () {
    try {
      await carregarOriginal();
      const k = cpChaveCache();
      if (k) cpGravar(k, { em: Date.now(), profile: state.profile, surveys: state.surveys, survey_id: state.survey?.id || null, regions: state.regions, congregations: state.congregations, interviews: (state.interviews || []).slice(0, 100), dashboardInterviews: cpEhGestor() ? [] : (state.dashboardInterviews || []).slice(0, 500) });
    } catch (e) {
      if (!cpEhErroDeRede(e)) throw e;
      cpUsarCache();
    }
  };
  const usuarioOriginal = loadUser;
  loadUser = async function () {
    try { await usuarioOriginal(); }
    catch (e) {
      if (!cpEhErroDeRede(e)) throw e;
      const { data: { session } } = await sb.auth.getSession();
      if (!session) throw e;
      state.user = session.user;
      cpUsarCache();
    }
  };
})();
function cpUsarCache() {
  const c = cpLer(cpChaveCache(), null); if (!c) return false;
  state.profile = state.profile || c.profile;
  if (!state.surveys?.length) state.surveys = c.surveys || [];
  if (!state.survey) state.survey = (state.surveys || []).find(s => s.id === c.survey_id) || (state.surveys.length === 1 ? state.surveys[0] : null);
  if (!state.regions?.length) state.regions = c.regions || [];
  if (!state.congregations?.length) state.congregations = c.congregations || [];
  if (!state.interviews?.length) state.interviews = c.interviews || [];
  if (!state.dashboardInterviews?.length) state.dashboardInterviews = c.dashboardInterviews || [];
  state.cpDoCache = c.em;
  return true;
}

/* ---------------- troca do código no primeiro acesso ---------------- */
function cpPedirTrocaCodigo() {
  if (document.getElementById("cpTrocaCodigo")) return;
  const m = document.createElement("div"); m.id = "cpTrocaCodigo"; m.className = "cp-modal";
  m.innerHTML = `<div class="card cp-modal-caixa">
    <div style="font-size:44px;text-align:center">🔐</div>
    <h2 style="text-align:center;margin:6px 0">Crie o seu código de acesso</h2>
    <p class="muted" style="text-align:center">Por segurança, troque o código inicial por um código só seu. Ninguém mais (nem o administrador) fica sabendo.</p>
    <div class="field"><label>Código atual</label><input id="cpCodAtual" type="password" autocomplete="current-password" inputmode="numeric"></div>
    <div class="field"><label>Novo código (mínimo 4)</label><input id="cpCodNovo" type="password" autocomplete="new-password" inputmode="numeric"></div>
    <div class="field"><label>Repita o novo código</label><input id="cpCodNovo2" type="password" autocomplete="new-password" inputmode="numeric" onkeydown="if(event.key==='Enter')cpSalvarCodigo()"></div>
    <div id="cpCodErro" class="cp-erro"></div>
    <button id="cpCodBotao" class="btn primary" style="width:100%;margin-top:14px" onclick="cpSalvarCodigo()">SALVAR NOVO CÓDIGO</button>
    <button class="btn" style="width:100%;margin-top:8px" onclick="document.getElementById('cpTrocaCodigo')?.remove();logout()">Sair</button>
  </div>`;
  document.body.appendChild(m);
  setTimeout(() => document.getElementById("cpCodAtual")?.focus(), 50);
}
async function cpSalvarCodigo() {
  const atual = document.getElementById("cpCodAtual").value.trim();
  const novo = document.getElementById("cpCodNovo").value.trim();
  const novo2 = document.getElementById("cpCodNovo2").value.trim();
  const erro = document.getElementById("cpCodErro"), bt = document.getElementById("cpCodBotao");
  erro.textContent = "";
  if (!atual) return (erro.textContent = "Digite o código atual.");
  if (novo.length < 4) return (erro.textContent = "O novo código precisa ter pelo menos 4 caracteres.");
  if (novo !== novo2) return (erro.textContent = "Os dois novos códigos não são iguais.");
  if (novo === atual || novo === CP_CODIGO_INICIAL) return (erro.textContent = "Escolha um código diferente do inicial.");
  bt.disabled = true; bt.textContent = "SALVANDO...";
  try {
    await cpFuncao({ action: "change_own_code", current_code: atual, new_code: novo });
    // entra de novo já com o código novo
    const email = state.user?.email;
    if (email) await sb.auth.signInWithPassword({ email, password: senhaAuth(novo) });
    if (state.profile) state.profile.must_change_code = false;
    document.getElementById("cpTrocaCodigo")?.remove();
    cpAviso("✅ Código alterado. Use o novo código nos próximos acessos.");
  } catch (e) {
    erro.textContent = e.message || "Não foi possível trocar o código.";
    bt.disabled = false; bt.textContent = "SALVAR NOVO CÓDIGO";
  }
}
function cpTrocarMeuCodigo() { cpPedirTrocaCodigo(); const t = document.querySelector("#cpTrocaCodigo h2"); if (t) t.textContent = "Trocar o meu código de acesso"; }

/* ---------------- instalar como aplicativo ---------------- */
let cpPedidoInstalar = null;
window.addEventListener("beforeinstallprompt", e => { e.preventDefault(); cpPedidoInstalar = e; document.querySelectorAll(".cp-instalar").forEach(b => (b.style.display = "")); });
window.addEventListener("appinstalled", () => { cpPedidoInstalar = null; cpAviso("📲 Aplicativo instalado!"); });
function cpJaInstalado() { return window.matchMedia?.("(display-mode: standalone)").matches || navigator.standalone === true; }
async function cpInstalar() {
  if (cpPedidoInstalar) { cpPedidoInstalar.prompt(); try { await cpPedidoInstalar.userChoice; } catch (e) { /* cancelado */ } cpPedidoInstalar = null; return; }
  const ios = /iphone|ipad|ipod/i.test(navigator.userAgent);
  alert(ios
    ? "Para instalar no iPhone/iPad:\n\n1. Abra este endereço no Safari\n2. Toque no botão Compartilhar (quadrado com seta)\n3. Escolha \"Adicionar à Tela de Início\""
    : "Para instalar no celular:\n\n1. Abra este endereço no Chrome\n2. Toque no menu ⋮ (três pontinhos)\n3. Escolha \"Instalar app\" ou \"Adicionar à tela inicial\"");
}
if ("serviceWorker" in navigator && (location.protocol === "https:" || location.hostname === "localhost")) {
  window.addEventListener("load", () => navigator.serviceWorker?.register("sw.js").catch(e => console.warn("Modo sem internet indisponível:", e)));
}

/* ---------------- menu e tela ---------------- */
function cpBotoesExtras() {
  const ativo = p => (state.page === p ? "active" : "");
  let h = "";
  if (cpEhGestor()) h += `<button type="button" class="nav-btn ${ativo("trash")}" onclick="nav('trash')">🗑️ Lixeira</button>`;
  h += `<button type="button" class="nav-btn" onclick="openCentralSettings()">⚙️ Configurações</button>`;
  h += `<button type="button" class="nav-btn" onclick="cpTrocarMeuCodigo()">🔐 Trocar meu código</button>`;
  if (!cpJaInstalado()) h += `<button type="button" class="nav-btn cp-instalar" onclick="cpInstalar()">📲 Instalar app</button>`;
  return h;
}
function cpDepoisDeRender() {
  cpAtualizarSelo();
  if (state.user && state.profile?.must_change_code) cpPedirTrocaCodigo();
  if (state.cpDoCache && !navigator.onLine) {
    const c = document.querySelector(".content");
    if (c && !c.querySelector(".cp-faixa-off")) c.insertAdjacentHTML("afterbegin", `<div class="cp-faixa-off">📴 Sem internet — mostrando os dados guardados em ${cpDataHora(state.cpDoCache)}. Entrevistas novas ficam guardadas e são enviadas sozinhas.</div>`);
  }
}

/* ---------------- lixeira ---------------- */
async function cpLixeiraPage() {
  if (!cpEhGestor()) return `<div class="card"><h2>Sem permissão</h2></div>`;
  let d;
  try { d = await cpFuncao({ action: "list_trash" }); }
  catch (e) { return `<div class="card"><h1>🗑️ Lixeira</h1><p class="cp-erro">${esc(e.message)}</p></div>`; }
  const pessoas = Object.fromEntries((d.pessoas || []).map(p => [p.id, p.full_name]));
  const nomeSurvey = Object.fromEntries((d.itens.survey || []).map(s => [s.id, s.candidate_name || s.name]));
  (state.surveys || []).forEach(s => (nomeSurvey[s.id] = nomeSurvey[s.id] || s.candidate_name || s.name));
  const resta = dt => Math.max(0, d.dias - Math.floor((Date.now() - new Date(dt).getTime()) / 86400000));
  const bloco = (tipo, titulo, icone, lista) => `
    <div class="card"><h2>${icone} ${titulo} <span class="badge">${lista.length}</span></h2>
    ${lista.length ? `<div class="table-wrap"><table><thead><tr><th>Nome</th>${tipo === "survey" ? "<th>Cargo</th>" : "<th>Pesquisa</th>"}<th>Excluída em</th><th>Por</th><th>Apaga sozinha em</th><th></th></tr></thead><tbody>
    ${lista.map(x => `<tr><td><strong>${esc(x.candidate_name || x.name)}</strong></td>
      <td>${esc(tipo === "survey" ? x.office || "" : nomeSurvey[x.survey_id] || "—")}</td>
      <td>${esc(cpDataHora(x.deleted_at))}</td><td>${esc(pessoas[x.deleted_by] || "—")}</td><td>${resta(x.deleted_at)} dia(s)</td>
      <td class="actions"><button class="btn small primary" onclick="cpRestaurar('${tipo}','${x.id}')">↩ Restaurar</button>
      ${d.pode_apagar ? `<button class="btn small cp-perigo" onclick="cpApagarDeVez('${tipo}','${x.id}',${htmlJsArg(x.candidate_name || x.name)})">Apagar de vez</button>` : ""}</td></tr>`).join("")}
    </tbody></table></div>` : `<p class="muted">Nada aqui.</p>`}</div>`;
  return `<div class="grid" style="gap:18px">
    <div class="card"><h1>🗑️ Lixeira</h1><p class="muted">O que foi excluído fica aqui por ${d.dias} dias e pode ser restaurado. Depois disso é apagado sozinho.${d.pode_apagar ? "" : " Só o Administrador pode apagar de vez antes do prazo."}</p></div>
    ${bloco("survey", "Pesquisas", "🎯", d.itens.survey || [])}
    ${bloco("region", "Regiões", "📍", d.itens.region || [])}
    ${bloco("congregation", "Congregações", "⛪", d.itens.congregation || [])}
  </div>`;
}
async function cpRestaurar(kind, id) {
  try { const r = await cpFuncao({ action: "restore", kind, id }); await loadSurveyData(); render(); cpAviso("↩ " + r.message); }
  catch (e) { showError(e); }
}
async function cpApagarDeVez(kind, id, nome) {
  if (!confirm(`APAGAR DE VEZ "${nome}"?\n\nIsso não tem volta.` + (kind === "survey" ? "\nTodas as entrevistas desta pesquisa também serão apagadas." : ""))) return;
  if (kind === "survey" && prompt('Para confirmar, digite APAGAR') !== "APAGAR") return;
  try { const r = await cpFuncao({ action: "purge", kind, id }); render(); cpAviso(r.message); }
  catch (e) { showError(e); }
}

/* ---------------- nomes de regiões/congregações (para gráficos e Excel) ---------------- */
async function cpNomes(surveyId) {
  state.cpNomes = state.cpNomes || {};
  if (state.cpNomes[surveyId]) return state.cpNomes[surveyId];
  if (state.survey?.id === surveyId && state.regions?.length) {
    return (state.cpNomes[surveyId] = { regioes: Object.fromEntries(state.regions.map(r => [r.id, r.name])), congs: Object.fromEntries(state.congregations.map(c => [c.id, c.name])) });
  }
  try {
    const [r, c] = await Promise.all([sb.from("regions").select("id,name").eq("survey_id", surveyId), sb.from("congregations").select("id,name").eq("survey_id", surveyId)]);
    return (state.cpNomes[surveyId] = { regioes: Object.fromEntries((r.data || []).map(x => [x.id, x.name])), congs: Object.fromEntries((c.data || []).map(x => [x.id, x.name])) });
  } catch (e) { return { regioes: {}, congs: {} }; }
}

/* ---------------- gráficos ---------------- */
function cpPesquisaDoGrafico() {
  const lista = state.surveys || [];
  if (!lista.length) return null;
  return lista.find(s => s.id === state.cpGrafSurvey) || state.survey || lista[0];
}
function cpTrocarGrafico(id) { state.cpGrafSurvey = id; render(); }
function cpBarras(linhas, total) {
  if (!linhas.length) return `<p class="muted">Ainda sem entrevistas.</p>`;
  const max = Math.max(...linhas.map(l => l.total), 1);
  return `<div class="cp-barras">${linhas.map(l => `
    <div class="cp-barra-linha"><div class="cp-barra-nome" title="${esc(l.nome)}">${esc(l.nome)}</div>
      <div class="cp-barra-trilho"><div class="cp-barra-cheia" style="width:${(l.total / max) * 100}%">
        ${Object.keys(CP_CORES).map(k => l[k] ? `<span style="width:${(l[k] / l.total) * 100}%;background:${CP_CORES[k]}" title="${CP_INTENCOES[k]}: ${l[k]}"></span>` : "").join("")}
      </div></div>
      <div class="cp-barra-num">${fmt(l.total)} <small>${pct(l.yes, l.total)} sim</small></div></div>`).join("")}</div>`;
}
function cpAgrupar(rows, chave, nomes) {
  const g = {};
  rows.forEach(r => { const k = r[chave] || "—"; g[k] = g[k] || { nome: nomes[k] || (k === "—" ? "Sem informação" : "Excluída/sem nome"), total: 0, yes: 0, no: 0, other: 0, undecided: 0 }; g[k].total++; if (g[k][r.intention] !== undefined) g[k][r.intention]++; });
  return Object.values(g).sort((a, b) => b.total - a.total);
}
async function cpGraficosPainel() {
  const s = cpPesquisaDoGrafico(); if (!s) return "";
  const rows = (state.dashboardInterviews || []).filter(r => r.survey_id === s.id);
  const nomes = await cpNomes(s.id);
  const total = rows.length;
  const cont = k => rows.filter(r => r.intention === k).length;
  const pizza = Object.keys(CP_CORES).map(k => ({ k, n: cont(k) }));
  let acc = 0;
  const fatias = total ? pizza.map(p => { const ini = acc; acc += (p.n / total) * 100; return `${CP_CORES[p.k]} ${ini}% ${acc}%`; }).join(",") : "#e2e8f0 0 100%";
  const dias = []; for (let i = 13; i >= 0; i--) { const d = new Date(); d.setHours(0, 0, 0, 0); d.setDate(d.getDate() - i); dias.push(d); }
  const porDia = dias.map(d => ({ d, n: rows.filter(r => { const x = new Date(r.created_at); return x >= d && x < new Date(d.getTime() + 86400000); }).length }));
  const maxDia = Math.max(...porDia.map(x => x.n), 1);
  const podeExportar = await cpPodeExportar(s.id);
  return `
  <div class="card cp-graficos" style="margin-top:20px">
    <div class="row"><div><h2>📈 Gráficos da pesquisa</h2><p class="muted">${fmt(total)} entrevista(s)${cpEhGestor() ? "" : " que você pode ver"}.</p></div>
      <div class="actions">
        ${(state.surveys || []).length > 1 ? `<select onchange="cpTrocarGrafico(this.value)" style="width:auto">${state.surveys.map(x => `<option value="${x.id}" ${x.id === s.id ? "selected" : ""}>${esc(x.candidate_name || x.name)}</option>`).join("")}</select>` : `<strong>${esc(s.candidate_name || s.name)}</strong>`}
        ${podeExportar ? `<button class="btn primary" onclick="cpExportarExcel('${s.id}')">📥 Exportar Excel</button>` : ""}
      </div></div>
    <div class="cp-legenda">${Object.keys(CP_CORES).map(k => `<span><i style="background:${CP_CORES[k]}"></i>${k === "yes" ? esc(s.candidate_name || "Candidato") : CP_INTENCOES[k]}</span>`).join("")}</div>
    <div class="cp-graf-grade">
      <div class="card"><h3>Intenção geral</h3>
        <div class="cp-pizza" style="background:conic-gradient(${fatias})"><div>${fmt(total)}<small>entrevistas</small></div></div>
        <div class="cp-pizza-lista">${pizza.map(p => `<div><i style="background:${CP_CORES[p.k]}"></i>${p.k === "yes" ? esc(s.candidate_name || "Candidato") : CP_INTENCOES[p.k]}<b>${fmt(p.n)} • ${pct(p.n, total)}</b></div>`).join("")}</div>
      </div>
      <div class="card"><h3>Entrevistas por dia (últimos 14 dias)</h3>
        <div class="cp-colunas">${porDia.map(x => `<div class="cp-coluna" title="${x.d.toLocaleDateString("pt-BR")}: ${x.n}"><span>${x.n || ""}</span><div style="height:${(x.n / maxDia) * 100}%"></div><small>${String(x.d.getDate()).padStart(2, "0")}</small></div>`).join("")}</div>
      </div>
    </div>
    <div class="card" style="margin-top:14px"><h3>📍 Por região</h3>${cpBarras(cpAgrupar(rows, "region_id", nomes.regioes), total)}</div>
    <div class="card" style="margin-top:14px"><h3>⛪ Por congregação (as 15 maiores)</h3>${cpBarras(cpAgrupar(rows, "congregation_id", nomes.congs).slice(0, 15), total)}</div>
  </div>`;
}

/* ---------------- exportar para Excel ---------------- */
async function cpPodeExportar(surveyId) {
  if (cpEhGestor()) return true;
  if (!navigator.onLine) return false;
  state.cpExporta = state.cpExporta || {};
  if (state.cpExporta[surveyId] !== undefined) return state.cpExporta[surveyId];
  try {
    const { data } = await sb.from("survey_access").select("can_export").eq("user_id", state.user.id).eq("survey_id", surveyId).maybeSingle();
    return (state.cpExporta[surveyId] = !!data?.can_export);
  } catch (e) { return false; }
}
function cpCarregarScript(src) {
  return new Promise((ok, falha) => { const s = document.createElement("script"); s.src = src; s.onload = ok; s.onerror = () => falha(new Error("Não foi possível carregar o gerador de Excel. Verifique a internet.")); document.head.appendChild(s); });
}
async function cpExportarExcel(surveyId) {
  const s = (state.surveys || []).find(x => x.id === surveyId); if (!s) return;
  if (!(await cpPodeExportar(surveyId))) return alert("Você não tem permissão para exportar esta pesquisa.");
  try {
    cpAviso("📥 Preparando a planilha…");
    if (!window.XLSX) await cpCarregarScript("lib/xlsx-0.18.5.min.js");
    const todas = [];
    for (let de = 0; ; de += 1000) {
      const { data, error } = await sb.from("interviews").select("id,created_at,device_time,interviewee_name,region_id,congregation_id,intention,reason,interviewer_id,latitude,longitude,location_accuracy,location_status,synced_offline").eq("survey_id", surveyId).order("created_at", { ascending: true }).range(de, de + 999);
      if (error) throw error;
      todas.push(...(data || []));
      if (!data || data.length < 1000) break;
    }
    const nomes = await cpNomes(surveyId);
    let pessoas = {};
    if (cpEhGestor()) { const { data } = await sb.from("profiles").select("id,full_name"); pessoas = Object.fromEntries((data || []).map(p => [p.id, p.full_name])); }
    const rotulo = k => (k === "yes" ? `Votaria em ${s.candidate_name || "candidato"}` : CP_INTENCOES[k] || k);
    const linhas = todas.map(r => ({
      "Data/hora (servidor)": cpDataHora(r.created_at),
      "Hora no aparelho": cpDataHora(r.device_time),
      "Entrevistado": r.interviewee_name,
      "Região": nomes.regioes[r.region_id] || "",
      "Congregação": nomes.congs[r.congregation_id] || "",
      "Intenção": rotulo(r.intention),
      "Observação": r.reason || "",
      "Pesquisador": pessoas[r.interviewer_id] || (r.interviewer_id === state.user.id ? state.profile?.full_name || "" : ""),
      "Localização": CP_LOCAL_TEXTO[r.location_status] || (r.location_status ? r.location_status : "Não registrada"),
      "Latitude": r.latitude ?? "",
      "Longitude": r.longitude ?? "",
      "Precisão (m)": r.location_accuracy ?? "",
      "Mapa": r.latitude != null ? `https://maps.google.com/?q=${r.latitude},${r.longitude}` : "",
      "Enviada depois (sem internet)": r.synced_offline ? "Sim" : "Não"
    }));
    const resumo = (grupos, titulo) => grupos.map(g => ({ [titulo]: g.nome, "Entrevistas": g.total, [rotulo("yes")]: g.yes, "Não votaria": g.no, "Outro": g.other, "Indeciso": g.undecided, "% Sim": g.total ? +(g.yes / g.total * 100).toFixed(1) : 0 }));
    const wb = XLSX.utils.book_new();
    const add = (dados, nome, larg) => { const ws = XLSX.utils.json_to_sheet(dados.length ? dados : [{ Aviso: "Sem dados" }]); if (larg) ws["!cols"] = larg.map(w => ({ wch: w })); XLSX.utils.book_append_sheet(wb, ws, nome); };
    add(linhas, "Entrevistas", [20, 20, 28, 20, 24, 26, 30, 22, 18, 12, 12, 10, 40, 14]);
    add(resumo(cpAgrupar(todas, "region_id", nomes.regioes), "Região"), "Por região", [28, 12, 22, 12, 10, 10, 8]);
    add(resumo(cpAgrupar(todas, "congregation_id", nomes.congs), "Congregação"), "Por congregação", [28, 12, 22, 12, 10, 10, 8]);
    const nomeArq = `pesquisa_${String(s.candidate_name || s.name || "resultado").normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/[^a-z0-9]+/gi, "_").toLowerCase()}_${new Date().toISOString().slice(0, 10)}.xlsx`;
    XLSX.writeFile(wb, nomeArq);
    cpAviso(`✅ Planilha gerada com ${fmt(todas.length)} entrevista(s).`);
  } catch (e) { showError(e); }
}

window.cpSalvarCodigo = cpSalvarCodigo; window.cpTrocarMeuCodigo = cpTrocarMeuCodigo; window.cpInstalar = cpInstalar;
window.cpRestaurar = cpRestaurar; window.cpApagarDeVez = cpApagarDeVez; window.cpTrocarGrafico = cpTrocarGrafico;
window.cpExportarExcel = cpExportarExcel; window.cpSincronizar = cpSincronizar; window.openCentralSettings = openCentralSettings;
