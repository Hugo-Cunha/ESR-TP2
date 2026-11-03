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

# Métrica: custo da ligação = PESO_SALTO + PESO_ATRASO×A + PESO_PERDAS×P + PESO_CARGA×C
PESO_SALTO = 1
PESO_ATRASO = 2
PESO_PERDAS = 3
PESO_CARGA = 1
DEGRAU_ATRASO_MS = 10   # A = RTT da ligação / 10 ms (arredondado); usa-se o RTT inteiro
                        # porque a ida e a volta podem demorar tempos diferentes
DEGRAU_PERDAS_PCT = 5   # P = perdas (%) / 5 (arredondado)
JANELA_PERDAS = 5.0     # janela de medição das perdas (s)

# Reparação do overlay (falhas duplas): um nó que fica sem caminho para nenhum
# servidor liga-se diretamente a um vizinho dos vizinhos que morreram.
REPARAR_ESPERA = 2.0    # tempo isolado antes de abrir a ligação de recurso (s)
PESO_RECURSO = 10       # custo extra de uma ligação de recurso: só é usada se não houver outra

FPS = 20                # frames por segundo emitidas pelo servidor (1 a cada 50 ms)
