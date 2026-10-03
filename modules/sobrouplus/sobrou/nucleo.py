"""Núcleo do Sobrou+: erros, quem está agindo (Ator), permissões por papel, relógio e utilidades.

Padrão copiado e adaptado do RMD Atendimento (nucleo.py / permissoes.py): matriz recurso × ação,
com o escopo de empresa conferido em toda leitura e escrita.
"""
from __future__ import annotations

import json
import math
import os
import re
import secrets
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

try:
    from zoneinfo import ZoneInfo
    FUSO = ZoneInfo(os.getenv("SOBROU_FUSO", "America/Sao_Paulo"))
except Exception:  # noqa: BLE001 - Windows sem tzdata: horário de Brasília fixo (sem horário de verão)
    FUSO = timezone(timedelta(hours=-3))


class ErroNegocio(Exception):
    status = 400


class NaoEncontrado(ErroNegocio):
    status = 404


class SemPermissao(ErroNegocio):
    status = 403


class NaoAutenticado(ErroNegocio):
    status = 401


def novo_id() -> str:
    return secrets.token_hex(10)


# ------------------------------------------------------------------ tempo
def iso(dt: datetime) -> str:
    """Todas as datas são guardadas em UTC, no mesmo formato (comparáveis como texto)."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=FUSO)
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def ler_data(texto: str | None) -> datetime | None:
    """Aceita '2026-10-02T18:30' (horário local do Brasil) ou ISO com fuso."""
    if not texto:
        return None
    t = str(texto).strip().replace("Z", "+00:00").replace(" ", "T")
    try:
        dt = datetime.fromisoformat(t)
    except ValueError as e:
        raise ErroNegocio(f"Data/hora inválida: {texto}") from e
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=FUSO)
    return dt


def normalizar_data(texto: str | None, obrigatoria: bool = False, nome: str = "data") -> str | None:
    dt = ler_data(texto)
    if dt is None:
        if obrigatoria:
            raise ErroNegocio(f"Informe {nome}.")
        return None
    return iso(dt)


# ------------------------------------------------------------------ texto e números
def slugificar(texto: str) -> str:
    t = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode().lower()
    t = re.sub(r"[^a-z0-9]+", "-", t).strip("-")
    return t[:50] or "empresa"


def texto(valor, maximo: int = 300, obrigatorio: bool = False, nome: str = "campo") -> str | None:
    v = " ".join(str(valor or "").split()) if maximo <= 300 else str(valor or "").strip()
    if not v:
        if obrigatorio:
            raise ErroNegocio(f"Preencha {nome}.")
        return None
    return v[:maximo]


def inteiro(valor, nome: str = "valor", minimo: int | None = None, maximo: int | None = None, padrao=None) -> int:
    if valor in (None, ""):
        if padrao is not None:
            return padrao
        raise ErroNegocio(f"Informe {nome}.")
    try:
        n = int(valor)
    except (TypeError, ValueError) as e:
        raise ErroNegocio(f"{nome.capitalize()} inválido.") from e
    if minimo is not None and n < minimo:
        raise ErroNegocio(f"{nome.capitalize()} deve ser no mínimo {minimo}.")
    if maximo is not None and n > maximo:
        raise ErroNegocio(f"{nome.capitalize()} deve ser no máximo {maximo}.")
    return n


def centavos(valor, nome: str = "preço", obrigatorio: bool = True) -> int | None:
    """Aceita centavos (int) ou reais em texto ('12,50' / '12.50')."""
    if valor in (None, ""):
        if obrigatorio:
            raise ErroNegocio(f"Informe {nome}.")
        return None
    if isinstance(valor, int):
        n = valor
    else:
        t = str(valor).replace("R$", "").strip()
        if "," in t:
            t = t.replace(".", "").replace(",", ".")
        try:
            n = round(float(t) * 100)
        except ValueError as e:
            raise ErroNegocio(f"{nome.capitalize()} inválido.") from e
    if n < 0:
        raise ErroNegocio(f"{nome.capitalize()} não pode ser negativo.")
    return n


def real(valor, nome: str, minimo=None, maximo=None, obrigatorio=False) -> float | None:
    if valor in (None, ""):
        if obrigatorio:
            raise ErroNegocio(f"Informe {nome}.")
        return None
    try:
        n = float(str(valor).replace(",", "."))
    except ValueError as e:
        raise ErroNegocio(f"{nome.capitalize()} inválido.") from e
    if (minimo is not None and n < minimo) or (maximo is not None and n > maximo):
        raise ErroNegocio(f"{nome.capitalize()} fora do limite.")
    return n


def distancia_km(lat1, lng1, lat2, lng2) -> float | None:
    """Distância em linha reta (haversine). Sem coordenadas → None (nunca inventa)."""
    if None in (lat1, lng1, lat2, lng2):
        return None
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return round(2 * r * math.asin(math.sqrt(a)), 2)


def jcarregar(t, padrao):
    try:
        return json.loads(t) if t else padrao
    except (TypeError, ValueError):
        return padrao


# ------------------------------------------------------------------ papéis e permissões
PAPEIS = {
    "admin_sobrou": "Administrador Sobrou+",
    "operador_sobrou": "Operador Sobrou+",
    "admin_empresa": "Administrador da empresa",
    "operador_empresa": "Operador da empresa",
    "financeiro": "Financeiro",
    "logistica": "Logística",
    "entregador": "Entregador",
    "cliente": "Cliente",
    "instituicao": "Instituição",
}
PAPEIS_PLATAFORMA = ("admin_sobrou", "operador_sobrou")
PAPEIS_EMPRESA = ("admin_empresa", "operador_empresa", "financeiro", "logistica")

T = PAPEIS_PLATAFORMA
# recurso -> ação -> papéis
MATRIZ = {
    "empresas":      {"ver": T + ("admin_empresa",), "editar": T + ("admin_empresa",), "aprovar": T},
    "usuarios":      {"ver": T + ("admin_empresa",), "editar": ("admin_sobrou", "admin_empresa")},
    "unidades":      {"ver": T + PAPEIS_EMPRESA, "editar": T + ("admin_empresa",)},
    "ofertas":       {"ver": T + PAPEIS_EMPRESA, "editar": T + ("admin_empresa", "operador_empresa")},
    "preco":         {"editar": T + ("admin_empresa", "operador_empresa")},
    "estoque":       {"ver": T + PAPEIS_EMPRESA, "editar": T + ("admin_empresa", "operador_empresa")},
    "pedidos":       {"ver": T + PAPEIS_EMPRESA, "operar": T + ("admin_empresa", "operador_empresa"),
                      "cancelar": T + ("admin_empresa",)},
    "retirada":      {"validar": T + ("admin_empresa", "operador_empresa")},
    "dispatch":      {"ver": T + ("admin_empresa", "logistica"), "operar": T + ("admin_empresa", "logistica")},
    "entregadores":  {"ver": T + ("admin_empresa", "logistica"), "editar": T + ("admin_empresa", "logistica")},
    "financeiro":    {"ver": T + ("admin_empresa", "financeiro"), "repassar": ("admin_sobrou", "financeiro")},
    "doacoes":       {"ver": T + ("admin_empresa", "operador_empresa", "instituicao"),
                      "propor": T + ("admin_empresa", "operador_empresa")},
    "instituicoes":  {"ver": T + ("admin_empresa", "operador_empresa"), "autorizar": T},
    "impacto":       {"ver": T + PAPEIS_EMPRESA + ("instituicao",)},
    "auditoria":     {"ver": ("admin_sobrou", "admin_empresa")},
    "config":        {"ver": T + ("admin_empresa",), "editar": ("admin_sobrou", "admin_empresa")},
    "sistema":       {"ver": ("admin_sobrou",)},
}


@dataclass
class Ator:
    usuario_id: str | None
    papel: str
    nome: str = ""
    empresa_id: str | None = None
    instituicao_id: str | None = None
    ip: str | None = None
    extras: dict = field(default_factory=dict)

    @property
    def plataforma(self) -> bool:
        """Equipe Sobrou+ (vê todas as empresas). Financeiro/logística sem empresa = equipe da plataforma."""
        return self.papel in PAPEIS_PLATAFORMA or (self.papel in ("financeiro", "logistica") and not self.empresa_id)

    def pode(self, recurso: str, acao: str) -> bool:
        return self.papel in MATRIZ.get(recurso, {}).get(acao, ())

    def exigir(self, recurso: str, acao: str) -> None:
        if not self.pode(recurso, acao):
            raise SemPermissao("Seu perfil não tem permissão para esta ação.")

    def empresa_alvo(self, empresa_id: str | None) -> str:
        """Empresa em que a ação acontece. Usuário de empresa: sempre a dele (nunca outra)."""
        if self.plataforma:
            if not empresa_id:
                raise ErroNegocio("Escolha a empresa.")
            return empresa_id
        if not self.empresa_id:
            raise SemPermissao("Seu perfil não está ligado a uma empresa.")
        if empresa_id and empresa_id != self.empresa_id:
            raise SemPermissao("Você não tem acesso a esta empresa.")
        return self.empresa_id

    def conferir_empresa(self, registro: dict | None, o_que: str = "Registro") -> dict:
        """Empresa A nunca enxerga registro da empresa B — responde 'não encontrado' (não revela que existe)."""
        if not registro:
            raise NaoEncontrado(f"{o_que} não encontrado.")
        if self.plataforma:
            return registro
        if not self.empresa_id or registro.get("empresa_id") != self.empresa_id:
            raise NaoEncontrado(f"{o_que} não encontrado.")
        return registro


SISTEMA = Ator(None, "admin_sobrou", "Rotina automática")
