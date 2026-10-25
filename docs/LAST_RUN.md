# Lần chạy gần nhất – 26/10/2026

> File này được **ghi đè sau mỗi lần làm xong một yêu cầu** (xem quy tắc trong CLAUDE.md).
> Người dùng đọc nó ở bên chat claude.ai. Giữ đúng các mục bên dưới, không giới hạn độ dài.
> Dữ liệu hành vi là **mô phỏng**. Số liệu lấy từ `data/output/perf_report.json`, `perf_runs.jsonl` (đọc từ Spark History Server) và các report JSON.

## Yêu cầu
Trả lời 7 câu hỏi của bản đề xuất đo hiệu năng:
1. 06b `--fixed` chỉ chạy view test.
2. Không chạy đủ ma trận. Chỉ đo: 100% chuỗi 04 → 06f ở 1 và 2 worker, 1 lần, riêng 05 và 06b chạy thêm 2 lần mỗi cấu hình (tổng 3, lấy trung vị); 50% chuỗi ở 2 worker, 1 lần; 10% chuỗi ở 1 và 2 worker, 1 lần; danh mục (02, 03, 06g) ở 1 và 2 worker, 1 lần. Cập nhật `--plan` và ước tính (khoảng 3 giờ).
3. 06f `--fixed` bỏ `explore_beyond`.
4. Chỉ dừng `spark-worker-2`, không thêm cấu hình 1 × 4 core. Report ghi rõ 1 worker là giảm cả số core lẫn bộ nhớ executor.
5. Đồng ý `/perf/...` và 2 biến môi trường. Kiểm tra: chạy bản thường không đặt biến phải ra report giống bản trước.
6. 50% sinh bằng `04 --scale 0.5`, report ghi rõ đây là dân số sinh mới, không phải tập con.
7. Đồng ý collection `perf` và thẻ "Hiệu năng Spark", không đo 07.

Nếu 06b ở 100% với 1 worker hết bộ nhớ: không giảm rank cho riêng một bên, ghi lại, đo speedup 06b bằng `--quick`.
Việc cần làm: ghi D17, sửa code theo mục C và D, chạy thử theo bước 1–3 của mục I, rồi chạy toàn bộ bằng `scripts/09_perf.py`; tổng hợp, `07 --only perf`, sửa E24 và thẻ trang Đánh giá, pytest, LAST_RUN, /handoff.

## Đã làm
**1. D17** (`docs/DECISIONS.md`): thiết kế đã chốt theo 7 câu trả lời, thêm phần "Khi cài đặt và chạy" và "Kết quả chính".

**2. Sửa code (mục C, D):**
- `src/common.py`:
  - `Paths` đọc `VIFOOD_DATA_ROOT` (gốc HDFS, mặc định `/data`) và `VIFOOD_OUTPUT_DIR` (report; `processed_local` cũng chuyển vào `<thư mục>/processed`). `raw` luôn đọc `/data/raw`. Checkpoint ALS nằm trong gốc đo. `output_prod` luôn là `data/output`.
  - `VIFOOD_RUN_TAG` gắn vào tên ứng dụng (vd `06b_als|s100|w1|r2`).
  - `Timer` dùng chung: đo thời gian giai đoạn và gắn job group Spark trùng tên, để gom số liệu stage theo giai đoạn. Có `T.mark()` cho script không chia khối `with`.
- `src/rec_common.py`: thêm `--fixed`, `prod_report()` (đọc report của bản thật), dùng `common.Timer`.
- `--fixed`:
  - 06b: chỉ view test, tham số `best_*` của `model_als_report.json`;
  - 06c: bỏ vòng MinHash;
  - 06e: chỉ KMeans k = 3, 8, 11;
  - 06f: chỉ view test, trọng số từ `model_hybrid_report.json`, bỏ `tune_weights`, `explore_beyond`, `cold_items`;
  - 06g: λ, rank, regParam từ `model_control_report.json`. 06g đọc số liệu mô phỏng để so sánh từ `output_prod`.
- 02, 03, 04 có thêm `timings_s` (02, 03 có thêm `total_seconds`). 05 dùng `common.Timer`.
- `scripts/09_perf.py` (chạy trên máy, chỉ dùng thư viện chuẩn):
  - bật/tắt `spark-worker-2`, chờ master báo đủ worker; chờ khi có ứng dụng khác đang giữ executor;
  - chạy từng job bằng `docker exec` với 3 biến môi trường; lấy mẫu `docker stats` mỗi 10 giây (đỉnh RAM, CPU);
  - đọc History Server REST: thời lượng, jobs (job group), stages, executors;
  - ghi nối tiếp `perf_runs.jsonl` (chạy lại thì bỏ qua lần đã có), tổng hợp `perf_report.json`;
  - `--plan`, `--only muc[:wN[:job[:rK]]]`, `--with-06b-quick`, `--retry-failed`, `--summarize`.
