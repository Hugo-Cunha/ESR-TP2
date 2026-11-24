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
| **Server** (10.0.0.22) | S1 (filmeA, filmeB, movie) | `python3 servidor.py 10.0.0.23 filmeA filmeB movie` |
| **PC1** (10.0.0.20) | O1 | `python3 onode.py 10.0.0.23` |
| **PC2** (10.0.0.21) | cliente, ligado ao O1 | `python3 cliente.py 10.0.0.20 filmeA` |

## A.2 Guião

| # | Fazer | O que se vê | O que dizer |
|---|---|---|---|
| 1 | Arrancar bootstrapper, S1 e O1 | O1: `Registado como O1 ...; vizinhos: S1`; `Vizinho S1 ligado` | "O bootstrapper só dá a cada nó o nome e os vizinhos; depois não intervém." |
| 2 | Arrancar o cliente | janela com o vídeo; cliente: `Onode 10.0.0.20: a enviar` | "O cliente só conhece o seu onode." |
| 3 | `arvore` no PC1 (O1) | `S1/filmeA  ATIVO  S1  cliente 10.0.0.21` | "O O1 só sabe quem é o seu pai (o S1) e quem são os seus filhos (o cliente)." |
| 4 | `rotas` no Server (S1) | `S1/filmeA  (local) ... O1  ativa`; `S1/filmeB ... inativa` | "O servidor só envia o que alguém pediu: o filmeB não sai." |
| 5 | `ping` no Server | O1 escreve o caminho `S1 > O1` | Etapa 3. |
| 6 | **Ctrl+C no PC1** (O1) | cliente: `Sem vídeo de 'filmeA' há 1 s` e `o onode não responde` | "Se o onode do cliente morre, o cliente fica sem vídeo..." |
| 7 | Voltar a arrancar o O1 | cliente: `A receber 'filmeA' (vídeo parado durante ...)` | "...e quando volta, o vídeo volta sozinho (o cliente pede de 1 em 1 s)." |
| 8 | `play filmeB` no cliente | o vídeo muda; `rotas` no Server: filmeA `inativa`, filmeB `ativa` | "Mudança de stream: o ramo antigo é podado." |
| 9 | `stop` no cliente | PC1: `INATIVO (sem filhos): poda enviada ao pai S1`; Server: `deixo de enviar` | "Sem clientes não há tráfego." |

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
| **Server1** (10.0.1.20) | S1 (filmeA, filmeB, movie) | `python3 servidor.py 10.0.6.20 filmeA filmeB movie` |
| **PC1** (10.0.0.20) | S2 (filmeB, filmeC) | `python3 servidor.py 10.0.6.20 filmeB filmeC` |
| **PC2** (10.0.5.20) | cliente, ligado ao S2 | `python3 cliente.py 10.0.0.20 filmeA` |

## B.2 Guião

| # | Fazer | O que se vê | O que dizer |
|---|---|---|---|
| 1 | Arrancar bootstrapper, S1 e S2 | `Vizinho S1 ligado` / `Vizinho S2 ligado` | "Dois servidores; o S2 também é um onode." |
| 2 | Arrancar o cliente (filmeA) | vídeo; cliente: `a enviar` | — |
| 3 | `arvore` no PC1 (S2) | `S1/filmeA  ATIVO  S1  cliente 10.0.5.20` | "Só o S1 tem o filmeA: o S2 recebe-o do S1 e passa-o ao cliente, como qualquer onode." |
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
| **Server** (10.0.18.20) | S1 | `python3 servidor.py 10.0.18.10 filmeA filmeB movie` |
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
| **PC8** | O4 (PC9) | `python3 cliente.py 10.0.20.20 filmeA` |
| **PC6** | O5 (PC7) | `python3 cliente.py 10.0.0.21 filmeB` |

Sem janela: acrescentar `--sem-gui`.

O S1 também tem o `movie` (o `movie.Mjpeg` do livro, que o enunciado manda usar): em qualquer cliente, `play movie`.

