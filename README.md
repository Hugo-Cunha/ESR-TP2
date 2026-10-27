# Serviço OTT sobre uma rede *overlay* aplicacional — código

Este diretório contém a implementação de um serviço *Over-the-Top* de entrega de vídeo em tempo real, construído sobre uma rede *overlay* aplicacional e avaliado no emulador CORE. O documento resume as decisões de desenho, a organização do código, o protocolo de encaminhamento, a métrica utilizada e o tratamento de falhas. O formato de cada mensagem está em [`message_types.md`](message_types.md); o guião de demonstração está em [`DEMO.md`](DEMO.md) (Topologia 3) e [`TOPOLOGIAS_1_2.md`](TOPOLOGIAS_1_2.md).

## 1. Decisões de desenho

| Aspeto | Decisão |
|---|---|
| Linguagem | Python 3 (≥ 3.6), apenas com a biblioteca padrão; PIL/Tkinter só para a janela do cliente |
| Transporte | **TCP persistente** entre vizinhos para o controlo; **UDP** para os dados (RTP) |
| Construção do *overlay* | **Bootstrapper** num nó dedicado: cada onode regista-se ao arrancar e recebe o seu nome e a lista de vizinhos, lidos de um ficheiro de configuração. Depois disso, o bootstrapper não intervém |
| Clientes | **Não pertencem ao *overlay***: conhecem apenas o IP do seu onode de acesso, a quem pedem a stream (UDP). Se esse onode falhar, o cliente fica sem vídeo; quando o onode recupera, o vídeo é retomado sem intervenção |
| Encaminhamento | Vetor de distâncias com números de sequência originados nos servidores (à semelhança do DSDV e do Babel). Cada onode conhece apenas o **próximo salto** (a *Origem*) e o **custo** até cada servidor, e nunca o caminho completo |
| Árvores | Uma árvore de caminhos mais curtos por servidor, formada pelas Origens; os ramos são ativados pelos recetores (ATIVAR) e podados quando deixam de ter destinos (DESATIVAR), como no PIM-SM/DVMRP |
| Métrica | Custo de ligação ponderado: **1×salto + 2×atraso + 3×perdas + 1×carga** (secção 4) |
| Streams | S1: filmeA, filmeB · S2: filmeB, filmeC. O filmeB está replicado: o onode de acesso escolhe o servidor de menor custo e muda automaticamente se este falhar |
| Vídeo | MJPEG em RTP (exemplo do livro de Kurose & Ross); o servidor só emite quando há destinos |

## 2. Organização do código

```
Projeto/
├── bootstrapper.py        conhece o overlay completo; responde apenas a registos
├── onode.py               nó do overlay: arranca os serviços (lista em onode.iniciar)
├── servidor.py            onode + anúncios + emissão das streams
├── cliente.py             NÃO é onode: pede a stream ao seu onode e reproduz-a
├── database.py            ESTADO do nó (vizinhos, rotas, fluxos, clientes) — apenas dados
├── servicos/              LÓGICA, separada por função
│   ├── vizinhos.py        registo, ligações TCP, ALIVE, deteção de falhas, ADEUS, MÉTRICA
│   ├── rotas.py           ANUNCIO, condição de viabilidade, split horizon, route poisoning
│   ├── fluxos.py          ATIVAR / DESATIVAR, escolha do servidor para os clientes, carga
│   ├── clientes.py        atende os clientes do onode (PEDIR / PARAR)
│   └── dados.py           emissão, reencaminhamento e réplica do vídeo; medição de perdas; PING
├── comum/                 mensagem, RtpPacket (cada campo explicado), VideoStream, ClienteGUI,
│                          pacote_dados (cabeçalho do overlay), estatisticas, config, log
├── configs/               mapa do overlay de cada topologia (apenas onodes)
├── videos/                filmeA..C.Mjpeg (gerados por tools/gen_video.py)
├── ottctl.py              envia comandos de gestão a um onode em execução
├── core_run.sh            (opcional) arranque automático no CORE a partir do contentor
└── tests/                 testes automáticos sem CORE
```

Cada serviço é uma função `svc_...` executada numa *thread*; cada tipo de mensagem é tratado por uma função `handle_...`.

## 3. Protocolo de encaminhamento

