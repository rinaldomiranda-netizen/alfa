/* Central de Pesquisas — usuários e acessos */
function openNewUserForm() {

  if (!canManageUsers()) {

    alert(
      "Somente Administrador e Coordenador podem cadastrar usuários."
    );

    return;
  }

  renderUserForm();
}

function renderUserForm() {

  const currentRole =
    state.profile?.role;

  const roleOptions = [];

  if (
    currentRole ===
    "admin"
  ) {

    roleOptions.push(`
      <option value="admin">
        👑 Administrador
      </option>
    `);

  }

  if (
    currentRole === "admin" ||
    currentRole === "coordinator"
  ) {

    roleOptions.push(`
      <option value="coordinator">
        👥 Coordenador
      </option>
    `);

  }

  roleOptions.push(`
    <option value="researcher">
      📝 Pesquisador
    </option>

    <option value="candidate">
      ⭐ Candidato
    </option>
  `);

  const oldForm =
    document.querySelector(
      "#newUserForm"
    );

  if (oldForm) {
    oldForm.remove();
  }

  const wrapper =
    document.createElement(
      "div"
    );

  wrapper.id =
    "newUserForm";

  wrapper.style.position =
    "fixed";

  wrapper.style.inset =
    "0";

  wrapper.style.zIndex =
    "9999";

  wrapper.style.background =
    "rgba(0,0,0,.55)";

  wrapper.style.display =
    "flex";

  wrapper.style.alignItems =
    "center";

  wrapper.style.justifyContent =
    "center";

  wrapper.style.padding =
    "20px";

  wrapper.innerHTML = `

    <div
      class="card"
      style="
        width:100%;
        max-width:620px;
        max-height:90vh;
        overflow:auto;
      "
    >

      <div
        class="row"
        style="margin-bottom:20px"
      >

        <div>

          <h2
            style="margin:0"
          >
            ➕ Novo usuário
          </h2>

          <p class="muted">
            Cadastre uma pessoa para acessar
            a Central de Pesquisas.
          </p>

        </div>

        <button
          class="btn small"
          onclick="
            closeNewUserForm()
          "
        >
          ✕ Fechar
        </button>

      </div>


      <div class="field">

        <label>
          Nome completo
        </label>

        <input
          id="newUserFullName"
          type="text"
          placeholder="Digite o nome completo"
          autocomplete="name"
        >

      </div>


      <div
        class="card"
        style="
          margin-top:15px;
          background:rgba(22,163,74,.08);
          border:1px solid rgba(22,163,74,.20);
        "
      >

        <strong>
          🔐 Acesso automático
        </strong>

        <p
          class="muted"
          style="margin-bottom:0"
        >
          O sistema irá gerar automaticamente
          o usuário e o código de acesso.
          Não é necessário e-mail.
        </p>

      </div>


      <div class="field">

        <label>
          Função
        </label>

        <select
          id="newUserRole"
        >

          ${roleOptions.join("")}

        </select>

      </div>


      <div
        class="card"
        style="
          margin-top:15px;
          background:rgba(0,0,0,.03);
        "
      >

        <strong>
          Permissões
        </strong>

        <p
          class="muted"
          style="margin-bottom:0"
        >

          ${
            currentRole ===
            "admin"

              ? "Você está logado como Administrador e pode criar qualquer função."

              : "Como Coordenador, você pode criar usuários, mas não pode criar Administradores."
          }

        </p>

      </div>


      <div
        class="actions"
        style="margin-top:20px"
      >

        <button
          class="btn"
          onclick="
            closeNewUserForm()
          "
        >
          CANCELAR
        </button>

        <button
          id="createUserButton"
          class="btn primary"
          onclick="
            createUserFromPanel()
          "
        >
          GERAR ACESSO
        </button>

      </div>

    </div>

  `;

  document.body.appendChild(
    wrapper
  );

  setTimeout(() => {

    document
      .querySelector(
        "#newUserFullName"
      )
      ?.focus();

  }, 100);
}


function closeNewUserForm() {

  document
    .querySelector(
      "#newUserForm"
    )
    ?.remove();

}
/* =========================================================
   CRIAR USUÁRIO
   ========================================================= */

