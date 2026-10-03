/* Central de Pesquisas no ALFA — nome da empresa no cabeçalho e temas antigos convertidos para claro/médio/escuro. */
(function () {
  "use strict";
  var ANTIGOS = { green: "claro", blue: "claro", purple: "claro", dark: "escuro" };
  function ler(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }
  function gravar(k, v) { try { if (v) localStorage.setItem(k, v); else localStorage.removeItem(k); } catch (e) { /* sem armazenamento */ } }
  var t = ler("central_theme");
  if (t && ANTIGOS[t]) { gravar("central_theme", ANTIGOS[t]); }
  function temaAtual() { var v = ler("central_theme") || "claro"; return ANTIGOS[v] || v; }
  function empresa() { return (ler("central_empresa") || "").trim(); }
  window.rmdSalvarEmpresa = function (v) { gravar("central_empresa", (v || "").trim().slice(0, 60)); aplicar(); };
  function aplicar() {
    if (document.body && document.body.dataset.theme !== temaAtual()) document.body.dataset.theme = temaAtual();
    var nome = empresa();
    document.querySelectorAll(".sidebar .brand small").forEach(function (el) { var alvo = nome || "PESQUISAS"; if (el.textContent.trim() !== alvo) el.textContent = alvo; });
    var topo = document.querySelector(".topbar");
    if (topo) {
      var tag = topo.querySelector(".rmd-empresa-topo");
      if (nome) { if (!tag) { tag = document.createElement("span"); tag.className = "rmd-empresa-topo"; var ult = topo.lastElementChild; topo.insertBefore(tag, ult); } if (tag.textContent !== nome) tag.textContent = nome; }
      else if (tag) tag.remove();
    }
    var campo = document.getElementById("rmdEmpresaNome");
    if (campo && document.activeElement !== campo && campo.value !== nome) campo.value = nome;
    document.title = (nome ? nome + " — " : "") + "Central de Pesquisas";
  }
  var pend = false;
  new MutationObserver(function () { if (pend) return; pend = true; requestAnimationFrame(function () { pend = false; aplicar(); }); })
    .observe(document.documentElement, { childList: true, subtree: true });
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", aplicar); else aplicar();
})();
