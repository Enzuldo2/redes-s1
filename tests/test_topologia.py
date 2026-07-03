import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def fonte(nome):
    conteudo = (ROOT / nome).read_text(encoding="utf-8")
    ast.parse(conteudo, filename=nome)
    return conteudo


def normalizar(codigo):
    return codigo.replace('"', "'")


class TestTopologia(unittest.TestCase):
    def test_placa1_liga_pty_a_placa2_pela_p0(self):
        codigo = normalizar(fonte("placa1.py"))
        self.assertIn("driver.obter_porta(0)", codigo)
        self.assertIn("outra_ponta = '192.168.200.1'", codigo)
        self.assertIn("nossa_ponta = '192.168.200.2'", codigo)
        self.assertIn("'192.168.200.3': serial1", codigo)
        self.assertIn(
            "('192.168.200.0/24', '192.168.200.3')",
            codigo,
        )

    def test_placa2_liga_p4_a_placa1_e_p0_a_placa3(self):
        codigo = normalizar(fonte("placa2.py"))
        self.assertIn("serial1 = driver.obter_porta(0)", codigo)
        self.assertIn("serial2 = driver.obter_porta(4)", codigo)
        self.assertIn("'192.168.200.4': serial1", codigo)
        self.assertIn("'192.168.200.2': serial2", codigo)
        self.assertIn(
            "('192.168.200.4/32', '192.168.200.4')",
            codigo,
        )

    def test_placa3_oferece_eco_e_irc_separadamente(self):
        eco = normalizar(fonte("placa3_eco.py"))
        irc = normalizar(fonte("placa3.py"))
        self.assertIn("porta_tcp = 7000", eco)
        self.assertIn("porta_tcp = 6667", irc)
        self.assertIn(
            "from servidor_irc import conexao_aceita",
            irc,
        )
        self.assertIn("driver.obter_porta(0)", irc)
        self.assertIn("('0.0.0.0/0', outra_ponta)", irc)


if __name__ == "__main__":
    unittest.main()
