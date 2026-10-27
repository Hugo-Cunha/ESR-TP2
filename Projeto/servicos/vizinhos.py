# Serviços de VIZINHOS: registo no bootstrapper, ligações TCP com os vizinhos,
# ALIVE (deteção de falhas + RTT) e saída do overlay.
#
# Cada vizinho tem UMA ligação TCP persistente. Para não haver duas ligações
# entre o mesmo par de nós, só o nó com o IP menor é que inicia a ligação.
# O socket tem um timeout de VIZINHO_TIMEOUT: como os vizinhos trocam ALIVE a
# cada segundo, se o recv() ficar 3,5 s sem receber nada, o vizinho morreu.

import ipaddress
import socket
import threading
import time

from comum import config
from comum.log import log
from comum.mensagem import LeitorMensagens, Mensagem
from database import Vizinho
from servicos import dados, fluxos, rotas


##################################################################################
#* Registo no bootstrapper (só no arranque)

def registar_no_bootstrapper(db):
    """Pergunta ao bootstrapper quem somos e quem são os nossos vizinhos."""
    while True:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            if db.bind_ip != "0.0.0.0":
                s.bind((db.bind_ip, 0))       # (testes) sair com o IP certo
            s.settimeout(3)
            s.connect((db.bootstrapper, config.BOOTSTRAP_PORT))
            s.sendall(Mensagem(Mensagem.REGISTO).serialize())
            resposta = LeitorMensagens(s).ler()
            s.close()
            break
        except OSError as e:
            print(f"Bootstrapper {db.bootstrapper} indisponível ({e}); nova tentativa em 2 s")
            time.sleep(2)
    if resposta is None or resposta.tipo != Mensagem.BOAS_VINDAS:
        raise SystemExit(f"O bootstrapper recusou o registo: {resposta}")

    db.meu_ip = resposta.dados["ip"]
    db.meu_nome = resposta.dados["nome"]
    for v in resposta.dados["vizinhos"]:
        db.vizinhos[v["ip"]] = Vizinho(v["ip"], v["nome"])
    log(f"Registado como {db.meu_nome} ({db.meu_ip}); vizinhos: "
        + ", ".join(v.nome for v in db.vizinhos.values()))


##################################################################################
#* Envio de mensagens a um vizinho

def enviar(db, ip, msg):
    """Envia uma mensagem de controlo ao vizinho 'ip' (se estiver ligado)."""
    atraso = db.atrasos.get(ip)
    if atraso:                                # (testes) emula atraso na ligação
        threading.Timer(atraso, _enviar_agora, (db, ip, msg)).start()
    else:
        _enviar_agora(db, ip, msg)


def _enviar_agora(db, ip, msg):
    v = db.vizinhos.get(ip)
    if v is None or not v.ligado():
        return
    msg.origem = db.meu_ip
    try:
        with v.lock_envio:
            v.sock.sendall(msg.serialize())
    except OSError as e:
        vizinho_em_baixo(db, ip, v.sock, f"erro ao enviar ({e})")


def enviar_a_todos(db, msg, exceto=()):
    for v in db.vizinhos_ligados():
        if v.ip not in exceto:
            enviar(db, v.ip, msg)


##################################################################################
#* Serviço que aceita ligações de vizinhos

def svc_aceitar_ligacoes(db):
    servidor = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    servidor.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    servidor.bind((db.bind_ip, config.CONTROL_PORT))
    servidor.listen()
    while db.a_correr:
        sock, _ = servidor.accept()
        threading.Thread(target=cumprimentar, args=(db, sock, False), daemon=True).start()


##################################################################################
#* Serviço que liga aos vizinhos em falta (de 2 em 2 s)

def svc_ligar_vizinhos(db):
    while db.a_correr:
        for v in list(db.vizinhos.values()):
            if not v.ligado() and _sou_eu_a_ligar(db.meu_ip, v.ip):
                threading.Thread(target=_ligar, args=(db, v.ip), daemon=True).start()
        time.sleep(config.LIGAR_INTERVALO)


def _sou_eu_a_ligar(meu_ip, ip_vizinho):
    """Só o nó com o IP menor inicia a ligação (evita ligações duplicadas)."""
    return ipaddress.ip_address(meu_ip) < ipaddress.ip_address(ip_vizinho)


def _ligar(db, ip):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        if db.bind_ip != "0.0.0.0":
            sock.bind((db.bind_ip, 0))
        sock.settimeout(2)
        sock.connect((ip, config.CONTROL_PORT))
        cumprimentar(db, sock, True)
    except OSError:
        pass                                  # o vizinho ainda não está ativo; tenta-se depois


