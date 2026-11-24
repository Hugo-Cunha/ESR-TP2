#!/usr/bin/env python3
# Cliente de streaming. NÃO é um nó do overlay: só conhece o IP do seu onode.
#
#   - de 1 em 1 s envia PEDIR {stream} ao onode (UDP 6003);
#   - recebe os pacotes de vídeo na porta UDP 6001 e mostra-os (só pacotes RTP:
#     o onode retira o cabeçalho do overlay, por isso o cliente não sabe de que
#     servidor vem o vídeo nem por que caminho);
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

from comum import config, log as log_mod
from comum.estatisticas import Estatisticas
from comum.log import log
from comum.mensagem import Mensagem
from comum.RtpPacket import RtpPacket


class Cliente:
    def __init__(self, onode, stream, ip="0.0.0.0", stats=False):
        self.onode = onode
        self.mostrar_stats = stats            # --stats: linha de estatísticas de 2 em 2 s (testes)
        self.stream = stream                  # None = parado
        self.estado = None                    # última resposta do onode
        self.stats = Estatisticas()
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
        self.stream = self.ultima_stream = stream
        log(f"A pedir '{stream}' ao onode {self.onode}")

    ##############################################################################
    #* Receção do vídeo

    def svc_receber(self):
        while self.a_correr:
            rtp_bytes, _ = self.sock_dados.recvfrom(65535)
            if self.stream is None or len(rtp_bytes) <= 12:
                continue
            rtp = RtpPacket()
            rtp.decode(rtp_bytes)
            if self.stats.registar(rtp):
                self.ultima_frame = rtp.getPayload()

    def svc_estatisticas(self):
        """No terminal só aparecem EVENTOS: começou a receber, ficou sem vídeo, o vídeo
        voltou, a fonte mudou. Com --stats (usado pelos testes) escreve também uma linha
        de estatísticas de 2 em 2 s."""
        a_receber, ssrc, ultimo_stats, stream, parado_desde = False, None, 0.0, None, None
        while self.a_correr:
            time.sleep(0.25)
            agora = time.time()
            s = self.stats
            if self.stream != stream:             # play/stop: recomeça do zero
                a_receber, ssrc, stream, parado_desde = False, None, self.stream, None
            if self.stream is None:
                continue
            recente = s.ultima_chegada is not None and agora - s.ultima_chegada < 1.0
            if recente and not a_receber:
                log(f"A receber '{self.stream}'" + (f" (vídeo parado durante {agora - parado_desde:.1f} s)"
                                                     if parado_desde else ""))
            elif a_receber and not recente:
                parado_desde = s.ultima_chegada
                log(f"Sem vídeo de '{self.stream}' há 1 s")
            if recente and ssrc is not None and s.ssrc != ssrc:
                log(f"A stream passou a vir de outra fonte (SSRC {ssrc:08x} -> {s.ssrc:08x})")
            if recente:
                ssrc = s.ssrc
            a_receber = recente
            if self.mostrar_stats and agora - ultimo_stats >= 2:
                ultimo_stats = agora
                log(f"STATS stream={self.stream} {s.resumo()}")


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
    ap.add_argument("--sem-gui", action="store_true", help="não abre janela")
    ap.add_argument("--stats", action="store_true", help="escreve estatísticas (perdas, fps, jitter) de 2 em 2 s")
    args = ap.parse_args()

    log_mod.nome = socket.gethostname() if args.ip == "0.0.0.0" else f"cliente {args.ip}"
    cliente = Cliente(args.onode, args.stream, args.ip, args.stats)
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
            # o Play retoma a última stream pedida (que pode ter mudado com "play <stream>")
            gui = ClienteGUI(root, lambda: cliente.ver(cliente.ultima_stream), cliente.parar)

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
