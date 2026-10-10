/* Central de Pesquisas — dashboard */
/* =========================================================
   DASHBOARD
   ========================================================= */

async function dashboardPage() {

  /*
   * Para o administrador/coordenador,
   * o dashboard separa os resultados por pesquisa.
   */
  if (
    state.profile?.role === "admin" ||
    state.profile?.role === "coordinator"
  ) {

    let allInterviews =
      state.dashboardInterviews || [];


    const activeSurveys =
      state.surveys || [];


    return `

      <div
        class="grid"
        style="gap:20px"
      >

        <div class="card">

          <div class="row">

            <div>

              <h1>
                📊 Dashboard
              </h1>

              <p class="muted">
                Resultados separados por candidato/pesquisa.
              </p>

            </div>


            <button
              type="button"
              class="btn"
              onclick="
                refresh()
              "
            >
              ↻ ATUALIZAR
            </button>

          </div>

        </div>


        <!-- TOTAL GERAL -->

        <div
          class="grid stats"
        >

          <div class="card stat">

            <span>
              📝 ENTREVISTAS
            </span>

            <strong>
              ${fmt(
                allInterviews.length
              )}
            </strong>

            <span>
              Total realizado
            </span>

          </div>


          <div class="card stat">

            <span>
              🎯 PESQUISAS
            </span>

            <strong>
              ${fmt(
                activeSurveys.length
              )}
            </strong>

            <span>
              Cadastradas
            </span>

          </div>

        </div>


        <!-- AÇÕES RÁPIDAS -->

        <div class="card">
          <div class="row">
            <div>
              <h2>⚡ Ações rápidas</h2>
              <p class="muted">Atalhos para as operações administrativas mais usadas.</p>
            </div>
          </div>
          <div class="actions" style="flex-wrap:wrap;margin-top:15px">
            <button type="button" class="btn primary" onclick="openSurveyForm()">➕ Nova pesquisa</button>
            <button type="button" class="btn" onclick="nav('users')">👥 Usuários</button>
            <button type="button" class="btn" onclick="nav('regions')">📍 Regiões</button>
            <button type="button" class="btn" onclick="nav('congregations')">⛪ Congregações</button>
            <button type="button" class="btn" onclick="openPlatformAccess()">📱 Acesso multiplataforma</button>
          </div>
        </div>

        <!-- RESULTADOS POR PESQUISA -->

        <div
          class="grid"
          style="
            gap:20px;
          "
        >

          ${
            activeSurveys.length

              ? activeSurveys
                  .map(
                    survey => {

                      const rows =
                        allInterviews.filter(
                          interview =>
                            interview.survey_id ===
                            survey.id
                        );


                      const total =
                        rows.length;


                      const yes =
                        rows.filter(
                          row =>
                            row.intention ===
                            "yes"
                        ).length;


                      const no =
                        rows.filter(
                          row =>
                            row.intention ===
                            "no"
                        ).length;


                      const other =
                        rows.filter(
                          row =>
                            row.intention ===
                            "other"
                        ).length;


                      const undecided =
                        rows.filter(
                          row =>
                            row.intention ===
                            "undecided"
                        ).length;


                      return `

                        <div class="card">

                          <div
                            class="row"
                          >

                            <div>

                              <h2>
                                🎯 ${esc(
                                  survey.candidate_name ||
                                  survey.name ||
                                  "Pesquisa"
                                )}
                              </h2>

                              <p class="muted">
                                ${esc(
                                  survey.office ||
                                  ""
                                )}
                              </p>

                            </div>


                            <span class="badge green">
                              ${fmt(total)}
                              entrevistas
                            </span>

                          </div>


                          <div
                            class="grid stats"
                            style="
                              margin-top:20px;
                            "
                          >

                            <!-- SIM -->

                            <div
                              class="card stat"
                            >

                              <span>
                                👍 INTENÇÃO
                              </span>

                              <strong>
                                ${fmt(yes)}
                              </strong>

                              <span>
                                ${pct(
                                  yes,
                                  total
                                )}
                              </span>

                            </div>


                            <!-- NÃO -->

                            <div
                              class="card stat"
                            >

                              <span>
                                👎 NÃO
                              </span>

                              <strong>
                                ${fmt(no)}
                              </strong>

                              <span>
                                ${pct(
                                  no,
                                  total
                                )}
                              </span>

                            </div>


                            <!-- OUTRO -->

                            <div
                              class="card stat"
                            >

                              <span>
                                🤷 OUTRO
                              </span>

                              <strong>
                                ${fmt(other)}
                              </strong>

                              <span>
                                ${pct(
                                  other,
                                  total
                                )}
                              </span>

                            </div>


                            <!-- INDECISO -->

                            <div
                              class="card stat"
                            >

                              <span>
                                ❓ INDECISOS
                              </span>

                              <strong>
                                ${fmt(undecided)}
                              </strong>

                              <span>
                                ${pct(
                                  undecided,
                                  total
                                )}
                              </span>

                            </div>

                          </div>


                          <!-- BARRA -->

                          <div
                            style="
                              margin-top:25px;
                            "
                          >

                            <div
                              style="
                                display:flex;
                                justify-content:space-between;
                                margin-bottom:8px;
                              "
                            >

                              <strong>
                                ${esc(
                                  survey.candidate_name ||
                                  survey.name ||
                                  "Candidato"
                                )}
                              </strong>

                              <strong>
                                ${pct(
                                  yes,
                                  total
                                )}
                              </strong>

                            </div>


                            <div
                              style="
                                width:100%;
                                height:18px;
                                background:#e5e7eb;
                                border-radius:999px;
                                overflow:hidden;
                              "
                            >

                              <div
                                style="
                                  width:${total
                                    ? (
                                        yes /
                                        total *
                                        100
                                      )
                                    : 0
                                  }%;
                                  height:100%;
                                  background:#2563eb;
                                  border-radius:999px;
                                "
                              ></div>

                            </div>

                          </div>

                        </div>

                      `;

                    }
                  )
                  .join("")

              : `

                <div class="card">

                  <h2>
                    Nenhuma pesquisa cadastrada
                  </h2>

                  <p class="muted">
                    Crie uma pesquisa para começar.
                  </p>

                </div>

              `
          }

        </div>

      </div>

    `;
  }


  /*
   * Dashboard do pesquisador.
   */
  const rows =
    state.dashboardInterviews || [];


  const total =
    rows.length;


  const yes =
    rows.filter(
      row =>
        row.intention ===
        "yes"
    ).length;


  const no =
    rows.filter(
      row =>
        row.intention ===
        "no"
    ).length;


  const other =
    rows.filter(
      row =>
        row.intention ===
        "other"
    ).length;


  const undecided =
    rows.filter(
      row =>
        row.intention ===
        "undecided"
    ).length;


  return `

    <div
      class="grid"
      style="gap:20px"
    >

      <div class="card">

        <div class="row">

          <div>

            <h1>
              📊 Meu dashboard
            </h1>

            <p class="muted">
              Resultado das entrevistas realizadas.
            </p>

          </div>


          <button
            type="button"
            class="btn"
            onclick="
              refresh()
            "
          >
            ↻ ATUALIZAR
          </button>

        </div>

      </div>


      <div
        class="grid stats"
      >

        <div class="card stat">

          <span>
            📝 ENTREVISTAS
          </span>

          <strong>
            ${fmt(total)}
          </strong>

          <span>
            Realizadas por você
          </span>

        </div>


        <div class="card stat">

          <span>
            👍 INTENÇÃO
          </span>

          <strong>
            ${fmt(yes)}
          </strong>

          <span>
            ${pct(
              yes,
              total
            )}
          </span>

        </div>


        <div class="card stat">

          <span>
            👎 NÃO
          </span>

          <strong>
            ${fmt(no)}
          </strong>

          <span>
            ${pct(
              no,
              total
            )}
          </span>

        </div>


        <div class="card stat">

          <span>
            ❓ INDECISOS
          </span>

          <strong>
            ${fmt(undecided)}
          </strong>

          <span>
            ${pct(
              undecided,
              total
            )}
          </span>

        </div>

      </div>

    </div>

  `;
}


/* =========================================================
   RENDER PRINCIPAL
   ========================================================= */

