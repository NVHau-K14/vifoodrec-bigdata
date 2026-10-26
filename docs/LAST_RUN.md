# Lần chạy gần nhất – 26/10/2026 (tối)

> File này được **ghi đè sau mỗi lần làm xong một yêu cầu** (xem quy tắc trong CLAUDE.md).
> Người dùng đọc nó ở bên chat claude.ai. Giữ đúng các mục bên dưới, không giới hạn độ dài.
> Dữ liệu hành vi là **mô phỏng**. Số liệu lấy từ `data/output/perf_report.json`, `perf_runs.jsonl`, `stream_report.json`,
> `screenshots.json`, `data/sample/README.md` và các lần chạy ghi trong `data/stream/runs/`.

## Yêu cầu
Trả lời 4 câu của LAST_RUN trước:
1. Có: đo lại 04 ở 100% / 1 worker thêm 2 lần, cập nhật `perf_report`, `speedup_by_scale`, thẻ Hiệu năng, `07 --only perf`.
2. Chỉ ghi vào báo cáo, nhưng trong `10_stream.py` bấm giờ riêng (a) upsert `trending_cells` và (b) đọc lại ô + top 20 + ghi `trending`; chạy lại riêng bài đo thông lượng của 10d (2 và 4 core), ghi tỷ lệ (a)/(b) vào `stream_report` và D18.
3. Giữ dữ liệu streaming trong `vifood`.
4. Báo cáo Word và slide để sau. Làm xong phần dữ liệu và code theo thứ tự:
   - a. kiểm tra replayer (tick cuối sau mọi sự kiện bị giữ); D18 ghi rõ "lọc sau khử trùng" dựa vào optimizer Spark 4.2.0, 10t là test hồi quy; đánh giá luồng: 300 bền vững, 1.200 chạm trần;
   - b. notebook biểu đồ 05, 06, thêm 09 và 10, PNG `docs/images/nb_*`;
   - c. đọc lại `01_ingest.sh`, chạy thử vào thư mục HDFS tạm rồi xóa;
   - d. xóa `hdfs:///tmp/checkpoint`, giữ `/perf`;
   - e. đóng gói: README, requirements, `data/sample/`, `.env.example`, bỏ `.env` khỏi Git;
   - f. trang Thời gian thực: cả đoạn phát lại khi dừng, "Cửa sổ chưa đủ 1 giờ dữ liệu", ngày phát lại ở đầu trang, "24:00 · 27/09/2026 (hết đoạn phát lại)";
   - g. đợt ảnh cuối bằng Playwright.

Ghi chú: yêu cầu nói "đọc README_DOAN trong Project". Thư mục dự án không có file nào tên như vậy (có thể là file trong Project bên claude.ai, phía này không đọc được). Phiên này làm theo `docs/PROGRESS.md`, `docs/LAST_RUN.md` và 4 câu trả lời ở trên.

## Đã làm
**1. Đo lại 04 ở 100% / 1 worker (câu 1)**
- `scripts/09_perf.py`: `build_plan` thêm `add("s100", 1, ["04"], rep)` cho rep 2 và 3; report ghi `plan.repeats_100pct_1w = {"04": 3}`. Chạy `09_perf.py --only s100:w1:04`: 2/2 OK, tổng 66 lần chạy, 0 lỗi.
- `07 --only perf`: collection `perf` 55 doc.
- Thẻ "Hiệu năng Spark" (`web/js/danh-gia.js`): chú thích "trung vị nhiều lần" giờ suy từ `rows` (`n_runs`), không ghi cứng. Nhãn vạch "lý tưởng 2,00" ở biểu đồ speedup từng job chuyển lên đầu vạch (trước đó đè lên nhãn trục 2,00; sửa trong `charts.js`).
- D17 thêm mục kết quả.

**2. Tách thời gian sink của luồng (câu 2)**
- `src/10_stream.py`: mỗi batch ghi thêm `cells_ms` (a: upsert `trending_cells`) và `trending_ms` (b: đọc lại ô, top 20 + "tăng nhanh", ghi `trending`); `mongo_ms` = (a) + (b) như cũ.
- `src/10d_stream_bench.py`: `sink_breakdown_s` thêm `mongo_cells_upsert`, `mongo_trending`, `ratio_cells_to_trending`, `share_cells_of_mongo`.
- Chạy `10d --only thr_c2,thr_c4`. Các khóa độ trễ (`lat60`, `lat300`, `lat1200`) giữ nguyên từ lần đo sáng.
- D18 thêm bảng kết quả.

