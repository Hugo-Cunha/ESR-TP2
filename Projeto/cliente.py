#!/usr/bin/env python3
# Cliente de streaming = nó do overlay + janela para ver o vídeo.
# O cliente também é um nó overlay: tem vizinhos e rotas, por isso, se o vizinho
# por onde recebe o vídeo cair, passa a receber por outro.
#
# Uso:  python3 cliente.py <ip_bootstrapper> <stream> [--sem-gui]
# ex.:  python3 cliente.py 10.0.18.10 filmeA
#
# Comandos extra: play <stream> | stop

import threading
import time

import onode
from comum.estatisticas import Estatisticas
from comum.log import log
from comum.RtpPacket import RtpPacket
from servicos import fluxos


def mostrar_estatisticas(db, stats):
    """De 2 em 2 s escreve no terminal como está a correr a receção."""
    while db.a_correr:
        time.sleep(2)
        if db.stream_pedida:
            with db.lock:
                rota = db.rotas.get(db.fluxo_local[0]) if db.fluxo_local else None
                servidor = rota.nome_servidor if rota else None
                caminho = " > ".join([n for _, n in rota.caminho] + [db.meu_nome]) if rota and rota.origem else "-"
            log(f"STATS stream={db.stream_pedida} servidor={servidor} {stats.resumo()} caminho={caminho}")


if __name__ == "__main__":
    ap = onode.argumentos("Cliente de streaming")
    ap.add_argument("stream", help="stream a ver (ex.: filmeA)")
    ap.add_argument("--sem-gui", action="store_true", help="não abre janela (só estatísticas)")
    args = ap.parse_args()

    db = onode.iniciar(args.bootstrapper, args.ip, onode.atrasos(args))
    stats = Estatisticas()
    gui = None

    def receber(rtp_bytes, saltos, t_envio):
        """Chamada pelo serviço de dados para cada pacote do fluxo que estamos a ver."""
        rtp = RtpPacket()
        rtp.decode(rtp_bytes)
        if stats.registar(rtp, saltos, t_envio) and gui:
            gui.ultima_frame = rtp.getPayload()

    db.entregar_local = receber
    threading.Thread(target=mostrar_estatisticas, args=(db, stats), daemon=True).start()
    fluxos.pedir_stream(db, args.stream)

    comandos = onode.comandos_base(db)
    comandos["play"] = lambda a: fluxos.pedir_stream(db, a[0]) or f"a ver {a[0]}"
    comandos["stop"] = lambda a: fluxos.parar_stream(db) or "parado"

    if args.sem_gui:
        onode.correr(db, comandos)
    else:
        from tkinter import Tk
        from comum.ClienteGUI import ClienteGUI
        threading.Thread(target=onode.correr, args=(db, comandos), daemon=True).start()
        root = Tk()
        root.title(f"{db.meu_nome} - {args.stream}")
        gui = ClienteGUI(root, lambda: fluxos.pedir_stream(db, args.stream),
                         lambda: fluxos.parar_stream(db))
        root.mainloop()
        from servicos import vizinhos
        vizinhos.sair(db)
