"""
Cliente REAL do BETA-CLOUD (Supabase, projeto dedicado — NUNCA
central-pesquisas) — integração final da plataforma.

    BETA LOCAL <-> memory/sync.py <-> BetaCloudClient <-> Supabase (beta-cloud)

Usa SOMENTE a REST API pública do Supabase (Data API/PostgREST +
Auth/GoTrue) via urllib — nenhum SDK novo instalado. NUNCA usa
service_role: a `publishable_key` vai sempre no header `apikey`; a
sessão do usuário autenticado (JWT do Supabase Auth) vai no header
`Authorization` — é essa sessão que a RLS do projeto usa pra decidir
o que cada usuário pode ler/escrever.

Configuração (nunca hardcoded — ver .env.example):
    BETA_CLOUD_PROJECT_URL
    BETA_CLOUD_PUBLISHABLE_KEY

Sem as duas definidas, `configurado()` é False e toda chamada de rede
é recusada com BetaCloudIndisponivel — nunca finge uma resposta.

SCHEMA REAL (confirmado pelo dono do projeto, ver relatório da
integração — NUNCA inventado por este código):
    beta_profiles(id, owner_key, display_name, organization_name,
                  profile_kind, organization_id, created_at, updated_at)
    beta_environments(id, profile_id, device_key, hostname, os_name,
                       cpu, ram_mb, gpu, has_microphone, has_camera,
                       internet_available, ollama_available,
                       local_models, discovered_apps, capabilities,
                       last_seen_at, created_at)
    beta_skills(id, profile_id, name, description, definition, source,
                approved, enabled, version, created_at, updated_at)
    beta_tasks(id, profile_id, device_id, task_type, status, objective,
               plan, current_step, context, result, error_message,
               created_at, updated_at, completed_at)
    beta_releases(id, component, version, min_core_version, platform,
                  package_url, sha256, release_notes, enabled, created_at)
    beta_memory(id, profile_id, device_id, memory_type, title, content,
                source, source_url, confidence, approved, embedding,
                metadata, created_at, updated_at)
    beta_skill_packages(id, skill_id, name, version, description,
                         manifest, package_url, sha256,
                         min_core_version, enabled, created_at)
    beta_sync_events(id, profile_id, device_id, entity_type, entity_id,
                      operation, payload, created_at, attempts,
                      last_attempt_at, synced_at)
    beta_organizations(id, name, kind, created_by, created_at, updated_at)
    beta_organization_members(organization_id, user_id, role, created_at)

`owner_key` de beta_profiles é sempre o `uid` do usuário autenticado
no Supabase Auth — NUNCA o nome digitado/falado (item de segurança:
"nunca usar nome como identidade de segurança").

IMPORTANTE sobre upsert: nenhuma das tabelas acima tem uma coluna
"evento_id" nem foi confirmada uma UNIQUE constraint composta — este
módulo NUNCA inventa uma constraint que não foi confirmada. Os
métodos abaixo tentam upsert pela chave que faz sentido pelo desenho
da tabela (ex.: `owner_key` em beta_profiles, `(profile_id,
device_key)` em beta_environments); se o Postgres recusar por falta
de uma constraint real, o erro REAL do servidor é propagado, nunca
mascarado (ver BetaCloudIndisponivel).
"""

import json
import os
import urllib.error
import urllib.request


class BetaCloudIndisponivel(Exception):
    """Configuração ausente, autenticação recusada, RLS negou, ou o
    Supabase respondeu erro/ficou inacessível — nunca usada para
    fingir sucesso."""


