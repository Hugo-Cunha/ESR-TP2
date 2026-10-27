# Estado de um nó do overlay. Aqui só há DADOS; a lógica está em servicos/.
#
# Todas as threads do nó partilham uma Database. Quem a lê ou altera deve
# fazê-lo dentro de "with db.lock:" para não haver corridas.

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
        self.rtts = []                  # últimas medições de RTT (ms)

    def ligado(self):
        return self.sock is not None


class Candidato:
    """Um caminho até um servidor, anunciado por um vizinho."""

    def __init__(self, custo, saltos, caminho, seq):
        self.custo = custo
        self.saltos = saltos
        self.caminho = caminho          # [[ip, nome], ...] do servidor até ao vizinho
        self.seq = seq
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
        self.caminho = []
        self.seq_reenviado = 0          # último anúncio reenviado (inundação controlada)
        self.custo_reenviado = None
        self.sem_caminho_desde = None


class Fluxo:
    """Um fluxo (servidor, stream) que passa por este nó."""

    def __init__(self, servidor, stream):
        self.servidor = servidor
        self.stream = stream
        self.destinos = {}              # ip do vizinho -> instante do último ATIVAR
        self.local = False              # True se o cliente deste nó o está a ver
        self.pedido_a = None            # vizinho a quem pedimos o fluxo (a Origem)
        self.ultimo_ativar = 0.0

    def preciso(self):
        return self.local or len(self.destinos) > 0


class Database:

    def __init__(self, bootstrapper, meu_ip="0.0.0.0"):
        self.lock = threading.RLock()
        self.a_correr = True
        self.bootstrapper = bootstrapper
        self.bind_ip = meu_ip           # IP onde escutar (0.0.0.0 = todos)
        self.meu_ip = None              # dado pelo bootstrapper
        self.meu_nome = None
        self.vizinhos = {}              # ip -> Vizinho
        self.rotas = {}                 # ip do servidor -> Rota
        self.fluxos = {}                # (servidor, stream) -> Fluxo
        self.streams_locais = {}        # (servidor) nome da stream -> ficheiro
        self.stream_pedida = None       # (cliente) stream que o utilizador quer ver
        self.fluxo_local = None         # (cliente) chave do fluxo que está a ver
        self.entregar_local = None      # (cliente) função que recebe os pacotes
        self.sock_dados = None          # socket UDP de dados
        self.atrasos = {}               # (testes) ip -> atraso emulado em segundos

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
            linhas = [f"{'Vizinho':8} {'IP':15} {'Estado':10} {'RTT(ms)':>8}"]
            for v in sorted(self.vizinhos.values(), key=lambda v: v.nome):
                rtt = f"{sum(v.rtts) / len(v.rtts):.2f}" if v.rtts else "-"
                linhas.append(f"{v.nome:8} {v.ip:15} {'ligado' if v.ligado() else 'desligado':10} {rtt:>8}")
            return "\n".join(linhas)

    def tabela_rotas(self):
        """Tabela pedida no enunciado: Fluxo, Origem, Métrica, Destinos, Estado."""
        with self.lock:
            linhas = [f"{'Fluxo':14} {'Origem':7} {'Métrica':>7} {'Saltos':>6} {'Destinos':16} {'Estado':8} Alternativas"]
            for stream in sorted(self.streams_locais):
                f = self.fluxos.get((self.meu_ip, stream))
                linhas.append(f"{self.meu_nome + '/' + stream:14} {'(local)':7} {0:>7} {0:>6} "
                              f"{self._destinos(f):16} {'ativa' if f and f.destinos else 'inativa':8}")
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

    def _destinos(self, f):
        if f is None:
            return "-"
        nomes = [self.nome_de(ip) for ip in f.destinos]
        if f.local:
            nomes.append("local")
        return ",".join(nomes) or "-"