O PC8 vê o **filmeA**, que só existe no S1: chega ao O4 pelo O2 (S1 → O2 → O4), por isso há um relay a replicar e um relay para matar no passo 6. Com o filmeC o vídeo viria direto do S2.

## C.2 Comandos (escrever no terminal do próprio nó)

| Comando | Onde | Mostra |
|---|---|---|
| `arvore` | onodes e servidores | **o essencial**: para cada filme, se está ATIVO, quem é o **pai** e quem são os **filhos** |
| `rotas` | onodes e servidores | a tabela do enunciado: Fluxo, Origem, Métrica, Saltos, Destinos, Estado, Alternativas |
| `vizinhos` | onodes e servidores | RTT, perdas, carga e decomposição do custo de cada ligação |
| `ping` | servidor | PING pelos fluxos ativos; cada nó escreve o caminho no seu terminal |
| `play <filme>` / `stop` | cliente | muda de filme / pára |
| `sair` (ou Ctrl+C) | todos | sai avisando os vizinhos (ADEUS) / o onode (PARAR) |

**O que os terminais escrevem sozinhos** (só eventos, sem médias):

| Nó | Linhas | Quando |
|---|---|---|
| onode/servidor | `Árvore S1: pai O2 -> O3 (custo 2)` | mudou o vizinho por onde chega ao S1 |
| onode/servidor | `S1/filmeA: ATIVO, pedido ao pai O2` · `S1/filmeA: troca de pai O2 -> O3` | o fluxo passou a ser preciso / mudou de pai |
| onode/servidor | `S1/filmeA: novo filho O4` · `S1/filmeA: o filho O4 saiu (poda)` | um vizinho pediu / deixou de pedir o fluxo |
| onode/servidor | `S1/filmeA: INATIVO (sem filhos): poda enviada ao pai O2` | ninguém abaixo precisa do fluxo |
| onode | `Em perigo para S1 ...` · `Reserva: se O3 cair, ligo-me a S1` · `a abrir ligação de recurso` | falhas duplas (extra) |
| cliente | `A receber 'filmeA'` · `Sem vídeo de 'filmeA' há 1 s` · `A receber 'filmeA' (vídeo parado durante 2.2 s)` · `A stream passou a vir de outra fonte` | só quando o estado muda |

## C.3 Guião (o que mostrar e o que dizer)

**Num terminal do contentor** (o do `docker exec`, não num PC do CORE), deixar à vista durante toda a demo:

```bash
cd /volume/ESR-TP2/Projeto && python3 tools/arvore.py --core --watch 2
```

Mostra, de 2 em 2 s, a árvore de cada servidor juntando o que cada nó sabe (só lê o estado local de cada nó com `vcmd`; não gera tráfego na rede). Para gerar figuras: `--dot arvore` (precisa de `apt install -y graphviz`).

**Ideia a repetir:** o trabalho é sobre **árvores**. O vídeo desce pela árvore de cada servidor (overlay, "por cima"); a latência e as perdas medem-se na rede física ("por baixo"); onde não há filhos, não passa vídeo.

### Parte 1 — A árvore constrói-se a pedido

Arrancar bootstrapper, servidores e onodes, **ainda sem clientes**.

