# Lần chạy gần nhất – 26/10/2026 (sáng)

> File này được **ghi đè sau mỗi lần làm xong một yêu cầu** (xem quy tắc trong CLAUDE.md).
> Người dùng đọc nó ở bên chat claude.ai. Giữ đúng các mục bên dưới, không giới hạn độ dài.
> Dữ liệu hành vi là **mô phỏng**. Số liệu lấy từ `data/output/perf_report.json`, `perf_runs.jsonl` (đọc từ Spark History Server), `export_report.json` và `analysis/heatmap_hour_dow.json`.

## Yêu cầu
Trả lời 4 câu của LAST_RUN trước:
1. Ảnh History Server: chụp cùng đợt ảnh cuối dự án.
2. Giữ `/perf` đến khi viết xong báo cáo.
3. Đo thêm chuỗi 50% với 1 worker, 1 lần. Thêm vào `perf_report.json` khóa `speedup_by_scale` (speedup của cả chuỗi và của 04, 05, 06b ở 10/50/100%). Thẻ Hiệu năng Spark thêm biểu đồ (d): speedup theo mức dữ liệu, vạch lý tưởng 2. Chạy lại `07 --only perf`, sửa E24 và pytest.
4. Bước tiếp theo là Structured Streaming: viết thiết kế vào LAST_RUN trước, chưa code (nguồn sự kiện; schema, cửa sổ, watermark, phép tổng hợp; sink `foreachBatch` idempotent, checkpoint; chạy trên cụm, song song với `api`, bật/tắt khi demo; schema `trending`, sửa E25 và trang Thời gian thực; kiểm thử và đo; các điểm cần quyết định).

Sửa nhỏ: ẩn nhãn số trên cột của biểu đồ (a) khi thẻ hẹp hơn 520px.

## Đã làm
**1. Câu 1 và 2:** ghi vào PROGRESS (ảnh History Server chụp cùng đợt cuối; `/perf` giữ đến khi viết xong báo cáo). Không đụng `/perf`.

**2. Đo 50% / 1 worker** (`scripts/09_perf.py`):
- `build_plan` thêm `add("s050", 1, CHAIN)`, docstring sửa theo. `--plan`: 8/62 lần cần chạy, ước tính 0,48 giờ.
- Chạy `python scripts/09_perf.py --only s050:w1`: 8/8 lần OK, từ 07:58 đến 08:29 (tổng thời gian lệnh 1.697,5 giây). Cuối cùng script bật lại `spark-worker-2`, master báo 2 worker, 4 core.
- Report của 1 và 2 worker ở 50% **giống hệt nhau** (`simulate_report`, `analysis_report`, `model_als_report`, `model_hybrid_report`, bỏ qua khóa thời gian): 04 sinh lại `/perf/s050` ra đúng dữ liệu cũ (11.783.628 sự kiện).

**3. `speedup_by_scale`:** `summarize()` thêm danh sách `speedup_by_scale [{key, step, level, level_pct, t_1w_s, t_2w_s, speedup, efficiency}]`, `key` là `chain` (tổng chuỗi lấy từ `chain_totals` khi đủ 8 job) hoặc `04`, `05`, `06b` (`SCALE_JOBS`). Thêm 1 câu vào `notes`. Phải chạy `--summarize` lại một lần, vì tiến trình đo đã nạp code từ trước khi sửa.

**4. MongoDB và API:**
- `07 --only perf`: collection `perf` 55 doc (54 dòng + `summary`), size 213.379 B. Các kiểm tra của 07 vẫn đạt (múi giờ: 0 / 4.929.272 phiên lệch; `food_id` ngoài `dishes`: 0).
- E24: khóa `perf` trả thêm `speedup_by_scale`.
- Test `test_perf_matches_collection` thêm: `speedup_by_scale` có đủ 12 cặp (chuỗi, 04, 05, 06b × 3 mức); thời gian lấy đúng từ `chain_totals` / `rows`; speedup = T(1 worker) ÷ T(2 worker).

