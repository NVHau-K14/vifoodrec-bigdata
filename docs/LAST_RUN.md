# Lần chạy gần nhất – 26/10/2026 (chiều)

> File này được **ghi đè sau mỗi lần làm xong một yêu cầu** (xem quy tắc trong CLAUDE.md).
> Người dùng đọc nó ở bên chat claude.ai. Giữ đúng các mục bên dưới, không giới hạn độ dài.
> Dữ liệu hành vi là **mô phỏng**. Số liệu lấy từ `data/output/perf_report.json`, `stream_prep_report.json`, `stream_semantics_report.json`, `stream_report.json`, `export_report.json`.

## Yêu cầu
Trả lời 12 câu của LAST_RUN trước:
- câu 1: có, chạy lại 04 ở 50% / 1 worker thêm 2 lần;
- câu 2–11: theo đề xuất;
- câu 12: chỉ ghi vào báo cáo.

Ghi D18 cho Structured Streaming với 12 sửa đổi, rồi làm theo thứ tự trong PROGRESS:
1. Tick cho phút trống và tick cuối (giờ kết thúc + 75 phút); phép lọc đứng sau `withWatermark`.
2. Bài thử nhỏ: `dropDuplicatesWithinWatermark` có tự lọc dòng có ts < watermark không; đọc `numRowsDroppedByWatermark` theo từng stateOperator.
3. 10c chạy 3 kịch bản: s1 và s2 khớp tuyệt đối, s3 thỏa bất đẳng thức.
4. Đáp án chỉ tính ts ≥ `--from`.
5. `last_batch_id` lưu kèm `query.id`.
6. "Tăng nhanh" so [t−60, t) với [t−120, t−60).
7. Trigger là tham số; bài đo thông lượng dùng ít file lớn; đổi cấu hình thì phải reset checkpoint.
8. Độ trễ là của sự kiện mới nhất, kèm cận trên.
9. "1 giờ qua" là cửa sổ gần nhất có `window_end` ≤ `sim_now`; cửa sổ đang diễn ra gắn nhãn "đang cập nhật".
10. Thêm cổng 4041.
11. 10c in vài dòng state store.
12. Dùng `/data/stream`.

## Đã làm
**1. Chạy lại 04 ở 50% / 1 worker (câu 1):**
- `build_plan` thêm 2 lần, `perf_report.json` có `plan.repeats_50pct_1w`.
- Kết quả: 575,8 và 631,8 giây (lần 1 là 604,0). Trung vị vẫn 604,0, nên speedup 04 ở 50% vẫn là 2,19. **Không phải nhiễu.**
- 64/64 lần chạy OK. Thẻ Hiệu năng: chú thích biểu đồ (d) sửa theo. Chạy lại `07 --only perf`.

**2. D18** (`docs/DECISIONS.md`): thiết kế đã chốt, 12 sửa đổi và cách làm, kết quả bài thử, phần "Khi cài đặt và chạy", kết quả chính. D17 thêm kết quả 3 lần chạy 04 và câu 12.

**3. Code bước 10:**
- `src/stream_common.py` (dùng chung):
  - hằng số, schema;
  - `stream_query()`, `aggregate()`, `window_docs()`: luồng, đáp án batch và bài thử dùng cùng một hàm;
  - WebHDFS / thư mục local;
  - MongoDB, `reset`, `status`, `stop`;
  - `run_pair()`: chạy luồng và replayer thành tiến trình con.
- `src/10a_stream_prep.py`: lọc ngày, gán `event_id`, ghi `data/stream/replay_<ngày>.jsonl.gz` và `/data/stream/replay/<ngày>`, tính đáp án `/data/stream/truth/<ngày>_0600-2400`.
- `src/10b_replayer.py`:
  - đồng hồ mô phỏng, mỗi giây thật 1 file;
  - ghi WebHDFS vào `_staging` rồi RENAME sang `incoming`;
  - `--late 0|1|2`, tick cho phút trống, tick cuối;
  - `--speed max --chunk-min` để đo thông lượng;
  - ghi `replayer.json` (kèm danh sách sự kiện bị giữ) và `DONE`.
