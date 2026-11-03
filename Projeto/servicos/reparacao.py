# REPARAÇÃO DO OVERLAY em falhas duplas (extra acordado com o docente).
#
# Exemplo:            O2
#            C — O1 <    > O4 — S
#                     O3
# Se só O2 (ou só O3) morrer, o encaminhamento já resolve: há alternativa.
# Se O2 E O3 morrerem, O1 fica sem caminho para o servidor, embora O1 e O4
# continuem alcançáveis no underlay. Nessa situação, O1 abre uma ligação de
# RECURSO diretamente a O4, que é vizinho dos vizinhos que morreram.
#
# Como O1 sabe que O4 existe: no OLA cada vizinho envia a lista dos SEUS
# vizinhos (um só nível; ninguém fica a conhecer a topologia nem as rotas).
#
# Regras:
#   1. Só se repara quando as três condições se juntam:
#        a) o nó está SEM CAMINHO PARA NENHUM SERVIDOR há REPARAR_ESPERA segundos
#           (enquanto houver uma alternativa, o encaminhamento resolve sozinho);
#        b) perdeu-o porque MORREU UM VIZINHO QUE LHE LEVAVA A ROTA (era a Origem);
#        c) esse vizinho NÃO É UM SERVIDOR (um servidor morto não se contorna).
#   2. Liga-se aos vizinhos desses vizinhos mortos que não sejam já seus
#      vizinhos. A ligação de recurso funciona como outra qualquer (ANUNCIO,
#      ATIVAR, vídeo), mas custa mais PESO_RECURSO: é sempre o último recurso.
#   3. Quando um vizinho original volta, o caminho por ele fica mais barato e
#      passa a ser o usado. A ligação de recurso fica livre e, ao fim de
#      REPARAR_ESPERA segundos sem ser precisa, quem a abriu fecha-a (ADEUS).

import threading
import time

from comum import config
from comum.log import log
from comum.mensagem import Mensagem
from database import Vizinho
from servicos import vizinhos


def svc_reparar_overlay(db):
    while db.a_correr:
        time.sleep(1)
        with db.lock:
            verificar_isolamento(db)
            fechar_recursos_livres(db)


##################################################################################
#* Abrir ligações de recurso

def vizinhos_mortos(db):
    """Onodes vizinhos que caíram quando nos levavam a rota (regras 1b e 1c)."""
    return [v for v in db.vizinhos.values() if not v.recurso and not v.ligado() and v.levava_rota]


def sem_caminho(db):
    return not any(rota.origem is not None for rota in db.rotas.values())


def isolado(db):
    return sem_caminho(db) and bool(vizinhos_mortos(db))


def verificar_isolamento(db):
    mortos = vizinhos_mortos(db)
    if not isolado(db):
        db.isolado_desde = None
        return
    agora = time.time()
    if db.isolado_desde is None:
        db.isolado_desde = agora
        return
    if agora - db.isolado_desde < config.REPARAR_ESPERA:
        return
    for ip, nome in candidatos(db, mortos).items():
        if agora - db.recurso_tentado.get(ip, 0) < 5:
            continue                          # tentado há pouco (pode estar morto também)
        db.recurso_tentado[ip] = agora
        log(f"Sem caminho para nenhum servidor (morreram: {', '.join(m.nome for m in mortos)}): "
            f"a abrir ligação de recurso a {nome} ({ip})")
        v = db.vizinhos[ip] = Vizinho(ip, nome)
        v.recurso = v.recurso_meu = True
        threading.Thread(target=vizinhos._ligar, args=(db, ip, True), daemon=True).start()


def candidatos(db, mortos):
    """Vizinhos dos vizinhos mortos que ainda não são nossos vizinhos."""
    resultado = {}
    for morto in mortos:
        for x in db.vizinhos_de.get(morto.ip, []):
            if x["ip"] != db.meu_ip and x["ip"] not in db.vizinhos:
                resultado[x["ip"]] = x["nome"]
    return resultado


##################################################################################
#* Fechar ligações de recurso que já não são precisas

def em_uso(db, ip):
    """A ligação é precisa se for a Origem de alguma rota ou levar algum fluxo."""
    if any(rota.origem == ip for rota in db.rotas.values()):
        return True
    return any(f.pedido_a == ip or ip in f.destinos for f in db.fluxos.values())


def fechar_recursos_livres(db):
    if not any(v.ligado() and not v.recurso for v in db.vizinhos.values()):
        return                                # continuamos isolados: mantém-se tudo
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
