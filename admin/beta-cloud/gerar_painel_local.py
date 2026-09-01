"""
Painel administrativo BETA-CLOUD — FASE 2 da expansão de plataforma.

IMPORTANTE — leia antes de usar: hoje NÃO existe nenhum servidor
BETA-CLOUD real configurado (ver memory/sync.py e
core/alfa_core.py -> cloud.enabled). Este script gera uma PRÉVIA
LOCAL, a partir de dados que já existem de verdade NESTE computador
(habilidades instaladas, fila de sincronização pendente, versão) —
nunca inventa usuário, organização, dispositivo ou evento que não
exista aqui. Quando um projeto BETA-CLOUD real existir (Supabase com
autenticação + RLS), o painel de verdade vai LER de lá — isto não é
esse painel, é a prévia que prepara o terreno pra ele.

NUNCA mostra biometria facial nem segredo nenhum (service_role,
tokens) — os próprios dados locais que alimentam isto não carregam
esse tipo de informação (ver memory/sync.py -> CAMPOS_PROIBIDOS, que
recusa até guardar isso na fila).

Uso:
    python "admin/beta-cloud/gerar_painel_local.py"
Gera admin/beta-cloud/painel_local.html — abra no navegador.
"""

import json
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE not in sys.path:
    sys.path.insert(0, BASE)

from agente.skill_registry import SkillRegistry
from core.version import versao_completa
from memory import sync


def _coletar_dados():
    registry = SkillRegistry()
    skills = registry.descobrir()
    linhas_skills = [
        {
            "nome": m.nome,
            "versao": m.versao,
            "ativa": registry.esta_ativa(m.nome),
            "permissoes": m.permissoes,
        }
        for m in skills.values()
    ]

    fila = sync._ler_fila()
    eventos = [
        {"tipo": e.get("tipo"), "origem": e.get("origem"), "tentativas": e.get("tentativas", 0)}
        for e in fila
    ]

    return {
        "versao": versao_completa(),
        "skills": linhas_skills,
        "sincronizacao_pendente": len(fila),
        "eventos_pendentes": eventos,
    }


def gerar_html(dados):
    linhas_skills = "".join(
        f"<tr><td>{s['nome']}</td><td>{s['versao']}</td>"
        f"<td>{'ativa' if s['ativa'] else 'inativa'}</td>"
        f"<td>{', '.join(s['permissoes'])}</td></tr>"
        for s in dados["skills"]
    ) or "<tr><td colspan='4'>Nenhuma habilidade encontrada</td></tr>"

    linhas_eventos = "".join(
        f"<tr><td>{e['tipo']}</td><td>{e['origem'] or '-'}</td><td>{e['tentativas']}</td></tr>"
        for e in dados["eventos_pendentes"]
    ) or "<tr><td colspan='3'>Nenhum evento pendente</td></tr>"

    return f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8">
<title>BETA-CLOUD - Previa local</title>
<style>
body {{ font-family: 'Segoe UI', sans-serif; background:#0f172a; color:#e5e7eb; padding:24px; }}
h1 {{ color:#38bdf8; }}
.aviso {{ background:#7c2d12; color:#fed7aa; padding:12px; border-radius:8px; margin-bottom:24px; max-width:760px; }}
table {{ border-collapse: collapse; width:100%; max-width:760px; margin-bottom:32px; }}
th, td {{ border:1px solid #334155; padding:8px 12px; text-align:left; }}
th {{ background:#1e293b; }}
</style></head>
<body>
<h1>BETA-CLOUD — Prévia local</h1>
<div class="aviso">
  Isto é uma PRÉVIA gerada localmente, sem nenhuma conexão com um
  servidor BETA-CLOUD real (nenhum foi configurado neste computador).
  Nenhum dado de biometria ou segredo é exibido aqui.
</div>

<h2>Versão</h2>
<pre>{json.dumps(dados['versao'], indent=2, ensure_ascii=False)}</pre>

<h2>Habilidades instaladas</h2>
<table><tr><th>Nome</th><th>Versão</th><th>Estado</th><th>Permissões</th></tr>
{linhas_skills}
</table>

<h2>Sincronização — {dados['sincronizacao_pendente']} evento(s) pendente(s)</h2>
<table><tr><th>Tipo</th><th>Origem</th><th>Tentativas</th></tr>
{linhas_eventos}
</table>
</body></html>
"""


def main():
    dados = _coletar_dados()
    html = gerar_html(dados)
    caminho_saida = os.path.join(os.path.dirname(os.path.abspath(__file__)), "painel_local.html")
    with open(caminho_saida, "w", encoding="utf-8") as arquivo:
        arquivo.write(html)
    print(f"Painel local gerado em: {caminho_saida}")


if __name__ == "__main__":
    main()
