# Portas e temporizadores do overlay (tempos em segundos).

BOOTSTRAP_PORT = 5000   # TCP: registo no bootstrapper
CONTROL_PORT = 6000     # TCP: ligação de controlo com cada vizinho
DATA_PORT = 6001        # UDP: pacotes de vídeo
CMD_PORT = 6002         # TCP (só 127.0.0.1): comandos de gestão enviados pelo ottctl.py
CLIENTE_PORT = 6003     # UDP: pedidos dos clientes ao seu onode (PEDIR / PARAR)

# HEARTBEAT: período das mensagens periódicas do overlay (ALIVE e ANUNCIO).
# Escolhido entre 5 e 15 s com os testes de tools/testar_heartbeat.py: pequeno
# demais gera tráfego de controlo constante em todas as ligações (e abre a porta
# a inundações de respostas); grande demais torna lenta a deteção de um nó
# congelado. As mudanças (falhas, rotas novas, poisoning) NÃO esperam pelo
# heartbeat: são avisadas logo. Pode ser alterado com a variável OTT_HEARTBEAT.
import os
HEARTBEAT = float(os.environ.get("OTT_HEARTBEAT", 10.0))
ESPERA_FALHA = 2 * HEARTBEAT + 1    # sem nada durante este tempo -> perdeu-se (tolera 1 heartbeat)

ALIVE_INTERVALO = HEARTBEAT         # ALIVE a cada vizinho (deteção de nós congelados + RTT)
VIZINHO_TIMEOUT = ESPERA_FALHA      # sem receber nada de um vizinho -> está morto
LIGAR_INTERVALO = HEARTBEAT         # nova tentativa de ligar a vizinhos em falta

ANUNCIO_INTERVALO = HEARTBEAT       # anúncio periódico de cada servidor
ROTA_TIMEOUT = ESPERA_FALHA         # caminho sem anúncios novos -> deixa de valer
ROTA_ESQUECER = 3 * HEARTBEAT       # servidor sem caminho há este tempo -> sai da tabela

ATIVAR_INTERVALO = HEARTBEAT        # refrescamento do pedido de um fluxo (só onde há fluxo)
DESTINO_TIMEOUT = ESPERA_FALHA      # destino que não refresca o pedido -> removido

PEDIR_INTERVALO = 1.0               # cliente -> o seu onode (só enquanto vê uma stream)
CLIENTE_TIMEOUT = 3.5               # cliente sem PEDIR durante este tempo -> esquecido

# Métrica: custo da ligação = PESO_SALTO + PESO_ATRASO×A + PESO_PERDAS×P + PESO_CARGA×C
# (a Origem é o candidato viável com menor custo acumulado; ver servicos/vizinhos.py)
PESO_SALTO = 1
PESO_ATRASO = 2
PESO_PERDAS = 3
PESO_CARGA = 1
DEGRAU_ATRASO_MS = 10   # A = RTT local da ligação / 10 ms (arredondado); usa-se o RTT inteiro
                        # porque a ida e a volta podem demorar tempos diferentes
DEGRAU_PERDAS_PCT = 5   # P = perdas (%) / 5 (arredondado)
JANELA_PERDAS = 5.0     # janela de medição das perdas (s)
PERDAS_HOLD_DOWN = 3 * HEARTBEAT  # sem vídeo, a última perda medida fica congelada este tempo
                        # antes de começar a decair (evita voltar a experimentar logo a ligação má)

# Reparação do overlay em falhas duplas (servicos/reparacao.py)
REPARAR_ESPERA = 2.0                # sem caminho durante este tempo -> ligação de recurso
PESO_RECURSO = 10                   # saltos extra de uma ligação de recurso (último recurso)
PEDIDO_SEQ_INTERVALO = 1.0          # no máximo 1 pedido de anúncio por servidor por segundo

FPS = 20                # frames por segundo emitidas pelo servidor (1 a cada 50 ms)
