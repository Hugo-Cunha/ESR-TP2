#!/usr/bin/env python3
# Cliente de streaming. NÃO é um nó do overlay: só conhece o IP do seu onode.
#
#   - de 1 em 1 s envia PEDIR {stream} ao onode (UDP 6003);
#   - recebe os pacotes de vídeo na porta UDP 6001 e mostra-os;
#   - se o onode morrer, deixa de receber vídeo mas continua a pedir; quando o
#     onode voltar, o vídeo volta sozinho.
#
# Uso:  python3 cliente.py <ip_do_onode> <stream> [--sem-gui]
# ex.:  python3 cliente.py 10.0.17.20 filmeA        (PC5, ligado ao PC4)
#
# Comandos no terminal: play <stream> | stop | sair

import argparse
import socket
import sys
import threading
import time

from comum import config, log as log_mod, pacote_dados
from comum.estatisticas import Estatisticas
from comum.log import log
from comum.mensagem import Mensagem
from comum.RtpPacket import RtpPacket


class Cliente:
    def __init__(self, onode, stream, ip="0.0.0.0"):
        self.onode = onode
        self.stream = stream                  # None = parado
        self.estado = None                    # última resposta do onode
        self.stats = Estatisticas()
        self.servidor = None
        self.ultima_frame = None              # lida pela janela
        self.a_correr = True
        self.sock_dados = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock_dados.bind((ip, config.DATA_PORT))
        self.sock_pedidos = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock_pedidos.bind((ip, 0))
        self.sock_pedidos.settimeout(config.PEDIR_INTERVALO)

    ##############################################################################
    #* Pedidos ao onode (de 1 em 1 s)

    def svc_pedir(self):
        while self.a_correr:
            if self.stream is None:
                time.sleep(config.PEDIR_INTERVALO)
                continue
            msg = Mensagem(Mensagem.PEDIR, dados={"stream": self.stream})
            self.sock_pedidos.sendto(msg.serialize(), (self.onode, config.CLIENTE_PORT))
            try:
                resposta = Mensagem.deserialize(self.sock_pedidos.recv(4096).decode())
                estado = resposta.dados["estado"]
                time.sleep(config.PEDIR_INTERVALO)
            except (socket.timeout, ValueError):
                estado = "o onode não responde"
            except OSError:                    # (ex.: ICMP port unreachable: onode em baixo)
                estado = "o onode não responde"
                time.sleep(config.PEDIR_INTERVALO)
            if estado != self.estado:
                log(f"Onode {self.onode}: {estado}")
                self.estado = estado

    def parar(self):
        self.stream = None
        msg = Mensagem(Mensagem.PARAR)
        self.sock_pedidos.sendto(msg.serialize(), (self.onode, config.CLIENTE_PORT))
        log("Parado")

    def ver(self, stream):
        if self.stream != stream:
            self.stats = Estatisticas()
        self.stream = stream
        log(f"A pedir '{stream}' ao onode {self.onode}")

    ##############################################################################
    #* Receção do vídeo

    def svc_receber(self):
        while self.a_correr:
            pacote, _ = self.sock_dados.recvfrom(65535)
            lido = pacote_dados.ler(pacote)
            if lido is None or self.stream is None:
                continue
            servidor, stream, saltos, t_envio, rtp_bytes = lido
            if stream != self.stream:
                continue
            rtp = RtpPacket()
            rtp.decode(rtp_bytes)
            self.servidor = servidor
            if self.stats.registar(rtp, saltos, t_envio):
                self.ultima_frame = rtp.getPayload()

    def svc_estatisticas(self):
        """De 2 em 2 s escreve no terminal como está a correr a receção."""
        while self.a_correr:
            time.sleep(2)
            if self.stream:
                log(f"STATS stream={self.stream} servidor={self.servidor} {self.stats.resumo()}")


def consola(cliente):
    for linha in sys.stdin:
        partes = linha.split()
        if partes[:1] == ["play"] and len(partes) == 2:
            cliente.ver(partes[1])
        elif partes[:1] == ["stop"]:
            cliente.parar()
        elif partes[:1] == ["sair"]:
            break
        elif partes:
            print("Comandos: play <stream> | stop | sair", flush=True)
    else:
        while cliente.a_correr:              # sem terminal: fica a correr
            time.sleep(1)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Cliente de streaming")
    ap.add_argument("onode", help="IP do onode a que este cliente se liga")
    ap.add_argument("stream", help="stream a ver (ex.: filmeA)")
    ap.add_argument("--ip", default="0.0.0.0", help="(testes) IP local a usar")
    ap.add_argument("--sem-gui", action="store_true", help="não abre janela (só estatísticas)")
    args = ap.parse_args()

    log_mod.nome = socket.gethostname() if args.ip == "0.0.0.0" else f"cliente {args.ip}"
    cliente = Cliente(args.onode, args.stream, args.ip)
    cliente.ver(args.stream)
    for svc in (cliente.svc_pedir, cliente.svc_receber, cliente.svc_estatisticas):
        threading.Thread(target=svc, daemon=True).start()

    try:
        if args.sem_gui:
            consola(cliente)
        else:
            from tkinter import Tk
            from comum.ClienteGUI import ClienteGUI
            threading.Thread(target=consola, args=(cliente,), daemon=True).start()
            root = Tk()
            root.title(f"{log_mod.nome} - {args.stream} (onode {args.onode})")
            gui = ClienteGUI(root, lambda: cliente.ver(args.stream), cliente.parar)

            def copiar_frame():                 # passa a frame mais recente para a janela
                gui.ultima_frame = cliente.ultima_frame
                root.after(40, copiar_frame)
            copiar_frame()
            root.mainloop()
    except KeyboardInterrupt:
        pass
    if cliente.stream:
        cliente.parar()
    cliente.a_correr = False
