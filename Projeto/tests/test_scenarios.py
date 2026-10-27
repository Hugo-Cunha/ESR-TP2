#!/usr/bin/env python3
"""Testes automáticos do overlay na Topologia 3 (sem CORE, tudo em 127.10.0.x).

Uso:
    python3 tests/test_scenarios.py [pasta_de_logs]
    ONLY=t6 python3 tests/test_scenarios.py        (só um teste)

Overlay: S1 (filmeA, filmeB), S2 (filmeB, filmeC), O1..O4.
Clientes e o seu onode (como no CORE): C1->O2, C2->O3, C3->O4, C4->S2.
No fim é escrito um resumo em <pasta>/resultados.md (útil para o relatório).
"""

import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from local_overlay import TODOS, LocalOverlay  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CFG = os.path.join(ROOT, "configs", "overlay_topo3.json")
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "tests", "logs")
ONODE_DE = {"C1": "O2", "C2": "O3", "C3": "O4", "C4": "S2"}

results = []


def check(test, cond, desc):
    results.append((test, bool(cond), desc))
    print(f"  [{'PASS' if cond else 'FAIL'}] {desc}", flush=True)


def fnum(x):
    return float(re.sub(r"[^0-9.]", "", x or "0") or 0)


def setup(name):
    o = LocalOverlay(CFG, os.path.join(OUT, name))
    o.start_bootstrapper()
    o.start("S1", "servidor.py", "filmeA", "filmeB")
    o.start("S2", "servidor.py", "filmeB", "filmeC")
    for n in ("O1", "O2", "O3", "O4"):
        o.start(n)
    return o


def client(o, name, stream):
    o.start_cliente(name, ONODE_DE[name], stream)


def nome_servidor(o, ip):
    return next((n for n, i in o.ip.items() if i == ip), ip)


def healthy(o, name, min_fps=15):
    s = o.last_stats(name)
    return s is not None and fnum(s["fps"]) >= min_fps


def linha_rota(o, no, fluxo):
    """Linha da tabela de rotas do nó para o fluxo (ex.: 'S1/filmeA')."""
    return next((l for l in o.ottctl(no, "rotas").splitlines() if l.startswith(fluxo + " ")), "")


def origem(o, no, fluxo):
    linha = linha_rota(o, no, fluxo)
    return linha.split()[1] if linha else None


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
              f"{c} (onode {ONODE_DE[c]}) a ver {s and s['stream']} do servidor "
              f"{s and nome_servidor(o, s['servidor'])}: fps={s and s['fps']} perdas={s and s['perdas']}")
    o.stop_all()


def t2_arvore():
    print("T2: árvore partilhada (4 clientes no filmeA, que só o S1 tem)")
    o = setup("t2")
    for c in ("C1", "C2", "C3", "C4"):
        client(o, c, "filmeA")
    time.sleep(8)
    dests = (linha_rota(o, "S1", "S1/filmeA").split() + ["-"] * 5)[4].split(",")
    check("T2", all(healthy(o, c) for c in ("C1", "C2", "C3", "C4")), "os 4 clientes recebem o filmeA")
    check("T2", 0 < len(dests) < 4, f"o S1 envia só {len(dests)} cópia(s) ({','.join(dests)}) para 4 clientes")
    with open(os.path.join(OUT, "t2", "tabelas.txt"), "w") as f:
        for n in ("S1", "O1", "O2", "O3", "O4", "S2"):
            f.write(f"== {n}\n{o.ottctl(n, 'rotas')}\n")
    o.stop_all()


def _falha_de_relay(teste, como):
    o = setup(teste.lower())
    client(o, "C3", "filmeA")             # C3 -> O4 -> (O2 ou O3) -> S1
    time.sleep(7)
    relay = origem(o, "O4", "S1/filmeA")
    print(f"     O4 recebe o filmeA via {relay}; a provocar a falha de {relay} ({como})")
    if como == "kill":
        o.kill(relay)
    elif como == "sair":
        o.kill(relay, graceful=True)
    else:
        o.freeze(relay)
    time.sleep(8)
    novo = origem(o, "O4", "S1/filmeA")
    s = o.last_stats("C3")
    return o, relay, novo, s


def t3_falha_relay():
    print("T3: falha abrupta (kill -9) de um nó intermédio")
    o, relay, novo, s = _falha_de_relay("T3", "kill")
    check("T3", healthy(o, "C3") and novo not in (relay, None),
          f"O4 passou a receber via {novo}; C3 continua a ver (maior falha {s['maior_falha']})")
    o.stop_all()


def t4_saida_ordeira():
    print("T4: saída ordeira (ADEUS) de um nó intermédio")
    o, relay, novo, s = _falha_de_relay("T4", "sair")
    check("T4", healthy(o, "C3") and novo not in (relay, None) and fnum(s["maior_falha"]) < 1000,
          f"O4 passou a receber via {novo}; maior falha no C3 {s['maior_falha']} (sem esperar timeout)")
    o.stop_all()


def t4b_falha_silenciosa():
    print("T4b: nó intermédio congelado (SIGSTOP) -> deteção pelo timeout de 3,5 s")
    o, relay, novo, s = _falha_de_relay("T4b", "congelar")
    check("T4b", healthy(o, "C3") and novo not in (relay, None),
          f"O4 passou a receber via {novo}; maior falha no C3 {s['maior_falha']}")
    o.stop_all()


