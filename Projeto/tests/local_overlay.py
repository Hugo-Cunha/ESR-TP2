"""Utilitários para correr um overlay inteiro numa só máquina (sem CORE).

Cada nó recebe um IP próprio em 127.10.0.x (todo o 127.0.0.0/8 é loopback em
Linux), por isso todos podem usar as mesmas portas, como no CORE.
  - onodes/servidores: 127.10.0.1, .2, ... (pela ordem do JSON)
  - clientes:          127.10.0.101, .102, ...
  - bootstrapper:      127.10.0.250
"""

import json
import os
import re
import signal
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TODOS = []          # overlays criados (para parar tudo mesmo se um teste rebentar)


class LocalOverlay:
    def __init__(self, cfg_path, workdir, base="127.10.0."):
        with open(cfg_path) as f:
            cfg = json.load(f)
        self.base = base
        self.ip = {n: f"{base}{i + 1}" for i, n in enumerate(cfg["nodes"])}
        for n in cfg["nodes"]:
            cfg["nodes"][n]["ip"] = self.ip[n]
        os.makedirs(workdir, exist_ok=True)
        self.workdir = workdir
        self.cfg = os.path.join(workdir, "overlay_local.json")
        with open(self.cfg, "w") as f:
            json.dump(cfg, f, indent=1)
        self.boot_ip = base + "250"
        self.procs = {}
        self.n_clientes = 0
        TODOS.append(self)

    def _spawn(self, key, args):
        logf = open(os.path.join(self.workdir, f"{key}.log"), "a")
        p = subprocess.Popen([sys.executable, "-u"] + args, cwd=ROOT, stdin=subprocess.PIPE,
                             stdout=logf, stderr=subprocess.STDOUT, text=True,
                             env=dict(os.environ, PYTHONUNBUFFERED="1"))
        self.procs[key] = p

    def start_bootstrapper(self):
        self._spawn("BOOT", ["bootstrapper.py", self.cfg, self.boot_ip])
        time.sleep(0.5)

    def start(self, name, programa="onode.py", *extra):
        """programa: onode.py ou servidor.py"""
        self._spawn(name, [programa, self.boot_ip, "--ip", self.ip[name]] + list(extra))

    def start_cliente(self, name, onode, stream):
        if name not in self.ip:
            self.n_clientes += 1
            self.ip[name] = f"{self.base}{100 + self.n_clientes}"
        self._spawn(name, ["cliente.py", self.ip[onode], stream, "--ip", self.ip[name], "--sem-gui"])

    def cmd(self, name, line):
        """Escreve uma linha no terminal (stdin) do processo."""
        p = self.procs[name]
        p.stdin.write(line + "\n")
        p.stdin.flush()

    def ottctl(self, name, comando):
        """Pede um comando a um onode pela porta de comandos e devolve a resposta."""
        r = subprocess.run([sys.executable, "ottctl.py", "--ip", self.ip[name]] + comando.split(),
                           cwd=ROOT, capture_output=True, text=True, timeout=10)
        return r.stdout

    def kill(self, name, graceful=False):
        p = self.procs.pop(name)
        if graceful:
            try:
                p.stdin.write("sair\n")
                p.stdin.flush()
                p.wait(3)
                return
            except Exception:
                pass
        p.send_signal(signal.SIGKILL)        # simula falha abrupta (sem ADEUS)
        p.wait()

    def freeze(self, name):
        """Congela o processo (SIGSTOP): não fecha sockets, só deixa de responder.
        Simula uma falha de ligação/máquina detetada apenas pelo timeout."""
        self.procs[name].send_signal(signal.SIGSTOP)

    def log(self, name):
        with open(os.path.join(self.workdir, f"{name}.log"), errors="replace") as f:
            return f.read()

    def last_stats(self, name):
        """Última linha STATS do cliente, como dict."""
        lines = [l for l in self.log(name).splitlines() if "STATS" in l]
        return dict(re.findall(r"(\w+)=(\S+)", lines[-1])) if lines else None

    def stop_all(self):
        for name in list(self.procs):
            self.kill(name)
