# Integração do Seminário de Redes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Consolidar as quatro práticas em `redes-s1` e entregar a topologia de três placas com teste de eco na porta 7000 e serviço IRC final na porta 6667.

**Architecture:** A aplicação da placa 3 usa a pilha `TCP → IP → SLIP → UART`; a placa 2 encaminha pacotes entre suas portas P4 e P0; a placa 1 liga a pilha Python à rede nativa do Linux por uma PTY. O eco e o IRC são executados separadamente na placa 3, preservando a sequência de validação do README do seminário.

**Tech Stack:** Python 3, `asyncio`, biblioteca padrão, SLIP, IPv4, TCP simplificado, IRC simplificado, Arch Linux ARM, Zybo Z7-20, `unittest`, `slattach`, `ifconfig`, `ip`, `nc` e `mtr`.

---

## Estrutura de arquivos

O plano parte do estado atual: `tcp.py`, `tcputils.py`, `ip.py`, `iputils.py`,
`slip.py`, `placa3_eco.py` e `servidor_irc.py` já existem no working tree, mas
ainda não estão versionados. `placa3.py` já contém uma alteração não commitada.
Esses arquivos devem ser validados e preservados.

- `.gitignore`: ignora caches gerados pelos testes Python.
- `camadafisica.py`: driver oficial da Zybo e implementação da PTY.
- `tcputils.py`: utilitários da prática 2.
- `tcp.py`: implementação TCP da prática 2.
- `iputils.py`: utilitários da prática 3.
- `ip.py`: implementação IP da prática 3.
- `slip.py`: implementação SLIP da prática 4.
- `placa1.py`: PTY `192.168.200.1 ↔ 192.168.200.2` e enlace P0 para a placa 2.
- `placa2.py`: roteador entre P4, voltada à placa 1, e P0, voltada à placa 3.
- `placa3_eco.py`: servidor de eco na porta 7000.
- `servidor_irc.py`: aplicação IRC adaptada à classe `Conexao` da prática 2.
- `placa3.py`: servidor IRC na porta 6667.
- `tests/test_pilha_integrada.py`: handshake passando por SLIP, IP e TCP.
- `tests/test_placa3_eco.py`: comportamento do eco e importação sem acessar hardware.
- `tests/test_servidor_irc.py`: protocolo IRC sobre conexões falsas.
- `tests/test_topologia.py`: endereços, portas físicas, rotas e serviços das placas.
- `tests/test_documentacao.py`: comandos operacionais obrigatórios no README.
- `verificar_projeto.sh`: verificação reproduzível no Linux antes de usar as placas.
- `README.md`: preparação, cópia, cabeamento, execução e diagnóstico.

### Task 1: Versionar e validar a pilha TCP/IP/SLIP

**Files:**
- Create: `.gitignore`
- Create: `tests/__init__.py`
- Create: `tests/test_pilha_integrada.py`
- Add: `tcp.py`
- Add: `tcputils.py`
- Add: `ip.py`
- Add: `iputils.py`
- Add: `slip.py`

- [ ] **Step 1: Criar as exclusões de artefatos Python**

Criar `.gitignore` com:

```gitignore
__pycache__/
*.py[cod]
```

- [ ] **Step 2: Criar o pacote de testes**

Criar `tests/__init__.py` com:

```python
"""Testes automatizados do projeto integrado."""
```

- [ ] **Step 3: Escrever o teste de integração da pilha**

Criar `tests/test_pilha_integrada.py` com:

```python
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
```

- [ ] **Step 4: Executar as suítes originais das três camadas**

Executar no PowerShell, a partir de `redes-s1`:

```powershell
Push-Location '..\2-tcp-redes-1-1'
python -m unittest discover -s tests -v
Pop-Location
Push-Location '..\3-ip-redes-1'
python -m unittest discover -s tests -v
Pop-Location
Push-Location '..\4-slip-redes-1'
python -m unittest discover -s tests -v
Pop-Location
```

Expected: 7 testes TCP, 5 testes IP e 15 testes SLIP terminam com `OK`.
Os tracebacks deliberados do teste 5 de SLIP podem aparecer, seguidos por `OK`.

- [ ] **Step 5: Confirmar a origem dos arquivos consolidados**

Executar:

```powershell
git diff --no-index -- '..\2-tcp-redes-1-1\tcp.py' '.\tcp.py'
git diff --no-index -- '..\2-tcp-redes-1-1\tcputils.py' '.\tcputils.py'
git diff --no-index -- '..\3-ip-redes-1\ip.py' '.\ip.py'
git diff --no-index -- '..\3-ip-redes-1\iputils.py' '.\iputils.py'
git diff --no-index -- '..\4-slip-redes-1\slip.py' '.\slip.py'
git diff --no-index -- '..\Seminario_final_redes-main\Seminario_final_redes-main\camadafisica.py' '.\camadafisica.py'
```

