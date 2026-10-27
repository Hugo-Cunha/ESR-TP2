# Portas e temporizadores do overlay (tempos em segundos).

BOOTSTRAP_PORT = 5000   # TCP: registo no bootstrapper
CONTROL_PORT = 6000     # TCP: ligação de controlo com cada vizinho
DATA_PORT = 6001        # UDP: pacotes de vídeo
CMD_PORT = 6002         # TCP (só 127.0.0.1): comandos de gestão enviados pelo ottctl.py
CLIENTE_PORT = 6003     # UDP: pedidos dos clientes ao seu onode (PEDIR / PARAR)

ALIVE_INTERVALO = 1.0   # de quanto em quanto tempo se envia ALIVE a cada vizinho
VIZINHO_TIMEOUT = 3.5   # sem receber nada de um vizinho durante este tempo -> está morto
LIGAR_INTERVALO = 2.0   # de quanto em quanto tempo se tenta ligar a vizinhos em falta

ANUNCIO_INTERVALO = 1.0 # de quanto em quanto tempo um servidor se anuncia
ROTA_TIMEOUT = 3.5      # caminho sem anúncios novos durante este tempo -> deixa de valer

ATIVAR_INTERVALO = 2.0  # de quanto em quanto tempo se refresca o pedido de um fluxo
DESTINO_TIMEOUT = 6.5   # destino que não refresca o pedido durante este tempo -> removido

PEDIR_INTERVALO = 1.0   # o cliente repete o PEDIR de 1 em 1 s
CLIENTE_TIMEOUT = 3.5   # cliente sem PEDIR durante este tempo -> o onode esquece-o

FPS = 20                # frames por segundo emitidas pelo servidor (1 a cada 50 ms)