async function createUserFromPanel() {

  const fullName =
    document
      .querySelector("#newUserFullName")
      ?.value
      .trim() || "";

  const role =
    document
      .querySelector("#newUserRole")
      ?.value || "researcher";

  if (!fullName) {

    alert(
      "Digite o nome completo."
    );

    return;
  }

  if (
    ![
      "admin",
      "coordinator",
      "researcher",
      "candidate"
    ].includes(role)
  ) {

    alert(
      "Função inválida."
    );

    return;
  }

  if (
    !canCreateRole(role)
  ) {

    alert(
      "Você não tem permissão para criar essa função."
    );

    return;
  }

  const button =
    document.querySelector(
      "#createUserButton"
    );

  if (button) {

    button.disabled =
      true;

    button.textContent =
      "GERANDO...";
  }

  try {

    /*
     * Gera o código localmente.
     *
     * O código será utilizado como senha
     * no Supabase Authentication.
     */
    const accessCode =
      String(
        Math.floor(
          100000 +
          Math.random() *
          900000
        )
      );

    /*
     * A Edge Function cria o usuário
     * no Supabase Auth e o perfil.
     *
     * Nenhum e-mail é enviado.
     */
    const {
      data,
      error
    } = await sb.functions.invoke(
      "admin-users",
      {
        body: {

          action:
            "create",

          full_name:
            fullName,

          role:
            role,

          password:
            accessCode
        }
      }
    );

    if (error) {

      console.error(
        "Erro da função admin-users:",
        error
      );

      throw new Error(
        error.message ||
        "Não foi possível gerar o acesso."
      );
    }

    if (
      !data ||
      data.error
    ) {

      throw new Error(
        data?.error ||
        "O usuário não foi criado."
      );
    }

    /*
     * Usa o código devolvido pelo servidor,
     * caso ele seja retornado.
     */
    const finalAccessCode =
      data.access_code ||
      data.accessCode ||
      accessCode;

    const username =
      data.username ||
      "";

    /*
     * GUARDA O ACESSO TEMPORARIAMENTE
     * para poder copiar novamente.
     */
    window.lastCreatedUser = {

      full_name:
        fullName,

      username:
        username,

      access_code:
        finalAccessCode,

      role:
        role
    };

    /*
     * Fecha o formulário.
     */
    closeNewUserForm();

    /*
     * Atualiza a lista.
     */
    await loadProfiles();

    render();

    /*
     * Mostra o acesso completo
     * ao administrador.
     */
    showCreatedUserAccess(
      window.lastCreatedUser
    );

  } catch (error) {

    console.error(
      "Erro ao gerar acesso:",
      error
    );

    alert(
      "Não foi possível criar o usuário.\n\n" +
      (
        error?.message ||
        "Erro desconhecido."
      )
    );

  } finally {

    const currentButton =
      document.querySelector(
        "#createUserButton"
      );

    if (currentButton) {

      currentButton.disabled =
        false;

      currentButton.textContent =
        "GERAR ACESSO";
    }
  }
}


/* =========================================================
   MOSTRAR ACESSO GERADO
   ========================================================= */

function showCreatedUserAccess(
  user
) {

  const old =
    document.querySelector(
      "#createdUserAccess"
    );

  if (old) {
    old.remove();
  }

  const wrapper =
    document.createElement(
      "div"
    );

  wrapper.id =
    "createdUserAccess";

  wrapper.style.position =
    "fixed";

  wrapper.style.inset =
    "0";

  wrapper.style.zIndex =
    "10001";

  wrapper.style.background =
    "rgba(0,0,0,.60)";

  wrapper.style.display =
    "flex";

  wrapper.style.alignItems =
    "center";

  wrapper.style.justifyContent =
    "center";

  wrapper.style.padding =
    "20px";

  wrapper.innerHTML = `

    <div
      class="card"
      style="
        width:100%;
        max-width:520px;
        text-align:center;
      "
    >

      <div
        style="
          font-size:55px;
          margin-bottom:10px;
        "
      >
        ✅
      </div>

      <h2>
        Usuário criado!
      </h2>

      <p class="muted">
        Entregue estas informações. No primeiro acesso o sistema pede para a pessoa criar o próprio código.
      </p>


      <div
        class="card"
        style="
          text-align:left;
          margin-top:20px;
          background:#f8fafc;
        "
      >

        <div
          style="
            margin-bottom:15px;
          "
        >

          <small class="muted">
            NOME
          </small>

          <div
            style="
              font-size:18px;
              font-weight:700;
            "
          >
            ${esc(user.full_name)}
          </div>

        </div>


        <div
          style="
            margin-bottom:15px;
          "
        >

          <small class="muted">
            USUÁRIO
          </small>

          <div
            style="
              display:flex;
              align-items:center;
              gap:8px;
              margin-top:4px;
            "
          >

            <strong
              style="
                font-size:20px;
                word-break:break-all;
              "
            >
              ${esc(user.username)}
            </strong>

            <button
              type="button"
              class="btn small"
              onclick="
                copyUserAccess(
                  'username'
                )
              "
            >
              📋
            </button>

          </div>

        </div>


        <div>

          <small class="muted">
            CÓDIGO DE ACESSO
          </small>

          <div
            style="
              display:flex;
              align-items:center;
              gap:8px;
              margin-top:4px;
            "
          >

            <strong
              style="
                font-size:28px;
                letter-spacing:4px;
              "
            >
              ${esc(user.access_code)}
            </strong>

            <button
              type="button"
              class="btn small"
              onclick="
                copyUserAccess(
                  'access_code'
                )
              "
            >
              📋
            </button>

          </div>

        </div>

      </div>


      <div
        class="actions"
        style="
          justify-content:center;
          margin-top:20px;
        "
      >

        <button
          type="button"
          class="btn primary"
          onclick="
            copyFullAccess()
          "
        >
          📋 COPIAR ACESSO COMPLETO
        </button>

        <button
          type="button"
          class="btn"
          onclick="
            closeCreatedUserAccess()
          "
        >
          FECHAR
        </button>

      </div>

    </div>

  `;

  document.body.appendChild(
    wrapper
  );
}