Expected: nenhum diff e código de saída `0` em cada comparação.

- [ ] **Step 6: Executar o teste com as versões consolidadas**

Run:

```powershell
python -m unittest tests.test_pilha_integrada -v
```

Expected: `test_handshake_percorre_slip_ip_e_tcp ... ok` e `OK`.

- [ ] **Step 7: Commit**

```powershell
git add .gitignore tests/__init__.py tests/test_pilha_integrada.py tcp.py tcputils.py ip.py iputils.py slip.py
git commit -m "feat: integrar camadas tcp ip e slip"
```

### Task 2: Tornar o servidor de eco testável e seguro para importação

**Files:**
- Create: `tests/test_placa3_eco.py`
- Modify: `placa3_eco.py:1-40`

- [ ] **Step 1: Escrever os testes do servidor de eco**

Criar `tests/test_placa3_eco.py` com:

```python
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
```

- [ ] **Step 2: Executar os testes para verificar a falha**

Run:

```powershell
python -m unittest tests.test_placa3_eco -v
```

Expected: FAIL com `AssertionError: o hardware foi acessado durante o import`,
porque o script atual inicializa a Zybo no nível do módulo.

- [ ] **Step 3: Isolar a inicialização do hardware em `main()`**

Substituir o conteúdo de `placa3_eco.py` por:

```python
#!/usr/bin/env python3
import asyncio

from camadafisica import ZyboSerialDriver
from ip import IP
from slip import CamadaEnlace
from tcp import Servidor


def dados_recebidos(conexao, dados):
    if dados == b"":
        conexao.fechar()
    else:
        conexao.enviar(dados)


def conexao_aceita(conexao):
    conexao.registrar_recebedor(dados_recebidos)


def main():
    nossa_ponta = "192.168.200.4"
    outra_ponta = "192.168.200.3"
    porta_tcp = 7000

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
```

- [ ] **Step 4: Executar os testes novamente**

Run:

```powershell
python -m unittest tests.test_placa3_eco -v
```

Expected: 2 testes terminam com `OK`.

- [ ] **Step 5: Commit**

```powershell
git add placa3_eco.py tests/test_placa3_eco.py
git commit -m "feat: adicionar servidor de eco da placa 3"
```

### Task 3: Validar e versionar a aplicação IRC adaptada

**Files:**
- Create: `tests/test_servidor_irc.py`
- Add: `servidor_irc.py`

- [ ] **Step 1: Escrever os testes da adaptação IRC**

Criar `tests/test_servidor_irc.py` com:

```python
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
```

- [ ] **Step 2: Executar os testes de caracterização**

Run:

```powershell
python -m unittest tests.test_servidor_irc -v
```

Expected: 3 testes terminam com `OK`. O arquivo já contém a adaptação feita no
working tree; estes testes impedem regressões antes de versioná-lo.

- [ ] **Step 3: Confirmar que somente o bootstrap foi removido do servidor original**

Run:

```powershell
git diff --no-index -- '..\1-irc-redes-1\servidor' '.\servidor_irc.py'
```

Expected: o diff remove os imports de `asyncio`, `tcp` e `sys`, a política de
event loop do Windows e o bootstrap final; os manipuladores do protocolo
permanecem iguais.

- [ ] **Step 4: Executar a suíte original do IRC**

Em PowerShell, iniciar uma instância nova do servidor para cada módulo de teste:

```powershell
$repo = (Resolve-Path '..\1-irc-redes-1').Path
$testes = @(
    'tests.test_ping',
    'tests.test_ping_fragmented',
    'tests.test_nick_validation',
    'tests.test_nick_duplicate',
    'tests.test_privmsg',
    'tests.test_join',
    'tests.test_part',
    'tests.test_quit',
    'tests.test_names',
    'tests.test_disconnect'
)
foreach ($teste in $testes) {
    $processo = Start-Process python -ArgumentList 'servidor' `
        -WorkingDirectory $repo -WindowStyle Hidden -PassThru
    Start-Sleep -Milliseconds 250
    Push-Location $repo
    python -m unittest $teste -v
    $codigo = $LASTEXITCODE
    Pop-Location
    if (-not $processo.HasExited) {
        Stop-Process -Id $processo.Id -Force
    }
    if ($codigo -ne 0) {
        throw "Falha em $teste"
    }
}
```

Expected: os 10 módulos de teste terminam com `OK`.

- [ ] **Step 5: Commit**

```powershell
git add servidor_irc.py tests/test_servidor_irc.py
git commit -m "feat: integrar servidor irc à pilha tcp"
```

### Task 4: Fixar a topologia e os serviços das três placas

**Files:**
- Create: `tests/test_topologia.py`
- Modify: `placa3.py:1-26`

- [ ] **Step 1: Escrever o teste dos contratos de topologia**

Criar `tests/test_topologia.py` com:

```python
import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def fonte(nome):
    conteudo = (ROOT / nome).read_text(encoding="utf-8")
    ast.parse(conteudo, filename=nome)
    return conteudo


