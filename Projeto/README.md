# Serviço OTT sobre uma rede *overlay* aplicacional — código

Este diretório contém a implementação de um serviço *Over-the-Top* de entrega de vídeo em tempo real, construído sobre uma rede *overlay* aplicacional e avaliado no emulador CORE. O documento resume as decisões de desenho, a organização do código, o protocolo de encaminhamento, a métrica utilizada e o tratamento de falhas. O formato de cada mensagem está em [`message_types.md`](message_types.md); o guião de demonstração está em [`DEMO.md`](DEMO.md) (Topologias 1, 2 e 3) e as árvores de distribuição da Topologia 3 em [`ARVORES_TOPO3.md`](ARVORES_TOPO3.md).

## 1. Decisões de desenho

| Aspeto | Decisão |
|---|---|
| Linguagem | Python 3 (≥ 3.6), apenas com a biblioteca padrão; PIL/Tkinter só para a janela do cliente |
| Transporte | **TCP persistente** entre vizinhos para o controlo; **UDP** para os dados (RTP) |
| Construção do *overlay* | **Bootstrapper** num nó dedicado: cada onode regista-se ao arrancar e recebe o seu nome e a lista de vizinhos, lidos de um ficheiro de configuração. Depois disso, o bootstrapper não intervém |
| Clientes | **Não pertencem ao *overlay***: conhecem apenas o IP do seu onode de acesso, a quem pedem a stream (UDP). Recebem **só pacotes RTP** (o onode retira o cabeçalho do *overlay*), por isso não sabem de que servidor vem o vídeo nem por que caminho. Se esse onode falhar, o cliente fica sem vídeo; quando o onode recupera, o vídeo é retomado sem intervenção |
| Encaminhamento | Vetor de distâncias com números de sequência originados nos servidores (à semelhança do DSDV e do Babel). Cada onode conhece apenas o **próximo salto** (a *Origem*) e o **custo** até cada servidor, e nunca o caminho completo |
| Árvores | Uma árvore de caminhos mais curtos por servidor, formada pelas Origens; os ramos são ativados pelos recetores (ATIVAR) e podados quando deixam de ter destinos (DESATIVAR), como no PIM-SM/DVMRP |
| Métrica | Custo de ligação ponderado: **1×salto + 2×atraso + 3×perdas + 1×carga**, com o atraso medido pelo RTT local (secção 4) |
| Comunicação | Só o previsto: numa ligação sem fluxo passam apenas o heartbeat (`ALIVE`) e o anúncio periódico, a cada 10 s; tudo o resto é desencadeado por eventos (secção 4.1) |
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
│   ├── fluxos.py          ATIVAR / DESATIVAR, escolha do servidor para os clientes
│   ├── clientes.py        atende os clientes do onode (PEDIR / PARAR)
│   ├── reparacao.py       falhas duplas: ENDANGERED e ligação de recurso
│   └── dados.py           emissão, reencaminhamento e réplica do vídeo; medição de perdas; PING
├── comum/                 mensagem, RtpPacket (cada campo explicado), VideoStream, ClienteGUI,
│                          pacote_dados (cabeçalho do overlay), estatisticas, config, log
├── configs/               mapa do overlay de cada topologia (apenas onodes)
├── videos/                filmeA..C.Mjpeg (gerados por tools/gen_video.py)
├── ottctl.py              envia comandos de gestão a um onode em execução
├── tools/arvore.py        (observação) junta o estado de todos os nós e desenha as árvores
├── tools/testar_heartbeat.py  mede tráfego de controlo e tempos de deteção para vários heartbeats
├── core_run.sh            (opcional) arranque automático no CORE a partir do contentor
└── tests/                 testes automáticos sem CORE
```

Cada serviço é uma função `svc_...` executada numa *thread*; cada tipo de mensagem é tratado por uma função `handle_...`.

## 3. Protocolo de encaminhamento

**Anúncios.** Cada servidor envia, a cada *heartbeat* (10 s), um `ANUNCIO` com custo 0 e um número de sequência crescente (a hora em milissegundos, que cresce mesmo após um reinício); a um vizinho que acaba de se ligar envia-o logo. Um onode que recebe o anúncio do vizinho *v* regista um **candidato** com custo `custo_anunciado(v) + custo_ligação(v)` e, se o anúncio for novo, reenvia-o aos restantes vizinhos com o **seu próprio custo**. O anúncio não transporta o caminho: cada onode sabe apenas por que vizinho chega a cada servidor e com que custo.

**Escolha da Origem.** A Origem para um servidor é o candidato **viável** de menor custo (desempates: menos saltos, depois menor IP). As Origens de todos os onodes formam uma árvore de caminhos mais curtos com raiz no servidor.

**Prevenção de ciclos sem conhecer o caminho.** Sem o caminho completo, um onode poderia, após uma falha, adotar uma rota desatualizada que passasse por si próprio. Para o evitar usam-se três mecanismos clássicos:

1. ***Split horizon***: uma rota nunca é anunciada ao vizinho que é a sua Origem.
2. **Condição de viabilidade** (Babel, RFC 8966; EIGRP): um candidato só é aceite se trouxer um número de sequência mais recente, ou, com o mesmo número de sequência, se o custo que o vizinho anuncia for **estritamente inferior** ao melhor custo que o onode já teve. Um vizinho que chegue ao servidor através do próprio onode anuncia necessariamente um custo superior, pelo que nunca é viável.
3. ***Route poisoning***: um onode que fica sem rota viável anuncia de imediato **custo infinito** (`custo: null`), para que os onodes a jusante reajam sem esperar pela expiração da rota.
4. **Pedido de número de sequência** (como no Babel): esse onode envia ainda um `PEDIDO_SEQ` aos vizinhos que ainda chegam ao servidor; o pedido sobe pelas Origens até ao servidor, que se anuncia logo. Assim a rota é refeita sem esperar pelo próximo *heartbeat*. Só acontece em falhas e está limitado a 1 por segundo por servidor.

**Fluxos.** Um fluxo é o par (servidor, stream). O onode de acesso escolhe o servidor de menor custo que tem a stream pedida e envia `ATIVAR` à respetiva Origem; cada onode no percurso regista o remetente como **Destino** e, se ainda não recebia o fluxo, propaga o pedido. Onde dois ramos se juntam passa apenas uma cópia. O estado é *soft* (o `ATIVAR` é repetido a cada *heartbeat*, só nas ligações por onde passa o fluxo, e um Destino expira ao fim de 2 *heartbeats* + 1 s); um onode sem Destinos nem clientes envia `DESATIVAR` (poda). Os dados só são aceites quando chegam da Origem do respetivo servidor.

## 4. Métrica

O custo de uma ligação (do vizinho *v* para o onode) é uma soma ponderada de quatro componentes, quantizadas em degraus para que o ruído de medição não provoque oscilação de rotas. O custo de uma rota é a soma dos custos das ligações até ao servidor:

```
custo(v) = 1×SALTO + 2×A + 3×P + 1×C

