import asyncio
import random
import time
from tcputils import *


class Servidor:
    def __init__(self, rede, porta):
        self.rede = rede
        self.porta = porta
        self.conexoes = {}
        self.callback = None
        self.rede.registrar_recebedor(self._rdt_rcv)

    def registrar_monitor_de_conexoes_aceitas(self, callback):
        self.callback = callback

    def _rdt_rcv(self, src_addr, dst_addr, segment):
        src_port, dst_port, seq_no, ack_no, \
            flags, window_size, checksum, urg_ptr = read_header(segment)

        if dst_port != self.porta:
            return
        if not self.rede.ignore_checksum and calc_checksum(segment, src_addr, dst_addr) != 0:
            print('descartando segmento com checksum incorreto')
            return

        payload = segment[4*(flags>>12):]
        id_conexao = (src_addr, src_port, dst_addr, dst_port)

        if (flags & FLAGS_SYN) == FLAGS_SYN:
            seq_servidor = random.randint(0, 2**32 - 1)
            ack_cliente = seq_no + 1

            conexao = self.conexoes[id_conexao] = Conexao(
                self, id_conexao,
                seq_no_inicial=seq_servidor,
                ack_no_inicial=ack_cliente
            )

            src_addr, src_port, dst_addr, dst_port = id_conexao

            header = make_header(
                dst_port,
                src_port,
                seq_servidor,
                ack_cliente,
                FLAGS_SYN | FLAGS_ACK
            )

            segmento = fix_checksum(header, dst_addr, src_addr)
            self.rede.enviar(segmento, src_addr)

            if self.callback:
                self.callback(conexao)

        elif id_conexao in self.conexoes:
            self.conexoes[id_conexao]._rdt_rcv(seq_no, ack_no, flags, payload)
        else:
            print('%s:%d -> %s:%d (pacote associado a conexão desconhecida)' %
                  (src_addr, src_port, dst_addr, dst_port))


