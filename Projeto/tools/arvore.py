#!/usr/bin/env python3
"""Desenha as árvores de distribuição do overlay, a partir do que cada nó sabe.

É uma ferramenta de OBSERVAÇÃO (para a demo e o relatório). Os onodes continuam
a não conhecer a árvore nem as rotas: cada um só sabe a sua Origem (por servidor)
e os seus Destinos. A ferramenta pergunta isso a todos os nós (comando 'estado')
e junta as peças, como faríamos à mão com o comando 'rotas' em cada terminal.

Uso no CORE (na shell do contentor, com a topologia a correr):
    python3 tools/arvore.py --core                # uma vez
    python3 tools/arvore.py --core --watch 2      # atualiza de 2 em 2 s (Ctrl+C para sair)
    python3 tools/arvore.py --core --dot arvore   # também gera arvore_<servidor>.dot (e .png se houver Graphviz)

Uso nos testes locais (nós em 127.10.0.x):
    python3 tools/arvore.py --ips 127.10.0.1 127.10.0.2 ...
"""

import argparse
import json
import os
import shutil
import socket
import stat
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

PROJETO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJETO)
from comum import config  # noqa: E402


##################################################################################
#* Recolha: pergunta 'estado' a cada nó

def estado_por_ip(ip):
    try:
        s = socket.create_connection((ip, config.CMD_PORT), timeout=2)
        s.sendall(b"estado\n")
        resposta = b""
        while True:
            parte = s.recv(65536)
            if not parte:
                break
            resposta += parte
        return json.loads(resposta)
    except (OSError, ValueError):
        return None


def sessao_core():
    sessoes = [os.path.join("/tmp", d) for d in os.listdir("/tmp") if d.startswith("pycore.")]
    if len(sessoes) != 1:
        sys.exit(f"Esperava uma sessão CORE ativa em /tmp/pycore.*, encontrei {len(sessoes)}")
    return sessoes[0]


def estado_por_no_core(sessao, no):
    """Corre 'ottctl.py estado' dentro do nó CORE (a porta de comandos é local a cada nó)."""
    try:
        r = subprocess.run(["vcmd", "-c", os.path.join(sessao, no), "--", "bash", "-c",
                            f"cd '{PROJETO}' && python3 ottctl.py estado"],
                           capture_output=True, text=True, timeout=5)
        return json.loads(r.stdout) if r.returncode == 0 else None
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return None


def recolher(args):
    with ThreadPoolExecutor(max_workers=16) as ex:
        if args.core:
            sessao = sessao_core()
            nos = [n for n in os.listdir(sessao) if stat.S_ISSOCK(os.stat(os.path.join(sessao, n)).st_mode)]
            estados = ex.map(lambda n: estado_por_no_core(sessao, n), nos)
        else:
            estados = ex.map(estado_por_ip, args.ips)
        return {e["nome"]: e for e in estados if e}


##################################################################################
#* Desenho

def desenhar(raiz, filhos, etiqueta, prefixo="", linhas=None):
    linhas = [raiz] if linhas is None else linhas
    lista = sorted(filhos.get(raiz, []))
    for i, f in enumerate(lista):
        ultimo = i == len(lista) - 1
        linhas.append(prefixo + ("└─ " if ultimo else "├─ ") + etiqueta(f))
        desenhar(f, filhos, etiqueta, prefixo + ("   " if ultimo else "│  "), linhas)
    return linhas


def arvores_de_origens(estados):
    """Árvore potencial de cada servidor: a união das Origens de todos os nós."""
    por_servidor = {}
    for nome, e in estados.items():
        for r in e["rotas"]:
            if r["origem"]:
                por_servidor.setdefault(r["servidor"], {})[nome] = r
    texto = []
    for servidor in sorted(por_servidor):
        rotas = por_servidor[servidor]
        filhos = {}
        for no, r in rotas.items():
            filhos.setdefault(r["origem"], []).append(no)

        def etiqueta(no, rotas=rotas):
            r = rotas[no]
            alt = ", ".join(f"{a}:{c}" for a, c in sorted(r["alternativas"].items()) if c is not None)
            saltos = f"{r['saltos']} salto" + ("s" if r["saltos"] != 1 else "")
            return f"{no}  (custo {r['custo']}, {saltos}" + (f"; alternativas {alt})" if alt else ")")
        texto.append(f"Árvore do {servidor} (Origens; potencial)")
        texto += desenhar(servidor, filhos, etiqueta)
        sem = sorted(n for n in estados if n != servidor and n not in rotas)
        if sem:
            texto.append(f"   sem rota para {servidor}: {', '.join(sem)}")
        texto.append("")
    return texto, por_servidor


