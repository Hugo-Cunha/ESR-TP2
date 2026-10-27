| Teste | Resultado | Descrição |
|---|---|---|
| T1 | PASS | C1 (onode O2) a ver filmeA do servidor S1: fps=20.0 perdas=0 |
| T1 | PASS | C2 (onode O3) a ver filmeB do servidor S1: fps=20.0 perdas=0 |
| T1 | PASS | C3 (onode O4) a ver filmeC do servidor S2: fps=20.0 perdas=0 |
| T1 | PASS | C4 (onode S2) a ver filmeB do servidor S2: fps=20.0 perdas=0 |
| T2 | PASS | os 4 clientes recebem o filmeA |
| T2 | PASS | o S1 envia só 2 cópia(s) (O2,O3) para 4 clientes |
| T3 | PASS | O4 passou a receber via O3; C3 continua a ver (maior falha 51ms) |
| T4 | PASS | O4 passou a receber via O3; maior falha no C3 55ms (sem esperar timeout) |
| T4b | PASS | O4 passou a receber via O3; maior falha no C3 2610ms |
| T5 | PASS | O3 morreu: C2 ficou sem vídeo (fps=0.0) e avisa que o onode não responde |
| T5 | PASS | O3 voltou (religou-se a 8 vizinhos): C2 volta a ver (fps=20.0) |
| T6 | PASS | ligação S1-O2 passa a 40 ms: O4 troca a Origem O2 -> O3 (mesmo nº de saltos, menos atraso) |
| T6 | PASS | o atraso passa para S1-O3: O4 volta à Origem O2 |
| T7 | PASS | cada onode escolhe o melhor servidor: C2 (via O3) <- S1, C4 (via S2) <- S2 |
| T7 | PASS | S1 caiu: C2 passou para S2 (trocas=1, maior falha 51ms) |
| T8 | PASS | com cliente: S1/filmeA      (local)       0      0 O2               ativa |
| T8 | PASS | sem cliente: S1/filmeA      (local)       0      0 -                inativa |
| T8 | PASS | 4 mensagens de poda registadas ao longo do ramo |
| T9 | PASS | perdas em S1->O2: O4 troca a Origem O2 -> O3; ligação vista por O2: 40.0% 0 25 = 1 + 2×0 + 3×8 + 1×0 |
| T10 | PASS | O2 morreu: o S2 recusou a rota velha (não viável), anunciou custo infinito=True e passou a receber via O4; maior falha no C4 101ms |