- Bước 07: collection `perf` (1 doc mỗi job × mức × số worker + doc `summary`), chỉ nạp khi có `perf_report.json`.
- API:
  - E24 thêm khóa `perf` (`available`, `rows`, `speedup`, `chain_totals`, `scaling_2w`, `cluster`, `data`, `notes`);
  - E1: bước 09 "Đo hiệu năng Spark" (Xong khi có `perf.summary`), Structured Streaming thành bước 10.
- Trang Đánh giá:
  - thẻ "Thời gian chạy trên cụm" bỏ viên "Chưa", ghi rõ đây là lần chạy thật có dò tham số;
  - thẻ mới **"Hiệu năng Spark"**: câu tóm tắt; (a) cột nhóm thời gian từng job ở 100%, 1 và 2 worker; (b) đường tổng chuỗi theo mức 10 / 50 / 100%; (c) thanh ngang speedup từng job (100% / danh mục và 10%), vạch lý tưởng 2.
  - `hGroupedBars` có thêm `markX` (trục kéo tới vạch) và lề trái 20px (nhãn tiếng Việt dài nhất bị cắt 6px khi lề 8px); `lines` có `connectNulls` theo series; thêm lớp `.chart-tall` (380px).
- Test mới `test_perf_matches_collection`: E24 khớp collection `perf`, trung vị nằm trong [min, max], speedup = T(1 worker) ÷ T(2 worker), bước 09 đúng trạng thái. Chạy được cả khi không có `perf` (`vifood_local`).
- Tài liệu: `CLAUDE.md` (dòng bước 09, cách chạy), `docs/DATA_DICTIONARY.md` (`/perf`, `perf_runs.jsonl`, `perf_report.json`, collection `perf`, E1, E24), `.gitignore` (bỏ `processed/` và CSV trong `data/output/perf/`).

**3. Chạy thử (mục I, bước 1–3):**
- Bước 1: chạy 05, 06a, 06b `--quick`, 06c `--quick`, 06d, 06e `--quick`, 06f, 06g ở `--local` bằng code cũ (mốc), rồi bằng code mới, không đặt biến. **28/28 file report giống hệt** (bỏ qua khóa thời gian). `analysis/explain.txt` chỉ khác số hiệu nội bộ (`#id`, `plan_id`); chuẩn hóa các số này thì giống hệt. Sau đó khôi phục `data/output/` của bản cụm bằng `git checkout`.
- Bước 2: chuỗi 10%, 2 worker: 8/8 lần OK, `perf_runs.jsonl` có đủ số liệu. Kết quả 10% hợp lý (06b chỉ view test; hybrid NDCG@10 0,1589). `data/processed/` và report thật không bị đụng.
- Bước 3: 06b `--fixed` ở 100%, 1 worker: **không hết bộ nhớ**. 817,9 giây, không spill, đỉnh RAM container worker 2.970,6 MiB (giới hạn 4 GB). Không cần phương án `--quick`.

**4. Chạy toàn bộ:** 54 lần, **54 OK**, từ 21:26 ngày 25/10 đến 00:29 ngày 26/10 (tổng thời gian lệnh 2,71 giờ). Một lần (03 / danh mục / 1 worker) được chạy lại, xem mục "Lỗi / sự cố".

**5. Tổng hợp và nạp:** `perf_report.json` (46 dòng job × mức × số worker, 19 cặp speedup); `07 --only perf` ghi 47 doc (size 0,2 MB), các kiểm tra của 07 vẫn đạt (múi giờ: 0 / 4.929.272 phiên lệch; `food_id` ngoài `dishes`: 0). Restart `api`, trang Đánh giá hiển thị đủ 3 biểu đồ ở 1440px và 375px (không cuộn ngang).

## Số liệu chính
**Cấu hình:** máy ảo Docker 8 CPU, 18,9 GB (theo `docker info` lúc tổng hợp). Worker 2 core, 3 GB; executor 2 GB; driver 2 GB; `shuffle.partitions` 8 (06c đặt 64, 06f đặt 32). 1 worker = 1 executor 2 core 2 GB; 2 worker = 2 executor, tổng 4 core 4 GB: **giảm cả core lẫn bộ nhớ executor**.

**Dữ liệu mỗi mức** (sinh mới bằng 04, cùng seed; 10% và 50% **không phải tập con** của 100%):

| Mức | User | Sự kiện | events trên HDFS | results | models |
|---|---|---|---|---|---|
| 10% | 5.000 | 2.292.479 | 28,6 MB | 51,9 MB | 5,8 MB |
| 50% | 25.000 | 11.783.628 | 137,3 MB | 247,4 MB | 16,5 MB |
| 100% | 50.000 | 23.205.143 | 261,8 MB | 460,8 MB | 29,8 MB |