A = RTT local da ligação (média das 2 últimas medições do ALIVE) / 10 ms (arredondado)
P = perdas na ligação v → onode (%) / 5 %                               (arredondado)
C = nº de fluxos de OUTROS servidores já recebidos de v (carga)
```

| Componente | Medição | Custo adicional |
|---|---|---|
| Salto | sempre 1 | — |
| Atraso | RTT local medido com `ALIVE`/`ALIVE_RESP`, já trocados para deteção de falhas (a primeira medição, inflacionada pelo arranque da ligação, é ignorada). Usa-se o RTT inteiro e não RTT/2, porque a ida e a volta podem ter atrasos diferentes | nenhum pacote adicional |
| Perdas | **passiva**: cada pacote de vídeo leva um número de sequência por ligação; o recetor conta as lacunas numa janela de 5 s | nenhum pacote adicional |
| Carga | contagem local dos fluxos recebidos de cada vizinho | nenhuma comunicação |

**Exemplos** (pesos 1, 2, 3, 1): ligação sem atraso nem perdas → 1 (equivale a contar saltos); ligação com RTT de 80 ms (40 ms em cada sentido) → 1 + 2×8 = 17; ligação com 10 % de perdas → 1 + 3×2 = 7.

Como as perdas só são medidas quando há tráfego, uma ligação que deixe de ser usada mantém o último valor medido durante um *hold-down* de 3 heartbeats (30 s), como no RIP/EIGRP, e só depois o vai "esquecendo" (fator 0,8 por janela). Ao fim desse tempo volta a ser experimentada e, se continuar com perdas, é novamente penalizada. Sem o hold-down, no CORE, uma ligação com 20% de perdas era abandonada e voltava a ser experimentada a cada ~30 s, e o cliente apanhava as perdas em cada regresso. A carga considera apenas fluxos de outros servidores, para que um fluxo não fuja de uma ligação por causa de si próprio. Cada onode recalcula a cada segundo o custo dos seus candidatos com as últimas medições das suas ligações (custo anunciado + custo atual da ligação), por isso uma ligação que piora é evitada sem esperar pelo próximo anúncio. Os pesos e degraus estão em `comum/config.py`.

### 4.1 Comunicação de controlo e escolha do *heartbeat*

Numa ligação do *overlay* por onde não passa nenhum fluxo só há tráfego **periódico e previsto**: o `ALIVE`/`ALIVE_RESP` (deteção de nós congelados e RTT) e o `ANUNCIO` de cada servidor, ambos a cada *heartbeat*. Vídeo, `ATIVAR`, `PING` e pedidos só passam nas ligações da árvore; tudo o resto (`OLA`, `ADEUS`, *poisoning*, `PEDIDO_SEQ`, `ENDANGERED`) é desencadeado por eventos. Uma saída de um nó deteta-se de imediato pelo fecho do TCP ou pelo `ADEUS`; o *heartbeat* só condiciona a deteção de um nó **congelado** (a ligação não fecha) e a reação a mudanças de RTT.

O *heartbeat* foi escolhido com `tools/testar_heartbeat.py` (Topologia 3, ligação O1–O3 sem fluxo):

| *Heartbeat* | Controlo numa ligação sem fluxo | Nó congelado detetado em | Relay que sai (maior falha) | Onode do cliente volta (vídeo em) |
|---|---|---|---|---|
| 5 s | 96 msg/min (12,2 KB/min) | 6–11 s (medido 7,2 s) | 54 ms | 2,8 s |
| **10 s** | **48 msg/min (6,1 KB/min)** | **11–21 s (medido 17 s)** | **59 ms** | **3,0 s** |
| 15 s | 32 msg/min (4,1 KB/min) | 16–31 s (medido 17 s) | 66 ms | 3,0 s |

A falha de um nó que sai e o regresso de um nó não dependem do *heartbeat* (são tratados por eventos). Escolheu-se **10 s**: metade do tráfego de 5 s, e o pior caso de deteção de um nó congelado (21 s) ainda é aceitável; a partir daí o ganho em tráfego é pequeno (−33 %) e a deteção piora 50 %. O valor está em `comum/config.py` (`HEARTBEAT`) e pode ser alterado com a variável de ambiente `OTT_HEARTBEAT`.

## 5. Falhas e recuperação

| Evento | Deteção | Reação |
|---|---|---|
| Onode termina (processo morto) | fecho da ligação TCP (imediato) | o vizinho a jusante escolhe outra Origem viável; se não houver, *route poisoning* |
| Saída ordeira | `ADEUS` (imediato) | idem |
| Onode bloqueado / ligação cortada | ausência de mensagens durante 2 *heartbeats* + 1 s = 21 s (`ALIVE` a cada 10 s) | idem |
| Servidor falha | fecho do TCP nos vizinhos; *poisoning* a partir deles | streams replicadas passam para o outro servidor; as restantes ficam "sem servidor", mas os pedidos são mantidos |
| Onode de acesso de um cliente falha | o cliente deixa de receber resposta ao `PEDIR` | o cliente fica sem vídeo e continua a pedir; o vídeo é retomado quando o onode recupera |
| Recuperação de um onode | — | regista-se no bootstrapper, volta a ligar-se aos vizinhos, recebe de imediato as rotas conhecidas, e os pedidos repetidos (ATIVAR/PEDIR) reconstroem os fluxos |
| Bootstrapper falha | — | o *overlay* em funcionamento não é afetado; apenas novas entradas aguardam |
| Falha dupla: os dois caminhos de um nó morrem, um depois do outro | 1.ª falha: `ENDANGERED`; 2.ª falha: sem caminho durante 2 s | ligação de recurso ao próximo salto do vizinho que morreu em segundo lugar (ver 5.1) |

Resultados dos testes locais: falha de um onode intermédio → interrupção de ~50 ms; falha de um onode sem alternativa viável imediata (T10, com `PEDIDO_SEQ`) → ~50 ms; falha de um servidor com stream replicada → ~60 ms; onode bloqueado → até 2 *heartbeats* + 1 s.

### 5.1 Reparação do *overlay* em falhas duplas

Exemplo (acordado com o docente): `C — O1`, ligado a `O2` e `O3`, ambos ligados a `O4 — S`; o fluxo vai de `O4` para `O1`. `O1` e `O4` não são vizinhos no *overlay*, mas alcançam-se no *underlay*. Nenhum nó sabe mais do que os seus vizinhos enquanto não houver perigo:

1. **Perigo.** Morre `O2`. `O1` continua a receber por `O3`, mas, para esse servidor, já só lhe resta **um** vizinho com caminho, e há um fluxo ativo. Só então `O1` envia `ENDANGERED` a `O3`.
2. `O3` responde `ENDANGERED_RESP` **apenas com o IP da sua Origem** (`O4`). `O1` guarda-o como reserva; não fica a saber mais nada.
3. **Falha dupla.** Se `O3` também morrer e `O1` ficar 2 s sem caminho, abre uma **ligação de recurso** a `O4`. Funciona como uma ligação normal (anúncios, `ATIVAR`, vídeo), mas custa mais 10, para só ser usada quando não há outro caminho.
4. Quando `O2` ou `O3` regressa, o caminho por ele volta a ser o mais barato e passa a ser usado; a ligação de recurso fica livre e, 2 s depois, `O1` fecha-a (`ADEUS`).

Limitação: se `O2` e `O3` falharem ao mesmo tempo (antes da resposta ao `ENDANGERED`), `O1` não tem reserva e fica à espera que um deles volte. Código: `servicos/reparacao.py`; testes: `tests/test_falha_dupla.py` (topologia `configs/overlay_falha_dupla.json`).

## 6. Execução

Comandos por PC e guião da demonstração: [`DEMO.md`](DEMO.md) (Topologias 1, 2 e 3).

| Comando (terminal do onode, ou `python3 ottctl.py <comando>`) | Resultado |
|---|---|
| `rotas` | tabela de rotas: Fluxo, Origem, Métrica, Saltos, Destinos, Estado, Alternativas |
| `vizinhos` | vizinhos, RTT, perdas, carga e decomposição do custo de cada ligação |
| `ping` (servidor) | PING pelos fluxos ativos (Etapa 3); cada nó regista o caminho percorrido |
| `sair` | saída ordeira (`ADEUS`) |
| `estado` | estado local em JSON (Origens, Destinos e contadores de mensagens por vizinho), usado por `tools/arvore.py` e `tools/testar_heartbeat.py` |

**Ver as árvores.** `python3 tools/arvore.py --core --watch 2`, na shell do contentor do CORE, pergunta o `estado` a todos os nós e desenha a árvore de cada servidor (Origens, custos, alternativas) e os fluxos que estão mesmo a passar. Atualiza de 2 em 2 s, por isso vê-se a árvore mudar quando um nó morre ou quando se mete atraso numa ligação. Com `--dot arvore` gera também uma figura por servidor (`arvore_S1.png`, …), se houver Graphviz. É só observação: os onodes continuam a não conhecer a árvore.

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
| T4b | onode bloqueado (sem FIN/RST) → deteção por *timeout* (2 *heartbeats* + 1 s) |
| T5 | o onode de acesso falha → o cliente fica sem vídeo; o onode recupera → o vídeo volta |
| T6 | 40 ms na ligação O4–O2 → custo 1 + 2×8 → o O4 passa para o O3; e regresso |
| T7 | escolha do servidor mais próximo para uma stream replicada; mudança quando este falha |
| T8 | sem clientes, o fluxo fica inativo e a poda propaga-se pela árvore |
| T9 | 30 % de perdas numa ligação (medidas com o próprio vídeo) → mudança de Origem |
| T10 | falha de um onode: a rota desatualizada é recusada (viabilidade), há *route poisoning*, `PEDIDO_SEQ` e recuperação |
| T11 | a melhor rota morre → passa-se para a alternativa; quando volta → regressa-se à melhor rota |
| T12 | numa ligação sem fluxo (O1–O3) passam 0 pacotes de vídeo e só o número previsto de mensagens de controlo |
| Reparação | em nenhum destes cenários se abre uma ligação de recurso (há sempre alternativa) |

`tests/test_falha_dupla.py` testa o extra da secção 5.1: F1, só um nó do meio morre → muda de rota, **não** abre ligação de recurso, mas envia `ENDANGERED` e guarda a reserva; F2, morre o outro → ligação de recurso, o vídeo volta; um deles volta → regressa à rota normal e a ligação de recurso fecha; F3, igual, com mais um vizinho vivo sem rota; F4, morre o servidor → **ninguém** abre ligação de recurso; F5 (limitação), os dois congelam ao mesmo tempo → sem reserva, não há reparação.

Os comandos `delay <IP> <ms>` e `perda <IP> <%>` (e a opção `--link-delay`) emulam atraso e perdas **apenas para estes testes**; no CORE usam-se as propriedades das ligações.

## 8. Trabalho futuro

Extensões possíveis: *buffer* de compensação de *jitter* no cliente; fragmentação das *frames* na aplicação (RTP/JPEG, RFC 2435), para evitar a fragmentação IP; escolha automática de vizinhos pelo bootstrapper com base na proximidade.
