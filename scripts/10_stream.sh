#!/usr/bin/env bash
# 10_stream.sh - Bat / tat luong Structured Streaming khi demo (buoc 10, D18). Chay tu may (Git Bash), thu muc du an.
#
#   bash scripts/10_stream.sh start [--from 16:00] [--speed 60] [--late 1] [--day 2026-09-27] [--to 24:00]
#   bash scripts/10_stream.sh stop        dung em: replayer dung ngay, luong dung sau batch dang chay
#   bash scripts/10_stream.sh status      trang thai trong MongoDB stream_status
#   bash scripts/10_stream.sh reset       xoa /data/stream/{incoming,_staging,archive,checkpoint}, trending, trending_cells
#
# start chay 2 tien trinh nen trong container jupyter: src/10_stream.py (driver, Spark UI :4041) va
# src/10b_replayer.py (chi bat sau khi luong bao "dang chay"). Log: logs/stream/<run_id>_{stream,replayer}.log
# Trigger: 5 giay o speed <= 60, 1 giay o speed cao hon (10_stream.py tu chon).
# Kich ban demo: reset, roi start --from 16:00 --speed 60 (17h-19h la gio nau dong nhat, roi vao phut 1-3).
set -euo pipefail
export MSYS_NO_PATHCONV=1
cd "$(dirname "$0")/.."
PYPATH=/usr/local/spark/python/lib/py4j-0.10.9.9-src.zip:/usr/local/spark/python
EXEC=(docker exec -w /home/jovyan/work -e PYTHONPATH=$PYPATH jupyter)
cmd=${1:-status}; shift || true

case "$cmd" in
  start)
    day=2026-09-27; from=06:00; to=24:00; speed=60; late=1
    while [ $# -gt 0 ]; do
      case "$1" in
        --day) day=$2; shift 2 ;; --from) from=$2; shift 2 ;; --to) to=$2; shift 2 ;;
        --speed) speed=$2; shift 2 ;; --late) late=$2; shift 2 ;;
        *) echo "tham so la: $1"; exit 1 ;;
      esac
    done
    run_id="demo_$(date +%m%d_%H%M%S)"
    mkdir -p logs/stream
    rm -f data/stream/STOP
    common=(--run-id "$run_id" --day "$day" --from "$from" --to "$to" --speed "$speed" --late "$late")
    docker exec -d -w /home/jovyan/work -e PYTHONPATH=$PYPATH jupyter \
      bash -c "python src/10_stream.py ${common[*]} > logs/stream/${run_id}_stream.log 2>&1"
    echo "[10] khoi dong luong $run_id, cho bao 'dang chay'..."
    for _ in $(seq 1 90); do
      if grep -q "dang chay" "logs/stream/${run_id}_stream.log" 2>/dev/null; then break; fi
      if grep -q "Traceback\|checkpoint dang dung" "logs/stream/${run_id}_stream.log" 2>/dev/null; then
        tail -5 "logs/stream/${run_id}_stream.log"; exit 1
      fi
      sleep 1
    done
    docker exec -d -w /home/jovyan/work -e PYTHONPATH=$PYPATH jupyter \
      bash -c "python src/10b_replayer.py ${common[*]} > logs/stream/${run_id}_replayer.log 2>&1"
    echo "[10] da bat replayer. Dashboard: http://localhost:8000/thoi-gian-thuc.html  Spark UI: http://localhost:4041"
    ;;
  stop)   "${EXEC[@]}" python src/stream_common.py stop ;;
  status) "${EXEC[@]}" python src/stream_common.py status ;;
  reset)  "${EXEC[@]}" python src/stream_common.py reset ;;
  *) echo "lenh: start | stop | status | reset"; exit 1 ;;
esac