/* =========================================================
   COPIAR USUÁRIO OU CÓDIGO
   ========================================================= */

async function copyUserAccess(
  type
) {

  const user =
    window.lastCreatedUser;

  if (!user) {
    return;
  }

  const value =
    type === "username"
      ? user.username
      : user.access_code;

  try {

    await navigator.clipboard.writeText(
      value
    );

    alert(
      type === "username"
        ? "Usuário copiado!"
        : "Código de acesso copiado!"
    );

  } catch (error) {

    console.error(error);

    alert(
      value
    );
  }
}


/* =========================================================
   COPIAR ACESSO COMPLETO
   ========================================================= */

async function copyFullAccess() {

  const user =
    window.lastCreatedUser;

  if (!user) {
    return;
  }

  const text =
`ACESSO À CENTRAL DE PESQUISAS

Nome: ${user.full_name}
Usuário: ${user.username}
Código de acesso: ${user.access_code}
Função: ${roleLabel(user.role)}

Acesse a Central de Pesquisas e informe o usuário e o código de acesso.`;

  try {

    await navigator.clipboard.writeText(
      text
    );

    alert(
      "Acesso completo copiado!"
    );

  } catch (error) {

    console.error(error);

    alert(
      text
    );
  }
}


/* =========================================================
   FECHAR ACESSO GERADO
   ========================================================= */

function closeCreatedUserAccess() {

  document
    .querySelector(
      "#createdUserAccess"
    )
    ?.remove();
}


/* =========================================================
   LISTA DE USUÁRIOS
   ========================================================= */

let userRoleFilter =
  "all";

let usersCache =
  [];


/* =========================================================
   CARREGAR USUÁRIOS
   ========================================================= */

async function loadProfiles() {

  const {
    data,
    error
  } = await sb
    .from("profiles")
    .select(`
      id,
      full_name,
      username,
      must_change_code,
      role,
      active,
      created_at
    `)
    .order(
      "full_name",
      {
        ascending: true
      }
    );

  if (error) {
    throw error;
  }

  usersCache =
    data || [];

  return usersCache;
}


/* =========================================================
   FILTRO DE FUNÇÃO
   ========================================================= */

function setUserRoleFilter(
  role
) {

  userRoleFilter =
    role;

  render();
}


/* =========================================================
   ATIVAR / DESATIVAR
   ========================================================= */

async function toggleUserActive(
  userId,
  currentActive
) {

  if (!canManageUsers()) {

    alert(
      "Você não tem permissão para alterar usuários."
    );

    return;
  }

  if (
    userId ===
    state.user?.id
  ) {

    alert(
      "Você não pode desativar o usuário que está conectado."
    );

    return;
  }

  const newStatus =
    !currentActive;

  const confirmed =
    confirm(
      newStatus
        ? "Deseja ativar este usuário?"
        : "Deseja desativar este usuário?"
    );

  if (!confirmed) {
    return;
  }

  try {

    const { data, error } = await sb.functions.invoke("admin-users", {
      body: { action: "toggle", user_id: userId, active: newStatus }
    });
    if (error) throw error;
    if (!data?.success) throw new Error(data?.error || "Não foi possível alterar o status do usuário.");

    await loadProfiles();

    render();

  } catch (error) {

    showError(error);

  }
}


/* =========================================================
   ALTERAR FUNÇÃO
   ========================================================= */

async function changeUserRole(
  userId,
  currentRole
) {

  if (!canManageUsers()) {
    return;
  }

  if (
    userId ===
    state.user?.id
  ) {

    alert(
      "A função do usuário conectado não pode ser alterada."
    );

    return;
  }

  const newRole =
    prompt(
      "Digite a nova função:\n\n" +
      "admin\n" +
      "coordinator\n" +
      "researcher\n" +
      "candidate",
      currentRole
    );

  if (!newRole) {
    return;
  }

  const normalized =
    newRole
      .trim()
      .toLowerCase();

  if (
    ![
      "admin",
      "coordinator",
      "researcher",
      "candidate"
    ].includes(
      normalized
    )
  ) {

    alert(
      "Função inválida."
    );

    return;
  }

  if (
    state.profile?.role ===
      "coordinator" &&
    normalized ===
      "admin"
  ) {

    alert(
      "O Coordenador não pode criar ou promover um Administrador."
    );

    return;
  }

  try {

    const { data, error } = await sb.functions.invoke("admin-users", {
      body: { action: "update", user_id: userId, role: normalized }
    });
    if (error) throw error;
    if (!data?.success) throw new Error(data?.error || "Não foi possível alterar a função.");

    await loadProfiles();

    render();

  } catch (error) {

    showError(error);

  }
}



