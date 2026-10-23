#!/bin/bash
export LD_LIBRARY_PATH=/tmp/q6-tools/root/usr/lib/x86_64-linux-gnu:/tmp/q6-tools/root/usr/lib/x86_64-linux-gnu/singular${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}

if [ -n "${EXACT_CAPTURE_DIR:-}" ]; then
  mkdir -p "$EXACT_CAPTURE_DIR"
  cat /proc/self/limits > "$EXACT_CAPTURE_DIR/limits.txt"
  cat /proc/self/status > "$EXACT_CAPTURE_DIR/status.txt"
  args=("$@")
  for ((i=0; i<${#args[@]}; i++)); do
    if [ "${args[i]}" = "-f" ]; then cp "${args[i+1]}" "$EXACT_CAPTURE_DIR/in.ms"; fi
    if [ "${args[i]}" = "-o" ]; then ln -s "$EXACT_CAPTURE_DIR/out.ms" "${args[i+1]}"; fi
  done
fi
exec /tmp/q6-tools/root/usr/bin/msolve "$@"
