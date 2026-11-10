# REPARAÇÃO DO OVERLAY em falhas duplas (extra acordado com o docente).
#
# Exemplo:            O2
#            C — O1 <    > O4 — S        fluxo: S -> O4 -> (O2 ou O3) -> O1 -> C
#                     O3
# O1 só conhece os seus vizinhos (O2 e O3). Ninguém lhe diz mais nada enquanto
# não houver perigo.
#
#   1. PERIGO. Morre O2. O1 continua a receber por O3, mas para esse servidor já
#      só lhe resta UM vizinho com caminho (O3), e há um fluxo ativo. Então, e
#      só então, O1 envia ENDANGERED ao O3: "qual é o teu próximo salto?".
#   2. O3 responde ENDANGERED_RESP apenas com o IP da sua Origem (O4). O1 guarda
#      esse IP como RESERVA. Não fica a saber mais nada (nem caminho, nem
#      topologia, nem os outros vizinhos do O3).
#   3. FALHA DUPLA. Se O3 também morrer e O1 ficar sem caminho para o servidor
#      durante REPARAR_ESPERA segundos, O1 abre uma ligação de RECURSO ao O4.
#      Funciona como as outras (ANUNCIO, ATIVAR, vídeo), mas conta mais
#      PESO_RECURSO saltos: só é usada quando não há outro caminho.
#   4. Quando O2 ou O3 volta, o caminho por ele fica mais curto e passa a ser o
#      usado; a ligação de recurso fica livre e quem a abriu fecha-a (ADEUS).
#
# Limitação: se O2 e O3 morrerem ao mesmo tempo (antes da resposta ao
# ENDANGERED), O1 não tem reserva e fica à espera que um deles volte.

import threading
import time

from comum import config
from comum.log import log
from comum.mensagem import Mensagem
from database import Vizinho
from servicos import vizinhos


##################################################################################
#* 1-2. Perigo: só resta um vizinho com caminho -> ENDANGERED

def vizinhos_com_caminho(db, rota):
    return [ip for ip in rota.candidatos
            if ip in db.vizinhos and db.vizinhos[ip].ligado() and not db.vizinhos[ip].recurso]


def tem_fluxo_ativo(db, servidor):
    return any(f.servidor == servidor and f.preciso() for f in db.fluxos.values())


def vizinho_caiu(db, ip_morto):
    """Chamado quando um vizinho cai. Para cada servidor de que temos um fluxo
    ativo: se agora só nos resta UM vizinho com caminho, pedimos-lhe o próximo salto."""
    for rota in db.rotas.values():
        if not tem_fluxo_ativo(db, rota.servidor):
            continue
        restantes = vizinhos_com_caminho(db, rota)
        if len(restantes) != 1 or restantes[0] == rota.servidor:
            continue                          # ainda há alternativa, ou o que resta é o próprio servidor
        sobrevivente = restantes[0]
        if db.em_perigo.get(rota.servidor) == sobrevivente:
            continue                          # já perguntámos
        db.em_perigo[rota.servidor] = sobrevivente
        log(f"Em perigo para {rota.nome_servidor}: {db.nome_de(ip_morto)} caiu e só resta "
            f"{db.nome_de(sobrevivente)}; a pedir-lhe o próximo salto (ENDANGERED)")
        vizinhos.enviar(db, sobrevivente, Mensagem(Mensagem.ENDANGERED, dados={"servidor": rota.servidor}))


def handle_endangered(db, ip, msg):
    """Um vizinho só tem o nosso caminho: dizemos-lhe APENAS a nossa Origem."""
    rota = db.rotas.get(msg.dados["servidor"])
    if rota is None or rota.origem is None or rota.origem == ip:
        return                                # não podemos ajudar
    log(f"{db.nome_de(ip)} está em perigo: a dar-lhe o meu próximo salto ({db.nome_de(rota.origem)})")
    vizinhos.enviar(db, ip, Mensagem(Mensagem.ENDANGERED_RESP, dados={
        "servidor": rota.servidor, "ip": rota.origem, "nome": db.nome_de(rota.origem)}))


def handle_endangered_resp(db, ip, msg):
    d = msg.dados
    if d["ip"] == db.meu_ip:
        return
    db.reservas[d["servidor"]] = {"ip": d["ip"], "nome": d["nome"], "via": ip, "sem_caminho_desde": None}
    log(f"Reserva: se {db.nome_de(ip)} cair, ligo-me a {d['nome']} ({d['ip']})")


##################################################################################
#* 3-4. Falha dupla: abrir (e depois fechar) a ligação de recurso

def svc_reparar_overlay(db):
    """De 1 em 1 s, só localmente (não envia nada a não ser numa falha dupla)."""
    while db.a_correr:
        time.sleep(1)
        with db.lock:
            verificar_reservas(db)
            fechar_recursos_livres(db)


def verificar_reservas(db):
    agora = time.time()
    for servidor in list(db.reservas):
        reserva = db.reservas[servidor]
        rota = db.rotas.get(servidor)
        if rota is not None and len(vizinhos_com_caminho(db, rota)) >= 2:
            del db.reservas[servidor]         # o perigo passou (um vizinho voltou)
            db.em_perigo.pop(servidor, None)
            continue
        via = db.vizinhos.get(reserva["via"])
        sem_caminho = rota is None or rota.origem is None
        if not (sem_caminho and (via is None or not via.ligado())):
            reserva["sem_caminho_desde"] = None
            continue
        if reserva["sem_caminho_desde"] is None:
            reserva["sem_caminho_desde"] = agora
            continue
        if agora - reserva["sem_caminho_desde"] < config.REPARAR_ESPERA:
            continue
        abrir_recurso(db, reserva, agora)


def abrir_recurso(db, reserva, agora):
    ip, nome = reserva["ip"], reserva["nome"]
    if ip in db.vizinhos or agora - db.recurso_tentado.get(ip, 0) < 5:
        return                                # já é vizinho, ou tentámos há pouco
    db.recurso_tentado[ip] = agora
    log(f"Falha dupla: sem caminho e {db.nome_de(reserva['via'])} em baixo; "
        f"a abrir ligação de recurso a {nome} ({ip})")
    v = db.vizinhos[ip] = Vizinho(ip, nome)
    v.recurso = v.recurso_meu = True
    threading.Thread(target=vizinhos._ligar, args=(db, ip, True), daemon=True).start()


def em_uso(db, ip):
    """A ligação é precisa se for a Origem de alguma rota ou levar algum fluxo."""
    if any(rota.origem == ip for rota in db.rotas.values()):
        return True
    return any(f.pedido_a == ip or ip in f.destinos for f in db.fluxos.values())


def fechar_recursos_livres(db):
    agora = time.time()
    for v in list(db.vizinhos.values()):
        if not (v.recurso_meu and v.ligado()):
            continue
        if em_uso(db, v.ip):
            v.livre_desde = None
        elif v.livre_desde is None:
            v.livre_desde = agora
        elif agora - v.livre_desde >= config.REPARAR_ESPERA:
            log(f"Ligação de recurso a {v.nome} já não é precisa: a fechar")
            vizinhos.enviar(db, v.ip, Mensagem(Mensagem.ADEUS))
            vizinhos.vizinho_em_baixo(db, v.ip, v.sock, "ligação de recurso fechada")