/* =========================================================
   EDITAR / RESETAR USUÁRIO
   ========================================================= */
async function editUser(userId) {
  if (!canManageUsers()) return alert("Você não tem permissão para editar usuários.");
  const user = usersCache?.find(u => u.id === userId);
  if (!user) return alert("Usuário não encontrado.");
  const fullName = prompt("Nome completo:", user.full_name || "");
  if (fullName === null) return;
  const username = prompt("Usuário de acesso:", user.username || "");
  if (username === null) return;
  const resetar = confirm("A pessoa esqueceu o código?\n\nOK = voltar o código para o inicial (ela cria um novo no próximo acesso)\nCancelar = manter o código atual");
  try {
    const { data, error } = await sb.functions.invoke("admin-users", { body: { action: "update", user_id: userId, full_name: fullName.trim(), username: username.trim().toLowerCase() } });
    if (error) throw new Error(await cpErroFuncao(error));
    if (!data?.success) throw new Error(data?.error || "Não foi possível atualizar o usuário.");
    if (resetar) {
      const r = await sb.functions.invoke("admin-users", { body: { action: "reset_code", user_id: userId } });
      if (r.error) throw new Error(await cpErroFuncao(r.error));
      if (!r.data?.success) throw new Error(r.data?.error || "Não foi possível voltar o código.");
    }
    await loadProfiles(); render();
    alert(resetar ? "Usuário atualizado.\n\nCódigo de acesso voltou para o inicial: " + (CP_CODIGO_INICIAL) + "\nNo próximo acesso a pessoa cria o próprio código." : "Usuário atualizado com sucesso!");
  } catch (error) { showError(error); }
}

/* =========================================================
   EXCLUIR USUÁRIO
   ========================================================= */

async function deleteUserFromPanel(
  userId
) {

  if (!canManageUsers()) {
    return;
  }

  if (
    userId ===
    state.user?.id
  ) {

    alert(
      "Você não pode excluir o usuário conectado."
    );

    return;
  }

  const userName = usersCache?.find?.(u => u.id === userId)?.full_name || "Usuário";

  const confirmed =
    confirm(
      `Deseja realmente excluir o usuário "${userName}"?`
    );

  if (!confirmed) {
    return;
  }

  try {

    const {
      data,
      error
    } = await sb.functions.invoke(
      "admin-users",
      {
        body: {
          action:
            "delete",
          user_id:
            userId
        }
      }
    );

    if (error) {
      throw error;
    }

    if (data?.error) {
      throw new Error(
        data.error
      );
    }

    await loadProfiles();

    render();

    alert(
      "Usuário excluído com sucesso."
    );

  } catch (error) {

    showError(error);

  }
}


/* =========================================================
   SINCRONIZAR USUÁRIOS
   ========================================================= */

async function syncAuthenticationUsers() {

  if (!canManageUsers()) {
    return;
  }

  const confirmed =
    confirm(
      "Deseja sincronizar os usuários do Authentication com os perfis?"
    );

  if (!confirmed) {
    return;
  }

  try {

    const {
      data,
      error
    } = await sb.functions.invoke(
      "admin-users",
      {
        body: {
          action:
            "sync"
        }
      }
    );

    if (error) {
      throw error;
    }

    if (data?.error) {
      throw new Error(
        data.error
      );
    }

    await loadProfiles();

    render();

    alert(
      data?.message ||
      "Sincronização concluída."
    );

  } catch (error) {

    showError(error);

  }
}
/* =========================================================
   PÁGINA DE USUÁRIOS
   ========================================================= */