def arvores_ativas(estados):
    """Fluxos que estão mesmo a passar: Destinos e clientes de cada nó."""
    por_fluxo = {}
    for nome, e in estados.items():
        for f in e["fluxos"]:
            por_fluxo.setdefault(f["fluxo"], {})[nome] = f
    texto = []
    for fluxo in sorted(por_fluxo):
        nos = por_fluxo[fluxo]
        filhos = {n: f["destinos"] + [f"cliente {c}" for c in f["clientes"]] for n, f in nos.items()}
        servidor = fluxo.split("/")[0]
        copias = len(nos.get(servidor, {}).get("destinos", [])) + len(nos.get(servidor, {}).get("clientes", []))
        texto.append(f"Fluxo {fluxo} (ativo; o servidor envia {copias} cópia(s))")
        texto += desenhar(servidor, filhos, lambda n: n)
        texto.append("")
    return texto, por_fluxo


def gerar_dot(por_servidor, por_fluxo, base):
    """Uma figura por servidor: a árvore das Origens (tracejado, com o custo) e,
    por cima, os ramos onde o vídeo está mesmo a passar (grosso, com a stream)."""
    cores = ["#1f77b4", "#d62728", "#2ca02c", "#9467bd", "#ff7f0e"]
    feito = []
    for servidor, rotas in sorted(por_servidor.items()):
        ativos = {}                                   # (pai, filho) -> [streams]
        for fluxo, nos in por_fluxo.items():
            if fluxo.split("/")[0] != servidor:
                continue
            for no, f in nos.items():
                for d in f["destinos"]:
                    ativos.setdefault((no, d), []).append(fluxo.split("/")[1])
                for c in f["clientes"]:
                    ativos.setdefault((no, f"cliente {c}"), []).append(fluxo.split("/")[1])
        streams = sorted({s for lst in ativos.values() for s in lst})
        cor = {st: cores[k % len(cores)] for k, st in enumerate(streams)}
        linhas = [f'digraph "{servidor}" {{', "  rankdir=TB; nodesep=0.5;",
                  "  node [shape=box, style=rounded, fontname=Helvetica]; edge [fontname=Helvetica];",
                  f'  labelloc=t; fontname=Helvetica; label="Árvore do {servidor} '
                  f'(tracejado: Origens e custo; grosso: vídeo a passar)";',
                  f'  "{servidor}" [shape=box, style="filled,rounded", fillcolor="#eeeeee"];',
                  f'  {{ rank=source; "{servidor}"; }}']
        for no, r in sorted(rotas.items()):
            if (r["origem"], no) not in ativos:
                linhas.append(f'  "{r["origem"]}" -> "{no}" [style=dashed, color="#888888", '
                              f'label="{r["custo"]}", fontsize=10, fontcolor="#666666"];')
        for (pai, filho), sts in sorted(ativos.items()):
            if filho.startswith("cliente"):
                linhas.append(f'  "{filho}" [shape=ellipse, style=solid];')
            custo = rotas[filho]["custo"] if filho in rotas else ""
            for st in sts:
                linhas.append(f'  "{pai}" -> "{filho}" [penwidth=2.5, color="{cor[st]}", '
                              f'label="{st}' + (f' ({custo})' if custo != "" else "") + '", fontsize=10];')
        linhas.append("}")
        nome = f"{base}_{servidor}"
        with open(nome + ".dot", "w") as fd:
            fd.write("\n".join(linhas) + "\n")
        feito.append(nome + ".dot")
        if shutil.which("dot"):
            subprocess.run(["dot", "-Tpng", "-Gdpi=110", nome + ".dot", "-o", nome + ".png"], check=False)
            feito.append(nome + ".png")
    return feito


##################################################################################

def mostrar(args):
    estados = recolher(args)
    if not estados:
        return "Nenhum nó respondeu (os onodes estão a correr?)"
    t1, por_servidor = arvores_de_origens(estados)
    t2, por_fluxo = arvores_ativas(estados)
    texto = [time.strftime("[%H:%M:%S] ") + f"{len(estados)} nós: {', '.join(sorted(estados))}", ""]
    texto += t1 + (t2 or ["(nenhum fluxo ativo)"])
    if args.dot:
        texto.append("Gerado: " + ", ".join(gerar_dot(por_servidor, por_fluxo, args.dot)))
    return "\n".join(texto)


def main():
    ap = argparse.ArgumentParser(description="Desenha as árvores do overlay")
    ap.add_argument("--core", action="store_true", help="recolher dos nós da sessão CORE (via vcmd)")
    ap.add_argument("--ips", nargs="*", default=[], help="(testes) IPs dos nós")
    ap.add_argument("--watch", type=float, help="atualizar de N em N segundos")
    ap.add_argument("--dot", help="gerar <nome>_<servidor>.dot (e .png se houver Graphviz)")
    args = ap.parse_args()
    if not args.core and not args.ips:
        ap.error("indica --core ou --ips")
    if not args.watch:
        print(mostrar(args))
        return
    try:
        while True:
            texto = mostrar(args)
            print("\033[2J\033[H" + texto, flush=True)
            time.sleep(args.watch)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
