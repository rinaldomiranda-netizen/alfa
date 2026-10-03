/* RMD Atendimento — carregado no <head>, antes de desenhar a tela.
   1) Aplica logo de início o último tema usado (evita a tela escura piscando antes do sistema abrir).
   2) Identifica sozinho se é computador, tablet ou celular e ajusta a tela (data-dispositivo).
      A pessoa pode trocar no menu do usuário: Automático / Computador / Tablet / Celular. */
(function () {
  "use strict";
  var raiz = document.documentElement;
  function ler(chave) { try { return localStorage.getItem(chave); } catch (e) { return null; } }
  var pessoal = ler("rmd_tema"), ultimo = ler("rmd_tema_ultimo");
  var tema = pessoal && pessoal !== "empresa" ? pessoal : ultimo;
  if (tema) raiz.dataset.tema = tema;

  var LARGURA_VISOR = { computador: 1280, tablet: 900 };
  function automatico() {
    var w = Math.min(window.screen && screen.width || 9999, window.innerWidth || 9999);
    var toque = window.matchMedia && matchMedia("(pointer:coarse)").matches;
    if (w <= 740) return "celular";
    if (w <= 1180 && (toque || w <= 1024)) return "tablet";
    return "computador";
  }
  function aplicar() {
    var escolha = ler("rmd_tela") || "auto";
    var auto = automatico();
    var final = escolha === "auto" ? auto : escolha;
    raiz.dataset.dispositivo = final;
    raiz.dataset.telaEscolha = escolha;
    var visor = document.querySelector('meta[name="viewport"]');
    if (visor) {
      // num aparelho pequeno, "Computador"/"Tablet" mostram a tela larga (como o "modo computador" do navegador)
      var largura = escolha !== "auto" && LARGURA_VISOR[escolha] && (screen.width || 9999) < LARGURA_VISOR[escolha] ? LARGURA_VISOR[escolha] : 0;
      var conteudo = largura ? "width=" + largura : "width=device-width, initial-scale=1";
      if (visor.getAttribute("content") !== conteudo) visor.setAttribute("content", conteudo);
    }
  }
  window.RMDTela = {
    opcoes: [["auto", "Automático"], ["computador", "Computador"], ["tablet", "Tablet"], ["celular", "Celular"]],
    escolha: function () { return ler("rmd_tela") || "auto"; },
    escolher: function (v) { try { if (v === "auto") localStorage.removeItem("rmd_tela"); else localStorage.setItem("rmd_tela", v); } catch (e) { /* sem armazenamento */ } aplicar(); },
    detectado: automatico,
    aplicar: aplicar
  };
  aplicar();
  var t = null;
  window.addEventListener("resize", function () { clearTimeout(t); t = setTimeout(aplicar, 150); });
  window.addEventListener("orientationchange", function () { setTimeout(aplicar, 200); });
})();