async function usersPage() {

  if (!canManageUsers()) {

    return `
      <div class="card">

        <h1>
          Acesso restrito
        </h1>

        <p class="muted">
          Somente Administrador e Coordenador
          podem administrar usuários.
        </p>

      </div>
    `;
  }

  let users = [];

  try {

    users =
      await loadProfiles();

  } catch (error) {

    console.error(
      "Erro ao carregar usuários:",
      error
    );

    return `
      <div class="card">

        <h2>
          Erro ao carregar usuários
        </h2>

        <p class="muted">
          ${esc(
            error?.message ||
            "Não foi possível carregar a lista."
          )}
        </p>

        <button
          class="btn primary"
          onclick="refreshUsers()"
        >
          ↻ TENTAR NOVAMENTE
        </button>

      </div>
    `;
  }


  const counts = {

    all:
      users.length,

    admin:
      users.filter(
        u =>
          u.role === "admin"
      ).length,

    coordinator:
      users.filter(
        u =>
          u.role === "coordinator"
      ).length,

    candidate:
      users.filter(
        u =>
          u.role === "candidate"
      ).length,

    researcher:
      users.filter(
        u =>
          u.role === "researcher"
      ).length
  };


  const filtered =
    userRoleFilter === "all"
      ? users
      : users.filter(
          u =>
            u.role ===
            userRoleFilter
        );


  return `

    <div
      class="grid"
      style="gap:20px"
    >

      <!-- CABEÇALHO -->

      <div class="card">

        <div class="row">

          <div>

            <h1>
              Usuários e permissões
            </h1>

            <p class="muted">
              Gerencie as pessoas que têm acesso
              à Central de Pesquisas.
            </p>

          </div>


          <div
            class="actions"
            style="
              flex-wrap:wrap;
            "
          >

            <button
              class="btn small"
              onclick="
                syncAuthenticationUsers()
              "
            >
              🔄 Sincronizar
            </button>


            <button
              class="btn small"
              onclick="
                refreshUsers()
              "
            >
              ↻ Atualizar
            </button>


            <button
              class="btn primary"
              onclick="
                openNewUserForm()
              "
            >
              ➕ NOVO USUÁRIO
            </button>

          </div>

        </div>

      </div>


      <!-- RESUMO -->

      <div
        class="grid stats"
      >

        <button
          class="card stat"
          type="button"
          onclick="
            setUserRoleFilter('all')
          "
        >

          <span>
            👤 TODOS
          </span>

          <strong>
            ${fmt(counts.all)}
          </strong>

          <span>
            Usuários cadastrados
          </span>

        </button>


        <button
          class="card stat"
          type="button"
          onclick="
            setUserRoleFilter('admin')
          "
        >

          <span>
            👑 ADMINISTRADORES
          </span>

          <strong>
            ${fmt(counts.admin)}
          </strong>

          <span>
            Controle geral
          </span>

        </button>


        <button
          class="card stat"
          type="button"
          onclick="
            setUserRoleFilter('coordinator')
          "
        >

          <span>
            👥 COORDENADORES
          </span>

          <strong>
            ${fmt(counts.coordinator)}
          </strong>

          <span>
            Administração
          </span>

        </button>


        <button
          class="card stat"
          type="button"
          onclick="
            setUserRoleFilter('researcher')
          "
        >

          <span>
            📝 PESQUISADORES
          </span>

          <strong>
            ${fmt(counts.researcher)}
          </strong>

          <span>
            Entrevistas
          </span>

        </button>


        <button
          class="card stat"
          type="button"
          onclick="
            setUserRoleFilter('candidate')
          "
        >

          <span>
            ⭐ CANDIDATOS
          </span>

          <strong>
            ${fmt(counts.candidate)}
          </strong>

          <span>
            Visualização
          </span>

        </button>

      </div>


      <!-- LISTA -->

      <div class="card">

        <div
          class="row"
          style="
            margin-bottom:18px;
          "
        >

          <div>

            <h2>
              ${
                userRoleFilter === "all"
                  ? "Todos os usuários"
                  : roleLabel(
                      userRoleFilter
                    )
              }
            </h2>

            <p class="muted">
              Lista completa de pessoas cadastradas
              no sistema.
            </p>

          </div>


          <span class="badge">

            ${filtered.length}

            ${
              filtered.length === 1
                ? " usuário"
                : " usuários"
            }

          </span>

        </div>


        <div
          style="
            overflow-x:auto;
          "
        >

          <table
            style="
              width:100%;
              min-width:1050px;
            "
          >

            <thead>

              <tr>

                <th>
                  Nome
                </th>

                <th>
                  Usuário
                </th>

                <th>
                  Código de acesso
                </th>

                <th>
                  Função
                </th>

                <th>
                  Status
                </th>

                <th>
                  Criado em
                </th>

                <th>
                  Ações
                </th>

              </tr>

            </thead>


            <tbody>

              ${
                filtered.length

                  ? filtered
                      .map(user => {

                        const active =
                          user.active !== false;

                        const created =
                          user.created_at
                            ? new Date(
                                user.created_at
                              ).toLocaleString(
                                "pt-BR"
                              )
                            : "-";

                        const isSelf =
                          user.id ===
                          state.user?.id;

                        const username =
                          user.username ||
                          "—";

                        const accessCode =
                          user.must_change_code
                            ? "🔑 Inicial — troca no 1º acesso"
                            : "🔒 Pessoal (só a pessoa sabe)";


                        return `

                          <tr>

                            <!-- NOME -->

                            <td>

                              <strong>
                                ${esc(
                                  user.full_name ||
                                  "Sem nome"
                                )}
                              </strong>


                              ${
                                isSelf

                                  ? `
                                    <span
                                      class="badge green"
                                      style="
                                        margin-left:6px;
                                      "
                                    >
                                      VOCÊ
                                    </span>
                                  `

                                  : ""
                              }

                            </td>


                            <!-- USUÁRIO -->

                            <td>

                              <div
                                style="
                                  display:flex;
                                  align-items:center;
                                  gap:6px;
                                "
                              >

                                <code>
                                  ${esc(
                                    username
                                  )}
                                </code>


                                ${
                                  username !== "—"

                                    ? `
                                      <button
                                        type="button"
                                        class="btn small"
                                        title="Copiar usuário"
                                        onclick="
                                          copyExistingUserAccess(
                                            '${user.id}',
                                            'username'
                                          )
                                        "
                                      >
                                        📋
                                      </button>
                                    `

                                    : ""
                                }

                              </div>

                            </td>


                            <!-- CÓDIGO -->

                            <td>

                              <div
                                style="
                                  display:flex;
                                  align-items:center;
                                  gap:6px;
                                "
                              >

                                <strong
                                  style="
                                    letter-spacing:2px;
                                  "
                                >
                                  ${esc(
                                    accessCode
                                  )}
                                </strong>


                                ${
                                  false

                                    ? `
                                      <button
                                        type="button"
                                        class="btn small"
                                        title="Copiar código"
                                        onclick="
                                          copyExistingUserAccess(
                                            '${user.id}',
                                            'access_code'
                                          )
                                        "
                                      >
                                        📋
                                      </button>
                                    `

                                    : ""
                                }

                              </div>

                            </td>


                            <!-- FUNÇÃO -->

                            <td>

                              ${roleIcon(
                                user.role
                              )}

                              ${esc(
                                roleLabel(
                                  user.role
                                )
                              )}

                            </td>


                            <!-- STATUS -->

                            <td>

                              ${
                                active

                                  ? `
                                    <span
                                      class="badge green"
                                    >
                                      ATIVO
                                    </span>
                                  `

                                  : `
                                    <span
                                      class="badge red"
                                    >
                                      INATIVO
                                    </span>
                                  `
                              }

                            </td>


                            <!-- DATA -->

                            <td>
                              ${esc(
                                created
                              )}
                            </td>


                            <!-- AÇÕES -->

                            <td>

                              <div
                                class="actions"
                                style="
                                  flex-wrap:wrap;
                                "
                              >

                                ${
                                  !isSelf

                                    ? `

                                      <button type="button" class="btn small" onclick="editUser('${user.id}')">✏️ Editar</button>

                                      <button
                                        type="button"
                                        class="btn small"
                                        onclick="
                                          toggleUserActive(
                                            '${user.id}',
                                            ${active}
                                          )
                                        "
                                      >
                                        ${
                                          active
                                            ? "Desativar"
                                            : "Ativar"
                                        }
                                      </button>


                                      <button
                                        type="button"
                                        class="btn small"
                                        onclick="
                                          changeUserRole(
                                            '${user.id}',
                                            '${user.role}'
                                          )
                                        "
                                      >
                                        ⚙ Função
                                      </button>


                                      ${
                                        user.role ===
                                        "researcher"

                                          ? `
                                            <button
                                              type="button"
                                              class="btn small"
                                              onclick="
                                                manageResearcherSurveys(
                                                  '${user.id}',
                                                  ${htmlJsArg(
                                                    user.full_name ||
                                                    "Pesquisador"
                                                  )}
                                                )
                                              "
                                            >
                                              🎯 Pesquisas
                                            </button>
                                          `

                                          : ""
                                      }


                                      <button
                                        type="button"
                                        class="btn small primary"
                                        onclick="openUserPermissions('${user.id}', ${htmlJsArg(user.full_name || "Usuário")})"
                                      >
                                        🔐 Acesso
                                      </button>

                                      <button
                                        type="button"
                                        class="btn small"
                                        onclick="shareUserAccess('${user.id}')"
                                      >
                                        📲 WhatsApp
                                      </button>

                                      <button
                                        type="button"
                                        class="btn small"
                                        onclick="
                                          deleteUserFromPanel('${user.id}')
                                        "
                                      >
                                        🗑 Excluir
                                      </button>

                                    `

                                    : `

                                      <span
                                        class="muted"
                                      >
                                        Usuário atual
                                      </span>

                                    `
                                }

                              </div>

                            </td>

                          </tr>

                        `;

                      })
                      .join("")

                  : `

                    <tr>

                      <td
                        colspan="7"
                        style="
                          text-align:center;
                          padding:40px;
                        "
                      >

                        <div
                          style="
                            font-size:40px;
                            margin-bottom:10px;
                          "
                        >
                          👤
                        </div>

                        <strong>
                          Nenhum usuário encontrado.
                        </strong>

                        <p class="muted">
                          Clique em
                          <b>+ NOVO USUÁRIO</b>
                          para cadastrar uma pessoa.
                        </p>

                      </td>

                    </tr>

                  `
              }

            </tbody>

          </table>

        </div>

      </div>

    </div>
  `;
}


