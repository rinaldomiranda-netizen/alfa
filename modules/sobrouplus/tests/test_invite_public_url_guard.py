import unittest
from web import app

class FakeHandler:
    def __init__(self, base, trusted, https):
        self.base, self.trusted, self.is_https = base, trusted, https
    def _proxy_confiavel(self): return self.trusted
    def https(self): return self.is_https
    def url_acesso(self): return self.base

class PublicInviteUrlGuard(unittest.TestCase):
    def test_blocks_local_http_and_private_addresses(self):
        cases = [
            ("http://192.168.0.3:8096", False, False),
            ("http://127.0.0.1:8096", False, False),
            ("https://192.168.0.3", True, True),
            ("https://localhost", True, True),
        ]
        for base, trusted, https in cases:
            with self.subTest(base=base):
                self.assertEqual(app._base_convites_externos(FakeHandler(base, trusted, https)), "")
    def test_accepts_public_https_from_trusted_proxy(self):
        base = "https://rmd-atendimento-web-production.up.railway.app/sobrou"
        self.assertEqual(app._base_convites_externos(FakeHandler(base, True, True)), base)

if __name__ == "__main__":
    unittest.main()