def t5_onode_do_cliente():
    print("T5: o onode do cliente morre (o cliente fica sem vídeo) e volta (o vídeo volta)")
    o = setup("t5")
    client(o, "C2", "filmeA")             # C2 -> O3
    time.sleep(7)
    antes = healthy(o, "C2")
    o.kill("O3")
    time.sleep(5)
    s = o.last_stats("C2")
    sem_video = fnum(s["fps"]) == 0 and "não responde" in o.log("C2")
    o.start("O3", "onode.py")
    time.sleep(9)
    check("T5", antes and sem_video, f"O3 morreu: C2 ficou sem vídeo (fps={s['fps']}) e avisa que o onode não responde")
    nviz = len(re.findall(r"Vizinho \w+ .* ligado", o.log("O3")))
    check("T5", healthy(o, "C2"), f"O3 voltou (religou-se a {nviz} vizinhos): C2 volta a ver "
                                  f"(fps={o.last_stats('C2')['fps']})")
    o.stop_all()


def t6_metrica_atraso():
    print("T6: métrica de atraso (40 ms numa ligação, alterado em execução)")
    o = setup("t6")
    client(o, "C3", "filmeA")             # O4 chega ao S1 por O2 ou O3 (2 saltos cada)
    time.sleep(7)
    a = origem(o, "O4", "S1/filmeA")
    b = "O3" if a == "O2" else "O2"

    def delay(x, ms):
        o.ottctl("S1", f"delay {o.ip[x]} {ms}")
        o.ottctl(x, f"delay {o.ip['S1']} {ms}")

    delay(a, 40)
    time.sleep(8)
    p1 = origem(o, "O4", "S1/filmeA")
    check("T6", p1 == b and healthy(o, "C3"),
          f"ligação S1-{a} passa a 40 ms: O4 troca a Origem {a} -> {p1} (mesmo nº de saltos, menos atraso)")
    with open(os.path.join(OUT, "t6", "tabela_O4.txt"), "w") as f:
        f.write(o.ottctl("O4", "rotas"))
    delay(a, 0)
    delay(b, 40)
    time.sleep(8)
    p2 = origem(o, "O4", "S1/filmeA")
    check("T6", p2 == a and healthy(o, "C3"), f"o atraso passa para S1-{b}: O4 volta à Origem {p2}")
    o.stop_all()


def t7_escolha_servidor():
    print("T7: filmeB está nos dois servidores: escolha do melhor e falha de servidor")
    o = setup("t7")
    client(o, "C2", "filmeB")             # O3 está a 1 salto do S1 e a 2 do S2
    client(o, "C4", "filmeB")             # o onode do C4 é o próprio S2
    time.sleep(8)
    a, b = o.last_stats("C2"), o.last_stats("C4")
    sa, sb = nome_servidor(o, a["servidor"]), nome_servidor(o, b["servidor"])
    check("T7", sa == "S1" and sb == "S2",
          f"cada onode escolhe o melhor servidor: C2 (via O3) <- {sa}, C4 (via S2) <- {sb}")
    o.kill("S1")
    time.sleep(9)
    a = o.last_stats("C2")
    check("T7", nome_servidor(o, a["servidor"]) == "S2" and healthy(o, "C2"),
          f"S1 caiu: C2 passou para {nome_servidor(o, a['servidor'])} (trocas={a['trocas']}, "
          f"maior falha {a['maior_falha']})")
    o.stop_all()


def t8_poda():
    print("T8: sem clientes não há tráfego (poda)")
    o = setup("t8")
    client(o, "C3", "filmeA")
    time.sleep(7)
    on = linha_rota(o, "S1", "S1/filmeA")
    o.cmd("C3", "stop")
    time.sleep(3)
    off = linha_rota(o, "S1", "S1/filmeA")
    check("T8", " ativa" in on, f"com cliente: {on.strip()}")
    check("T8", "inativa" in off, f"sem cliente: {off.strip()}")
    poda = sum(o.log(n).count("poda") for n in ("O1", "O2", "O3", "O4", "S1"))
    check("T8", poda > 0, f"{poda} mensagens de poda registadas ao longo do ramo")
    o.stop_all()


def main():
    os.makedirs(OUT, exist_ok=True)
    tests = [t1_basico, t2_arvore, t3_falha_relay, t4_saida_ordeira, t4b_falha_silenciosa,
             t5_onode_do_cliente, t6_metrica_atraso, t7_escolha_servidor, t8_poda]
    only = os.environ.get("ONLY")
    for t in tests:
        if only and not t.__name__.startswith(only):
            continue
        try:
            t()
        except Exception as e:
            check(t.__name__, False, f"exceção: {e!r}")
        for o in TODOS:                   # garante que não ficam processos pendurados
            o.stop_all()
    ok = sum(1 for r in results if r[1])
    print(f"\n{ok}/{len(results)} verificações passaram")
    with open(os.path.join(OUT, "resultados.md"), "w") as f:
        f.write("| Teste | Resultado | Descrição |\n|---|---|---|\n")
        for t, r, d in results:
            f.write(f"| {t} | {'PASS' if r else 'FAIL'} | {d} |\n")
    sys.exit(0 if ok == len(results) else 1)


if __name__ == "__main__":
    main()
