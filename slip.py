import dataclasses
import traceback

SLIP_END = b'\xC0'  # Delimitador
SLIP_ESC = b'\xDB'  # Escape
SLIP_ESC_END = b'\xDB\xDC'      # Escape de SLIP_END
SLIP_ESC_ESC = b'\xDB\xDD'      # Escape de SLIP_ESC

class CamadaEnlace:
    ignore_checksum = False

    def __init__(self, linhas_seriais):
        """
        Inicia uma camada de enlace com um ou mais enlaces, cada um conectado
        a uma linha serial distinta. O argumento linhas_seriais é um dicionário
        no formato {ip_outra_ponta: linha_serial}. O ip_outra_ponta é o IP do
        host ou roteador que se encontra na outra ponta do enlace, escrito como
        uma string no formato 'x.y.z.w'. A linha_serial é um objeto da classe
        PTY (vide camadafisica.py) ou de outra classe que implemente os métodos
        registrar_recebedor e enviar.
        """
        self.enlaces = {}
        self.callback = None
        # Constrói um Enlace para cada linha serial
        for ip_outra_ponta, linha_serial in linhas_seriais.items():
            enlace = Enlace(linha_serial)
            self.enlaces[ip_outra_ponta] = enlace
            enlace.registrar_recebedor(self._callback)

    def registrar_recebedor(self, callback):
        """
        Registra uma função para ser chamada quando dados vierem da camada de enlace
        """
        self.callback = callback

    def enviar(self, datagrama, next_hop):
        """
        Envia datagrama para next_hop, onde next_hop é um endereço IPv4
        fornecido como string (no formato x.y.z.w). A camada de enlace se
        responsabilizará por encontrar em qual enlace se encontra o next_hop.
        """
        # Encontra o Enlace capaz de alcançar next_hop e envia por ele
        self.enlaces[next_hop].enviar(datagrama)

    def _callback(self, datagrama):
        if self.callback:
            self.callback(datagrama)


class Enlace:
    def __init__(self, linha_serial):
        self.data = bytearray()
        self.linha_serial = linha_serial
        self.linha_serial.registrar_recebedor(self.__raw_recv)
        self.callback = None

    def registrar_recebedor(self, callback):
        self.callback = callback

    def enviar(self, datagrama):
        data = datagrama.replace(SLIP_ESC, SLIP_ESC_ESC).replace(SLIP_END, SLIP_ESC_END)
        frame = SLIP_END + data + SLIP_END
        self.linha_serial.enviar(frame)

    def __raw_recv(self, dados):
        # Colocar dados recebidos no final do array
        self.data.extend(dados) 
        
        while SLIP_END in self.data:
            end = self.data.index(SLIP_END)    # Encontra o delimitador
            frame = self.data[:end]          # Obtém os dados do quadro
            self.data = self.data[end + 1:]       # Remove o quadro processado do buffer
            
            # Descarta se o quadro for vazio
            if len(frame) == 0:
                continue
            
            try:
                # Decodificação
                datagram = frame.replace(SLIP_ESC_END, SLIP_END).replace(SLIP_ESC_ESC, SLIP_ESC)
                if self.callback:
                    self.callback(datagram)  # Passa o datagrama processado para a camada superior
            except:
                traceback.print_exc()
                self.data.clear()      # Limpa buffer após erro no callback