/* =========================================================
   COPIAR DADOS DE USUÁRIO JÁ CADASTRADO
   ========================================================= */

async function copyExistingUserAccess(
  userId,
  type
) {

  try {

    const user =
      usersCache.find(
        item =>
          item.id === userId
      );

    if (!user) {

      throw new Error(
        "Usuário não encontrado."
      );

    }

    const value =
      type === "username"
        ? user.username
        : user.access_code;

    if (!value) {

      throw new Error(
        "Este usuário não possui essa informação cadastrada."
      );

    }

    await navigator.clipboard.writeText(
      String(value)
    );

    alert(
      type === "username"
        ? "Usuário copiado!"
        : "Código de acesso copiado!"
    );

  } catch (error) {

    console.error(
      error
    );

    alert(
      error?.message ||
      "Não foi possível copiar."
    );

  }
}


/* =========================================================
   ATUALIZAR LISTA DE USUÁRIOS
   ========================================================= */

async function refreshUsers() {

  if (!canManageUsers()) {

    alert(
      "Você não tem permissão para administrar usuários."
    );

    return;
  }

  try {

    await loadProfiles();

    render();

  } catch (error) {

    showError(error);

  }
}


/* =========================================================
   PESQUISAS DO PESQUISADOR
   ========================================================= */