**5. Thẻ "Hiệu năng Spark"** (trang Đánh giá):
- Hàng thứ hai thành 2 cột: (c) speedup từng job và **(d) speedup theo quy mô dữ liệu**: 4 đường (cả chuỗi nét đậm, 04, 05, 06b), trục y từ 0, vạch đứt "lý tưởng 2,00". Tên series là mã job để chú giải nằm trên 1 dòng ở 375px; tên đầy đủ ghi trong dòng chú thích.
- `lines()` có thêm `markY` (vạch ngang màu `--neutral`, nhãn nằm trong vùng vẽ, trục kéo tới vạch và làm tròn lên bội số 0,5) và `width` theo series.
- Câu tóm tắt thêm "Speedup của cả chuỗi theo mức dữ liệu: 0,88 ở 10%, 1,59 ở 50%, 1,36 ở 100%" (lấy từ API). Biểu đồ (b) bỏ câu "1 worker không đo ở 50%" và bỏ `connectNulls`.
- **Sửa nhỏ:** `groupedBars()` có tùy chọn `labelMinWidth`; biểu đồ (a) dùng 520: nhãn số trên cột ẩn khi thẻ hẹp hơn 520px (theo dõi bằng ResizeObserver). Kiểm tra: thẻ 1.110px hiện nhãn, thẻ 342px (màn 375px) ẩn nhãn.
- Thêm: trục x của (c) bật `hideOverlap` (ở 375px các nhãn 0,50 / 1,00 / 1,50 / 2,00 dính nhau).
- `theme.css`: `.mini-grid + .mini-grid {margin-top:16px}`.
- Đã xem ở 1440px và 375px: không cuộn ngang (scrollWidth 375 ở màn 375), không có mã màu hex ngoài `theme.css` và `charts.js`.

**6. pytest:** `vifood` 62/62 đạt; `vifood_local` 59 đạt, 3 bỏ qua (như trước).

**7. Thiết kế Structured Streaming:** xem mục riêng bên dưới. Chưa viết code.

**8. Tài liệu:** D17 thêm phần "Bổ sung 26/10 (sáng)"; `DATA_DICTIONARY.md` (`perf_report.json`, collection `perf`, E24 thêm `speedup_by_scale`; sửa dòng `perf` trong bảng collection bị vỡ định dạng do dấu `|`); PROGRESS.

## Số liệu chính
**Thời gian ở 50% (giây, theo History Server, mỗi cấu hình 1 lần):**

| Job | 50% · 1w | 50% · 2w | Speedup | Efficiency |
|---|---|---|---|---|
| 04 Sinh hành vi | 604,0 | 275,2 | **2,19** | 1,10 |
| 05 Phân tích | 110,5 | 90,8 | 1,22 | 0,61 |
| 06a Chia dữ liệu | 99,0 | 73,8 | 1,34 | 0,67 |
| 06b ALS + baseline | 518,6 | 331,4 | 1,56 | 0,78 |
| 06c Content | 155,4 | 115,0 | 1,35 | 0,68 |
| 06d FP-Growth | 38,8 | 38,1 | 1,02 | 0,51 |
| 06e K-means | 46,6 | 43,0 | 1,08 | 0,54 |
| 06f Hybrid | 85,5 | 77,5 | 1,10 | 0,55 |
| **Tổng chuỗi** | **1.658,4** | **1.044,8** | **1,59** | 0,80 |

**`speedup_by_scale`:**

| | 10% | 50% | 100% |
|---|---|---|---|
| Chuỗi 04 → 06f | 0,88 | **1,59** | 1,36 |
| 04 Sinh hành vi | 1,03 | 2,19 | 1,64 |
| 05 Phân tích hành vi | 0,77 | 1,22 | 1,21 |
| 06b ALS + baseline | 1,01 | 1,56 | 1,32 |

- Tổng chuỗi 1 worker theo mức: 473,1 → 1.658,4 → 2.309,2 giây (3,51 và 4,88 lần so với 10%); 2 worker: 535,8 → 1.044,8 → 1.702,9 giây (1,95 và 3,18 lần).
- Số sự kiện mỗi giây ở 50%: 04 19.509 (1 worker) / 42.818 (2 worker); 05 106.639 / 129.776.

