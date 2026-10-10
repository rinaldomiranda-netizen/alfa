/* Central de Pesquisas — entrevista (passo a passo) */
function interviewPage() {

  /*
   * Pesquisador só pode entrar na entrevista
   * se tiver pelo menos uma pesquisa autorizada.
   */
  if (
    state.profile?.role === "researcher" &&
    state.surveys.length === 0
  ) {

    return `
      <div class="card">

        <h1>
          📝 Nova entrevista
        </h1>

        <div
          class="card"
          style="
            margin-top:20px;
            background:#fff7ed;
            border:1px solid #fed7aa;
          "
        >

          <strong>
            Nenhuma pesquisa autorizada
          </strong>

          <p class="muted">
            O administrador ainda não liberou
            uma pesquisa para você realizar.
          </p>

        </div>

      </div>
    `;
  }


  /*
   * Se o pesquisador possui várias pesquisas,
   * ele poderá escolher somente entre as autorizadas.
   */
  const selector =
    state.profile?.role === "researcher" &&
    state.surveys.length > 1
      ? surveySelector()
      : "";


  if (!state.survey) {

    return `
      ${selector}

      <div class="card">

        <h2>
          📝 Nova entrevista
        </h2>

        <p class="muted">
          Selecione uma pesquisa autorizada
          para iniciar a entrevista.
        </p>

      </div>
    `;
  }


  return `
    ${selector}

    <div class="card">

      <div
        class="row"
        style="
          align-items:center;
          margin-bottom:20px;
        "
      >

        <div>

          <h1>
            📝 Nova entrevista
          </h1>

          <p class="muted">
            Pesquisa:
            <strong>
              ${esc(
                state.survey.candidate_name ||
                state.survey.name ||
                "Pesquisa"
              )}
            </strong>
          </p>

        </div>


        <span class="badge green">
          PESQUISA ATIVA
        </span>

      </div>


      ${
        state.interviewStep === 1
          ? interviewStep1()
          : state.interviewStep === 2
          ? interviewStep2()
          : interviewStep3()
      }

    </div>
  `;
}


/* =========================================================
   ETAPA 1
   ========================================================= */

function interviewStep1() {

  return `

    <div>

      <h2>
        1. Identificação
      </h2>

      <p class="muted">
        Informe os dados básicos da pessoa entrevistada.
      </p>


      <div class="field">

        <label>
          Nome da pessoa entrevistada
        </label>

        <input
          id="intervieweeName"
          type="text"
          value="${esc(
            state.form.interviewee_name
          )}"
          placeholder="Digite o nome"
          autocomplete="off"
        >

      </div>


      <div class="field">

        <label>
          Região
        </label>

        <select
          id="interviewRegion"
          onchange="
            changeRegion()
          "
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
                    ${
                      state.form.region_id ===
                      region.id
                        ? "selected"
                        : ""
                    }
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
          Congregação
        </label>

        <select
          id="interviewCongregation"
          onchange="
            state.form.congregation_id =
              this.value
          "
        >

          <option value="">
            Selecione a congregação
          </option>

          ${
            state.congregations
              .filter(
                congregation =>
                  !state.form.region_id ||
                  congregation.region_id ===
                  state.form.region_id
              )
              .map(
                congregation => `

                  <option
                    value="${congregation.id}"
                    ${
                      state.form.congregation_id ===
                      congregation.id
                        ? "selected"
                        : ""
                    }
                  >
                    ${esc(
                      congregation.name
                    )}
                  </option>

                `
              )
              .join("")
          }

        </select>

      </div>


      <div
        class="actions"
        style="
          justify-content:flex-end;
          margin-top:25px;
        "
      >

        <button
          type="button"
          class="btn primary"
          onclick="
            nextInterviewStep1()
          "
        >
          PRÓXIMO →
        </button>

      </div>

    </div>

  `;
}


/* =========================================================
   ETAPA 1 → 2
   ========================================================= */

function nextInterviewStep1() {

  /*
   * Captura os valores ANTES de renderizar novamente.
   * Isso corrige o bug do nome desaparecendo.
   */
  const nameInput =
    document.querySelector(
      "#intervieweeName"
    );

  const regionInput =
    document.querySelector(
      "#interviewRegion"
    );

  const congregationInput =
    document.querySelector(
      "#interviewCongregation"
    );


  /*
   * Salva tudo no state.
   */
  if (nameInput) {

    state.form.interviewee_name =
      nameInput.value.trim();

  }

  if (regionInput) {

    state.form.region_id =
      regionInput.value;

  }

  if (congregationInput) {

    state.form.congregation_id =
      congregationInput.value;

  }


  if (
    !state.form.interviewee_name
  ) {

    alert(
      "Digite o nome da pessoa entrevistada."
    );

    return;
  }


  if (
    !state.form.region_id
  ) {

    alert(
      "Selecione a região."
    );

    return;
  }


  if (
    !state.form.congregation_id
  ) {

    alert(
      "Selecione a congregação."
    );

    return;
  }


  state.interviewStep =
    2;


  render();
}


