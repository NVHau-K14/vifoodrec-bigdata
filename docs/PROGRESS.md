# Tiến độ đồ án

> Cập nhật lần cuối: **26/10/2026**, sau khi đo hiệu năng Spark (D17): 54 lần chạy, 1/2 worker × 10/50/100%, collection `perf`, thẻ "Hiệu năng Spark".
> File này là nguồn chính về tiến độ. Mỗi cuối phiên cập nhật bằng `/handoff`.

## Trạng thái các bước

| Bước | Trạng thái | Kết quả chính |
|---|---|---|
| Hạ tầng Docker | ✅ Xong | 11 container: HDFS 1+2, Spark 1+2, Spark History (:18080), Jupyter, MongoDB, mongo-express (:8090), api (:8000). Đã chạy test 2 worker. |
| 01 Nạp HDFS | ✅ Xong | 4 CSV trong `/data/raw`. Script `scripts/01_ingest.sh` mới viết, chưa chạy lại trên cụm. |
| 02 Làm sạch (clean v2) | ✅ Xong | `foods` 5.499 món (3.996 giữ id cũ, 1.503 món mới id 4001–5503); `ratings_original` 182.556 dòng |
| 03 Đặc trưng món | ✅ Xong (sửa 24/10) | `dish_features` 5.499 dòng, khớp từng giá trị với lần chạy local. Loại món: mặn 3.448, ngọt 1.236, chay 580, đồ uống 235. Đã sửa "hào" (D10) |
| 04 Sinh hành vi | ✅ Xong (100%, chạy lại 24/10) | 50.000 user (49.815 có hoạt động); **23.205.143 sự kiện**; Parquet 261MB; chạy 9 phút. `zipf_offset = 30`, món đứng đầu 1,44% (D11) |
| 05 Phân tích hành vi | ✅ Xong | `src/05_analysis.py`, 14 bảng trong `/data/results/analysis` và JSON trong `data/output/analysis/`; chạy trên cụm 104 giây |
| 06 Mô hình + đánh giá | ✅ Xong | Trên test (39.012 user), NDCG@10: hybrid **0,1588**, hybrid + content 2 vị trí 0,1495 (dùng cho `recs_final`), ALS implicit 0,1539 (alpha 1, rank 128), nấu lại 0,1317. RMSE: ALS 0,684, bias 0,737. Dashboard dùng k = 8. D12, D13 |
| 07 Xuất MongoDB | ✅ Xong | Database `vifood`: 26 collection (25 có dữ liệu, `trending` để trống). Size 290,5 MB, storage 85,2 MB (nén 3,41 lần), index 4,1 MB. `recs` 50.000 doc, 204,3 MB sau khi thêm `because_cooked` (D15). Chạy trên cụm 66,1 giây. Mọi kiểm tra đạt. D14 |
| 08 FastAPI + dashboard | ✅ Xong (2 đợt) | Service `api` (:8000) phục vụ 25 endpoint E0–E26 và 7 trang đầy đủ. pytest 61/61 đạt trên `vifood` (58 đạt + 3 bỏ qua trên `vifood_local`). Độ trễ p95 (`api_report.json`, `vifood`): endpoint cache 1,3–3,5 ms; E12 14,2; E13 4,2; E18 2,9; E19 5,5; E20 9,1 ms, mọi mục tiêu đạt ở cả 2 database; E19 10 luồng p95 37,2 ms, 344,5 req/s. RAM 59,2 MiB / 512 MiB. Ảnh 7 trang ở `docs/images/08_*`. D15, D16 |
| 09 Đo hiệu năng (1 vs 2 worker, 10/50/100%) | ✅ Xong | `scripts/09_perf.py`, 54/54 lần OK (2,71 giờ). 100%: chuỗi 04 → 06f 1.702,9 giây (2 worker) so với 2.309,2 giây (1 worker), **speedup 1,36**; 04 1,64, 06b 1,32. 10%: speedup 0,88 (2 worker chậm hơn). `perf_report.json`, collection `perf` (47 doc), thẻ ở trang Đánh giá. D17 |
| 10 Nâng cao: Structured Streaming | ⬜ Chưa | |
| Báo cáo Word + slide | ⬜ Chưa | |

