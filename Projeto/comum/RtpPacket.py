# Pacote RTP (Real-time Transport Protocol, RFC 3550), baseado no exemplo do Kurose.
#
# O RTP não garante entrega; só acrescenta a cada pedaço de media a informação de
# que o recetor precisa para o reproduzir: ordem (nº de sequência), instante
# (timestamp), formato (payload type) e de que fonte vem (SSRC).
#
# Cabeçalho fixo de 12 bytes:
#
#   byte 0      byte 1      bytes 2-3        bytes 4-7       bytes 8-11
#  +-----------+-----------+----------------+---------------+---------------+
#  |V V P X C C C C|M P P P P P P P| nº de sequência | timestamp     | SSRC          |
#  +-----------+-----------+----------------+---------------+---------------+
#  | payload (aqui: uma frame JPEG) ...
#
#  V    (2 bits)  versão do RTP; é sempre 2
#  P    (1 bit)   padding: 1 se houver bytes de enchimento no fim (não usamos -> 0)
#  X    (1 bit)   extension: 1 se houver um cabeçalho de extensão (não usamos -> 0)
#  CC   (4 bits)  nº de fontes contribuintes (CSRC), usado por misturadores (-> 0)
#  M    (1 bit)   marker: marca um evento, p.ex. fim de uma frame (não usamos -> 0)
#  PT   (7 bits)  payload type: formato dos dados; 26 = JPEG
#  seq  (16 bits) nº de sequência: +1 por pacote; o recetor deteta perdas e
#                 pacotes fora de ordem
#  timestamp (32 bits) instante de amostragem da frame, num relógio de 90 kHz
#                 (padrão para vídeo): frame n -> n * 90000 / fps
#  SSRC (32 bits) identificador da fonte; se mudar, o recetor sabe que a stream
#                 passou a vir de outro servidor

HEADER_SIZE = 12
PT_JPEG = 26


class RtpPacket:

    def encode(self, version, padding, extension, cc, seqnum, marker, pt, ssrc, timestamp, payload):
        """Constrói o cabeçalho byte a byte (operações de bits) e junta o payload."""
        header = bytearray(HEADER_SIZE)
        # byte 0: V(2) P(1) X(1) CC(4)
        header[0] = (version << 6) | (padding << 5) | (extension << 4) | (cc & 0x0F)
        # byte 1: M(1) PT(7)
        header[1] = (marker << 7) | (pt & 0x7F)
        # bytes 2-3: nº de sequência (16 bits, primeiro o byte mais significativo)
        header[2] = (seqnum >> 8) & 0xFF
        header[3] = seqnum & 0xFF
        # bytes 4-7: timestamp (32 bits)
        header[4] = (timestamp >> 24) & 0xFF
        header[5] = (timestamp >> 16) & 0xFF
        header[6] = (timestamp >> 8) & 0xFF
        header[7] = timestamp & 0xFF
        # bytes 8-11: SSRC (32 bits)
        header[8] = (ssrc >> 24) & 0xFF
        header[9] = (ssrc >> 16) & 0xFF
        header[10] = (ssrc >> 8) & 0xFF
        header[11] = ssrc & 0xFF
        self.header = header
        self.payload = payload

    def decode(self, byte_stream):
        """Separa os 12 bytes de cabeçalho do payload."""
        self.header = bytearray(byte_stream[:HEADER_SIZE])
        self.payload = byte_stream[HEADER_SIZE:]

    def version(self):
        return self.header[0] >> 6

    def seqNum(self):
        return (self.header[2] << 8) | self.header[3]

    def timestamp(self):
        return (self.header[4] << 24) | (self.header[5] << 16) | (self.header[6] << 8) | self.header[7]

    def payloadType(self):
        return self.header[1] & 0x7F

    def ssrc(self):
        return (self.header[8] << 24) | (self.header[9] << 16) | (self.header[10] << 8) | self.header[11]

    def getPayload(self):
        return self.payload

    def getPacket(self):
        return bytes(self.header) + self.payload
