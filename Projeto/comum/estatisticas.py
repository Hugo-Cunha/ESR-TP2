# Estatísticas de receção no cliente (impressas no terminal de 2 em 2 s).
# O cliente só recebe pacotes RTP: tudo sai dos campos do RTP.
#
#   perdas : buracos no nº de sequência RTP (ex.: chega 10 e depois 12 -> perdeu-se 1)
#   jitter : variação do tempo entre chegadas face ao timestamp RTP (RFC 3550, 6.4.1)
#   trocas : quantas vezes mudou o SSRC (a stream passou a vir de outra fonte);
#            o cliente não sabe qual é o servidor, só que a fonte mudou
#   maior falha : maior intervalo sem receber nada (mede quanto demora a recuperar)

import time

RELOGIO_RTP = 90000                           # Hz (timestamp RTP de vídeo)


class Estatisticas:
    def __init__(self):
        self.recebidos = 0
        self.perdidos = 0
        self.ultimo_seq = None
        self.ssrc = None
        self.trocas_fonte = 0
        self.jitter = 0.0
        self.transito_anterior = None
        self.ultima_chegada = None
        self.maior_falha = 0.0
        self.chegadas = []                   # para calcular os fps

    def registar(self, rtp):
        agora = time.time()
        if self.ssrc is not None and rtp.ssrc() != self.ssrc:
            self.trocas_fonte += 1            # a stream passou a vir de outra fonte
            self.ultimo_seq, self.transito_anterior = None, None
        self.ssrc = rtp.ssrc()
        if self.ultimo_seq is not None:
            salto_seq = (rtp.seqNum() - self.ultimo_seq) % 65536
            if salto_seq == 0 or salto_seq > 30000:
                return False                  # duplicado ou atrasado: ignora
            self.perdidos += salto_seq - 1
        self.ultimo_seq = rtp.seqNum()
        if self.ultima_chegada is not None:
            self.maior_falha = max(self.maior_falha, agora - self.ultima_chegada)
        self.ultima_chegada = agora

        # jitter (RFC 3550): D = diferença entre os "tempos de trânsito" relativos
        transito = agora * 1000 - rtp.timestamp() * 1000 / RELOGIO_RTP
        if self.transito_anterior is not None:
            d = abs(transito - self.transito_anterior)
            if d < 1000:                      # ignora saltos de timestamp (ex.: o vídeo recomeçou)
                self.jitter += (d - self.jitter) / 16
        self.transito_anterior = transito
        self.recebidos += 1
        self.chegadas = [t for t in self.chegadas if agora - t < 2] + [agora]
        return True

    def resumo(self):
        agora = time.time()
        fps = len([t for t in self.chegadas if agora - t < 2]) / 2   # frames nos últimos 2 s
        total = self.recebidos + self.perdidos
        perdas_pct = 100 * self.perdidos / total if total else 0
        fonte = f"{self.ssrc:08x}" if self.ssrc is not None else "-"
        return (f"fonte={fonte} frames={self.recebidos} perdas={self.perdidos} ({perdas_pct:.1f}%) "
                f"fps={fps:.1f} jitter={self.jitter:.2f}ms "
                f"trocas={self.trocas_fonte} maior_falha={self.maior_falha * 1000:.0f}ms")