**Vì sao speedup cao nhất ở 50% chứ không phải 100%** (số liệu stage):
- **04 ở 50% / 1 worker chậm bất thường.** Giai đoạn sinh (stage mapInPandas) tốn 543,6 giây thời gian task cho 25.000 user, tức 21,7 ms/user. Các cấu hình khác: 100% / 1 worker 15,6 ms; 50% / 2 worker 17,9 ms; 100% / 2 worker 18,5 ms. `generate_write` 546,7 giây ở 50% so với 801,4 giây ở 100% (chỉ gấp 1,47 lần dù dữ liệu gấp 2). Chỉ có 1 lần nên chưa biết đây là nhiễu của máy lúc chạy (sáng nay, các lần đo trước chạy ban đêm) hay thật. Bỏ 04 ra, speedup phần còn lại của chuỗi là **1,37 ở 50% và 1,23 ở 100%**.
- **Ở 100%, thêm worker tốn thêm nhiều thời gian task hơn.** 06b: tổng thời gian task tăng 5,8% khi thêm worker ở 50% (910,4 → 963,1 giây), nhưng tăng 24,2% ở 100% (1.491,5 → 1.852,3 giây). GC 6,7 → 11,2 giây, đọc shuffle từ xa 1.815,5 MB ở 100% (1.023,0 MB ở 50%). Giai đoạn `test:als_implicit`: speedup 1,62 ở 50% (429,7 / 265,4 giây), 1,39 ở 100% (716,6 / 516,5 giây).
- Spill ở 50% / 1 worker: 05 1.856,0 MB (bộ nhớ) so với 528,0 MB khi 2 worker; 06a 2.199,7 MB; 06c 11.923,6 MB bộ nhớ, 2.626,4 MB đĩa; 06f 2.720,0 MB. 04 và 06b không spill.
- Đỉnh RAM container ở 50% / 1 worker: `spark-worker-1` 3.123,2 MiB (06c), `jupyter` 2.701,3 MiB (06f).

**Phát hiện phụ ở 04:** phần sinh sự kiện chạy **2 lần** trong mỗi lần chạy 04. `repartitionByRange(12, "month")` phải lấy mẫu để tìm ranh giới, nên Spark chạy toàn bộ mapInPandas một lần cho việc lấy mẫu (stage 4, không ghi shuffle) rồi chạy lại để ghi thật (stage 6). Hai stage có thời gian task gần bằng nhau, vd 100% / 2 worker: 926,2 và 923,4 giây. Sửa (cache trước khi chia, hoặc chia theo hash) có thể giảm gần một nửa thời gian sinh, nhưng số đo 04 sẽ không còn so được với các lần đã đo (câu 12).

## Thiết kế Structured Streaming (bước 10, chưa code)

Mục tiêu: trang Thời gian thực trả lời "món nào đang được nấu nhiều trong 1 giờ qua, ở từng vùng", cập nhật vài giây một lần.
Phần này thể hiện các kỹ thuật của Structured Streaming: nguồn file trên HDFS, cửa sổ theo thời gian sự kiện và watermark, join luồng với bảng tĩnh, khử trùng trong watermark, ghi MongoDB idempotent bằng `foreachBatch`, checkpoint, đo độ trễ và thông lượng.
Dữ liệu vẫn là **mô phỏng** (phát lại sự kiện của bước 04).

Các con số về lưu lượng dưới đây là **ước tính** từ `data/output/analysis/heatmap_hour_dow.json` chia cho 52 ngày Chủ nhật trong năm mô phỏng (giờ ở bảng này là giờ bắt đầu phiên). Số chính xác của ngày được chọn sẽ do bước chuẩn bị đếm và ghi vào report.

### A. Nguồn sự kiện
**A1. Phát lại hay sinh mới.** Đề xuất **phát lại** `events` của bước 04, vì:
- cùng phân bố với các trang khác của dashboard (vùng, bữa, đuôi dài), không phải viết bộ sinh thứ hai;
- có sẵn "đáp án": đếm bằng Spark batch trên đúng đoạn được phát, nên kiểm tra được kết quả luồng khớp tuyệt đối;
- sinh mới chỉ hơn ở chỗ chạy vô hạn. Phát lại cũng lặp được (hết ngày thì phát tiếp ngày khác) nếu cần.

**A2. Đoạn phát lại.** Chủ nhật **27/09/2026**: Chủ nhật cuối của tháng test (09/2026), Chủ nhật là ngày đông nhất tuần (4.435.996 sự kiện cả năm, so với 2.798.919 của thứ Ba).
- Ước tính 1 ngày Chủ nhật: khoảng 85.300 sự kiện, 10.400 lượt nấu. Giờ đông nhất: 19h khoảng 9.700 sự kiện; 17h khoảng 1.280 lượt nấu.
- 0h–5h gần như trống, nên mặc định phát từ 06:00 giờ mô phỏng (`--from`).

