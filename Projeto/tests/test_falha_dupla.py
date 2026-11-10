#!/usr/bin/env python3
"""Testes do extra das falhas duplas (reparação do overlay), sem CORE.

    S1 — O4 —┬— O2 —┬— O1 — C1
             └— O3 —┘    └— O5   (folha; só arrancada no F3)

Regra: quando, num fluxo ativo, um nó fica com UM só vizinho com caminho (O2
morre), pede-lhe o próximo salto (ENDANGERED -> só o IP do O4). Se esse vizinho
também morrer e o nó ficar sem caminho, liga-se diretamente ao O4 (recurso).

Uso:  python3 tests/test_falha_dupla.py [pasta_de_logs]
"""

import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from local_overlay import TODOS, LocalOverlay  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from comum.config import HEARTBEAT as HB  # noqa: E402
CFG = os.path.join(ROOT, "configs", "overlay_falha_dupla.json")
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "tests", "logs_falha_dupla")
results = []


def check(test, cond, desc):
    results.append((test, bool(cond), desc))
    print(f"  [{'PASS' if cond else 'FAIL'}] {desc}", flush=True)


def fnum(x):
    return float(re.sub(r"[^0-9.]", "", x or "0") or 0)


def setup(name, folha=False):
    o = LocalOverlay(CFG, os.path.join(OUT, name))
    o.start_bootstrapper()
    o.start("S1", "servidor.py", "filmeA", "filmeB")
    for n in ("O4", "O2", "O3", "O1") + (("O5",) if folha else ()):
        o.start(n)
    time.sleep(3)
    o.start_cliente("C1", "O1", "filmeA")
    time.sleep(6)
    return o


def healthy(o, name, min_fps=15):
    s = o.last_stats(name)
    return s is not None and fnum(s["fps"]) >= min_fps


def origem(o, no, fluxo="S1/filmeA"):
    linha = next((l for l in o.ottctl(no, "rotas").splitlines() if l.startswith(fluxo + " ")), "")
    return linha.split()[1] if linha else None


def estado_vizinho(o, no, vizinho):
    linha = next((l for l in o.ottctl(no, "vizinhos").splitlines() if l.startswith(vizinho + " ")), "")
    return linha.split()[2] if linha else None


def recursos(o, no):
    return o.log(no).count("a abrir ligação de recurso")


def f1_falha_simples():
    print("F1: só O2 morre -> o encaminhamento resolve (via O3) e NÃO se abre ligação de recurso")
    o = setup("f1")
    antes = origem(o, "O1")
    o.kill(antes)
    time.sleep(7)
    depois = origem(o, "O1")
    check("F1", depois not in (antes, None) and healthy(o, "C1"),
          f"{antes} morreu: O1 passou para {depois}; C1 continua a ver")
    check("F1", recursos(o, "O1") == 0, "nenhuma ligação de recurso aberta (havia alternativa)")
    check("F1", "ENDANGERED" in o.log("O1") and "Reserva: se" in o.log("O1"),
          "O1 ficou só com um caminho: enviou ENDANGERED e guardou o próximo salto como reserva")
    o.stop_all()


def f2_falha_dupla():
    print("F2: O2 morre (ENDANGERED), depois O3 morre -> O1 liga-se ao O4 (recurso); "
          "O2 volta -> regressa ao O2 e a ligação de recurso fecha")
    o = setup("f2")
    check("F2", healthy(o, "C1"), f"antes: C1 a ver via {origem(o, 'O1')}")
    o.kill("O2")
    time.sleep(3)
    o.kill("O3")
    time.sleep(10)
    s = o.last_stats("C1")
    check("F2", origem(o, "O1") == "O4" and estado_vizinho(o, "O1", "O4") == "recurso",
          f"O2 e O3 morreram: O1 abriu ligação de recurso a O4 (Origem = {origem(o, 'O1')})")
    check("F2", healthy(o, "C1"),
          f"C1 voltou a ver (fps={s['fps']}; maior falha {s['maior_falha']})")
    o.start("O2")
    time.sleep(12)
    check("F2", origem(o, "O1") == "O2" and healthy(o, "C1"),
          f"O2 voltou: O1 regressou à Origem {origem(o, 'O1')}; C1 continua a ver")
    check("F2", estado_vizinho(o, "O1", "O4") is None and "já não é precisa" in o.log("O1"),
          "a ligação de recurso O1-O4 foi fechada (já não era precisa)")
    o.stop_all()


def f3_folha_viva():
    print("F3: igual ao F2, mas o O1 tem mais um vizinho vivo sem rota (O5) -> repara na mesma")
    o = setup("f3", folha=True)
    o.kill("O2")
    time.sleep(3)
    o.kill("O3")
    time.sleep(10)
    s = o.last_stats("C1")
    check("F3", origem(o, "O1") == "O4" and estado_vizinho(o, "O1", "O5") == "ligado",
          f"O1 abriu ligação de recurso a O4 (Origem = {origem(o, 'O1')}); O5 continua ligado")
    check("F3", healthy(o, "C1"), f"C1 voltou a ver (maior falha {s['maior_falha']})")
    check("F3", origem(o, "O5") == "O1", f"o O5 também volta a ter rota, via O1 ({origem(o, 'O5')})")
    o.stop_all()


def f4_servidor_morre():
    print("F4: morre o servidor -> ninguém abre ligação de recurso (um servidor morto não se contorna)")
    o = setup("f4")
    o.kill("S1")
    time.sleep(10)
    total = sum(recursos(o, n) for n in ("O1", "O2", "O3", "O4"))
    check("F4", total == 0, f"nenhuma ligação de recurso aberta ({total})")
    o.stop_all()


def f5_simultanea():
    print("F5 (limitação): O2 e O3 morrem AO MESMO TEMPO -> sem aviso prévio não há reserva nem reparação")
    o = setup("f5")
    o.freeze("O2")                        # congelados ao mesmo tempo: nenhum responde ao ENDANGERED
    o.freeze("O3")
    time.sleep(2 * HB + 10)
    check("F5", recursos(o, "O1") == 0 and origem(o, "O1") in (None, "-"),
          "O1 fica sem caminho e espera que O2 ou O3 volte (comportamento esperado)")
    o.stop_all()


def main():
    os.makedirs(OUT, exist_ok=True)
    for t in (f1_falha_simples, f2_falha_dupla, f3_folha_viva, f4_servidor_morre, f5_simultanea):
        try:
            t()
        except Exception as e:
            check(t.__name__, False, f"exceção: {e!r}")
        for o in TODOS:
            o.stop_all()
    ok = sum(1 for r in results if r[1])
    print(f"\n{ok}/{len(results)} verificações passaram")
    sys.exit(0 if ok == len(results) else 1)


if __name__ == "__main__":
    main()
