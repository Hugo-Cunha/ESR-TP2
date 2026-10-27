#!/usr/bin/env python3
# Envia um comando a um nó que esteja a correr nesta máquina (ou neste nó do CORE)
# e mostra a resposta. Útil quando o nó corre em fundo, sem terminal.
#
# Uso:  python3 ottctl.py rotas
#       python3 ottctl.py vizinhos
#       python3 ottctl.py ping            (num servidor)
#       python3 ottctl.py --ip 127.10.0.5 rotas   (testes locais)

import socket
import sys

from comum import config

args = sys.argv[1:]
ip = "127.0.0.1"
if len(args) >= 2 and args[0] == "--ip":
    ip, args = args[1], args[2:]
if not args:
    print(__doc__ if __doc__ else "Uso: python3 ottctl.py <comando>")
    sys.exit(1)
try:
    s = socket.create_connection((ip, config.CMD_PORT), timeout=5)
except OSError as e:
    sys.exit(f"Não há nenhum nó a correr aqui ({e})")
s.sendall((" ".join(args) + "\n").encode())
resposta = b""
while True:
    parte = s.recv(65536)
    if not parte:
        break
    resposta += parte
print(resposta.decode().rstrip())