- `src/10_stream.py`:
  - query: `withWatermark` → `dropDuplicatesWithinWatermark` → lọc → join broadcast `users` → `window(60, 15)` → `update` → `foreachBatch`;
  - sink: `trending_cells` (số đếm tuyệt đối, upsert), `trending` (top 20 + "tăng nhanh", 4 phạm vi), `stream_status`;
  - `StreamingQueryListener` ghi watermark, ts lớn nhất, tốc độ, số dòng bị bỏ theo từng operator;
  - bỏ qua batch đã ghi theo cặp (`query.id`, `last_batch_id`);
  - kiểm tra cấu hình với `checkpoint_conf.json`;
  - query lỗi thì thoát mã 1; `--exit-when-done`.
- `common.get_spark()` có tham số `conf`. Luồng dùng `cores.max 2`, executor 1 GB, driver 1 GB, `shuffle.partitions 4`, Spark UI ở cổng 4041.
- `scripts/10_stream.sh start|stop|status|reset`. Compose thêm cổng `4041:4041` cho `jupyter`; đã `docker compose up -d jupyter`.
- `src/10t_stream_semantics.py` (bài thử), `src/10c_stream_check.py` (3 kịch bản + state store), `src/10d_stream_bench.py` (độ trễ, thông lượng; gộp `api/bench_stream.py` của bản thiết kế).

**4. API và trang:**
- E25 viết lại:
  - tham số `scope`, `limit`, `windows`;
  - trả về `status`, `stream`, `current` (có `final`, `items` với `prev_cooks` / `delta`, `rising`), `in_progress`, `series` theo 4 phạm vi;
  - `sim_now` không vượt mốc kết thúc của đoạn phát lại.
- E1: bước 10 "Xong" khi có `reports.stream_report`.
- 07 tạo index `trending {scope, window_end -1}` và `trending_cells {ws}`; đã chạy `07 --only perf,trending,reports` (reports 17 doc, perf 55 doc).
- Test mới `api/tests/test_realtime.py` (3 test); bỏ `test_trending` cũ trong `test_consistency.py`.
- Trang Thời gian thực:
  - 5 thẻ KPI: trạng thái, giờ mô phỏng, sự kiện/giây, độ trễ p50 / p95 / cận trên, sự kiện trễ bị bỏ;
  - biểu đồ lượt nấu theo cửa sổ: toàn quốc và 3 vùng;
  - thẻ "Luồng xử lý";
  - "Món thịnh hành trong 1 giờ qua" có nút phạm vi Toàn quốc / Bắc / Trung / Nam;
  - "Tăng nhanh", "Cửa sổ đang cập nhật" (luồng đã dừng thì ghi "chưa đủ 1 giờ");
  - gọi lại mỗi 5 giây khi luồng chạy, 15 giây khi chưa chạy hoặc đã dừng.
  
  Đã xem ở 1440px và 390px: không cuộn ngang, nút phạm vi chạy đúng (Miền Bắc 83 lượt nấu, khớp E25).

**5. Chạy:**
- 10t;
- 10a (CN 27/09 và 7 ngày 21–27/09);
- chạy thử ngắn 16:00–17:30;
- 10c (2 lần, xem "Lỗi");
- 10d (2 lần);
- cuối cùng phát lại cả ngày 06:00–24:00 ở tốc độ 300 để dashboard có dữ liệu (trạng thái "đã dừng").

**6. Tài liệu:** D17, D18, `DATA_DICTIONARY.md`:
- HDFS `/data/stream`, schema sự kiện luồng, 4 report mới;
- `trending`, `trending_cells`, `stream_status`, E1, E25;
- sửa dòng `perf_runs.jsonl` bị chèn nhầm.

`CLAUDE.md`: dòng bước 10, cách chạy, cổng 4041, 2 lỗi môi trường mới. `.gitignore`: `data/stream/`. PROGRESS.

