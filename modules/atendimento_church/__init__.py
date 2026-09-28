"""Módulo RMD Atendimento Church para o ALPHA.

Central de atendimento multicanal (WhatsApp, site, telefone,
presencial) adaptada para uso de igrejas: conversas, filas, equipe,
serviços, fluxos automáticos, agenda e relatórios. Persistência
compartilhada na beta-cloud (Supabase), em tabelas com prefixo
``church_`` (ver store.py) — isoladas do restante do ALFA/BETA.
"""

from .modulo import AtendimentoChurchModule
from .service import AtendimentoChurchService

__all__ = ["AtendimentoChurchModule", "AtendimentoChurchService"]