**3. Kiểm tra replayer, D18 (mục a)**
- **Tick cuối đã phát sau mọi sự kiện bị giữ, không cần sửa.** `10b_replayer.py` chỉ ghi tick cuối sau khi vòng phát đã đẩy hết `items`, mà `items` gồm cả sự kiện bị giữ.
- Kiểm chứng trên lần chạy s3 (`check_s3_1026_055228`): 7 sự kiện bị giữ phát sau 24:00 nằm ở batch 203–208; tick cuối (ts 01:15) là batch 209, batch có dữ liệu cuối cùng. **Không chạy lại s3.**
- D18 thêm:
  - kết quả kiểm tra trên;
  - "lọc sau khử trùng" dựa vào hành vi của optimizer Spark 4.2.0, không phải bảo đảm của API; 10t là bài thử hồi quy, đổi phiên bản Spark thì chạy lại;
  - đánh giá luồng: tốc độ 60 và 300 bền vững, 1.200 chạm trần (số liệu ở mục "Số liệu chính").

**4. Notebook biểu đồ (mục b)**
- `notebooks/nb_style.py`: kiểu chung (màu theo token dashboard, nhãn số kiểu Việt Nam, dòng "Dữ liệu hành vi là mô phỏng" dưới mỗi ảnh). Không ghi tên thành viên.
- `notebooks/05_hanh_vi.ipynb` (từ `data/output/analysis/*.json`): 10 PNG.
- `notebooks/06_mo_hinh.ipynb` (từ `models_metrics.json`, `model_*_report.json`): 9 PNG, gồm bảng so sánh mô hình dạng ảnh, khoảng tin cậy, lưới ALS, RMSE đối chứng, Silhouette / ARI / NMI theo k, recall LSH, món mới + FP-Growth.
- `notebooks/09_10_hieu_nang_luong.ipynb` (từ `perf_report.json`, `stream_*report.json`): 7 PNG.
- Notebook không chạy Spark; chạy lại bằng `nbconvert --execute` trong container `jupyter` (lệnh trong CLAUDE.md). Đã xem từng ảnh và sửa chỗ nhãn đè nhau.

**5. Bước 01 và HDFS (mục c, d)**
- `scripts/01_ingest.sh` thêm biến `INGEST_DST` (mặc định `/data/raw`) để chạy thử vào thư mục khác.
- Chạy thử vào `/tmp/ingest_test`:
  - nạp đủ 4 file, 19,0 MB (38,0 MB tính cả bản sao), replication 2;
  - md5 của cả 4 file khớp giữa `/tmp/ingest_test`, `/data/raw` và `data/raw/` trên máy;
  - chạy lại thì bỏ qua cả 4 file; `--force` thì ghi đè cả 4 file.
- Đã xóa `/tmp/ingest_test` và `/tmp/checkpoint` (52,7 MB). `/tmp` trên HDFS giờ trống. `/perf` giữ nguyên (1,3 GB; 2,5 GB tính cả bản sao).
- Lưu ý: `rec_common` vẫn đặt checkpoint ALS ở `/tmp/checkpoint`, chạy lại 06 thì Spark tạo lại thư mục này.

**6. Đóng gói (mục e)**
- `README.md`:
  - giới thiệu, cấu trúc thư mục;
  - dựng cụm, bảng 11 container và cổng;
  - lệnh chạy 01 → 10 kèm thời gian đo được (`perf_report`, `model_*_report`);
  - demo Structured Streaming, nguồn dữ liệu.
- `requirements.txt`: phiên bản đang chạy trong container (pyspark 4.2.0, pandas 2.3.3, …, fastapi 0.162.0).
- `scripts/make_sample.py` (chạy trên cụm) → `data/sample/`: 11 file CSV, `README.md` (nguồn, cách chọn, số dòng), `columns.json`. Cách chọn cố định nên chạy lại ra cùng kết quả.
- `.env.example` với chỗ điền mật khẩu. `git rm --cached .env`, thêm `.env` vào `.gitignore` (file trên máy giữ nguyên).
- `DATA_DICTIONARY.md` thêm mục `data/sample/`, notebook, các khóa mới; `CLAUDE.md` thêm phần đóng gói và 3 lỗi môi trường.

