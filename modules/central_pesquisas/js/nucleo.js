/* Central de Pesquisas — núcleo: estado, carga de dados, login, navegação, perfis */
/*
 * CENTRAL DE PESQUISAS — VERSÃO CORRIGIDA
 */

const sb = window.supabase.createClient(
  window.APP_CONFIG.SUPABASE_URL,
  window.APP_CONFIG.SUPABASE_ANON_KEY
);

const state = {
  user: null,
  profile: null,
  surveys: [],
  survey: null,
  regions: [],
  congregations: [],
  interviews: [],
  dashboardInterviews: [],
  page: "dashboard",
  interviewStep: 1,

  form: {
    interviewee_name: "",
    region_id: "",
    congregation_id: "",
    intention: "",
    reason: ""
  }
};

const esc = (value) =>
  String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");

const fmt = (n) =>
  Number(n || 0).toLocaleString("pt-BR");

const pct = (n, total) =>
  total
    ? `${((n / total) * 100).toFixed(1).replace(".", ",")}%`
    : "0,0%";

// Serializa argumentos usados em onclick e escapa o HTML para impedir que
// aspas nos nomes quebrem o atributo e impeçam o clique.
function htmlJsArg(value) {
  return esc(JSON.stringify(String(value ?? "")));
}

async function init() {
  const {
    data: { session }
  } = await sb.auth.getSession();

  if (session) {
    await loadUser();
  }

  render();

  sb.auth.onAuthStateChange(async (_event, session) => {
    if (session) {
      try {
        await loadUser();
      } catch (error) {
        console.error(error);
      }
    } else {
      state.user = null;
      state.profile = null;
      state.surveys = [];
      state.survey = null;
    }

    render();
  });
}

async function loadUser() {
  const {
    data: { user },
    error: userError
  } = await sb.auth.getUser();

  if (userError) {
    throw userError;
  }

  state.user = user;

  const {
    data: profile,
    error
  } = await sb
    .from("profiles")
    .select("*")
    .eq("id", user.id)
    .maybeSingle();

  if (error) {
    throw error;
  }

  state.profile = profile;

  if (state.profile?.active === false) {
    await sb.auth.signOut();

    state.user = null;
    state.profile = null;

    alert(
      "Seu usuário está desativado. Procure o administrador."
    );

    return;
  }

  await loadSurveyData();
}

