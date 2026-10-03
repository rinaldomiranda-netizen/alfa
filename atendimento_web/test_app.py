"""Testes do servidor web do RMD Atendimento (HTTP de verdade, porta aleatória)."""
import http.client
import json
import shutil
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.parse import urlparse

from atendimento_web import app, recepcao
from modules.atendimento.plataforma import Plataforma, demo, seguranca

_ITERACOES = seguranca.ITERACOES


class Cliente:
    def __init__(self, porta):
        self.porta = porta
        self.cookie = None

    def pedir(self, metodo, caminho, dados=None, cabecalhos=None, csrf=True):
        conexao = http.client.HTTPConnection("127.0.0.1", self.porta, timeout=10)
        h = dict(cabecalhos or {})
        corpo = None
        if dados is not None:
            corpo = json.dumps(dados).encode()
            h["Content-Type"] = "application/json"
        if csrf:
            h["X-RMD"] = "1"
        if self.cookie:
            h["Cookie"] = self.cookie
        conexao.request(metodo, caminho, body=corpo, headers=h)
        resposta = conexao.getresponse()
        bruto = resposta.read()
        novo = resposta.getheader("Set-Cookie")
        if novo:
            self.cookie = novo.split(";", 1)[0]
        conexao.close()
        try:
            conteudo = json.loads(bruto.decode()) if bruto else None
        except ValueError:
            conteudo = bruto.decode(errors="replace")
        return resposta.status, conteudo, resposta


class AtendimentoWebTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        seguranca.ITERACOES = 2_000
        cls.pasta = Path(tempfile.mkdtemp())
        cls.plataforma = Plataforma(cls.pasta / "web.db", pasta_backups=cls.pasta / "bk")
        cls.plataforma.envio_sincrono = True
        app.definir_plataforma(cls.plataforma)
        cls.demo = demo.garantir_demonstracao(cls.plataforma)
        recepcao.definir_store(None)
        recepcao.caminho_store = lambda: cls.pasta / "recepcao.json"
        cls.servidor = app.criar_servidor("127.0.0.1", 0)
        cls.thread = threading.Thread(target=cls.servidor.serve_forever, daemon=True)
        cls.thread.start()
        cls.porta = cls.servidor.server_address[1]

    @classmethod
    def tearDownClass(cls):
        cls.servidor.shutdown()
        cls.servidor.server_close()
        cls.servidor.parar_rotina.set()
        shutil.rmtree(cls.pasta, ignore_errors=True)
        seguranca.ITERACOES = _ITERACOES

    def entrar(self, perfil):
        cliente = Cliente(self.porta)
        token = seguranca.criar_token_unico(self.demo["usuarios"][perfil], self.demo["empresa_id"])
        status, _, resposta = cliente.pedir("GET", "/entrar?token=" + token, csrf=False)
        self.assertEqual(status, 303)
        self.assertIn("HttpOnly", resposta.getheader("Set-Cookie"))
        self.assertIn("SameSite=Strict", resposta.getheader("Set-Cookie"))
        return cliente

    def test_saude_e_cabecalhos_de_seguranca(self):
        status, corpo, resposta = Cliente(self.porta).pedir("GET", "/api/health")
        self.assertEqual(status, 200)
        self.assertTrue(corpo["ok"])
        self.assertIn("default-src 'self'", resposta.getheader("Content-Security-Policy"))
        self.assertEqual(resposta.getheader("X-Frame-Options"), "DENY")
        self.assertIsNone(resposta.getheader("Access-Control-Allow-Origin"))

    def test_sem_login_nao_ve_dados(self):
        status, corpo, _ = Cliente(self.porta).pedir("GET", "/api/contatos")
        self.assertEqual(status, 401)
        status, corpo, _ = Cliente(self.porta).pedir("GET", "/api/recepcao/historico")
        self.assertEqual(status, 401)

    def test_csrf_bloqueia_sem_cabecalho(self):
        cliente = self.entrar("admin")
        status, _, _ = cliente.pedir("POST", "/api/contatos", {"nome": "Sem CSRF"}, csrf=False)
        self.assertEqual(status, 403)
        status, corpo, _ = cliente.pedir("POST", "/api/contatos", {"nome": "Com CSRF", "telefone": "79911223344"})
        self.assertEqual(status, 200, corpo)

    def test_telas_por_perfil(self):
        _, admin, _ = self.entrar("admin").pedir("GET", "/api/sessao")
        _, atendente, _ = self.entrar("atendente").pedir("GET", "/api/sessao")
        _, cliente, _ = self.entrar("cliente").pedir("GET", "/api/sessao")
        _, owner, _ = self.entrar("owner").pedir("GET", "/api/sessao")
        self.assertIn("users", admin["telas"])
        self.assertNotIn("users", atendente["telas"])
        self.assertIn("chat", atendente["telas"])
        self.assertEqual(cliente["telas"], ["portal"])
        self.assertIn("companies", owner["telas"])
        self.assertNotIn("companies", admin["telas"])
        status, _, _ = self.entrar("atendente").pedir("GET", "/api/usuarios")
        self.assertEqual(status, 403)

    def test_arquivos_estaticos_e_protecao_de_caminho(self):
        status, corpo, _ = Cliente(self.porta).pedir("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn("RMD Atendimento", corpo)
        status, _, _ = Cliente(self.porta).pedir("GET", "/static/../app.py")
        self.assertEqual(status, 404)

    def test_chat_publico_do_site(self):
        visitante = Cliente(self.porta)
        status, corpo, _ = visitante.pedir("POST", "/api/publico/demonstracao/conversas", {"nome": "Visitante Web", "texto": "oi"})
        self.assertEqual(status, 200, corpo)
        token = corpo["token"]
        status, corpo, _ = visitante.pedir("POST", f"/api/publico/conversas/{token}/mensagens", {"texto": "Orçamento"})
        self.assertEqual(corpo["status"], "aguardando")
        status, _, _ = visitante.pedir("GET", "/api/publico/conversas/token-que-nao-existe-123456")
        self.assertEqual(status, 404)

    def test_api_publica_com_chave(self):
        admin = self.entrar("admin")
        _, chave, _ = admin.pedir("POST", "/api/integracoes/chaves", {"nome": "Teste", "escopos": ["names:read"]})
        externo = Cliente(self.porta)
        status, corpo, _ = externo.pedir("GET", "/api/v1/nomes", cabecalhos={"Authorization": "Bearer " + chave["chave"]}, csrf=False)
        self.assertEqual(status, 200)
        self.assertTrue(corpo["itens"])
        status, _, _ = externo.pedir("GET", "/api/v1/nomes", cabecalhos={"Authorization": "Bearer rmd_falsa.123"}, csrf=False)
        self.assertEqual(status, 401)

    def test_recepcao_por_roteiro_continua_funcionando(self):
        cliente = self.entrar("atendente")
        status, corpo, _ = cliente.pedir("POST", "/api/recepcao/atendimentos", {})
        if status == 400 and "bibliotecas" in (corpo or {}).get("erro", ""):
            self.skipTest("Bibliotecas de câmera/tela do ALFA não instaladas neste ambiente.")
        self.assertEqual(status, 200, corpo)
        self.assertIn("Com quem estou falando?", corpo["mensagem"])
        sid = corpo["session_id"]
        status, corpo, _ = cliente.pedir("POST", f"/api/recepcao/atendimentos/{sid}/mensagens", {"texto": "Maria"})
        self.assertEqual(corpo["acao"], "confirmar")
        status, corpo, _ = cliente.pedir("POST", f"/api/recepcao/atendimentos/{sid}/mensagens", {"texto": "sim"})
        self.assertTrue(corpo["status"]["ativo"])
        status, corpo, _ = cliente.pedir("GET", "/api/recepcao/historico")
        self.assertGreaterEqual(len(corpo["itens"]), 1)
        outro = self.entrar("admin")
        status, _, _ = outro.pedir("POST", f"/api/recepcao/atendimentos/{sid}/mensagens", {"texto": "x"})
        self.assertEqual(status, 200)  # mesma empresa pode continuar a sessão


class SegurancaExtraTests(unittest.TestCase):
    """HSTS, verificação em duas etapas e cópia fora do servidor (2026-09-28)."""
    setUpClass = classmethod(AtendimentoWebTests.setUpClass.__func__)
    tearDownClass = classmethod(AtendimentoWebTests.tearDownClass.__func__)

    def test_hsts_so_com_https(self):
        _, _, r = Cliente(self.porta).pedir("GET", "/api/health")
        self.assertIsNone(r.getheader("Strict-Transport-Security"))
        _, _, r = Cliente(self.porta).pedir("GET", "/api/health", cabecalhos={"X-Forwarded-Proto": "https"})
        self.assertEqual(r.getheader("Strict-Transport-Security"), "max-age=31536000; includeSubDomains")

    def test_verificacao_em_duas_etapas(self):
        import time
        p = self.plataforma
        email = "dois.fatores@teste.local"
        p.criar_usuario(None, "Dois Fatores", email, "admin", senha="Senha1234x", empresa_id=self.demo["empresa_id"])
        c = Cliente(self.porta)
        st, corpo, _ = c.pedir("POST", "/api/entrar", {"email": email, "senha": "Senha1234x"})
        self.assertEqual(st, 200, corpo)
        st, corpo, _ = c.pedir("GET", "/api/seguranca")
        self.assertFalse(corpo["dois_fatores"])
        st, ini, _ = c.pedir("POST", "/api/seguranca/2fa/iniciar", {})
        self.assertEqual(st, 200, ini)
        self.assertTrue(ini["endereco"].startswith("otpauth://totp/"))
        st, corpo, _ = c.pedir("POST", "/api/seguranca/2fa/ativar", {"codigo": "000000"})
        self.assertEqual(st, 400)
        agora = int(time.time() // 30)
        st, corpo, _ = c.pedir("POST", "/api/seguranca/2fa/ativar", {"codigo": seguranca.codigo_totp(ini["segredo"], agora)})
        self.assertEqual(st, 200, corpo)
        # o segredo nunca vai para o backup
        exportado = p.exportar_dados(self.demo["empresa_id"])
        self.assertTrue(all("totp_segredo" not in u for u in exportado["tabelas"]["usuarios"]))
        # login sem código: pede o código, sem abrir sessão
        c2 = Cliente(self.porta)
        st, corpo, _ = c2.pedir("POST", "/api/entrar", {"email": email, "senha": "Senha1234x"})
        self.assertEqual(st, 401)
        self.assertTrue(corpo["precisa_codigo"])
        self.assertIsNone(c2.cookie)
        # senha errada continua dizendo só "e-mail ou senha" (não revela que há 2 etapas)
        st, corpo, _ = c2.pedir("POST", "/api/entrar", {"email": email, "senha": "errada123x", "codigo": "123456"})
        self.assertEqual(st, 401)
        self.assertNotIn("precisa_codigo", corpo)
        # código errado
        st, corpo, _ = c2.pedir("POST", "/api/entrar", {"email": email, "senha": "Senha1234x", "codigo": "111111"})
        self.assertEqual(st, 401)
        self.assertTrue(corpo["precisa_codigo"])
        # código do próximo intervalo (o do atual já foi usado na ativação e não vale de novo)
        st, corpo, _ = c2.pedir("POST", "/api/entrar", {"email": email, "senha": "Senha1234x", "codigo": seguranca.codigo_totp(ini["segredo"], agora)})
        self.assertEqual(st, 401, "código já usado não pode entrar de novo")
        st, corpo, _ = c2.pedir("POST", "/api/entrar", {"email": email, "senha": "Senha1234x", "codigo": seguranca.codigo_totp(ini["segredo"], agora + 1)})
        self.assertEqual(st, 200, corpo)
        self.assertTrue(corpo["sessao"])
        # desligar exige a senha
        st, _, _ = c2.pedir("POST", "/api/seguranca/2fa/desativar", {"senha": "errada"})
        self.assertEqual(st, 400)
        st, corpo, _ = c2.pedir("POST", "/api/seguranca/2fa/desativar", {"senha": "Senha1234x"})
        self.assertEqual(st, 200, corpo)
        st, corpo, _ = Cliente(self.porta).pedir("POST", "/api/entrar", {"email": email, "senha": "Senha1234x"})
        self.assertEqual(st, 200, corpo)

    def test_copia_fora_do_servidor(self):
        import gzip
        import os
        import sqlite3
        from http.server import BaseHTTPRequestHandler, HTTPServer
        from modules.atendimento.plataforma import backup_externo
        recebido = {}

        class Destino(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_POST(self):
                recebido["chave"] = self.headers.get("x-rmd-chave")
                recebido["caminho"] = self.path
                recebido["corpo"] = self.rfile.read(int(self.headers["Content-Length"]))
                ok = recebido["chave"] == "segredo-teste"
                corpo = json.dumps({"ok": True, "arquivo": "teste/hoje.db.gz"} if ok else {"ok": False, "erro": "chave"}).encode()
                self.send_response(200 if ok else 401)
                self.send_header("Content-Length", str(len(corpo)))
                self.end_headers()
                self.wfile.write(corpo)

        destino = HTTPServer(("127.0.0.1", 0), Destino)
        threading.Thread(target=destino.serve_forever, daemon=True).start()
        antigos = {k: os.environ.get(k) for k in ("RMD_BACKUP_URL", "RMD_BACKUP_CHAVE", "RMD_BACKUP_NOME", "RMD_ATENDIMENTO_DADOS")}
        try:
            os.environ["RMD_ATENDIMENTO_DADOS"] = str(self.pasta)
            os.environ.pop("RMD_BACKUP_URL", None)
            self.assertFalse(backup_externo.configurado())
            backup_externo.talvez_enviar(self.plataforma.banco.caminho)  # sem configuração: não faz nada
            self.assertEqual(recebido, {})
            os.environ.update(RMD_BACKUP_URL=f"http://127.0.0.1:{destino.server_address[1]}/rmd-backup",
                              RMD_BACKUP_CHAVE="errada", RMD_BACKUP_NOME="teste")
            est = backup_externo.enviar_agora(self.plataforma.banco.caminho)
            self.assertEqual(est["ultimo_erro"], "HTTP 401")
            self.assertIsNone(est["ultimo_ok"])
            os.environ["RMD_BACKUP_CHAVE"] = "segredo-teste"
            backup_externo.talvez_enviar(self.plataforma.banco.caminho)  # falhou há menos de 1 h: espera
            self.assertEqual(recebido["chave"], "errada")
            est = backup_externo.enviar_agora(self.plataforma.banco.caminho)
            self.assertTrue(est["ultimo_ok"], est)
            self.assertIsNone(est["ultimo_erro"])
            self.assertIn("servico=teste", recebido["caminho"])
            copia = self.pasta / "restaurado.db"
            copia.write_bytes(gzip.decompress(recebido["corpo"]))
            banco = sqlite3.connect(str(copia))
            self.assertGreater(banco.execute("SELECT COUNT(*) FROM usuarios").fetchone()[0], 0)
            banco.close()
            recebido.clear()
            backup_externo.talvez_enviar(self.plataforma.banco.caminho)  # já enviou hoje
            self.assertEqual(recebido, {})
        finally:
            for k, v in antigos.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v
            destino.shutdown()


class IpAtrasDeProxyTests(unittest.TestCase):
    def _ip(self, atras, cabecalhos):
        falso = type("H", (), {"headers": cabecalhos, "client_address": ("10.0.0.9", 1234)})()
        antigo = app.ATRAS_DE_PROXY
        app.ATRAS_DE_PROXY = atras
        try:
            return app.Handler._ip(falso)
        finally:
            app.ATRAS_DE_PROXY = antigo

    def test_sem_proxy_ignora_cabecalho_inventado(self):
        self.assertEqual(self._ip(False, {"X-Forwarded-For": "1.2.3.4"}), "10.0.0.9")

    def test_atras_de_proxy_usa_ip_do_visitante(self):
        self.assertEqual(self._ip(True, {"X-Forwarded-For": "1.2.3.4, 10.0.0.1"}), "1.2.3.4")
        self.assertEqual(self._ip(True, {"X-Real-IP": "5.6.7.8"}), "5.6.7.8")
        self.assertEqual(self._ip(True, {}), "10.0.0.9")


if __name__ == "__main__":
    unittest.main()
