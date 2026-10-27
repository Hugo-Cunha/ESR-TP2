# Serviços de ROTAS: anúncios dos servidores e escolha da Origem.
#
# 1. Cada servidor envia um ANUNCIO aos vizinhos de 1 em 1 s (seq = hora em ms).
# 2. Quem recebe guarda o caminho como "candidato" (um por vizinho), soma o custo
#    da ligação por onde chegou e reenvia-o aos outros vizinhos (inundação).
# 3. A ORIGEM para cada servidor é o candidato com menor custo. As Origens de
#    todos os nós formam uma árvore de caminhos mais curtos com raiz no servidor.
#
# Inundação controlada: cada anúncio só é reenviado uma vez (ou de novo se
# chegar com um custo melhor) e nunca aos nós que já estão no nosso caminho até
# ao servidor (esses iriam descartá-lo). Reenvia-se mesmo a quem nos mandou a
# primeira cópia: esse vizinho pode precisar do NOSSO caminho para refrescar o dele.

import time

from comum import config
from comum.log import log
from comum.mensagem import Mensagem
from database import Candidato, Rota
from servicos import fluxos, vizinhos


##################################################################################
#* Serviço do servidor: anunciar-se periodicamente

def svc_anunciar(db):
    while db.a_correr:
        with db.lock:
            msg = Mensagem(Mensagem.ANUNCIO, dados={
                "servidor": db.meu_ip, "nome": db.meu_nome,
                "streams": sorted(db.streams_locais),
                "seq": int(time.time() * 1000),   # cresce sempre, mesmo se o servidor reiniciar
                "custo": 0, "saltos": 0,
                "caminho": [[db.meu_ip, db.meu_nome]],
            })
            vizinhos.enviar_a_todos(db, msg)
        time.sleep(config.ANUNCIO_INTERVALO)


##################################################################################
#* Receção de um ANUNCIO

def handle_anuncio(db, ip_vizinho, msg):
    d = msg.dados
    if d["servidor"] == db.meu_ip or caminho_tem_ciclo(db, d["caminho"]):
        return
    rota = db.rotas.get(d["servidor"])
    if rota is None:
        rota = db.rotas[d["servidor"]] = Rota(d["servidor"], d["nome"])
        log(f"Descoberto o servidor {d['nome']} com as streams {d['streams']}")
    rota.streams = d["streams"]
    rota.sem_caminho_desde = None

    custo = d["custo"] + vizinhos.custo_ligacao(db, ip_vizinho)
    rota.candidatos[ip_vizinho] = Candidato(custo, d["saltos"] + 1, d["caminho"], d["seq"])

    escolher_origem(db, rota)
    reenviar_anuncio(db, rota, d["seq"])
    fluxos.atualizar(db)


def caminho_tem_ciclo(db, caminho):
    """Se eu já estou no caminho, o anúncio deu a volta: descarta-se.
    (É para isto que o anúncio leva o caminho completo.)"""
    return any(ip == db.meu_ip for ip, _ in caminho)


##################################################################################
#* Escolha da Origem (melhor vizinho para chegar ao servidor)

def escolher_origem(db, rota):
    # deita fora candidatos de vizinhos desligados ou sem anúncios recentes
    agora = time.time()
    for ip in list(rota.candidatos):
        v = db.vizinhos.get(ip)
        if v is None or not v.ligado() or agora - rota.candidatos[ip].instante > config.ROTA_TIMEOUT:
            del rota.candidatos[ip]

    if not rota.candidatos:
        if rota.origem is not None:
            log(f"Rota para {rota.nome_servidor} perdida")
        rota.origem, rota.custo, rota.saltos, rota.caminho = None, None, None, []
        if rota.sem_caminho_desde is None:
            rota.sem_caminho_desde = agora
        return

    # menor custo; em empate, menos saltos; em empate, o vizinho com menor IP
    melhor_ip = min(rota.candidatos, key=lambda ip: (rota.candidatos[ip].custo,
                                                     rota.candidatos[ip].saltos, ip))
    melhor = rota.candidatos[melhor_ip]
    if melhor_ip != rota.origem:
        caminho = " > ".join(nome for _, nome in melhor.caminho)
        log(f"Rota para {rota.nome_servidor}: Origem {db.nome_de(rota.origem) if rota.origem else '-'}"
            f" -> {db.nome_de(melhor_ip)} (custo {melhor.custo}, caminho {caminho} > {db.meu_nome})")
    rota.origem, rota.custo, rota.saltos, rota.caminho = melhor_ip, melhor.custo, melhor.saltos, melhor.caminho


##################################################################################
#* Reenvio do anúncio aos outros vizinhos (inundação controlada)

def reenviar_anuncio(db, rota, seq):
    if rota.origem is None:
        return
    novo = seq > rota.seq_reenviado
    melhorou = seq == rota.seq_reenviado and rota.custo < rota.custo_reenviado
    if not (novo or melhorou):
        return
    rota.seq_reenviado, rota.custo_reenviado = seq, rota.custo
    vizinhos.enviar_a_todos(db, anuncio_da_rota(db, rota, seq),
                            exceto=[ip for ip, _ in rota.caminho])


def anuncio_da_rota(db, rota, seq):
    """O anúncio que reenviamos leva o NOSSO custo e o caminho com nós no fim."""
    return Mensagem(Mensagem.ANUNCIO, dados={
        "servidor": rota.servidor, "nome": rota.nome_servidor, "streams": rota.streams,
        "seq": seq, "custo": rota.custo, "saltos": rota.saltos,
        "caminho": rota.caminho + [[db.meu_ip, db.meu_nome]],
    })


def dar_a_conhecer_rotas(db, ip_novo_vizinho):
    """Quando um vizinho liga, envia-lhe logo as rotas que já conhecemos
    (assim não tem de esperar pelo próximo anúncio)."""
    for rota in db.rotas.values():
        if rota.origem is not None and rota.origem != ip_novo_vizinho:
            vizinhos.enviar(db, ip_novo_vizinho, anuncio_da_rota(db, rota, rota.seq_reenviado))


##################################################################################
#* Manutenção

def esquecer_vizinho(db, ip):
    """Um vizinho caiu: esquece os caminhos que ele anunciou ou que passavam por ele."""
    for rota in db.rotas.values():
        for ip_cand in list(rota.candidatos):
            caminho = rota.candidatos[ip_cand].caminho
            if ip_cand == ip or any(ip_no == ip for ip_no, _ in caminho):
                del rota.candidatos[ip_cand]
        escolher_origem(db, rota)


def svc_manter_rotas(db):
    """De 1 em 1 s: expira caminhos antigos e apaga servidores que desapareceram."""
    while db.a_correr:
        time.sleep(1)
        with db.lock:
            for servidor in list(db.rotas):
                rota = db.rotas[servidor]
                escolher_origem(db, rota)
                if rota.sem_caminho_desde and time.time() - rota.sem_caminho_desde > 15:
                    log(f"Servidor {rota.nome_servidor} removido da tabela")
                    del db.rotas[servidor]
            fluxos.atualizar(db)