async function loadSurveyData() {

  if (!state.user) {
    state.surveys = [];
    state.survey = null;
    state.regions = [];
    state.congregations = [];
    state.interviews = [];
    state.dashboardInterviews = [];
    return;
  }

  /*
   * ADMINISTRADOR E COORDENADOR
   * podem visualizar todas as pesquisas.
   */
  if (
    state.profile?.role === "admin" ||
    state.profile?.role === "coordinator"
  ) {

    const {
      data: surveys,
      error
    } = await sb
      .from("surveys")
      .select("*").is("deleted_at", null)
      .order("created_at", {
        ascending: false
      });

    if (error) {
      throw error;
    }

    state.surveys = surveys || [];

  } else {

    /*
     * PESQUISADOR:
     * somente pesquisas liberadas para ele.
     */
    const {
      data: access,
      error
    } = await sb
      .from("survey_access")
      .select(`
        survey_id,
        can_view,
        surveys (*)
      `)
      .eq(
        "user_id",
        state.user.id
      )
      .eq(
        "can_view",
        true
      );

    if (error) {
      throw error;
    }

    state.surveys =
      (access || [])
        .map(item => item.surveys)
        .filter(Boolean)
        .filter(
          survey =>
            survey.status === "active"
        );
  }

  /*
   * Mantém a pesquisa atual se ela ainda
   * estiver disponível.
   */
  if (
    state.survey &&
    !state.surveys.some(
      s => s.id === state.survey.id
    )
  ) {
    state.survey = null;
  }

  /*
   * Se existe somente uma pesquisa disponível,
   * seleciona automaticamente.
   */
  if (
    !state.survey &&
    state.surveys.length === 1
  ) {
    state.survey =
      state.surveys[0];
  }

  if (!state.survey) {
    state.regions = [];
    state.congregations = [];
    state.interviews = [];
    state.dashboardInterviews = [];
    return;
  }

  const [
    regions,
    congregations,
    interviews
  ] = await Promise.all([

    sb
      .from("regions")
      .select("*").is("deleted_at", null)
      .eq(
        "survey_id",
        state.survey.id
      )
      .order("name"),

    sb
      .from("congregations")
      .select("*").is("deleted_at", null)
      .eq(
        "survey_id",
        state.survey.id
      )
      .order("name"),

    sb
      .from("interviews")
      .select("*")
      .eq(
        "survey_id",
        state.survey.id
      )
      .order(
        "created_at",
        {
          ascending: false
        }
      )
      .limit(100)
  ]);

  if (regions.error) {
    throw regions.error;
  }

  if (congregations.error) {
    throw congregations.error;
  }

  if (interviews.error) {
    throw interviews.error;
  }

  state.regions =
    regions.data || [];

  state.congregations =
    congregations.data || [];

  state.interviews =
    interviews.data || [];

  /*
   * Dashboard administrativo:
   * carrega entrevistas de todas as pesquisas.
   */
  if (
    state.profile?.role === "admin" ||
    state.profile?.role === "coordinator"
  ) {

    const {
      data: allInterviews,
      error: allError
    } = await sb
      .from("interviews")
      .select(`
        survey_id,
        intention,
        created_at,
        interviewee_name,
        region_id,
        congregation_id
      `)
      .order(
        "created_at",
        {
          ascending: false
        }
      )
      .limit(5000);

    if (allError) {
      throw allError;
    }

    state.dashboardInterviews =
      allInterviews || [];

  } else {

    state.dashboardInterviews =
      state.interviews || [];
  }
}


/* =========================================================
   SELECIONAR PESQUISA
   ========================================================= */

async function selectSurvey(surveyId) {

  const survey =
    state.surveys.find(
      item =>
        item.id === surveyId
    );

  if (!survey) {
    alert(
      "Pesquisa não encontrada."
    );
    return;
  }

  /*
   * A lista state.surveys do pesquisador já contém
   * somente as pesquisas autorizadas.
   */
  state.survey =
    survey;

  await loadSurveyData();

  render();
}


/* =========================================================
   SELETOR DE PESQUISAS
   ========================================================= */

function surveySelector() {

  if (
    !state.surveys ||
    state.surveys.length === 0
  ) {

    return `
      <div class="card">

        <h2>
          🎯 Pesquisas autorizadas
        </h2>

        <p class="muted">
          Nenhuma pesquisa foi atribuída a você.
        </p>

      </div>
    `;
  }

  /*
   * Uma única pesquisa:
   * não mostra escolha ao pesquisador.
   */
  if (
    state.profile?.role === "researcher" &&
    state.surveys.length === 1
  ) {

    const survey =
      state.surveys[0];

    return `
      <div
        class="card"
        style="
          margin-bottom:18px;
          border-left:4px solid var(--primary);
        "
      >

        <strong>
          🎯 Pesquisa autorizada
        </strong>

        <div
          style="
            margin-top:6px;
            font-size:18px;
          "
        >
          ${esc(
            survey.candidate_name ||
            survey.name ||
            "Pesquisa"
          )}
        </div>

        <div
          class="muted"
          style="
            margin-top:3px;
          "
        >
          ${esc(
            survey.office || ""
          )}
        </div>

      </div>
    `;
  }

  /*
   * Duas ou mais pesquisas:
   * mostra SOMENTE as autorizadas.
   */
  return `
    <div
      class="card"
      style="margin-bottom:18px"
    >

      <h2>
        🎯 Pesquisas autorizadas
      </h2>

      <p class="muted">
        Selecione a pesquisa que você foi autorizado
        a realizar.
      </p>

      <div
        style="
          display:grid;
          gap:12px;
          margin-top:15px;
        "
      >

        ${state.surveys
          .map(survey => {

            const selected =
              state.survey?.id ===
              survey.id;

            return `
              <button
                type="button"
                class="card"
                onclick="
                  selectSurvey(
                    '${survey.id}'
                  )
                "
                style="
                  text-align:left;
                  cursor:pointer;
                  border:2px solid
                    ${
                      selected
                        ? "#2563eb"
                        : "#e5e7eb"
                    };
                  background:
                    ${
                      selected
                        ? "#eff6ff"
                        : "#fff"
                    };
                "
              >

                <strong>
                  ${esc(
                    survey.candidate_name ||
                    survey.name ||
                    "Pesquisa"
                  )}
                </strong>

                <div
                  class="muted"
                  style="
                    margin-top:5px;
                  "
                >
                  ${esc(
                    survey.office || ""
                  )}
                </div>

              </button>
            `;
          })
          .join("")}

      </div>

    </div>
  `;
}