/* =========================================================
   TROCAR REGIÃO
   ========================================================= */

function changeRegion() {

  const region =
    document.querySelector(
      "#interviewRegion"
    );


  /*
   * IMPORTANTE:
   * Não apaga o nome da pessoa.
   */
  if (region) {

    state.form.region_id =
      region.value;

  }

  /* guarda o nome digitado antes de redesenhar a tela (antes ele sumia ao escolher a região) */
  const nome = document.querySelector("#intervieweeName");
  if (nome) state.form.interviewee_name = nome.value.trim();


  /*
   * Ao mudar a região,
   * somente a congregação é resetada.
   */
  state.form.congregation_id =
    "";


  render();
}


/* =========================================================
   ETAPA 2 — INTENÇÃO DE VOTO
   ========================================================= */

function interviewStep2() {

  const candidateName =
    state.survey?.candidate_name ||
    state.survey?.name ||
    "Candidato";


  return `

    <div>

      <h2>
        2. Intenção de voto
      </h2>

      <p class="muted">
        Selecione a resposta da pessoa entrevistada.
      </p>


      <div
        style="
          display:grid;
          gap:14px;
          margin-top:20px;
        "
      >

        <!-- CANDIDATO DA PESQUISA -->

        <button
          type="button"
          class="card"
          onclick="
            chooseIntention(
              'yes'
            )
          "
          style="
            cursor:pointer;
            text-align:left;
            border:
              2px solid
              ${
                state.form.intention ===
                "yes"
                  ? "#2563eb"
                  : "#e5e7eb"
              };
          "
        >

          <div
            style="
              font-size:22px;
              font-weight:700;
            "
          >
            👍 ${esc(
              candidateName
            )}
          </div>

          <div class="muted">
            Escolhe este candidato
          </div>

        </button>


        <!-- NÃO -->

        <button
          type="button"
          class="card"
          onclick="
            chooseIntention(
              'no'
            )
          "
          style="
            cursor:pointer;
            text-align:left;
            border:
              2px solid
              ${
                state.form.intention ===
                "no"
                  ? "#2563eb"
                  : "#e5e7eb"
              };
          "
        >

          <div
            style="
              font-size:22px;
              font-weight:700;
            "
          >
            👎 Não votaria
          </div>

          <div class="muted">
            Não escolheria este candidato
          </div>

        </button>


        <!-- OUTRO -->

        <button
          type="button"
          class="card"
          onclick="
            chooseIntention(
              'other'
            )
          "
          style="
            cursor:pointer;
            text-align:left;
            border:
              2px solid
              ${
                state.form.intention ===
                "other"
                  ? "#2563eb"
                  : "#e5e7eb"
              };
          "
        >

          <div
            style="
              font-size:22px;
              font-weight:700;
            "
          >
            🤷 Outro
          </div>

          <div class="muted">
            Votaria em outro candidato
          </div>

        </button>


        <!-- INDECISO -->

        <button
          type="button"
          class="card"
          onclick="
            chooseIntention(
              'undecided'
            )
          "
          style="
            cursor:pointer;
            text-align:left;
            border:
              2px solid
              ${
                state.form.intention ===
                "undecided"
                  ? "#2563eb"
                  : "#e5e7eb"
              };
          "
        >

          <div
            style="
              font-size:22px;
              font-weight:700;
            "
          >
            ❓ Indeciso
          </div>

          <div class="muted">
            Ainda não decidiu
          </div>

        </button>

      </div>


      <div
        class="actions"
        style="
          justify-content:space-between;
          margin-top:25px;
        "
      >

        <button
          type="button"
          class="btn"
          onclick="
            state.interviewStep = 1;
            render()
          "
        >
          ← VOLTAR
        </button>


        <button
          type="button"
          class="btn primary"
          onclick="
            state.interviewStep = 3;
            render()
          "
        >
          PRÓXIMO →
        </button>

      </div>

    </div>

  `;
}


/* =========================================================
   ESCOLHER INTENÇÃO
   ========================================================= */

function chooseIntention(
  intention
) {

  state.form.intention =
    intention;

  render();
}


/* =========================================================
   ETAPA 3
   ========================================================= */

