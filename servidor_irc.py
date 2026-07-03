#!/usr/bin/env python3
# Servidor IRC adaptado para funcionar sobre a stack TCP custom (P2).
# Lógica de aplicação extraída de 1-irc-redes-1/servidor.
# NÃO instancia Servidor nem event loop — isso é feito por placa3.py.

import re

# Mapas globais para gerenciar o estado do servidor
# Nickname em minúsculas -> objeto Conexao
conexoes_por_nick = {}
# Nome do canal em minúsculas -> conjunto de objetos Conexao
membros_por_canal = {}


def validar_nome(nome):
    return re.match(br'^[a-zA-Z][a-zA-Z0-9_-]*$', nome) is not None


def sair(conexao):
    print(conexao, 'conexão fechada')
    
    # Notificar outros usuários nos canais
    if hasattr(conexao, 'nick') and conexao.nick != b'*':
        nick_atual = conexao.nick
        quit_msg = b':' + nick_atual + b' QUIT :Connection closed\r\n'
        
        canais_para_notificar = set()
        for canal_nome, membros in membros_por_canal.items():
            if conexao in membros:
                for membro in membros:
                    if membro != conexao:
                        canais_para_notificar.add(membro)
                # removeremos depois para evitar RuntimeError se chamarmos em loop, 
                # mas aqui estamos iterando sobre itens do dicionário. 
                # Na verdade, precisamos remover o usuário do canal.
        
        for canal_nome in list(membros_por_canal.keys()):
            if conexao in membros_por_canal[canal_nome]:
                membros_por_canal[canal_nome].remove(conexao)
                if not membros_por_canal[canal_nome]:
                    del membros_por_canal[canal_nome]

        for membro in canais_para_notificar:
            membro.enviar(quit_msg)
            
        # Remover do mapa de nicks
        nick_key = nick_atual.lower()
        if conexoes_por_nick.get(nick_key) == conexao:
            del conexoes_por_nick[nick_key]

    conexao.fechar()


def processar_mensagem(conexao, mensagem):
    if not mensagem:
        return

    partes = mensagem.split(b' ', 1)
    comando = partes[0].upper()
    args = partes[1] if len(partes) > 1 else b''

    if comando == b'PING':
        conexao.enviar(b':server PONG server :' + args + b'\r\n')

    elif comando == b'NICK':
        novo_nick = args.strip()
        if not validar_nome(novo_nick):
            apelido_atual = conexao.nick if conexao.nick != b'*' else b'*'
            conexao.enviar(b':server 432 ' + apelido_atual + b' ' + novo_nick + b' :Erroneous nickname\r\n')
            return

        nick_key = novo_nick.lower()
        if nick_key in conexoes_por_nick and conexoes_por_nick[nick_key] != conexao:
            apelido_atual = conexao.nick if conexao.nick != b'*' else b'*'
            conexao.enviar(b':server 433 ' + apelido_atual + b' ' + novo_nick + b' :Nickname is already in use\r\n')
            return

        apelido_antigo = conexao.nick
        conexao.nick = novo_nick
        
        if apelido_antigo == b'*':
            # Registro inicial
            conexoes_por_nick[nick_key] = conexao
            conexao.enviar(b':server 001 ' + novo_nick + b' :Welcome\r\n')
            conexao.enviar(b':server 422 ' + novo_nick + b' :MOTD File is missing\r\n')
        else:
            # Troca de nick
            # Notificar o próprio usuário
            msg_nick = b':' + apelido_antigo + b' NICK ' + novo_nick + b'\r\n'
            conexao.enviar(msg_nick)
            
            # Notificar membros de canais em comum
            antigo_key = apelido_antigo.lower()
            if conexoes_por_nick.get(antigo_key) == conexao:
                del conexoes_por_nick[antigo_key]
            conexoes_por_nick[nick_key] = conexao
            
            outros_para_notificar = set()
            for membros in membros_por_canal.values():
                if conexao in membros:
                    for membro in membros:
                        if membro != conexao:
                            outros_para_notificar.add(membro)
            
            for membro in outros_para_notificar:
                membro.enviar(msg_nick)

    elif comando == b'JOIN':
        canal_nome = args.strip()
        # Canal começa com # e o resto segue validar_nome
        if not canal_nome.startswith(b'#') or not validar_nome(canal_nome[1:]):
            conexao.enviar(b':server 403 ' + canal_nome + b' :No such channel\r\n')
            return
        
        canal_key = canal_nome.lower()
        if canal_key not in membros_por_canal:
            membros_por_canal[canal_key] = set()
        
        membros_por_canal[canal_key].add(conexao)
        
        # Enviar JOIN para todos no canal
        msg_join = b':' + conexao.nick + b' JOIN :' + canal_nome + b'\r\n'
        for membro in membros_por_canal[canal_key]:
            membro.enviar(msg_join)
        
        # Listagem de membros (353)
        lista_membros = sorted([m.nick for m in membros_por_canal[canal_key]])
        
        # Montar mensagens de até 512 bytes
        prefixo = b':server 353 ' + conexao.nick + b' = ' + canal_nome + b' :'
        msg_atual = prefixo
        for i, m_nick in enumerate(lista_membros):
            espaco = b' ' if i > 0 else b''
            if len(msg_atual) + len(espaco) + len(m_nick) + 2 > 512:
                conexao.enviar(msg_atual + b'\r\n')
                msg_atual = prefixo + m_nick
            else:
                msg_atual += espaco + m_nick
        conexao.enviar(msg_atual + b'\r\n')
        
        # Fim da lista (366)
        conexao.enviar(b':server 366 ' + conexao.nick + b' ' + canal_nome + b' :End of /NAMES list.\r\n')

    elif comando == b'PART':
        partes_part = args.strip().split(b' ', 1)
        if not partes_part:
            return
        canal_nome = partes_part[0]
        canal_key = canal_nome.lower()
        
        if canal_key in membros_por_canal and conexao in membros_por_canal[canal_key]:
            msg_part = b':' + conexao.nick + b' PART ' + canal_nome + b'\r\n'
            for membro in membros_por_canal[canal_key]:
                membro.enviar(msg_part)
            
            membros_por_canal[canal_key].remove(conexao)
            if not membros_por_canal[canal_key]:
                del membros_por_canal[canal_key]

    elif comando == b'PRIVMSG':
        partes_msg = args.split(b' ', 1)
        if len(partes_msg) < 2:
            return
        destinatario = partes_msg[0]
        conteudo = partes_msg[1]
        if conteudo.startswith(b':'):
            conteudo = conteudo[1:]
        
        msg_full = b':' + conexao.nick + b' PRIVMSG ' + destinatario + b' :' + conteudo + b'\r\n'
        
        if destinatario.startswith(b'#'):
            dest_key = destinatario.lower()
            if dest_key in membros_por_canal:
                for membro in membros_por_canal[dest_key]:
                    if membro != conexao:
                        membro.enviar(msg_full)
        else:
            dest_key = destinatario.lower()
            if dest_key in conexoes_por_nick:
                conexoes_por_nick[dest_key].enviar(msg_full)


def dados_recebidos(conexao, dados):
    if dados == b'':
        return sair(conexao)
    
    conexao.residual += dados
    while b'\r\n' in conexao.residual:
        mensagem, conexao.residual = conexao.residual.split(b'\r\n', 1)
        processar_mensagem(conexao, mensagem)


def conexao_aceita(conexao):
    print(conexao, 'nova conexão')

    conexao.nick = b'*'
    conexao.residual = b''

    conexao.registrar_recebedor(dados_recebidos)
