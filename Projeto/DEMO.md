# Cábula da demonstração — Topologia 3

## 0. Preparar

1. Abrir `Topologia/Topologia_test3.xml` no CORE → **Start** → esperar ~30 s (OSPF).
2. Testar a rede física: no terminal do **Bootstrapper**, `ping -c2 10.0.20.21` (PC8). Se não responder, o problema é do routing, não do código.
3. Em **cada terminal** (duplo clique no PC): `cd /volume/ESR-TP2/Projeto`

## 1. Arrancar (por esta ordem)

**Overlay** (1.º argumento = IP do bootstrapper, 10.0.18.10):

| PC | Papel | Comando |
|---|---|---|
| **Bootstrapper** | bootstrapper | `python3 bootstrapper.py configs/overlay_topo3.json` |
| **Server** | S1 | `python3 servidor.py 10.0.18.10 filmeA filmeB` |
| **PC6** | S2 | `python3 servidor.py 10.0.18.10 filmeB filmeC` |
| **PC1** | O1 | `python3 onode.py 10.0.18.10` |
| **PC4** | O2 | `python3 onode.py 10.0.18.10` |
| **PC2** | O3 | `python3 onode.py 10.0.18.10` |
| **PC9** | O4 | `python3 onode.py 10.0.18.10` |

**Clientes** (NÃO são nós do overlay; 1.º argumento = IP do **seu onode**, o da mesma LAN):

| PC | Liga-se a | Comando |
|---|---|---|
| **PC5** | O2 (PC4) | `python3 cliente.py 10.0.17.20 filmeA` |
| **PC3** | O3 (PC2) | `python3 cliente.py 10.0.19.21 filmeB` |
| **PC8** | O4 (PC9) | `python3 cliente.py 10.0.20.20 filmeC` |
| **PC7** | S2 (PC6) | `python3 cliente.py 10.0.0.20 filmeB` |

Sem janela: acrescentar `--sem-gui`.

## 2. Comandos (escrever no terminal do próprio nó)

| Comando | Onde | Mostra |
|---|---|---|
| `rotas` | onodes e servidores | Fluxo, Origem, Métrica, Saltos, Destinos (vizinhos e `cliente:IP`), Estado, Alternativas |
| `vizinhos` | onodes e servidores | vizinhos, ligado/desligado, RTT |
| `ping` | servidor | PING pelos fluxos ativos; cada nó escreve o caminho no seu terminal |
| `play filmeC` / `stop` | cliente | muda de stream / pára |
| `sair` (ou Ctrl+C) | todos | sai avisando os vizinhos (ADEUS) / o onode (PARAR) |

## 3. Guião (o que mostrar e o que dizer)

| # | Fazer | O que se vê | O que dizer |
|---|---|---|---|
| 1 | Arrancar bootstrapper e onodes | `Registado como O3 ...; vizinhos: ...` | "O bootstrapper só dá a cada onode o nome e os vizinhos; depois não intervém." |
| 2 | Arrancar os clientes | cliente: `Onode 10.0.19.21: a enviar` | "O cliente só conhece o seu onode; não sabe nada de rotas." |
| 3 | `rotas` no PC2 (O3) | Origem para S1 e S2; `cliente:10.0.19.20` nos Destinos | "O onode escolhe o servidor e o caminho pelo cliente." |
| 4 | `rotas` no PC4 (O2) | um fluxo com 2+ Destinos | "Recebe uma cópia e replica-a: é a árvore de distribuição." |
| 5 | `ping` no Server (S1) | caminho em cada terminal: `S1 > O3`, ... | Etapa 3. |
| 6 | `rotas` no PC9 (O4) e ver a Origem do fluxo em uso → **Ctrl+C nesse relay** | a Origem do O4 muda; o cliente do PC8 continua a ver | "Falha de um nó intermédio: a rota muda sozinha (ADEUS, desvio imediato)." |
| 7 | Voltar a arrancar esse relay | `Vizinho ... ligado` | "Volta a entrar sozinho." |
| 8 | **Ctrl+C no PC2 (O3)**, o onode do cliente do PC3 | cliente: `o onode não responde`, fps=0 | "O cliente só conhece este onode: se ele morre, o cliente fica sem vídeo..." |
| 9 | Voltar a arrancar o O3 | cliente: `a enviar`, vídeo volta | "...e quando volta, o vídeo volta sozinho (o cliente continua a pedir de 1 em 1 s)." |
| 10 | Duplo clique numa ligação usada (ex.: R1–R3) → **Delay 40000 µs** | ao fim de ~5 s a Origem muda em `rotas` | "A métrica é 1 por salto + 1 por cada 5 ms de atraso, medido com ALIVE." |
| 11 | **Ctrl+C no Server (S1)** | o cliente do PC3 (filmeB) passa a receber do S2 (`trocas` nas STATS) | "O filmeB está nos dois servidores; o onode muda para o outro." |
| 12 | `stop` num cliente | `poda` nos terminais acima; em `rotas`, `inativa` | "Sem clientes não há tráfego." |
| 13 | (opcional) Wireshark num relay, filtro `udp.port==6001` | 1 fluxo a entrar, N a sair | prova de que não há marosca |

## 4. Se algo correr mal

| Sintoma | Causa provável | Resolver |
|---|---|---|
| `Bootstrapper ... indisponível` | bootstrapper ainda não arrancou ou rede sem routing | arrancar o bootstrapper; testar `ping 10.0.18.10` |
| cliente: `o onode não responde` | o onode desse cliente não está a correr, ou IP errado | arrancar o onode; confirmar o IP na tabela acima |
| cliente: `nenhum servidor tem esta stream` | rotas ainda a convergir ou nome da stream errado | esperar 2-3 s; streams: filmeA, filmeB, filmeC |
| `Address already in use` | já há um programa a correr nesse PC | `pkill -f "onode.py\|servidor.py\|cliente.py"` |
| `no display name` (cliente) | terminal sem acesso ao ecrã | `export DISPLAY=:0` ou usar `--sem-gui` |
| `recusou o registo` | o IP do PC não está em `configs/overlay_topo3.json` | só onodes/servidores se registam; confirmar o PC |
