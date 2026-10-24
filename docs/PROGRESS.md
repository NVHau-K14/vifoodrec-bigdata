# Tiến độ đồ án

> Cập nhật lần cuối: **24/10/2026** (khuya), sau khi chạy xong bước 06 (06a–06g) trên cụm.
> File này là nguồn chính về tiến độ. Mỗi cuối phiên cập nhật bằng `/handoff`.

## Trạng thái các bước

| Bước | Trạng thái | Kết quả chính |
|---|---|---|
| Hạ tầng Docker | ✅ Xong | 9 container: HDFS 1+2, Spark 1+2, Spark History (:18080), Jupyter, MongoDB. Đã chạy test 2 worker. |
| 01 Nạp HDFS | ✅ Xong | 4 CSV trong `/data/raw`. Script `scripts/01_ingest.sh` mới viết, chưa chạy lại trên cụm. |
| 02 Làm sạch (clean v2) | ✅ Xong | `foods` 5.499 món (3.996 giữ id cũ, 1.503 món mới id 4001–5503); `ratings_original` 182.556 dòng |
| 03 Đặc trưng món | ✅ Xong (sửa 24/10) | `dish_features` 5.499 dòng, khớp từng giá trị với lần chạy local. Loại món: mặn 3.448, ngọt 1.236, chay 580, đồ uống 235. Đã sửa "hào" (D10) |
| 04 Sinh hành vi | ✅ Xong (100%, chạy lại 24/10) | 50.000 user (49.815 có hoạt động); **23.205.143 sự kiện**; Parquet 261MB; chạy 9 phút. `zipf_offset = 30`, món đứng đầu 1,44% (D11) |
| 05 Phân tích hành vi | ✅ Xong | `src/05_analysis.py`, 14 bảng trong `/data/results/analysis` và JSON trong `data/output/analysis/`; chạy trên cụm 104 giây |
| 06 Mô hình + đánh giá | ✅ Xong (chờ chốt 3 câu hỏi) | 06a–06g chạy local rồi trên cụm. Trên test (39.012 user), NDCG@10: hybrid **0,1564**, ALS implicit 0,1508, nấu lại 0,1317, popularity theo vùng-tuổi 0,0571. RMSE: ALS 0,684, bias 0,737. D12, D13 |
| 07 Xuất MongoDB | ⬜ Chưa | |
| 08 FastAPI + dashboard | ⬜ Chưa | |
| Nâng cao: Structured Streaming | ⬜ Chưa | |
| Đo hiệu năng (1 vs 2 worker, 10/50/100%) | ⬜ Chưa | |
| Báo cáo Word + slide | ⬜ Chưa | |

### Số liệu bước 06 (cụm, 24/10; chi tiết trong `data/output/models_metrics.json` và `model_*_report.json`)
- **Chia dữ liệu (06a):** view test có 39.012 user được đánh giá, gồm ấm 36.979, ít 742, **lạnh 1.291** (tính theo train + val; nếu tính theo train như bản đề xuất cũ thì ra 2.690). Mẫu dò tham số: 10.000 user của val.
- **Xếp hạng trên test, NDCG@10 (tất cả / ấm / ít / lạnh):**
  - hybrid 0,1564 / 0,1611 / 0,0975 / 0,0540;
  - ALS implicit 0,1508 / 0,1572 / 0,0986 / 0;
  - nấu lại 0,1317;
  - popularity theo vùng-tuổi 0,0571, chung 0,0510, 2 tháng cuối 0,0497;
  - content 0,0095;
  - random 0,0015.
- **Khoảng tin cậy 95% của hiệu NDCG@10:**
  - hybrid − ALS = +0,0055 [0,0046; 0,0065];
  - ALS − nấu lại = +0,0191 [0,0172; 0,0210];
  - hybrid − popularity theo vùng-tuổi = +0,0993 [0,0975; 0,1011].
- **Biến thể khám phá, NDCG@10:** ALS 0,0934, hybrid 0,0905, content 0,0087.
- **Ngoài độ chính xác (test, top 10):** coverage hybrid 35,6%, ALS 32,9%, content 77,0%, popularity 0,2–0,5%. Novelty hybrid 8,98, content 12,93. Diversity hybrid 0,859, content 0,736.
- **ALS implicit tốt nhất:** alpha 1, rank 64, regParam 0,1, cả hai đều nằm ở biên của lưới. Độ nhạy trọng số implicit: 1/3/5 cho 0,1591, 1/2/10 cho 0,1593, chỉ cook cho 0,1327.
- **Hybrid:** trọng số ALS 0,8, nấu lại 0,2, content 0, popularity 0. Nhóm "ít" giữ nguyên trọng số này (0,0999 so với 0,0647 khi đặt α = 0).
- **RMSE (test, 63.370 dòng chung):** trung bình chung 1,071, bias (λ = 5) 0,737, ALS explicit (rank 16, reg 0,1) 0,684. ALS bỏ 4,55% số dòng. Trên toàn bộ dòng, "ALS thiếu thì dùng bias" đạt 0,689.
- **Đối chứng 06g (ratings gốc, 182.556 dòng):** ALS 1,673, **kém hơn** trung bình chung 1,578 (−6,0%). Trên dữ liệu mô phỏng, ALS tốt hơn trung bình chung 36,1%.
- **Content (06c):** từ điển 2.862 token, trung bình 15,6 token mỗi món. Tính chính xác 10,9M cặp có độ tương tự khác 0 mất 37 giây. MinHashLSH recall@20 là 0,789 / 0,868 / 0,993 với 3 / 5 / 10 bảng băm.
- **FP-Growth (06d):**
  - mâm cơm: 279.148 phiên, 677 luật, 656 món có món ăn kèm;
  - hit rate@3 trên test: luật 0,219; luật thiếu thì dùng mốc theo nhóm món 0,240; mốc theo nhóm món 0,076; mốc 3 canh phổ biến 0,035;
  - luật nguyên liệu (bỏ gia vị): 36 luật, ví dụ men nở → bột mì (lift 8,7).