### Số liệu bước 06 (cụm, chạy lại 25/10; chi tiết trong `data/output/models_metrics.json` và `model_*_report.json`)
- **Chia dữ liệu (06a):** view test có 39.012 user được đánh giá, gồm ấm 36.979, ít 742, **lạnh 1.291** (tính theo train + val). Mẫu dò tham số: 10.000 user của val.
- **Xếp hạng trên test, NDCG@10 (tất cả / ấm / ít / lạnh):**
  - hybrid 0,1588 / 0,1636 / 0,1034 / 0,0540;
  - hybrid + content 2 vị trí 0,1495 / 0,1539 / 0,0987 / 0,0540;
  - ALS implicit 0,1539 / 0,1602 / 0,1062 / 0;
  - nấu lại 0,1317;
  - popularity theo vùng-tuổi 0,0571;
  - content 0,0095;
  - random 0,0015.
- **Khoảng tin cậy 95% của hiệu NDCG@10:**
  - hybrid − ALS = +0,0049 [0,0042; 0,0056];
  - hybrid + content 2 vị trí − hybrid = −0,0092 [−0,0096; −0,0089];
  - ALS − nấu lại = +0,0221 [0,0203; 0,0240].
- **Hybrid và hybrid + content 2 vị trí (test, top 10):**

  | | Hybrid | Hybrid + content 2 vị trí |
  |---|---|---|
  | Coverage | 41,3% | 58,0% |
  | Novelty | 9,13 | 9,91 |
  | Diversity | 0,854 | 0,849 |
  | Recall món mới @10 | 0 | 1,80% |
  | NDCG@10 biến thể khám phá | 0,0960 | 0,0846 |

- **ALS implicit:** alpha 1, rank 128, regParam 0,1, chọn sau khi mở rộng lưới một lần (D13). Rank 128 hơn rank 64 0,0032 trên val. Trọng số hybrid: ALS 0,9, nấu lại 0,1.
- **RMSE (test, 63.370 dòng chung):** trung bình chung 1,071, bias 0,737, ALS explicit 0,684. Trên toàn bộ dòng, "ALS thiếu thì dùng bias" đạt 0,689.
- **Đối chứng 06g:** trên ratings gốc, ALS 1,673 kém hơn trung bình chung 1,578 (−6,0%). Trên dữ liệu mô phỏng, ALS tốt hơn trung bình chung 36,1%.
- **Content:** MinHashLSH recall@20 là 0,789 / 0,868 / 0,993 với 3 / 5 / 10 bảng băm. Tính chính xác 10,9M cặp mất 37 giây.
- **FP-Growth, hit rate@3 cho món ăn kèm:** luật 0,219; mốc theo nhóm món 0,076; mốc 3 canh phổ biến 0,035.
- **K-means (dashboard dùng k = 8):**
  - k = 3: Silhouette 0,227, ARI 0,285, NMI 0,365;
  - k = 8: Silhouette 0,174, ARI 0,418, NMI 0,442;
  - k = 11: Silhouette 0,184, ARI 0,504, NMI 0,512.
- **`recs_final`:** 50.000 user × 50 món. Nguồn lý do gợi ý: als 2.312.304 dòng, content_slot 96.346 dòng (96,7% có món đã nấu làm lý do), pop 91.350 dòng.
- **Thời gian trên cụm (lần chạy 25/10):** 06b 2.756 giây (dò ALS 1.973 giây vì có rank 128), 06f 1.386 giây (thí nghiệm món mới 806 giây), 06e 315 giây. Các file khác lấy từ lần chạy 24/10: 06a 101 giây, 06c 200 giây, 06d 34 giây, 06g 61 giây.

### Số liệu bước 05 (chạy lại 24/10 với `zipf_offset = 30`)
- Kiểm tra: đọc đủ 23.205.143 sự kiện, tổng của hai khối `cube_cook` và `monthly` khớp với bảng gốc. Bảng cơ sở chiếm 237MB trong cache. Chạy trên cụm 104 giây.
- Phễu theo cặp user–món: 11,1% cặp đã xem được lưu, 14,4% được nấu; 44,6% cặp đã nấu được chấm. Tỷ lệ user: lưu 98,1%, nấu 99,0%, chấm 94,6%.
- Thời gian: lượt nấu cuối tuần gần gấp đôi ngày thường, đỉnh là CN 17–19h. Món Tết chiếm 19,2% lượt nấu tháng 2, các tháng khác khoảng 3%.
- Lift: miền Trung với món cay 1,36; nhóm 18–24 tuổi với pha/xay 2,02; nhóm 45+ với canh/súp 1,39; cuối tuần với lẩu 1,54.
- Đuôi dài: Gini lượt nấu 0,698; 1% món đầu chiếm 19,0%, 10% món đầu chiếm 57,7% lượt nấu. Món đứng đầu là "Canh hào thanh mát" với **1,44%** (trước đó 5,17%).
- Tỷ lệ nấu lại cùng một món: 18,7% số cặp đã nấu.