class TestTopologia(unittest.TestCase):
    def test_placa1_liga_pty_a_placa2_pela_p0(self):
        codigo = fonte("placa1.py")
        self.assertIn("driver.obter_porta(0)", codigo)
        self.assertIn("outra_ponta = '192.168.200.1'", codigo)
        self.assertIn("nossa_ponta = '192.168.200.2'", codigo)
        self.assertIn("'192.168.200.3': serial1", codigo)
        self.assertIn(
            "('192.168.200.0/24', '192.168.200.3')",
            codigo,
        )

    def test_placa2_liga_p4_a_placa1_e_p0_a_placa3(self):
        codigo = fonte("placa2.py")
        self.assertIn("serial1 = driver.obter_porta(0)", codigo)
        self.assertIn("serial2 = driver.obter_porta(4)", codigo)
        self.assertIn("'192.168.200.4': serial1", codigo)
        self.assertIn("'192.168.200.2': serial2", codigo)
        self.assertIn(
            "('192.168.200.4/32', '192.168.200.4')",
            codigo,
        )

    def test_placa3_oferece_eco_e_irc_separadamente(self):
        eco = fonte("placa3_eco.py")
        irc = fonte("placa3.py")
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
```

- [ ] **Step 2: Executar o teste da topologia**

Run:

```powershell
python -m unittest tests.test_topologia -v
```

Expected: 3 testes terminam com `OK`, confirmando o working tree aprovado.

- [ ] **Step 3: Normalizar `placa3.py` sem alterar o comportamento**

Substituir `placa3.py` por:

```python
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
```

- [ ] **Step 4: Ajustar o teste para aspas independentes**

Como o código normalizado usa aspas duplas, substituir
`tests/test_topologia.py` pelo conteúdo abaixo:

```python
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
```

- [ ] **Step 5: Executar todos os testes integrados**

Run:

```powershell
python -m unittest discover -s tests -v
```

Expected: 9 testes terminam com `OK`.

- [ ] **Step 6: Commit**

```powershell
git add placa3.py tests/test_topologia.py
git commit -m "feat: configurar topologia e serviço irc"
```

### Task 5: Documentar cópia, cabeamento e execução no Linux

**Files:**
- Create: `tests/test_documentacao.py`
- Modify: `README.md`

- [ ] **Step 1: Escrever o teste da documentação operacional**

Criar `tests/test_documentacao.py` com:

```python
import unittest
from pathlib import Path


README = (
    Path(__file__).resolve().parents[1] / "README.md"
).read_text(encoding="utf-8")


class TestDocumentacao(unittest.TestCase):
    def test_readme_contem_fluxo_completo_das_placas(self):
        trechos = [
            "Placa 1 P0 ↔ Placa 2 P4",
            "Placa 2 P0 ↔ Placa 3 P0",
            "sudo python3 placa1.py",
            "sudo python3 placa2.py",
            "sudo python3 placa3_eco.py",
            "nc 192.168.200.4 7000",
            "sudo python3 placa3.py",
            "nc -C 192.168.200.4 6667",
        ]
        for trecho in trechos:
            with self.subTest(trecho=trecho):
                self.assertIn(trecho, README)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Executar o teste para verificar a falha**

Run:

```powershell
python -m unittest tests.test_documentacao -v
```

Expected: FAIL porque o README atual não documenta os dois programas da placa
3 nem o teste IRC na porta 6667.

- [ ] **Step 3: Adicionar o guia operacional ao final do README**

Adicionar após o Passo 3:

````markdown

# Projeto integrado do grupo

Esta pasta contém as implementações das práticas P1 a P4 integradas à
topologia do seminário. O servidor de eco valida primeiro a pilha completa; o
IRC é iniciado somente depois que o eco funcionar.

## Arquivos usados nas placas

Arquivos comuns às três placas:

```text
camadafisica.py
tcputils.py
iputils.py
tcp.py
ip.py
slip.py
```

