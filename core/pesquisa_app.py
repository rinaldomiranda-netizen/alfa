"""
Localização/abertura da aplicação REAL de pesquisa (Central de
Pesquisas Online) — para a BETA não depender de a tela já estar
aberta antes do atendimento começar.

Estratégia (100% local/offline, sem chamada de rede):
  1. Procurar entre as janelas abertas do Windows uma cujo título
     contenha alguma palavra-chave da pesquisa real (configurável em
     config/alfa.json -> pesquisa.palavras_chave_janela) e trazê-la
     para frente.
  2. Se nenhuma janela for encontrada, tentar abrir o aplicativo a
     partir do caminho local configurado (pesquisa.caminho_local) —
     o mesmo projeto real identificado em core/roteiro_pesquisa.py.

Login/navegação até a tela "Nova entrevista" continuam sendo feitos
por uma pessoa (a aplicação usa autenticação real do Supabase; a
BETA não tem — e não deve ter — credenciais para logar sozinha).
"""

import json
import os
import time

import win32con
import win32gui

PALAVRAS_CHAVE_PADRAO = ["central de pesquisas", "nova entrevista", "entrevistas"]


def _resolver_caminho_local_padrao():
    """
    Nenhum caminho pessoal fixo no código: cada computador configura o
    seu, nesta ordem de prioridade —
      1. variável de ambiente BETA_PESQUISA_CAMINHO_LOCAL;
      2. config/alfa.json -> pesquisa.caminho_local, SE esse arquivo
         existir neste computador (perfil pessoal do ALFA; nunca
         existe na distribuição portátil);
      3. None — quem chamar trata a ausência sem gerar erro (ver
         localizar_ou_abrir).
    """
    caminho_env = os.environ.get("BETA_PESQUISA_CAMINHO_LOCAL")
    if caminho_env:
        return caminho_env

    caminho_config = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "alfa.json"
    )
    if os.path.exists(caminho_config):
        try:
            with open(caminho_config, "r", encoding="utf-8") as arquivo:
                dados = json.load(arquivo)
            return dados.get("pesquisa", {}).get("caminho_local")
        except Exception:
            return None

    return None


def _listar_titulos_janelas():
    titulos = []

    def callback(hwnd, _):
        if win32gui.IsWindowVisible(hwnd):
            titulo = win32gui.GetWindowText(hwnd)
            if titulo.strip():
                titulos.append((hwnd, titulo))
        return True

    win32gui.EnumWindows(callback, None)
    return titulos


def encontrar_janela_pesquisa(palavras_chave=None):
    """Retorna (hwnd, titulo) da janela da pesquisa já aberta, ou None."""
    palavras_chave = [p.lower() for p in (palavras_chave or PALAVRAS_CHAVE_PADRAO)]

    for hwnd, titulo in _listar_titulos_janelas():
        titulo_lower = titulo.lower()
        if any(palavra in titulo_lower for palavra in palavras_chave):
            return hwnd, titulo

    return None


def focar_janela(hwnd):
    try:
        if win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        win32gui.SetForegroundWindow(hwnd)
        return True
    except Exception:
        return False


def abrir_aplicativo(caminho_local=None, url_producao=None):
    """
    Abre a pesquisa no navegador padrão: prioriza a URL de produção,
    se configurada (config/alfa.json -> pesquisa.url_producao); senão
    usa o caminho local configurado neste computador (ver
    _resolver_caminho_local_padrao). Sem nenhum dos dois configurados,
    não há o que abrir — retorna False sem erro.
    """
    alvo = url_producao or caminho_local or _resolver_caminho_local_padrao()

    if not url_producao and (not alvo or not os.path.exists(alvo)):
        return False

    try:
        os.startfile(alvo)
        return True
    except Exception:
        return False


def localizar_ou_abrir(palavras_chave=None, caminho_local=None, url_producao=None, espera_apos_abrir=3):
    """
    Tenta trazer a janela da pesquisa para frente; se não encontrar
    nenhuma, tenta abrir o aplicativo. Sempre best-effort — nunca
    levanta exceção, e nunca bloqueia o atendimento por muito tempo.

    Retorna uma string curta descrevendo o que aconteceu:
        "encontrada" | "aberta" | "aberta_sem_confirmar" | "nao_encontrada"
        | "pesquisa não configurada neste computador"
    """
    try:
        achado = encontrar_janela_pesquisa(palavras_chave)
        if achado:
            hwnd, _ = achado
            focar_janela(hwnd)
            return "encontrada"

        if not url_producao and not (caminho_local or _resolver_caminho_local_padrao()):
            return "pesquisa não configurada neste computador"

        if abrir_aplicativo(caminho_local, url_producao):
            time.sleep(espera_apos_abrir)
            achado = encontrar_janela_pesquisa(palavras_chave)
            if achado:
                focar_janela(achado[0])
                return "aberta"
            return "aberta_sem_confirmar"

        return "nao_encontrada"
    except Exception:
        return "nao_encontrada"
