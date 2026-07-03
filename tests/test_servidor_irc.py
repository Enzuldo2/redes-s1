import unittest

import servidor_irc


class ConexaoFalsa:
    def __init__(self):
        self.recebedor = None
        self.enviados = []
        self.fechada = False

    def registrar_recebedor(self, callback):
        self.recebedor = callback

    def enviar(self, dados):
        self.enviados.append(dados)

    def fechar(self):
        self.fechada = True

    def receber(self, dados):
        self.recebedor(self, dados)


class TestServidorIRC(unittest.TestCase):
    def setUp(self):
        servidor_irc.conexoes_por_nick.clear()
        servidor_irc.membros_por_canal.clear()

    def conectar(self, nick):
        conexao = ConexaoFalsa()
        servidor_irc.conexao_aceita(conexao)
        conexao.receber(b"NICK " + nick + b"\r\n")
        conexao.enviados.clear()
        return conexao

    def test_ping_fragmentado(self):
        conexao = ConexaoFalsa()
        servidor_irc.conexao_aceita(conexao)

        conexao.receber(b"PI")
        conexao.receber(b"NG teste\r\n")

        self.assertEqual(
            conexao.enviados,
            [b":server PONG server :teste\r\n"],
        )

    def test_privmsg_em_canal_chega_apenas_ao_outro_membro(self):
        alice = self.conectar(b"Alice")
        bob = self.conectar(b"Bob")
        alice.receber(b"JOIN #redes\r\n")
        bob.receber(b"JOIN #redes\r\n")
        alice.enviados.clear()
        bob.enviados.clear()

        alice.receber(b"PRIVMSG #redes :ola\r\n")

        self.assertEqual(alice.enviados, [])
        self.assertEqual(
            bob.enviados,
            [b":Alice PRIVMSG #redes :ola\r\n"],
        )

    def test_desconexao_notifica_canal_e_libera_nick(self):
        alice = self.conectar(b"Alice")
        bob = self.conectar(b"Bob")
        alice.receber(b"JOIN #redes\r\n")
        bob.receber(b"JOIN #redes\r\n")
        alice.enviados.clear()
        bob.enviados.clear()

        alice.receber(b"")

        self.assertTrue(alice.fechada)
        self.assertEqual(
            bob.enviados,
            [b":Alice QUIT :Connection closed\r\n"],
        )
        self.assertNotIn(b"alice", servidor_irc.conexoes_por_nick)
        self.assertNotIn(alice, servidor_irc.membros_por_canal[b"#redes"])


if __name__ == "__main__":
    unittest.main()
