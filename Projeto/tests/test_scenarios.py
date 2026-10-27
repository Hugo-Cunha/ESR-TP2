#!/usr/bin/env python3
"""Testes automáticos do overlay na Topologia 3 (sem CORE, tudo em 127.10.0.x).

Uso:
    python3 tests/test_scenarios.py [pasta_de_logs]

Cada teste arranca o overlay de raiz, provoca um evento (falha, saída,
atraso, ...) e verifica o comportamento pelas estatísticas dos clientes.
No fim é escrito um resumo em <pasta>/resultados.md (útil para o relatório).
"""

import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from local_overlay import LocalOverlay  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CFG = os.path.join(ROOT, "configs", "overlay_topo3.json")
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "tests", "logs")

results = []


def check(test, cond, desc):
    results.append((test, bool(cond), desc))
    print(f"  [{'PASS' if cond else 'FAIL'}] {desc}", flush=True)


def fnum(x):
    return float(re.sub(r"[^0-9.]", "", x or "0") or 0)


def table(o, name):
    """Pede a tabela de rotas ao nó e devolve-a (lida do log)."""
    o.cmd(name, "rotas")
    time.sleep(0.5)
    txt = o.log(name)
    i = txt.rfind("Fluxo ")
    return txt[i:].split("\n[")[0] if i >= 0 else ""


def setup(name, s2_streams=("filmeB", "filmeC"), relay_cliente=None):
    """Arranca bootstrapper, S1 (filmeA, filmeB), S2 (filmeB, filmeC) e os relays O1..O4.
    relay_cliente=("O1", "filmeA"): esse relay corre o cliente.py (também é relay)."""
    o = LocalOverlay(CFG, os.path.join(OUT, name))
    o.start_bootstrapper()
    o.start("S1", "servidor.py", "filmeA", "filmeB")
    o.start("S2", "servidor.py", *s2_streams)
    for n in ("O1", "O2", "O3", "O4"):
        if relay_cliente and relay_cliente[0] == n:
            o.start(n, "cliente.py", relay_cliente[1], "--sem-gui")
        else:
            o.start(n, "onode.py")
    return o


def client(o, name, stream):
    o.start(name, "cliente.py", stream, "--sem-gui")


def healthy(o, name, min_fps=15):
    s = o.last_stats(name)
    return s is not None and fnum(s["fps"]) >= min_fps and s["servidor"] != "None"


# ---------------------------------------------------------------------------

def t1_basico():
    print("T1: entrega básica, 2 servidores x 2 streams (filmeB nos dois), 4 clientes")
    o = setup("t1")
    for c, s in (("C1", "filmeA"), ("C2", "filmeB"), ("C3", "filmeC"), ("C4", "filmeB")):
        client(o, c, s)
    time.sleep(9)
    for c in ("C1", "C2", "C3", "C4"):
        s = o.last_stats(c)
        check("T1", s and fnum(s["fps"]) >= 18 and s["perdas"] == "0",
              f"{c} a ver {s and s['stream']} de {s and s['servidor']}: fps={s and s['fps']} "
              f"perdas={s and s['perdas']} caminho {s and s['caminho']}")
    o.stop_all()


def t2_arvore():
    print("T2: árvore partilhada (4 clientes na mesma stream)")
    o = setup("t2")
    for c in ("C1", "C2", "C3", "C4"):
        client(o, c, "filmeA")
    time.sleep(8)
    tab = table(o, "S1")
    line = next((l for l in tab.splitlines() if l.startswith("S1/filmeA")), "")
    dests = line.split()[4].split(",") if line else []
    check("T2", all(healthy(o, c) for c in ("C1", "C2", "C3", "C4")), "os 4 clientes recebem filmeA")
    check("T2", 0 < len(dests) < 4,
          f"S1 envia apenas {len(dests)} cópia(s) ({','.join(dests)}) para 4 clientes")
    with open(os.path.join(OUT, "t2", "tabelas.txt"), "w") as f:
        for n in ("S1", "O1", "O2", "O3", "O4", "S2"):
            f.write(f"== {n}\n{table(o, n)}\n\n")
    o.stop_all()


