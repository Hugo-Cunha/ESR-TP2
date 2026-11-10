# Estado de um nó do overlay. Aqui só há DADOS; a lógica está em servicos/.
#
# Todas as threads do nó partilham uma Database. Quem a lê ou altera deve
# fazê-lo dentro de "with db.lock:" para não haver corridas.

import json
import threading
import time


class Vizinho:
    """Um vizinho indicado pelo bootstrapper e o estado da ligação TCP com ele."""

    def __init__(self, ip, nome):
        self.ip = ip
        self.nome = nome
        self.sock = None                # socket TCP; None = não estamos ligados
        self.lock_envio = threading.Lock()
        self.ligado_desde = None
        self.iniciada_pelo_menor = False # a ligação atual foi aberta pelo nó de IP menor
        self.rtts = []                  # 2 últimas medições de RTT (ms), pelo ALIVE
        self.n_rtts = 0                 # nº de medições feitas (a 1.ª é ignorada)
        self.tx_msgs = 0                # mensagens de controlo enviadas a este vizinho
        self.tx_bytes = 0
        # Perdas na ligação vizinho -> eu, medidas passivamente com o vídeo (só
        # informativas). Cada pacote traz um nº de sequência da ligação.
        self.seq_rx = None              # último nº de sequência recebido deste vizinho
        self.rx_recebidos = 0           # contadores da janela atual
        self.rx_perdidos = 0
        self.janela_inicio = time.time()
        self.perdas_pct = 0.0           # perdas (%) da última janela completa
        # Reparação do overlay (servicos/reparacao.py)
        self.recurso = False            # ligação de recurso (não vem do bootstrapper; é temporária)
        self.recurso_meu = False        # fui eu que a abri (e sou eu que a fecho)
        self.livre_desde = None         # (recurso) desde quando não é precisa

    def ligado(self):
        return self.sock is not None


class Candidato:
    """Um caminho até um servidor, anunciado por um vizinho.
    O nó não sabe por onde passa: só sabe o custo que o vizinho anunciou."""

    def __init__(self, custo, anunciado, saltos, seq):
        self.custo = custo              # custo do vizinho + custo da ligação até ele
        self.anunciado = anunciado      # custo que o próprio vizinho anunciou
        self.saltos = saltos
        self.seq = seq                  # nº de sequência do anúncio (dado pelo servidor)
        self.instante = time.time()


class Rota:
    """Entrada da tabela de rotas para um servidor."""

    def __init__(self, servidor, nome_servidor):
        self.servidor = servidor
        self.nome_servidor = nome_servidor
        self.streams = []
        self.candidatos = {}            # ip do vizinho -> Candidato
        self.origem = None              # vizinho escolhido para chegar ao servidor
        self.custo = None
        self.saltos = None
        self.seq_reenviado = 0          # último anúncio reenviado (inundação controlada)
        self.custo_reenviado = None
        # Condição de viabilidade (como no Babel/EIGRP): melhor custo que este nó
        # já teve para o nº de sequência mais recente que conhece.
        self.seq_viavel = 0
        self.custo_viavel = None
        self.sem_caminho_desde = None


class Fluxo:
    """Um fluxo (servidor, stream) que passa por este nó."""

    def __init__(self, servidor, stream):
        self.servidor = servidor
        self.stream = stream
        self.destinos = {}              # ip do vizinho -> instante do último ATIVAR
        self.clientes = set()           # IPs dos clientes ligados a este nó que veem este fluxo
        self.pedido_a = None            # vizinho a quem pedimos o fluxo (a Origem)
        self.ultimo_ativar = 0.0

    def preciso(self):
        return len(self.clientes) > 0 or len(self.destinos) > 0


