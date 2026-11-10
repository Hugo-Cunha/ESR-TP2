# Árvores de distribuição na Topologia 3

Nenhum onode conhece a árvore. Cada um guarda, por servidor, só a sua **Origem** (o vizinho de quem recebe) e o custo. A árvore é a união das Origens de todos os nós; vê-se juntando a coluna Origem da tabela `rotas` de cada nó, ou com o `ping`.

Para ver estas árvores ao vivo: `python3 tools/arvore.py --core --watch 2` na shell do contentor do CORE (ou `--dot arvore` para gerar uma figura por servidor).

Os custos abaixo são para a rede em repouso: todas as ligações custam 1 (sem atraso, perdas nem carga), por isso custo = nº de saltos. Em caso de empate ganha o menor nº de saltos e depois o menor IP.

## Overlay

| Nó | PC | IP | Vizinhos |
|---|---|---|---|
| S1 | Server | 10.0.18.20 | O1, O2, O3 |
| S2 | Server2 | 10.0.0.22 | O2, O4, O5 |
| O1 | PC1 | 10.0.18.21 | S1, O2, O3 |
| O2 | PC4 | 10.0.17.20 | S1, S2, O1, O3, O4, O5 |
| O3 | PC2 | 10.0.19.21 | S1, O1, O2, O4 |
| O4 | PC9 | 10.0.20.20 | S2, O2, O3, O5 |
| O5 | PC7 | 10.0.0.21 | S2, O2, O4 |

Clientes: PC5 → O2, PC3 → O3, PC8 → O4, PC6 → O5.

---

## 1. Árvore do S1 (filmeA, filmeB)

**Árvores possíveis:** cada linha diz os pais que cada nó pode ter. São os candidatos que aparecem na coluna "Alternativas" da tabela `rotas`. O split horizon exclui os vizinhos que recebem deste nó.

| Nó | Candidatos (vizinho: custo) | Origem escolhida | Porquê |
|---|---|---|---|
| O1 | **S1: 1**, O2: 2, O3: 2 | S1 | menor custo |
| O2 | **S1: 1**, O1: 2, O3: 2 | S1 | menor custo |
| O3 | **S1: 1**, O2: 2, O1: 2, O4: 3 | S1 | menor custo |
| O4 | **O2: 2**, O3: 2, O5: 3, S2: 3 | O2 | empate O2/O3 (custo 2) → menor IP (10.0.17.20 < 10.0.19.21) |
| O5 | **O2: 2**, S2: 3, O4: 3 | O2 | menor custo |
| S2 | **O2: 2**, O5: 3, O4: 3 | O2 | menor custo |

**Árvore usada:**

```
S1 ─┬─ O1
    ├─ O2 ─┬─ O4
    │      ├─ O5
    │      └─ S2
    └─ O3
```

A única outra árvore com o mesmo custo é a que pendura o O4 no O3 em vez do O2.

## 2. Árvore do S2 (filmeB, filmeC)

| Nó | Candidatos (vizinho: custo) | Origem escolhida | Porquê |
|---|---|---|---|
| O2 | **S2: 1**, O5: 2, O4: 2 | S2 | menor custo |
| O4 | **S2: 1**, O5: 2, O2: 2, O3: 3 | S2 | menor custo |
| O5 | **S2: 1**, O2: 2, O4: 2 | S2 | menor custo |
| O1 | **O2: 2**, S1: 3, O3: 3 | O2 | menor custo |
| O3 | **O2: 2**, O4: 2, S1: 3, O1: 3 | O2 | empate O2/O4 (custo 2) → menor IP (10.0.17.20 < 10.0.20.20) |
| S1 | **O2: 2**, O1: 3, O3: 3 | O2 | menor custo |

**Árvore usada:**

```
S2 ─┬─ O2 ─┬─ O1
    │      ├─ O3
    │      └─ S1
    ├─ O4
    └─ O5
```

A única outra árvore com o mesmo custo pendura o O3 no O4 em vez do O2.

---

## 3. O que passa realmente na rede (árvore podada)

As árvores acima são **potenciais**: o vídeo só desce pelos ramos que têm clientes (ATIVAR/poda). Cada cliente pede uma stream ao seu onode, e esse onode escolhe o servidor de menor custo que a tem.

**a) Clientes da demo** (PC5 filmeA, PC3 filmeB, PC8 filmeC, PC6 filmeB):

| Cliente | Onode | Stream | Servidor escolhido | Ramo ativo |
|---|---|---|---|---|
| PC5 | O2 | filmeA | S1 (o único que a tem) | S1 → O2 |
| PC3 | O3 | filmeB | S1 (custo 1; o S2 custa 2) | S1 → O3 |
| PC8 | O4 | filmeC | S2 (o único que a tem) | S2 → O4 |
| PC6 | O5 | filmeB | S2 (custo 1; o S1 custa 2) | S2 → O5 |

Cada cliente fica a 1 salto do servidor. É a vantagem de ter o filmeB nos dois servidores: cada onode vai buscá-lo ao mais próximo.

**b) Os 4 clientes a ver o filmeA** (é o teste T2; só o S1 tem o filmeA):

```
S1 ─┬─ O2 ─┬─ PC5 (cliente local)
    │      ├─ O4 ── PC8
    │      └─ O5 ── PC6
    └─ O3 ── PC3
```

O S1 envia **2 cópias** (O2 e O3) para 4 clientes. O O1 e o S2 não recebem nada, porque não têm clientes deste fluxo (foram podados).

---

## 4. Como a árvore muda (monitorização)

A árvore não é fixa: cada nó volta a escolher a Origem sempre que chega um anúncio (a cada heartbeat, 10 s) e sempre que um vizinho cai ou volta. Três situações:

**a) Atraso de 40 ms em cada sentido no acesso do O2** (ligação PC4–s5): todas as ligações do O2 passam a ter RTT 80 ms, ou seja, custo 1 + 2×8 = 17.

| Nó | Antes | Depois | Porquê |
|---|---|---|---|
| O2 | S1 (1) | S1 (17) | todas as ligações do O2 custam 17; pelo S1 continua a ser o mais barato |
| O4 | O2 (2) | O3 (2) | via O2 custaria 1 + 17 = 18 |
| O5 | O2 (2) | O4 (3) | via O2 custaria 18 |
| S2 | O2 (2) | O4 (3) | idem |

```
S1 ─┬─ O1
    ├─ O2
    └─ O3 ── O4 ─┬─ O5
                 └─ S2
```

O vídeo foge do O2: só o cliente do próprio O2 continua a recebê-lo por ele.

**b) O O2 morre** (árvore do S1):

```
S1 ─┬─ O1
    └─ O3 ── O4 ─┬─ O5
                 └─ S2
```

O O4 passa para o O3; o O5 e o S2 perdem a Origem e passam a receber pelo O4, com custo 3.

**c) O O2 volta:** volta a anunciar-se. Os seus anúncios trazem um número de sequência novo e um custo menor, por isso voltam a ser viáveis, e cada nó regressa à árvore da secção 1 (a melhor). O teste T11 verifica isto: O2 morre → O4 passa para O3 → O2 volta → O4 regressa ao O2, com 53 ms de falha no cliente.

*(Os valores das secções 1, 2 e 4 foram calculados com as mesmas regras do código; os de 3b e 4c foram confirmados nos testes T2 e T11.)*
