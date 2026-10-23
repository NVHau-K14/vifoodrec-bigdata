#!/usr/bin/env bash
# 01_ingest.sh - Nap 4 file CSV goc cua ViFoodRec len HDFS /data/raw
#
# Chay trong container namenode (thu muc du an duoc mount vao /home/jovyan/work):
#   docker exec namenode bash /home/jovyan/work/scripts/01_ingest.sh
# Them --force de ghi de file da co tren HDFS.
set -euo pipefail

SRC=/home/jovyan/work/data/raw
DST=/data/raw
FILES="food_dataset_cookyweb.csv food_dataset_mnmnweb.csv foods.csv ratings.csv"
PUT_OPT=""
[ "${1:-}" = "--force" ] && PUT_OPT="-f"

for f in $FILES; do
  [ -f "$SRC/$f" ] || { echo "Thieu $SRC/$f - tai tu repo ViFoodRec (Data/Raw Dataset, Data/Clean Dataset)"; exit 1; }
done

# Doi NameNode thoat safe mode (vai chuc giay sau khi khoi dong)
hdfs dfsadmin -safemode wait

hdfs dfs -mkdir -p "$DST"
for f in $FILES; do
  if hdfs dfs -test -e "$DST/$f" && [ -z "$PUT_OPT" ]; then
    echo "Da co $DST/$f (bo qua, dung --force de ghi de)"
  else
    hdfs dfs -put $PUT_OPT "$SRC/$f" "$DST/$f"
    echo "Da nap $f"
  fi
done

hdfs dfs -ls -h "$DST"
hdfs dfs -du -s -h "$DST"