(Nhân 2 khi tính bản sao. Bản 100% ra đúng 23.205.143 sự kiện như `/data`.)

**Thời gian (giây, theo History Server).** 05 và 06b ở 100%: trung vị 3 lần [min–max]; còn lại 1 lần.

| Job | 10% · 1w | 10% · 2w | 50% · 2w | 100% · 1w | 100% · 2w | Speedup 100% | Speedup 10% |
|---|---|---|---|---|---|---|---|
| 04 Sinh hành vi | 100,7 | 97,4 | 275,2 | 864,4 | 527,5 | **1,64** | 1,03 |
| 05 Phân tích | 53,1 | 68,6 | 90,8 | 133,9 [133,3–135,8] | 110,3 [102,8–112,2] | 1,21 | 0,77 |
| 06a Chia dữ liệu | 41,0 | 47,5 | 73,8 | 134,1 | 103,1 | 1,30 | 0,86 |
| 06b ALS + baseline | 120,4 | 119,5 | 331,4 | 790,5 [776,5–817,9] | 599,3 [583,9–600,3] | 1,32 | 1,01 |
| 06c Content | 68,4 | 84,0 | 115,0 | 182,0 | 158,7 | 1,15 | 0,81 |
| 06d FP-Growth | 24,6 | 34,9 | 38,1 | 38,1 | 42,6 | 0,89 | 0,70 |
| 06e K-means | 27,0 | 35,6 | 43,0 | 48,8 | 52,4 | 0,93 | 0,76 |
| 06f Hybrid | 37,9 | 48,3 | 77,5 | 117,4 | 109,0 | 1,08 | 0,78 |
| **Tổng chuỗi** | **473,1** | **535,8** | **1.044,8** | **2.309,2** | **1.702,9** | **1,36** | **0,88** |

Danh mục (1w / 2w, speedup): 02 Làm sạch 42,1 / 47,0 (0,90); 03 Đặc trưng món 38,8 / 39,6 (0,98); 06g Đối chứng 20,7 / 28,4 (0,73).

**Theo quy mô (2 worker):** tổng chuỗi 10% → 50% → 100% tăng 1,95 và 3,18 lần, trong khi dữ liệu tăng 5 và 10 lần. Chỉ 04 (5,42 lần) và 06b (5,02 lần) tăng gần tuyến tính; 05 1,61; 06a 2,17; 06c 1,89; 06d 1,22; 06e 1,47; 06f 2,26 lần. Số sự kiện xử lý mỗi giây ở 100% / 2 worker: 04 43.991, 05 210.382.

**Giải thích speedup dưới 2** (số liệu stage của lần gần trung vị, 100%):

| Job | Worker | Tổng thời gian task | Shuffle đọc (từ xa) | Spill bộ nhớ / đĩa | CPU / thời gian chạy |
|---|---|---|---|---|---|
| 05 | 1 | 179,1 s | 300,4 MB (0) | 3.344,0 / 263,5 MB | 0,928 |
| 05 | 2 | 267,2 s | 322,7 MB (161,3) | 3.241,9 / 258,4 MB | 0,847 |
| 06a | 1 | 208,2 s | 642,9 MB (0) | 7.526,9 / 930,1 MB | 0,901 |
| 06a | 2 | 267,9 s | 677,3 MB (342,9) | 4.129,9 / 530,1 MB | 0,860 |
| 06b | 1 | 1.491,5 s | 3.746,2 MB (0) | 0 / 0 | 0,988 |
| 06b | 2 | 1.852,3 s | 3.748,1 MB (1.815,5) | 0 / 0 | 0,979 |
| 06f | 1 | 151,4 s | 1.286,2 MB (0) | 5.715,7 / 818,6 MB | 0,864 |
| 06f | 2 | 235,2 s | 1.290,2 MB (593,8) | 3.957,1 / 514,3 MB | 0,778 |

- Thêm worker thì **tổng thời gian task tăng** (06b +24%, 05 +49%): 2 worker dùng chung 8 CPU của một máy ảo với datanode, namenode và driver, và khoảng một nửa shuffle đọc từ worker kia qua mạng ảo.
- Phần không song song được: khởi động SparkSession, `collect` về driver, numpy trên driver. Job nhỏ có ít task nên phần này chiếm phần lớn; ở 10% thêm worker còn làm chậm hơn (chuỗi 0,88).
- Bù lại, 1 worker ít bộ nhớ hơn nên spill nhiều hơn (06a, 06f; 04 spill 2.144 MB với 1 worker, 0 với 2 worker). 04 có speedup cao nhất (1,64) vì phần sinh sự kiện (mapInPandas, Python) chia đều theo core.
- 06b, giai đoạn `test:als_implicit`: 716,6 giây (1 worker) so với 516,5 giây (2 worker); tổng thời gian task 1.419,5 so với 1.741,6 giây; đọc từ xa 0 so với 1.578,1 MB.
- Lưu ý: `executorCpuTime` không tính CPU của tiến trình Python, nên tỷ lệ CPU của 04 chỉ 0,07–0,08.