**A3. Tốc độ.** Replayer giữ một đồng hồ mô phỏng, `--speed 60` mặc định (1 giây thật = 1 phút mô phỏng):
- cả ngày mất 24 phút; 16h–21h mất 5 phút;
- giờ cao điểm khoảng 162 sự kiện/giây, 21 lượt nấu/giây;
- `--speed 300` để demo nhanh (cao điểm khoảng 810 sự kiện/giây); `--speed max` để đo thông lượng (mục F).

**A4. Định dạng và đường đi: file JSON Lines trên HDFS.**
- `src/10a_stream_prep.py` (Spark batch, chạy 1 lần cho mỗi ngày):
  - lọc `events` của ngày đã chọn, gán `event_id` (thứ tự theo `ts`, `session_id`), ghi `data/stream/replay_<ngày>.jsonl.gz` cho replayer đọc;
  - ghi **đáp án**: đếm theo cửa sổ × vùng × món bằng batch, cùng định nghĩa cửa sổ với luồng → `/stream/truth/<ngày>` và top 20 trong `data/output/stream_truth_<ngày>.json`.
- `src/10b_replayer.py` (Python thường, không dùng Spark, chạy trong container `jupyter`):
  - mỗi giây thật ghi 1 file `part-<số>.jsonl` gồm các sự kiện có `ts` trong khoảng đồng hồ mô phỏng vừa trôi qua, gắn `emit_ts` (giờ thật lúc ghi);
  - ghi qua WebHDFS (`http://namenode:9870`, đã thử: gọi được từ `jupyter`, `requests` 2.34.2 có sẵn) vào `/stream/_staging/`, rồi RENAME sang `/stream/incoming/`. Rename trong HDFS là nguyên tử, nên file source chỉ thấy file đã ghi xong.
  - Tùy chọn `--late` (mặc định bật): 3% sự kiện bị giữ lại 1–8 phút mô phỏng (vẫn trong watermark, phải được tính), 0,3% bị giữ 20–40 phút (quá watermark, phải bị bỏ), 0,2% bị gửi lặp cùng `event_id` (phải bị khử). `--late 0` để kiểm tra khớp tuyệt đối.
- Không chọn:
  - **Kafka:** thêm 1–2 container (khoảng 1 GB RAM) và một hệ thống phải cấu hình, trong khi chỉ có 1 nguồn, khoảng 1.000 sự kiện/giây. Báo cáo ghi rõ: đổi `readStream.format("json")` sang `format("kafka")` là chuyển lên Kafka, phần còn lại giữ nguyên.
  - **Socket:** không phát lại được, không checkpoint, không exactly-once; tài liệu Spark ghi là chỉ dùng để thử.
  - **Rate source:** không có nội dung thật.
  - **Thư mục mount trên máy** (`file:///home/jovyan/work/...`, worker cũng thấy): chạy được, nhưng ổ Windows qua WSL2 liệt kê nhiều file nhỏ chậm, và không phải HDFS.

### B. Schema, cửa sổ, watermark, phép tổng hợp
**B1. Schema sự kiện** (khai báo cứng, không suy luận):

| Cột | Kiểu | Ghi chú |
|---|---|---|
| `event_id` | long | Khóa để khử trùng |
| `user_id`, `food_id` | int | |
| `event_type` | string | view, favorite, cook, rate |
| `ts` | timestamp | Giờ sự kiện mô phỏng, ISO 8601 có `+07:00` |
| `meal_slot` | string | |
| `session_id` | long | |
| `rating` | float | Chỉ có ở `rate` |
| `emit_ts` | timestamp | Giờ thật lúc replayer ghi file, dùng để đo độ trễ |

Sự kiện không mang vùng hay tuổi (ứng dụng thật không gửi hồ sơ trong mỗi sự kiện), nên luồng join với `users` (50.000 dòng, bảng tĩnh, broadcast) để lấy `region`.

**B2. Các bước của query:**
```
readStream.json(/stream/incoming, maxFilesPerTrigger=10, cleanSource=archive -> /stream/archive)
 -> withWatermark("ts", "10 minutes")
 -> dropDuplicatesWithinWatermark("event_id")
 -> filter(event_type in cook, view, favorite)
 -> join(broadcast(users.select(user_id, region)))
 -> groupBy(window(ts, "60 minutes", "15 minutes"), region, food_id)
    .agg(cooks, views, favorites, last_emit = max(emit_ts))
 -> outputMode("update"), trigger(processingTime="5 seconds")
 -> foreachBatch(ghi MongoDB, mục C)
```

