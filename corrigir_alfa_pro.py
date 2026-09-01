from pathlib import Path

p = Path("core/alfa_pro.py")
s = p.read_text(encoding="utf-8")

a = s.index("    def direction(self, text):")
b = s.index("    def program(self, text):", a)
s = s[:a] + '    def direction(self, text):\n        c = self.normalize(text)\n\n        if any(x in c for x in ["esquerda", "esquerdo", "esquer"]):\n            return "esquerda"\n\n        if any(x in c for x in ["direita", "direito", "direit", "direto"]):\n            return "direita"\n\n        if any(x in c for x in ["cima", "acima", "topo", "suba", "sobe", "eleva"]):\n            return "cima"\n\n        if any(x in c for x in ["baixo", "abaixo", "fundo", "desca", "desça", "baixe"]):\n            return "baixo"\n\n        if any(x in c for x in ["centro", "meio"]):\n            return "centro"\n\n        return None\n\n\n' + s[b:]

a = s.index("        # Comando de mouse inequívoco")
b = s.index("        # Embedding semântico.", a)
s = s[:a] + '        # MOUSE: prioridade máxima. Não consultar o cérebro.\n        mouse_words = [\n            "mouse", "mause", "maus", "mou",\n            "malwe", "malve", "cursor"\n        ]\n\n        direction_words = [\n            "esquerda", "esquerdo", "esquer",\n            "direita", "direito", "direit", "direto",\n            "cima", "acima", "topo", "suba", "sobe",\n            "baixo", "abaixo", "fundo", "desca", "desça", "baixe",\n            "centro", "meio"\n        ]\n\n        tem_mouse = any(x in c for x in mouse_words)\n        tem_direcao = any(x in c for x in direction_words)\n\n        if tem_mouse and tem_direcao:\n            direction = self.direction(c)\n            if direction:\n                self.last_target = "MOUSE"\n                return {\n                    "intent": "MOVER_MOUSE",\n                    "confidence": 1.0,\n                    "direction": direction,\n                }\n\n        move_words = [\n            "mover", "mova", "move", "movam",\n            "mexer", "mexa", "mexe", "mecho", "mexo",\n            "levar", "leve", "leva",\n            "deslocar", "desloque",\n            "arrastar", "arraste",\n            "subir", "suba", "sobe",\n            "descer", "desca", "desça",\n            "baixar", "baixe",\n            "elevar", "eleve",\n            "jogar", "jogue", "joga"\n        ]\n\n        if tem_mouse and any(x in c for x in move_words):\n            direction = self.direction(c)\n            if direction:\n                self.last_target = "MOUSE"\n                return {\n                    "intent": "MOVER_MOUSE",\n                    "confidence": 1.0,\n                    "direction": direction,\n                }\n\n' + s[b:]

needle = "        # Embedding semântico.\n"
block = '''        # Evita que uma frase curta e ambígua vire uma ação aleatória.
        if len(c.split()) <= 4 and not any(x in c for x in [
            "clique", "copiar", "copie", "colar", "cole",
            "desfazer", "enter", "escape", "esc",
            "abrir", "abra", "fechar", "feche",
            "sair", "saia"
        ]):
            return {"intent": "DESCONHECIDO", "confidence": 0.0}

        # Embedding semântico.
'''
if needle in s:
    s = s.replace(needle, block, 1)

p.write_text(s, encoding="utf-8")
print("CORRIGIDO:", p.resolve())