## Số liệu chính
**Đoạn phát lại (10a):**
- CN 27/09/2026: 92.893 sự kiện (view 73.137, cook 11.402, favorite 4.771, rate 3.583), file 1,47 MB.
- Đáp án 06:00–24:00: 92.302 sự kiện, trong đó 88.969 được đếm; 205.920 ô, 70 cửa sổ.
- Cửa sổ đông nhất là 17:00–18:00: 1.455 lượt nấu, 8.221 lượt xem, 908 món được nấu.
- Đoạn 7 ngày: 488.741 sự kiện, 7,59 MB.
- HDFS `/data/stream`: 37,8 MB (75,6 MB tính cả bản sao).

**Bài thử 10t:**

| | Lọc ngay sau withWatermark | Lọc sau khử trùng (dùng) |
|---|---|---|
| Số dòng đọc ở F1 (7 nếu đọc cả tick) | 6 | 7 |
| Watermark sau F3 (chỉ có tick 11:30) | 10:15 (đứng yên) | 11:20 |
| Bỏ theo watermark: khử trùng / tổng hợp | 2 / 0 | 3 / 0 |
| Lượt nấu cửa sổ 10:00 (đúng là 7) | 8 (id 101 lọt vì watermark chậm) | 7 |

- Phép lọc `event_type` (không dùng `ts`) bị optimizer đẩy xuống dưới `EventTimeWatermark`, tới tận nguồn JSON, nên tick bị loại trước khi tính watermark.
- `dropDuplicatesWithinWatermark` tự bỏ dòng có ts < watermark; phép tổng hợp không còn gì để bỏ. Một sự kiện quá watermark bị bỏ hoàn toàn, kể cả khi vài cửa sổ trượt chứa nó vẫn còn mở (id 104).

**Kiểm tra 10c** (tốc độ 300, trigger 1 giây, 06:00–24:00; tổng 773 giây):

| Kịch bản | Ô lệch / doc lệch (trên 205.920 ô, 280 doc) | Trễ ≤ 8 phút | Gửi lặp | Bị giữ 20–40 phút | Bỏ theo watermark (khử trùng / tổng hợp) | Kết quả |
|---|---|---|---|---|---|---|
| s1 `--late 0` | 0 / 0 | 0 | 0 | 0 | 0 / 0 | **Khớp tuyệt đối** |
| s2 `--late 1` | 0 / 0 | 2.757 | 180 | 0 | 0 / 0 | **Khớp tuyệt đối** |
| s3 `--late 2` | 957 / 254, không ô nào vượt đáp án | 2.795 | 173 | 264 (249 thuộc cook/view/favorite) | 255 / 0 | **Đạt bất đẳng thức**: thiếu 960 ≤ 996 lượt cửa sổ của 249 sự kiện bị giữ |

- Ở s3 không phải sự kiện bị giữ nào cũng bị bỏ, vì watermark của batch tính từ batch trước.
  - Khoảng nhận sự kiện trễ của mỗi batch (ts lớn nhất − watermark) có trung vị 15 phút.
  - 11 batch có khoảng ≥ 20 phút (batch chạy quá 1 giây, gom 2 file).
  - 7 sự kiện bị giữ được phát sau 24:00, khi đã hết tick nên watermark đứng yên.
- State store đọc ở batch 180 (`data/output/stream/statestore_sample.txt`):
  - phép tổng hợp 7.130 dòng (key = cửa sổ, vùng, món; value = 7 số đếm + `emit_ts` lớn nhất);
  - phép khử trùng 1.544 dòng (key = `event_id`; value = mốc hết hạn).

**Độ trễ (10d)** = sự kiện mới nhất trong batch (lúc ghi MongoDB xong − `emit_ts`). Cận trên = độ trễ đó + trigger + 1 giây.

