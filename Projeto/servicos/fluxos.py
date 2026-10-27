# Serviços de FLUXOS: ativação e poda dos ramos da árvore.
#
# Um fluxo é o par (servidor, stream). Quando um cliente quer ver uma stream:
#   - o seu nó envia ATIVAR à Origem para esse servidor;
#   - esse nó regista quem pediu como Destino e, se ainda não recebia o fluxo,
#     envia ATIVAR à sua própria Origem... até chegar ao servidor.
# Assim liga-se um ramo à árvore. Onde dois ramos se juntam passa só uma cópia.
#
# Quando um nó fica sem Destinos (e sem cliente local), envia DESATIVAR à Origem
# (poda). Os ATIVAR são repetidos de 2 em 2 s; um Destino que deixe de os enviar
# é removido ao fim de 6,5 s (assim nada fica pendurado se um nó morrer).

import time

from comum import config
from comum.log import log
from comum.mensagem import Mensagem
from servicos import vizinhos


##################################################################################
#* Receção de ATIVAR / DESATIVAR

def handle_ativar(db, ip, msg):
    servidor, stream = msg.dados["servidor"], msg.dados["stream"]
    if servidor == db.meu_ip and stream not in db.streams_locais:
        return                                # pediram-nos uma stream que não temos
    fluxo = db.obter_fluxo(servidor, stream)
    if ip not in fluxo.destinos:
        log(f"Fluxo {db.nome_fluxo(fluxo)}: novo destino {db.nome_de(ip)}")
    fluxo.destinos[ip] = time.time()
    atualizar(db)


def handle_desativar(db, ip, msg):
    fluxo = db.fluxos.get((msg.dados["servidor"], msg.dados["stream"]))
    if fluxo and fluxo.destinos.pop(ip, None) is not None:
        log(f"Fluxo {db.nome_fluxo(fluxo)}: destino {db.nome_de(ip)} removido (poda)")
        atualizar(db)


##################################################################################
#* Acertar os pedidos com as rotas atuais

def atualizar(db):
    """Chamada sempre que algo muda (rota, destino, vizinho). Para cada fluxo:
       - se é preciso e ainda não o pedimos à Origem atual -> ATIVAR (e DESATIVAR à antiga);
       - se já não é preciso -> DESATIVAR (poda) e esquecê-lo."""
    escolher_servidor(db)
    for chave in list(db.fluxos):
        fluxo = db.fluxos[chave]
        if fluxo.servidor == db.meu_ip:       # sou o servidor deste fluxo: não peço a ninguém
            if not fluxo.preciso():
                del db.fluxos[chave]
            continue

        rota = db.rotas.get(fluxo.servidor)
        origem = rota.origem if rota else None
        if fluxo.preciso() and fluxo.pedido_a != origem:
            if fluxo.pedido_a:
                _enviar(db, fluxo.pedido_a, Mensagem.DESATIVAR, fluxo)
            if origem:
                _enviar(db, origem, Mensagem.ATIVAR, fluxo)
                log(f"Fluxo {db.nome_fluxo(fluxo)} pedido a {db.nome_de(origem)}")
            fluxo.pedido_a = origem
        elif not fluxo.preciso():
            if fluxo.pedido_a:
                _enviar(db, fluxo.pedido_a, Mensagem.DESATIVAR, fluxo)
                log(f"Fluxo {db.nome_fluxo(fluxo)} sem destinos: poda enviada a {db.nome_de(fluxo.pedido_a)}")
            del db.fluxos[chave]


def _enviar(db, ip, tipo, fluxo):
    vizinhos.enviar(db, ip, Mensagem(tipo, dados={"servidor": fluxo.servidor, "stream": fluxo.stream}))
    if tipo == Mensagem.ATIVAR:
        fluxo.ultimo_ativar = time.time()


def esquecer_vizinho(db, ip):
    """Um vizinho caiu: deixa de ser destino e deixa de ser a quem pedimos fluxos."""
    for fluxo in db.fluxos.values():
        fluxo.destinos.pop(ip, None)
        if fluxo.pedido_a == ip:
            fluxo.pedido_a = None


##################################################################################
#* Serviço de manutenção (de 1 em 1 s)

def svc_manter_fluxos(db):
    while db.a_correr:
        time.sleep(1)
        with db.lock:
            agora = time.time()
            for fluxo in list(db.fluxos.values()):
                # destinos que deixaram de refrescar o pedido
                for ip, instante in list(fluxo.destinos.items()):
                    if agora - instante > config.DESTINO_TIMEOUT:
                        del fluxo.destinos[ip]
                        log(f"Fluxo {db.nome_fluxo(fluxo)}: destino {db.nome_de(ip)} expirou")
                # refrescar o nosso pedido (soft state)
                if fluxo.pedido_a and agora - fluxo.ultimo_ativar >= config.ATIVAR_INTERVALO:
                    _enviar(db, fluxo.pedido_a, Mensagem.ATIVAR, fluxo)
            atualizar(db)


##################################################################################
#* Cliente: pedir uma stream e escolher o servidor (extra: o mais próximo)

def pedir_stream(db, stream):
    with db.lock:
        db.stream_pedida = stream
        log(f"Cliente quer ver '{stream}'")
        atualizar(db)


def parar_stream(db):
    with db.lock:
        db.stream_pedida = None
        log("Cliente parou")
        atualizar(db)


def escolher_servidor(db):
    """Entre os servidores que têm a stream pedida, escolhe o de menor custo.
    Se esse servidor deixar de estar alcançável, passa automaticamente a outro."""
    melhor = None
    if db.stream_pedida:
        opcoes = [(rota.custo, rota.saltos, rota.servidor) for rota in db.rotas.values()
                  if rota.origem and db.stream_pedida in rota.streams]
        if opcoes:
            melhor = (min(opcoes)[2], db.stream_pedida)
    if melhor == db.fluxo_local:
        return
    if db.fluxo_local in db.fluxos:
        db.fluxos[db.fluxo_local].local = False
    if melhor:
        db.obter_fluxo(*melhor).local = True
        log(f"Cliente: '{melhor[1]}' a partir do servidor {db.rotas[melhor[0]].nome_servidor}")
    db.fluxo_local = melhor