**Anúncios.** Cada servidor envia, a cada segundo, um `ANUNCIO` com custo 0 e um número de sequência crescente (a hora em milissegundos, que cresce mesmo após um reinício). Um onode que recebe o anúncio do vizinho *v* regista um **candidato** com custo `custo_anunciado(v) + custo_ligação(v)` e, se o anúncio for novo, reenvia-o aos restantes vizinhos com o **seu próprio custo**. O anúncio não transporta o caminho: cada onode sabe apenas por que vizinho chega a cada servidor e com que custo.

**Escolha da Origem.** A Origem para um servidor é o candidato **viável** de menor custo (desempates: menos saltos, depois menor IP). As Origens de todos os onodes formam uma árvore de caminhos mais curtos com raiz no servidor.

**Prevenção de ciclos sem conhecer o caminho.** Sem o caminho completo, um onode poderia, após uma falha, adotar uma rota desatualizada que passasse por si próprio. Para o evitar usam-se três mecanismos clássicos:

1. ***Split horizon***: uma rota nunca é anunciada ao vizinho que é a sua Origem.
2. **Condição de viabilidade** (Babel, RFC 8966; EIGRP): um candidato só é aceite se trouxer um número de sequência mais recente, ou, com o mesmo número de sequência, se o custo que o vizinho anuncia for **estritamente inferior** ao melhor custo que o onode já teve. Um vizinho que chegue ao servidor através do próprio onode anuncia necessariamente um custo superior, pelo que nunca é viável.
3. ***Route poisoning***: um onode que fica sem rota viável anuncia de imediato **custo infinito** (`custo: null`), para que os onodes a jusante reajam sem esperar pela expiração da rota.

**Fluxos.** Um fluxo é o par (servidor, stream). O onode de acesso escolhe o servidor de menor custo que tem a stream pedida e envia `ATIVAR` à respetiva Origem; cada onode no percurso regista o remetente como **Destino** e, se ainda não recebia o fluxo, propaga o pedido. Onde dois ramos se juntam passa apenas uma cópia. O estado é *soft* (o `ATIVAR` é repetido a cada 2 s e um Destino expira ao fim de 6,5 s); um onode sem Destinos nem clientes envia `DESATIVAR` (poda). Os dados só são aceites quando chegam da Origem do respetivo servidor.

## 4. Métrica

O custo de uma ligação (do vizinho *v* para o onode) é uma soma ponderada de quatro componentes, quantizadas em degraus para que o ruído de medição não provoque oscilação de rotas:

```
custo(v) = 1×SALTO + 2×A + 3×P + 1×C

A = atraso num sentido (RTT/2, média dos 3 últimos ALIVE) / 5 ms        (arredondado)
P = perdas na ligação v → onode (%) / 5 %                               (arredondado)
C = nº de fluxos de OUTROS servidores já recebidos de v (carga)
```

| Componente | Medição | Custo adicional |
|---|---|---|
| Salto | sempre 1 | — |
| Atraso | `ALIVE`/`ALIVE_RESP`, já trocados para deteção de falhas | nenhum pacote adicional |
| Perdas | **passiva**: cada pacote de vídeo leva um número de sequência por ligação; o recetor conta as lacunas numa janela de 5 s | nenhum pacote adicional |
| Carga | contagem local dos fluxos recebidos de cada vizinho | nenhuma comunicação |

**Exemplos** (pesos 1, 2, 3, 1): ligação sem atraso nem perdas → 1 (equivale a contar saltos); ligação com 40 ms → 1 + 2×8 = 17; ligação com 10 % de perdas → 1 + 3×2 = 7.

Como as perdas só são medidas quando há tráfego, uma ligação que deixe de ser usada vai "esquecendo" o valor medido (fator 0,8 por janela). Ao fim de algum tempo volta a ser experimentada e, se continuar com perdas, é novamente penalizada. A carga considera apenas fluxos de outros servidores, para que um fluxo não fuja de uma ligação por causa de si próprio. Os pesos e degraus estão em `comum/config.py`.

## 5. Falhas e recuperação