**7. Trang Thời gian thực (mục f)**
- E25 (`api/routers/realtime.py`):
  - luồng đã dừng thì `series` trả cả đoạn phát lại (bỏ giới hạn `windows`);
  - `series` là lưới 15 phút liên tục; cửa sổ không có doc trong `trending` ghi 0. Trước đó 14:45 → 16:15 bị nối thẳng, vì 5 cửa sổ kết thúc 15:00–16:00 không có sự kiện nào được đếm;
  - `stream` thêm `replay_end` (mốc kết thúc đoạn phát lại) và `at_end`.
- `web/js/thoi-gian-thuc.js`:
  - tiêu đề "Cửa sổ chưa đủ 1 giờ dữ liệu" khi luồng đã dừng;
  - mốc 00:00 của ngày sau ghi là 24:00 (trục biểu đồ, cửa sổ hiện tại, danh sách cửa sổ);
  - KPI giờ mô phỏng ở mốc kết thúc: "24:00", dòng phụ "27/09/2026 (hết đoạn phát lại) · tốc độ 300 lần".
- Viên đầu trang: `layout.js` không lấy mốc dữ liệu khi `head-pills` có `data-pill="replay"`; trang tự ghi "Ngày phát lại: 27/09/2026".
- pytest: `vifood` 64/64 đạt; `vifood_local` 61 đạt, 3 bỏ qua.

**8. Đợt ảnh cuối (mục g)**
- `scripts/capture_screens.py` (Playwright Chromium headless, chạy trên máy):
  - các nhóm: `dashboard`, `perfcard`, `history`, `hdfs`, `mongo`, `realtime`, `sparkui`, `stopped`, `live05`;
  - trước khi lưu, kiểm tra văn bản của trang không chứa mật khẩu trong `.env`. 0 ảnh bị bỏ;
  - danh sách ảnh ghi vào `data/output/screenshots.json`.
- Thứ tự chạy:
  1. ảnh tĩnh;
  2. `10_stream.sh reset`, rồi `start --from 16:00 --speed 60`; chụp trang ở 18:03 (1440) và 18:28 (390) giờ mô phỏng, cùng Spark UI :4041;
  3. dừng, `reset`, phát lại cả ngày 06:00–24:00 ở tốc độ 300 (214 batch, watermark cuối 01:05); dừng rồi chụp trạng thái "Đã dừng" và mongo-express.
- Cài thêm trên máy: `playwright` (pip) và Chromium của Playwright.

## Số liệu chính
**04 ở 100% / 1 worker (D17)**

| Lần | Thời gian (History Server) | Thời gian task giai đoạn sinh / user | Ghi chú |
|---|---|---|---|
| r1 (25/10) | 864,4 giây | 31,9 ms | |
| r2 (26/10 14:05) | 1.230,1 giây | 45,6 ms | chạy trùng lúc tôi chạy notebook bằng nbconvert trong container `jupyter` và lệnh HDFS (chạy thử 01, so md5) |
| r3 (26/10 14:27) | 900,4 giây | 33,3 ms | máy không làm gì khác |

- Trung vị 900,4 giây; r2 là lần chậm nhất nên không làm lệch trung vị.
- Ở 50% / 1 worker, thời gian task giai đoạn sinh mỗi user là 43,4 / 41,1 / 44,9 ms. Vậy **50% / 1 worker chậm hơn thật trên mỗi user**, còn r1 ở 100% không phải lần may mắn.
- `speedup_by_scale` sau khi đo lại:

| | 10% | 50% | 100% |
|---|---|---|---|
| Chuỗi 04 → 06f | 0,88 | 1,59 | **1,38** (trước 1,36; 2.345,2 so với 1.702,9 giây) |
| 04 Sinh hành vi | 1,03 | 2,19 | **1,71** (trước 1,64) |
| 05 Phân tích | 0,77 | 1,22 | 1,21 |
| 06b ALS + baseline | 1,01 | 1,56 | 1,32 |

**Thông lượng luồng, đo lại** (7 ngày 21–27/09, 490.570 dòng, 15 file, 2 file mỗi trigger)