/* =========================================================
   ERROS
   ========================================================= */

function showError(error) {

  console.error(
    "CENTRAL DE PESQUISAS:",
    error
  );

  alert(
    error?.message ||
    "Ocorreu um erro. Verifique o Supabase."
  );
}


/* =========================================================
   ATUALIZAR
   ========================================================= */

async function refresh() {

  if (!state.user) {
    return;
  }

  try {

    await loadSurveyData();

    render();

  } catch (error) {

    showError(error);

  }
}


/* =========================================================
   LOGIN
   ========================================================= */

/* Códigos de acesso com menos de 6 caracteres (como a senha padrão) são completados do mesmo jeito em todo lugar. */
function senhaAuth(codigo) {
  const c = String(codigo || "").trim();
  return c.length >= 6 ? c : "rmd#" + c + "#cp";
}

async function login() {

  const username =
    document
      .querySelector("#email")
      ?.value
      .trim();

  const password =
    document
      .querySelector("#password")
      ?.value;

  if (!username || !password) {

    alert(
      "Preencha usuário e código de acesso."
    );

    return;
  }

  const button =
    document.querySelector(
      "#loginButton"
    );

  if (button) {

    button.disabled =
      true;

    button.textContent =
      "ENTRANDO...";

  }

  try {

    /*
     * Login por usuário + código de acesso.
     * 1) O banco devolve o e-mail técnico do usuário ativo (função cp_login_email, sem expor mais nada).
     * 2) O Supabase Auth confere o código. Códigos curtos (ex.: a senha padrão) são completados por
     *    senhaAuth(), porque o Supabase exige pelo menos 6 caracteres.
     */
    const {
      data: loginEmail,
      error: loginError
    } = await sb.rpc("cp_login_email", { p_username: username });

    if (loginError) {
      throw loginError;
    }

    if (!loginEmail) {
      throw new Error("Usuário ou código de acesso inválido.");
    }

    const {
      error: signInError
    } = await sb.auth.signInWithPassword({
      email: loginEmail,
      password: senhaAuth(password)
    });

    if (signInError) {
      throw new Error("Usuário ou código de acesso inválido.");
    }


  } catch (error) {

    console.error(
      "Erro de login:",
      error
    );

    alert(
      error?.message ||
      "Não foi possível entrar."
    );

    if (button) {

      button.disabled =
        false;

      button.textContent =
        "ENTRAR";

    }
  }
}


/* =========================================================
   LOGOUT
   ========================================================= */

async function logout() {

  await sb.auth.signOut();

  state.user =
    null;

  state.profile =
    null;

  state.surveys =
    [];

  state.survey =
    null;

  state.regions =
    [];

  state.congregations =
    [];

  state.interviews =
    [];

  state.dashboardInterviews =
    [];

  state.page =
    "dashboard";

  render();
}


/* =========================================================
   NAVEGAÇÃO
   ========================================================= */

function nav(page) {

  state.page =
    page;

  state.interviewStep =
    1;

  if (
    page ===
    "interview"
  ) {

    resetForm();

  }

  render();
}


/* =========================================================
   LIMPAR FORMULÁRIO
   ========================================================= */

