#!/bin/bash
export LD_LIBRARY_PATH=/tmp/q6-tools/root/usr/lib/x86_64-linux-gnu:/tmp/q6-tools/root/usr/lib/x86_64-linux-gnu/singular${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}
export SINGULARPATH=/tmp/q6-tools/root/usr/share/singular/LIB
export SINGULAR_PROCS_DIR=/tmp/q6-tools/root/usr/lib/x86_64-linux-gnu/singular/MOD

if [ -n "${EXACT_CAPTURE_DIR:-}" ]; then
  mkdir -p "$EXACT_CAPTURE_DIR"
  cat /proc/self/limits > "$EXACT_CAPTURE_DIR/limits.txt"
  cat /proc/self/status > "$EXACT_CAPTURE_DIR/status.txt"
  for arg in "$@"; do if [ -f "$arg" ]; then cp "$arg" "$EXACT_CAPTURE_DIR/in.sing"; fi; done
fi
exec /tmp/q6-tools/root/usr/bin/Singular "$@"