### Số liệu bước 04 (bản 100% chạy lại 24/10 với `zipf_offset = 30`, dùng cho bước 05–06)
- Sự kiện: view 18.637.934 · cook 2.382.842 · favorite 1.385.472 · rate 798.895.
- Tỷ lệ chuyển đổi (theo sự kiện): favorite/view 7,4% · cook/view 12,8% · rate/cook 33,5%.
- Rating: trung bình 3,705, độ lệch chuẩn 1,07, có 47.108 user từng chấm. Mật độ ma trận user × món: 4,55%.
- Số user có hoạt động: tháng 08/2026 (validation) 43.010, tháng 09/2026 (test) 43.687.
- Phiên nấu kiểu "mâm cơm" (từ 2 món trở lên): 15,6%.
- Kiểm tra quy luật (theo món được nấu):
  - Persona ăn chay: 100% món chay.
  - Persona mê hải sản: 65,2% món hải sản.
  - Persona bận rộn: 92,3% món nhanh.
  - Persona thích cay/nhậu: 67,0% món cay.
- Parquet 261MB, chạy 9 phút trên cụm. Bản 10% ở local (`data/hdfs_local`): 5.000 user, 2.292.479 sự kiện.
- Chạy thử 10% ở local (bản **trước** 24/10, cần chạy lại ở bước 06): ALS explicit RMSE 0,771, tốt hơn baseline bias (0,801) và trung bình chung (1,078). ALS implicit P@10 0,024, gấp khoảng 2,5 lần popularity (0,009).

## Việc tiếp theo (theo thứ tự)
1. **Chờ người dùng trả lời 4 câu trong LAST_RUN 26/10:** chụp ảnh History Server ngay hay cuối dự án; giữ hay xóa `/perf` (2,5 GB tính cả bản sao); có đo thêm 50% / 1 worker (khoảng 20 phút: thêm `add("s050", 1, CHAIN)` vào `build_plan` của `scripts/09_perf.py`, chạy `python scripts/09_perf.py`, rồi `07 --only perf`); đồng ý làm Structured Streaming.
2. **Structured Streaming (bước 10, nâng cao):** viết bản thiết kế vào LAST_RUN trước khi code: nguồn sự kiện (phát lại `events` theo thời gian hay sinh mới), cửa sổ, watermark, ghi `trending` (index `window_end -1`). E25 hiện đọc dạng `{window_start, window_end, total_cooks, items: [{food_id, cooks}]}`; tiến độ ở Tổng quan là bước "10".
3. **Kiểm tra `scripts/01_ingest.sh`:** đọc lại script, chưa cần chạy.

