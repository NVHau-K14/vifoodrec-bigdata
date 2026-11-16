# ViFoodRec Big Data: phân tích hành vi ăn uống và gợi ý món ăn

Đồ án môn Nhập môn Big Data. Pipeline Spark trên cụm Docker (HDFS + Spark Standalone) đi từ dữ liệu món ăn
thật đến phân tích hành vi, mô hình gợi ý, xuất MongoDB, API + dashboard và Structured Streaming.

- **Món ăn là món thật**: 5.499 món sau khi làm sạch, từ Cooky và Món Ngon Mỗi Ngày (bộ ViFoodRec).
- **Hành vi người dùng là mô phỏng**: 50.000 user, 23.205.143 sự kiện (xem, lưu, nấu, chấm), 10/2025 → 09/2026,
  sinh ở bước 04. Mọi kết quả về hành vi chỉ đúng với dữ liệu mô phỏng này.
- Số liệu kiểm tra của từng bước nằm trong `data/output/*report*.json`; quyết định thiết kế trong
  `docs/DECISIONS.md` (D1–D18); ý nghĩa các cột trong `docs/DATA_DICTIONARY.md`.

## 1. Cấu trúc thư mục

```
docker/            docker-compose.yml (11 container), Dockerfile.spark, Dockerfile.api, hadoop.env
src/               02–07, 10*: các bước Spark (common.py, rec_common.py, stream_common.py dùng chung)
scripts/           01_ingest.sh, 08_fetch_vendor.sh, 09_perf.py, 10_stream.sh, make_sample.py
api/               FastAPI (bước 08): main.py, routers/, tests/ (pytest), bench_latency.py
web/               dashboard 7 trang (HTML/CSS/JS thuần + ECharts, không cần mạng khi demo)
notebooks/         05_hanh_vi, 06_mo_hinh, 09_10_hieu_nang_luong: biểu đồ cho báo cáo (đọc data/output/*.json)
data/raw/          4 CSV gốc (không đưa lên Git; tải từ repo ViFoodRec)
data/sample/       vài trăm dòng mỗi bảng để xem cấu trúc (scripts/make_sample.py)
data/output/       report JSON của từng bước, bảng phân tích nhỏ, kết quả đo hiệu năng
docs/              PROGRESS, DECISIONS, DATA_DICTIONARY, LAST_RUN, images/ (ảnh chụp và biểu đồ)
```

## 2. Dựng cụm

Yêu cầu: Docker Desktop (Windows dùng WSL2), khoảng 12 GB RAM cho Docker, 10 GB đĩa. Đã chạy trên Windows 11, RAM 24 GB.

```bash
cp .env.example .env              # rồi điền mật khẩu (MongoDB phải trùng MONGO_INITDB_ROOT_PASSWORD trong compose)
cd docker
docker compose up -d --build      # lần đầu build image vifood-spark:4.2.0 và vifood-api:0.1
docker compose ps                 # đủ 11 container
```

| Container | Vai trò | Cổng trên máy |
|---|---|---|
| `namenode`, `datanode1`, `datanode2` | HDFS (replication 2) | UI http://localhost:9870, RPC 8020 |
| `spark-master` | Spark 4.2.0 Standalone | UI http://localhost:8080, 7077 |
| `spark-worker-1`, `spark-worker-2` | mỗi worker 2 core, 3 GB | UI http://localhost:8081, http://localhost:8082 |
| `spark-history` | xem lại job đã chạy (event log ở `logs/spark-events/`) | http://localhost:18080 |
| `jupyter` | driver của mọi job; Jupyter Lab (token `bigdata`) | http://localhost:8888, Spark UI job đang chạy :4040, luồng Structured Streaming :4041 |
| `mongodb` | MongoDB 7, database `vifood` | 27017 |
| `mongo-express` | xem MongoDB trên web (tài khoản trong `.env`) | http://localhost:8090 |
| `api` | FastAPI + dashboard | http://localhost:8000, tài liệu API http://localhost:8000/docs |

Thư mục dự án được mount vào `/home/jovyan/work` ở mọi container. Dữ liệu HDFS và MongoDB nằm trong Docker volume,
vẫn còn sau khi tắt máy. **Không** chạy `docker compose down -v` (xóa volume là mất toàn bộ HDFS).

NameNode ở chế độ an toàn khoảng 30 giây đầu sau khi khởi động (`Safe mode is ON`): đợi rồi chạy lại.

## 3. Chạy pipeline 01 → 10

Các lệnh dưới chạy từ thư mục dự án trên máy (Git Bash). Job Spark chạy trong container `jupyter` và nộp lên cụm:

```bash
export MSYS_NO_PATHCONV=1         # Git Bash: không đổi /home/jovyan/work thành đường dẫn Windows
RUN="docker exec -w /home/jovyan/work -e PYTHONPATH=/usr/local/spark/python/lib/py4j-0.10.9.9-src.zip:/usr/local/spark/python jupyter python"
```

