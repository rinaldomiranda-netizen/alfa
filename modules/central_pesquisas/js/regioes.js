/* Central de Pesquisas — regiões e congregações */
async function regionsPage() {

  if (!canManageUsers()) {

    return `
      <div class="card">

        <h1>
          Acesso restrito
        </h1>

      </div>
    `;
  }


  let regions = [];


  try {

    if (state.survey) {

      const {
        data,
        error
      } = await sb
        .from("regions")
        .select("*").is("deleted_at", null)
        .eq(
          "survey_id",
          state.survey.id
        )
        .order(
          "name"
        );


      if (error) {
        throw error;
      }


      regions =
        data || [];

    }


  } catch (error) {

    return `
      <div class="card">

        <h2>
          Erro ao carregar regiões
        </h2>

        <p>
          ${esc(
            error?.message ||
            "Erro desconhecido."
          )}
        </p>

      </div>
    `;
  }


  return `

    <div
      class="grid"
      style="gap:20px"
    >

      <div class="card">

        <div class="row">

          <div>

            <h1>
              Regiões
            </h1>

            <p class="muted">
              Regiões utilizadas nas entrevistas.
            </p>

          </div>


          <button
            type="button"
            class="btn primary"
            onclick="
              openRegionForm()
            "
          >
            ➕ NOVA REGIÃO
          </button>

        </div>

      </div>


      <div class="card">

        <table>

          <thead>

            <tr>

              <th>
                Região
              </th>

              <th>
                Ações
              </th>

            </tr>

          </thead>


          <tbody>

            ${
              regions.length

                ? regions
                    .map(
                      region => `

                        <tr>

                          <td>

                            <strong>
                              ${esc(
                                region.name
                              )}
                            </strong>

                          </td>

                          <td>

                            <button type="button" class="btn small" onclick="editRegion('${region.id}')">✏️ Editar</button>
                            <button type="button" class="btn small" onclick="deleteRegion('${region.id}')">🗑 Excluir</button>

                          </td>

                        </tr>

                      `
                    )
                    .join("")

                : `

                  <tr>

                    <td
                      colspan="2"
                      style="
                        text-align:center;
                        padding:30px;
                      "
                    >
                      Nenhuma região cadastrada.
                    </td>

                  </tr>

                `
            }

          </tbody>

        </table>

      </div>

    </div>

  `;
}


/* =========================================================
   NOVA REGIÃO
   ========================================================= */

