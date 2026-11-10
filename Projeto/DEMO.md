# Cábula da demonstração

Três cenários, do mais simples para o completo. Em todos: comandos diretos no terminal de cada PC (duplo clique no PC no CORE), a partir de `/volume/ESR-TP2/Projeto`, e arranque pela ordem **bootstrapper → servidores → onodes → clientes**.

| Cenário | Ficheiro | Overlay | Mostra |
|---|---|---|---|
| [A — Topologia 1](#a-topologia-1--uma-lan-um-switch) | `Topologia_test1.xml` | S1 — O1 — cliente | registo, rota, PING, vídeo por um nó intermédio, poda |
| [B — Topologia 2](#b-topologia-2--três-routers) | `Topologia_test2.xml` | S1 — S2 — cliente | dois servidores, um servidor a reencaminhar o outro, escolha do servidor, falha de servidor, atraso |
| [C — Topologia 3](#c-topologia-3--cenário-completo) | `Topologia_test3.xml` | 2 servidores + 5 onodes | árvore, rotas alternativas, falhas, métrica, troca de servidor |

Para mudar de cenário no CORE: **Stop** (mata os processos dos nós) → abrir o outro `.xml` → **Start** → esperar ~30 s pelo OSPF.

Em todas as topologias o bootstrapper corre num **PC próprio, chamado Bootstrapper** (nunca num servidor nem no cliente):

| Cenário | IP do bootstrapper (1.º argumento de servidores e onodes) |
|---|---|
| A — Topologia 1 | 10.0.0.23 |
| B — Topologia 2 | 10.0.6.20 |
| C — Topologia 3 | 10.0.18.10 |

---

# A. Topologia 1 — uma LAN, um switch

Rede física: PC1 (10.0.0.20), PC2 (10.0.0.21), Server (10.0.0.22) e Bootstrapper (10.0.0.23) ligados ao mesmo switch; não há routers.
Overlay (`configs/overlay_topo1.json`): `S1 — O1`; o cliente liga-se ao O1.

## A.0 Preparar

1. Abrir `Topologia/Topologia_test1.xml` no CORE → **Start** (sem routers, não é preciso esperar pelo OSPF).
2. Testar a rede: no terminal do **Bootstrapper**, `ping -c2 10.0.0.22` e `ping -c2 10.0.0.21`.
3. Em cada terminal: `cd /volume/ESR-TP2/Projeto`.

## A.1 Arrancar (por esta ordem)

| PC | Papel | Comando |
|---|---|---|
| **Bootstrapper** (10.0.0.23) | bootstrapper | `python3 bootstrapper.py configs/overlay_topo1.json` |
| **Server** (10.0.0.22) | S1 (filmeA, filmeB) | `python3 servidor.py 10.0.0.23 filmeA filmeB` |
| **PC1** (10.0.0.20) | O1 | `python3 onode.py 10.0.0.23` |
| **PC2** (10.0.0.21) | cliente, ligado ao O1 | `python3 cliente.py 10.0.0.20 filmeA` |

## A.2 Guião

| # | Fazer | O que se vê | O que dizer |
|---|---|---|---|
| 1 | Arrancar bootstrapper, S1 e O1 | O1: `Registado como O1 ...; vizinhos: S1`; `Vizinho S1 ligado` | "O bootstrapper só dá a cada nó o nome e os vizinhos; depois não intervém." |
| 2 | Arrancar o cliente | janela com o vídeo; cliente: `Onode 10.0.0.20: a enviar` | "O cliente só conhece o seu onode." |
| 3 | `rotas` no PC1 (O1) | `S1/filmeA  S1  1  1  cliente:10.0.0.21  ativa` | "O O1 só sabe que chega ao S1 diretamente, com custo 1, e para quem copia o fluxo." |
| 4 | `rotas` no Server (S1) | `S1/filmeA  (local) ... O1  ativa`; `S1/filmeB ... inativa` | "O servidor só envia o que alguém pediu: o filmeB não sai." |
| 5 | `ping` no Server | O1 escreve o caminho `S1 > O1` | Etapa 3. |
| 6 | **Ctrl+C no PC1** (O1) | cliente: `o onode não responde`, fps=0 | "Se o onode do cliente morre, o cliente fica sem vídeo..." |
| 7 | Voltar a arrancar o O1 | cliente: `a enviar`, o vídeo volta | "...e quando volta, o vídeo volta sozinho (o cliente pede de 1 em 1 s)." |
| 8 | `play filmeB` no cliente | o vídeo muda; `rotas` no Server: filmeA `inativa`, filmeB `ativa` | "Mudança de stream: o ramo antigo é podado." |
| 9 | `stop` no cliente | `poda` no PC1; `rotas` no Server: tudo `inativa` | "Sem clientes não há tráfego." |

---

# B. Topologia 2 — três routers

Rede física: Server1 (10.0.1.20) atrás do R1, PC1 (10.0.0.20) atrás do R3, PC2 (10.0.5.20) atrás do R2 e Bootstrapper (10.0.6.20) na sua própria rede; os três routers em triângulo (OSPF).
Overlay (`configs/overlay_topo2.json`): `S1 — S2`; o cliente liga-se ao S2 (um servidor também é onode e reencaminha).

## B.0 Preparar

1. Abrir `Topologia/Topologia_test2.xml` no CORE → **Start** → esperar ~30 s (OSPF).
2. Testar a rede: no terminal do **Bootstrapper**, `ping -c2 10.0.1.20` e `ping -c2 10.0.0.20`; no **PC2**, `ping -c2 10.0.0.20`. Se não responder, o problema é do routing, não do código.
3. Em cada terminal: `cd /volume/ESR-TP2/Projeto`.

## B.1 Arrancar (por esta ordem)

| PC | Papel | Comando |
|---|---|---|
| **Bootstrapper** (10.0.6.20) | bootstrapper | `python3 bootstrapper.py configs/overlay_topo2.json` |
| **Server1** (10.0.1.20) | S1 (filmeA, filmeB) | `python3 servidor.py 10.0.6.20 filmeA filmeB` |
| **PC1** (10.0.0.20) | S2 (filmeB, filmeC) | `python3 servidor.py 10.0.6.20 filmeB filmeC` |
| **PC2** (10.0.5.20) | cliente, ligado ao S2 | `python3 cliente.py 10.0.0.20 filmeA` |

## B.2 Guião

| # | Fazer | O que se vê | O que dizer |
|---|---|---|---|
| 1 | Arrancar bootstrapper, S1 e S2 | `Vizinho S1 ligado` / `Vizinho S2 ligado` | "Dois servidores; o S2 também é um onode." |
| 2 | Arrancar o cliente (filmeA) | vídeo; cliente: `a enviar` | — |
| 3 | `rotas` no PC1 (S2) | `S1/filmeA  S1  1  1  cliente:10.0.5.20  ativa` | "Só o S1 tem o filmeA: o S2 recebe-o do S1 e passa-o ao cliente, como qualquer onode." |
| 4 | `ping` no Server1 | S2 escreve `S1 > S2` | Etapa 3. |
| 5 | `play filmeB` no cliente | `rotas` no PC1: `S2/filmeB (local) ... cliente:10.0.5.20 ativa`; no Server1 o filmeA fica `inativa` | "O filmeB está nos dois servidores; o onode escolhe o de menor custo, aqui ele próprio (custo 0). O S1 deixa de enviar (poda)." |
| 6 | `play filmeA` no cliente; **Ctrl+C no Server1** | cliente: `nenhum servidor tem esta stream (ainda)` | "Só o S1 tinha o filmeA; o S1 avisa ao sair (ADEUS) e a rota desaparece." |
| 7 | Voltar a arrancar o S1 | o vídeo volta | "O S1 volta a anunciar-se e a rota reaparece sozinha." |
| 8 | `vizinhos` no PC1 | custo da ligação ao S1 = `1 = 1 + 2×0 + 3×0 + 1×0` | "A métrica: salto, atraso (RTT local), perdas e carga." |
| 9 | Duplo clique na ligação **R1–R3** → **Delay 40000 µs** | ao fim de 1–2 heartbeats (10–20 s), em `vizinhos` no PC1, o custo da ligação ao S1 sobe para 1 + 2×8 = 17; `rotas` mostra Métrica 17 | "O OSPF não liga ao atraso, mas o overlay mede-o com o ALIVE." |
| 10 | Delay 0 e **Loss 20%** na mesma ligação | ao fim de ~10 s, Perdas ≈ 20% e o custo sobe 3×4 | "As perdas medem-se com o próprio vídeo, pelas lacunas no nº de sequência." |

Nota: com só um caminho no overlay, o atraso e as perdas fazem subir o custo mas a Origem não pode mudar; a mudança de rota mostra-se na Topologia 3.

---

# C. Topologia 3 — cenário completo

Overlay (`configs/overlay_topo3.json`): S1 = Server, S2 = Server2, O1 = PC1, O2 = PC4, O3 = PC2, O4 = PC9, O5 = PC7. Vizinhos: S1–O1, S1–O2, S1–O3, S2–O2, S2–O4, S2–O5, O1–O2, O1–O3, O2–O3, O2–O4, O2–O5, O3–O4, O4–O5.

## C.0 Preparar

1. Abrir `Topologia/Topologia_test3.xml` no CORE → **Start** → esperar ~30 s (OSPF).
2. Testar a rede física: no terminal do **Bootstrapper**, `ping -c2 10.0.20.21` (PC8). Se não responder, o problema é do routing, não do código.
3. Em **cada terminal** (duplo clique no PC): `cd /volume/ESR-TP2/Projeto`

## C.1 Arrancar (por esta ordem)

**Overlay** (1.º argumento = IP do bootstrapper, 10.0.18.10):

| PC | Papel | Comando |
|---|---|---|
| **Bootstrapper** | bootstrapper | `python3 bootstrapper.py configs/overlay_topo3.json` |
| **Server** (10.0.18.20) | S1 | `python3 servidor.py 10.0.18.10 filmeA filmeB` |
| **Server2** (10.0.0.22) | S2 | `python3 servidor.py 10.0.18.10 filmeB filmeC` |
| **PC1** | O1 | `python3 onode.py 10.0.18.10` |
| **PC4** | O2 | `python3 onode.py 10.0.18.10` |
| **PC2** | O3 | `python3 onode.py 10.0.18.10` |
| **PC9** | O4 | `python3 onode.py 10.0.18.10` |
| **PC7** (10.0.0.21) | O5 | `python3 onode.py 10.0.18.10` |

**Clientes** (NÃO são nós do overlay; 1.º argumento = IP do **seu onode**, o da mesma LAN):

| PC | Liga-se a | Comando |
|---|---|---|
| **PC5** | O2 (PC4) | `python3 cliente.py 10.0.17.20 filmeA` |
| **PC3** | O3 (PC2) | `python3 cliente.py 10.0.19.21 filmeB` |
| **PC8** | O4 (PC9) | `python3 cliente.py 10.0.20.20 filmeC` |
| **PC6** | O5 (PC7) | `python3 cliente.py 10.0.0.21 filmeB` |

Sem janela: acrescentar `--sem-gui`.

## C.2 Comandos (escrever no terminal do próprio nó)

| Comando | Onde | Mostra |
|---|---|---|
| `rotas` | onodes e servidores | Fluxo, Origem, Métrica, Saltos, Destinos (vizinhos e `cliente:IP`), Estado, Alternativas |
| `vizinhos` | onodes e servidores | vizinhos, RTT, perdas, carga e decomposição do custo de cada ligação |
| `ping` | servidor | PING pelos fluxos ativos; cada nó escreve o caminho no seu terminal |
| `play filmeC` / `stop` | cliente | muda de stream / pára |
| `sair` (ou Ctrl+C) | todos | sai avisando os vizinhos (ADEUS) / o onode (PARAR) |

## C.3 Guião (o que mostrar e o que dizer)

**Opcional, mas ajuda muito:** num terminal do **contentor** (o mesmo do `docker exec`, não num PC do CORE), correr

```bash
cd /volume/ESR-TP2/Projeto && python3 tools/arvore.py --core --watch 2
```

Este terminal mostra, de 2 em 2 s (só lê o estado local de cada nó com `vcmd`; não gera tráfego na rede), a árvore de cada servidor (Origem, custo e alternativas de cada nó) e os fluxos que estão a passar, juntando o que cada nó sabe. Deixá-lo à vista durante os passos 6, 11, 12 e 13 para se ver a árvore mudar. Para gerar figuras: `--dot arvore` (precisa de `apt install -y graphviz` no contentor).

| # | Fazer | O que se vê | O que dizer |
|---|---|---|---|
| 1 | Arrancar bootstrapper e onodes | `Registado como O3 ...; vizinhos: ...` | "O bootstrapper só dá a cada onode o nome e os vizinhos; depois não intervém." |
| 2 | Arrancar os clientes | cliente: `Onode 10.0.19.21: a enviar` | "O cliente só conhece o seu onode; não sabe nada de rotas." |
| 3 | `rotas` no PC2 (O3) | Origem para S1 e S2; `cliente:10.0.19.20` nos Destinos | "Cada onode só sabe por que vizinho chega a cada servidor e com que custo; não conhece o caminho. O onode escolhe o servidor pelo cliente." |
| 4 | `rotas` no PC4 (O2) | um fluxo com 2+ Destinos | "Recebe uma cópia e replica-a: é a árvore de distribuição." |
| 5 | `ping` no Server (S1) | caminho em cada terminal: `S1 > O3`, ... | Etapa 3. |
| 6 | `rotas` no PC9 (O4) e ver a Origem do fluxo em uso → **Ctrl+C nesse relay** | a Origem do O4 muda; o cliente do PC8 continua a ver; noutros nós pode aparecer `custo infinito` | "Falha de um nó intermédio: escolhe-se outra Origem viável; quem fica sem alternativa anuncia custo infinito (route poisoning)." |
| 7 | Voltar a arrancar esse relay | `Vizinho ... ligado` | "Volta a entrar sozinho." |
| 8 | **Ctrl+C no PC2 (O3)**, o onode do cliente do PC3 | cliente: `o onode não responde`, fps=0 | "O cliente só conhece este onode: se ele morre, o cliente fica sem vídeo..." |
| 9 | Voltar a arrancar o O3 | cliente: `a enviar`, vídeo volta | "...e quando volta, o vídeo volta sozinho (o cliente continua a pedir de 1 em 1 s)." |
| 10 | `vizinhos` no PC9 (O4) | coluna "Custo da ligação" = 1 + 2×A + 3×P + 1×C | "A métrica pondera salto, atraso (RTT local, pelo ALIVE), perdas (medidas com o próprio vídeo) e carga; não usa pacotes extra." |
| 11 | Duplo clique na ligação **PC4–s5** (o acesso do O2) → **Delay 40000 µs** | ao fim de 1–2 heartbeats (10–20 s), em `vizinhos` no PC9 o custo da ligação ao O2 sobe para 1 + 2×8 = 17 e em `rotas` a Origem do O4 para o S1 passa de O2 para O3 | "O atraso pesa 2 por cada 10 ms de RTT." |
| 12 | Na mesma ligação: Delay 0 e **Loss 20%** | ao fim de ~10 s, em `vizinhos` no PC9, Perdas ≈ 20% e o custo sobe 3×4; a Origem continua longe do O2 | "As perdas medem-se pelas lacunas no nº de sequência de cada ligação." |
| 13 | **Ctrl+C no Server (S1)** | o cliente do PC3 (filmeB, via O3) passa a receber do S2 (nas STATS muda a `fonte`, o SSRC, e `trocas` sobe; o cliente não sabe qual é o servidor); o cliente do PC6 (filmeB, via O5) já recebia do S2 e nem dá por isso | "O filmeB está nos dois servidores; cada onode escolhe o mais perto e, se esse morre, muda para o outro." |
| 14 | `stop` num cliente | `poda` nos terminais acima; em `rotas`, `inativa` | "Sem clientes não há tráfego." |
| 15 | (opcional) Wireshark num relay, filtro `udp.port==6001` | 1 fluxo a entrar, N a sair | prova de que não há marosca |
| 16 | Wireshark no PC1 (O1), filtro `ip.addr==10.0.18.21 && ip.addr==10.0.19.21` (ligação O1–O3, sem fluxo) | só `ALIVE`/`ALIVE_RESP` e `ANUNCIO`, a cada 10 s; nenhum pacote UDP 6001 | "Onde não há fluxo só passa o heartbeat previsto; tudo o resto é por eventos." |

---

# Se algo correr mal (todos os cenários)

| Sintoma | Causa provável | Resolver |
|---|---|---|
| `Bootstrapper ... indisponível` | bootstrapper ainda não arrancou, IP errado ou rede sem routing | arrancar o bootstrapper; confirmar o IP (10.0.0.23 / 10.0.6.20 / 10.0.18.10) e testar `ping` para ele |
| cliente: `o onode não responde` | o onode desse cliente não está a correr, ou IP errado | arrancar o onode; confirmar o IP na tabela acima |
| cliente: `nenhum servidor tem esta stream` | rotas ainda a convergir ou nome da stream errado | esperar 2-3 s; streams: filmeA, filmeB, filmeC |
| `Address already in use` | já há um programa a correr nesse PC | `pkill -f "onode.py\|servidor.py\|cliente.py"` |
| `no display name` (cliente) | terminal sem acesso ao ecrã | `export DISPLAY=:0` ou usar `--sem-gui` |
| `recusou o registo` | o IP do PC não está no `configs/overlay_topoN.json` do cenário | só onodes/servidores se registam; confirmar o PC |
