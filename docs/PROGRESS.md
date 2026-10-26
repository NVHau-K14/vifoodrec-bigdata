# Tiến độ đồ án

> Cập nhật lần cuối: **26/10/2026 (khuya, chốt kiểm tay)**. **Phần dữ liệu và code đã xong hoàn toàn, kể cả kiểm tay 100 món** (D19: món đúng cả 7 thuộc tính 59%, 60% khi bỏ `season`). **Không còn việc nào cần chạy trên cụm.** Bước tiếp theo là báo cáo Word và slide. Lần trước (tối) làm xong: đo lại 04 ở 100% / 1 worker, tách thời gian sink của luồng, notebook biểu đồ, đóng gói (README, requirements, `data/sample/`, `.env.example`), sửa trang Thời gian thực, đợt ảnh cuối (32 ảnh giao diện + 26 biểu đồ notebook). Còn lại: báo cáo Word + slide.
> File này là nguồn chính về tiến độ. Mỗi cuối phiên cập nhật bằng `/handoff`.

## Trạng thái các bước

| Bước | Trạng thái | Kết quả chính |
|---|---|---|
| Hạ tầng Docker | ✅ Xong | 11 container: HDFS 1+2, Spark 1+2, Spark History (:18080), Jupyter, MongoDB, mongo-express (:8090), api (:8000). Đã chạy test 2 worker. |
| 01 Nạp HDFS | ✅ Xong | 4 CSV trong `/data/raw`. `scripts/01_ingest.sh` đã chạy thử vào `/tmp/ingest_test` (26/10): md5 khớp `/data/raw` và file trên máy, replication 2, chạy lại thì bỏ qua, `--force` ghi đè; đã xóa thư mục thử. |
| 02 Làm sạch (clean v2) | ✅ Xong | `foods` 5.499 món (3.996 giữ id cũ, 1.503 món mới id 4001–5503); `ratings_original` 182.556 dòng |
| 03 Đặc trưng món | ✅ Xong (sửa 24/10) | `dish_features` 5.499 dòng, khớp từng giá trị với lần chạy local. Loại món: mặn 3.448, ngọt 1.236, chay 580, đồ uống 235. Đã sửa "hào" (D10). Kiểm tay 100 món (D19): `main_protein` 90%, `main_method` 79%, `dish_category` 95%, `dish_type_fixed` 97%, `is_vegetarian` 90%, `is_spicy` 99% (cách (b) mở rộng 84%, ước tính), `season` 99%; đúng cả 7: 59% |
| 04 Sinh hành vi | ✅ Xong (100%, chạy lại 24/10) | 50.000 user (49.815 có hoạt động); **23.205.143 sự kiện**; Parquet 261MB; chạy 9 phút. `zipf_offset = 30`, món đứng đầu 1,44% (D11) |
| 05 Phân tích hành vi | ✅ Xong | `src/05_analysis.py`, 14 bảng trong `/data/results/analysis` và JSON trong `data/output/analysis/`; chạy trên cụm 104 giây |
| 06 Mô hình + đánh giá | ✅ Xong | Trên test (39.012 user), NDCG@10: hybrid **0,1588**, hybrid + content 2 vị trí 0,1495 (dùng cho `recs_final`), ALS implicit 0,1539 (alpha 1, rank 128), nấu lại 0,1317. RMSE: ALS 0,684, bias 0,737. Dashboard dùng k = 8. D12, D13 |
| 07 Xuất MongoDB | ✅ Xong | Database `vifood`: 26 collection (25 có dữ liệu, `trending` để trống). Size 290,5 MB, storage 85,2 MB (nén 3,41 lần), index 4,1 MB. `recs` 50.000 doc, 204,3 MB sau khi thêm `because_cooked` (D15). Chạy trên cụm 66,1 giây. Mọi kiểm tra đạt. D14 |
| 08 FastAPI + dashboard | ✅ Xong (2 đợt) | Service `api` (:8000) phục vụ 25 endpoint E0–E26 và 7 trang đầy đủ. pytest 61/61 đạt trên `vifood` (58 đạt + 3 bỏ qua trên `vifood_local`). Độ trễ p95 (`api_report.json`, `vifood`): endpoint cache 1,3–3,5 ms; E12 14,2; E13 4,2; E18 2,9; E19 5,5; E20 9,1 ms, mọi mục tiêu đạt ở cả 2 database; E19 10 luồng p95 37,2 ms, 344,5 req/s. RAM 59,2 MiB / 512 MiB. Ảnh 7 trang ở `docs/images/08_*`. D15, D16 |
| 09 Đo hiệu năng (1 vs 2 worker, 10/50/100%) | ✅ Xong | `scripts/09_perf.py`, 66/66 lần OK. Speedup cả chuỗi 04 → 06f: **0,88 / 1,59 / 1,38** ở 10/50/100% (100%: 2.345,2 → 1.702,9 giây). 04: 1,03 / 2,19 / **1,71** (04 ở 1 worker chạy 3 lần ở cả 50% và 100%; 100%: 864,4 / 1.230,1 / 900,4 giây, r2 chạy trùng việc khác trên máy); 06b: 1,01 / 1,56 / 1,32. `perf_report.json`, collection `perf` (55 doc), thẻ 4 biểu đồ ở trang Đánh giá. D17 |
| 10 Nâng cao: Structured Streaming | ✅ Xong | Phát lại CN 27/09/2026 (92.893 sự kiện) qua file JSONL trên HDFS, cửa sổ 60/15 phút, watermark 10 phút, khử trùng, join `users`, `foreachBatch` → `trending` (idempotent). 10c: 3 kịch bản đều đạt (s1, s2 khớp tuyệt đối 205.920 ô). Độ trễ sự kiện → API p95 2,85 giây ở tốc độ 60; tốc độ 300 bền vững, 1.200 chạm trần. Thông lượng (đo lại 26/10 chiều) 6.645 / 7.394 dòng/giây với 2 / 4 core; ghi MongoDB 64–67% thời gian batch, trong đó upsert `trending_cells` gấp 3,45–3,64 lần phần top 20 + `trending`. `scripts/10_stream.sh`, Spark UI :4041. D18 |
| Đóng gói + ảnh | ✅ Xong (26/10) | `README.md`, `requirements.txt`, `.env.example` (`.env` bỏ khỏi Git), `data/sample/` (11 file, 299–500 dòng), 3 notebook biểu đồ (26 PNG `docs/images/nb_*`), 32 ảnh giao diện (`data/output/screenshots.json`) |
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
1. **Báo cáo Word + slide.** Phần dữ liệu và code đã xong hoàn toàn (26/10), kể cả kiểm tay; không còn việc nào cần chạy trên cụm. Số liệu lấy từ `data/output/*report*.json`, D10–D19 (độ chính xác đặc trưng món: đúng cả 7 thuộc tính 59%, ghi thêm 60% khi bỏ `season` vì mẫu `season` nhỏ; `is_spicy` cách (b) 84,0%, 16 lỗi, ước tính); biểu đồ `docs/images/nb_*.png`; ảnh giao diện theo `data/output/screenshots.json`.