Programas específicos:

- Placa 1: `placa1.py`
- Placa 2: `placa2.py`
- Placa 3, teste de eco: `placa3_eco.py`
- Placa 3, serviço final: `placa3.py` e `servidor_irc.py`

`placa3_eco.py` e `placa3.py` são alternativas. Nunca execute os dois ao mesmo
tempo.

## Criar o diretório e copiar os arquivos

Em cada placa:

```bash
mkdir -p ~/grupo-redes
```

Em um computador Linux, dentro da pasta `redes-s1`, informe os endereços SSH e
copie somente os arquivos necessários:

```bash
read -r -p "IP SSH da placa 1: " PLACA1_SSH
read -r -p "IP SSH da placa 2: " PLACA2_SSH
read -r -p "IP SSH da placa 3: " PLACA3_SSH

COMUNS="camadafisica.py tcputils.py iputils.py tcp.py ip.py slip.py"
scp $COMUNS placa1.py "alarm@$PLACA1_SSH:~/grupo-redes/"
scp $COMUNS placa2.py "alarm@$PLACA2_SSH:~/grupo-redes/"
scp $COMUNS placa3_eco.py placa3.py servidor_irc.py \
    "alarm@$PLACA3_SSH:~/grupo-redes/"
```

O usuário e a senha padrão são `alarm`.

## Cabeamento

Desligue as placas antes de alterar os fios. Una primeiro os terras das três
placas. Em cada enlace, ligue TX de uma placa ao RX da outra e RX ao TX:

```text
Placa 1 P0 ↔ Placa 2 P4
Placa 2 P0 ↔ Placa 3 P0
```

Não conecte os pinos de alimentação.

## Teste do servidor de eco

Na placa 2:

```bash
cd ~/grupo-redes
sudo python3 placa2.py
```

Na placa 3:

```bash
cd ~/grupo-redes
sudo python3 placa3_eco.py
```

Na placa 1:

```bash
cd ~/grupo-redes
sudo python3 placa1.py
```

Sem encerrar `placa1.py`, abra outros terminais com `tmux`. Em um deles, informe
a PTY exibida e execute `slattach`:

```bash
read -r -p "PTY exibida por placa1.py: " PTY_SLIP
sudo slattach -v -p slip "$PTY_SLIP"
```

Em outro terminal, execute os comandos impressos por `placa1.py`:

```bash
sudo ifconfig sl0 192.168.200.1 pointopoint 192.168.200.2
sudo ip route add 192.168.200.0/24 via 192.168.200.2
```

Ainda na placa 1:

```bash
nc 192.168.200.4 7000
```

Tudo que for digitado deve voltar igual. Encerre o `nc` com `Ctrl+C`. Se a
implementação IP inclui ICMP Time Exceeded, também execute:

```bash
mtr 192.168.200.4
```

## Teste do servidor IRC

Na placa 3, encerre `placa3_eco.py` com `Ctrl+C` e inicie o serviço final:

```bash
sudo python3 placa3.py
```

Na placa 1:

```bash
nc -C 192.168.200.4 6667
```

Digite:

```text
PING teste
NICK aluno
JOIN #redes
```

As respostas devem incluir `PONG`, o código `001`, o código `422`, a mensagem
`JOIN` e o fim da lista de nomes `366`. Para testar `PRIVMSG`, abra um segundo
`nc`, registre outro apelido, entre em `#redes` e envie:

```text
PRIVMSG #redes :mensagem entre as placas
```
````

- [ ] **Step 4: Executar o teste da documentação novamente**

Run:

```powershell
python -m unittest tests.test_documentacao -v
```

Expected: 1 teste, com 8 subtestes, termina com `OK`.

- [ ] **Step 5: Commit**

```powershell
git add README.md tests/test_documentacao.py
git commit -m "docs: explicar execução do projeto nas placas"
```

### Task 6: Adicionar a verificação reproduzível para Linux

**Files:**
- Create: `verificar_projeto.sh`

- [ ] **Step 1: Criar o script de verificação**

Criar `verificar_projeto.sh` com:

```bash
#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

python3 -m compileall -q \
    camadafisica.py \
    tcputils.py \
    tcp.py \
    iputils.py \
    ip.py \
    slip.py \
    servidor_irc.py \
    placa1.py \
    placa2.py \
    placa3_eco.py \
    placa3.py

python3 -m unittest discover -s tests -v

echo "Projeto validado: sintaxe e testes integrados passaram."
```

- [ ] **Step 2: Validar a sintaxe do shell**

Run on Linux or WSL:

```bash
bash -n verificar_projeto.sh
```