| Core | Dòng/giây (cả lần chạy) | Xử lý/giây p50 | Tổng thời gian batch | collect | (a) upsert ô | (b) top 20 + `trending` | (a)/(b) | (a) / phần ghi MongoDB |
|---|---|---|---|---|---|---|---|---|
| 2 | 6.645 | 6.582 | 73,8 giây | 20,5 giây | 36,6 giây | 10,6 giây | **3,45** | 77,5% |
| 4 | 7.394 | 7.672 | 66,3 giây | 16,5 giây | 34,9 giây | 9,6 giây | **3,64** | 78,5% |

- Ghi MongoDB vẫn là phần lớn nhất (64% và 67% thời gian batch); trong đó upsert 1.159.191 ô gấp khoảng 3,5 lần phần top 20.
- Lần đo sáng ra 4.654 / 4.543 dòng/giây, ghi MongoDB 66,4 / 70,0 giây. Code tính không đổi, khác biệt nằm ở phần ghi MongoDB, nên số tuyệt đối dao động theo tải của máy. Kết luận về nút thắt không đổi. Lần này 4 core nhanh hơn 11% (collect 20,5 → 16,5 giây).

**Đánh giá luồng theo tốc độ** (lần đo 10d sáng 26/10; chia các batch có dữ liệu làm 3 phần đều)

| Tốc độ | Trung vị độ trễ sự kiện → MongoDB (đầu / giữa / cuối) | Batch vượt trigger | Xử lý/giây | Kết luận |
|---|---|---|---|---|
| 60 (trigger 5 giây) | 2,30 / 2,12 / 2,21 giây | 1/38 | p50 660 | bền vững |
| 300 (trigger 1 giây) | 2,36 / 2,38 / 1,95 giây | 31/33 | p50 854, ngang tốc độ đến | **bền vững**: độ trễ không tăng dần |
| 1.200 (trigger 1 giây) | 7,51 / 3,34 / 2,93 giây | 17/17 | p95 3.442, max 3.500; đến tới 4.704 | **chạm trần**: batch p50 2,59 giây, max 11,23 giây; độ trễ p95 8,39 giây |

**Phát lại cả ngày để giữ trong `vifood` (câu 3):** 06:00–24:00, tốc độ 300, `--late 1`.
- 214 batch đã ghi, watermark cuối 01:05 (28/09).
- Bỏ theo watermark: 0 / 0 (khử trùng / tổng hợp).
- Biểu đồ của trang có 72 cửa sổ (06:15 → 24:00).

**`data/sample/`**

| File | Số dòng | Số cột |
|---|---|---|
| `users.csv`, `users_truth.csv` | 299 | 6, 7 |
| `events.csv` | 500 | 8 |
| `foods.csv`, `dish_features.csv` | 306 | 23, 16 |
| `ratings_original.csv`, `recs_final.csv` | 300 | 3, 8 |
| `raw_*.csv` (4 file) | 300 mỗi file | 15 / 18 / 16 / 3 |

**Danh sách ảnh giao diện** (`docs/images/`, PNG, tỷ lệ điểm ảnh 1; 32 ảnh)