- **K-means (06e):** 46.130 user. Silhouette chọn k = 3 (0,227; ARI 0,285; NMI 0,365). Tại k = 8: ARI 0,418, NMI 0,442; các cụm khớp rõ với từng persona (ví dụ cụm "gia đình truyền thống" có 90,6% user thuộc persona đó).
- **Món mới (300 món bị ẩn):** content recall@100 là 10,25%; ALS, popularity, nấu lại và hybrid đều bằng 0.
- **Thời gian trên cụm:** 06a 101 giây, 06b 1.294 giây (ALS implicit dò tham số 870 giây), 06c 200 giây, 06f 662 giây, 06d 34 giây, 06e 256 giây, 06g 61 giây.
- `recs_final`: 50.000 user × 50 món.

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
1. **Đọc câu trả lời cho 3 câu hỏi của bước 06** (`docs/LAST_RUN.md`, mục "Cần người dùng quyết định"):
   - (a) mở rộng lưới ALS (alpha {0,25; 0,5}, rank 128) hay giữ nguyên;
   - (b) cách đưa content vào gợi ý cuối, để có món mới và lý do gợi ý đa dạng hơn;
   - (c) dashboard dùng k = 3 hay k = 8.

   Có sửa thì chạy lại các file liên quan (06b → 06f hoặc 06e), ghi `--local` trước, rồi cập nhật D13.
2. **Bước 07, `src/07_export_mongo.py`:** đọc HDFS, ghi vào MongoDB `vifood` (`.env`: `MONGO_URI`) bằng `pymongo` (đã có trong image), chia lô bằng `foreachPartition` hoặc collect các bảng nhỏ. Các collection dự kiến:
   - `dishes`: `foods` + `dish_features` + `dish_stats` của bước 05 + `image_link`;
   - `recs` (`recs_final`), `similar` (`item_sim` top 20), `companions` (`companion`);
   - `users` (`users` + `user_clusters`), `clusters` (`cluster_profile`);
   - `analysis_*`: 14 bảng của bước 05;
   - `metrics`: `models_metrics.json`.

   Tạo index theo `user_id` và `food_id`. Thêm service `mongo-express` vào compose.
3. **Bước 08:** FastAPI (`api/`) đọc MongoDB, rồi dashboard (`web/`, ECharts).
4. **Kiểm tra `scripts/01_ingest.sh`:** đọc lại script, chưa cần chạy.

## Việc còn treo
- [ ] Kiểm tra tay 100 món trong `data/output/features_check_sample.csv` (Hậu 50, Ngọc 50), điền cột `kiem_tra`, rồi tính độ chính xác cho báo cáo. **Mẫu đã chốt theo hash (24/10), có thể bắt đầu điền.** Chạy lại 03 vẫn ra đúng 100 món này, nhưng file sẽ bị ghi đè nên cần sao lưu cột đã điền trước khi chạy.
- [x] Ratings gốc: đã làm thí nghiệm đối chứng 06g (ALS kém hơn trung bình chung 6%).
- [ ] Ảnh chụp UI cho báo cáo: **để cuối dự án, làm cùng lúc với đo hiệu năng**. Lấy từ History Server http://localhost:18080 (các app 02–06; với 05 thì chụp thêm tab Storage và tab SQL) và HDFS UI (`/data/curated`, `/data/events`, `/data/results/analysis`). `docs/images/` đang trống.
- [x] Chốt mẫu kiểm tra tay theo hash: đã chạy lại 03 trên cụm (24/10).
- [x] HDFS replication: `get_spark()` ghi 2 bản sao, đã `setrep -R 2 /data`, fsck HEALTHY (D12).
- [x] Đã xóa `/data/events/events_csv` (bản cũ). Sinh lại bằng `04 --csv` khi đo hiệu năng.
- [ ] Repo GitHub và `git config`: tạm chưa làm, theo quyết định của nhóm (tác giả commit đang là `Admin`).
- [ ] Ngọc: dựng notebook biểu đồ từ `data/output/analysis/*.json`, làm nền cho trang "Hành vi ăn uống" của dashboard.
- [ ] Notebook hoặc biểu đồ cho bước 06 từ `data/output/models_metrics.json` và `model_*_report.json`: bảng so sánh mô hình, khoảng tin cậy, lưới dò ALS, Silhouette theo k, recall của LSH. Dùng cho trang "Đánh giá mô hình".
- [ ] Thư mục checkpoint của ALS (`hdfs:///tmp/checkpoint`) có thể xóa sau khi chốt bước 06.
- [ ] Nhắn giảng viên về việc dùng dữ liệu hành vi mô phỏng (kế hoạch mục 2.2 khuyến nghị). Chưa rõ đã nhắn hay chưa.
- [ ] Chưa có `mongo-express`, `api` trong `docker-compose.yml` (thêm ở bước 07–08).
- [ ] `README.md`, `requirements.txt`, `data/sample/`: làm lúc nộp bài.

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