class Conexao:
    def __init__(self, servidor, id_conexao, seq_no_inicial, ack_no_inicial):
        self.servidor = servidor
        self.id_conexao = id_conexao
        self.callback = None
        self.seq_no = seq_no_inicial + 1  
        self.ack_no = ack_no_inicial
        self.fechada = False
        
        self.base = self.seq_no
        self.nextseqnum = self.seq_no
        self.timer = None
        self.buffer = {}  
        self.expected_seqno = self.ack_no

        # RTT Dinâmico e Timeout 
        self.estimated_rtt = None
        self.dev_rtt = None
        self.timeout_interval = 1.0  
        self.tempo_envio = {}  
        
        # Pipelining e Congestion Control
        self.cwnd = 1 * MSS  
        self.bytes_in_flight = 0
        self.pending_data = b''
        self.dup_ack_count = 0  
        self.bytes_ack_para_aumento = 0 # Contador para o aumento da janela

    def _iniciar_timer(self):
        if self.timer is None and self.base < self.nextseqnum:
            self.timer = asyncio.get_event_loop().call_later(
                self.timeout_interval, self._timeout_handler
            )

    def _parar_timer(self):
        if self.timer is not None:
            self.timer.cancel()
            self.timer = None

    def _timeout_handler(self):
        self.timer = None
        self._retransmitir()
        
        # AIMD - Multiplicative Decrease: Ocorre apenas no Timeout
        self.cwnd = max(MSS, self.cwnd // 2)
        self.bytes_ack_para_aumento = 0 
        
        self._iniciar_timer()

    def _retransmitir(self):
        src_addr, src_port, dst_addr, dst_port = self.id_conexao
        payload = self.buffer.get(self.base, b'')

        # Algoritmo de Karn
        if self.base in self.tempo_envio:
            del self.tempo_envio[self.base]

        flags = FLAGS_FIN | FLAGS_ACK if payload == b'' else FLAGS_ACK
        header = make_header(dst_port, src_port, self.base, self.ack_no, flags)
        segmento = fix_checksum(header + payload, dst_addr, src_addr)
        self.servidor.rede.enviar(segmento, src_addr)

    def _rdt_rcv(self, seq_no, ack_no, flags, payload):
        src_addr, src_port, dst_addr, dst_port = self.id_conexao

        if self.fechada:
            return

        # 1. Trata FIN
        if (flags & FLAGS_FIN) == FLAGS_FIN:
            self.expected_seqno += 1
            self.ack_no = self.expected_seqno
            if self.callback:
                self.callback(self, b'')
            
            header = make_header(dst_port, src_port, self.nextseqnum, self.ack_no, FLAGS_ACK)
            segmento = fix_checksum(header, dst_addr, src_addr)
            self.servidor.rede.enviar(segmento, src_addr)
            return

        # 2. Processa ACKs
        if (flags & FLAGS_ACK) == FLAGS_ACK:
            # Novo ACK cumulativo
            if ack_no > self.base and ack_no <= self.nextseqnum:
                self.dup_ack_count = 0  
                
                # Cálculos de RTT Dinâmico
                if self.base in self.tempo_envio:
                    sample_rtt = time.time() - self.tempo_envio[self.base]
                    
                    if self.estimated_rtt is None:
                        self.estimated_rtt = sample_rtt
                        self.dev_rtt = sample_rtt / 2
                    else:
                        # ORDEM CORRETA: O DevRTT DEVE usar o NOVO EstimatedRTT
                        self.estimated_rtt = 0.875 * self.estimated_rtt + 0.125 * sample_rtt
                        self.dev_rtt = 0.75 * self.dev_rtt + 0.25 * abs(sample_rtt - self.estimated_rtt)
                    
                    self.timeout_interval = self.estimated_rtt + 4 * self.dev_rtt

                seq = self.base
                while seq < ack_no:
                    payload_buf = self.buffer.get(seq, b'')
                    
                    if seq in self.buffer:
                        del self.buffer[seq]
                    
                    if seq in self.tempo_envio:
                        del self.tempo_envio[seq]
                    
                    if payload_buf != b'':
                        self.bytes_in_flight -= len(payload_buf)
                        
                        # AIMD - Additive Increase: Preservando os "restos"
                        self.bytes_ack_para_aumento += len(payload_buf)
                        if self.bytes_ack_para_aumento >= self.cwnd:
                            self.bytes_ack_para_aumento -= self.cwnd # Em vez de = 0, subtrai a janela
                            self.cwnd += MSS
                    
                    seq += 1 if payload_buf == b'' else len(payload_buf)

                self.base = ack_no
                self._parar_timer()
                
                if self.base < self.nextseqnum:
                    self._iniciar_timer()

                if self.pending_data:
                    self.enviar(b'')

            # Fast Retransmit (3 ACKs duplicados)
            elif ack_no == self.base and self.base < self.nextseqnum:
                self.dup_ack_count += 1
                if self.dup_ack_count == 3:
                    self._retransmitir()
                    self.dup_ack_count = 0
                    self._parar_timer()
                    self._iniciar_timer()

        # 3. Processa Dados
        if len(payload) > 0:
            if seq_no == self.expected_seqno:
                self.expected_seqno += len(payload)
                self.ack_no = self.expected_seqno
                
                if self.callback:
                    self.callback(self, payload)
            
            header = make_header(dst_port, src_port, self.nextseqnum, self.ack_no, FLAGS_ACK)
            segmento = fix_checksum(header, dst_addr, src_addr)
            self.servidor.rede.enviar(segmento, src_addr)

    def registrar_recebedor(self, callback):
        self.callback = callback

    def enviar(self, dados):
        if self.fechada:
            return

        src_addr, src_port, dst_addr, dst_port = self.id_conexao

        if dados:
            self.pending_data += dados

        while self.pending_data:
            payload = self.pending_data[:MSS]

            if self.bytes_in_flight + len(payload) > self.cwnd:
                break

            self.pending_data = self.pending_data[MSS:]
            self.buffer[self.nextseqnum] = payload
            self.tempo_envio[self.nextseqnum] = time.time()  

            header = make_header(dst_port, src_port, self.nextseqnum, self.ack_no, FLAGS_ACK)
            segmento = fix_checksum(header + payload, dst_addr, src_addr)
            self.servidor.rede.enviar(segmento, src_addr)

            self.bytes_in_flight += len(payload)
            self.nextseqnum += len(payload)

            self._iniciar_timer()

    def fechar(self):
        if self.fechada:
            return
        
        src_addr, src_port, dst_addr, dst_port = self.id_conexao
        header = make_header(dst_port, src_port, self.nextseqnum, self.ack_no, FLAGS_FIN | FLAGS_ACK)
        segmento = fix_checksum(header, dst_addr, src_addr)
        self.servidor.rede.enviar(segmento, src_addr)
        
        self.buffer[self.nextseqnum] = b'' 
        self.nextseqnum += 1
        self.fechada = True
        self._iniciar_timer()