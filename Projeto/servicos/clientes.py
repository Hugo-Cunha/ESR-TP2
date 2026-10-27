# Serviço de CLIENTES: atende os clientes ligados a este onode (UDP, porta 6003).
#
# O cliente não faz parte do overlay: só conhece o IP do seu onode. De 1 em 1 s
# envia-lhe PEDIR {stream}; o onode responde PEDIR_RESP com o estado e passa a
# enviar-lhe os pacotes de vídeo (UDP, porta 6001 do cliente).
#   - se o cliente deixar de pedir durante 3,5 s, o onode esquece-o (e poda o fluxo);
#   - se o onode morrer, o cliente fica sem vídeo mas continua a pedir; quando o
#     onode volta, recebe o PEDIR seguinte e o vídeo regressa.

import socket
import time

from comum import config
from comum.log import log
from comum.mensagem import Mensagem
from servicos import fluxos


def svc_clientes(db):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((db.bind_ip, config.CLIENTE_PORT))
    sock.settimeout(1)                        # acorda pelo menos de 1 em 1 s para expirar clientes
    while db.a_correr:
        try:
            dados, (ip, porta) = sock.recvfrom(4096)
            msg = Mensagem.deserialize(dados.decode())
        except socket.timeout:
            msg = None
        except ValueError:
            continue
        with db.lock:
            if msg and msg.tipo == Mensagem.PEDIR:
                resposta = handle_pedir(db, ip, msg)
                sock.sendto(resposta.serialize(), (ip, porta))
            elif msg and msg.tipo == Mensagem.PARAR:
                handle_parar(db, ip)
            expirar_clientes(db)


def handle_pedir(db, ip, msg):
    stream = msg.dados["stream"]
    cliente = db.clientes.get(ip)
    if cliente is None or cliente["stream"] != stream:
        log(f"Cliente {ip} pediu '{stream}'")
        db.clientes[ip] = cliente = {"stream": stream, "servidor": None}
    cliente["instante"] = time.time()
    fluxos.atualizar(db)                      # escolhe o servidor e ativa o fluxo, se preciso
    estado = "a enviar" if cliente["servidor"] else "nenhum servidor tem esta stream (ainda)"
    return Mensagem(Mensagem.PEDIR_RESP, db.meu_ip, {"stream": stream, "estado": estado})


def handle_parar(db, ip):
    if db.clientes.pop(ip, None):
        log(f"Cliente {ip} parou")
        fluxos.atualizar(db)


def expirar_clientes(db):
    agora = time.time()
    for ip in [ip for ip, c in db.clientes.items() if agora - c["instante"] > config.CLIENTE_TIMEOUT]:
        del db.clientes[ip]
        log(f"Cliente {ip} deixou de pedir: esquecido")
        fluxos.atualizar(db)
