/* Central de Pesquisas — pesquisas */
async function surveysPage() {

  if (!canManageUsers()) {

    return `
      <div class="card">

        <h1>
          Acesso restrito
        </h1>

        <p class="muted">
          Somente Administrador e Coordenador
          podem administrar pesquisas.
        </p>

      </div>
    `;
  }

  let surveys = [];

  try {

    const {
      data,
      error
    } = await sb
      .from("surveys")
      .select("*").is("deleted_at", null)
      .order(
        "created_at",
        {
          ascending: false
        }
      );

    if (error) {
      throw error;
    }

    surveys =
      data || [];

  } catch (error) {

    console.error(
      "Erro ao carregar pesquisas:",
      error
    );

    return `
      <div class="card">

        <h2>
          Erro ao carregar pesquisas
        </h2>

        <p class="muted">
          ${esc(
            error?.message ||
            "Erro desconhecido."
          )}
        </p>

        <button
          type="button"
          class="btn primary"
          onclick="refresh()"
        >
          ↻ TENTAR NOVAMENTE
        </button>

      </div>
    `;
  }


  return `

    <div
      class="grid"
      style="gap:20px"
    >

      <!-- CABEÇALHO -->

      <div class="card">

        <div
          class="row"
          style="
            align-items:center;
            gap:20px;
          "
        >

          <div>

            <h1>
              Pesquisas
            </h1>

            <p class="muted">
              Cadastre e controle as pesquisas
              disponíveis na Central.
            </p>

          </div>

          <button
            type="button"
            class="btn primary"
            onclick="openSurveyForm()"
          >
            ➕ NOVA PESQUISA
          </button>

        </div>

      </div>


      <!-- LISTA -->

      <div class="card">

        <div
          style="
            width:100%;
            overflow-x:auto;
          "
        >

          <table
            style="
              width:100%;
              min-width:750px;
            "
          >

            <thead>

              <tr>

                <th>
                  Pesquisa
                </th>

                <th>
                  Cargo
                </th>

                <th>
                  Descrição
                </th>

                <th>
                  Status
                </th>

                <th>
                  Ações
                </th>

              </tr>

            </thead>

            <tbody>

              ${
                surveys.length

                  ? surveys
                      .map(
                        survey => {

                          const name =
                            survey.candidate_name ||
                            survey.name ||
                            "Pesquisa";

                          let statusLabel =
                            "ARQUIVADA";

                          let statusClass =
                            "";

                          if (
                            survey.status ===
                            "active"
                          ) {

                            statusLabel =
                              "ATIVA";

                            statusClass =
                              "green";

                          } else if (
                            survey.status ===
                            "paused"
                          ) {

                            statusLabel =
                              "PAUSADA";

                          }


                          return `

                            <tr>

                              <td>

                                <strong>
                                  ${esc(name)}
                                </strong>

                              </td>


                              <td>

                                ${esc(
                                  survey.office ||
                                  "-"
                                )}

                              </td>


                              <td>

                                <span
                                  class="muted"
                                >
                                  ${esc(
                                    survey.description ||
                                    "-"
                                  )}
                                </span>

                              </td>


                              <td>

                                <span
                                  class="badge ${statusClass}"
                                >
                                  ${statusLabel}
                                </span>

                              </td>


                              <td>

                                <div
                                  class="actions"
                                  style="
                                    flex-wrap:wrap;
                                  "
                                >

                                  ${
                                    survey.status ===
                                    "active"

                                      ? `
                                        <button
                                          type="button"
                                          class="btn small"
                                          onclick="
                                            toggleSurveyStatus(
                                              '${survey.id}',
                                              'active'
                                            )
                                          "
                                        >
                                          ⏸ PAUSAR
                                        </button>
                                      `

                                      : survey.status ===
                                        "paused"

                                      ? `
                                        <button
                                          type="button"
                                          class="btn small primary"
                                          onclick="
                                            toggleSurveyStatus(
                                              '${survey.id}',
                                              'paused'
                                            )
                                          "
                                        >
                                          ▶ ATIVAR
                                        </button>
                                      `

                                      : ""
                                  }


                                  <button
                                    type="button"
                                    class="btn small"
                                    onclick="editSurvey('${survey.id}')"
                                  >
                                    ✏️ EDITAR
                                  </button>

                                  <button
                                    type="button"
                                    class="btn small"
                                    onclick="deleteSurvey('${survey.id}')"
                                  >
                                    🗑 EXCLUIR
                                  </button>

                                </div>

                              </td>

                            </tr>

                          `;

                        }
                      )
                      .join("")

                  : `

                    <tr>

                      <td
                        colspan="5"
                        style="
                          text-align:center;
                          padding:35px;
                        "
                      >

                        <div
                          style="
                            font-size:42px;
                          "
                        >
                          🎯
                        </div>

                        <strong>
                          Nenhuma pesquisa cadastrada.
                        </strong>

                        <p class="muted">
                          Clique em
                          <b>+ NOVA PESQUISA</b>
                          para começar.
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
   NOVA PESQUISA
   ========================================================= */

function openSurveyForm() {

  const old =
    document.querySelector(
      "#surveyForm"
    );

  if (old) {
    old.remove();
  }


  const wrapper =
    document.createElement(
      "div"
    );

  wrapper.id =
    "surveyForm";

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
        max-width:600px;
      "
    >

      <div
        class="row"
        style="
          margin-bottom:20px;
        "
      >

        <h2>
          ➕ Nova pesquisa
        </h2>

        <button
          type="button"
          class="btn small"
          onclick="
            closeSurveyForm()
          "
        >
          ✕
        </button>

      </div>


      <div class="field">

        <label>
          Nome do candidato
        </label>

        <input
          id="surveyCandidate"
          type="text"
          placeholder="Nome do candidato"
        >

      </div>


      <div class="field">

        <label>
          Cargo
        </label>

        <input
          id="surveyOffice"
          type="text"
          placeholder="Ex.: Deputado Estadual"
        >

      </div>


      <div class="field">

        <label>
          Descrição
        </label>

        <textarea
          id="surveyDescription"
          placeholder="Descrição da pesquisa"
        ></textarea>

      </div>


      <div class="actions">

        <button
          type="button"
          class="btn"
          onclick="
            closeSurveyForm()
          "
        >
          CANCELAR
        </button>


        <button
          type="button"
          id="saveSurveyButton"
          class="btn primary"
          onclick="
            createSurvey()
          "
        >
          CRIAR PESQUISA
        </button>

      </div>

    </div>

  `;


  document.body.appendChild(
    wrapper
  );


  document
    .querySelector(
      "#surveyCandidate"
    )
    ?.focus();
}


/* =========================================================
   FECHAR PESQUISA
   ========================================================= */

function closeSurveyForm() {

  document
    .querySelector(
      "#surveyForm"
    )
    ?.remove();
}


/* =========================================================
   CRIAR PESQUISA
   ========================================================= */

async function createSurvey() {

  if (!canManageUsers()) {

    alert(
      "Você não tem permissão para criar pesquisas."
    );

    return;
  }


  const candidate =
    document
      .querySelector(
        "#surveyCandidate"
      )
      ?.value
      .trim();


  const office =
    document
      .querySelector(
        "#surveyOffice"
      )
      ?.value
      .trim();


  const description =
    document
      .querySelector(
        "#surveyDescription"
      )
      ?.value
      .trim();


  if (!candidate) {

    alert(
      "Digite o nome do candidato."
    );

    return;
  }


  if (!office) {

    alert(
      "Digite o cargo."
    );

    return;
  }


  const button =
    document.querySelector(
      "#saveSurveyButton"
    );


  if (button) {

    button.disabled =
      true;

    button.textContent =
      "CRIANDO...";
  }


  try {

    /*
     * IMPORTANTE:
     * name é obrigatório na tabela surveys.
     *
     * candidate_name também é preenchido
     * para manter compatibilidade com a interface.
     */
    const {
      data,
      error
    } = await sb
      .from("surveys")
      .insert({

        name:
          candidate,

        candidate_name:
          candidate,

        office:
          office,

        description:
          description ||
          null,

        status:
          "active"

      })
      .select()
      .single();


    if (error) {
      throw error;
    }


    closeSurveyForm();


    await loadSurveyData();


    /*
     * Seleciona automaticamente
     * a pesquisa recém-criada.
     */
    if (data) {

      state.survey =
        data;

      await loadSurveyData();

    }


    render();


    alert(
      "Pesquisa criada com sucesso!"
    );


  } catch (error) {

    console.error(
      "ERRO AO CRIAR PESQUISA:",
      error
    );


    showError(error);


    if (button) {

      button.disabled =
        false;

      button.textContent =
        "CRIAR PESQUISA";

    }
  }
}


/* =========================================================
   ALTERAR STATUS DA PESQUISA
   ========================================================= */

async function toggleSurveyStatus(
  surveyId,
  currentStatus
) {

  if (!canManageUsers()) {

    alert(
      "Você não tem permissão para alterar pesquisas."
    );

    return;
  }


  const newStatus =
    currentStatus === "active"
      ? "paused"
      : "active";


  const question =
    currentStatus === "active"

      ? "Deseja pausar esta pesquisa?"

      : "Deseja ativar esta pesquisa novamente?";


  if (!confirm(question)) {
    return;
  }


  try {

    const {
      error
    } = await sb
      .from("surveys")
      .update({
        status:
          newStatus
      })
      .eq(
        "id",
        surveyId
      );


    if (error) {
      throw error;
    }


    /*
     * Se a pesquisa atual foi pausada,
     * o pesquisador não poderá mais
     * utilizá-la.
     */
    if (
      state.survey?.id ===
      surveyId
    ) {

      state.survey =
        null;

    }


    await loadSurveyData();

    render();


  } catch (error) {

    showError(error);

  }
}


/* =========================================================
   EXCLUIR PESQUISA
   ========================================================= */

async function deleteSurvey(
  surveyId
) {

  if (!canManageUsers()) {

    alert(
      "Você não tem permissão para excluir pesquisas."
    );

    return;
  }


  const surveyName = state.surveys?.find?.(s => s.id === surveyId)?.candidate_name ||
    state.surveys?.find?.(s => s.id === surveyId)?.name || "Pesquisa";

  const confirmed =
    confirm(
      `ATENÇÃO!

Deseja excluir definitivamente a pesquisa:

"${surveyName}"?

Essa ação poderá remover também
os dados relacionados a ela.`
    );


  if (!confirmed) {
    return;
  }


  try {

    const { data: deleted, error } = await sb.functions.invoke("admin-users", { body: { action: "delete_survey", survey_id: surveyId } });
    if (error) throw new Error(await cpErroFuncao(error));
    if (!deleted?.success) throw new Error(deleted?.error || "Não foi possível mover para a lixeira.");


    if (
      state.survey?.id ===
      surveyId
    ) {

      state.survey =
        null;

    }


    await loadSurveyData();

    render();


    alert(
      "Pesquisa enviada para a lixeira. Dá para restaurar em até 30 dias."
    );


  } catch (error) {

    console.error(
      "ERRO AO EXCLUIR PESQUISA:",
      error
    );

    showError(error);

  }
}



/* =========================================================
   EDIÇÃO DE PESQUISA
   ========================================================= */
async function editSurvey(surveyId) {
  if (!canManageUsers()) return alert("Você não tem permissão para editar pesquisas.");
  const survey = state.surveys?.find(s => s.id === surveyId);
  if (!survey) return alert("Pesquisa não encontrada.");
  const candidate = prompt("Nome da pesquisa/candidato:", survey.candidate_name || survey.name || "");
  if (candidate === null) return;
  const office = prompt("Cargo:", survey.office || "");
  if (office === null) return;
  const description = prompt("Descrição:", survey.description || "");
  if (description === null) return;
  try {
    const { data, error } = await sb.from("surveys").update({
      name: candidate.trim(), candidate_name: candidate.trim(), office: office.trim(), description: description.trim() || null
    }).eq("id", surveyId).select("id").maybeSingle();
    if (error) throw error;
    if (!data) throw new Error("A pesquisa não foi atualizada. Verifique suas permissões no Supabase.");
    await loadSurveyData(); render(); alert("Pesquisa atualizada com sucesso!");
  } catch (error) { showError(error); }
}

/* =========================================================
   EDIÇÃO DE REGIÃO
   ========================================================= */
async function editRegion(id) {
  if (!canManageUsers()) return alert("Você não tem permissão para editar regiões.");
  const item = state.regions?.find(r => r.id === id);
  if (!item) return alert("Região não encontrada.");
  const name = prompt("Nome da região:", item.name || "");
  if (name === null) return;
  const value = name.trim();
  if (!value) return alert("Informe o nome da região.");
  try {
    const { data, error } = await sb.from("regions").update({ name: value }).eq("id", id).select("id").maybeSingle();
    if (error) throw error;
    if (!data) throw new Error("A região não foi atualizada. Verifique suas permissões.");
    await loadSurveyData(); render();
  } catch (error) { showError(error); }
}

/* =========================================================
   EDIÇÃO DE CONGREGAÇÃO
   ========================================================= */
async function editCongregation(id) {
  if (!canManageUsers()) return alert("Você não tem permissão para editar congregações.");
  const item = state.congregations?.find(c => c.id === id);
  if (!item) return alert("Congregação não encontrada.");
  const name = prompt("Nome da congregação:", item.name || "");
  if (name === null) return;
  const value = name.trim();
  if (!value) return alert("Informe o nome da congregação.");
  try {
    const { data, error } = await sb.from("congregations").update({ name: value }).eq("id", id).select("id").maybeSingle();
    if (error) throw error;
    if (!data) throw new Error("A congregação não foi atualizada. Verifique suas permissões.");
    await loadSurveyData(); render();
  } catch (error) { showError(error); }
}

/* =========================================================
   PERMISSÕES / LIBERAR ACESSO
   ========================================================= */
async function openUserPermissions(userId, userName) {
  if (!canManageUsers()) return alert("Você não tem permissão para administrar acessos.");
  try {
    const [{ data: surveys, error: se }, { data: access, error: ae }] = await Promise.all([
      sb.from("surveys").select("id,name,candidate_name,office,status").is("deleted_at", null).neq("status", "archived").order("created_at", { ascending: false }),
      sb.from("survey_access").select("survey_id,can_view,can_create_interview,can_export,can_manage_users").eq("user_id", userId)
    ]);
    if (se) throw se;
    if (ae) throw ae;
    const map = new Map((access || []).map(a => [a.survey_id, a]));
    const old = document.querySelector("#userPermissionsModal"); if (old) old.remove();
    const wrapper = document.createElement("div"); wrapper.id = "userPermissionsModal";
    Object.assign(wrapper.style,{position:"fixed",inset:"0",zIndex:"10001",background:"rgba(0,0,0,.65)",display:"flex",alignItems:"center",justifyContent:"center",padding:"20px"});
    wrapper.innerHTML = `<div class="card" style="width:100%;max-width:900px;max-height:90vh;overflow:auto">
      <div class="row"><div><h2>🔐 Liberar acesso</h2><p class="muted">${esc(userName)} — escolha as pesquisas e permissões.</p></div><button class="btn small" onclick="closeUserPermissions()">✕</button></div>
      <div style="overflow-x:auto"><table style="width:100%"><thead><tr><th>Pesquisa</th><th>Ver</th><th>Entrevistar</th><th>Exportar</th><th>Gerenciar</th></tr></thead><tbody>
      ${(surveys || []).map(s => { const a=map.get(s.id)||{}; const label=s.candidate_name||s.name||"Pesquisa"; return `<tr><td><strong>${esc(label)}</strong><div class="muted">${esc(s.office||"")}</div></td>
        <td><input class="perm-view" data-survey="${s.id}" type="checkbox" ${a.can_view ? "checked" : ""}></td>
        <td><input class="perm-interview" data-survey="${s.id}" type="checkbox" ${a.can_create_interview ? "checked" : ""}></td>
        <td><input class="perm-export" data-survey="${s.id}" type="checkbox" ${a.can_export ? "checked" : ""}></td>
        <td><input class="perm-manage" data-survey="${s.id}" type="checkbox" ${a.can_manage_users ? "checked" : ""}></td></tr>`; }).join("") || `<tr><td colspan="5" style="text-align:center;padding:30px">Nenhuma pesquisa cadastrada.</td></tr>`}
      </tbody></table></div>
      <div class="actions" style="justify-content:flex-end;margin-top:20px"><button class="btn" onclick="closeUserPermissions()">CANCELAR</button><button id="saveUserPermissionsButton" class="btn primary" onclick="saveUserPermissions('${userId}')">💾 SALVAR ACESSOS</button></div>
    </div>`;
    document.body.appendChild(wrapper);
  } catch (error) { showError(error); }
}
function closeUserPermissions(){ document.querySelector("#userPermissionsModal")?.remove(); }
async function saveUserPermissions(userId) {
  if (!canManageUsers()) return;
  const button=document.querySelector("#saveUserPermissionsButton"); if(button){button.disabled=true;button.textContent="SALVANDO...";}
  try {
    const ids = Array.from(document.querySelectorAll(".perm-view")).map(x=>x.dataset.survey);
    const existingResult = await sb.from("survey_access").select("id,survey_id").eq("user_id",userId);
    if(existingResult.error) throw existingResult.error;
    const existing=new Map((existingResult.data||[]).map(x=>[x.survey_id,x.id]));
    for(const surveyId of ids){
      const view=document.querySelector(`.perm-view[data-survey="${surveyId}"]`).checked;
      const interview=document.querySelector(`.perm-interview[data-survey="${surveyId}"]`).checked;
      const exp=document.querySelector(`.perm-export[data-survey="${surveyId}"]`).checked;
      const manage=document.querySelector(`.perm-manage[data-survey="${surveyId}"]`).checked;
      const payload={can_view:view,can_create_interview:interview,can_export:exp,can_manage_users:manage};
      if(existing.has(surveyId)) { const r=await sb.from("survey_access").update(payload).eq("id",existing.get(surveyId)).select("id").maybeSingle(); if(r.error) throw r.error; }
      else if(view||interview||exp||manage) { const r=await sb.from("survey_access").insert({user_id:userId,survey_id:surveyId,...payload}).select("id").maybeSingle(); if(r.error) throw r.error; }
    }
    closeUserPermissions(); await loadProfiles(); await loadSurveyData(); render(); alert("Acessos atualizados com sucesso!");
  } catch(error){ showError(error); if(button){button.disabled=false;button.textContent="💾 SALVAR ACESSOS";} }
}
async function shareUserAccess(userId) {
  const user=usersCache?.find(u=>u.id===userId); if(!user) return alert("Usuário não encontrado.");
  const text=`ACESSO À CENTRAL DE PESQUISAS\n\nNome: ${user.full_name||""}\nUsuário: ${user.username||""}\nCódigo de acesso: ${user.must_change_code ? "o código inicial informado pelo administrador (o sistema pede para trocar no 1º acesso)" : "o seu código pessoal"}\n\nAcesse a Central e informe seu usuário e código de acesso.`;
  const url=`https://wa.me/?text=${encodeURIComponent(text)}`;
  window.open(url,"_blank","noopener,noreferrer");
}

/* =========================================================
   REGIÕES
   ========================================================= */