| Evento | Deteção | Reação |
|---|---|---|
| Onode termina (processo morto) | fecho da ligação TCP (imediato) | o vizinho a jusante escolhe outra Origem viável; se não houver, *route poisoning* |
| Saída ordeira | `ADEUS` (imediato) | idem |
| Onode bloqueado / ligação cortada | ausência de mensagens durante 3,5 s (ALIVE a cada 1 s) | idem |
| Servidor falha | os anúncios deixam de ser renovados; *poisoning* a partir dos vizinhos | streams replicadas passam para o outro servidor; as restantes ficam "sem servidor", mas os pedidos são mantidos |
| Onode de acesso de um cliente falha | o cliente deixa de receber resposta ao `PEDIR` | o cliente fica sem vídeo e continua a pedir; o vídeo é retomado quando o onode recupera |
| Recuperação de um onode | — | regista-se no bootstrapper, volta a ligar-se aos vizinhos, recebe de imediato as rotas conhecidas, e os pedidos repetidos (ATIVAR/PEDIR) reconstroem os fluxos |
| Bootstrapper falha | — | o *overlay* em funcionamento não é afetado; apenas novas entradas aguardam |

Resultados dos testes locais: falha de um onode intermédio → interrupção de ~50 ms; onode bloqueado → ~2,6 s; falha de um onode sem alternativa viável imediata (T10) → ~100 ms; falha de um servidor com stream replicada → ~80 ms.

## 6. Execução

Comandos por PC e guião da demonstração: [`DEMO.md`](DEMO.md) (Topologia 3) e [`TOPOLOGIAS_1_2.md`](TOPOLOGIAS_1_2.md).

| Comando (terminal do onode, ou `python3 ottctl.py <comando>`) | Resultado |
|---|---|
| `rotas` | tabela de rotas: Fluxo, Origem, Métrica, Saltos, Destinos, Estado, Alternativas |
| `vizinhos` | vizinhos, RTT, perdas, carga e decomposição do custo de cada ligação |
| `ping` (servidor) | PING pelos fluxos ativos (Etapa 3); cada nó regista o caminho percorrido |
| `sair` | saída ordeira (`ADEUS`) |

No cliente: `play <stream>`, `stop`, `sair`.

## 7. Testes automáticos

`tests/test_scenarios.py` executa a Topologia 3 numa só máquina (cada nó num IP 127.10.0.x):

```bash
python3 tests/test_scenarios.py            # ~3 min; resultados em tests/logs/resultados.md
ONLY=t9 python3 tests/test_scenarios.py    # apenas um teste
```

| Teste | Verifica |
|---|---|
| T1 | 2 servidores × 2 streams, 4 clientes, 20 fps sem perdas |
| T2 | árvore partilhada: 4 clientes, o servidor envia menos de 4 cópias |
| T3 | falha abrupta de um onode intermédio → mudança de Origem, o vídeo continua |
| T4 | saída ordeira (`ADEUS`) → desvio imediato |
| T4b | onode bloqueado (sem FIN/RST) → deteção por *timeout* |
| T5 | o onode de acesso falha → o cliente fica sem vídeo; o onode recupera → o vídeo volta |
| T6 | 40 ms numa ligação → mudança para um caminho com o mesmo nº de saltos e menor atraso; e regresso |
| T7 | escolha do servidor mais próximo para uma stream replicada; mudança quando este falha |
| T8 | sem clientes, o fluxo fica inativo e a poda propaga-se pela árvore |
| T9 | 30 % de perdas numa ligação (medidas com o próprio vídeo) → mudança de Origem |
| T10 | falha de um onode: a rota desatualizada é recusada (viabilidade), há *route poisoning* e recuperação |

Os comandos `delay <IP> <ms>` e `perda <IP> <%>` (e a opção `--link-delay`) emulam atraso e perdas **apenas para estes testes**; no CORE usam-se as propriedades das ligações.

## 8. Trabalho futuro

**Reparação do *overlay* através do "próximo do vizinho".** Numa cadeia sem alternativas (por exemplo `S1 — O2 — O4`), a falha de O2 isola O4 até O2 recuperar. Se cada anúncio incluísse também a Origem de quem o envia (um único campo, e não o caminho completo), O4 saberia que o próximo salto de O2 é S1 e poderia abrir diretamente uma ligação a S1, restabelecendo o fluxo sem esperar pela recuperação de O2. Esta extensão foi sugerida pelo docente e fica prevista como trabalho futuro.

Outras extensões possíveis: *buffer* de compensação de *jitter* no cliente; fragmentação das *frames* na aplicação (RTP/JPEG, RFC 2435), para evitar a fragmentação IP; escolha automática de vizinhos pelo bootstrapper com base na proximidade.
