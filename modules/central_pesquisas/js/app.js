/* Central de Pesquisas — montagem da tela, menu, configurações e funções expostas aos botões */
async function render() {

  const app =
    document.querySelector(
      "#app"
    );

  if (!app) {
    return;
  }


  /*
   * Usuário não conectado.
   */
  if (!state.user) {

    app.innerHTML =
      loginView();

    return;
  }


  /*
   * Carrega lista de usuários somente
   * quando necessário.
   */
  if (
    canManageUsers() &&
    state.page ===
      "users"
  ) {

    try {

      await loadProfiles();

    } catch (error) {

      console.error(
        error
      );

    }
  }


  let content =
    "";


  switch (
    state.page
  ) {

    case "users":

      content =
        await usersPage();

      break;


    case "surveys":

      content =
        await surveysPage();

      break;


    case "regions":

      content =
        await regionsPage();

      break;


    case "congregations":

      content =
        await congregationsPage();

      break;


    case "interview":
      content = interviewPage();
      break;

    case "trash":
      content = await cpLixeiraPage();
      break;


    case "dashboard":

    default:

      content = (await dashboardPage()) + (await cpGraficosPainel());
      break;

  }


  app.innerHTML = `

    <div class="app-shell">

      <aside
        class="sidebar"
        id="sidebar"
      >

        <div
          class="brand"
        >

          <div
            style="
              font-size:30px;
            "
          >
            🇧🇷
          </div>

          <div>

            <strong>
              CENTRAL
            </strong>

            <small>
              PESQUISAS
            </small>

          </div>

        </div>


        <div
          class="profile-mini"
        >

          <div
            style="
              font-size:28px;
            "
          >
            ${roleIcon(
              state.profile?.role
            )}
          </div>

          <div>

            <strong>
              ${esc(
                state.profile?.full_name ||
                "Usuário"
              )}
            </strong>

            <small>
              ${esc(
                roleLabel(
                  state.profile?.role
                )
              )}
            </small>

          </div>

        </div>


        <nav>

          <button
            type="button"
            class="
              nav-btn
              ${
                state.page ===
                "dashboard"
                  ? "active"
                  : ""
              }
            "
            onclick="
              nav('dashboard')
            "
          >
            📊
            Dashboard
          </button>


          ${
            canManageUsers()

              ? `

                <button
                  type="button"
                  class="
                    nav-btn
                    ${
                      state.page ===
                      "surveys"
                        ? "active"
                        : ""
                    }
                  "
                  onclick="
                    nav('surveys')
                  "
                >
                  🎯
                  Pesquisas
                </button>


                <button
                  type="button"
                  class="
                    nav-btn
                    ${
                      state.page ===
                      "users"
                        ? "active"
                        : ""
                    }
                  "
                  onclick="
                    nav('users')
                  "
                >
                  👥
                  Usuários
                </button>


                <button
                  type="button"
                  class="
                    nav-btn
                    ${
                      state.page ===
                      "regions"
                        ? "active"
                        : ""
                    }
                  "
                  onclick="
                    nav('regions')
                  "
                >
                  📍
                  Regiões
                </button>


                <button
                  type="button"
                  class="
                    nav-btn
                    ${
                      state.page ===
                      "congregations"
                        ? "active"
                        : ""
                    }
                  "
                  onclick="
                    nav('congregations')
                  "
                >
                  ⛪
                  Congregações
                </button>

              `

              : ""
          }


          ${
            state.profile?.role ===
            "researcher"

              ? `

                <button
                  type="button"
                  class="
                    nav-btn
                    ${
                      state.page ===
                      "interview"
                        ? "active"
                        : ""
                    }
                  "
                  onclick="
                    nav('interview')
                  "
                >
                  📝
                  Nova entrevista
                </button>

              `

              : ""
          }

          ${cpBotoesExtras()}
        </nav>


        <div
          style="
            margin-top:auto;
          "
        >

          <button
            type="button"
            class="nav-btn"
            onclick="
              refresh()
            "
          >
            ↻
            Atualizar
          </button>


          <button
            type="button"
            class="nav-btn"
            onclick="
              logout()
            "
          >
            🚪
            Sair
          </button>

        </div>

      </aside>


      <main
        class="main"
      >

        <header
          class="topbar"
        >

          <button
            type="button"
            class="btn small"
            onclick="
              toggleSidebar()
            "
          >
            ☰
          </button>


          <div>

            <strong>
              ${
                state.page ===
                "dashboard"
                  ? "Dashboard"

                  : state.page ===
                    "users"
                  ? "Usuários"

                  : state.page ===
                    "surveys"
                  ? "Pesquisas"

                  : state.page ===
                    "regions"
                  ? "Regiões"

                  : state.page ===
                    "congregations"
                  ? "Congregações"

                  : state.page ===
                    "interview"
                  ? "Nova entrevista"
                  : state.page === "trash"
                  ? "Lixeira"

                  : "Central"
              }
            </strong>

          </div>


          <button
            type="button"
            class="btn small"
            onclick="
              refresh()
            "
          >
            ↻
          </button>

        </header>


        <section
          class="content"
        >

          ${content}

        </section>

      </main>

    </div>

  `;

  cpDepoisDeRender();
}



