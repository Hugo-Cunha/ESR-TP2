#!/usr/bin/env python3
# Nó do overlay (onode). O servidor.py é este mesmo nó com as streams por cima.
# Os clientes (cliente.py) NÃO são nós do overlay: ligam-se a um onode.
#
# Uso:  python3 onode.py <ip_bootstrapper>
#
# Comandos no terminal (ou a partir de outro terminal com: python3 ottctl.py <comando>):
#     vizinhos | rotas | sair

import argparse
import socket
import sys
import threading

from comum import config, log as log_mod
from comum.log import log
from database import Database
from servicos import clientes, dados, fluxos, rotas, vizinhos


def iniciar(bootstrapper, ip="0.0.0.0", atrasos=None):
    """Regista o nó no bootstrapper e arranca todos os serviços (uma thread cada)."""
    db = Database(bootstrapper, ip)
    vizinhos.registar_no_bootstrapper(db)
    log_mod.nome = db.meu_nome
    db.atrasos = dict(atrasos or {})
    dados.abrir_socket_dados(db)

    servicos = [
        vizinhos.svc_aceitar_ligacoes,    # aceita ligações de vizinhos
        vizinhos.svc_ligar_vizinhos,      # liga a vizinhos em falta
        vizinhos.svc_alive,               # ALIVE de 1 em 1 s
        rotas.svc_manter_rotas,           # expira caminhos antigos
        fluxos.svc_manter_fluxos,         # refresca/expira pedidos de fluxos
        dados.svc_receber_dados,          # recebe e reencaminha o vídeo
        clientes.svc_clientes,            # atende os clientes ligados a este nó
    ]
    for svc in servicos:
        threading.Thread(target=svc, args=(db,), daemon=True).start()
    return db


##################################################################################
#* Comandos de gestão (terminal e ottctl.py)

def comandos_base(db):
    return {
        "vizinhos": lambda args: db.tabela_vizinhos(),
        "rotas": lambda args: db.tabela_rotas(),
        "delay": lambda args: definir_atraso(db, args),
    }


def definir_atraso(db, args):
    """(testes sem CORE) delay <ip> <ms>: emula atraso na ligação para esse vizinho."""
    ip, ms = args[0], float(args[1])
    db.atrasos[ip] = ms / 1000
    return f"atraso para {db.nome_de(ip)} = {ms:.0f} ms"


def executar(comandos, linha):
    partes = linha.split()
    if not partes:
        return ""
    comando = comandos.get(partes[0])
    if comando is None:
        return "Comandos: " + ", ".join(sorted(comandos)) + ", sair"
    return comando(partes[1:])


def svc_comandos(db, comandos):
    """Recebe comandos do ottctl.py numa porta local e devolve a resposta."""
    servidor = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    servidor.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    servidor.bind(("127.0.0.1" if db.bind_ip == "0.0.0.0" else db.bind_ip, config.CMD_PORT))
    servidor.listen()
    while True:
        sock, _ = servidor.accept()
        linha = sock.recv(1024).decode().strip()
        if linha == "sair":
            sock.sendall(b"a sair\n")
            sock.close()
            vizinhos.sair(db)
            continue
        sock.sendall((executar(comandos, linha) + "\n").encode())
        sock.close()


def correr(db, comandos):
    """Lê comandos do terminal até 'sair' (ou Ctrl+C). Se não houver terminal
    (processo em fundo), fica simplesmente a correr."""
    threading.Thread(target=svc_comandos, args=(db, comandos), daemon=True).start()
    try:
        for linha in sys.stdin:
            if linha.strip() == "sair":
                break
            resposta = executar(comandos, linha)
            if resposta:
                print(resposta, flush=True)
        else:
            while db.a_correr:                # stdin fechado: continua até 'sair' pelo ottctl
                threading.Event().wait(1)
    except KeyboardInterrupt:
        pass
    vizinhos.sair(db)


def argumentos(descricao):
    ap = argparse.ArgumentParser(description=descricao)
    ap.add_argument("bootstrapper", help="IP do bootstrapper")
    ap.add_argument("--ip", default="0.0.0.0", help="(testes) IP local a usar")
    ap.add_argument("--link-delay", action="append", default=[], metavar="IP=MS",
                    help="(testes sem CORE) atraso emulado para um vizinho")
    return ap


def atrasos(args):
    return {ip: float(ms) / 1000 for ip, ms in (x.split("=") for x in args.link_delay)}


if __name__ == "__main__":
    args = argumentos("Nó do overlay (relay)").parse_args()
    db = iniciar(args.bootstrapper, args.ip, atrasos(args))
    correr(db, comandos_base(db))
