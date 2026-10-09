"""Banco de dados do Sobrou+ (SQLite, arquivo próprio — nunca o do RMD Delivery nem o do RMD Atendimento).

Mesmo mecanismo testado no RMD Atendimento: lista de migrações numeradas, aplicadas uma vez,
uma conexão curta por operação (seguro com vários usuários ao mesmo tempo).
"""
from __future__ import annotations

import os
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


def pasta_dados() -> Path:
    return Path(os.getenv("SOBROU_DADOS", str(RAIZ / "data")))


def agora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


ESQUEMA = [
    # 1 — base: empresas, usuários, sessões, auditoria, configuração
    """
    CREATE TABLE empresas (
        id TEXT PRIMARY KEY,
        nome TEXT NOT NULL,
        slug TEXT NOT NULL UNIQUE,
        tipo TEXT NOT NULL DEFAULT 'restaurante',
        documento TEXT,
        telefone TEXT,
        email TEXT,
        ativa INTEGER NOT NULL DEFAULT 1,
        aprovada INTEGER NOT NULL DEFAULT 0,
        taxa_percentual REAL,
        demonstracao INTEGER NOT NULL DEFAULT 0,
        criada_em TEXT NOT NULL
    );
    CREATE TABLE usuarios (
        id TEXT PRIMARY KEY,
        empresa_id TEXT REFERENCES empresas(id),
        instituicao_id TEXT,
        nome TEXT NOT NULL,
        email TEXT NOT NULL UNIQUE COLLATE NOCASE,
        telefone TEXT,
        senha_hash TEXT NOT NULL,
        senha_salt TEXT NOT NULL,
        papel TEXT NOT NULL,
        ativo INTEGER NOT NULL DEFAULT 1,
        trocar_senha INTEGER NOT NULL DEFAULT 0,
        tentativas_falhas INTEGER NOT NULL DEFAULT 0,
        bloqueado_ate TEXT,
        ultimo_acesso TEXT,
        criado_em TEXT NOT NULL
    );
    CREATE TABLE sessoes (
        token_hash TEXT PRIMARY KEY,
        usuario_id TEXT NOT NULL REFERENCES usuarios(id),
        criada_em TEXT NOT NULL,
        expira_em TEXT NOT NULL,
        ip TEXT
    );
    CREATE TABLE auditoria (
        id TEXT PRIMARY KEY,
        quando TEXT NOT NULL,
        usuario_id TEXT,
        empresa_id TEXT,
        acao TEXT NOT NULL,
        alvo TEXT,
        detalhe TEXT,
        ip TEXT
    );
    CREATE INDEX ix_auditoria ON auditoria(empresa_id, quando);
    CREATE TABLE config (
        chave TEXT PRIMARY KEY,
        valor TEXT
    );
    CREATE TABLE config_empresa (
        empresa_id TEXT PRIMARY KEY REFERENCES empresas(id),
        tema TEXT NOT NULL DEFAULT 'padrao',
        nome_exibicao TEXT,
        aceita_retirada INTEGER NOT NULL DEFAULT 1,
        aceita_entrega INTEGER NOT NULL DEFAULT 0,
        taxa_entrega_centavos INTEGER NOT NULL DEFAULT 0,
        raio_entrega_km REAL NOT NULL DEFAULT 5
    );
    """,
    # 2 — unidades, ofertas, estoque, preço, fotos
    """
    CREATE TABLE unidades (
        id TEXT PRIMARY KEY,
        empresa_id TEXT NOT NULL REFERENCES empresas(id),
        nome TEXT NOT NULL,
        endereco TEXT,
        bairro TEXT,
        cidade TEXT,
        lat REAL,
        lng REAL,
        telefone TEXT,
        instrucoes_retirada TEXT,
        ativa INTEGER NOT NULL DEFAULT 1,
        criada_em TEXT NOT NULL
    );
    CREATE TABLE fotos (
        id TEXT PRIMARY KEY,
        empresa_id TEXT NOT NULL REFERENCES empresas(id),
        arquivo TEXT NOT NULL,
        miniatura TEXT,
        tipo TEXT NOT NULL,
        bytes INTEGER NOT NULL,
        criada_em TEXT NOT NULL
    );
    CREATE TABLE ofertas (
        id TEXT PRIMARY KEY,
        empresa_id TEXT NOT NULL REFERENCES empresas(id),
        unidade_id TEXT NOT NULL REFERENCES unidades(id),
        tipo TEXT NOT NULL,                 -- produto | cesta | kit
        nome TEXT NOT NULL,
        descricao TEXT,
        categoria TEXT NOT NULL,
        foto_id TEXT REFERENCES fotos(id),
        preco_normal_centavos INTEGER NOT NULL,
        preco_centavos INTEGER NOT NULL,    -- preço Sobrou+ vigente
        preco_minimo_centavos INTEGER,      -- piso do preço inteligente (definido pelo parceiro)
        valor_estimado_min_centavos INTEGER,-- cesta surpresa: faixa de valor
        valor_estimado_max_centavos INTEGER,
        quantidade_total INTEGER NOT NULL,
        reservada INTEGER NOT NULL DEFAULT 0,
        vendida INTEGER NOT NULL DEFAULT 0,
        expirada INTEGER NOT NULL DEFAULT 0,
        destinada INTEGER NOT NULL DEFAULT 0,
        limite_por_cliente INTEGER NOT NULL DEFAULT 5,
        estoque_critico INTEGER NOT NULL DEFAULT 2,
        peso_kg_unidade REAL NOT NULL DEFAULT 0.5,
        inicio TEXT NOT NULL,
        fim TEXT NOT NULL,                  -- fim da venda
        retirada_inicio TEXT,
        retirada_fim TEXT,
        permite_retirada INTEGER NOT NULL DEFAULT 1,
        permite_entrega INTEGER NOT NULL DEFAULT 0,
        validade TEXT,                      -- data/hora limite para consumo
        prioridade INTEGER NOT NULL DEFAULT 0,
        regra_preco TEXT NOT NULL DEFAULT 'fixo',  -- fixo | progressivo | estoque
        regra_preco_dados TEXT,             -- JSON com os degraus
        status TEXT NOT NULL DEFAULT 'rascunho',   -- rascunho | ativa | pausada | esgotada | encerrada
        criada_por TEXT,
        criada_em TEXT NOT NULL,
        atualizada_em TEXT NOT NULL
    );
    CREATE INDEX ix_ofertas_vitrine ON ofertas(status, fim);
    CREATE INDEX ix_ofertas_empresa ON ofertas(empresa_id, status);
    CREATE TABLE movimentos_estoque (
        id TEXT PRIMARY KEY,
        oferta_id TEXT NOT NULL REFERENCES ofertas(id),
        empresa_id TEXT NOT NULL,
        tipo TEXT NOT NULL,     -- entrada | reserva | liberacao | venda | cancelamento | expiracao | doacao | ajuste
        quantidade INTEGER NOT NULL,
        pedido_id TEXT,
        usuario_id TEXT,
        motivo TEXT,
        quando TEXT NOT NULL
    );
    CREATE INDEX ix_mov_oferta ON movimentos_estoque(oferta_id, quando);
    CREATE TABLE historico_precos (
        id TEXT PRIMARY KEY,
        oferta_id TEXT NOT NULL REFERENCES ofertas(id),
        empresa_id TEXT NOT NULL,
        de_centavos INTEGER NOT NULL,
        para_centavos INTEGER NOT NULL,
        origem TEXT NOT NULL,   -- manual | regra
        motivo TEXT,
        usuario_id TEXT,
        quando TEXT NOT NULL
    );
    """,
    # 3 — clientes, pedidos, histórico, pagamentos
    """
    CREATE TABLE pedidos (
        id TEXT PRIMARY KEY,
        numero INTEGER NOT NULL,
        empresa_id TEXT NOT NULL REFERENCES empresas(id),
        unidade_id TEXT NOT NULL REFERENCES unidades(id),
        cliente_id TEXT NOT NULL REFERENCES usuarios(id),
        modo TEXT NOT NULL,             -- retirada | entrega
        status TEXT NOT NULL,
        subtotal_centavos INTEGER NOT NULL,
        normal_centavos INTEGER NOT NULL,
        entrega_centavos INTEGER NOT NULL DEFAULT 0,
        total_centavos INTEGER NOT NULL,
        taxa_percentual REAL NOT NULL,
        taxa_centavos INTEGER NOT NULL,
        repasse_centavos INTEGER NOT NULL,
        endereco_entrega TEXT,
        entrega_lat REAL,
        entrega_lng REAL,
        codigo_retirada TEXT NOT NULL,
        token_retirada TEXT NOT NULL UNIQUE,
        reserva_expira_em TEXT,
        janela_inicio TEXT,
        janela_fim TEXT,
        peso_kg REAL NOT NULL DEFAULT 0,
        observacao TEXT,
        criado_em TEXT NOT NULL,
        atualizado_em TEXT NOT NULL,
        concluido_em TEXT
    );
    CREATE INDEX ix_pedidos_empresa ON pedidos(empresa_id, status, criado_em);
    CREATE INDEX ix_pedidos_cliente ON pedidos(cliente_id, criado_em);
    CREATE TABLE pedido_itens (
        id TEXT PRIMARY KEY,
        pedido_id TEXT NOT NULL REFERENCES pedidos(id),
        oferta_id TEXT NOT NULL REFERENCES ofertas(id),
        nome TEXT NOT NULL,
        quantidade INTEGER NOT NULL,
        preco_centavos INTEGER NOT NULL,
        preco_normal_centavos INTEGER NOT NULL,
        peso_kg REAL NOT NULL
    );
    CREATE TABLE pedido_historico (
        id TEXT PRIMARY KEY,
        pedido_id TEXT NOT NULL REFERENCES pedidos(id),
        de_status TEXT,
        para_status TEXT NOT NULL,
        usuario_id TEXT,
        nota TEXT,
        quando TEXT NOT NULL
    );
    CREATE INDEX ix_hist_pedido ON pedido_historico(pedido_id, quando);
    CREATE TABLE pagamentos (
        id TEXT PRIMARY KEY,
        pedido_id TEXT NOT NULL REFERENCES pedidos(id),
        empresa_id TEXT NOT NULL,
        meio TEXT NOT NULL,             -- teste | pix | cartao (real = pendente de integração)
        valor_centavos INTEGER NOT NULL,
        status TEXT NOT NULL,           -- pendente | aprovado | recusado | estornado
        referencia_externa TEXT,
        criado_em TEXT NOT NULL,
        atualizado_em TEXT NOT NULL
    );
    CREATE TABLE contadores (
        nome TEXT PRIMARY KEY,
        valor INTEGER NOT NULL
    );
    """,
    # 4 — entregadores e dispatch
    """
    CREATE TABLE entregadores (
        id TEXT PRIMARY KEY,
        usuario_id TEXT NOT NULL UNIQUE REFERENCES usuarios(id),
        empresa_id TEXT REFERENCES empresas(id),   -- vazio = entregador da rede Sobrou+
        tipo TEXT NOT NULL DEFAULT 'sobrou',      -- proprio | sobrou | parceiro
        veiculo TEXT,
        online INTEGER NOT NULL DEFAULT 0,
        lat REAL,
        lng REAL,
        posicao_em TEXT,
        capacidade INTEGER NOT NULL DEFAULT 2,
        criado_em TEXT NOT NULL
    );
    CREATE TABLE entregas (
        id TEXT PRIMARY KEY,
        pedido_id TEXT NOT NULL UNIQUE REFERENCES pedidos(id),
        empresa_id TEXT NOT NULL,
        entregador_id TEXT REFERENCES entregadores(id),
        status TEXT NOT NULL,      -- aguardando | ofertada | aceita | em_coleta | coletada | em_rota | entregue | falhou
        oferta_expira_em TEXT,
        recusados TEXT NOT NULL DEFAULT '[]',
        distancia_km REAL,
        eta_min INTEGER,
        prioridade REAL,
        ganho_centavos INTEGER NOT NULL DEFAULT 0,
        criada_em TEXT NOT NULL,
        atualizada_em TEXT NOT NULL
    );
    CREATE INDEX ix_entregas_status ON entregas(status);
    CREATE TABLE posicoes (
        id TEXT PRIMARY KEY,
        entregador_id TEXT NOT NULL,
        lat REAL NOT NULL,
        lng REAL NOT NULL,
        precisao_m REAL,
        quando TEXT NOT NULL
    );
    CREATE INDEX ix_posicoes ON posicoes(entregador_id, quando);
    """,
    # 5 — instituições, doações, repasses
    """
    CREATE TABLE instituicoes (
        id TEXT PRIMARY KEY,
        nome TEXT NOT NULL,
        documento TEXT,
        responsavel TEXT,
        telefone TEXT,
        endereco TEXT,
        cidade TEXT,
        pessoas_atendidas INTEGER NOT NULL DEFAULT 0,
        autorizada INTEGER NOT NULL DEFAULT 0,
        autorizada_por TEXT,
        autorizada_em TEXT,
        criada_em TEXT NOT NULL
    );
    CREATE TABLE doacoes (
        id TEXT PRIMARY KEY,
        empresa_id TEXT NOT NULL REFERENCES empresas(id),
        oferta_id TEXT REFERENCES ofertas(id),
        instituicao_id TEXT NOT NULL REFERENCES instituicoes(id),
        quantidade INTEGER NOT NULL,
        peso_kg REAL NOT NULL,
        descricao TEXT,
        status TEXT NOT NULL,     -- proposta | aceita | recusada | coletada | destinada | cancelada
        proposta_por TEXT, proposta_em TEXT,
        aceita_por TEXT, aceita_em TEXT,
        coleta_por TEXT, coleta_em TEXT, coleta_responsavel TEXT,
        destinada_por TEXT, destinada_em TEXT, pessoas_beneficiadas INTEGER,
        nota TEXT
    );
    CREATE TABLE repasses (
        id TEXT PRIMARY KEY,
        empresa_id TEXT NOT NULL REFERENCES empresas(id),
        periodo_inicio TEXT NOT NULL,
        periodo_fim TEXT NOT NULL,
        pedidos INTEGER NOT NULL,
        bruto_centavos INTEGER NOT NULL,
        taxa_centavos INTEGER NOT NULL,
        valor_centavos INTEGER NOT NULL,
        status TEXT NOT NULL,     -- calculado | pago
        pago_em TEXT,
        referencia TEXT,
        criado_por TEXT,
        criado_em TEXT NOT NULL
    );
    ALTER TABLE pedidos ADD COLUMN repasse_id TEXT;
    """,
    # 6 — preço base, várias fotos, favoritos, notificações internas, erros, doação de pedido não retirado
    """
    ALTER TABLE ofertas ADD COLUMN preco_base_centavos INTEGER;
    UPDATE ofertas SET preco_base_centavos = preco_centavos;
    CREATE TABLE oferta_fotos (
        oferta_id TEXT NOT NULL REFERENCES ofertas(id),
        foto_id TEXT NOT NULL REFERENCES fotos(id),
        ordem INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY (oferta_id, foto_id)
    );
    CREATE TABLE favoritos (
        cliente_id TEXT NOT NULL REFERENCES usuarios(id),
        empresa_id TEXT NOT NULL REFERENCES empresas(id),
        criado_em TEXT NOT NULL,
        PRIMARY KEY (cliente_id, empresa_id)
    );
    CREATE TABLE notificacoes (
        id TEXT PRIMARY KEY,
        usuario_id TEXT,
        empresa_id TEXT,
        papel_alvo TEXT,
        texto TEXT NOT NULL,
        link TEXT,
        lida INTEGER NOT NULL DEFAULT 0,
        criada_em TEXT NOT NULL
    );
    CREATE INDEX ix_notif_usuario ON notificacoes(usuario_id, lida, criada_em);
    CREATE INDEX ix_notif_empresa ON notificacoes(empresa_id, lida, criada_em);
    CREATE TABLE erros_sistema (
        id TEXT PRIMARY KEY,
        quando TEXT NOT NULL,
        rota TEXT,
        metodo TEXT,
        tipo TEXT,
        mensagem TEXT
    );
    ALTER TABLE doacoes ADD COLUMN pedido_id TEXT REFERENCES pedidos(id);
    ALTER TABLE doacoes ADD COLUMN origem TEXT NOT NULL DEFAULT 'oferta';
    """,
    # 7 — integrações (pagamento real, WhatsApp) e mapas (cache de endereço e de rota)
    """
    ALTER TABLE pagamentos ADD COLUMN externo_id TEXT;
    ALTER TABLE pagamentos ADD COLUMN qr_code TEXT;
    ALTER TABLE pagamentos ADD COLUMN qr_base64 TEXT;
    ALTER TABLE pagamentos ADD COLUMN link_pagamento TEXT;
    ALTER TABLE pagamentos ADD COLUMN expira_em TEXT;
    CREATE INDEX ix_pag_externo ON pagamentos(externo_id);
    CREATE TABLE fila_mensagens (
        id TEXT PRIMARY KEY,
        canal TEXT NOT NULL DEFAULT 'whatsapp',
        usuario_id TEXT,
        telefone TEXT,
        texto TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pendente',   -- pendente | enviada | falhou | desligado
        tentativas INTEGER NOT NULL DEFAULT 0,
        erro TEXT,
        criada_em TEXT NOT NULL,
        enviada_em TEXT
    );
    CREATE INDEX ix_fila_status ON fila_mensagens(status, criada_em);
    CREATE TABLE cache_mapas (
        chave TEXT PRIMARY KEY,
        valor TEXT NOT NULL,
        criado_em TEXT NOT NULL
    );
    """,    # 8 — recuperação de senha, termos (LGPD), avaliações, planos e faturas, aviso no celular (push)
    """
    ALTER TABLE usuarios ADD COLUMN aceite_termos_em TEXT;
    ALTER TABLE usuarios ADD COLUMN excluido_em TEXT;
    CREATE TABLE codigos_senha (
        id TEXT PRIMARY KEY,
        usuario_id TEXT NOT NULL REFERENCES usuarios(id),
        codigo_hash TEXT NOT NULL,
        expira_em TEXT NOT NULL,
        tentativas INTEGER NOT NULL DEFAULT 0,
        usado INTEGER NOT NULL DEFAULT 0,
        criado_em TEXT NOT NULL
    );
    CREATE TABLE avaliacoes (
        id TEXT PRIMARY KEY,
        pedido_id TEXT NOT NULL UNIQUE REFERENCES pedidos(id),
        empresa_id TEXT NOT NULL REFERENCES empresas(id),
        cliente_id TEXT NOT NULL REFERENCES usuarios(id),
        nota INTEGER NOT NULL,
        comentario TEXT,
        resposta TEXT,
        respondida_em TEXT,
        criada_em TEXT NOT NULL
    );
    CREATE INDEX ix_aval_empresa ON avaliacoes(empresa_id, criada_em);
    CREATE TABLE planos (
        id TEXT PRIMARY KEY,
        nome TEXT NOT NULL,
        descricao TEXT,
        mensalidade_centavos INTEGER NOT NULL DEFAULT 0,
        taxa_percentual REAL NOT NULL,
        limite_ofertas INTEGER,
        destaque INTEGER NOT NULL DEFAULT 0,
        ativo INTEGER NOT NULL DEFAULT 1,
        criado_em TEXT NOT NULL
    );
    ALTER TABLE empresas ADD COLUMN plano_id TEXT REFERENCES planos(id);
    CREATE TABLE faturas (
        id TEXT PRIMARY KEY,
        empresa_id TEXT NOT NULL REFERENCES empresas(id),
        plano_id TEXT,
        competencia TEXT NOT NULL,
        valor_centavos INTEGER NOT NULL,
        status TEXT NOT NULL DEFAULT 'aberta',
        vence_em TEXT,
        paga_em TEXT,
        referencia TEXT,
        criada_em TEXT NOT NULL,
        UNIQUE(empresa_id, competencia)
    );
    CREATE TABLE push_inscricoes (
        id TEXT PRIMARY KEY,
        usuario_id TEXT NOT NULL REFERENCES usuarios(id),
        endpoint TEXT NOT NULL UNIQUE,
        p256dh TEXT NOT NULL,
        auth TEXT NOT NULL,
        criada_em TEXT NOT NULL
    );
    """,    # 9 — link de acesso (convite), verificação em 2 etapas do Desenvolvedor, dados para repasse
    """
    CREATE TABLE convites (
        id TEXT PRIMARY KEY,
        usuario_id TEXT NOT NULL REFERENCES usuarios(id),
        token_hash TEXT NOT NULL UNIQUE,
        expira_em TEXT NOT NULL,
        usado_em TEXT,
        criado_por TEXT,
        criado_em TEXT NOT NULL
    );
    ALTER TABLE usuarios ADD COLUMN totp_segredo TEXT;
    ALTER TABLE usuarios ADD COLUMN totp_ultimo INTEGER;
    ALTER TABLE config_empresa ADD COLUMN pix_tipo TEXT;
    ALTER TABLE config_empresa ADD COLUMN pix_chave TEXT;
    ALTER TABLE config_empresa ADD COLUMN titular TEXT;
    ALTER TABLE config_empresa ADD COLUMN banco TEXT;
    ALTER TABLE config_empresa ADD COLUMN whatsapp_loja TEXT;
    """,    # 10 — "Criador" passa a se chamar "Desenvolvedor RMD" (nomes já gravados)
    """
    UPDATE usuarios SET nome='Desenvolvedor RMD' WHERE nome='Criador do Sobrou+';
    UPDATE usuarios SET nome=replace(nome, '(teste do Criador)', '(teste RMD)') WHERE nome LIKE '%(teste do Criador)%';
    UPDATE usuarios SET email=replace(email, '@criador.sobrou.invalid', '@rmd.sobrou.invalid') WHERE email LIKE '%@criador.sobrou.invalid';
    UPDATE empresas SET nome='Loja Teste RMD' WHERE nome='Loja Teste do Criador';
    UPDATE instituicoes SET nome='Instituição Teste RMD' WHERE nome='Instituição Teste do Criador';
    UPDATE ofertas SET descricao='Oferta de TESTE RMD (imagem ilustrativa)' WHERE descricao='Oferta de TESTE do Criador (imagem ilustrativa)';
    """,
    # 11 — trilha segura de pagamento real e eventos idempotentes do provedor
    """
    ALTER TABLE pagamentos ADD COLUMN gateway TEXT;
    ALTER TABLE pagamentos ADD COLUMN ambiente TEXT;
    ALTER TABLE pagamentos ADD COLUMN idempotency_key TEXT;
    ALTER TABLE pagamentos ADD COLUMN preference_id TEXT;
    ALTER TABLE pagamentos ADD COLUMN parcelas INTEGER;
    ALTER TABLE pagamentos ADD COLUMN moeda TEXT NOT NULL DEFAULT 'BRL';
    ALTER TABLE pagamentos ADD COLUMN detalhe_status TEXT;
    ALTER TABLE pagamentos ADD COLUMN resposta_gateway TEXT;
    ALTER TABLE pagamentos ADD COLUMN estorno_em TEXT;
    ALTER TABLE pagamentos ADD COLUMN cancelado_em TEXT;
    ALTER TABLE pagamentos ADD COLUMN aprovado_em TEXT;
    CREATE UNIQUE INDEX ux_pag_idempotencia ON pagamentos(idempotency_key) WHERE idempotency_key IS NOT NULL;
    CREATE UNIQUE INDEX ux_pag_gateway_externo ON pagamentos(gateway, ambiente, externo_id) WHERE externo_id IS NOT NULL;
    CREATE TABLE eventos_pagamento (
        gateway TEXT NOT NULL,
        ambiente TEXT NOT NULL,
        evento_id TEXT NOT NULL,
        pagamento_id TEXT,
        tipo TEXT,
        recebido_em TEXT NOT NULL,
        processado_em TEXT,
        resultado TEXT,
        PRIMARY KEY (gateway, ambiente, evento_id)
    );
    CREATE INDEX ix_eventos_pagamento_id ON eventos_pagamento(pagamento_id, recebido_em);
    """,
    # 12 — remove credenciais antigas do gateway que eram guardadas na configuração do app
    """
    DELETE FROM config WHERE chave='int:mercadopago';
    """,
    # 13 — avaliação bilateral e pontos de fidelidade para pedidos realmente concluídos
    """
    CREATE TABLE avaliacoes_clientes (
        id TEXT PRIMARY KEY,
        pedido_id TEXT NOT NULL UNIQUE REFERENCES pedidos(id),
        empresa_id TEXT NOT NULL REFERENCES empresas(id),
        cliente_id TEXT NOT NULL REFERENCES usuarios(id),
        nota INTEGER NOT NULL CHECK (nota BETWEEN 1 AND 5),
        comentario TEXT,
        criada_em TEXT NOT NULL
    );
    CREATE INDEX ix_aval_cliente_empresa ON avaliacoes_clientes(empresa_id, criada_em);
    CREATE TABLE pontos_fidelidade (
        pedido_id TEXT PRIMARY KEY REFERENCES pedidos(id),
        cliente_id TEXT NOT NULL REFERENCES usuarios(id),
        pontos INTEGER NOT NULL CHECK (pontos > 0),
        criada_em TEXT NOT NULL
    );
    CREATE INDEX ix_pontos_cliente ON pontos_fidelidade(cliente_id, criada_em);
    """,
    # 14 — eventos mínimos de navegação para análise de conversão da plataforma; sem IP, nome ou contato
    """
    CREATE TABLE eventos_uso (
        id TEXT PRIMARY KEY,
        visitante TEXT NOT NULL,
        tipo TEXT NOT NULL CHECK (tipo IN ('visita', 'loja', 'oferta', 'checkout', 'pedido')),
        empresa_id TEXT,
        oferta_id TEXT,
        criado_em TEXT NOT NULL
    );
    CREATE INDEX ix_eventos_data ON eventos_uso(criado_em, tipo);
    CREATE INDEX ix_eventos_empresa ON eventos_uso(empresa_id, criado_em);
    """,
    # 15 — ocorrências reais registradas pelo entregador durante uma tentativa de entrega
    """
    CREATE TABLE ocorrencias_entrega (
        id TEXT PRIMARY KEY,
        entrega_id TEXT NOT NULL REFERENCES entregas(id),
        entregador_id TEXT NOT NULL REFERENCES entregadores(id),
        tipo TEXT NOT NULL CHECK (tipo IN ('cliente_recusou', 'cliente_nao_pagou', 'cliente_ausente', 'outro')),
        descricao TEXT,
        criada_em TEXT NOT NULL
    );
    CREATE INDEX ix_ocorrencias_entrega ON ocorrencias_entrega(entrega_id, criada_em);
    """,
    # 16 — liberação de recursos por empresa, com herança do padrão da plataforma e trilha de auditoria
    """
    CREATE TABLE recursos_empresa (
        empresa_id TEXT NOT NULL REFERENCES empresas(id) ON DELETE CASCADE,
        recurso TEXT NOT NULL,
        habilitado INTEGER NOT NULL CHECK (habilitado IN (0,1)),
        atualizado_por TEXT REFERENCES usuarios(id),
        atualizado_em TEXT NOT NULL,
        PRIMARY KEY (empresa_id, recurso)
    );
    CREATE INDEX ix_recursos_empresa_recurso ON recursos_empresa(recurso, habilitado);
    """,
    # 17 — registra o custo do hash da senha para endurecimento gradual sem invalidar contas existentes
    """
    ALTER TABLE usuarios ADD COLUMN senha_iteracoes INTEGER NOT NULL DEFAULT 200000;
    """,
    # 18 — testes com os sócios: cada pessoa ganha uma conta por aplicativo (Central, Loja, Caixa, Entregador, Cliente)
    """
    CREATE TABLE testadores (
        id TEXT PRIMARY KEY,
        nome TEXT NOT NULL,
        telefone TEXT,
        ativo INTEGER NOT NULL DEFAULT 1,
        criado_por TEXT,
        criado_em TEXT NOT NULL
    );
    CREATE TABLE testador_contas (
        testador_id TEXT NOT NULL REFERENCES testadores(id),
        app TEXT NOT NULL,
        usuario_id TEXT NOT NULL REFERENCES usuarios(id),
        PRIMARY KEY (testador_id, app)
    );
    """,
]

