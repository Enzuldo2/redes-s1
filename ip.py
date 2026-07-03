from iputils import *


class IP:
    def __init__(self, enlace):
        """
        Inicia a camada de rede. Recebe como argumento uma implementação
        de camada de enlace capaz de localizar os next_hop (por exemplo,
        Ethernet com ARP).
        """
        self.callback = None
        self.enlace = enlace
        self.enlace.registrar_recebedor(self.__raw_recv)
        self.ignore_checksum = self.enlace.ignore_checksum
        self.meu_endereco = None
        self.identification = 0

    def __raw_recv(self, datagrama):
        dscp, ecn, identification, flags, frag_offset, ttl, proto, \
           src_addr, dst_addr, payload = read_ipv4_header(datagrama)
        if dst_addr == self.meu_endereco:
            # atua como host
            if proto == IPPROTO_TCP and self.callback:
                self.callback(src_addr, dst_addr, payload)
        else:
            # atua como roteador
            next_hop = self._next_hop(dst_addr)
            
            # Verificando se sou o último hop do pacote
            if ttl <= 1:
                # Descartamos a mensagem e enviamos de volta um aviso de que o TTL expirou
                self.send_icmp_ttl_expired(datagrama, src_addr)
                return
            
            ttl_novo = ttl - 1
            version_ihl = 0x45
            dscp_ecn = (dscp << 2) | ecn
            total_length = 20 + len(payload)
            flags_frag = (flags << 13) | frag_offset
            checksum = 0
            src_bytes = str2addr(src_addr)
            dst_bytes = str2addr(dst_addr)

            header = struct.pack('!BBHHHBBH4s4s',
                version_ihl, dscp_ecn, total_length, identification,
                flags_frag, ttl_novo, proto, checksum, src_bytes, dst_bytes
            )

            checksum_calculado = calc_checksum(header)

            header = struct.pack('!BBHHHBBH4s4s',
                version_ihl, dscp_ecn, total_length, identification,
                flags_frag, ttl_novo, proto, checksum_calculado, src_bytes, dst_bytes
            )

            datagrama = header + payload

            self.enlace.enviar(datagrama, next_hop)
            
    def send_icmp_ttl_expired(self, datagrama_original, endereco_origem):
        tipo_icmp = 11
        codigo_icmp = 0
        checksum_icmp = 0
        campo_unused = 0

        icmp_payload = datagrama_original[:28]

        header_icmp = struct.pack('!BBHI', tipo_icmp, codigo_icmp, checksum_icmp, campo_unused)
        pacote_icmp = header_icmp + icmp_payload

        checksum_calculado = calc_checksum(pacote_icmp)

        header_icmp = struct.pack('!BBHI', tipo_icmp, codigo_icmp, checksum_calculado, campo_unused)
        pacote_icmp = header_icmp + icmp_payload

        cabecalho_ip_icmp = self.ip_header(
            src=self.meu_endereco,
            dst=endereco_origem,
            proto=IPPROTO_ICMP,
            tam_payload=len(pacote_icmp)
        )

        datagrama_icmp = cabecalho_ip_icmp + pacote_icmp

        next_hop = self._next_hop(endereco_origem)
        if next_hop:
            self.enlace.enviar(datagrama_icmp, next_hop)
            
    def ip_header(self, src, dst, proto, tam_payload, ttl=64):
        version_ihl = 0x45
        dscp_ecn = 0
        total_length = 20 + tam_payload
        identification = self.identification
        flags_frag_offset = 0
        checksum = 0
        src_bytes = str2addr(src)
        dst_bytes = str2addr(dst)

        # Monta o cabeçalho
        header = struct.pack('!BBHHHBBH4s4s', version_ihl, dscp_ecn, total_length, identification, 
                            flags_frag_offset, ttl, proto, checksum, src_bytes, dst_bytes)

        # Calcula o checksum
        checksum = calc_checksum(header)
        
        # Monta o cabeçalho novamente 
        header = struct.pack('!BBHHHBBH4s4s', version_ihl, dscp_ecn, total_length, identification,
                            flags_frag_offset, ttl, proto, checksum, src_bytes, dst_bytes)

        return header

    def _next_hop(self, dest_addr):
        dest_int = self.ip_to_int(dest_addr)
        best_prefix = -1
        best_next_hop = None

        for rede_int, mascara, prefix, next_hop in self.tabela:
            if (dest_int & mascara) == (rede_int & mascara):
                if prefix > best_prefix:    # Prefixo mais longo é o melhor hop
                    best_prefix = prefix
                    best_next_hop = next_hop

        return best_next_hop

    def definir_endereco_host(self, meu_endereco):
        """
        Define qual o endereço IPv4 (string no formato x.y.z.w) deste host.
        Se recebermos datagramas destinados a outros endereços em vez desse,
        atuaremos como roteador em vez de atuar como host.
        """
        self.meu_endereco = meu_endereco

    def definir_tabela_encaminhamento(self, tabela):
        """
        Define a tabela de encaminhamento no formato
        [(cidr0, next_hop0), (cidr1, next_hop1), ...]

        Onde os CIDR são fornecidos no formato 'x.y.z.w/n', e os
        next_hop são fornecidos no formato 'x.y.z.w'.
        """
        self.tabela = []
        for cidr, next_hop in tabela:
            rede_str, prefix_str = cidr.split('/')
            rede_int = self.ip_to_int(rede_str)
            prefix = int(prefix_str)
            mascara = (0xFFFFFFFF << (32 - prefix)) & 0xFFFFFFFF
            self.tabela.append((rede_int, mascara, prefix, next_hop))
            
    def ip_to_int(self, ip_str):
        """
        Transforma o endereço IP em um endereço binário para facilitar comparações
        """
        partes = list(map(int, ip_str.split('.')))
        return (partes[0] << 24) | (partes[1] << 16) | (partes[2] << 8) | partes[3]

    def registrar_recebedor(self, callback):
        """
        Registra uma função para ser chamada quando dados vierem da camada de rede
        """
        self.callback = callback

    def enviar(self, segmento, dest_addr):
        """
        Envia segmento para dest_addr, onde dest_addr é um endereço IPv4
        (string no formato x.y.z.w).
        """
        next_hop = self._next_hop(dest_addr)
        proto = IPPROTO_TCP

        header = self.ip_header(src=self.meu_endereco, dst=dest_addr, proto=proto, tam_payload=len(segmento))
        datagrama = header + segmento
        
        self.enlace.enviar(datagrama, next_hop)