**B3. Cửa sổ:** 60 phút, trượt 15 phút ("thịnh hành trong 1 giờ qua", cập nhật mỗi 15 phút mô phỏng, tức 15 giây thật ở 60x). Mỗi sự kiện rơi vào 4 cửa sổ.

**B4. Watermark 10 phút mô phỏng.**
- Nhận sự kiện trễ tối đa 10 phút. Cửa sổ [t, t+60) được chốt khi watermark vượt t+60, tức khi luồng đã thấy sự kiện có `ts` sau t+70 (ở 60x, khoảng 10 giây thật sau khi cửa sổ kết thúc).
- Trạng thái chỉ giữ các cửa sổ chưa chốt (khoảng 5 cửa sổ × vùng × món đã có sự kiện): cỡ vài chục nghìn dòng, đủ nhỏ cho state store mặc định (HDFS-backed).

**B5. Theo vùng hay bữa.**
- Nhóm theo **vùng** (Bắc, Trung, Nam). "Toàn quốc" là tổng 3 vùng, cộng trong `foreachBatch`.
- **Bữa** không thành một chiều nhóm: cửa sổ 1 giờ gần như nằm trọn trong 1 bữa, nên chỉ ghi `meal_slot` chiếm đa số của cửa sổ làm nhãn. Chia thêm theo bữa sẽ nhân trạng thái mà hầu hết ô bằng 0.

**B6. Xếp hạng** theo `cooks`, hòa thì theo `views`, rồi `food_id` (để chạy lại ra cùng thứ tự). "Tăng nhanh": so `cooks` với cửa sổ trước đó 15 phút, cùng phạm vi.

### C. Sink, idempotent, checkpoint
**C1. `foreachBatch(df, batch_id)`.** `df` gồm các ô (cửa sổ, vùng, món) vừa thay đổi trong batch, mang số đếm **tuyệt đối** của ô (không phải phần tăng thêm). Các bước:
1. `collect()` lên driver (vài trăm đến vài nghìn dòng mỗi batch).
2. Upsert vào `trending_cells`, `_id = "<window_start>|<region>|<food_id>"`, `$set` các số đếm. Ghi lại cùng một batch cho ra cùng giá trị, nên **idempotent**.
3. Với mỗi cửa sổ bị chạm: đọc lại các ô của cửa sổ đó (index `window_start`), tính top 20 cho 4 phạm vi, `replaceOne(upsert)` vào `trending`, `_id = "<window_start>|<scope>"`.
4. Cập nhật `stream_status` (heartbeat, số liệu batch, độ trễ).
5. Lưu `last_batch_id`: batch có `batch_id` đã ghi thì bỏ qua (Spark chạy lại batch cuối khi khởi động lại từ checkpoint). Không có bước này kết quả vẫn đúng vì ghi giá trị tuyệt đối; bước này chỉ để khỏi ghi thừa và để số liệu đo không bị đếm 2 lần.

Ghi bằng `pymongo` (4.19.0, đã có trong `jupyter`, bước 07 đang dùng) thay vì Mongo Spark Connector: image chưa có jar của connector, và ở cỡ này gom về driver vẫn đủ, lại tính được top N sau khi gộp vùng.

**C2. Checkpoint** ở `hdfs:///stream/checkpoint/trending` (offset, commit, state). Dừng rồi chạy lại cùng checkpoint thì luồng đọc tiếp các file chưa xử lý, trạng thái cửa sổ còn nguyên. Đổi định nghĩa query (cửa sổ, watermark, chiều nhóm) thì phải xóa checkpoint (`reset`, mục D).

**C3. Cửa sổ đã chốt.** `StreamingQueryListener` (có trong PySpark 4) đọc `eventTime.watermark` của mỗi lần tiến độ và ghi vào `stream_status`. API tính `final = window_end <= watermark`, không cần ghi lại doc cũ.

**C4. Dọn dẹp.** Một ngày có 96 cửa sổ × 4 phạm vi = 384 doc `trending`, không cần TTL. `cleanSource=archive` chuyển file đã đọc sang `/stream/archive` để thư mục nguồn không phình (1 file mỗi giây). `reset` xóa hết.

