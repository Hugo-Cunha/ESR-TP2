#!/usr/bin/env python3
# Bootstrapper: o único que conhece o overlay inteiro (lido de um ficheiro JSON).
#
# Cada nó, ao arrancar, envia-lhe REGISTO e recebe BOAS_VINDAS com o seu nome e a
# lista de vizinhos (nome + IP). A ligação fecha logo a seguir e o bootstrapper
# não volta a intervir: rotas, fluxos e falhas são tratados entre vizinhos.
# Fica à escuta apenas para os nós que entrem (ou reentrem) mais tarde.
#
# Uso:  python3 bootstrapper.py configs/overlay_topo3.json

import json
import socket
import sys
import threading

from comum import config, log as log_mod
from comum.log import log
from comum.mensagem import LeitorMensagens, Mensagem


def ler_configuracao(ficheiro):
    """Lê o mapa do overlay e torna as ligações simétricas (se A tem B, B tem A).

    Formato: {"nodes": {"S1": {"ip": "10.0.18.20", "neighbours": ["O1", "O2"]}, ...}}"""
    with open(ficheiro) as f:
        nos = json.load(f)["nodes"]
    vizinhos = {nome: set(no["neighbours"]) for nome, no in nos.items()}
    for nome in nos:
        for v in list(vizinhos[nome]):
            vizinhos[v].add(nome)
    return nos, vizinhos


def handle_registo(sock, ip, nos, vizinhos):
    try:
        msg = LeitorMensagens(sock).ler()
        if msg is None or msg.tipo != Mensagem.REGISTO:
            return
        nome = next((n for n, no in nos.items() if no["ip"] == ip), None)
        if nome is None:
            log(f"Registo recusado: {ip} não está na configuração")
            sock.sendall(Mensagem(Mensagem.ERRO, dados={"motivo": f"{ip} desconhecido"}).serialize())
            return
        lista = [{"ip": nos[v]["ip"], "nome": v} for v in sorted(vizinhos[nome])]
        sock.sendall(Mensagem(Mensagem.BOAS_VINDAS, dados={"ip": ip, "nome": nome, "vizinhos": lista}).serialize())
        log(f"{nome} ({ip}) registado -> vizinhos: {', '.join(v['nome'] for v in lista)}")
    finally:
        sock.close()


def main():
    if len(sys.argv) < 2:
        print(f"Uso: python3 {sys.argv[0]} <configuracao.json> [ip]")
        sys.exit(1)
    nos, vizinhos = ler_configuracao(sys.argv[1])
    ip_escuta = sys.argv[2] if len(sys.argv) > 2 else "0.0.0.0"
    log_mod.nome = "BOOT"

    log(f"Overlay com {len(nos)} nós:")
    for nome in sorted(nos):
        log(f"  {nome:3} {nos[nome]['ip']:15} -> {', '.join(sorted(vizinhos[nome]))}")

    servidor = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    servidor.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    servidor.bind((ip_escuta, config.BOOTSTRAP_PORT))
    servidor.listen()
    log(f"À escuta na porta {config.BOOTSTRAP_PORT}")
    while True:
        sock, (ip, _) = servidor.accept()
        threading.Thread(target=handle_registo, args=(sock, ip, nos, vizinhos), daemon=True).start()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
