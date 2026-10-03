"""Mapas: endereço → coordenadas (geocodificação) e distância/tempo PELAS RUAS (rota), com cache.

Provedores padrão (gratuitos, OpenStreetMap):
- rota: OSRM — https://router.project-osrm.org (servidor público de demonstração; para muito volume, trocar a URL
  pela de um OSRM próprio ou de um provedor pago em Integrações → Mapas);
- endereço: Nominatim — https://nominatim.openstreetmap.org (limite 1 consulta por segundo; o sistema respeita).
Se o serviço de rota não responder, o sistema usa uma ESTIMATIVA (linha reta × 1,35) e mostra isso na tela.
"""
from __future__ import annotations

import json
import threading
import time
import urllib.parse

from .nucleo import Ator, ErroNegocio, distancia_km, texto
from .rede import ErroRede

ROTAS_PADRAO = "https://router.project-osrm.org"
ENDERECOS_PADRAO = "https://nominatim.openstreetmap.org"
FATOR_ESTIMATIVA = 1.35
KMH_ESTIMATIVA = 22
_trava_nominatim = threading.Lock()
_rotas_memoria: dict[str, tuple[float, dict]] = {}   # cache de rotas em memória (nunca grava no banco: pode estar dentro de transação)
_trava_rotas = threading.Lock()
_ultima_consulta = [0.0]


class MapasMixin:
    def _cfg_mapas(self) -> dict:
        c = self.ler_integracao("mapas")
        return {"rotas_url": (c.get("rotas_url") or ROTAS_PADRAO).rstrip("/"),
                "enderecos_url": (c.get("enderecos_url") or ENDERECOS_PADRAO).rstrip("/"),
                "ligado": c.get("ligado", True) not in (False, 0, "0", "false")}

    def _cache_ler(self, chave: str, dias: int):
        r = self.banco.um("SELECT valor, criado_em FROM cache_mapas WHERE chave=?", (chave,))
        if not r:
            return None
        from .nucleo import ler_data
        idade = (self.agora_dt() - ler_data(r["criado_em"])).total_seconds()
        return json.loads(r["valor"]) if idade < dias * 86400 else None

    def _cache_gravar(self, chave: str, valor) -> None:
        self.banco.executar("INSERT INTO cache_mapas(chave, valor, criado_em) VALUES (?,?,?) ON CONFLICT(chave) DO UPDATE SET valor=excluded.valor, criado_em=excluded.criado_em",
                            (chave, json.dumps(valor), self.agora()))

    # ================================================================ ROTA (distância pelas ruas)
    def rota(self, lat1, lng1, lat2, lng2, com_linha: bool = False, so_cache: bool = False) -> dict | None:
        """Distância e tempo pelas ruas. so_cache=True: não chama a internet (usado dentro de transações)."""
        reta = distancia_km(lat1, lng1, lat2, lng2)
        if reta is None:
            return None
        estimada = {"km": round(reta * FATOR_ESTIMATIVA, 2), "minutos": max(1, round(reta * FATOR_ESTIMATIVA / KMH_ESTIMATIVA * 60)),
                    "fonte": "estimada", "linha": None}
        cfg = self._cfg_mapas()
        if not cfg["ligado"]:
            return estimada
        chave = f"{lat1:.4f},{lng1:.4f};{lat2:.4f},{lng2:.4f}:{int(com_linha)}"
        with _trava_rotas:
            g = _rotas_memoria.get(chave)
        if g and time.time() - g[0] < 6 * 3600:
            return g[1]
        if so_cache:
            return estimada
        url = (f"{cfg['rotas_url']}/route/v1/driving/{lng1:.6f},{lat1:.6f};{lng2:.6f},{lat2:.6f}"
               f"?overview={'simplified' if com_linha else 'false'}&geometries=geojson")
        try:
            r = self.rede("GET", url, tempo=6)
            if r.get("code") != "Ok" or not r.get("routes"):
                return estimada
            rt = r["routes"][0]
            linha = [[c[1], c[0]] for c in rt.get("geometry", {}).get("coordinates", [])] if com_linha else None
            res = {"km": round(rt["distance"] / 1000, 2), "minutos": max(1, round(rt["duration"] / 60)), "fonte": "ruas", "linha": linha}
            with _trava_rotas:
                if len(_rotas_memoria) > 5000:
                    _rotas_memoria.clear()
                _rotas_memoria[chave] = (time.time(), res)
            return res
        except (ErroRede, KeyError, TypeError, ValueError):
            return estimada

    # ================================================================ ENDEREÇO → COORDENADAS
    def buscar_endereco(self, ator: Ator, consulta: str) -> list[dict]:
        q = texto(consulta, 200, True, "o endereço")
        if len(q) < 4:
            raise ErroNegocio("Digite o endereço com rua e cidade.")
        cfg = self._cfg_mapas()
        if not cfg["ligado"]:
            raise ErroNegocio("A busca de endereço está desligada em Integrações → Mapas.")
        chave = "end:" + q.lower()
        guardada = self._cache_ler(chave, 30)
        if guardada is not None:
            return guardada
        url = f"{cfg['enderecos_url']}/search?" + urllib.parse.urlencode(
            {"q": q, "format": "jsonv2", "limit": 5, "countrycodes": "br", "addressdetails": 0, "accept-language": "pt-BR"})
        with _trava_nominatim:  # política do Nominatim: no máximo 1 consulta por segundo
            espera = 1.05 - (time.time() - _ultima_consulta[0])
            if espera > 0:
                time.sleep(espera)
            try:
                r = self.rede("GET", url, tempo=8)
            except ErroRede as e:
                raise ErroNegocio("O serviço de endereços não respondeu agora. Tente de novo em instantes ou use a localização do aparelho.") from e
            finally:
                _ultima_consulta[0] = time.time()
        res = [{"nome": x.get("display_name"), "lat": float(x["lat"]), "lng": float(x["lon"])} for x in (r or []) if "lat" in x]
        self._cache_gravar(chave, res)
        return res
