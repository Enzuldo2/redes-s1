#!/usr/bin/env python3
import asyncio

from camadafisica import ZyboSerialDriver
from ip import IP
from servidor_irc import conexao_aceita
from slip import CamadaEnlace
from tcp import Servidor


def main():
    nossa_ponta = "192.168.200.4"
    outra_ponta = "192.168.200.3"
    porta_tcp = 6667

    driver = ZyboSerialDriver()
    linha_serial = driver.obter_porta(0)

    enlace = CamadaEnlace({outra_ponta: linha_serial})
    rede = IP(enlace)
    rede.definir_endereco_host(nossa_ponta)
    rede.definir_tabela_encaminhamento([
        ("0.0.0.0/0", outra_ponta),
    ])

    servidor = Servidor(rede, porta_tcp)
    servidor.registrar_monitor_de_conexoes_aceitas(conexao_aceita)
    asyncio.get_event_loop().run_forever()


if __name__ == "__main__":
    main()
