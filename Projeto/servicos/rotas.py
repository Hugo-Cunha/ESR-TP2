# Serviços de ROTAS: anúncios dos servidores e escolha da Origem.
#
# Modelo (vetor de distâncias com números de sequência, à semelhança do DSDV e
# do Babel):
#   1. Cada servidor envia ANUNCIO aos vizinhos a cada HEARTBEAT (5 s), com um
#      nº de sequência crescente (seq = hora em ms) e custo 0.
#   2. Quem recebe guarda um CANDIDATO por vizinho, com o custo total
#      (custo anunciado + custo da ligação até esse vizinho), e reenvia o
#      anúncio aos outros vizinhos com o SEU custo (inundação controlada).
#   3. A ORIGEM para cada servidor é o candidato VIÁVEL de menor custo. As
#      Origens formam uma árvore de caminhos mais curtos com raiz no servidor.
#
# O nó NÃO conhece o caminho até ao servidor: só sabe por que vizinho ir e com
# que custo. Os ciclos são evitados por três mecanismos:
#   - split horizon: não se anuncia uma rota ao vizinho que é a Origem dela;
#   - condição de viabilidade: um vizinho só pode ser Origem se trouxer um
#     anúncio mais recente, ou se o custo que anuncia for MENOR do que o melhor
#     custo que este nó já teve (logo, não pode estar a passar por nós);
#   - route poisoning: quem fica sem rota anuncia logo custo infinito (null),
#     para que os nós a jusante não esperem pelo fim do timeout;
#   - pedido de nº de sequência (como no Babel): quem fica sem candidato viável
#     pede ao servidor um anúncio novo (PEDIDO_SEQ), para não esperar pelo
#     próximo heartbeat. Só acontece em falhas.

import ipaddress
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
            anunciar(db)
        time.sleep(config.ANUNCIO_INTERVALO)


def anunciar(db, so_para=None):
    """Anúncio do servidor. Uma ronda nova (seq novo) vai sempre a TODOS os
    vizinhos; a um vizinho que acabou de ligar repete-se a ronda atual (mesmo
    seq). Se só um vizinho recebesse um seq novo, os outros veriam esse seq
    chegar primeiro por caminhos indiretos e aceitá-los-iam como mais recentes
    do que a rota direta, o que estragava a condição de viabilidade."""
    if so_para and db.seq_anuncio:
        seq = db.seq_anuncio
    else:
        seq = db.seq_anuncio = int(time.time() * 1000)   # cresce sempre, mesmo se o servidor reiniciar
        so_para = None
    msg = Mensagem(Mensagem.ANUNCIO, dados={
        "servidor": db.meu_ip, "nome": db.meu_nome,
        "streams": sorted(db.streams_locais),
        "seq": seq, "custo": 0, "saltos": 0,
    })
    if so_para:
        vizinhos.enviar(db, so_para, msg)
    else:
        vizinhos.enviar_a_todos(db, msg)


def handle_pedido_seq(db, ip_vizinho, msg):
    """Alguém ficou sem rota viável para um servidor. Se somos o servidor,
    anunciamo-nos já; senão passamos o pedido à nossa Origem (no máximo 1 vez
    por segundo por servidor, para nunca se multiplicar)."""
    servidor = msg.dados["servidor"]
    agora = time.time()
    if agora - db.ultimo_pedido_seq.get(servidor, 0) < config.PEDIDO_SEQ_INTERVALO:
        return
    db.ultimo_pedido_seq[servidor] = agora
    if servidor == db.meu_ip:
        log(f"{db.nome_de(ip_vizinho)} pediu um anúncio novo: a anunciar já")
        anunciar(db)
        return
    rota = db.rotas.get(servidor)
    if rota and rota.origem and rota.origem != ip_vizinho:
        vizinhos.enviar(db, rota.origem, msg)