_LOCK = threading.Lock()
_PRONTOS: set[str] = set()


def _abrir(caminho: Path) -> sqlite3.Connection:
    c = sqlite3.connect(str(caminho), timeout=15, isolation_level=None, check_same_thread=False)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")
    c.execute("PRAGMA busy_timeout = 15000")
    return c


def preparar(caminho: Path) -> Path:
    chave = str(caminho.resolve())
    with _LOCK:
        if chave in _PRONTOS and caminho.exists():
            return caminho
        caminho.parent.mkdir(parents=True, exist_ok=True)
        c = _abrir(caminho)
        try:
            c.execute("PRAGMA journal_mode = WAL")
            c.execute("CREATE TABLE IF NOT EXISTS versao_esquema (versao INTEGER NOT NULL)")
            atual = c.execute("SELECT MAX(versao) AS v FROM versao_esquema").fetchone()["v"] or 0
            for numero, sql in enumerate(ESQUEMA, start=1):
                if numero > atual:
                    c.executescript("BEGIN;" + sql + f"; INSERT INTO versao_esquema(versao) VALUES ({numero}); COMMIT;")
        finally:
            c.close()
        _PRONTOS.add(chave)
    return caminho


class Banco:
    def __init__(self, caminho: Path | str | None = None):
        self.caminho = preparar(Path(caminho) if caminho else pasta_dados() / "sobrou.db")

    def _c(self) -> sqlite3.Connection:
        return _abrir(self.caminho)

    def um(self, sql: str, p=()) -> dict | None:
        c = self._c()
        try:
            r = c.execute(sql, p).fetchone()
            return dict(r) if r else None
        finally:
            c.close()

    def todos(self, sql: str, p=()) -> list[dict]:
        c = self._c()
        try:
            return [dict(r) for r in c.execute(sql, p).fetchall()]
        finally:
            c.close()

    def executar(self, sql: str, p=()) -> int:
        c = self._c()
        try:
            return c.execute(sql, p).rowcount
        finally:
            c.close()

    @contextmanager
    def transacao(self):
        c = self._c()
        try:
            c.execute("BEGIN IMMEDIATE")
            yield c
            c.execute("COMMIT")
        except BaseException:
            c.execute("ROLLBACK")
            raise
        finally:
            c.close()
