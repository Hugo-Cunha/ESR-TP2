# Cábula da demonstração — Topologia 3

## 0. Preparar

1. Abrir `Topologia/Topologia_test3.xml` no CORE → **Start** → esperar ~30 s (OSPF).
2. Testar a rede física: no terminal do **Bootstrapper**, `ping -c2 10.0.20.21` (PC8). Se não responder, o problema é do routing, não do código.
3. Em **cada terminal** (duplo clique no PC): `cd /volume/ESR-TP2/Projeto`

## 1. Arrancar (por esta ordem)

| PC | Papel | Comando |
|---|---|---|
| **Bootstrapper** | bootstrapper | `python3 bootstrapper.py configs/overlay_topo3.json` |
| **Server** | S1 | `python3 servidor.py 10.0.18.10 filmeA filmeB` |
| **PC6** | S2 | `python3 servidor.py 10.0.18.10 filmeB filmeC` |
| **PC1** | O1 | `python3 onode.py 10.0.18.10` |
| **PC4** | O2 | `python3 onode.py 10.0.18.10` |
| **PC2** | O3 | `python3 onode.py 10.0.18.10` |
| **PC9** | O4 | `python3 onode.py 10.0.18.10` |
| **PC5** | C1 | `python3 cliente.py 10.0.18.10 filmeA` |
| **PC3** | C2 | `python3 cliente.py 10.0.18.10 filmeB` |
| **PC8** | C3 | `python3 cliente.py 10.0.18.10 filmeC` |
| **PC7** | C4 | `python3 cliente.py 10.0.18.10 filmeB` |

Regra: o 1.º argumento é sempre o **IP do bootstrapper** (10.0.18.10). Os servidores recebem os **nomes das streams**; os clientes, a **stream que querem ver**. Sem janela: acrescentar `--sem-gui` ao cliente.

## 2. Comandos (escrever no terminal do próprio nó)

| Comando | Onde | Mostra |
|---|---|---|
| `rotas` | qualquer nó | Fluxo, Origem, Métrica, Saltos, Destinos, Estado, Alternativas |
| `vizinhos` | qualquer nó | vizinhos, ligado/desligado, RTT |
| `ping` | servidor | PING pelos fluxos ativos; cada nó escreve o caminho no seu terminal |
| `play filmeC` / `stop` | cliente | muda de stream / pára |
| `sair` (ou Ctrl+C) | qualquer nó | sai do overlay avisando os vizinhos (ADEUS) |

## 3. Guião (o que mostrar e o que dizer)

| # | Fazer | O que se vê | O que dizer |
|---|---|---|---|
| 1 | Arrancar o bootstrapper e os nós | `Registado como O3 ...; vizinhos: ...` | "O bootstrapper só dá a cada nó o nome e os vizinhos; depois não intervém." |
| 2 | `rotas` no PC2 (O3) | tabela com Origem para S1 e S2 | "Cada nó só sabe por que vizinho chega a cada servidor e com que custo." |
| 3 | `rotas` num relay com 2 clientes atrás | Destinos com 2 vizinhos | "Recebe uma cópia e replica-a: é a árvore de distribuição." |
| 4 | `ping` no Server (S1) | caminho em cada terminal: `S1 > O2 > C2` | Etapa 3. |
| 5 | `rotas` no PC3 (C2, a ver filmeB) | `S1/filmeB` e `S2/filmeB`, cada um com o seu custo; o usado fica `ativa` | "O filmeB está nos dois servidores; o cliente usa o de menor custo." |
| 6 | **Ctrl+C** no relay que um cliente usa | o cliente muda de caminho; STATS `maior_falha` ~50 ms | "Saída ordeira: ADEUS, desvio imediato." |
| 7 | Voltar a arrancar esse relay | `Vizinho ... ligado` | "Volta a entrar sozinho." |
| 8 | Duplo clique numa ligação usada (ex.: R1–R3) → **Delay 40000 µs** | ao fim de ~5 s a Origem muda em `rotas` | "A métrica é 1 por salto + 1 por cada 5 ms de atraso, medido com ALIVE." |
| 9 | **Ctrl+C** no servidor que o C2 está a usar (ver `servidor=` nas STATS do C2) | o C2 passa a receber o filmeB do outro servidor (`trocas=1`) | "Mudança automática de servidor." |
| 10 | `stop` num cliente | `poda` nos terminais acima; em `rotas`, `inativa` | "Sem clientes não há tráfego." |
| 11 | (opcional) Wireshark num relay, filtro `udp.port==6001` | 1 fluxo a entrar, N a sair | prova de que não há marosca |

## 4. Se algo correr mal

| Sintoma | Causa provável | Resolver |
|---|---|---|
| `Bootstrapper ... indisponível` | bootstrapper ainda não arrancou ou rede sem routing | arrancar o bootstrapper; testar `ping 10.0.18.10` |
| `Address already in use` | já há um programa do overlay nesse PC | `pkill -f "onode.py\|servidor.py\|cliente.py"` |
| `no display name` (cliente) | terminal sem acesso ao ecrã | `export DISPLAY=:0` ou usar `--sem-gui` |
| `recusou o registo` | o IP do PC não está em `configs/overlay_topo3.json` | confirmar o PC/IP |