| File | Nội dung | Kích thước (px) | KB |
|---|---|---|---|
| `08_tong-quan_1440.png` | Dashboard, trang Tổng quan, rộng 1440 (toàn trang) | 1440 × 2386 | 374 |
| `08_tong-quan_390.png` | Trang Tổng quan, rộng 390 | 390 × 4777 | 359 |
| `08_hanh-vi_1440.png` | Trang Hành vi ăn uống, 1440 | 1440 × 3730 | 508 |
| `08_hanh-vi_390.png` | Trang Hành vi ăn uống, 390 | 390 × 6420 | 449 |
| `08_mon-an_1440.png` | Trang Món ăn, 1440 | 1440 × 2887 | 671 |
| `08_mon-an_390.png` | Trang Món ăn, 390 | 390 × 8009 | 494 |
| `08_phan-khuc_1440.png` | Trang Phân khúc người dùng, 1440 | 1440 × 2638 | 473 |
| `08_phan-khuc_390.png` | Trang Phân khúc người dùng, 390 | 390 × 5976 | 473 |
| `08_goi-y_1440.png` | Trang Gợi ý món, 1440 | 1440 × 1805 | 541 |
| `08_goi-y_390.png` | Trang Gợi ý món, 390 | 390 × 5810 | 757 |
| `08_danh-gia_1440.png` | Trang Đánh giá mô hình, 1440 | 1440 × 3874 | 550 |
| `08_danh-gia_390.png` | Trang Đánh giá mô hình, 390 | 390 × 6883 | 514 |
| `08_thoi-gian-thuc_1440.png` | Trang Thời gian thực khi **luồng đang chạy**, giờ mô phỏng 18:03, tốc độ 60 | 1440 × 2091 | 735 |
| `08_thoi-gian-thuc_390.png` | Như trên, rộng 390, giờ mô phỏng 18:28 | 390 × 6249 | 942 |
| `10_thoi-gian-thuc_da-dung_1440.png` | Trang Thời gian thực khi **đã dừng** sau khi phát lại cả ngày: "24:00", "Cửa sổ chưa đủ 1 giờ dữ liệu", biểu đồ 06:15–24:00 | 1440 × 2135 | 451 |
| `09_the_hieu_nang.png` | Thẻ "Hiệu năng Spark" ở trang Đánh giá (riêng một ảnh) | 1128 × 1065 | 166 |
| `10_spark_ui_streaming.png` | Spark UI :4041, tab Structured Streaming, query đang chạy | 1440 × 1000 | 47 |
| `10_spark_ui_streaming_stats.png` | Spark UI :4041, thống kê query (tốc độ vào / xử lý, thời gian batch, state) | 1440 × 2320 | 149 |
| `hs_danh_sach_app.png` | History Server :18080, danh sách ứng dụng | 1440 × 1000 | 123 |
| `hs_06b_s100_w1_timeline.png` | History Server, `06b_als\|s100\|w1\|r1`: Jobs + Event Timeline | 1440 × 6925 | 752 |
| `hs_06b_s100_w1_executors.png` | Như trên, tab Executors | 1440 × 1000 | 63 |
| `hs_06b_s100_w2_timeline.png` | History Server, `06b_als\|s100\|w2\|r1`: Jobs + Event Timeline | 1440 × 5414 | 701 |
| `hs_06b_s100_w2_executors.png` | Như trên, tab Executors | 1440 × 1000 | 67 |
| `hs_05_sql.png` | History Server, 05 (`05_analysis\|s100\|w2\|r1`), tab SQL / DataFrame | 1440 × 1000 | 108 |
| `hs_05_storage.png` | Tab Storage của 05 **lúc đang chạy** (:4040, gốc đo `/perf/s100`): bảng cơ sở 237,1 MiB, `dish_features` 227,1 KiB, bảng tổng hợp 10,7 MiB, đều cache 100% | 1440 × 1000 | 140 |
| `hdfs_curated.png` | HDFS UI :9870, `/data/curated` | 1440 × 1000 | 33 |
| `hdfs_events.png` | HDFS UI, `/data/events` | 1440 × 1000 | 36 |
| `hdfs_results_analysis.png` | HDFS UI, `/data/results/analysis` | 1440 × 1000 | 75 |
| `hdfs_stream.png` | HDFS UI, `/data/stream` | 1440 × 1000 | 49 |
| `mongo_vifood.png` | mongo-express :8090, database `vifood` (29 collection kể cả hệ thống, thống kê) | 1440 × 2557 | 371 |
| `mongo_recs.png` | mongo-express, collection `recs` | 1440 × 1000 | 59 |
| `mongo_trending.png` | mongo-express, collection `trending` (280 doc của lượt phát lại cả ngày) | 1440 × 1000 | 75 |

Không ảnh nào có mật khẩu hay tên thành viên. Spark UI hiện tên người dùng `jovyan` của container.

**Danh sách biểu đồ notebook** (`docs/images/nb_*.png`, 150 dpi; 26 ảnh)