def t3_falha_relay():
    print("T3: falha abrupta (kill -9) do nó intermédio mais usado")
    o = setup("t3")
    clients = ("C1", "C2", "C3", "C4")
    for c in clients:
        client(o, c, "filmeA")
    time.sleep(7)
    before = {c: o.last_stats(c)["caminho"] for c in clients}
    relays = ("O1", "O2", "O3", "O4")
    victim = max(relays, key=lambda r: sum(r in p.split(" > ") for p in before.values()))
    users = [c for c in clients if victim in before[c].split(" > ")]
    print(f"     a matar {victim}, usado por {users}")
    o.kill(victim)
    time.sleep(8)
    for c in clients:
        s = o.last_stats(c)
        check("T3", healthy(o, c) and victim not in s["caminho"].split(" > "),
              f"{c}: {before[c]}  ->  {s['caminho']} (maior falha {s['maior_falha']})")
    o.stop_all()


def t4_saida_ordeira():
    print("T4: saída ordeira (comando 'sair' -> ADEUS) do relay usado por C1")
    o = setup("t4")
    client(o, "C1", "filmeA")
    time.sleep(7)
    s0 = o.last_stats("C1")
    relay = s0["caminho"].split(" > ")[1]
    o.kill(relay, graceful=True)
    time.sleep(5)
    s = o.last_stats("C1")
    check("T4", healthy(o, "C1") and relay not in s["caminho"] and fnum(s["maior_falha"]) < 1000,
          f"{relay} saiu: C1 {s0['caminho']} -> {s['caminho']}, maior falha {s['maior_falha']} "
          f"(o ADEUS evita esperar pelo timeout)")
    o.stop_all()


def t4b_falha_silenciosa():
    print("T4b: falha silenciosa (SIGSTOP) do relay usado por C1 -> deteção por ALIVE/timeout")
    o = setup("t4b")
    client(o, "C1", "filmeA")
    time.sleep(7)
    s0 = o.last_stats("C1")
    relay = s0["caminho"].split(" > ")[1]
    o.freeze(relay)
    time.sleep(8)
    s = o.last_stats("C1")
    check("T4b", healthy(o, "C1") and relay not in s["caminho"],
          f"{relay} congelado: C1 {s0['caminho']} -> {s['caminho']}, maior falha {s['maior_falha']} "
          f"(timeout de vizinho = 3,5 s)")
    o.stop_all()


def t5_reentrada():
    print("T5: nó sai e volta a entrar (O3 reinicia)")
    o = setup("t5")
    client(o, "C3", "filmeA")
    time.sleep(7)
    s0 = o.last_stats("C3")
    o.kill("O3")
    time.sleep(6)
    s1 = o.last_stats("C3")
    o.start("O3", "onode.py")
    time.sleep(7)
    log = o.log("O3")
    nviz = len(re.findall(r"Vizinho \w+ .* ligado", log))
    check("T5", nviz >= 5, f"O3 voltou e religou-se a {nviz} vizinhos sem intervenção do bootstrapper")
    check("T5", healthy(o, "C3"), f"C3: {s0['caminho']} -> {s1['caminho']} -> {o.last_stats('C3')['caminho']}")
    o.stop_all()