async function manageResearcherSurveys(
  researcherId,
  researcherName
) {

  if (!canManageUsers()) {

    alert(
      "Você não tem permissão para administrar pesquisas."
    );

    return;
  }

  try {

    /*
     * Busca todas as pesquisas.
     */
    const {
      data: surveys,
      error: surveysError
    } = await sb
      .from("surveys")
      .select("*").is("deleted_at", null)
      .order(
        "created_at",
        {
          ascending: false
        }
      );

    if (surveysError) {
      throw surveysError;
    }


    /*
     * Busca as permissões atuais do pesquisador.
     *
     * A tabela correta é survey_access.
     */
    const {
      data: access,
      error: accessError
    } = await sb
      .from("survey_access")
      .select(
        "survey_id, can_view"
      )
      .eq(
        "user_id",
        researcherId
      );

    if (accessError) {
      throw accessError;
    }


    const assignedIds =
      new Set(
        (access || [])
          .filter(
            item =>
              item.can_view !== false
          )
          .map(
            item =>
              item.survey_id
          )
      );


    const wrapper =
      document.createElement(
        "div"
      );

    wrapper.id =
      "researcherSurveyModal";

    wrapper.style.position =
      "fixed";

    wrapper.style.inset =
      "0";

    wrapper.style.zIndex =
      "10000";

    wrapper.style.background =
      "rgba(0,0,0,.60)";

    wrapper.style.display =
      "flex";

    wrapper.style.alignItems =
      "center";

    wrapper.style.justifyContent =
      "center";

    wrapper.style.padding =
      "20px";


    wrapper.innerHTML = `

      <div
        class="card"
        style="
          width:100%;
          max-width:700px;
          max-height:90vh;
          overflow:auto;
        "
      >

        <div
          class="row"
          style="
            align-items:center;
            margin-bottom:20px;
          "
        >

          <div>

            <h2>
              🎯 Pesquisas do pesquisador
            </h2>

            <p class="muted">
              ${esc(
                researcherName
              )}
            </p>

          </div>


          <button
            type="button"
            class="btn small"
            onclick="
              closeResearcherSurveys()
            "
          >
            ✕
          </button>

        </div>


        <div
          class="card"
          style="
            background:#f8fafc;
          "
        >

          <h3>
            Pesquisas autorizadas
          </h3>

          <p class="muted">
            Marque somente as pesquisas que este
            pesquisador poderá realizar.
          </p>


          ${
            surveys &&
            surveys.length

              ? surveys
                  .map(
                    survey => {

                      const checked =
                        assignedIds.has(
                          survey.id
                        );

                      const candidate =
                        survey.candidate_name ||
                        survey.name ||
                        "Pesquisa";

                      const status =
                        survey.status ||
                        "active";

                      return `

                        <label
                          style="
                            display:flex;
                            align-items:center;
                            gap:12px;
                            padding:14px;
                            margin-top:10px;
                            border:1px solid #e5e7eb;
                            border-radius:10px;
                            cursor:pointer;
                            background:#fff;
                          "
                        >

                          <input
                            type="checkbox"
                            class="researcher-survey-check"
                            value="${survey.id}"
                            ${
                              checked
                                ? "checked"
                                : ""
                            }
                            style="
                              width:18px;
                              height:18px;
                            "
                          >


                          <div>

                            <strong>
                              ${esc(
                                candidate
                              )}
                            </strong>

                            <div
                              class="muted"
                              style="
                                margin-top:4px;
                              "
                            >

                              ${esc(
                                survey.office ||
                                ""
                              )}

                              ·

                              ${
                                status === "active"
                                  ? "ATIVA"
                                  : status === "paused"
                                  ? "PAUSADA"
                                  : "ARQUIVADA"
                              }

                            </div>

                          </div>

                        </label>

                      `;

                    }
                  )
                  .join("")

              : `

                <div
                  style="
                    padding:25px;
                    text-align:center;
                  "
                >

                  <div
                    style="
                      font-size:42px;
                    "
                  >
                    🎯
                  </div>

                  <p>
                    Nenhuma pesquisa cadastrada.
                  </p>

                  <p class="muted">
                    Cadastre uma pesquisa antes
                    de atribuí-la ao pesquisador.
                  </p>

                </div>

              `
          }

        </div>


        <div
          class="actions"
          style="
            justify-content:flex-end;
            margin-top:20px;
          "
        >

          <button
            type="button"
            class="btn"
            onclick="
              closeResearcherSurveys()
            "
          >
            CANCELAR
          </button>


          <button
            type="button"
            id="saveResearcherSurveysButton"
            class="btn primary"
            onclick="
              saveResearcherSurveys(
                '${researcherId}'
              )
            "
          >
            💾 SALVAR ATRIBUIÇÕES
          </button>

        </div>

      </div>

    `;

    document.body.appendChild(
      wrapper
    );

  } catch (error) {

    console.error(
      "ERRO AO CARREGAR PESQUISAS:",
      error
    );

    showError(error);
  }
}


