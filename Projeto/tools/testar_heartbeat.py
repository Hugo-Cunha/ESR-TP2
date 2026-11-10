#!/usr/bin/env python3
"""Escolha do HEARTBEAT (período do ALIVE e do ANUNCIO), sem CORE.

Para cada valor candidato, lança a Topologia 3 em IPs de loopback e mede:
  1. tráfego de controlo numa ligação SEM fluxo (O1-O3), em mensagens e bytes por minuto;
  2. deteção de um nó CONGELADO (O3 parado com SIGSTOP): quanto tempo até o O1 o dar como morto;
  3. falha de um relay que SAI (processo morto): maior interrupção no cliente;
  4. o onode do cliente sai e volta: quanto tempo até o cliente voltar a receber.

Uso:  python3 tools/testar_heartbeat.py [5 10 15]
"""

import json
import os
import re
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tests"))
from local_overlay import LocalOverlay  # noqa: E402

CFG = os.path.join(ROOT, "configs", "overlay_topo3.json")


def fnum(x):
    return float(re.sub(r"[^0-9.]", "", x or "0") or 0)


def esperar(cond, limite):
    t0 = time.time()
    while time.time() - t0 < limite:
        if cond():
            return time.time() - t0
        time.sleep(0.2)
    return None


def controlo(o, no, vizinho):
    e = json.loads(o.ottctl(no, "estado"))
    return e["controlo_enviado"].get(vizinho, {"msgs": 0, "bytes": 0})


def a_receber(o, cliente, desde):
    s = o.last_stats(cliente)
    return s is not None and fnum(s["fps"]) >= 10 and time.time() > desde


def medir(hb):
    os.environ["OTT_HEARTBEAT"] = str(hb)
    r = {"hb": hb}
    o = LocalOverlay(CFG, f"/tmp/heartbeat_{hb}", base="127.30.0.")
    try:
        o.start_bootstrapper()
        o.start("S1", "servidor.py", "filmeA", "filmeB")
        o.start("S2", "servidor.py", "filmeB", "filmeC")
        for n in ("O1", "O2", "O3", "O4", "O5"):
            o.start(n)
        time.sleep(3)
        o.start_cliente("C3", "O4", "filmeA")   # O4 recebe por O2 (O1-O3 fica sem fluxo)
        o.start_cliente("C2", "O3", "filmeB")   # cliente do O3 (para o teste 4)
        time.sleep(max(8, hb + 3))

        # 1. tráfego de controlo numa ligação sem fluxo (os dois sentidos), durante 60 s
        a0, b0 = controlo(o, "O1", "O3"), controlo(o, "O3", "O1")
        time.sleep(60)
        a1, b1 = controlo(o, "O1", "O3"), controlo(o, "O3", "O1")
        r["msgs_min"] = (a1["msgs"] - a0["msgs"]) + (b1["msgs"] - b0["msgs"])
        r["bytes_min"] = (a1["bytes"] - a0["bytes"]) + (b1["bytes"] - b0["bytes"])

        # 3. relay que sai: o O4 recebe o filmeA por O2; mata-se o O2
        o.kill("O2")
        time.sleep(4)
        r["falha_relay_ms"] = o.last_stats("C3")["maior_falha"]
        o.start("O2")
        time.sleep(hb + 4)

        # 2. nó congelado: O3 parado; quanto tempo até o O1 o declarar em baixo
        padrao = re.compile(r"Vizinho O3 \([0-9.]+\) em baixo")
        n_antes = len(padrao.findall(o.log("O1")))
        o.freeze("O3")
        t = esperar(lambda: len(padrao.findall(o.log("O1"))) > n_antes, 4 * hb + 10)
        r["congelado_s"] = round(t, 1) if t is not None else None
        o.kill("O3")
        time.sleep(1)

        # 4. o onode do cliente volta: tempo até o C2 voltar a receber
        o.start("O3")
        t0 = time.time()
        t = esperar(lambda: a_receber(o, "C2", t0 + 1.5), 4 * hb + 20)
        r["regresso_s"] = round(t, 1) if t is not None else None
    finally:
        o.stop_all()
    return r


def main():
    valores = [float(x) for x in sys.argv[1:]] or [5.0, 10.0, 15.0]
    resultados = [medir(hb) for hb in valores]
    print("\nHEARTBEAT | controlo O1-O3 sem fluxo | nó congelado | relay sai | onode do cliente volta")
    print("          | msgs/min  bytes/min     | detetado em  | maior falha | vídeo volta em")
    for r in resultados:
        print(f"{r['hb']:>7.0f} s | {r['msgs_min']:>8} {r['bytes_min']:>10}     | "
              f"{r['congelado_s']} s       | {r['falha_relay_ms']:>10} | {r['regresso_s']} s")


if __name__ == "__main__":
    main()
