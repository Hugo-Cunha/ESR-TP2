# Serviços de DADOS (UDP): emissão das streams no servidor, reencaminhamento
# nos nós intermédios e PING de teste do caminho (Etapa 3).

import random
import socket
import threading
import time
import zlib

from comum import config, pacote_dados
from comum.log import log
from comum.mensagem import Mensagem
from comum.RtpPacket import PT_JPEG, RtpPacket
from comum.VideoStream import VideoStream
from servicos import vizinhos


def abrir_socket_dados(db):
    db.sock_dados = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    db.sock_dados.bind((db.bind_ip, config.DATA_PORT))


def enviar_dados(db, pacote, ip, mais_um_salto):
    """Envia uma cópia do pacote a um vizinho (ou cliente), com o nº de sequência
    dessa ligação (é com ele que o vizinho mede as perdas)."""
    db.seq_tx[ip] = db.seq_tx.get(ip, 0) + 1
    pacote = pacote_dados.para_ligacao(pacote, db.seq_tx[ip], mais_um_salto)
    if random.random() * 100 < db.perdas_emuladas.get(ip, 0):
        return                                # (testes) emula perdas na ligação
    atraso = db.atrasos.get(ip)
    if atraso:                                # (testes) emula atraso na ligação
        threading.Timer(atraso, db.sock_dados.sendto, (pacote, (ip, config.DATA_PORT))).start()
    else:
        db.sock_dados.sendto(pacote, (ip, config.DATA_PORT))


##################################################################################
#* Serviço do servidor: emitir uma stream (uma thread por stream)

def svc_emitir_stream(db, stream, ficheiro):
    """Lê uma frame a cada 1/FPS s. Só a envia se houver destinos para este fluxo:
    sem clientes não há tráfego. É uma emissão "em direto": quem entra a meio
    começa a ver na frame atual."""
    video = VideoStream(ficheiro)
    ssrc = zlib.crc32(f"{db.meu_ip}/{stream}".encode())   # identifica esta fonte
    seq = 0
    log(f"A emitir '{stream}' ({ficheiro}) a {config.FPS} fps")
    while db.a_correr:
        frame = video.nextFrame()
        with db.lock:
            fluxo = db.fluxos.get((db.meu_ip, stream))
            destinos = list(fluxo.destinos) + list(fluxo.clientes) if fluxo else []
        if destinos:
            seq = (seq + 1) % 65536
            rtp = RtpPacket()
            rtp.encode(version=2, padding=0, extension=0, cc=0, seqnum=seq, marker=0, pt=PT_JPEG,
                       ssrc=ssrc, timestamp=(video.frameNbr() * 90000 // config.FPS) % 2**32, payload=frame)
            pacote = pacote_dados.criar(db.meu_ip, stream, 0, time.time(), rtp.getPacket())
            for ip in destinos:
                enviar_dados(db, pacote, ip, mais_um_salto=False)
        time.sleep(1 / config.FPS)


##################################################################################
#* Serviço de todos os nós: receber e reencaminhar pacotes de dados

def svc_receber_dados(db):
    while db.a_correr:
        pacote, (ip_origem, _) = db.sock_dados.recvfrom(65535)
        lido = pacote_dados.ler(pacote)
        if lido is None:
            continue
        servidor, stream, saltos, seq_ligacao, t_envio, _ = lido
        with db.lock:
            v = db.vizinhos.get(ip_origem)
            if v is not None:                 # medição passiva das perdas desta ligação
                vizinhos.registar_seq_recebido(v, seq_ligacao)
            rota = db.rotas.get(servidor)
            fluxo = db.fluxos.get((servidor, stream))
            # só aceitamos o pacote se vier da nossa Origem para esse servidor
            if rota is None or fluxo is None or rota.origem != ip_origem:
                continue
            destinos = list(fluxo.destinos) + list(fluxo.clientes)
        # uma cópia para cada destino e para cada cliente ligado a este nó
        # (é aqui que se "replica" na árvore)
        for ip in destinos:
            enviar_dados(db, pacote, ip, mais_um_salto=True)


##################################################################################
#* PING (Etapa 3): o servidor envia-o pelos fluxos ativos; cada nó regista a
#  passagem, acrescenta-se ao caminho e reenvia-o para os seus destinos.

def enviar_ping(db):
    with db.lock:
        enviados = 0
        for fluxo in db.fluxos.values():
            if fluxo.servidor == db.meu_ip and fluxo.preciso():
                msg = Mensagem(Mensagem.PING, dados={"servidor": db.meu_ip, "stream": fluxo.stream,
                                                     "t0": time.time(), "caminho": [db.meu_nome]})
                for ip in fluxo.destinos:
                    vizinhos.enviar(db, ip, msg)
                if fluxo.clientes:
                    log(f"PING: {db.meu_nome}/{fluxo.stream} tem clientes ligados diretamente: {sorted(fluxo.clientes)}")
                enviados += 1
        return f"PING enviado em {enviados} fluxo(s) ativo(s)" if enviados else \
            "Nenhum fluxo ativo (é preciso haver um cliente a ver uma stream deste servidor)"


def handle_ping(db, ip, msg):
    d = msg.dados
    caminho = d["caminho"] + [db.meu_nome]
    log(f"PING {d['caminho'][0]}/{d['stream']} recebido de {db.nome_de(ip)}; caminho: {' > '.join(caminho)}")
    fluxo = db.fluxos.get((d["servidor"], d["stream"]))
    if fluxo is None:
        return
    for destino in fluxo.destinos:
        vizinhos.enviar(db, destino, Mensagem(Mensagem.PING, dados=dict(d, caminho=caminho)))
    if fluxo.clientes:
        ms = (time.time() - d["t0"]) * 1000
        log(f"PING chegou ao onode dos clientes {sorted(fluxo.clientes)}: {' > '.join(caminho)} "
            f"({len(caminho) - 1} saltos, {ms:.1f} ms)")
