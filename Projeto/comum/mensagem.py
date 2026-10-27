# Mensagens de controlo trocadas por TCP.
#
# Cada mensagem é um objeto JSON numa linha de texto:
#     {"tipo": "ALIVE", "origem": "10.0.17.20", "dados": {...}}
# O formato de cada tipo está descrito em message_types.md.

import json


class Mensagem:
    # Bootstrapper
    REGISTO = "REGISTO"          # nó -> bootstrapper: "quem são os meus vizinhos?"
    BOAS_VINDAS = "BOAS_VINDAS"  # bootstrapper -> nó: o seu nome e a lista de vizinhos
    ERRO = "ERRO"
    # Vizinhos
    OLA = "OLA"                  # primeira mensagem numa ligação nova entre vizinhos
    ALIVE = "ALIVE"              # "estou vivo"; serve também para medir o RTT
    ALIVE_RESP = "ALIVE_RESP"    # resposta ao ALIVE
    ADEUS = "ADEUS"              # o nó vai sair do overlay
    # Rotas e fluxos
    ANUNCIO = "ANUNCIO"          # servidor anuncia-se; inunda o overlay
    ATIVAR = "ATIVAR"            # "envia-me o fluxo (servidor, stream)"
    DESATIVAR = "DESATIVAR"      # "já não preciso do fluxo" (poda)
    PING = "PING"                # teste do caminho (Etapa 3)

    def __init__(self, tipo, origem="", dados=None):
        self.tipo = tipo
        self.origem = origem     # IP de quem enviou
        self.dados = dados if dados is not None else {}

    def serialize(self):
        texto = json.dumps({"tipo": self.tipo, "origem": self.origem, "dados": self.dados})
        return (texto + "\n").encode()

    @staticmethod
    def deserialize(linha):
        d = json.loads(linha)
        return Mensagem(d["tipo"], d.get("origem", ""), d.get("dados", {}))

    def __str__(self):
        return f"{self.tipo} de {self.origem}: {self.dados}"


class LeitorMensagens:
    """Lê mensagens de um socket TCP, uma por linha.

    O TCP entrega um fluxo de bytes sem fronteiras: uma leitura pode trazer meia
    mensagem ou várias. Por isso guardamos os bytes num buffer até haver um '\\n'.
    """

    def __init__(self, sock):
        self.sock = sock
        self.buffer = b""

    def ler(self):
        """Devolve a próxima Mensagem, ou None se a ligação fechou."""
        while b"\n" not in self.buffer:
            bytes_lidos = self.sock.recv(4096)
            if not bytes_lidos:
                return None
            self.buffer += bytes_lidos
        linha, self.buffer = self.buffer.split(b"\n", 1)
        return Mensagem.deserialize(linha.decode())