function interviewStep3() {

  const candidateName =
    state.survey?.candidate_name ||
    state.survey?.name ||
    "Candidato";


  const intentionLabels = {

    yes:
      `👍 ${candidateName}`,

    no:
      "👎 Não votaria",

    other:
      "🤷 Outro",

    undecided:
      "❓ Indeciso"
  };


  return `

    <div>

      <h2>
        3. Confirmar entrevista
      </h2>


      <div
        class="card"
        style="
          margin-top:20px;
          background:#f8fafc;
        "
      >

        <div
          style="
            display:grid;
            gap:15px;
          "
        >

          <div>

            <small class="muted">
              ENTREVISTADO
            </small>

            <div>
              <strong>
                ${esc(
                  state.form.interviewee_name
                )}
              </strong>
            </div>

          </div>


          <div>

            <small class="muted">
              REGIÃO
            </small>

            <div>

              <strong>
                ${esc(
                  state.regions.find(
                    r =>
                      r.id ===
                      state.form.region_id
                  )?.name ||
                  "-"
                )}
              </strong>

            </div>

          </div>


          <div>

            <small class="muted">
              CONGREGAÇÃO
            </small>

            <div>

              <strong>
                ${esc(
                  state.congregations.find(
                    c =>
                      c.id ===
                      state.form.congregation_id
                  )?.name ||
                  "-"
                )}
              </strong>

            </div>

          </div>


          <div>

            <small class="muted">
              INTENÇÃO
            </small>

            <div>

              <strong>
                ${esc(
                  intentionLabels[
                    state.form.intention
                  ] ||
                  "-"
                )}
              </strong>

            </div>

          </div>

        </div>

      </div>


      <div
        class="field"
        style="
          margin-top:20px;
        "
      >

        <label>
          Observação
          <span class="muted">
            (opcional)
          </span>
        </label>

        <textarea
          id="interviewReason"
          placeholder="Observação sobre a entrevista"
        >${esc(
          state.form.reason
        )}</textarea>

      </div>


      <div
        class="actions"
        style="
          justify-content:space-between;
          margin-top:25px;
        "
      >

        <button
          type="button"
          class="btn"
          onclick="
            state.form.reason =
              document.querySelector(
                '#interviewReason'
              )?.value || '';
            state.interviewStep = 2;
            render()
          "
        >
          ← VOLTAR
        </button>


        <button
          type="button"
          class="btn primary"
          onclick="
            submitInterview()
          "
        >
          ✅ CONFIRMAR ENTREVISTA
        </button>

      </div>

    </div>

  `;
}


/* =========================================================
   ENVIAR ENTREVISTA
   ========================================================= */

async function submitInterview() {
  if (!state.user) { alert("Sua sessão expirou. Entre novamente."); return; }
  if (!state.survey) { alert("Nenhuma pesquisa selecionada."); return; }
  const reasonInput = document.querySelector("#interviewReason");
  if (reasonInput) state.form.reason = reasonInput.value.trim();
  if (!state.form.interviewee_name || !state.form.region_id || !state.form.congregation_id || !state.form.intention) {
    alert("Preencha todos os dados da entrevista.");
    return;
  }
  const button = document.querySelector("button[onclick*='submitInterview']");
  if (button) { button.disabled = true; button.textContent = "📍 REGISTRANDO LOCAL..."; }
  try {
    /* Onde e quando: hora do aparelho + localização (se a pessoa permitir). */
    const local = await cpLocalizacao();
    const registro = {
      client_uuid: cpNovoId(),
      survey_id: state.survey.id,
      interviewer_id: state.user.id,
      interviewee_name: state.form.interviewee_name,
      region_id: state.form.region_id,
      congregation_id: state.form.congregation_id,
      intention: state.form.intention,
      reason: state.form.reason || null,
      device_time: new Date().toISOString(),
      latitude: local.latitude,
      longitude: local.longitude,
      location_accuracy: local.precisao,
      location_status: local.status,
      app_version: CP_VERSAO
    };
    if (button) button.textContent = "ENVIANDO...";
    const r = await cpEnviarEntrevista(registro);
    resetForm();
    state.interviewStep = 1;
    if (r === "fila") {
      alert("📴 Sem internet agora.\n\nA entrevista ficou guardada neste aparelho e será enviada sozinha quando a internet voltar.");
      render();
    } else {
      alert("✅ Entrevista registrada com sucesso!");
      await loadSurveyData();
      render();
    }
  } catch (error) {
    console.error("ERRO AO ENVIAR ENTREVISTA:", error);
    showError(error);
    if (button) { button.disabled = false; button.textContent = "✅ CONFIRMAR ENTREVISTA"; }
  }
}