function openRegionForm() {

  if (!state.survey) {

    alert(
      "Selecione ou crie uma pesquisa primeiro."
    );

    return;
  }


  const old =
    document.querySelector(
      "#regionForm"
    );


  if (old) {
    old.remove();
  }


  const wrapper =
    document.createElement(
      "div"
    );


  wrapper.id =
    "regionForm";


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
        max-width:500px;
      "
    >

      <div class="row">

        <h2>
          ➕ Nova região
        </h2>

        <button
          type="button"
          class="btn small"
          onclick="
            closeRegionForm()
          "
        >
          ✕
        </button>

      </div>


      <div class="field">

        <label>
          Nome da região
        </label>

        <input
          id="regionName"
          type="text"
          placeholder="Digite o nome da região"
        >

      </div>


      <div class="actions">

        <button
          type="button"
          class="btn"
          onclick="
            closeRegionForm()
          "
        >
          CANCELAR
        </button>

        <button
          type="button"
          class="btn primary"
          onclick="
            createRegion()
          "
        >
          CADASTRAR
        </button>

      </div>

    </div>

  `;


  document.body.appendChild(
    wrapper
  );


  document
    .querySelector(
      "#regionName"
    )
    ?.focus();
}


function closeRegionForm() {

  document
    .querySelector(
      "#regionForm"
    )
    ?.remove();

}


/* =========================================================
   CRIAR REGIÃO
   ========================================================= */

async function createRegion() {

  if (!state.survey) {

    alert(
      "Selecione uma pesquisa primeiro."
    );

    return;
  }


  const name =
    document
      .querySelector(
        "#regionName"
      )
      ?.value
      .trim();


  if (!name) {

    alert(
      "Digite o nome da região."
    );

    return;
  }


  try {

    const { data: duplicate } = await sb.from("regions").select("id").is("deleted_at", null).eq("survey_id", state.survey.id).ilike("name", name).maybeSingle();
    if (duplicate) throw new Error("Já existe uma região com esse nome nesta pesquisa.");

    const {
      error
    } = await sb
      .from("regions")
      .insert({

        survey_id:
          state.survey.id,

        name:
          name

      });


    if (error) {
      throw error;
    }


    closeRegionForm();


    await loadSurveyData();


    render();


    alert(
      "Região cadastrada com sucesso!"
    );


  } catch (error) {

    showError(error);

  }
}


/* =========================================================
   EXCLUIR REGIÃO
   ========================================================= */

async function deleteRegion(
  id
) {

  if (!canManageUsers()) {
    alert("Você não tem permissão para excluir este registro.");
    return;
  }

  const name = state.regions?.find?.(r => r.id === id)?.name || "Região";

  if (
    !confirm(
      `Mover a região "${name}" para a lixeira?\n\nPode ser restaurada em até 30 dias.`
    )
  ) {
    return;
  }


  try {

    const { data: deleted, error } = await sb.functions.invoke("admin-users", { body: { action: "delete_region", region_id: id } });
    if (error) throw new Error(await cpErroFuncao(error));
    if (!deleted?.success) throw new Error(deleted?.error || "Não foi possível mover para a lixeira.");


    await loadSurveyData();

    render();


  } catch (error) {

    showError(error);

  }
}


/* =========================================================
   CONGREGAÇÕES
   ========================================================= */

async function congregationsPage() {

  if (!canManageUsers()) {

    return `
      <div class="card">

        <h1>
          Acesso restrito
        </h1>

      </div>
    `;
  }


  return `

    <div
      class="grid"
      style="gap:20px"
    >

      <div class="card">

        <div class="row">

          <div>

            <h1>
              Congregações
            </h1>

            <p class="muted">
              Cadastre os locais utilizados
              nas entrevistas.
            </p>

          </div>


          <button
            type="button"
            class="btn primary"
            onclick="
              openCongregationForm()
            "
          >
            ➕ NOVA CONGREGAÇÃO
          </button>

        </div>

      </div>


      <div class="card">

        <div
          style="
            overflow-x:auto;
          "
        >

          <table>

            <thead>

              <tr>

                <th>
                  Congregação
                </th>

                <th>
                  Região
                </th>

                <th>
                  Ações
                </th>

              </tr>

            </thead>


            <tbody>

              ${
                state.congregations.length

                  ? state.congregations
                      .map(
                        congregation => {

                          const region =
                            state.regions.find(
                              item =>
                                item.id ===
                                congregation.region_id
                            );


                          return `

                            <tr>

                              <td>

                                <strong>
                                  ${esc(
                                    congregation.name
                                  )}
                                </strong>

                              </td>


                              <td>

                                ${esc(
                                  region?.name ||
                                  "-"
                                )}

                              </td>


                              <td>

                                <button type="button" class="btn small" onclick="editCongregation('${congregation.id}')">✏️ Editar</button>
                                <button type="button" class="btn small" onclick="deleteCongregation('${congregation.id}')">🗑 Excluir</button>

                              </td>

                            </tr>

                          `;

                        }
                      )
                      .join("")

                  : `

                    <tr>

                      <td
                        colspan="3"
                        style="
                          text-align:center;
                          padding:30px;
                        "
                      >
                        Nenhuma congregação cadastrada.
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
   NOVA CONGREGAÇÃO
   ========================================================= */

function openCongregationForm() {

  if (!state.survey) {

    alert(
      "Selecione ou crie uma pesquisa primeiro."
    );

    return;
  }


  const old =
    document.querySelector(
      "#congregationForm"
    );


  if (old) {
    old.remove();
  }


  const wrapper =
    document.createElement(
      "div"
    );


  wrapper.id =
    "congregationForm";


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
        max-width:550px;
      "
    >

      <div class="row">

        <h2>
          ➕ Nova congregação
        </h2>

        <button
          type="button"
          class="btn small"
          onclick="
            closeCongregationForm()
          "
        >
          ✕
        </button>

      </div>


      <div class="field">

        <label>
          Região
        </label>

        <select
          id="congregationRegion"
        >

          <option value="">
            Selecione a região
          </option>

          ${
            state.regions
              .map(
                region => `
                  <option
                    value="${region.id}"
                  >
                    ${esc(
                      region.name
                    )}
                  </option>
                `
              )
              .join("")
          }

        </select>

      </div>


      <div class="field">

        <label>
          Nome da congregação
        </label>

        <input
          id="congregationName"
          type="text"
          placeholder="Digite o nome"
        >

      </div>


      <div class="actions">

        <button
          type="button"
          class="btn"
          onclick="
            closeCongregationForm()
          "
        >
          CANCELAR
        </button>

        <button
          type="button"
          class="btn primary"
          onclick="
            createCongregation()
          "
        >
          CADASTRAR
        </button>

      </div>

    </div>

  `;


  document.body.appendChild(
    wrapper
  );


  document
    .querySelector(
      "#congregationName"
    )
    ?.focus();
}


function closeCongregationForm() {

  document
    .querySelector(
      "#congregationForm"
    )
    ?.remove();

}


/* =========================================================
   CRIAR CONGREGAÇÃO
   ========================================================= */

async function createCongregation() {

  if (!state.survey) {

    alert(
      "Selecione uma pesquisa primeiro."
    );

    return;
  }


  const regionId =
    document
      .querySelector(
        "#congregationRegion"
      )
      ?.value;


  const name =
    document
      .querySelector(
        "#congregationName"
      )
      ?.value
      .trim();


  if (!regionId) {

    alert(
      "Selecione a região."
    );

    return;
  }


  if (!name) {

    alert(
      "Digite o nome da congregação."
    );

    return;
  }


  try {

    const { data: duplicate } = await sb.from("congregations").select("id").is("deleted_at", null).eq("survey_id", state.survey.id).ilike("name", name).maybeSingle();
    if (duplicate) throw new Error("Já existe uma congregação com esse nome nesta pesquisa.");

    const {
      error
    } = await sb
      .from("congregations")
      .insert({

        survey_id:
          state.survey.id,

        region_id:
          regionId,

        name:
          name

      });


    if (error) {
      throw error;
    }


    closeCongregationForm();


    await loadSurveyData();


    render();


    alert(
      "Congregação cadastrada com sucesso!"
    );


  } catch (error) {

    showError(error);

  }
}


/* =========================================================
   EXCLUIR CONGREGAÇÃO
   ========================================================= */

async function deleteCongregation(
  id
) {

  if (!canManageUsers()) {
    alert("Você não tem permissão para excluir este registro.");
    return;
  }

  const name = state.congregations?.find?.(c => c.id === id)?.name || "Congregação";

  if (
    !confirm(
      `Mover a congregação "${name}" para a lixeira?\n\nPode ser restaurada em até 30 dias.`
    )
  ) {
    return;
  }


  try {

    const { data: deleted, error } = await sb.functions.invoke("admin-users", { body: { action: "delete_congregation", congregation_id: id } });
    if (error) throw new Error(await cpErroFuncao(error));
    if (!deleted?.success) throw new Error(deleted?.error || "Não foi possível mover para a lixeira.");


    await loadSurveyData();

    render();


  } catch (error) {

    showError(error);

  }
}
/* =========================================================
   ENTREVISTA
   ========================================================= */