def pedir_seq(db, rota):
    """Fiquei sem candidato viável, mas há vizinhos que ainda chegam ao servidor:
    peço-lhes que façam chegar ao servidor um pedido de anúncio novo."""
    agora = time.time()
    if not rota.candidatos or agora - db.ultimo_pedido_seq.get(rota.servidor, 0) < config.PEDIDO_SEQ_INTERVALO:
        return
    db.ultimo_pedido_seq[rota.servidor] = agora
    for ip in rota.candidatos:
        vizinhos.enviar(db, ip, Mensagem(Mensagem.PEDIDO_SEQ, dados={"servidor": rota.servidor}))


##################################################################################
#* Receção de um ANUNCIO

def handle_anuncio(db, ip_vizinho, msg):
    d = msg.dados
    if d["servidor"] == db.meu_ip:
        return
    rota = db.rotas.get(d["servidor"])
    if rota is None:
        if d["custo"] is None:
            return                            # retirada de uma rota que nunca conhecemos
        rota = db.rotas[d["servidor"]] = Rota(d["servidor"], d["nome"])
        log(f"Descoberto o servidor {d['nome']} com as streams {d['streams']}")

    if d["custo"] is None:                    # route poisoning: o vizinho perdeu a rota
        if rota.candidatos.pop(ip_vizinho, None):
            log(f"{db.nome_de(ip_vizinho)} retirou a rota para {rota.nome_servidor} (custo infinito)")
            escolher_origem(db, rota)
            fluxos.atualizar(db)
        return

    rota.streams = d["streams"]
    rota.sem_caminho_desde = None
    custo = d["custo"] + vizinhos.custo_ligacao(db, ip_vizinho, rota.servidor)
    rota.candidatos[ip_vizinho] = Candidato(custo, d["custo"], d["saltos"] + 1, d["seq"])

    escolher_origem(db, rota)
    reenviar_anuncio(db, rota, d["seq"])
    fluxos.atualizar(db)


##################################################################################
#* Escolha da Origem

def viavel(rota, c):
    """Condição de viabilidade (Babel, RFC 8966; EIGRP).

    Um candidato é aceitável se trouxer um nº de sequência mais recente do que o
    que conhecemos, ou, com o mesmo nº de sequência, se o vizinho anunciar um
    custo estritamente menor do que o melhor custo que já tivemos. Um vizinho
    que chegue ao servidor através de nós anuncia sempre um custo maior do que o
    nosso, por isso nunca é viável: assim não se formam ciclos mesmo sem
    conhecer o caminho."""
    if c.seq > rota.seq_viavel:
        return True
    return c.seq == rota.seq_viavel and (rota.custo_viavel is None or c.anunciado < rota.custo_viavel)


def escolher_origem(db, rota):
    # 1) deita fora candidatos de vizinhos desligados ou sem anúncios recentes
    agora = time.time()
    for ip in list(rota.candidatos):
        v = db.vizinhos.get(ip)
        if v is None or not v.ligado() or agora - rota.candidatos[ip].instante > config.ROTA_TIMEOUT:
            del rota.candidatos[ip]

    # 2) entre os viáveis, o de menor custo (empate: menos saltos; depois menor IP)
    viaveis = {ip: c for ip, c in rota.candidatos.items() if viavel(rota, c)}
    if not viaveis:
        if rota.origem is not None:
            log(f"Rota para {rota.nome_servidor} perdida: a anunciar custo infinito aos vizinhos")
            envenenar(db, rota)
        rota.origem, rota.custo, rota.saltos = None, None, None
        if rota.sem_caminho_desde is None:
            rota.sem_caminho_desde = agora
        pedir_seq(db, rota)
        return

    def chave(ip):
        return (viaveis[ip].custo, viaveis[ip].saltos, ipaddress.ip_address(ip))
    melhor_ip = min(viaveis, key=chave)
    melhor = viaveis[melhor_ip]
    if melhor_ip != rota.origem:
        log(f"Rota para {rota.nome_servidor}: Origem {db.nome_de(rota.origem) if rota.origem else '-'}"
            f" -> {db.nome_de(melhor_ip)} (custo {melhor.custo}, {melhor.saltos} saltos)")
    rota.origem, rota.custo, rota.saltos = melhor_ip, melhor.custo, melhor.saltos

    # 3) atualiza a distância de viabilidade
    if melhor.seq > rota.seq_viavel:
        rota.seq_viavel, rota.custo_viavel = melhor.seq, melhor.custo
    else:
        rota.custo_viavel = min(rota.custo_viavel, melhor.custo)