/* =========================================================
   ACESSO MULTIPLATAFORMA
   ========================================================= */
function openPlatformAccess() {
  const old=document.querySelector("#platformAccessModal"); if(old) old.remove();
  const url=window.location.href;
  const modal=document.createElement("div"); modal.id="platformAccessModal";
  Object.assign(modal.style,{position:"fixed",inset:"0",zIndex:"10002",background:"rgba(0,0,0,.65)",display:"flex",alignItems:"center",justifyContent:"center",padding:"20px"});
  modal.innerHTML=`<div class="card" style="width:100%;max-width:620px"><div class="row"><div><h2>📱 Acesso multiplataforma</h2><p class="muted">A mesma Central pode ser aberta em celular, tablet, notebook ou computador.</p></div><button class="btn small" onclick="closePlatformAccess()">✕</button></div>
  <div class="card" style="margin-top:15px"><strong>Endereço da Central</strong><div style="display:flex;gap:8px;margin-top:10px"><input id="platformUrl" value="${esc(url)}" readonly style="flex:1"><button class="btn" onclick="copyPlatformUrl()">📋 Copiar</button></div></div>
  <div class="actions" style="margin-top:15px;flex-wrap:wrap"><button class="btn primary" onclick="openPlatformUrl()">🌐 Abrir Central</button><button class="btn" onclick="sharePlatformWhatsApp()">📲 Enviar pelo WhatsApp</button></div></div>`;
  document.body.appendChild(modal);
}
function closePlatformAccess(){document.querySelector("#platformAccessModal")?.remove();}
async function copyPlatformUrl(){try{await navigator.clipboard.writeText(window.location.href);alert("Endereço copiado!");}catch(e){showError(e);}}
function openPlatformUrl(){window.open(window.location.href,"_blank","noopener,noreferrer");}
function sharePlatformWhatsApp(){const text=`Acesse a Central de Pesquisas: ${window.location.href}`;window.open(`https://wa.me/?text=${encodeURIComponent(text)}`,"_blank","noopener,noreferrer");}

/* =========================================================
   MENU LATERAL
   ========================================================= */

function toggleSidebar() {

  document
    .querySelector(
      "#sidebar"
    )
    ?.classList.toggle(
      "open"
    );
}
/* =========================================================
   CONFIGURAÇÕES VISUAIS
   ========================================================= */

function openCentralSettings() {

  const old = document.querySelector("#centralSettings");

  if (old) {
    old.remove();
    return;
  }

  const modal = document.createElement("div");

  modal.id = "centralSettings";

  modal.style.cssText = `
    position:fixed;
    inset:0;
    z-index:99999;
    background:rgba(0,0,0,.55);
    display:flex;
    align-items:center;
    justify-content:center;
    padding:20px;
  `;

  modal.innerHTML = `
    <div
      style="
        width:100%;
        max-width:480px;
        background:#fff;
        border-radius:22px;
        padding:25px;
        box-shadow:0 20px 60px rgba(0,0,0,.30);
      "
    >

      <div
        style="
          display:flex;
          justify-content:space-between;
          align-items:center;
          margin-bottom:20px;
        "
      >

        <h2 style="margin:0">
          ⚙️ Configurações
        </h2>

        <button
          class="btn"
          onclick="openCentralSettings()"
          style="
            width:42px;
            height:42px;
            font-size:20px;
          "
        >
          ✕
        </button>

      </div>


      <h3>🎨 Aparência</h3>

      <div
        style="
          display:grid;
          grid-template-columns:1fr 1fr;
          gap:12px;
          margin-bottom:20px;
        "
      >

        <button class="btn" onclick="setCentralTheme('claro')">☀️ Claro</button>

        <button class="btn" onclick="setCentralTheme('medio')">🌗 Médio</button>

        <button class="btn" onclick="setCentralTheme('escuro')">🌙 Escuro</button>

        <div style="grid-column:1/-1;margin-top:6px">
          <label style="display:block;font-weight:700;font-size:13px;margin-bottom:6px">🏢 Nome da empresa (aparece no cabeçalho)</label>
          <input id="rmdEmpresaNome" placeholder="Ex.: RMD Pesquisas" style="width:100%;padding:11px;border:1px solid var(--border);border-radius:10px;background:var(--card);color:var(--text)"
            oninput="rmdSalvarEmpresa(this.value)">
        </div>

      </div>


      <h3>📐 Layout</h3>

      <div
        style="
          display:flex;
          gap:10px;
          margin-bottom:20px;
        "
      >

        <button
          class="btn"
          onclick="setCentralLayout('normal')"
        >
          Normal
        </button>

        <button
          class="btn"
          onclick="setCentralLayout('compact')"
        >
          Compacto
        </button>

      </div>


      <button
        class="btn"
        style="width:100%"
        onclick="resetCentralSettings()"
      >
        ↺ Restaurar configurações
      </button>

    </div>
  `;

  document.body.appendChild(modal);
}


