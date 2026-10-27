# Estatísticas de receção no cliente (impressas no terminal de 2 em 2 s).
#
#   perdas : buracos no nº de sequência RTP (ex.: chega 10 e depois 12 -> perdeu-se 1)
#   atraso : hora de chegada - hora de envio (vem no cabeçalho do overlay)
#   jitter : variação do atraso entre pacotes seguidos (média móvel, como no RFC 3550)
#   maior falha : maior intervalo sem receber nada (mede quanto demora a recuperar)

import time


class Estatisticas:
    def __init__(self):
        self.recebidos = 0
        self.perdidos = 0
        self.ultimo_seq = None
        self.ssrc = None
        self.trocas_servidor = 0
        self.atraso = 0.0
        self.jitter = 0.0
        self.saltos = 0
        self.ultima_chegada = None
        self.maior_falha = 0.0
        self.chegadas = []                   # para calcular os fps

    def registar(self, rtp, saltos, t_envio):
        agora = time.time()
        if self.ssrc is not None and rtp.ssrc() != self.ssrc:
            self.trocas_servidor += 1         # a stream passou a vir de outro servidor
            self.ultimo_seq = None
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

        atraso = (agora - t_envio) * 1000
        if self.recebidos > 0:
            self.jitter += (abs(atraso - self.atraso) - self.jitter) / 16
        self.atraso = atraso
        self.recebidos += 1
        self.saltos = saltos
        self.chegadas = [t for t in self.chegadas if agora - t < 2] + [agora]
        return True

    def resumo(self):
        agora = time.time()
        fps = len([t for t in self.chegadas if agora - t < 2]) / 2   # frames nos últimos 2 s
        total = self.recebidos + self.perdidos
        perdas_pct = 100 * self.perdidos / total if total else 0
        return (f"frames={self.recebidos} perdas={self.perdidos} ({perdas_pct:.1f}%) "
                f"fps={fps:.1f} atraso={self.atraso:.1f}ms jitter={self.jitter:.2f}ms "
                f"saltos={self.saltos} trocas={self.trocas_servidor} maior_falha={self.maior_falha * 1000:.0f}ms")