## Việc còn treo
- [x] Kiểm tra tay 100 món (26/10): bản cuối `features_check_sample.csv` và bản lần 1 `features_check_sample_lan1.csv` đã commit; độ chính xác trong `features_check_report.json` (`scripts/eval_features_check.py`) và D19. **Không sửa luật 03, không chạy lại pipeline** (người dùng chốt). Không chạy lại 03 khi chưa sao lưu file đã điền.
- [x] `data/features_check_sample.csv` (thư mục `data/`, ngày 24/10, cột `kiem_tra` trống, chưa đưa lên Git) là bản trống cũ, không phải file đã điền. **Người dùng chốt: để nguyên, không động tới** (không xóa, không commit).
- [x] Ratings gốc: đã làm thí nghiệm đối chứng 06g (ALS kém hơn trung bình chung 6%).
- [x] Ảnh chụp UI cho báo cáo (26/10 tối): 32 ảnh, danh sách trong LAST_RUN và `data/output/screenshots.json`. Ghi chú cũ: **để cuối dự án** (người dùng đã chọn 26/10, gồm cả ảnh History Server). Thêm: History Server Timeline + Executors của 06b ở 1 và 2 worker (`06b_als|s100|w1|r1`, `06b_als|s100|w2|r1`), thẻ "Hiệu năng Spark". Lấy từ History Server http://localhost:18080 (các app 02–06; với 05 thì chụp thêm tab Storage và tab SQL) và HDFS UI (`/data/curated`, `/data/events`, `/data/results/analysis`). `docs/images/` đang trống.
- [x] Chốt mẫu kiểm tra tay theo hash: đã chạy lại 03 trên cụm (24/10).
- [x] HDFS replication: `get_spark()` ghi 2 bản sao, đã `setrep -R 2 /data`, fsck HEALTHY (D12).
- [x] Đã xóa `/data/events/events_csv` (bản cũ). Sinh lại bằng `04 --csv` khi đo hiệu năng.
- [ ] Repo GitHub và `git config`: tạm chưa làm, theo quyết định của nhóm (tác giả commit đang là `Admin`).
- [x] Dựng notebook biểu đồ từ `data/output/analysis/*.json` (`notebooks/05_hanh_vi.ipynb`, 10 PNG).
- [x] Notebook `notebooks/06_mo_hinh.ipynb` (9 PNG) và `09_10_hieu_nang_luong.ipynb` (7 PNG). Ghi chú cũ: notebook hoặc biểu đồ cho bước 06 từ `data/output/models_metrics.json` và `model_*_report.json`: bảng so sánh mô hình, khoảng tin cậy, lưới dò ALS, Silhouette theo k, recall của LSH. Dùng cho trang "Đánh giá mô hình".
- [x] Đã xóa `hdfs:///tmp/checkpoint` (52,7 MB, 26/10). Chạy lại 06 thì Spark tạo lại.
- [ ] Nhắn giảng viên về việc dùng dữ liệu hành vi mô phỏng (kế hoạch mục 2.2 khuyến nghị). Chưa rõ đã nhắn hay chưa.
- [x] `mongo-express` đã có trong compose (cổng 8090, tài khoản trong `.env`). Service `api` đã có (cổng 8000).
- [x] (Đã xóa `vifood_local`, mục này không còn.) `vifood_local` không đồng bộ: các bảng `analysis_*` lệch `overview` 1.145 lượt nấu, `reports` là file của lần chạy trên cụm. Nếu cần bản local khớp thì chạy lại `05 --local` rồi `07 --local` (nhớ sao lưu `export_report.json` của cụm).
- [x] Ảnh món ăn trên dashboard hiện hay không **không quan trọng**, không cần chụp lại (người dùng chốt 26/10).
- [x] Ảnh món: trình duyệt thường tải được `monngonmoingay.com`, `image.cooky.vn` có lúc hết thời gian chờ. Không tải sẵn; dùng ảnh thay thế theo 10 nhóm món, bỏ ảnh sau 4 giây (D15, skill mục 4).
- [x] Ảnh chụp 7 trang dashboard ở 1440 và 390 (`docs/images/08_*`). Chụp lại sau khi có streaming.
- [x] Luật đề xuất cho cụm (D16): người dùng đã duyệt; mỗi cụm 1 câu, không trùng câu giữa các cụm (26/10).
- [x] `.env` bỏ khỏi Git (`git rm --cached`, thêm vào `.gitignore`), có `.env.example`. **Lưu ý:** `.env` vẫn còn trong lịch sử các commit cũ, và `docker-compose.yml` vẫn ghi mật khẩu MongoDB (`MONGO_INITDB_ROOT_PASSWORD`). Repo để riêng tư (người dùng chọn 26/10); README mục 5 ghi cách xử lý nếu công khai: đổi mật khẩu MongoDB / mongo-express.
- [x] Đã xóa database `vifood_local` (26/10, người dùng chọn); pytest mặc định `--db vifood` (64/64 đạt).
- [x] Ảnh `mongo-express` (database, `recs`, `trending`). Các `explain()` vẫn chỉ có trong `export_report.json` (chưa có ảnh).
- [x] `README.md`, `requirements.txt`, `data/sample/` (26/10).
- [ ] `/perf` trên HDFS (1,3 GB, 2,5 GB tính cả bản sao): **giữ đến khi viết xong báo cáo** (người dùng chốt 26/10), sau đó xóa bằng `hdfs dfs -rm -r /perf`.
- [ ] Lần 03 / danh mục / 1 worker để lại event log không đóng (2 lần liên tiếp, chưa rõ nguyên nhân); thời lượng lấy từ job cuối (D17).
- [x] Biểu đồ (a) thẻ Hiệu năng: nhãn số trên cột ẩn khi thẻ hẹp hơn 520px (26/10).
- [x] 04 chạy phần sinh sự kiện 2 lần (`repartitionByRange` lấy mẫu chạy lại mapInPandas): người dùng chọn chỉ ghi vào báo cáo (26/10).
- [x] Đợt ảnh cuối có trang Thời gian thực khi luồng đang chạy, Spark UI :4041 (danh sách query + thống kê). `data/output/stream/statestore_sample.txt` là file văn bản, dán thẳng vào báo cáo.
- [ ] `data/stream/` (file phát lại, nhật ký từng lần chạy) không đưa lên Git; sinh lại bằng `10a_stream_prep.py`. `/data/stream` trên HDFS giữ đoạn phát lại và đáp án; `reset` chỉ xóa incoming / archive / checkpoint.
- [ ] MongoDB `vifood` đang giữ kết quả của lượt phát lại cả ngày (06:00–24:00, tốc độ 300, phát lại 26/10 tối sau đợt ảnh), trạng thái "đã dừng" (người dùng chọn giữ). Demo thì `reset` rồi `start`.