Expected: código de saída `0`, sem saída.

- [ ] **Step 3: Executar a verificação completa sem acessar a Zybo**

Run on Linux or WSL:

```bash
bash verificar_projeto.sh
```

Expected: todos os testes terminam com `OK` e a última linha é
`Projeto validado: sintaxe e testes integrados passaram.`

- [ ] **Step 4: Marcar o script como executável e fazer commit**

```bash
git add verificar_projeto.sh
git update-index --chmod=+x verificar_projeto.sh
git commit -m "test: adicionar verificação do projeto integrado"
```

### Task 7: Executar a regressão final local

**Files:**
- Verify: todos os arquivos do projeto

- [ ] **Step 1: Executar todos os testes integrados**

Run:

```powershell
python -m unittest discover -s tests -v
```

Expected: todos os testes terminam com `OK`.

- [ ] **Step 2: Executar novamente as suítes das práticas**

Run:

```powershell
Push-Location '..\2-tcp-redes-1-1'
python -m unittest discover -s tests -v
Pop-Location
Push-Location '..\3-ip-redes-1'
python -m unittest discover -s tests -v
Pop-Location
Push-Location '..\4-slip-redes-1'
python -m unittest discover -s tests -v
Pop-Location
```

Expected: TCP, IP e SLIP terminam com `OK`.

- [ ] **Step 3: Verificar whitespace e estado Git**

Run:

```powershell
git diff --check
git status --short --branch
```

Expected: `git diff --check` não produz saída. O status não mostra arquivos
modificados ou não rastreados.

### Task 8: Validar nas três placas

**Files:**
- Verify: instalação copiada para `~/grupo-redes` em cada placa

- [ ] **Step 1: Conferir cabeamento e processos**

Confirmar fisicamente:

```text
Placa 1 P0 ↔ Placa 2 P4
Placa 2 P0 ↔ Placa 3 P0
Terra comum entre as três placas
Nenhum pino de alimentação conectado
```

Expected: apenas `placa1.py`, `placa2.py` e um dos programas da placa 3 estão
em execução.

- [ ] **Step 2: Iniciar roteador, eco e entrada Linux**

Na placa 2:

```bash
cd ~/grupo-redes
sudo python3 placa2.py
```

Na placa 3:

```bash
cd ~/grupo-redes
sudo python3 placa3_eco.py
```

Na placa 1:

```bash
cd ~/grupo-redes
sudo python3 placa1.py
```

Expected: os três processos permanecem em execução sem traceback.

- [ ] **Step 3: Configurar a interface da placa 1**

Em terminais adicionais da placa 1, executar:

```bash
read -r -p "PTY exibida por placa1.py: " PTY_SLIP
sudo slattach -v -p slip "$PTY_SLIP"
sudo ifconfig sl0 192.168.200.1 pointopoint 192.168.200.2
sudo ip route add 192.168.200.0/24 via 192.168.200.2
ip addr show sl0
ip route get 192.168.200.4
```

Expected: `sl0` mostra `192.168.200.1` com peer `192.168.200.2`; a rota para
`192.168.200.4` usa `192.168.200.2`.

- [ ] **Step 4: Validar eco ponta a ponta**

Na placa 1:

```bash
nc 192.168.200.4 7000
```

Digitar `teste-seminario` e pressionar Enter.

Expected: o servidor devolve `teste-seminario`. Encerrar o cliente com
`Ctrl+C`.

- [ ] **Step 5: Trocar o eco pelo IRC**

Encerrar `placa3_eco.py` com `Ctrl+C` na placa 3 e executar:

```bash
sudo python3 placa3.py
```

Expected: o IRC permanece em execução e nenhum processo de eco continua ativo.

- [ ] **Step 6: Validar IRC ponta a ponta**

Na placa 1:

```bash
nc -C 192.168.200.4 6667
```

Digitar, uma linha por vez:

```text
PING teste
NICK aluno
JOIN #redes
```

Expected: a saída contém `PONG`, `001 aluno`, `422 aluno`, `JOIN :#redes` e
`366 aluno #redes`. Encerrar o cliente com `Ctrl+C`.

- [ ] **Step 7: Registrar o resultado operacional**

Anotar no relatório do seminário:

```text
Topologia: placa 1 P0 ↔ placa 2 P4; placa 2 P0 ↔ placa 3 P0
Eco: 192.168.200.4:7000 validado a partir da placa 1
IRC: 192.168.200.4:6667 validado a partir da placa 1
Roteador intermediário: 192.168.200.3
```

Expected: os quatro itens refletem os resultados observados durante o teste.
