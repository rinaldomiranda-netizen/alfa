"""Painel web do RMD Atendimento no ALPHA e em modo standalone."""
from html import escape
from .modulo import AtendimentoModule


def renderizar_painel(modulo=None):
    modulo = modulo or AtendimentoModule()
    s = modulo.status()
    ativo = "Ativo" if s["ativo"] else "Inativo"
    pessoa = escape(s.get("nome_pessoa") or "Nenhuma")
    estado = escape(s.get("estado") or "INATIVO")
    atendimento = escape(str(s.get("atendimento_id") or "—"))
    versao = escape(s["versao"])
    return f'''<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>RMD Atendimento</title><style>*{{box-sizing:border-box}}body{{margin:0;font-family:system-ui,Arial;background:#f4f6fb;color:#172033}}header{{background:#111a33;color:#fff;padding:18px 20px}}main{{max-width:980px;margin:auto;padding:20px}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:14px}}.card{{background:#fff;border:1px solid #dfe4ef;border-radius:14px;padding:18px}}.label{{font-size:12px;color:#69738a;text-transform:uppercase}}.value{{font-size:20px;font-weight:700;margin-top:5px}}button{{border:0;border-radius:9px;padding:11px 15px;background:#315efb;color:#fff;font-weight:700}}</style></head><body><header><strong>RMD Atendimento</strong><div style="opacity:.75">Módulo ALPHA · versão {versao}</div></header><main><div class="grid"><div class="card"><div class="label">Status</div><div class="value">{ativo}</div></div><div class="card"><div class="label">Estado</div><div class="value">{estado}</div></div><div class="card"><div class="label">Pessoa atual</div><div class="value">{pessoa}</div></div><div class="card"><div class="label">Atendimento</div><div class="value">{atendimento}</div></div></div><div class="card" style="margin-top:14px"><h2>Atendimento</h2><p>Este painel usa diretamente o núcleo de atendimento existente, preservando identificação, confirmação, autorização, registro e encerramento.</p><button type="button" onclick="location.reload()">Atualizar</button></div></main></body></html>'''


def criar_app_wsgi():
    def app(environ, start_response):
        corpo = renderizar_painel().encode("utf-8")
        start_response("200 OK", [("Content-Type", "text/html; charset=utf-8"), ("Content-Length", str(len(corpo)))])
        return [corpo]
    return app
