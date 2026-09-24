# RMD Atendimento Web

Interface web para o módulo de atendimento do ALFA.

Execução local:
python atendimento_web/app.py

Acesse http://127.0.0.1:8080.

Rotas:
GET /api/health
POST /api/atendimentos
POST /api/atendimentos/{session_id}/mensagens
POST /api/atendimentos/{session_id}/finalizar
GET /api/historico?empresa_id=...

O motor usado é o mesmo core.atendimento.AtendimentoBeta do ALFA.
