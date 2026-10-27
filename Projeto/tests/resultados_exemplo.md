| Teste | Resultado | Descrição |
|---|---|---|
| T1 | PASS | C1 a ver filmeA de S1: fps=20.0 perdas=0 caminho S1 > O1 > C1 |
| T1 | PASS | C2 a ver filmeB de S1: fps=20.0 perdas=0 caminho S1 > O2 > C2 |
| T1 | PASS | C3 a ver filmeC de S2: fps=20.0 perdas=0 caminho S2 > O4 > C3 |
| T1 | PASS | C4 a ver filmeB de S2: fps=20.0 perdas=0 caminho S2 > C4 |
| T2 | PASS | os 4 clientes recebem filmeA |
| T2 | PASS | S1 envia apenas 3 cópia(s) (O2,O1,O3) para 4 clientes |
| T3 | PASS | C1: S1 > O1 > C1  ->  S1 > O1 > C1 (maior falha 57ms) |
| T3 | PASS | C2: S1 > O2 > C2  ->  S1 > O3 > C2 (maior falha 57ms) |
| T3 | PASS | C3: S1 > O3 > C3  ->  S1 > O3 > C3 (maior falha 57ms) |
| T3 | PASS | C4: S1 > O2 > S2 > C4  ->  S1 > O3 > O4 > C4 (maior falha 100ms) |
| T4 | PASS | O1 saiu: C1 S1 > O1 > C1 -> S1 > O2 > C1, maior falha 55ms (o ADEUS evita esperar pelo timeout) |
| T4b | PASS | O1 congelado: C1 S1 > O1 > C1 -> S1 > O2 > C1, maior falha 2614ms (timeout de vizinho = 3,5 s) |
| T5 | PASS | O3 voltou e religou-se a 10 vizinhos sem intervenção do bootstrapper |
| T5 | PASS | C3: S1 > O3 > C3 -> S1 > O2 > O4 > C3 -> S1 > O3 > C3 |
| T6 | PASS | S1-O2 passa a 40 ms: C2 S1 > O2 > C2 -> S1 > O3 > C2 (mesmo nº de saltos, menor atraso) |
| T6 | PASS | atraso passa para S1-O3: C2 volta a S1 > O2 > C2 |
| T7 | PASS | cada cliente escolhe o servidor mais próximo: O1<-S1 (S1 > O1), C4<-S2 (S2 > C4) |
| T7 | PASS | S1 caiu: O1 passou para S2 (S2 > O2 > O1), maior falha 54ms |
| T8 | PASS | com cliente:  S1/filmeB      (local)       0      0 O3               ativa |
| T8 | PASS | sem cliente:   S1/filmeB      (local)       0      0 -                inativa |
| T8 | PASS | 15 mensagens de poda registadas ao longo do ramo |