def cumprimentar(db, sock, fui_eu_a_ligar):
    """Troca de OLA entre os dois nós; depois a ligação fica registada no vizinho."""
    try:
        sock.settimeout(config.VIZINHO_TIMEOUT)
        # Desliga o algoritmo de Nagle: sem isto o TCP junta mensagens pequenas e
        # atrasa-as até ~40 ms, o que estragava as medições de RTT (e a métrica).
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        leitor = LeitorMensagens(sock)
        ola = Mensagem(Mensagem.OLA, db.meu_ip, {"nome": db.meu_nome})
        if fui_eu_a_ligar:
            sock.sendall(ola.serialize())
        resposta = leitor.ler()
        if resposta is None or resposta.tipo != Mensagem.OLA:
            sock.close()
            return
        if not fui_eu_a_ligar:
            sock.sendall(ola.serialize())
    except OSError:
        sock.close()
        return

    ip = resposta.origem
    with db.lock:
        v = db.vizinhos.setdefault(ip, Vizinho(ip, resposta.dados["nome"]))
        if v.ligado():                        # ligação antiga (ex.: o vizinho reiniciou)
            v.sock.close()
        v.sock, v.ligado_desde, v.rtts = sock, time.time(), []
        log(f"Vizinho {v.nome} ({ip}) ligado")
    threading.Thread(target=svc_ouvir_vizinho, args=(db, ip, sock, leitor), daemon=True).start()
    with db.lock:
        rotas.dar_a_conhecer_rotas(db, ip)    # o vizinho novo fica logo a saber das rotas
        fluxos.atualizar(db)


##################################################################################
#* Serviço que recebe as mensagens de um vizinho (uma thread por vizinho)

def svc_ouvir_vizinho(db, ip, sock, leitor):
    try:
        while True:
            msg = leitor.ler()
            if msg is None:
                raise OSError("ligação fechada")
            with db.lock:
                tratar_mensagem(db, ip, msg)
    except socket.timeout:
        vizinho_em_baixo(db, ip, sock, f"sem resposta há {config.VIZINHO_TIMEOUT} s")
    except (OSError, ValueError) as e:
        vizinho_em_baixo(db, ip, sock, str(e))


def tratar_mensagem(db, ip, msg):
    """Chama o handler certo para cada tipo de mensagem."""
    handlers = {
        Mensagem.ALIVE: handle_alive,
        Mensagem.ALIVE_RESP: handle_alive_resp,
        Mensagem.ADEUS: handle_adeus,
        Mensagem.ANUNCIO: rotas.handle_anuncio,
        Mensagem.ATIVAR: fluxos.handle_ativar,
        Mensagem.DESATIVAR: fluxos.handle_desativar,
        Mensagem.PING: dados.handle_ping,
    }
    handler = handlers.get(msg.tipo)
    if handler:
        handler(db, ip, msg)
    else:
        log(f"Mensagem desconhecida de {db.nome_de(ip)}: {msg}")


##################################################################################
#* Vizinho em baixo: limpa tudo o que dependia dele

def vizinho_em_baixo(db, ip, sock, motivo):
    with db.lock:
        v = db.vizinhos.get(ip)
        if v is None or v.sock is not sock:   # já tinha sido tratado (ou é uma ligação antiga)
            return
        v.sock.close()
        v.sock = None
        log(f"Vizinho {v.nome} ({ip}) em baixo: {motivo}")
        rotas.esquecer_vizinho(db, ip)
        fluxos.esquecer_vizinho(db, ip)
        fluxos.atualizar(db)


##################################################################################
#* ALIVE: de 1 em 1 s cada nó envia ALIVE aos vizinhos, que respondem com ALIVE_RESP.
#  Assim (1) as ligações nunca ficam caladas e (2) medimos o RTT de cada ligação.

def svc_alive(db):
    while db.a_correr:
        enviar_a_todos(db, Mensagem(Mensagem.ALIVE, dados={"t": time.time()}))
        time.sleep(config.ALIVE_INTERVALO)


def handle_alive(db, ip, msg):
    enviar(db, ip, Mensagem(Mensagem.ALIVE_RESP, dados=msg.dados))   # devolve o mesmo "t"


def handle_alive_resp(db, ip, msg):
    rtt_ms = (time.time() - msg.dados["t"]) * 1000
    v = db.vizinhos[ip]
    v.rtts = (v.rtts + [rtt_ms])[-3:]         # guarda as 3 últimas medições


def custo_ligacao(db, ip):
    """MÉTRICA de uma ligação = 1 (o salto) + 1 por cada 5 ms de atraso.

    atraso = RTT/2 (um sentido), média das 3 últimas medições. Exemplos:
      sem atraso configurado (RTT ~1 ms)  -> custo 1  (= contagem de saltos)
      ligação com 40 ms de atraso         -> custo 1 + 8 = 9
    Contar o atraso aos "degraus" de 5 ms faz com que variações pequenas do RTT
    (1-2 ms, normais quando o nó está ocupado) não façam as rotas oscilar.
    Até haver 3 medições (a 1.ª sai inflacionada no arranque) o custo é 1."""
    rtts = db.vizinhos[ip].rtts
    if len(rtts) < 3:
        return 1
    atraso_ms = sum(rtts) / len(rtts) / 2
    return 1 + round(atraso_ms / 5)


def handle_adeus(db, ip, msg):
    vizinho_em_baixo(db, ip, db.vizinhos[ip].sock, "saiu do overlay (ADEUS)")


def sair(db):
    """Saída ordeira: avisa os vizinhos para não terem de esperar pelo timeout."""
    enviar_a_todos(db, Mensagem(Mensagem.ADEUS))
    time.sleep(0.3)
    db.a_correr = False