function resetForm() {

  state.form = {

    interviewee_name:
      "",

    region_id:
      "",

    congregation_id:
      "",

    intention:
      "",

    reason:
      ""
  };
}


/* =========================================================
   FUNÇÕES DE PERFIL
   ========================================================= */

function roleLabel(role) {

  return {

    admin:
      "Administrador Principal",

    coordinator:
      "Coordenador",

    candidate:
      "Candidato",

    researcher:
      "Pesquisador"

  }[role] ||
  "Usuário";
}

function roleDescription(role) {

  return {

    admin:
      "Controle geral do sistema.",

    coordinator:
      "Administração de usuários e pesquisas.",

    candidate:
      "Visualização dos resultados.",

    researcher:
      "Realização das entrevistas."

  }[role] ||
  "Usuário do sistema.";
}

function roleIcon(role) {

  return {

    admin:
      "👑",

    coordinator:
      "👥",

    candidate:
      "⭐",

    researcher:
      "📝"

  }[role] ||
  "👤";
}


/* =========================================================
   TELA DE LOGIN
   ========================================================= */

function loginView() {
  // Entrada separada do Desenvolvedor RMD (endereço com #rmd): só a senha. A empresa nunca vê esta entrada.
  if (/rmd/i.test(location.hash || "")) {
    return `
    <div class="login">
      <div class="login-card">
        <div class="login-logo" style="font-size:64px;text-align:center;">🛠️</div>
        <h1>DESENVOLVEDOR RMD</h1>
        <div class="sub">Central de Pesquisas — acesso de administração do sistema</div>
        <input id="email" type="hidden" value="desenvolvedor">
        <div class="field">
          <label>Senha</label>
          <input id="password" type="password" placeholder="Digite a senha" autocomplete="current-password"
            onkeydown="if(event.key==='Enter') login()">
        </div>
        <button id="loginButton" class="btn primary" style="width:100%" onclick="login()">ENTRAR</button>
      </div>
    </div>`;
  }

  return `
    <div class="login">

      <div class="login-card">

        <div
          class="login-logo"
          style="
            font-size:64px;
            text-align:center;
          "
        >
          🇧🇷
        </div>

        <h1>
          CENTRAL DE PESQUISAS
        </h1>

        <div class="sub">
          Sistema online de pesquisas
          e intenção de voto
        </div>

        <div class="field">

          <label>
            Usuário
          </label>

          <input
            id="email"
            type="text"
            placeholder="Digite seu usuário"
            autocomplete="username"
          >

        </div>

        <div class="field">

          <label>
            Código de acesso
          </label>

          <input
            id="password"
            type="password"
            placeholder="Digite seu código"
            autocomplete="current-password"
            onkeydown="
              if(event.key==='Enter')
                login()
            "
          >

        </div>

        <button
          id="loginButton"
          class="btn primary"
          style="width:100%"
          onclick="login()"
        >
          ENTRAR
        </button>

        <div class="demo-box">

          <b>
            Acesso sem e-mail
          </b>

          <br>

          Use o usuário e o código
          fornecidos pelo administrador.

        </div>

      </div>

    </div>
  `;
}


/* =========================================================
   PERMISSÕES
   ========================================================= */

function normalizeRole(role) {
  return String(role || "")
    .trim()
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "");
}

function isAdminRole(role) {
  return ["admin", "administrator", "administrador"].includes(normalizeRole(role));
}

function isCoordinatorRole(role) {
  return ["coordinator", "coordenador"].includes(normalizeRole(role));
}

function isResearcherRole(role) {
  return ["researcher", "pesquisador"].includes(normalizeRole(role));
}

function canManageUsers() {
  const role = normalizeRole(state.profile?.role);
  return isAdminRole(role) || isCoordinatorRole(role);
}

function canCreateRole(role) {

  const currentRole =
    state.profile?.role;

  if (
    currentRole ===
    "admin"
  ) {

    return true;

  }

  if (
    currentRole ===
    "coordinator"
  ) {

    return role !==
      "admin";

  }

  return false;
}


/* =========================================================
   FORMULÁRIO DE NOVO USUÁRIO
   ========================================================= */

