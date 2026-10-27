#!/bin/bash
# Arranca/para o overlay da Topologia 3 dentro do CORE, a partir da shell do
# contentor (sem abrir um terminal por nó). Usa o vcmd para correr comandos em
# cada nó da sessão CORE ativa.
#
# Uso (com a topologia já arrancada no CORE):
#   ./core_run.sh start            # bootstrapper, 2 servidores, 4 relays, 4 clientes sem janela
#   ./core_run.sh status           # últimas estatísticas dos clientes
#   ./core_run.sh log C1           # segue o log de um nó (Ctrl+C para sair)
#   ./core_run.sh kill O2          # mata o programa num nó (teste de falha)
#   ./core_run.sh run O2 [args]    # (re)arranca o programa num nó
#   ./core_run.sh cmd O3 rotas     # envia um comando ao nó: rotas, vizinhos, sair,
#                                  #   ping (servidores), play <stream> / stop (clientes)
#   ./core_run.sh shell PC4        # shell interativa dentro de um nó CORE
#   ./core_run.sh stop             # para tudo

DIR="$(cd "$(dirname "$0")" && pwd)"
LOGS="${LOGS:-$DIR/core_logs}"
BOOT=10.0.18.10      # PC "Bootstrapper" (só corre o bootstrapper)
if [ -z "$SESSION" ]; then
  SESSIONS=( $(ls -d /tmp/pycore.* 2>/dev/null) )
  if [ ${#SESSIONS[@]} -gt 1 ]; then
    echo "Erro: há ${#SESSIONS[@]} sessões CORE abertas: ${SESSIONS[*]}" >&2
    echo "Fecha as que não usas (Session > Sessions > Shutdown) ou escolhe uma:" >&2
    echo "  SESSION=${SESSIONS[0]} $0 $*" >&2
    exit 1
  fi
  SESSION="${SESSIONS[0]}"
fi

# nome overlay -> nó CORE (Topologia_test3)
declare -A HOST=( [S1]=Server [S2]=PC6 [O1]=PC1 [O2]=PC4 [O3]=PC2 [O4]=PC9
                  [C1]=PC5 [C2]=PC3 [C3]=PC8 [C4]=PC7 )
declare -A PROG=( [S1]=servidor.py [S2]=servidor.py
                  [O1]=onode.py [O2]=onode.py [O3]=onode.py [O4]=onode.py
                  [C1]=cliente.py [C2]=cliente.py [C3]=cliente.py [C4]=cliente.py )
declare -A ARGS=(
  [S1]="filmeA filmeB" [S2]="filmeB filmeC"
  [C1]="filmeA --sem-gui" [C2]="filmeB --sem-gui"
  [C3]="filmeC --sem-gui" [C4]="filmeB --sem-gui" )
PROGRAMAS="onode.py|servidor.py|cliente.py"

die() { echo "Erro: $*" >&2; exit 1; }
[ -n "$SESSION" ] || die "nenhuma sessão CORE ativa (/tmp/pycore.*). Arranca a topologia primeiro."
command -v vcmd >/dev/null || die "vcmd não encontrado (é instalado com o CORE)."

node() {   # node <nó CORE> <comando...>
  local h=$1; shift
  [ -S "$SESSION/$h" ] || die "nó '$h' não existe em $SESSION"
  vcmd -c "$SESSION/$h" -- "$@"
}

bg() {   # bg <nome do log> <nó CORE> <comando> : corre no nó, em fundo, com log
  # O vcmd fica a correr (em fundo, do lado do contentor) enquanto o programa
  # viver no nó; se o programa fosse posto em fundo dentro do nó, o vcmd
  # terminava e levava-o com ele.
  local log=$1 h=$2; shift 2
  [ -S "$SESSION/$h" ] || die "nó '$h' não existe em $SESSION"
  nohup vcmd -c "$SESSION/$h" -- bash -c "cd '$DIR' && exec $*" < /dev/null >> "$LOGS/$log.log" 2>&1 &
}

arrancar() {   # arrancar <nome overlay> [args extra]
  local n=$1; shift
  bg "$n" "${HOST[$n]}" python3 -u ${PROG[$n]} $BOOT ${ARGS[$n]} "$@"
  echo "  $n (${HOST[$n]}) arrancado"
}

case "$1" in
  start)
    mkdir -p "$LOGS"
    echo "Sessão: $SESSION   logs: $LOGS"
    node Server ping -c1 -W2 10.0.20.21 >/dev/null || \
      echo "AVISO: Server não chega a PC8 — o routing (OSPF) pode ainda não ter convergido."
    bg BOOT Bootstrapper python3 -u bootstrapper.py configs/overlay_topo3.json
    echo "  bootstrapper (PC Bootstrapper) arrancado"; sleep 1
    for n in S1 S2 O1 O2 O3 O4; do arrancar $n; done
    sleep 3
    for n in C1 C2 C3 C4; do arrancar $n; done
    sleep 1
    for f in BOOT S1 S2 O1 O2 O3 O4 C1 C2 C3 C4; do
      grep -qE "Traceback|Error" "$LOGS/$f.log" 2>/dev/null && { echo "!! $f teve um erro:"; tail -3 "$LOGS/$f.log"; }
    done
    echo "Pronto. Usa '$0 status' daqui a ~10 s (ou '$0 log C1')." ;;
  status)
    for n in C1 C2 C3 C4; do
      printf '%s: ' "$n"; grep STATS "$LOGS/$n.log" 2>/dev/null | tail -1 | sed 's/.*STATS //' || echo "-"
      echo
    done ;;
  log)   tail -f "$LOGS/$2.log" ;;
  kill)  node "${HOST[$2]}" pkill -f "$PROGRAMAS" && echo "$2 morto" ;;
  run)   mkdir -p "$LOGS"; n=$2; shift 2; arrancar "$n" "$@" ;;
  shell) node "$2" bash ;;
  cmd)   # cmd <nome overlay> <comando...> : envia um comando ao nó a correr em fundo
    n=$2; shift 2
    [ -n "${HOST[$n]}" ] || die "nó overlay desconhecido: $n (usa S1, S2, O1..O4, C1..C4)"
    node "${HOST[$n]}" bash -c "cd '$DIR' && python3 ottctl.py $*" ;;
  stop)
    for h in "${HOST[@]}"; do node "$h" pkill -f "$PROGRAMAS" 2>/dev/null; done
    node Bootstrapper pkill -f bootstrapper.py 2>/dev/null
    echo "Tudo parado." ;;
  *) sed -n '2,16p' "$0" ;;
esac
