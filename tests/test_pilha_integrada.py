import unittest

from ip import IP
from iputils import IPPROTO_TCP, read_ipv4_header
from slip import CamadaEnlace, SLIP_END, SLIP_ESC, SLIP_ESC_END, SLIP_ESC_ESC
from tcp import Servidor
from tcputils import (
    FLAGS_ACK,
    FLAGS_SYN,
    calc_checksum,
    fix_checksum,
    make_header,
    read_header,
)


class LinhaSerialFalsa:
    def __init__(self):
        self.recebedor = None
        self.enviados = []

    def registrar_recebedor(self, callback):
        self.recebedor = callback

    def enviar(self, dados):
        self.enviados.append(dados)

    def receber(self, dados):
        self.recebedor(dados)


def codificar_slip(datagrama):
    dados = datagrama.replace(SLIP_ESC, SLIP_ESC_ESC)
    dados = dados.replace(SLIP_END, SLIP_ESC_END)
    return SLIP_END + dados + SLIP_END


def decodificar_slip(quadro):
    assert quadro.startswith(SLIP_END)
    assert quadro.endswith(SLIP_END)
    dados = quadro[1:-1].replace(SLIP_ESC_END, SLIP_END)
    return dados.replace(SLIP_ESC_ESC, SLIP_ESC)


class TestPilhaIntegrada(unittest.TestCase):
    def test_handshake_percorre_slip_ip_e_tcp(self):
        linha = LinhaSerialFalsa()
        enlace = CamadaEnlace({"192.168.200.3": linha})
        rede = IP(enlace)
        rede.definir_endereco_host("192.168.200.4")
        rede.definir_tabela_encaminhamento([
            ("0.0.0.0/0", "192.168.200.3"),
        ])

        servidor = Servidor(rede, 7000)
        conexoes_aceitas = []
        servidor.registrar_monitor_de_conexoes_aceitas(
            conexoes_aceitas.append
        )

        origem = "192.168.200.1"
        destino = "192.168.200.4"
        segmento = make_header(50000, 7000, 100, 0, FLAGS_SYN)
        segmento = fix_checksum(segmento, origem, destino)
        datagrama = (
            rede.ip_header(
                src=origem,
                dst=destino,
                proto=IPPROTO_TCP,
                tam_payload=len(segmento),
            )
            + segmento
        )

        linha.receber(codificar_slip(datagrama))

        self.assertEqual(len(conexoes_aceitas), 1)
        self.assertEqual(len(linha.enviados), 1)

        resposta = decodificar_slip(linha.enviados[0])
        (
            _dscp,
            _ecn,
            _identification,
            _ip_flags,
            _frag_offset,
            _ttl,
            proto,
            src_addr,
            dst_addr,
            segmento_resposta,
        ) = read_ipv4_header(resposta, verify_checksum=True)
        (
            src_port,
            dst_port,
            _seq_no,
            ack_no,
            flags,
            _window_size,
            _checksum,
            _urg_ptr,
        ) = read_header(segmento_resposta)

        self.assertEqual(proto, IPPROTO_TCP)
        self.assertEqual((src_addr, dst_addr), (destino, origem))
        self.assertEqual((src_port, dst_port), (7000, 50000))
        self.assertEqual(ack_no, 101)
        self.assertEqual(flags & (FLAGS_SYN | FLAGS_ACK), FLAGS_SYN | FLAGS_ACK)
        self.assertEqual(
            calc_checksum(segmento_resposta, src_addr, dst_addr),
            0,
        )


if __name__ == "__main__":
    unittest.main()