def envenenar(db, rota):
    """Route poisoning: avisa todos os vizinhos de que já não chegamos ao servidor."""
    vizinhos.enviar_a_todos(db, Mensagem(Mensagem.ANUNCIO, dados={
        "servidor": rota.servidor, "nome": rota.nome_servidor, "streams": rota.streams,
        "seq": rota.seq_viavel, "custo": None, "saltos": None,
    }), exceto=[rota.servidor])
    rota.seq_reenviado, rota.custo_reenviado = rota.seq_viavel, None


##################################################################################
#* Reenvio do anúncio (inundação controlada com split horizon)

def reenviar_anuncio(db, rota, seq):
    if rota.origem is None:
        return
    novo = seq > rota.seq_reenviado
    melhorou = seq == rota.seq_reenviado and (rota.custo_reenviado is None or rota.custo < rota.custo_reenviado)
    if not (novo or melhorou):
        return
    rota.seq_reenviado, rota.custo_reenviado = seq, rota.custo
    # split horizon: não se anuncia a rota ao vizinho de quem ela vem; e nunca se
    # anuncia um servidor a ele próprio (seria uma mensagem inútil)
    vizinhos.enviar_a_todos(db, anuncio_da_rota(rota, seq), exceto=[rota.origem, rota.servidor])


def anuncio_da_rota(rota, seq):
    """O anúncio que reenviamos leva o NOSSO custo (e nada sobre o caminho)."""
    return Mensagem(Mensagem.ANUNCIO, dados={
        "servidor": rota.servidor, "nome": rota.nome_servidor, "streams": rota.streams,
        "seq": seq, "custo": rota.custo, "saltos": rota.saltos,
    })


def dar_a_conhecer_rotas(db, ip_novo_vizinho):
    """Quando um vizinho liga, envia-lhe logo as rotas que já conhecemos
    (assim não tem de esperar pelo próximo anúncio). Um servidor anuncia-se logo."""
    if db.streams_locais:
        anunciar(db, so_para=ip_novo_vizinho)
    for rota in db.rotas.values():
        if rota.origem is not None and ip_novo_vizinho not in (rota.origem, rota.servidor):
            vizinhos.enviar(db, ip_novo_vizinho, anuncio_da_rota(rota, rota.seq_reenviado))


##################################################################################
#* Manutenção

def esquecer_vizinho(db, ip):
    """Um vizinho caiu: deixa de ser candidato. Se era a Origem, escolhe-se outra
    (viável) ou, não havendo, envenena-se a rota."""
    for rota in db.rotas.values():
        if rota.candidatos.pop(ip, None) is not None or rota.origem == ip:
            escolher_origem(db, rota)


def svc_manter_rotas(db):
    """De 1 em 1 s (local, sem enviar nada): fecha a janela das perdas medidas,
    atualiza o custo dos candidatos com as medições mais recentes das ligações
    (assim uma ligação que piora é evitada sem esperar pelo próximo anúncio),
    expira caminhos antigos e apaga servidores que desapareceram."""
    while db.a_correr:
        time.sleep(1)
        with db.lock:
            for v in db.vizinhos.values():
                vizinhos.fechar_janela_perdas(v)
            for servidor in list(db.rotas):
                rota = db.rotas[servidor]
                for ip, c in rota.candidatos.items():
                    if ip in db.vizinhos:
                        c.custo = c.anunciado + vizinhos.custo_ligacao(db, ip, rota.servidor)
                escolher_origem(db, rota)
                if rota.sem_caminho_desde and time.time() - rota.sem_caminho_desde > config.ROTA_ESQUECER:
                    log(f"Servidor {rota.nome_servidor} removido da tabela")
                    del db.rotas[servidor]
            fluxos.atualizar(db)
