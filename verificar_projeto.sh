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