| Lần đo | Sự kiện → MongoDB p50 / p95 / max | Cận trên p95 | Sự kiện → API p50 / p95 | Thời gian batch p50 | Batch vượt trigger | Xử lý / giây p50 |
|---|---|---|---|---|---|---|
| Tốc độ 60, trigger 5 giây (16–19h) | 2,25 / 2,53 / 6,34 giây | 8,53 giây | 2,52 / 2,85 giây | 1,28 giây | 1/38 | 660 |
| Tốc độ 300, trigger 1 giây (16–21h) | 2,21 / 3,32 / 5,62 giây | 5,32 giây | 3,00 / 3,89 giây | 1,82 giây | 31/33 | 854 |
| Tốc độ 1.200, trigger 1 giây (cả ngày) | 3,31 / 8,39 / 11,84 giây | 10,39 giây | 3,87 / 8,75 giây | 2,59 giây | 17/17 | 1.162 |

- Mục tiêu p95 sự kiện → API ≤ 15 giây ở tốc độ 60: **đạt** (2,85 giây). Trang gọi lại mỗi 5 giây, nên từ API lên dashboard cộng thêm tối đa 5 giây.
- Ở tốc độ 300 và 1.200, batch chạy lâu hơn trigger 1 giây nên Spark gom nhiều file mỗi batch; độ trễ vẫn ổn định ở 300 và tăng ở 1.200.

**Thông lượng** (7 ngày, 490.570 dòng, 15 file ghi sẵn, 2 file mỗi trigger):

| Core | Dòng / giây (cả lần chạy) | Xử lý / giây p50 | Tổng thời gian batch | Spark (collect) | Ghi MongoDB | Ô đã ghi |
|---|---|---|---|---|---|---|
| 2 | 4.654 | 4.197 | 105,3 giây | 30,0 giây | 66,4 giây | 1.159.191 |
| 4 | 4.543 | 4.294 | 107,9 giây | 29,0 giây | 70,0 giây | 1.159.191 |

Thêm core không nhanh hơn vì nút thắt là sink chạy một luồng trên driver: ghi MongoDB chiếm 63%. Phần Spark tính và gom về driver đạt khoảng 16.000 sự kiện/giây.

**pytest:** `vifood` 64/64 đạt; `vifood_local` 61 đạt, 3 bỏ qua.

## Lỗi / sự cố và cách xử lý
- **Đặt phép lọc ngay sau `withWatermark` làm tick vô dụng** (bài thử 10t). Đổi thứ tự: lọc sau khử trùng. Ghi trong D18 và "Khác với kế hoạch".
- **10c lần 1 lỗi ở bước đọc state store** (`CANNOT_LOAD_STATE_STORE`; nguyên nhân gốc `Cannot find endpoint: StateStoreCoordinator`). Phiên Spark của 10c chưa từng chạy query luồng nên driver chưa có coordinator. Sửa: gọi `spark.streams.active` trước khi đọc. 10c cũng ghi report trước bước này. Đã chạy lại cả 3 kịch bản (kết quả như lần 1: s1, s2 khớp tuyệt đối).
- **D18 ban đầu viết phần thiếu ở s3 "bằng đúng" số sự kiện bị giữ × số cửa sổ:** sai với số đo (960 < 996). Đã sửa, kèm giải thích về watermark theo batch.
- **10d lần 1 lỗi ở bài đo thông lượng:** `maxBytesPerTrigger` phải là số byte nguyên và không đặt cùng `maxFilesPerTrigger` được. Query lỗi nhưng `10_stream.py` vẫn thoát mã 0, và 10d chỉ ghi report ở cuối nên mất cả 3 lần đo độ trễ. Đã sửa cả ba (thoát mã 1, ghi report sau mỗi lần), rồi chạy lại toàn bộ 10d.
- **Chạy thử ngắn trên cụm:**
  - "1 giờ qua" lấy nhầm cửa sổ chỉ có 15 phút dữ liệu, vì tick cuối đẩy `sim_now` tới 18:45. Đã chặn ở mốc kết thúc.
  - `newest_emit` bị batch rỗng ghi đè thành rỗng. Thêm `data_batch_id`.
  - KPI tốc độ sau khi dừng hiện số của batch chỉ có tick cuối. Trang hiện "–" khi đã dừng; listener chỉ cập nhật tốc độ từ batch có dữ liệu.