class BetaCloudClient:
    def __init__(self, url=None, publishable_key=None, timeout_segundos=10):
        self.url = (url or os.environ.get("BETA_CLOUD_PROJECT_URL") or "").rstrip("/")
        self.publishable_key = publishable_key or os.environ.get("BETA_CLOUD_PUBLISHABLE_KEY")
        self.timeout_segundos = timeout_segundos
        self._access_token = None
        self._refresh_token = None
        self._user_id = None

    def configurado(self):
        return bool(self.url and self.publishable_key)

    def _exigir_configurado(self):
        if not self.configurado():
            raise BetaCloudIndisponivel(
                "BETA_CLOUD_PROJECT_URL/BETA_CLOUD_PUBLISHABLE_KEY não configurados."
            )

    def autenticado(self):
        return bool(self._access_token)

    @property
    def owner_key(self):
        """uid do Supabase Auth do usuário autenticado — é isso, e só
        isso, que vira `beta_profiles.owner_key`. None sem login."""
        return self._user_id

    # ------------------------------------------------------------
    # Autenticação (Supabase Auth) — nunca guarda a senha
    # ------------------------------------------------------------

    def autenticar(self, email, senha):
        """POST /auth/v1/token?grant_type=password. Guarda só o JWT e
        o uid da sessão em memória do processo — a senha passada aqui
        nunca é gravada em disco, log, nem em nenhum atributo além da
        variável local `senha` desta chamada (descartada ao sair da
        função)."""
        self._exigir_configurado()
        corpo = json.dumps({"email": email, "password": senha}).encode("utf-8")
        requisicao = urllib.request.Request(
            f"{self.url}/auth/v1/token?grant_type=password",
            data=corpo,
            headers={"apikey": self.publishable_key, "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(requisicao, timeout=self.timeout_segundos) as resposta:
                dados = json.loads(resposta.read().decode("utf-8"))
        except urllib.error.HTTPError as erro:
            detalhe = erro.read().decode("utf-8", errors="ignore")
            raise BetaCloudIndisponivel(f"Falha na autenticação ({erro.code}): {detalhe}") from erro
        except urllib.error.URLError as erro:
            raise BetaCloudIndisponivel(f"BETA-CLOUD inacessível: {erro}") from erro

        self._access_token = dados.get("access_token")
        self._refresh_token = dados.get("refresh_token")
        self._user_id = (dados.get("user") or {}).get("id")
        return bool(self._access_token)

    # ------------------------------------------------------------
    # HTTP genérico (Data API / PostgREST)
    # ------------------------------------------------------------

    def _cabecalhos(self, upsert=False):
        cabecalhos = {
            "apikey": self.publishable_key,
            "Authorization": f"Bearer {self._access_token or self.publishable_key}",
            "Content-Type": "application/json",
        }
        cabecalhos["Prefer"] = (
            "resolution=merge-duplicates,return=representation" if upsert else "return=representation"
        )
        return cabecalhos

    def _requisicao(self, metodo, tabela, dados=None, filtro_query=""):
        self._exigir_configurado()
        url = f"{self.url}/rest/v1/{tabela}{filtro_query}"
        corpo = json.dumps(dados).encode("utf-8") if dados is not None else None
        requisicao = urllib.request.Request(
            url, data=corpo, headers=self._cabecalhos(upsert=(metodo == "POST")), method=metodo,
        )
        try:
            with urllib.request.urlopen(requisicao, timeout=self.timeout_segundos) as resposta:
                bruto = resposta.read().decode("utf-8")
                return json.loads(bruto) if bruto else None
        except urllib.error.HTTPError as erro:
            detalhe = erro.read().decode("utf-8", errors="ignore")
            raise BetaCloudIndisponivel(f"BETA-CLOUD respondeu {erro.code} para '{tabela}': {detalhe}") from erro
        except urllib.error.URLError as erro:
            raise BetaCloudIndisponivel(f"BETA-CLOUD inacessível: {erro}") from erro

    # ------------------------------------------------------------
    # beta_profiles
    # ------------------------------------------------------------

    def obter_ou_criar_perfil(self, display_name=None, profile_kind="personal", organization_name=None):
        """
        GET beta_profiles?owner_key=eq.<uid> -> devolve se existir;
        senão POST um novo. `owner_key` é sempre o uid autenticado —
        nunca o nome. Exige autenticar() bem-sucedido antes.
        """
        if not self._user_id:
            raise BetaCloudIndisponivel("Não autenticado — sem uid não há owner_key de verdade.")

        existentes = self._requisicao(
            "GET", "beta_profiles", filtro_query=f"?owner_key=eq.{self._user_id}&select=*"
        )
        if existentes:
            return existentes[0]

        novo = {
            "owner_key": self._user_id,
            "display_name": display_name,
            "profile_kind": profile_kind,
            "organization_name": organization_name,
        }
        criado = self._requisicao("POST", "beta_profiles", dados=novo)
        return criado[0] if isinstance(criado, list) and criado else criado

    # ------------------------------------------------------------
    # beta_environments (dispositivo)
    # ------------------------------------------------------------

    def registrar_dispositivo(self, profile_id, device_key, ambiente=None):
        """
        Upsert em beta_environments por (profile_id, device_key) — só
        funciona se essas duas colunas tiverem uma UNIQUE constraint
        composta real no banco; se não tiverem, o Postgres recusa o
        on_conflict e o erro real sobe (ver BetaCloudIndisponivel),
        nunca é mascarado.
        """
        ambiente = ambiente or {}
        linha = {
            "profile_id": profile_id,
            "device_key": device_key,
            "hostname": ambiente.get("hostname"),
            "os_name": ambiente.get("os_name"),
            "cpu": ambiente.get("cpu"),
            "ram_mb": ambiente.get("ram_mb"),
            "gpu": ambiente.get("gpu"),
            "has_microphone": ambiente.get("has_microphone"),
            "has_camera": ambiente.get("has_camera"),
            "internet_available": ambiente.get("internet_available"),
            "ollama_available": ambiente.get("ollama_available"),
            "local_models": ambiente.get("local_models", []),
            "discovered_apps": ambiente.get("discovered_apps", []),
            "capabilities": ambiente.get("capabilities", {}),
        }
        return self._requisicao(
            "POST", "beta_environments", dados=linha, filtro_query="?on_conflict=profile_id,device_key",
        )

    # ------------------------------------------------------------
    # beta_skills
    # ------------------------------------------------------------

    def sincronizar_skill(self, profile_id, nome, definicao, enabled=True, descricao=None, source=None):
        """Upsert em beta_skills por (profile_id, name) — mesma
        ressalva de constraint do método acima."""
        linha = {
            "profile_id": profile_id,
            "name": nome,
            "description": descricao,
            "definition": definicao,
            "source": source,
            "enabled": enabled,
        }
        return self._requisicao("POST", "beta_skills", dados=linha, filtro_query="?on_conflict=profile_id,name")

    # ------------------------------------------------------------
    # beta_tasks
    # ------------------------------------------------------------

    def registrar_tarefa(self, profile_id, objective, device_id=None, task_type=None, status="pending", plan=None, context=None):
        linha = {
            "profile_id": profile_id,
            "device_id": device_id,
            "task_type": task_type,
            "status": status,
            "objective": objective,
            "plan": plan or [],
            "context": context or {},
        }
        return self._requisicao("POST", "beta_tasks", dados=linha)

    # ------------------------------------------------------------
    # beta_sync_events (log/auditoria de sincronização)
    # ------------------------------------------------------------

    def registrar_evento_sync(self, profile_id, entity_type, operation, payload, device_id=None, entity_id=None):
        linha = {
            "profile_id": profile_id,
            "device_id": device_id,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "operation": operation,
            "payload": payload or {},
        }
        return self._requisicao("POST", "beta_sync_events", dados=linha)

    # ------------------------------------------------------------
    # Consultas (releases / marketplace)
    # ------------------------------------------------------------

    def consultar_releases(self, component=None):
        """GET beta_releases, mais recente primeiro."""
        filtro = "?select=*&order=created_at.desc"
        if component:
            filtro += f"&component=eq.{component}"
        return self._requisicao("GET", "beta_releases", filtro_query=filtro)

    def consultar_pacotes_skills(self):
        """GET beta_skill_packages — para o marketplace (ver
        marketplace/cliente_distribuicao.py)."""
        return self._requisicao("GET", "beta_skill_packages", filtro_query="?select=*")

    # ------------------------------------------------------------
    # Ponte com a fila local (ver memory/sync.py -> sincronizar)
    # ------------------------------------------------------------

    def enviar_evento(self, evento):
        """
        Adapta UM evento da fila local (ver memory/sync.py ->
        TIPOS_EVENTO) para a tabela/coluna reais. `evento["dados"]`
        precisa trazer os campos daquela tabela específica (quem
        enfileira decide o formato; este método só direciona).
        Retorna True/False — nunca levanta exceção pra quem chama
        (usado como `enviar_evento` de sync.sincronizar, que já trata
        cada evento independentemente).
        """
        tipo = evento.get("tipo")
        dados = evento.get("dados") or {}
        try:
            if tipo in ("PROFILE_UPDATED", "CONFIG_UPDATED"):
                self.obter_ou_criar_perfil(
                    display_name=dados.get("display_name"),
                    profile_kind=dados.get("profile_kind", "personal"),
                    organization_name=dados.get("organization_name"),
                )
            elif tipo in ("DEVICE_REGISTERED", "DEVICE_UPDATED"):
                self.registrar_dispositivo(
                    profile_id=dados["profile_id"], device_key=dados["device_key"],
                    ambiente=dados.get("ambiente"),
                )
            elif tipo in ("SKILL_ENABLED", "SKILL_DISABLED"):
                self.sincronizar_skill(
                    profile_id=dados["profile_id"], nome=dados["nome"],
                    definicao=dados.get("definicao", {}), enabled=(tipo == "SKILL_ENABLED"),
                )
            elif tipo == "TASK_COMPLETED":
                self.registrar_tarefa(
                    profile_id=dados["profile_id"], objective=dados.get("objective", ""),
                    device_id=dados.get("device_id"), status="completed",
                )
            elif tipo == "VERSION_UPDATED":
                # beta_releases é normalmente escrito por quem PUBLICA
                # uma versão, não pelo cliente local — aqui só
                # registra o evento de auditoria (ver abaixo).
                pass
            else:
                return False

            self.registrar_evento_sync(
                profile_id=dados.get("profile_id"), entity_type=tipo, operation="sync", payload=dados,
                device_id=dados.get("device_id"),
            )
            return True
        except BetaCloudIndisponivel:
            return False
        except KeyError:
            # Campo obrigatório faltando em `dados` — não inventa
            # valor, só reporta falha deste evento específico (fica
            # na fila local para tentar de novo, ver memory/sync.py).
            return False
