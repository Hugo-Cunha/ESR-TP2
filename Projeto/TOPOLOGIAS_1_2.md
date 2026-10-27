# Topologias 1 e 2 — como correr

Em cada terminal (duplo clique no PC): `cd /volume/ESR-TP2/Projeto`. Arrancar por esta ordem: bootstrapper → servidores → onodes → clientes.

Nestas topologias não há um PC livre só para o bootstrapper, por isso ele corre no **PC do cliente** (o cliente gasta pouco CPU; o professor não quer o bootstrapper num servidor).

---

## Topologia 1 — `Topologia_test1.xml` (uma LAN, 1 switch)

| PC | IP | Papel | Comando |
|---|---|---|---|
| **PC2** | 10.0.0.21 | bootstrapper | `python3 bootstrapper.py configs/overlay_topo1.json` |
| **Server** | 10.0.0.22 | S1 (filmeA, filmeB) | `python3 servidor.py 10.0.0.21 filmeA filmeB` |
| **PC1** | 10.0.0.20 | O1 (onode) | `python3 onode.py 10.0.0.21` |
| **PC2** | 10.0.0.21 | cliente, ligado ao O1 | `python3 cliente.py 10.0.0.20 filmeA` |

Overlay: `S1 — O1 — cliente`. Serve para mostrar o básico: registo, ligação entre vizinhos, rota, PING (`ping` no Server) e vídeo a passar por um nó intermédio.

**Testes rápidos**
- `rotas` no PC1 → `S1/filmeA  Origem S1 ... cliente:10.0.0.21  ativa`
- Ctrl+C no PC1 → o cliente fica sem vídeo (`o onode não responde`); voltar a arrancar → o vídeo volta.
- `stop` no cliente → `poda` no PC1; `rotas` no Server mostra `inativa`.

---

## Topologia 2 — `Topologia_test2.xml` (3 routers)

| PC | IP | Papel | Comando |
|---|---|---|---|
| **PC2** | 10.0.5.20 | bootstrapper | `python3 bootstrapper.py configs/overlay_topo2.json` |
| **Server1** | 10.0.1.20 | S1 (filmeA, filmeB) | `python3 servidor.py 10.0.5.20 filmeA filmeB` |
| **PC1** | 10.0.0.20 | S2 (filmeB, filmeC) | `python3 servidor.py 10.0.5.20 filmeB filmeC` |
| **PC2** | 10.0.5.20 | cliente, ligado ao S2 | `python3 cliente.py 10.0.0.20 filmeA` |

Overlay: `S1 — S2 — cliente` (o S2 também é onode e reencaminha).

**Testes rápidos**
- **Reencaminhamento entre servidores:** o cliente pede o `filmeA`, que só o S1 tem → o S2 recebe-o do S1 e passa-o ao cliente. `rotas` no PC1 mostra `S1/filmeA  Origem S1 ... cliente:10.0.5.20  ativa`.
- **Escolha do servidor:** no cliente, `play filmeB` → como o S2 também tem o filmeB, é ele próprio a servi-lo (custo 0).
- **Falha de servidor:** com o cliente a ver o `filmeB`... não muda (o S2 é o onode dele). Para ver a mudança: o cliente vê `filmeA` (do S1); Ctrl+C no Server1 → o cliente fica sem vídeo (`nenhum servidor tem esta stream`); voltar a arrancar o S1 → o vídeo volta.
- **Atraso:** pôr Delay numa ligação entre routers no caminho S1–S2 e ver o custo a subir em `rotas` no PC1.