- **Trang chỉ gọi lại API khi luồng đang chạy,** nên mở trang trước khi bật luồng thì không bao giờ tự cập nhật. Đã sửa (15 giây khi chưa chạy).
- **`test_no_cdn` bắt link `http://localhost:4041`.** Link Spark UI giờ dựng lúc chạy từ hostname của trang.
- **`docker compose up -d jupyter`** khởi động lại cả `spark-master` và `mongodb`. Dữ liệu còn nguyên, worker đăng ký lại sau khoảng 10 giây (đã ghi vào CLAUDE.md).
- **Heredoc của Bash tool làm hỏng dấu `\` trong chuỗi Python** nên vài lần sửa file bằng script trượt (`assert`). Chuyển sang Edit hoặc script ghi ra file (đã ghi vào CLAUDE.md).
- Đầu phiên cụm đủ 11 container, master thấy 2 worker. Cuối phiên vẫn vậy; luồng đã dừng, không còn ứng dụng nào giữ executor.

## Cần người dùng quyết định
1. **Đo lại 04 ở 100% / 1 worker thêm 2 lần** (khoảng 30 phút)? Ở 50%, 3 lần đều chậm (21,5–23,8 ms/user), nên điểm khác thường có thể là lần duy nhất ở 100% / 1 worker (15,6 ms/user, thấp nhất trong mọi cấu hình). Đề xuất: có, vì speedup 04 (2,19 ở 50% so với 1,64 ở 100%) sẽ được nêu trong báo cáo.
2. **Nút thắt thông lượng của luồng là ghi MongoDB trên driver:** tối ưu (ghi song song từ executor bằng `foreachPartition` như bước 07, hoặc chỉ ghi ô có `cooks` > 0) rồi đo lại, hay chỉ ghi vào báo cáo như một phân tích nút thắt? Đề xuất: chỉ ghi vào báo cáo; ở tốc độ demo (60), mỗi batch chỉ mất khoảng 1,3 giây trên trigger 5 giây.
3. **Dữ liệu streaming đang có trong MongoDB `vifood`** (lượt phát lại cả ngày ở tốc độ 300, trạng thái "đã dừng"): giữ để trang Thời gian thực có số khi mở, hay `reset` cho trang về "chưa chạy"? Đề xuất: giữ; demo thì `reset` rồi `start --from 16:00 --speed 60`.
4. **Bước tiếp theo:** báo cáo Word + slide, hay còn phần nào của code cần làm thêm trước?

Việc cần người làm (không đổi): kiểm tra tay 100 món; dựng notebook biểu đồ cho bước 05 và 06; xem trang Thời gian thực (nên xem lúc luồng đang chạy: `bash scripts/10_stream.sh reset`, rồi `bash scripts/10_stream.sh start --from 16:00 --speed 60`).

## Commit
- `Buoc 10: Structured Streaming (D18), do lai 04 50% 1 worker`: `src/{stream_common,10a_stream_prep,10b_replayer,10_stream,10c_stream_check,10d_stream_bench,10t_stream_semantics}.py`, `src/common.py`, `src/07_export_mongo.py`, `scripts/{10_stream.sh,09_perf.py}`, `docker/docker-compose.yml`, `api/routers/{realtime,overview}.py`, `api/tests/{test_realtime,test_consistency}.py`, `web/{thoi-gian-thuc.html,js/thoi-gian-thuc.js,js/danh-gia.js,css/theme.css}`, `data/output/{stream_*report.json,stream/,perf_*,perf/04_s050_w1_r*/,export_report.json}`, `.gitignore`, `CLAUDE.md`, D17, D18, DATA_DICTIONARY, PROGRESS, file này.