| File | Nội dung | Kích thước (px) |
|---|---|---|
| `nb_05_pheu.png` | Phễu cặp user–món + tỷ lệ nấu/xem theo nhóm món | 1803 × 648 |
| `nb_05_heatmap_gio_thu.png` | Lượt nấu theo giờ × thứ (đỉnh CN 17h) | 1798 × 558 |
| `nb_05_theo_thang.png` | Lượt nấu theo tháng (train / Tết / val-test) + tỷ trọng món Tết | 1804 × 588 |
| `nb_05_duoi_dai.png` | Đường cong đuôi dài lượt nấu / xem (Gini 0,698) | 1135 × 708 |
| `nb_05_lift_vung.png`, `nb_05_lift_tuoi.png`, `nb_05_lift_bua.png` | Lift nhóm món theo vùng / tuổi / bữa | 1656 × 501–560 |
| `nb_05_mam_com.png` | Số món mỗi phiên nấu theo bữa | 1358 × 529 |
| `nb_05_nau_lai_diem_hoat_dong.png` | Nấu lại theo nhóm món, phân bố điểm, mức hoạt động user | 2250 × 618 |
| `nb_05_nguyen_lieu_danh_muc.png` | 15 nguyên liệu chính, danh mục so với lượt nấu | 1953 × 738 |
| `nb_06_ndcg_mo_hinh.png` | NDCG@10 của 9 mô hình (test) | 1359 × 678 |
| `nb_06_bang_so_sanh.png` | Bảng so sánh mô hình (P/R/NDCG/MAP@10, coverage, novelty, diversity, NDCG khám phá) | 1780 × 537 |
| `nb_06_ndcg_nhom_user.png` | NDCG@10 theo nhóm ấm / ít / lạnh | 1507 × 620 |
| `nb_06_khoang_tin_cay.png` | Khoảng tin cậy 95% của hiệu NDCG@10 | 1970 × 571 |
| `nb_06_luoi_als.png` | Lưới ALS implicit (alpha, rank) và explicit (rank × regParam) | 2250 × 618 |
| `nb_06_rmse_doi_chung.png` | RMSE: mô phỏng so với ratings gốc (06g) | 1359 × 588 |
| `nb_06_kmeans_theo_k.png` | Silhouette, ARI, NMI theo k (KMeans, BisectingKMeans) | 2250 × 589 |
| `nb_06_lsh_recall.png` | MinHashLSH: recall@20 và thời gian theo số bảng băm | 1656 × 560 |
| `nb_06_mon_moi_fpgrowth.png` | Recall món mới (cold item), hit rate@3 món ăn kèm | 1953 × 588 |
| `nb_09_speedup_theo_muc.png` | Speedup 2/1 worker theo mức dữ liệu (chuỗi, 04, 05, 06b) | 1656 × 650 |
| `nb_09_thoi_gian_chuoi.png` | Thời gian chuỗi 04 → 06f theo mức × số worker | 1359 × 588 |
| `nb_09_mo_rong_du_lieu.png` | Tỷ lệ thời gian so với mức 10% (2 worker) | 1210 × 680 |
| `nb_09_lap_lai_04.png` | 04: ms/user từng lần chạy, đánh dấu r2 | 1352 × 618 |
| `nb_10_cua_so_dap_an.png` | Lượt nấu theo cửa sổ 1 giờ, CN 27/09 (đáp án batch) | 1656 × 558 |
| `nb_10_do_tre.png` | Độ trễ luồng theo tốc độ 60 / 300 / 1.200 | 1507 × 618 |
| `nb_10_thong_luong.png` | Thông lượng: thời gian batch theo phần việc (collect, (a), (b), còn lại) | 1656 × 454 |