def t6_metrica_atraso():
    print("T6: métrica de atraso (40 ms numa ligação, alterado em execução)")
    o = setup("t6")
    client(o, "C2", "filmeA")            # C2 tem 2 caminhos de 2 saltos: via O2 ou via O3
    time.sleep(7)
    p0 = o.last_stats("C2")["caminho"]
    a = p0.split(" > ")[1]
    b = "O3" if a == "O2" else "O2"

    def delay(x, ms):
        o.cmd("S1", f"delay {o.ip[x]} {ms}")
        o.cmd(x, f"delay {o.ip['S1']} {ms}")

    delay(a, 40)                          # torna lenta a ligação S1-a, que está em uso
    time.sleep(8)
    p1 = o.last_stats("C2")["caminho"]
    check("T6", p1 == f"S1 > {b} > C2" and healthy(o, "C2"),
          f"S1-{a} passa a 40 ms: C2 {p0} -> {p1} (mesmo nº de saltos, menor atraso)")
    delay(a, 0)
    delay(b, 40)
    time.sleep(8)
    p2 = o.last_stats("C2")["caminho"]
    check("T6", p2 == f"S1 > {a} > C2" and healthy(o, "C2"),
          f"atraso passa para S1-{b}: C2 volta a {p2}")
    tab = table(o, "C2")
    with open(os.path.join(OUT, "t6", "tabela_C2.txt"), "w") as f:
        f.write(tab)
    o.stop_all()


def t7_falha_servidor():
    print("T7: filmeB está nos dois servidores: escolha do mais próximo e falha de servidor")
    o = setup("t7", relay_cliente=("O1", "filmeB"))   # O1 está a 1 salto de S1
    client(o, "C4", "filmeB")                        # C4 está a 1 salto de S2
    time.sleep(8)
    a, b = o.last_stats("O1"), o.last_stats("C4")
    check("T7", a["servidor"] == "S1" and b["servidor"] == "S2",
          f"cada cliente escolhe o servidor mais próximo: O1<-{a['servidor']} ({a['caminho']}), "
          f"C4<-{b['servidor']} ({b['caminho']})")
    o.kill("S1")
    time.sleep(9)
    a = o.last_stats("O1")
    check("T7", a["servidor"] == "S2" and healthy(o, "O1"),
          f"S1 caiu: O1 passou para {a['servidor']} ({a['caminho']}), maior falha {a['maior_falha']}")
    o.stop_all()


def t8_poda():
    print("T8: sem clientes não há tráfego (poda)")
    o = setup("t8")
    client(o, "C3", "filmeB")
    time.sleep(7)
    on = table(o, "S1")
    o.cmd("C3", "stop")
    time.sleep(3)
    off = table(o, "S1")
    l_on = next(l for l in on.splitlines() if l.startswith("S1/filmeB"))
    l_off = next(l for l in off.splitlines() if l.startswith("S1/filmeB"))
    check("T8", "ativa" in l_on.split()[-1:] or " ativa" in l_on, f"com cliente:  {l_on.strip()}")
    check("T8", "inativa" in l_off, f"sem cliente:   {l_off.strip()}")
    poda = sum(o.log(n).count("poda") for n in ("O1", "O2", "O3", "O4", "S1", "C3"))
    check("T8", poda > 0, f"{poda} mensagens de poda registadas ao longo do ramo")
    o.stop_all()


def main():
    os.makedirs(OUT, exist_ok=True)
    tests = [t1_basico, t2_arvore, t3_falha_relay, t4_saida_ordeira, t4b_falha_silenciosa, t5_reentrada,
             t6_metrica_atraso, t7_falha_servidor, t8_poda]
    only = os.environ.get("ONLY")
    for t in tests:
        if only and not t.__name__.startswith(only):
            continue
        try:
            t()
        except Exception as e:
            check(t.__name__, False, f"exceção: {e!r}")
    ok = sum(1 for r in results if r[1])
    print(f"\n{ok}/{len(results)} verificações passaram")
    with open(os.path.join(OUT, "resultados.md"), "w") as f:
        f.write("| Teste | Resultado | Descrição |\n|---|---|---|\n")
        for t, r, d in results:
            f.write(f"| {t} | {'PASS' if r else 'FAIL'} | {d} |\n")
    sys.exit(0 if ok == len(results) else 1)


if __name__ == "__main__":
    main()