| Bước | Lệnh | Thời gian trên cụm, 2 worker (nguồn) | Kết quả |
|---|---|---|---|
| 01 Nạp HDFS | `docker exec namenode bash /home/jovyan/work/scripts/01_ingest.sh` | vài giây | `/data/raw` (4 CSV) |
| 02 Làm sạch | `$RUN src/02_clean.py` | 47 giây (`perf_report`) | `/data/curated/{foods,ratings_original}` |
| 03 Đặc trưng món | `$RUN src/03_features.py` | 40 giây (`perf_report`) | `/data/features/dish_features` |
| 04 Sinh hành vi | `$RUN src/04_simulate.py --scale 1.0` | 528 giây (`perf_report`) | `/data/events/{events,users,users_truth}` |
| 05 Phân tích | `$RUN src/05_analysis.py` | 110 giây (`perf_report`) | `/data/results/analysis` (14 bảng) |
| 06 Mô hình | `$RUN src/06a_split.py`, rồi `06b_als.py` … `06g_control.py` theo thứ tự | 4.853 giây khi dò tham số (`model_*_report`); 1.093 giây với `--fixed` (`perf_report`) | `/data/results/models`, `/data/models` |
| 07 Xuất MongoDB | `$RUN src/07_export_mongo.py` | 66 giây | 26 collection trong `vifood` |
| 08 API + dashboard | `cd docker && docker compose up -d --build api` | – | http://localhost:8000 |
| 09 Đo hiệu năng | `python scripts/09_perf.py --plan`, rồi `python scripts/09_perf.py` (chạy trên máy) | vài giờ (`--plan` in ước tính) | `data/output/perf_report.json` |
| 10 Structured Streaming | `$RUN src/10a_stream_prep.py`, rồi xem mục 4 | – | `/data/stream`, MongoDB `trending` |

- Mọi script có `--local` (Spark local, ghi vào `data/hdfs_local/`, database `vifood_local`). Bước sinh dữ liệu và
  các bước nặng có `--scale` (vd `--scale 0.01`): nên chạy thử nhỏ trước rồi mới chạy đủ.
- Mỗi bước ghi `data/output/<bước>_report.json`; đọc report để kiểm tra sau khi chạy.
- Cụm chỉ có 4 core: tắt kernel notebook trước khi chạy job; không chạy job `--local` cùng lúc với job trên cụm.
- Kiểm thử API: `docker exec api python -m pytest -q -p no:cacheprovider api/tests` (mặc định database `vifood`).
  Đo độ trễ API: `docker exec -w /home/jovyan/work api python -m api.bench_latency`.
- Biểu đồ cho báo cáo: mở `notebooks/*.ipynb` trong Jupyter rồi *Run All* (không cần Spark), ảnh ghi ra `docs/images/nb_*.png`.

## 4. Demo Structured Streaming (bước 10)

Replayer phát lại sự kiện mô phỏng của Chủ nhật 27/09/2026 theo đồng hồ mô phỏng, ghi file JSON Lines vào HDFS
`/data/stream/incoming`; luồng Spark đếm lượt nấu / xem / lưu theo cửa sổ 60 phút trượt 15 phút × vùng × món
(watermark 10 phút, khử trùng theo `event_id`) và ghi MongoDB `trending` sau mỗi micro-batch.

```bash
bash scripts/10_stream.sh reset                          # xóa checkpoint, incoming, trending
bash scripts/10_stream.sh start --from 16:00 --speed 60  # 1 giây thật = 1 phút mô phỏng; 17–19h đông nhất
bash scripts/10_stream.sh status
bash scripts/10_stream.sh stop
```

Trong lúc chạy: trang **Thời gian thực** http://localhost:8000/thoi-gian-thuc.html (tự cập nhật mỗi 5 giây),
Spark UI của luồng http://localhost:4041/StreamingQuery/. Luồng giữ 2 core: không đo hiệu năng (09) khi luồng đang chạy.
Kiểm tra đúng / đo: `$RUN src/10c_stream_check.py` (3 kịch bản đến trễ) và `$RUN src/10d_stream_bench.py`
(độ trễ, thông lượng); cả hai đều reset luồng trước mỗi lần chạy.

## 5. Nếu công khai repo

Repo hiện để riêng tư. Các commit cũ có file `.env` (từ 26/10 chỉ còn `.env.example`), và `docker/docker-compose.yml`
ghi mật khẩu MongoDB mặc định (`MONGO_INITDB_ROOT_PASSWORD`). Trước khi công khai repo:

- **đổi mật khẩu MongoDB** (tài khoản `admin`) và **mật khẩu đăng nhập mongo-express** (`ME_CONFIG_BASICAUTH_PASSWORD`),
  rồi cập nhật `.env` và `MONGO_INITDB_ROOT_PASSWORD` trong compose. Biến `MONGO_INITDB_*` chỉ có tác dụng khi volume
  `mongodb` còn trống, nên với cụm đang chạy phải đổi mật khẩu ngay trong MongoDB (`db.changeUserPassword`);
- mật khẩu cũ vẫn đọc được trong lịch sử Git; đổi mật khẩu là đủ, không cần làm sạch lịch sử.

## 6. Dữ liệu và giấy phép

- Dữ liệu món ăn: bộ ViFoodRec: https://github.com/QuocAn55/A-New-Dataset-and-Empirical-Evaluation-for-Vietnamese-Food-Recommendation-System (Cooky, Món Ngon Mỗi Ngày). Đặt 4 file `food_dataset_cookyweb.csv`,
  `food_dataset_mnmnweb.csv`, `foods.csv`, `ratings.csv` vào `data/raw/` trước bước 01. Không sửa `data/raw/`.
- Dinh dưỡng và `cooking_time` trong dữ liệu gốc là số ngẫu nhiên: không dùng để rút ra kết luận.
- Font Be Vietnam Pro (giấy phép OFL, `web/fonts/OFL.txt`), ECharts 5.5.1 (Apache 2.0) nằm sẵn trong `web/`.