class Database:

    def __init__(self, bootstrapper, meu_ip="0.0.0.0"):
        self.lock = threading.RLock()
        self.a_correr = True
        self.bootstrapper = bootstrapper
        self.bind_ip = meu_ip           # IP onde escutar (0.0.0.0 = todos)
        self.meu_ip = None              # dado pelo bootstrapper
        self.meu_nome = None
        self.vizinhos = {}              # ip -> Vizinho
        # Reparação (servicos/reparacao.py): servidor -> {"ip", "nome", "via", "sem_caminho_desde"}
        # = o próximo salto do único vizinho que nos resta (pedido com ENDANGERED)
        self.reservas = {}
        self.em_perigo = {}             # servidor -> vizinho a quem já enviámos ENDANGERED
        self.recurso_tentado = {}       # ip -> instante da última tentativa de ligação de recurso
        self.seq_anuncio = None         # (servidor) seq da ronda de anúncios atual
        self.ultimo_pedido_seq = {}     # servidor -> instante do último PEDIDO_SEQ (limite de ritmo)
        self.rotas = {}                 # ip do servidor -> Rota
        self.fluxos = {}                # (servidor, stream) -> Fluxo
        self.streams_locais = {}        # (servidor) nome da stream -> ficheiro
        self.clientes = {}              # IP do cliente -> {"stream", "servidor", "instante"}
        self.sock_dados = None          # socket UDP de dados
        self.atrasos = {}               # (testes) ip -> atraso emulado em segundos
        self.perdas_emuladas = {}       # (testes) ip -> % de pacotes de vídeo descartados
        self.seq_tx = {}                # ip do vizinho -> último nº de sequência enviado

    # ---------------------------------------------------------- vizinhos
    def vizinhos_ligados(self):
        return [v for v in self.vizinhos.values() if v.ligado()]

    def nome_de(self, ip):
        if ip == self.meu_ip:
            return self.meu_nome
        v = self.vizinhos.get(ip)
        return v.nome if v else ip

    # ------------------------------------------------------------ fluxos
    def obter_fluxo(self, servidor, stream):
        chave = (servidor, stream)
        if chave not in self.fluxos:
            self.fluxos[chave] = Fluxo(servidor, stream)
        return self.fluxos[chave]

    def nome_fluxo(self, fluxo):
        rota = self.rotas.get(fluxo.servidor)
        servidor = rota.nome_servidor if rota else self.nome_de(fluxo.servidor)
        return f"{servidor}/{fluxo.stream}"

    # ---------------------------------------------------------- tabelas
    def tabela_vizinhos(self):
        with self.lock:
            from servicos.vizinhos import componentes_custo
            linhas = [f"{'Vizinho':8} {'IP':15} {'Estado':10} {'RTT(ms)':>8} {'Perdas':>7} {'Fluxos':>6} "
                      f"Custo da ligação (1×salto + 2×atraso + 3×perdas + 1×carga)"]
            for v in sorted(self.vizinhos.values(), key=lambda v: v.nome):
                rtt = f"{sum(v.rtts) / len(v.rtts):.2f}" if v.rtts else "-"
                estado = ("recurso" if v.recurso else "ligado") if v.ligado() else "desligado"
                linha = f"{v.nome:8} {v.ip:15} {estado:10} {rtt:>8}"
                if v.ligado():
                    c = componentes_custo(self, v.ip)
                    linha += (f" {v.perdas_pct:6.1f}% {c['carga']:>6} "
                              f"{c['total']} = 1 + 2×{c['atraso']} + 3×{c['perdas']} + 1×{c['carga']}"
                              + (f" + {c['recurso']} (recurso)" if c['recurso'] else ""))
                linhas.append(linha)
            return "\n".join(linhas)

    def tabela_rotas(self):
        """Tabela pedida no enunciado: Fluxo, Origem, Métrica, Destinos, Estado."""
        with self.lock:
            linhas = [f"{'Fluxo':14} {'Origem':7} {'Métrica':>7} {'Saltos':>6} {'Destinos':16} {'Estado':8} Alternativas"]
            for stream in sorted(self.streams_locais):
                f = self.fluxos.get((self.meu_ip, stream))
                linhas.append(f"{self.meu_nome + '/' + stream:14} {'(local)':7} {0:>7} {0:>6} "
                              f"{self._destinos(f):16} {'ativa' if f and f.preciso() else 'inativa':8}")
            for rota in sorted(self.rotas.values(), key=lambda r: r.nome_servidor):
                alternativas = " ".join(f"{self.nome_de(ip)}({c.custo})" for ip, c in rota.candidatos.items()
                                        if ip != rota.origem)
                for stream in rota.streams:
                    f = self.fluxos.get((rota.servidor, stream))
                    estado = "ativa" if f and f.preciso() and f.pedido_a else "inativa"
                    if rota.origem is None:
                        estado = "sem rota"
                    linhas.append(f"{rota.nome_servidor + '/' + stream:14} {self.nome_de(rota.origem) if rota.origem else '-':7} "
                                  f"{rota.custo if rota.custo is not None else '-':>7} "
                                  f"{rota.saltos if rota.saltos is not None else '-':>6} "
                                  f"{self._destinos(f):16} {estado:8} {alternativas}")
            return "\n".join(linhas)

    def estado_json(self):
        """Estado local em JSON (comando 'estado'), para a ferramenta tools/arvore.py.
        Só tem o que o nó sabe: a sua Origem por servidor e os seus Destinos."""
        with self.lock:
            rotas = [{"servidor": r.nome_servidor, "origem": self.nome_de(r.origem) if r.origem else None,
                      "custo": r.custo, "saltos": r.saltos,
                      "alternativas": {self.nome_de(ip): c.custo for ip, c in r.candidatos.items()
                                       if ip != r.origem}}
                     for r in self.rotas.values()]
            fluxos = [{"fluxo": self.nome_fluxo(f), "destinos": sorted(self.nome_de(ip) for ip in f.destinos),
                       "clientes": sorted(f.clientes)}
                      for f in self.fluxos.values() if f.preciso()]
            controlo = {v.nome: {"msgs": v.tx_msgs, "bytes": v.tx_bytes,
                                 "video": self.seq_tx.get(v.ip, 0)} for v in self.vizinhos.values()}
            return json.dumps({"nome": self.meu_nome, "ip": self.meu_ip,
                               "servidor": bool(self.streams_locais), "rotas": rotas, "fluxos": fluxos,
                               "controlo_enviado": controlo})

    def _destinos(self, f):
        if f is None:
            return "-"
        nomes = [self.nome_de(ip) for ip in f.destinos]
        nomes += [f"cliente:{ip}" for ip in sorted(f.clientes)]
        return ",".join(nomes) or "-"