## Lỗi / sự cố và cách xử lý
- **Lần 04 / 100% / 1 worker r2 bị ảnh hưởng bởi việc chạy song song.** Lỗi của tôi: trong lúc r2 chạy, tôi chạy notebook (nbconvert trong `jupyter`) và lệnh HDFS. Kết quả r2 chậm hơn r3 37%. Lần r3 để máy yên và khớp r1. Đã ghi rõ trong D17, biểu đồ `nb_09_lap_lai_04` và CLAUDE.md (không chạy gì khác khi đang đo).
- **Tab Storage của 05 trên History Server trống**, vì 05 bỏ cache trước khi kết thúc nên event log không còn bảng cache. Đã chạy lại 05 vào gốc đo `/perf/s100` (dữ liệu giống `/data`, không đụng `/data` và `data/output`) và chụp tab Storage ở :4040 khi bảng đã cache 100% (lần chụp đầu quá sớm, chỉ 20%). Report tạm của lần chạy này đã xóa; ứng dụng `05_analysis|storage` còn trên History Server.
- **Lần 05 "thật" trên cụm** (`05_analysis`, 23/10) chạy trước khi làm phẳng Zipf (D11). Vì vậy ảnh SQL và Storage dùng lần chạy trên dữ liệu hiện tại (`05_analysis|s100|w2|r1`, `05_analysis|storage`).
- **Script chụp ảnh dừng ở lần đầu** (History Server mở chậm khi đọc event log, và lấy nhầm ứng dụng `local-…`). Đã sửa: tăng thời gian chờ lên 180 giây, gặp lỗi ở một nhóm thì ghi lại rồi chụp tiếp, luôn ghi danh sách ảnh.
- **Biểu đồ trang Thời gian thực bị nối thẳng 14:45 → 16:15** khi vẽ cả ngày (thiếu cửa sổ không có doc). Đã sửa bằng lưới 15 phút liên tục.
- **Heredoc của Bash tool làm hỏng `\n`** trong vài lần sửa notebook. Đã sửa bằng Edit, như lỗi đã ghi trong CLAUDE.md.
- **Màu biểu đồ notebook:** skill `vifood-dashboard` chỉ cho 2 màu nhấn (herb, chili), nhưng cặp herb–chili có độ tách màu dưới mức cho người mù màu đỏ–lục (validator của skill `dataviz`). Biểu đồ nhiều chuỗi trong notebook vì vậy dùng herb, xanh dương, chili, vàng (kèm chú giải hoặc nhãn số). Dashboard không đổi.
- **Spark UI, mục "Global Watermark Gap" khoảng 2,5 triệu giây:** đây là khoảng cách giữa giờ thật (26/10) và giờ sự kiện mô phỏng (27/09), không phải lỗi.
- Đầu phiên cụm đủ 11 container. Cuối phiên vẫn vậy, 2 worker; không còn luồng hay job nào chạy.

## Cần người dùng quyết định
1. **`vifood_local` (bản 10%, 22,8 MB):** xóa, hay đồng bộ lại (`05 --local` rồi `07 --local`, nhớ sao lưu `export_report.json` của cụm)?
   - Hiện các bảng `analysis_*` lệch `overview` 1.145 lượt nấu, `reports` là file của lần chạy trên cụm.
   - pytest trên `vifood_local` vẫn 61 đạt, 3 bỏ qua.
   - Đề xuất: **xóa**. Phần code đã xong, dashboard và báo cáo dùng `vifood`. Xóa thì pytest mặc định (`--db vifood_local`) phải đổi sang `vifood` (sửa `conftest.py` và lệnh trong CLAUDE.md).
2. **Lịch sử Git vẫn chứa `.env`** (mật khẩu `admin123`, trùng mật khẩu ghi trong `docker-compose.yml`). Nếu đưa repo lên GitHub công khai: đổi mật khẩu MongoDB / mongo-express, hay làm sạch lịch sử (`git filter-repo`)? Đề xuất: repo để riêng tư thì chưa cần làm gì; công khai thì đổi mật khẩu (đơn giản hơn làm sạch lịch sử).

Việc cần người làm (không đổi): kiểm tra tay 100 món trong `data/output/features_check_sample.csv`.

## Commit
- `Dong goi, notebook bieu do, anh cuoi; do lai 04 100% 1 worker; tach thoi gian sink luong`:
  - code: `scripts/{09_perf.py,01_ingest.sh,make_sample.py,capture_screens.py}`, `src/{10_stream,10d_stream_bench}.py`, `api/routers/realtime.py`, `web/{thoi-gian-thuc.html,js/thoi-gian-thuc.js,js/layout.js,js/danh-gia.js,js/charts.js}`;
  - notebook: `notebooks/{nb_style.py,05_hanh_vi.ipynb,06_mo_hinh.ipynb,09_10_hieu_nang_luong.ipynb}`;
  - dữ liệu, report: `data/sample/`, `data/output/{perf_report.json,perf_runs.jsonl,perf/04_s100_w1_r{2,3}/,stream_report.json,export_report.json,screenshots.json}`, `docs/images/` (58 ảnh);
  - đóng gói, tài liệu: `README.md`, `requirements.txt`, `.env.example`, `.gitignore` (bỏ `.env`), `CLAUDE.md`, D17, D18, DATA_DICTIONARY, PROGRESS, file này.