## Hướng phát triển (cần nêu trong báo cáo)
Từ kiểm tay 100 món (D19). **Mỗi thay đổi dưới đây phải chạy lại 03 → 07** (đặc trưng, sinh hành vi, phân tích, mô hình, MongoDB) nên không làm trong phạm vi hiện tại.
- Thêm ớt tươi vào luật cay ("ớt" đứng riêng, ớt băm, ớt sừng, ớt trái), trừ ớt chuông; không lấy chữ "ớt" trong tên món làm căn cứ khi đó là ớt chuông; bỏ mù tạt khỏi luật cay.
- Thêm sữa, bơ, kem, phô mai, mật ong, gelatine (và mayonnaise) vào danh sách nguyên liệu động vật của luật chay; xử lý hạt nêm không ghi "chay".
- Luật mùa cho đồ uống ấm: trà nóng, trà quế, trà thảo mộc… không gán "nóng".
- Thêm nhóm món / cách làm còn thiếu: gia vị / xốt, cuốn, ủ / ngâm.
- Dùng các bước nấu (công thức) để gán `main_method`, thay vì chỉ dựa vào tên món và nguyên liệu (độ chính xác hiện 79%, thấp nhất).

## Khác với kế hoạch / hạn chế (cần nêu trong báo cáo)
- **Bộ sinh 04 không có lượt nấu khoảng 14–16h và 1–5h.** Giờ bắt đầu phiên lấy ngẫu nhiên trong khung của bữa (`SLOT_HOURS`: sáng 6–9h, trưa 10–13h, tối 16–20h, khuya 21–24h), nên ngoài các khung này chỉ có sự kiện lấn giờ của phiên bắt đầu trước đó (cả năm: 14h có 89 lượt nấu, 1h có 8, 2–5h và 15h bằng 0). Vì vậy biểu đồ ngày phát lại (bước 10) về 0 ở các cửa sổ kết thúc 15:00–16:00, và heatmap giờ × thứ có các cột trống. Đây là giới hạn của mô phỏng, không phải hành vi thật.
- **04 ở 50% / 1 worker chậm hơn tính trên mỗi user, qua 3 lần đo:** thời gian task của giai đoạn sinh là 41,1–44,9 ms/user, so với 31,9 và 33,3 ms/user ở 100% / 1 worker (r1, r3). Chưa rõ nguyên nhân (D17). Điều này làm speedup của 04 ở 50% (2,19) cao hơn ở 100% (1,71).
- Structured Streaming nằm ở `src/10*_*.py` + `src/stream_common.py` thay vì thư mục `src/streaming`. `api/bench_stream.py` trong bản thiết kế được gộp vào `src/10d_stream_bench.py`.
- Phép lọc loại sự kiện đặt sau phép khử trùng, không ngay sau `withWatermark` như bản thiết kế, vì optimizer đẩy phép lọc xuống dưới EventTimeWatermark và làm tick vô dụng (bài thử 10t, D18).
- Mã nguồn để phẳng `src/NN_ten.py` thay vì chia `src/ingest`, `src/etl`…
- Danh mục món là 5.499 món sau khi tự làm sạch, thay vì 4.000 món của bản clean gốc.
- `is_quick` xếp hạng theo độ ngắn của cách làm và số nguyên liệu trong từng nguồn, không theo "≤ 20 phút", vì `cooking_time` là số ngẫu nhiên.
- Dữ liệu sự kiện: 261MB Parquet (CSV tương đương 1,38GB), thấp hơn ước tính 1,5–3GB CSV.

