#!/usr/bin/env sh
# Sample docker stats every 5s while a sync runs; print peak memory and CPU per container.
# Usage: ./scripts/measure.sh docker compose run --rm sync
set -eu
OUT="${MEASURE_OUT:-measure.csv}"
: > "$OUT"
( while true; do
    docker stats --no-stream --format '{{.Name}},{{.CPUPerc}},{{.MemUsage}}' 2>/dev/null | sed "s/^/$(date +%s),/" >> "$OUT"
    sleep 5
  done ) &
SAMPLER=$!
trap 'kill $SAMPLER 2>/dev/null || true' EXIT
START=$(date +%s)
"$@"
END=$(date +%s)
kill $SAMPLER 2>/dev/null || true
echo "wall clock: $((END-START))s"
python3 - "$OUT" <<'PY'
import csv, re, sys
peak = {}
for ts, name, cpu, mem in csv.reader(open(sys.argv[1])):
    used = mem.split("/")[0].strip()
    m = re.match(r"([\d.]+)\s*(MiB|GiB|KiB)", used)
    mib = float(m.group(1)) * {"KiB": 1/1024, "MiB": 1, "GiB": 1024}[m.group(2)] if m else 0
    c = float(cpu.rstrip("%") or 0)
    p = peak.setdefault(name, {"mem_mib": 0, "cpu_pct": 0})
    p["mem_mib"] = max(p["mem_mib"], mib); p["cpu_pct"] = max(p["cpu_pct"], c)
for name, p in sorted(peak.items()):
    print(f"{name}: peak mem {p['mem_mib']:.0f} MiB, peak cpu {p['cpu_pct']:.0f}%")
PY
