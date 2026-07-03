# Integração do Seminário de Redes — Design

## Objetivo

Reunir em `redes-s1` as implementações das quatro práticas e os programas das
três placas, seguindo o roteiro do seminário. A validação começa com um servidor
de eco TCP e termina com o servidor IRC sobre a pilha completa em Python.

## Escopo

- Usar `tcp.py` e `tcputils.py` da prática 2.
- Usar `ip.py` e `iputils.py` da prática 3.
- Usar `slip.py` da prática 4.
- Usar o `camadafisica.py` fornecido pelo seminário para a Zybo Z7-20.
- Manter a topologia, os endereços e as portas seriais definidos no README do
  seminário.
- Adaptar a aplicação IRC da prática 1 à interface de conexão da implementação
  TCP da prática 2.
- Documentar preparação, cabeamento, execução e testes no Linux.

Não serão alterados os protocolos ou acrescentadas dependências externas.

## Arquitetura e responsabilidades

Os módulos formam a pilha `aplicação → TCP → IP → SLIP → porta serial`.

- `tcputils.py`: codificação, leitura e checksum de segmentos TCP.
- `tcp.py`: servidor TCP, conexões, confirmação, retransmissão e fechamento.
- `iputils.py`: leitura e validação de cabeçalhos IPv4.
- `ip.py`: entrega local, encaminhamento, tabela de rotas e ICMP Time Exceeded.
- `slip.py`: enquadramento de datagramas IP sobre linhas seriais.
- `camadafisica.py`: acesso às UARTs da Zybo e criação da PTY usada pelo Linux.
- `servidor_irc.py`: estado e comandos da aplicação IRC, sem criar TCP ou loop.
- `placa1.py`: conecta a rede nativa do Linux à pilha Python por uma PTY e à
  placa 2 pela porta física P0.
- `placa2.py`: roteia entre a placa 1 pela P4 e a placa 3 pela P0.
- `placa3_eco.py`: valida a pilha completa com eco TCP na porta 7000.
- `placa3.py`: executa o serviço final IRC na porta 6667.

Na placa 3, `placa3_eco.py` e `placa3.py` são alternativas executadas em
momentos diferentes. Eles não devem ser iniciados simultaneamente.

## Topologia e fluxo

O cabeamento será:

```text
Linux 192.168.200.1
        ↕ PTY
placa 1 / Python 192.168.200.2 / P0
        ↕
P4 / placa 2 192.168.200.3 / P0
        ↕
P0 / placa 3 192.168.200.4
```

Cada ligação física usa RX cruzado com TX e terra comum entre as placas. A
placa 1 encaminha a rede `192.168.200.0/24` para a placa 2. A placa 2 encaminha
o host `192.168.200.4` para a placa 3, que usa a placa 2 como rota padrão.

## Execução

Todos os arquivos de execução e da pilha serão copiados para o diretório do
grupo em cada placa. Os três programas principais serão iniciados com Python 3.
Na placa 1, os comandos `slattach`, `ifconfig` e `ip route` impressos por
`placa1.py` ligarão a rede nativa do Linux à PTY.

Primeiro, a placa 3 executará `placa3_eco.py`; a placa 1 validará o caminho com
`nc 192.168.200.4 7000`. Depois do teste, o eco será encerrado e `placa3.py`
iniciará o IRC; a validação será feita em `192.168.200.4:6667`.

## Tratamento de falhas

As implementações das práticas permanecem responsáveis por descartar quadros,
datagramas ou segmentos inválidos e por isolar exceções dos recebedores. O
roteamento mantém o tratamento de TTL e ICMP implementado na prática de IP. A
aplicação IRC acumula dados fragmentados até `\r\n`, remove conexões encerradas
dos mapas de usuários e canais e notifica os demais membros quando necessário.

Erros operacionais de cabeamento, dispositivo ou configuração serão
diagnosticados pela sequência de testes: práticas isoladas, eco ponta a ponta e
IRC ponta a ponta.

## Validação

Antes das placas:

1. Executar as suítes originais de TCP, IP, SLIP e IRC.
2. Verificar sintaxe e imports dos arquivos consolidados no Linux.
3. Confirmar que os módulos consolidados correspondem às implementações
   aprovadas nas práticas.

Nas placas:

1. Confirmar a criação de `sl0` e as rotas na placa 1.
2. Testar o servidor de eco da placa 3 a partir da placa 1.
3. Se disponível, executar `mtr 192.168.200.4`.
4. Substituir o eco pelo IRC e testar `PING`, `NICK`, `JOIN` e `PRIVMSG`.

O trabalho estará concluído quando o eco e o IRC forem acessíveis a partir da
placa 1 através da placa 2, sem executar os dois serviços simultaneamente.