### D. Chạy trên cụm, song song với `api`, bật/tắt khi demo
**D1. Ứng dụng `10_stream`** nộp lên `spark-master`, driver trong `jupyter`:
- `spark.cores.max 2` (1 executor 2 core), `executor.memory 1g`, `driver.memory 1g`, `shuffle.partitions 4` (8 hay 200 phân vùng làm mỗi batch nhỏ chậm đi), trigger 5 giây;
- còn 2 core cho việc khác (vd `07 --only ...`). Không đo hiệu năng (09) khi luồng đang chạy;
- `get_spark()` thêm tham số `conf` để ghi đè các giá trị trên, mặc định giữ nguyên như cũ.

**D2. Replayer** là tiến trình Python riêng trong `jupyter`, không giữ executor, khoảng vài chục MB RAM. Container `jupyter` có 4 GB: driver 1 GB + replayer vẫn còn chỗ, nhưng không chạy cùng lúc với job `--local` hay job batch khác có driver 2 GB.

**D3. `api`** không đổi kiến trúc, chỉ đọc MongoDB (`trending`, `stream_status`). E25 không dùng cache như các endpoint khác. Trang gọi lại mỗi 5 giây (hiện là 10 giây), dừng khi tab bị ẩn (đã có).

**D4. Bật/tắt:** `scripts/10_stream.sh start|stop|status|reset`, chạy từ máy (Git Bash hoặc PowerShell):
- `start [--day 2026-09-27] [--from 16:00] [--speed 60] [--late 1]`: `docker exec -d jupyter ...` cho driver và replayer, log ở `logs/stream/`;
- `stop`: tạo file `data/stream/STOP`. Replayer dừng ngay; driver gọi `query.stop()` sau batch đang chạy (dừng êm, checkpoint nhất quán) và ghi `stream_status.state = "đã dừng"`;
- `status`: in heartbeat, batch gần nhất, độ trễ, số sự kiện/giây;
- `reset`: xóa `/stream/{incoming,_staging,archive,checkpoint}`, `trending`, `trending_cells`, `stream_status`.
- Không có nút bật/tắt trên dashboard: muốn có thì container `api` phải có quyền điều khiển Docker, không nên.
- Kịch bản demo: `reset`, rồi `start --from 16:00 --speed 60`. Khoảng 1 phút sau có cửa sổ đầu tiên; 17h–19h (giờ nấu đông nhất) rơi vào phút thứ 1–3.

**D5. Trạng thái trên dashboard:** "đang chạy" khi heartbeat `stream_status.updated_at` mới hơn 30 giây; "đã dừng" khi có dữ liệu nhưng không còn heartbeat; "chưa chạy" khi trống. Bước 10 ở Tổng quan: "Xong" khi có `stream_report.json`, "Đang làm" khi có `trending`.

### E. Schema document, sửa E25 và trang Thời gian thực
**E1. `trending`**, 1 doc cho mỗi cửa sổ × phạm vi:
```
{
  _id: "2026-09-27T17:00|all",
  window_start: ISODate, window_end: ISODate,        // BSON datetime; API trả chuỗi giờ +07:00
  scope: "all" | "Bắc" | "Trung" | "Nam",
  meal_slot: "tối",                                  // bữa chiếm đa số trong cửa sổ
  total_cooks, total_views, total_favorites, n_dishes,
  items: [{ food_id, rank, cooks, views, favorites, prev_cooks }],   // top 20
  batch_id, updated_at,                              // giờ thật lúc ghi
  replay: { day: "2026-09-27", speed: 60 }
}
```
Index `{scope: 1, window_end: -1}`, thay index `window_end -1` mà 07 đang tạo (sửa 07 tương ứng).

**E2. `trending_cells`** (nội bộ, API không đọc): `{_id, window_start, region, food_id, cooks, views, favorites, last_emit}`, index `window_start`.

**E3. `stream_status`** (`_id: "current"`): `state`, `started_at`, `updated_at`, `batch_id`, `sim_now` (sự kiện mới nhất đã thấy), `watermark`, `replay {day, speed, from}`, `input_rows_per_s`, `processed_rows_per_s`, `batch_ms`, `dropped_by_watermark`, `duplicates_dropped`, `latency_s {p50, p95, max}` của 20 batch gần nhất.

