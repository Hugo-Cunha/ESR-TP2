| Teste | Resultado | Descrição |
|---|---|---|
| T1 | PASS | C1 (onode O2) a ver filmeA do servidor S1: fps=20.0 perdas=0 |
| T1 | PASS | C2 (onode O3) a ver filmeB do servidor S1: fps=19.5 perdas=0 |
| T1 | PASS | C3 (onode O4) a ver filmeC do servidor S2: fps=20.0 perdas=0 |
| T1 | PASS | C4 (onode O5) a ver filmeB do servidor S2: fps=20.0 perdas=0 |
| T2 | PASS | os 4 clientes recebem o filmeA |
| T2 | PASS | o S1 envia só 2 cópia(s) (O3,O2) para 4 clientes |
| T3 | PASS | O4 passou a receber via O3; C3 continua a ver (maior falha 52ms) |
| T4 | PASS | O4 passou a receber via O3; maior falha no C3 52ms (sem esperar timeout) |
| T4b | PASS | O4 passou a receber via O3; maior falha no C3 14114ms |
| T5 | PASS | O3 morreu: C2 ficou sem vídeo (fps=0.0) e avisa que o onode não responde |
| T5 | PASS | O3 voltou (religou-se a 8 vizinhos): C2 volta a ver (fps=19.5) |
| T6 | PASS | ligação O4-O2 passa a 40 ms (custo 1 + 2×8): O4 troca a Origem O2 -> O3 |
| T6 | PASS | o atraso passa para O4-O3: O4 volta à Origem O2 |
| T7 | PASS | cada onode escolhe o melhor servidor: C2 (via O3) <- S1, C4 (via O5) <- S2 |
| T7 | PASS | S1 caiu: C2 passou para S2 (trocas=1, maior falha 54ms) |
| T8 | PASS | com cliente: S1/filmeA      (local)       0      0 O2               ativa |
| T8 | PASS | sem cliente: S1/filmeA      (local)       0      0 -                inativa |
| T8 | PASS | 4 mensagens de poda registadas ao longo do ramo |
| T9 | PASS | perdas em O2->O4: O4 troca a Origem O2 -> O3; ligação vista pelo O4: - 20.2% 0 13 = 1 + 2×0 + 3×4 + 1×0 |
| T9 | PASS | hold-down: em 20 s o O4 não volta a O2 (0 trocas de Origem) |
| T10 | PASS | O2 morreu: o O5 recusou a rota velha (não viável), anunciou custo infinito=True, pediu um anúncio novo ao servidor e passou a receber via O4; maior falha no C4 52ms |
| T11 | PASS | O2 morreu: O4 passou para a alternativa O3 |
| T11 | PASS | O2 voltou: O4 regressou à melhor Origem O2 (maior falha no C3 53ms) |
| T12 | PASS | ligação O1-O3 sem fluxo: 0 pacotes de vídeo em 30 s |
| T12 | PASS | ligação O1-O3 sem fluxo: 24 mensagens de controlo em 30 s (máximo previsto 24) |
| T13 | PASS | O2 morreu: o O4 ficou só com o O3, pediu-lhe o próximo salto (ENDANGERED) e guardou o S1 como reserva |
| T13 | PASS | O3 também morreu: o O4 abriu uma ligação de recurso ao S1 e os clientes do O4 e do O5 voltaram a ver (maior falha no C3 2156ms) |
| T13 | PASS | O2 e O3 voltaram: a árvore volta à original (O4 pelo O2) e a ligação de recurso fecha |
| Reparação | PASS | fora do T13, nenhuma ligação de recurso aberta na Topologia 3 (0) |
