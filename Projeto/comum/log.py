# Escrita de mensagens no terminal: "[hora] [nome do nó] texto"

import threading
import time

nome = "?"
_lock = threading.Lock()


def log(texto):
    hora = time.strftime("%H:%M:%S")
    with _lock:
        print(f"[{hora}] [{nome}] {texto}", flush=True)
