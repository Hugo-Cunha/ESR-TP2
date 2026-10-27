#!/usr/bin/env python3
# Servidor de streaming = nó do overlay + emissão de streams + anúncios.
#
# Uso:  python3 servidor.py <ip_bootstrapper> <stream> [<stream> ...]
# ex.:  python3 servidor.py 10.0.18.10 filmeA filmeB
#       (lê videos/filmeA.Mjpeg e videos/filmeB.Mjpeg; também aceita nome=ficheiro)
#
# Comandos extra: ping (Etapa 3: testa o caminho dos fluxos ativos)

import threading

import onode
from servicos import dados, rotas

if __name__ == "__main__":
    ap = onode.argumentos("Servidor de streaming")
    ap.add_argument("streams", nargs="+", metavar="STREAM")
    args = ap.parse_args()

    db = onode.iniciar(args.bootstrapper, args.ip, onode.atrasos(args))
    for s in args.streams:
        nome, _, ficheiro = s.partition("=")
        db.streams_locais[nome] = ficheiro or f"videos/{nome}.Mjpeg"

    threading.Thread(target=rotas.svc_anunciar, args=(db,), daemon=True).start()
    for stream, ficheiro in db.streams_locais.items():
        threading.Thread(target=dados.svc_emitir_stream, args=(db, stream, ficheiro), daemon=True).start()

    comandos = onode.comandos_base(db)
    comandos["ping"] = lambda a: dados.enviar_ping(db)
    onode.correr(db, comandos)
