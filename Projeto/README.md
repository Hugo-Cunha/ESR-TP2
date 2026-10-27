# Código do projeto — Serviço OTT sobre overlay aplicacional

## Decisões

| | Decisão |
|---|---|
| Linguagem | Python 3 (só biblioteca padrão; PIL/Tkinter apenas para a janela do cliente) |
| Transporte | **TCP persistente** com cada vizinho para o controlo; **UDP** para o vídeo |
| Construção do overlay | **Bootstrapper** num PC próprio: cada nó regista-se ao arrancar e recebe o nome e os vizinhos (lidos de um JSON). Depois o bootstrapper não intervém |
| Rotas | Cada servidor inunda **ANUNCIO**s; cada nó escolhe como **Origem** o vizinho com o caminho de menor custo. As Origens formam uma árvore por servidor |
| Métrica | custo de uma ligação = **1 + 1 por cada 5 ms de atraso** (atraso = RTT/2, medido com ALIVE) |
| Clientes | **Não fazem parte do overlay**: só conhecem o IP do seu onode, a quem pedem a stream (PEDIR, UDP, de 1 em 1 s). Se o onode morre, o cliente fica sem vídeo; quando volta, o vídeo volta |
| Fluxos | O onode do cliente escolhe o melhor servidor e envia **ATIVAR** pela árvore acima; nós sem destinos enviam **DESATIVAR** (poda) |
| Streaming | MJPEG em RTP (exemplo do Kurose); o servidor só envia se houver destinos |
| Streams | S1: filmeA, filmeB · S2: filmeB, filmeC (o filmeB está nos dois: o onode escolhe o melhor servidor) |
| Extras | escolha do melhor servidor e mudança se ele cair; estatísticas no cliente; testes automáticos |

## Estrutura

```
Projeto/
├── bootstrapper.py        conhece o overlay inteiro; só responde a registos
├── onode.py               nó do overlay: arranca os serviços
├── servidor.py            onode + anúncios + emissão das streams
├── cliente.py             NÃO é onode: pede a stream ao seu onode e mostra-a (janela ou --sem-gui)
├── database.py            ESTADO do nó: vizinhos, rotas, fluxos (só dados)
├── servicos/              LÓGICA, separada por assunto
│   ├── vizinhos.py        registo, ligações TCP, ALIVE, falhas, ADEUS, métrica
│   ├── rotas.py           ANUNCIO, escolha da Origem, inundação controlada
│   ├── fluxos.py          ATIVAR / DESATIVAR, escolha do servidor para os clientes
│   ├── clientes.py        atende os clientes ligados ao onode (PEDIR / PARAR)
│   └── dados.py           emitir (servidor), receber e replicar (todos), PING
├── comum/                 peças pequenas usadas por todos
│   ├── mensagem.py        tipos de mensagem e leitura de mensagens do TCP
│   ├── RtpPacket.py       pacote RTP, com cada campo explicado
│   ├── VideoStream.py     leitura do .Mjpeg (Kurose)
│   ├── pacote_dados.py    cabeçalho do overlay nos pacotes UDP
│   ├── ClienteGUI.py      janela (Kurose): Play / Pause / Teardown
│   ├── estatisticas.py    perdas, atraso, jitter
│   └── config.py, log.py
├── message_types.md       formato de cada mensagem
├── configs/               mapa do overlay para cada topologia
├── videos/                filmeA..C.Mjpeg (gerados por tools/gen_video.py)
├── ottctl.py              envia comandos a um nó a correr em fundo
├── DEMO.md                comandos de cada PC e guião da demonstração
├── core_run.sh            (opcional) arranca tudo no CORE a partir do contentor
└── tests/                 testes automáticos sem CORE
```

Cada serviço é uma função `svc_...` que corre numa thread; cada mensagem recebida é tratada por uma função `handle_...`. A lista de serviços de um nó está em `onode.iniciar()`.

## Correr no CORE (Topologia 3)

Comandos para cada PC e guião da demonstração: **ver [`DEMO.md`](DEMO.md)**.

| Nó overlay | PC no CORE | IP | Programa |
|---|---|---|---|
| — | **Bootstrapper** | 10.0.18.10 | `bootstrapper.py` (PC só para ele, para não gastar CPU dos servidores) |
| S1 | Server | 10.0.18.20 | `servidor.py` (filmeA, filmeB) |
| S2 | PC6 | 10.0.0.20 | `servidor.py` (filmeB, filmeC) |
| O1, O2, O3, O4 | PC1, PC4, PC2, PC9 | | `onode.py` |
| (clientes) | PC5 → O2, PC3 → O3, PC8 → O4, PC7 → S2 | | `cliente.py <IP do onode> <stream>` |

O **filmeB está nos dois servidores**: o onode de cada cliente recebe-o do servidor com o melhor caminho e, se esse servidor cair, passa para o outro.

`core_run.sh` (opcional) arranca tudo de uma vez a partir da shell do contentor Docker; serve para testar depressa, não para a demonstração.

### Comandos de cada nó (no terminal, ou `python3 ottctl.py <comando>`)

| Comando | Onde | O que faz |
|---|---|---|
| `rotas` | onodes | tabela: Fluxo, Origem, Métrica, Saltos, Destinos, Estado, Alternativas |
| `vizinhos` | onodes | vizinhos, estado da ligação e RTT |
| `ping` | servidor | PING pelos fluxos ativos |
| `play <stream>` / `stop` | cliente | começa / deixa de ver |
| `sair` | todos | sai (onode: ADEUS aos vizinhos; cliente: PARAR ao onode) |

## Testes sem CORE

`tests/test_scenarios.py` corre a Topologia 3 numa só máquina (cada nó num IP 127.10.0.x):

```bash
python3 tests/test_scenarios.py            # ~2,5 min; resultados em tests/logs/resultados.md
ONLY=t6 python3 tests/test_scenarios.py    # só um teste
```

| Teste | Verifica |
|---|---|
| T1 | 2 servidores × 2 streams, 4 clientes, 20 fps sem perdas |
| T2 | árvore partilhada: 4 clientes, o servidor envia menos de 4 cópias |
| T3 | `kill -9` de um nó intermédio → o onode do cliente muda de Origem, o vídeo continua |
| T4 | saída ordeira (ADEUS) → desvio imediato |
| T4b | nó congelado (sem FIN/RST) → deteção pelo timeout de 3,5 s |
| T5 | o onode do cliente morre → o cliente fica sem vídeo; o onode volta → o vídeo volta |
| T6 | 40 ms numa ligação → a rota muda para outra com o mesmo nº de saltos; e volta |
| T7 | o onode escolhe o servidor mais próximo para o filmeB; se ele cai, passa para o outro |
| T8 | sem clientes o fluxo fica inativo e a poda sobe pela árvore |

`--link-delay IP=ms` e o comando `delay <IP> <ms>` emulam atraso numa ligação **só para os testes**; no CORE usa-se o atraso das ligações.