| # | Fazer | O que se vê | O que dizer |
|---|---|---|---|
| 1 | `arvore` no PC4 (O2) | todos os filmes `inativo`; já há pai para cada servidor (S1 e S2) | "A árvore potencial já existe (cada nó sabe o seu pai para cada servidor), mas nada flui: não há filhos." |
| 2 | Wireshark no Server (S1), filtro `udp.port==6001` | **nenhum** pacote | "Sem clientes, zero vídeo." |
| 3 | Arrancar o **PC8** (filmeA) | PC9 (O4): `S1/filmeA: ATIVO, pedido ao pai O2`; PC4 (O2): `novo filho O4`; Server: `novo filho O2`; Wireshark: começa o vídeo | "O pedido sobe pela árvore, de pai em pai, até ao servidor (ATIVAR, como o join do PIM-SM)." |
| 4 | Arrancar o **PC5** (filmeA, no próprio O2) | PC4: `arvore` → filhos `O4, cliente ...`; o Server **não** escreve nada novo | "O O2 já recebia: só junta um filho. O S1 continua a enviar uma cópia." |
| 5 | Arrancar o **PC3** e o **PC6** (filmeB) | PC2 (O3) recebe do S1, PC7 (O5) recebe do S2 | "O filmeB está nos dois servidores; cada onode escolhe o de menor custo." |
| 6 | `ping` no Server (S1) | cada nó escreve o caminho (`S1 > O2 > O4`) | Etapa 3. |

### Parte 2 — Desativar e trocar

| # | Fazer | O que se vê | O que dizer |
|---|---|---|---|
| 7 | `stop` no PC8 | PC9: `INATIVO (sem filhos): poda enviada ao pai O2`; PC4: `o filho O4 saiu (poda)`; o O2 continua ATIVO (tem o PC5) | "A poda sobe só até onde ainda há filhos." |
| 8 | `stop` no PC5 | PC4: `INATIVO ... poda enviada ao pai S1`; Server: `S1/filmeA: INATIVO (sem filhos): deixo de enviar`; Wireshark no Server: o filmeA pára | "Se em cima ninguém precisa, não pode haver dados a fluir." |
| 9 | `play filmeA` no PC8 e no PC5 | volta tudo ao passo 4 | — |
| 10 | Ligação **PC4–s5** (acesso do O2) → **Delay 40000 µs** | ao fim de 10–20 s, PC9: `Árvore S1: pai O2 -> O3` e `S1/filmeA: troca de pai O2 -> O3`; o PC5 continua no O2 | "A latência mede-se por baixo (RTT do ALIVE) e muda a árvore por cima: 1 + 2×8 = 17 pelo O2 contra 2 pelo O3." |
| 11 | Delay 0 | PC9: `pai O3 -> O2` | "Volta à melhor rota quando ela recupera." |
| 12 | (opcional) **Loss 20%** e depois 0 | o mesmo, com as perdas (secção C.4) | "As perdas medem-se com o próprio vídeo; o hold-down evita voltar logo." |

### Parte 3 — Mortes, até à catastrófica

| # | Fazer | O que se vê | O que dizer |
|---|---|---|---|
| 13 | **Ctrl+C no PC4 (O2)** | PC9: `troca de pai O2 -> O3` (o PC8 nem pára); PC5: `Sem vídeo` (era o onode dele); PC9: `Em perigo para S1 ... só me resta O3` e `Reserva: se O3 cair, ligo-me a S1` | "O O4 ficou só com um caminho: pergunta ao O3 **apenas** o próximo salto (ENDANGERED)." |
| 14 | **Ctrl+C no PC2 (O3)** — morte catastrófica | PC9: `fiquei sem pai`; 2 s depois `a abrir ligação de recurso a S1` e `troca`/`ATIVO, pedido ao pai S1`; PC8: `A receber 'filmeA' (vídeo parado durante ~2 s)`; o PC3 fica sem vídeo (o O3 era o onode dele) | "Com os dois caminhos mortos, o O4 liga-se à reserva. É o único caso em que um nó se liga a alguém que não é seu vizinho." |
| 15 | Voltar a arrancar o O2 e o O3 | PC9: `pai S1 -> O2`; `Ligação de recurso a S1 já não é precisa: a fechar`; `arvore` igual ao passo 5; PC5 e PC3 voltam a ver | "Pomos tudo de volta e a árvore volta a ser a original." |
| 16 | **Ctrl+C no Server (S1)** | PC3: `A stream passou a vir de outra fonte` (filmeB passa para o S2); PC8: `nenhum servidor tem esta stream` (só o S1 tinha o filmeA) | "O filmeB está replicado; o filmeA não." |
| 17 | Voltar a arrancar o S1 | o PC8 volta a ver (SSRC novo, o cliente recomeça sozinho) | — |