**Đỉnh RAM container** (lấy mẫu `docker stats`): worker cao nhất 3.782,7 MiB (06c, 100%, 1 worker; giới hạn 4 GB); `jupyter` (driver) cao nhất 3.108,9 MiB (06f, 100%, 2 worker).

**pytest:** `vifood` 62/62 đạt; `vifood_local` 59 đạt, 3 bỏ qua (`perf` trống, test nhận đúng trạng thái "Chưa").

## Lỗi / sự cố và cách xử lý
- **Lần 03 / danh mục / 1 worker không có số trên History Server:** job xong (exit 0, report đủ), nhưng event log không được đóng (còn file `appstatus_…`), History Server coi là chưa kết thúc. Chạy lại riêng lần này thì lặp lại y hệt; mọi lần khác (kể cả 03 với 2 worker) đều bình thường; log không có lỗi nào liên quan. Chưa rõ nguyên nhân. Cách xử lý: `--summarize` tra lại ứng dụng theo tên (đọc được cả ứng dụng chưa đóng) và lấy thời lượng = kết thúc job cuối − bắt đầu ứng dụng = 38,8 giây, ghi `duration_note` trong report. Thời gian lệnh `docker exec` khớp với lần 2 worker (42,8 so với 42,5 giây). Bản ghi bị thay thế lưu ở `logs/perf/_03_catalog_w1_r1_event_log_khong_dong.json`.
- **History Server cập nhật chậm:** thêm bước bổ sung khi tổng hợp và tăng thời gian chờ lên 300 giây, tra trong 200 ứng dụng gần nhất (trước là 40).
- **3 lần 06b ở 100% / 1 worker chạy liền nhau** (bộ lọc của bước chạy thử khớp cả 3 lần), không xen kẽ với 2 worker. Ba lần lệch nhau 5,3%.
- **Ước tính cũ thấp hơn thực tế ở 10%** (giả định 0,2 lần thời gian 100%; thực tế chuỗi 10% bằng 0,31 lần). Đã sửa `--plan` theo số đo. Toàn bộ 54 lần mất 2,71 giờ.
- **Ở 375px, nhãn số trên cột nhỏ (06d, 06e) chồng nhau** trong biểu đồ (a). Không ảnh hưởng đọc số (tooltip vẫn đúng), chưa sửa.
- Lúc bắt đầu phiên cụm đang chạy đủ 11 container. Cuối phiên đã bật lại `spark-worker-2` (master báo 2 worker, 4 core). `/perf` trên HDFS vẫn giữ.

## Cần người dùng quyết định
1. **Ảnh History Server cho báo cáo** (Timeline và Executors của 06b ở 1 và 2 worker, `docs/images/09_*`): chụp ngay, hay để chung với đợt chụp ảnh cuối dự án như PROGRESS đang ghi?
2. **Giữ `/perf` trên HDFS** (`hdfs dfs -du -s /perf`: 1,3 GB, 2,5 GB tính cả bản sao) đến khi viết xong báo cáo, hay xóa ngay? Đề xuất: giữ, vì cần khi muốn chạy thêm.
3. **Đo thêm 50% với 1 worker** (khoảng 20 phút) để đường 1 worker trên biểu đồ (b) có đủ 3 điểm? Hiện đường này nối thẳng 10% với 100%.
4. **Bước tiếp theo** là Structured Streaming, viết bản thiết kế trước (nguồn sự kiện, cửa sổ, watermark, ghi `trending`) rồi mới làm: đồng ý không?

Việc cần người làm (không đổi): kiểm tra tay 100 món; dựng notebook biểu đồ cho bước 05 và 06; xem trang Phân khúc và thẻ Hiệu năng Spark trên trang Đánh giá.

## Commit
- `Buoc 09: do hieu nang Spark 1/2 worker x 10/50/100%` (`src/common.py`, `src/rec_common.py`, `src/02`–`07`, `scripts/09_perf.py`, `api/routers/{evaluation,overview}.py`, `api/tests/test_overview.py`, `web/danh-gia.html`, `web/js/{danh-gia,charts}.js`, `web/css/theme.css`, `data/output/{perf_runs.jsonl,perf_report.json,perf/,export_report.json}`, `.gitignore`, `CLAUDE.md`, D17, DATA_DICTIONARY, PROGRESS, file này).