**E4. E25 mới:** `GET /api/trending?scope=all&windows=16&limit=10`
```
{ status: "đang chạy" | "đã dừng" | "chưa chạy",
  stream: { sim_now, watermark, speed, day, input_rows_per_s, processed_rows_per_s, latency_s, dropped_by_watermark },
  scope, scopes: ["all", "Bắc", "Trung", "Nam"],
  windows: [{ window_start, window_end, meal_slot, total_cooks, final,
              items: [{ ...thẻ món, cooks, views, rank, delta }] }],
  rising: [{ ...thẻ món, cooks, prev_cooks, delta }] }       // 5 món tăng mạnh nhất so với cửa sổ trước
```
Khi trống vẫn trả `status: "chưa chạy"` như hiện nay.

**E5. Trang Thời gian thực** (theo skill `vifood-dashboard`):
- Hàng KPI: trạng thái luồng (viên), giờ mô phỏng, sự kiện/giây (xử lý), độ trễ sự kiện → MongoDB (p50 / p95), sự kiện trễ bị bỏ.
- "Lượt nấu theo cửa sổ": đường toàn quốc (đậm) và 3 vùng; cửa sổ chưa chốt đánh dấu bằng điểm rỗng.
- "Món thịnh hành": nhóm nút phân đoạn Toàn quốc / Bắc / Trung / Nam, lưới 10 thẻ món, dòng "N lượt nấu, tăng M so với 15 phút trước".
- "Tăng nhanh": danh sách 5 món.
- Chú thích: "Phát lại sự kiện mô phỏng ngày 27/09/2026, tốc độ 60 lần".

### F. Kiểm thử và đo
**F1. Đúng** (`src/10c_stream_check.py`, chạy sau khi phát xong một đoạn):
- `--late 0`: mọi cửa sổ đã chốt trong `trending` khớp **tuyệt đối** đáp án batch (tổng và top 20, cả 4 phạm vi).
- `--late 1`: sự kiện gửi lặp không làm tăng số; sự kiện trễ dưới 10 phút vẫn được tính; phần thiếu so với đáp án chỉ đến từ các sự kiện bị giữ quá watermark (đối chiếu danh sách replayer đã giữ > 10 phút với `numRowsDroppedByWatermark` của Spark).
- Khởi động lại: dừng driver giữa chừng (`stop` rồi `start`, và một lần `kill -9`), chạy tiếp cùng checkpoint, kết quả cuối vẫn khớp đáp án.
- pytest `api/tests/test_realtime.py`: dạng trả về khi trống và khi có dữ liệu; `items` giảm dần theo `cooks`; 3 vùng cộng lại bằng toàn quốc; E25 khớp collection; `final` khớp watermark.

**F2. Độ trễ:**
- **Sự kiện → MongoDB:** mỗi ô mang `last_emit = max(emit_ts)`. Ghi Mongo xong thì độ trễ = giờ hiện tại − `last_emit` của từng ô. Ghi p50 / p95 / max mỗi batch và cả lần chạy. Gồm: chờ trigger kế (≤ 5 giây), liệt kê file, xử lý, ghi Mongo.
- **Sự kiện → API:** `api/bench_stream.py` gọi E25 mỗi 0,5 giây, ghi lúc thấy `batch_id` mới.
- **API → dashboard:** cộng chu kỳ gọi lại của trang (≤ 5 giây, trung bình 2,5 giây); đo 1 lần trong trình duyệt (lúc DOM đổi).
- Mục tiêu đề xuất: p95 sự kiện → API ≤ 15 giây ở tốc độ 60.

**F3. Thông lượng:**
- Theo tốc độ phát 60, 300, 1.200: `inputRowsPerSecond`, `processedRowsPerSecond`, thời gian batch (listener ghi `logs/stream/progress.jsonl`). Bền vững khi thời gian batch dưới 5 giây và độ trễ không tăng dần.
- Tối đa: chép sẵn file của 7 ngày liền (ước tính khoảng 450 nghìn sự kiện) vào `incoming` rồi đọc dồn, đo `processedRowsPerSecond` với `cores.max` 2 và 4.
- `data/output/stream_report.json`: cấu hình, kết quả kiểm tra đúng, độ trễ, thông lượng theo tốc độ, sự kiện bị bỏ, số batch.

**F4. Ảnh chụp:** tab Structured Streaming của Spark UI (:4040), History Server, trang Thời gian thực ở 1440 và 390.