## Việc còn treo
- [ ] Kiểm tra tay 100 món trong `data/output/features_check_sample.csv`, điền cột `kiem_tra`, rồi tính độ chính xác cho báo cáo. **Mẫu đã chốt theo hash (24/10), có thể bắt đầu điền.** Chạy lại 03 vẫn ra đúng 100 món này, nhưng file sẽ bị ghi đè nên cần sao lưu cột đã điền trước khi chạy.
- [x] Ratings gốc: đã làm thí nghiệm đối chứng 06g (ALS kém hơn trung bình chung 6%).
- [ ] Ảnh chụp UI cho báo cáo: **để cuối dự án** (đo hiệu năng đã xong, chờ người dùng chọn chụp ngay hay để cuối). Thêm: History Server Timeline + Executors của 06b ở 1 và 2 worker (`06b_als|s100|w1|r1`, `06b_als|s100|w2|r1`), thẻ "Hiệu năng Spark". Lấy từ History Server http://localhost:18080 (các app 02–06; với 05 thì chụp thêm tab Storage và tab SQL) và HDFS UI (`/data/curated`, `/data/events`, `/data/results/analysis`). `docs/images/` đang trống.
- [x] Chốt mẫu kiểm tra tay theo hash: đã chạy lại 03 trên cụm (24/10).
- [x] HDFS replication: `get_spark()` ghi 2 bản sao, đã `setrep -R 2 /data`, fsck HEALTHY (D12).
- [x] Đã xóa `/data/events/events_csv` (bản cũ). Sinh lại bằng `04 --csv` khi đo hiệu năng.
- [ ] Repo GitHub và `git config`: tạm chưa làm, theo quyết định của nhóm (tác giả commit đang là `Admin`).
- [ ] Dựng notebook biểu đồ từ `data/output/analysis/*.json`, làm nền cho trang "Hành vi ăn uống" của dashboard.
- [ ] Notebook hoặc biểu đồ cho bước 06 từ `data/output/models_metrics.json` và `model_*_report.json`: bảng so sánh mô hình, khoảng tin cậy, lưới dò ALS, Silhouette theo k, recall của LSH. Dùng cho trang "Đánh giá mô hình".
- [ ] Thư mục checkpoint của ALS (`hdfs:///tmp/checkpoint`) có thể xóa sau khi chốt bước 06.
- [ ] Nhắn giảng viên về việc dùng dữ liệu hành vi mô phỏng (kế hoạch mục 2.2 khuyến nghị). Chưa rõ đã nhắn hay chưa.
- [x] `mongo-express` đã có trong compose (cổng 8090, tài khoản trong `.env`). Service `api` đã có (cổng 8000).
- [ ] `vifood_local` không đồng bộ: các bảng `analysis_*` lệch `overview` 1.145 lượt nấu, `reports` là file của lần chạy trên cụm. Nếu cần bản local khớp thì chạy lại `05 --local` rồi `07 --local` (nhớ sao lưu `export_report.json` của cụm).
- [x] Ảnh món: trình duyệt thường tải được `monngonmoingay.com`, `image.cooky.vn` có lúc hết thời gian chờ. Không tải sẵn; dùng ảnh thay thế theo 10 nhóm món, bỏ ảnh sau 4 giây (D15, skill mục 4).
- [x] Ảnh chụp 7 trang dashboard ở 1440 và 390 (`docs/images/08_*`). Chụp lại sau khi có streaming.
- [x] Luật đề xuất cho cụm (D16): người dùng đã duyệt; mỗi cụm 1 câu, không trùng câu giữa các cụm (26/10).
- [ ] `.env` đang được commit và có mật khẩu `admin123`. Nếu đưa repo lên GitHub công khai thì chuyển sang `.env.example`.
- [ ] Database `vifood_local` (bản 10%, 22,8 MB) giữ lại để phát triển API; xóa khi không cần nữa.
- [ ] Ảnh chụp cho báo cáo: thêm `mongo-express` và các `explain()` trong `export_report.json`.
- [ ] `README.md`, `requirements.txt`, `data/sample/`: làm lúc nộp bài.
- [ ] `/perf` trên HDFS (1,3 GB, 2,5 GB tính cả bản sao): giữ đến khi viết xong báo cáo, xóa bằng `hdfs dfs -rm -r /perf` khi không cần.
- [ ] Lần 03 / danh mục / 1 worker để lại event log không đóng (2 lần liên tiếp, chưa rõ nguyên nhân); thời lượng lấy từ job cuối (D17).
- [ ] Biểu đồ (a) thẻ Hiệu năng ở 375px: nhãn số trên cột nhỏ chồng nhau (chưa sửa).

## Khác với kế hoạch ban đầu (cần nêu trong báo cáo)
- Mã nguồn để phẳng `src/NN_ten.py` thay vì chia `src/ingest`, `src/etl`…
- Danh mục món là 5.499 món sau khi tự làm sạch, thay vì 4.000 món của bản clean gốc.
- `is_quick` xếp hạng theo độ ngắn của cách làm và số nguyên liệu trong từng nguồn, không theo "≤ 20 phút", vì `cooking_time` là số ngẫu nhiên.
- Dữ liệu sự kiện: 261MB Parquet (CSV tương đương 1,38GB), thấp hơn ước tính 1,5–3GB CSV.

## Nhật ký
- **23/10 sáng:** khảo sát ViFoodRec, lập kế hoạch chi tiết (`docs/plan/`), dựng cụm Docker.
- **23/10 chiều:**
  - clean v2, làm ở cuộc trò chuyện "Bộ dữ liệu vifoodrec";
  - bước 03, giữ cột `season`;
  - ratings gốc tạm gác lại.
- **23/10 tối:**
  - bước 04, chạy thử 1% và 10% ở local rồi 100% trên cụm;
  - dựng `CLAUDE.md`, `docs/`, `.claude/`;
  - chuyển sang làm việc bằng tab Code của Claude desktop.
- **23/10 khuya – 24/10:**
  - chuyển cấu hình vào `.claude/`, `git init` và commit đầu tiên;
  - viết bước 05, chạy thử trên bản 10% ở local rồi chạy trên cụm;
  - phát hiện "Canh hào thanh mát" bị gán `main_protein` là "đậu hũ/chay" và chiếm 4,2% lượt nấu;
  - sửa "hào" ở 03 (chỉ 1 món đổi) và kẹp `quality` ở 04, chạy lại 03 → 04 → 05 trên cụm. Món này vẫn chiếm 5,17% lượt nấu, chờ quyết định (D10).
