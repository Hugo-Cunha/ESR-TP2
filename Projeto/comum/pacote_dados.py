# Pacote de dados do overlay (UDP): um pequeno cabeçalho nosso + o pacote RTP.
#
# Os nós intermédios precisam de saber a que fluxo pertence cada pacote para o
# reencaminharem, e um fluxo é o par (servidor, stream). O RTP não tem esses
# campos, por isso juntamos este cabeçalho à frente:
#
#   'O' 'T' | saltos (1 byte) | servidor IPv4 (4 bytes) | t_envio (8 bytes) | len (1) | nome da stream | RTP...
#
#   saltos  : nº de nós por onde já passou (cada nó soma 1)
#   t_envio : hora a que o servidor o enviou; o cliente calcula o atraso fim-a-fim
#             (no CORE todos os nós partilham o relógio da máquina)

import socket
import struct

_FORMATO = struct.Struct("!2sB4sdB")   # ! = ordem de rede; 2s B 4s d B = campos acima


def criar(servidor_ip, stream, saltos, t_envio, rtp_bytes):
    nome = stream.encode()
    return _FORMATO.pack(b"OT", saltos, socket.inet_aton(servidor_ip), t_envio, len(nome)) + nome + rtp_bytes


def ler(pacote):
    """Devolve (servidor, stream, saltos, t_envio, rtp_bytes), ou None se não for nosso."""
    if len(pacote) < _FORMATO.size or pacote[:2] != b"OT":
        return None
    _, saltos, servidor, t_envio, n = _FORMATO.unpack_from(pacote)
    inicio = _FORMATO.size
    stream = pacote[inicio:inicio + n].decode()
    return socket.inet_ntoa(servidor), stream, saltos, t_envio, pacote[inicio + n:]


def mais_um_salto(pacote):
    """Cópia do pacote com o campo 'saltos' incrementado (byte nº 2)."""
    return pacote[:2] + bytes([min(pacote[2] + 1, 255)]) + pacote[3:]