## Nhật ký
- **26/10 (khuya, chốt):** người dùng chốt cách báo cáo kiểm tay (đúng cả 7 thuộc tính 59%, thêm 60% khi bỏ `season`; `is_spicy` (b) 84,0%, 16 lỗi, tính cả dòng 89), để nguyên bản trống cũ `data/features_check_sample.csv`. Phần dữ liệu và code xong hoàn toàn; không còn việc nào cần chạy trên cụm.
- **26/10 (khuya, tiếp):** người dùng kiểm tay xong 100 món. Commit bản cuối và bản lần 1 ngay; `scripts/eval_features_check.py` → `features_check_report.json`; D19 (độ chính xác, phát hiện); DATA_DICTIONARY (`is_spicy`, `is_vegetarian`, `season`); hướng phát triển. Không sửa luật 03, không chạy lại pipeline.
- **26/10 (khuya):** xóa `vifood_local`, pytest mặc định `vifood`. README mục "Nếu công khai repo". Ảnh `mongo_recs` thành 1 document (mở 3 phần tử `items`), thêm `mongo_trending_doc`; trang document riêng của mongo-express 1.0.2 làm sập container khi `_id` không phải ObjectId nên lọc theo `_id` trên trang collection. Bảng so sánh mô hình: sát lề trái, in đậm giá trị tốt nhất từng cột. Ghi 2 hạn chế cho báo cáo. Phần dữ liệu và code xong.
- **26/10 (tối):** đo 04 ở 100% / 1 worker thêm 2 lần (1.230,1 và 900,4 giây; r2 trùng việc khác trên máy), speedup 04 ở 100% 1,71, chuỗi 1,38. Kiểm tra replayer: tick cuối đã phát sau mọi sự kiện bị giữ, không sửa. `10_stream.py` tách thời gian (a) upsert ô / (b) top 20 + trending; đo lại thông lượng 10d. Notebook 05, 06, 09_10 (26 PNG). Chạy thử 01 vào `/tmp/ingest_test`, xóa `/tmp/checkpoint`. README, requirements, `data/sample/`, `.env.example`. Trang Thời gian thực: cả đoạn phát lại khi dừng, "Cửa sổ chưa đủ 1 giờ dữ liệu", ngày phát lại, 24:00. Đợt ảnh cuối bằng Playwright (32 ảnh).
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
- **26/10 (chiều):** chạy lại 04 ở 50% / 1 worker thêm 2 lần (575,8 và 631,8 giây: không phải nhiễu). Ghi D18 và làm Structured Streaming: `stream_common.py`, 10a (đoạn phát lại + đáp án), 10b (replayer qua WebHDFS, tick, trễ, gửi lặp), `10_stream.py` (dedup, join, cửa sổ 60/15, `foreachBatch` idempotent), `scripts/10_stream.sh`, cổng 4041. Bài thử 10t phát hiện phép lọc bị đẩy xuống dưới watermark nên đổi thứ tự. 10c: 3 kịch bản đều đạt; đọc state store (phải gọi `spark.streams` trước). 10d: độ trễ p95 sự kiện → API 2,85 giây ở tốc độ 60; thông lượng khoảng 4.600 dòng/giây, nút thắt là ghi MongoDB. E25 và trang Thời gian thực mới, 07 tạo index, E1 bước 10 "Xong". pytest 64/64.
- **26/10 (sáng):** đo thêm chuỗi 50% / 1 worker (8/8 OK, report giống hệt bản 2 worker). `speedup_by_scale`: chuỗi 0,88 / 1,59 / 1,36; speedup cao nhất ở 50%, một phần do 04 ở 50% / 1 worker chậm bất thường (21,7 ms/user so với 15,6–18,5 ms). Phát hiện 04 chạy phần sinh 2 lần. Biểu đồ (d), ẩn nhãn cột (a) khi thẻ < 520px, pytest 62/62. Viết bản thiết kế Structured Streaming vào LAST_RUN.
- **26/10:** mỗi cụm 1 đề xuất đặc trưng nhất, không trùng giữa các cụm; `cook_per_view` cao là "hay nấu sau khi xem". Khảo sát và viết bản đề xuất đo hiệu năng Spark (1/2 worker × 10/50/100%, `--fixed`, History Server REST), chờ duyệt.
