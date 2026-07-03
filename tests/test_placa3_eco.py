import importlib
import sys
import types
import unittest
from unittest import mock


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


def importar_sem_hardware():
    camadafisica_falsa = types.ModuleType("camadafisica")

    class DriverInesperado:
        def __init__(self):
            raise AssertionError("o hardware foi acessado durante o import")

    camadafisica_falsa.ZyboSerialDriver = DriverInesperado
    sys.modules.pop("placa3_eco", None)
    with mock.patch.dict(
        sys.modules,
        {"camadafisica": camadafisica_falsa},
    ):
        return importlib.import_module("placa3_eco")


class TestPlaca3Eco(unittest.TestCase):
    def test_importar_nao_acessa_hardware(self):
        modulo = importar_sem_hardware()
        self.assertTrue(callable(modulo.main))

    def test_eco_reenvia_dados_e_fecha_conexao(self):
        modulo = importar_sem_hardware()
        conexao = ConexaoFalsa()

        modulo.conexao_aceita(conexao)
        conexao.recebedor(conexao, b"mensagem")
        conexao.recebedor(conexao, b"")

        self.assertEqual(conexao.enviados, [b"mensagem"])
        self.assertTrue(conexao.fechada)


if __name__ == "__main__":
    unittest.main()