### Parte 4 — Tudo de volta, e as provas

| # | Fazer | O que se vê | O que dizer |
|---|---|---|---|
| 18 | `arvore` em todos os onodes | igual ao fim da Parte 1 | "Depois de todas as falhas, a rede volta ao estado inicial." |
| 19 | Wireshark no PC1 (O1), filtro `ip.addr==10.0.18.21 && ip.addr==10.0.19.21` (ligação O1–O3, sem filhos) | só `ALIVE`/`ALIVE_RESP` e `ANUNCIO`, a cada 10 s; nenhum UDP 6001 | "Onde não há fluxo só passa o heartbeat previsto." |
| 20 | Wireshark no PC4 (O2), `udp.port==6001` | 1 fluxo a entrar (do S1), 2 a sair (O4 e PC5) | "Uma cópia por ligação; o relay replica." |
| 21 | No contentor: `python3 tests/test_scenarios.py` e `python3 tests/test_falha_dupla.py` | todos os testes passam (Topologia 3 em loopback, ~15 min) | "Os mesmos cenários, automatizados." |

## C.4 Validação da métrica com `tc netem` (Tabela 6 do relatório)

Uma alteração de cada vez, no terminal do **PC4 (O2)**, com o PC8 a ver o filmeA. Depois de cada passo, esperar ~15 s e ver `vizinhos` e `rotas` no **PC9 (O4)**. O `netem` só atua à **saída** do PC4, por isso 40 ms dão RTT ≈ 41 ms (custo 1 + 2×4 = 9); no passo 11 do guião, o atraso do CORE aplica-se nos dois sentidos (RTT 80 ms, custo 17).

| Passo | Comando no PC4 | Esperado no PC9 |
|---|---|---|
| 0 | `tc qdisc show dev eth0` (não deve haver `netem`) | ligação ao O2 com custo 1 (2 com a carga do fluxo); `S1/filmeA` com Origem O2 (2) |
| 1 | `tc qdisc replace dev eth0 root netem delay 40ms` | RTT ao O2 ≈ 41 ms, custo 9; Origem do O4 passa a O3 (2); alternativa O2(18) |
| 2 | `tc qdisc replace dev eth0 root netem delay 80ms` | custo 17; alternativa O2(34) |
| 3 | `tc qdisc del dev eth0 root` | volta ao passo 0 (Origem O2) |
| 4 | `tc qdisc replace dev eth0 root netem loss 20%` | Perdas ≈ 20–30 %, custo ≈ 1 + 3×P; Origem passa a O3; com o *hold-down* (30 s) não volta logo ao O2 |
| 5 | `tc qdisc del dev eth0 root` | Perdas 0 %; a Origem regressa ao O2 e fica |

---

# Se algo correr mal (todos os cenários)

| Sintoma | Causa provável | Resolver |
|---|---|---|
| `Bootstrapper ... indisponível` | bootstrapper ainda não arrancou, IP errado ou rede sem routing | arrancar o bootstrapper; confirmar o IP (10.0.0.23 / 10.0.6.20 / 10.0.18.10) e testar `ping` para ele |
| cliente: `o onode não responde` | o onode desse cliente não está a correr, ou IP errado | arrancar o onode; confirmar o IP na tabela acima |
| cliente: `nenhum servidor tem esta stream` | rotas ainda a convergir ou nome da stream errado | esperar 2-3 s; streams: filmeA, filmeB, filmeC, movie |
| `Address already in use` | já há um programa a correr nesse PC | `pkill -f "onode.py\|servidor.py\|cliente.py"` |
| `no display name` (cliente) | terminal sem acesso ao ecrã | `export DISPLAY=:0` ou usar `--sem-gui` |
| `recusou o registo` | o IP do PC não está no `configs/overlay_topoN.json` do cenário | só onodes/servidores se registam; confirmar o PC |