/* =========================================================
   SALVAR PESQUISAS DO PESQUISADOR
   ========================================================= */

async function saveResearcherSurveys(
  researcherId
) {

  if (!canManageUsers()) {

    alert(
      "Você não tem permissão."
    );

    return;
  }

  const button =
    document.querySelector(
      "#saveResearcherSurveysButton"
    );

  try {

    if (button) {

      button.disabled =
        true;

      button.textContent =
        "SALVANDO...";
    }


    /*
     * Captura somente as pesquisas
     * marcadas pelo administrador.
     */
    const selected =
      Array.from(
        document.querySelectorAll(
          ".researcher-survey-check:checked"
        )
      ).map(
        checkbox =>
          checkbox.value
      );


    /*
     * Busca as permissões existentes.
     */
    const {
      data: existing,
      error: existingError
    } = await sb
      .from("survey_access")
      .select(
        "id, survey_id"
      )
      .eq(
        "user_id",
        researcherId
      );

    if (existingError) {
      throw existingError;
    }


    const existingMap =
      new Map(
        (existing || [])
          .map(
            item => [
              item.survey_id,
              item.id
            ]
          )
      );


    /*
     * Desativa permissões antigas.
     *
     * Não apagamos o histórico.
     */
    const {
      error: disableError
    } = await sb
      .from("survey_access")
      .update({
        can_view:
          false
      })
      .eq(
        "user_id",
        researcherId
      );

    if (disableError) {
      throw disableError;
    }


    /*
     * Reativa ou cria as selecionadas.
     */
    for (
      const surveyId of selected
    ) {

      const existingId =
        existingMap.get(
          surveyId
        );


      if (existingId) {

        const {
          error
        } = await sb
          .from("survey_access")
          .update({
            can_view: true
          })
          .eq(
            "id",
            existingId
          );

        if (error) {
          throw error;
        }

      } else {

        const {
          error
        } = await sb
          .from("survey_access")
          .insert({
            user_id:
              researcherId,

            survey_id:
              surveyId,

            can_view:
              true,
            can_create_interview:
              true,
            can_export:
              false,
            can_manage_users:
              false
          });

        if (error) {
          throw error;
        }
      }
    }


    closeResearcherSurveys();

    alert(
      "Pesquisas do pesquisador atualizadas com sucesso."
    );


    /*
     * Se estamos editando o usuário conectado,
     * recarrega imediatamente suas permissões.
     */
    if (
      researcherId ===
      state.user?.id
    ) {

      await loadSurveyData();

      render();

    }

  } catch (error) {

    console.error(
      "ERRO AO SALVAR ATRIBUIÇÕES:",
      error
    );

    showError(error);

    if (button) {

      button.disabled =
        false;

      button.textContent =
        "💾 SALVAR ATRIBUIÇÕES";

    }
  }
}


/* =========================================================
   FECHAR MODAL DE PESQUISAS
   ========================================================= */

function closeResearcherSurveys() {

  document
    .querySelector(
      "#researcherSurveyModal"
    )
    ?.remove();
}
/* =========================================================
   PESQUISAS
   ========================================================= */