- **24/10 sáng:**
  - bật Spark History Server (:18080) và event log;
  - thêm `zipf_offset = 30` ở 04 và chạy lại 04 (100%) → 05. Món đứng đầu giảm còn 1,44%, Gini 0,698;
  - mẫu kiểm tra tay chọn theo hash (D11).
- **24/10 (tiếp):** chạy lại 03 trên cụm để ghi mẫu kiểm tra theo hash. `dish_features` mới giống hệt bản cũ (`exceptAll` ra 0 dòng ở cả hai chiều). Bước 06 sẽ làm theo kiểu thiết kế trước.
- **24/10 tối:** chạy job khảo sát chia train/val/test (56,7% cặp được nấu ở test đã gặp ở train; 2.690 user lạnh trong test). Viết bản đề xuất thiết kế bước 06 vào LAST_RUN. Phát hiện lỗi replication 3 trên HDFS.
- **24/10 khuya:** chốt thiết kế bước 06 (D12, có 9 sửa đổi của chat). Sửa replication về 2, xóa `events_csv`. Viết `rec_common.py` và 06a–06g, chạy local rồi trên cụm. Số user lạnh ở test đúng ra là 1.291 (con số 2.690 ở dòng trên tính theo train). Hybrid thắng ALS với khoảng tin cậy dương, nhưng trọng số content bằng 0 (D13).
- **25/10:** chốt 3 câu hỏi của bước 06. Mở rộng lưới ALS một lần (chọn alpha 1, rank 128), thêm hybrid + content 2 vị trí cho `recs_final`, dashboard dùng k = 8 (có thêm k = 3 và k = 11). Chạy lại 06b, 06f, 06e trên cụm. Bước 07 sẽ làm theo kiểu thiết kế trước.
- **25/10 (tiếp):** viết bản đề xuất thiết kế bước 07 vào LAST_RUN. Đã đo kích thước BSON trên mẫu thật: `recs` 1 doc/user bỏ chuỗi lý do còn 4.052 B/user, so với 8.956 B khi giữ chuỗi. MongoDB đang trống, `pymongo` 4.19.0 có sẵn trong image.
- **25/10 (tối):** chốt bước 07 (D14). Thêm `mongo-express` (:8090). Viết `07_export_mongo.py`, chạy local 3 lần rồi chạy trên cụm 66 giây: 26 collection, 290,5 MB, nén 3,41 lần. 5 user mẫu khớp `recs_final`, không có `food_id` nào thiếu trong `dishes`. Kiểm tra múi giờ phải đổi sang giờ bắt đầu phiên, vì sự kiện trong phiên lấn sang giờ sau. Việc tiếp theo là thiết kế bước 08.
- **25/10 (khuya):** cài skill `frontend-design`, thêm quy tắc không ghi tên thành viên ngoài báo cáo. Đề xuất thiết kế bước 08 rồi chốt (D15): thêm `because_cooked` vào `recs` (chạy lại `07 --only recs`), sửa skill `vifood-dashboard`. Đợt 1: dựng service `api`, 16 endpoint, 3 trang (Tổng quan, Gợi ý món, Đánh giá mô hình), pytest 39/39 đạt trên `vifood`.
- **25/10 (đêm):** sửa sau khi xem đợt 1: biểu đồ theo tháng (bỏ series rỗng), bố cục trang Gợi ý (hàng đầu gọn, hồ sơ cột phải), ảnh thay thế theo nhóm món, chip "Bạn đã nấu N lần" (`n_cook_before`).
- **25/10 (đêm, tiếp):** đợt 2 bước 08 (D16): 9 endpoint, 4 trang Hành vi, Món ăn, Phân khúc, Thời gian thực, nhãn và đề xuất cụm theo luật, `test_consistency`, `bench_latency.py` (mọi mục tiêu đạt), 14 ảnh chụp.
- **26/10 (tiếp):** chốt đo hiệu năng (D17). `Paths` theo `VIFOOD_DATA_ROOT` / `VIFOOD_OUTPUT_DIR`, `common.Timer` gắn job group, `--fixed` cho 06b/c/e/f/g, `scripts/09_perf.py`. Bản thường ra 28/28 report giống hệt mốc. Chạy 54 lần (2,71 giờ, đều OK): speedup chuỗi 1,36 ở 100%, 0,88 ở 10%; 06b 1 worker không hết bộ nhớ. `07 --only perf`, thẻ "Hiệu năng Spark", pytest 62/62.
- **26/10:** mỗi cụm 1 đề xuất đặc trưng nhất, không trùng giữa các cụm; `cook_per_view` cao là "hay nấu sau khi xem". Khảo sát và viết bản đề xuất đo hiệu năng Spark (1/2 worker × 10/50/100%, `--fixed`, History Server REST), chờ duyệt.
