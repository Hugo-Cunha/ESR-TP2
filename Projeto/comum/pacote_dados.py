# Pacote de dados do overlay (UDP): um pequeno cabeçalho nosso + o pacote RTP.
#
# Os nós intermédios precisam de saber a que fluxo pertence cada pacote para o
# reencaminharem, e um fluxo é o par (servidor, stream). O RTP não tem esses
# campos, por isso juntamos este cabeçalho à frente:
#
#   'O' 'T' | saltos (1 B) | seq_ligacao (4 B) | servidor IPv4 (4 B) | t_envio (8 B) | len (1 B) | stream | RTP...
#
#   saltos      : nº de nós por onde já passou (cada nó soma 1)
#   seq_ligacao : nº de sequência POR LIGAÇÃO: quem envia numera os pacotes que
#                 manda a cada vizinho; quem recebe conta os buracos e obtém as
#                 perdas dessa ligação (medição passiva, sem pacotes extra)
#   t_envio     : hora a que o servidor o enviou; o cliente calcula o atraso
#                 fim-a-fim (no CORE todos os nós partilham o relógio da máquina)

import socket
import struct

_FORMATO = struct.Struct("!2sBI4sdB")   # ! = ordem de rede; campos pela ordem acima


def criar(servidor_ip, stream, saltos, t_envio, rtp_bytes):
    nome = stream.encode()
    return _FORMATO.pack(b"OT", saltos, 0, socket.inet_aton(servidor_ip), t_envio, len(nome)) + nome + rtp_bytes


def ler(pacote):
    """Devolve (servidor, stream, saltos, seq_ligacao, t_envio, rtp_bytes), ou None se não for nosso."""
    if len(pacote) < _FORMATO.size or pacote[:2] != b"OT":
        return None
    _, saltos, seq, servidor, t_envio, n = _FORMATO.unpack_from(pacote)
    inicio = _FORMATO.size
    stream = pacote[inicio:inicio + n].decode()
    return socket.inet_ntoa(servidor), stream, saltos, seq, t_envio, pacote[inicio + n:]


def para_ligacao(pacote, seq_ligacao, mais_um_salto):
    """Cópia do pacote para enviar a um vizinho: põe o nº de sequência dessa
    ligação e, se for reencaminhado, soma 1 aos saltos."""
    saltos = min(pacote[2] + 1, 255) if mais_um_salto else pacote[2]
    return pacote[:2] + bytes([saltos]) + struct.pack("!I", seq_ligacao % 2**32) + pacote[7:]