function setCentralTheme(theme) {

  document.body.dataset.theme = theme;

  localStorage.setItem(
    "central_theme",
    theme
  );

  openCentralSettings();
}


function setCentralLayout(layout) {

  document.body.dataset.layout = layout;

  localStorage.setItem(
    "central_layout",
    layout
  );

  openCentralSettings();
}


function resetCentralSettings() {

  localStorage.removeItem(
    "central_theme"
  );

  localStorage.removeItem(
    "central_layout"
  );

  document.body.dataset.theme = "claro";
  document.body.dataset.layout = "normal";

  openCentralSettings();
}


function loadCentralSettings() {

  const theme =
    localStorage.getItem(
      "central_theme"
    ) || "claro";

  const layout =
    localStorage.getItem(
      "central_layout"
    ) || "normal";

  document.body.dataset.theme =
    theme;

  document.body.dataset.layout =
    layout;
}

/* =========================================================
   EXPOR FUNÇÕES PARA OS BOTÕES HTML
   ========================================================= */

window.login =
  login;

window.logout =
  logout;

window.nav =
  nav;

window.refresh =
  refresh;

window.refreshUsers =
  refreshUsers;

window.openNewUserForm =
  openNewUserForm;

window.closeNewUserForm =
  closeNewUserForm;

window.createUserFromPanel =
  createUserFromPanel;

window.toggleUserActive =
  toggleUserActive;

window.changeUserRole =
  changeUserRole;

window.editUser =
  editUser;

window.openUserPermissions =
  openUserPermissions;

window.closeUserPermissions =
  closeUserPermissions;

window.saveUserPermissions =
  saveUserPermissions;

window.shareUserAccess =
  shareUserAccess;

window.deleteUserFromPanel =
  deleteUserFromPanel;

window.syncAuthenticationUsers =
  syncAuthenticationUsers;

window.setUserRoleFilter =
  setUserRoleFilter;

window.copyExistingUserAccess =
  copyExistingUserAccess;

window.copyUserAccess =
  copyUserAccess;

window.copyFullAccess =
  copyFullAccess;

window.closeCreatedUserAccess =
  closeCreatedUserAccess;

window.openSurveyForm =
  openSurveyForm;

window.closeSurveyForm =
  closeSurveyForm;

window.createSurvey =
  createSurvey;

window.toggleSurveyStatus =
  toggleSurveyStatus;

window.editSurvey =
  editSurvey;

window.deleteSurvey =
  deleteSurvey;

window.selectSurvey =
  selectSurvey;

window.manageResearcherSurveys =
  manageResearcherSurveys;

window.saveResearcherSurveys =
  saveResearcherSurveys;

window.closeResearcherSurveys =
  closeResearcherSurveys;

window.openRegionForm =
  openRegionForm;

window.closeRegionForm =
  closeRegionForm;

window.createRegion =
  createRegion;

window.editRegion =
  editRegion;

window.deleteRegion =
  deleteRegion;

window.openCongregationForm =
  openCongregationForm;

window.closeCongregationForm =
  closeCongregationForm;

window.createCongregation =
  createCongregation;

window.editCongregation =
  editCongregation;

window.deleteCongregation =
  deleteCongregation;

window.nextInterviewStep1 =
  nextInterviewStep1;

window.changeRegion =
  changeRegion;

window.chooseIntention =
  chooseIntention;

window.submitInterview =
  submitInterview;

window.openPlatformAccess =
  openPlatformAccess;

window.closePlatformAccess =
  closePlatformAccess;

window.copyPlatformUrl =
  copyPlatformUrl;

window.openPlatformUrl =
  openPlatformUrl;

window.sharePlatformWhatsApp =
  sharePlatformWhatsApp;

window.toggleSidebar =
  toggleSidebar;

window.render =
  render;

window.init =
  init;


/* =========================================================
   INICIALIZAÇÃO
   ========================================================= */