(Các điểm cần quyết định của bản thiết kế nằm ở mục "Cần người dùng quyết định", câu 2–11.)

## Lỗi / sự cố và cách xử lý
- **`perf_report.json` đầu tiên thiếu `speedup_by_scale`:** tiến trình `09_perf.py` khởi động lúc 07:58 đã nạp code trước khi `summarize()` được sửa. Chạy `python scripts/09_perf.py --summarize` lại thì có đủ.
- **Câu tóm tắt ban đầu viết "speedup tăng theo quy mô dữ liệu":** sai với số đo (0,88 → 1,59 → 1,36). Đã sửa thành "theo mức dữ liệu".
- **Biểu đồ (d):** vạch y = 2 trùng màu với đường lưới nên không thấy, nhãn bị cắt ở mép phải, trục y dừng ở 2,19, chú giải 4 mục xuống 2 dòng và đè nhãn trục ở 375px. Đã sửa (màu `--neutral`, nhãn trong vùng vẽ, làm tròn trục, tên series ngắn).
- **`DATA_DICTIONARY.md`:** dòng `perf` của bảng collection bị vỡ (dấu `|` trong mã không được thoát, phần đầu bị lặp). Đã viết lại.
- Lúc bắt đầu phiên cụm chạy đủ 11 container, master thấy 2 worker. Cuối phiên vẫn vậy; `api` đã restart.

## Cần người dùng quyết định
1. **04 ở 50% / 1 worker:** chạy lại riêng job này thêm 2 lần (khoảng 20 phút) để biết speedup 2,19 là nhiễu hay thật? Đề xuất: có, vì đây là điểm bất thường duy nhất trên biểu đồ (d) và dễ bị hỏi khi bảo vệ.

**Structured Streaming** (phương án "đề xuất" là mặc định nếu đồng ý cả gói):
2. **Nguồn:** phát lại Chủ nhật 27/09/2026 (đề xuất), hay sinh sự kiện mới liên tục?
3. **Đường vận chuyển:** file JSON Lines trên HDFS qua WebHDFS (đề xuất), hay thêm Kafka?
4. **Cửa sổ và watermark:** 60 phút trượt 15 phút, watermark 10 phút (đề xuất), hay cửa sổ cố định 15 / 30 phút?
5. **Chiều nhóm:** theo vùng, bữa chỉ là nhãn (đề xuất), hay chia thêm theo bữa hoặc nhóm tuổi?
6. **Tốc độ demo:** mặc định 60 lần, bắt đầu từ 16:00?
7. **Mô phỏng đến trễ và gửi lặp:** bật mặc định (3% trễ trong watermark, 0,3% quá watermark, 0,2% gửi lặp)?
8. **Ghi MongoDB:** `pymongo` trong `foreachBatch` (đề xuất), hay tải Mongo Spark Connector?
9. **Bật/tắt:** chỉ bằng `scripts/10_stream.sh` (đề xuất), hay cần nút trên dashboard?
10. **State store:** mặc định HDFS-backed (đề xuất), hay RocksDB (có sẵn trong Spark 4, đáng nêu trong báo cáo nhưng chưa cần ở cỡ này)?
11. **Tài nguyên:** `cores.max 2` (đề xuất, để lại 2 core), hay dùng cả 4 core?

**Khác:**
12. **Sửa 04 chạy phần sinh 2 lần** (cache trước `repartitionByRange`, hoặc `repartition(12, "month")`): sửa rồi đo lại 04 ở mọi cấu hình (khoảng 1 giờ), hay chỉ ghi vào báo cáo như một phát hiện tối ưu? Đề xuất: chỉ ghi vào báo cáo, không sửa, để số đo đã có vẫn so được.

Việc cần người làm (không đổi): kiểm tra tay 100 món; dựng notebook biểu đồ cho bước 05 và 06; xem thẻ Hiệu năng Spark (thêm biểu đồ (d)) trên trang Đánh giá.

## Commit
- `Buoc 09: do them 50% 1 worker, speedup theo muc du lieu; thiet ke streaming` (`scripts/09_perf.py`, `api/routers/evaluation.py`, `api/tests/test_overview.py`, `web/js/{charts,danh-gia}.js`, `web/css/theme.css`, `data/output/{perf_runs.jsonl,perf_report.json,perf/*_s050_w1_r1/,export_report.json}`, D17, DATA_DICTIONARY, PROGRESS, file này).
