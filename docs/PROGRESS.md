# Tiến độ đồ án

> Cập nhật lần cuối: **24/10/2026**, sau khi viết bản đề xuất thiết kế bước 06 vào `docs/LAST_RUN.md` (đang chờ góp ý).
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
| 06 Mô hình + đánh giá | 🟡 Thiết kế | Bản đề xuất nằm trong `docs/LAST_RUN.md`, chờ chat góp ý và người dùng chốt 7 câu hỏi. Chưa viết code |
| 07 Xuất MongoDB | ⬜ Chưa | |
| 08 FastAPI + dashboard | ⬜ Chưa | |
| Nâng cao: Structured Streaming | ⬜ Chưa | |
| Đo hiệu năng (1 vs 2 worker, 10/50/100%) | ⬜ Chưa | |
| Báo cáo Word + slide | ⬜ Chưa | |

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
1. **Bước 06: THIẾT KẾ TRƯỚC, CHƯA VIẾT CODE.** ✅ Đã ghi bản đề xuất vào `docs/LAST_RUN.md` (24/10). **Việc tiếp theo:** đọc góp ý của chat và câu trả lời cho 7 câu hỏi (replication, `events_csv`, giả lập món mới, giao thức, trọng số implicit và chuẩn hóa hybrid, tên module, 06g), ghi bản đã chốt thành D12, rồi mới viết code theo thứ tự 06a → 06b → 06c → 06f → 06d → 06e → 06g. Yêu cầu gốc: ghi bản đề xuất vào `docs/LAST_RUN.md` (mục "Đã làm" là bản thiết kế, mục "Cần người dùng quyết định" là các điểm cần chốt). Chat claude.ai sẽ góp ý, sau khi chốt mới viết code. Bản thiết kế phải có:
   - **Chia file:** ví dụ `src/06_*.py` theo từng nhóm mô hình, phần chung (chia dữ liệu, hàm độ đo) để ở đâu, file nào ghi gì lên `/data/results/models/...`, report JSON nào.
   - **Chia dữ liệu theo thời gian:** train 10/2025–07/2026, validation 08/2026, test 09/2026. Nêu cách xử lý user hoặc món chỉ có trong validation/test, cách định nghĩa "món liên quan" (relevant) cho độ đo xếp hạng, và có loại món user đã tương tác trong train khỏi danh sách gợi ý hay không.
   - **Cold-start:** user mới (28% đăng ký trong năm), món ít tương tác; chuyển sang content-based hoặc popularity như thế nào.
   - **Kỹ thuật Spark và tham số cho từng mô hình:**
     - baseline random và popularity;
     - ALS explicit và implicit (trọng số view/favorite/cook, dải rank, regParam, alpha; TrainValidationSplit hay tự dò trên validation);
     - content-based (tokenizer tiếng Việt, HashingTF/IDF, LSH);
     - FP-Growth (nguyên liệu, và "mâm cơm" theo session; minSupport, minConfidence);
     - K-means (đặc trưng user, chọn k bằng Silhouette, ARI so với `users_truth`);
     - hybrid (trọng số α, β, γ, dò trên validation).
   - **Bảng độ đo:** RMSE, MAE; P@K, R@K, NDCG@K, MAP@K với K = 5, 10; coverage, diversity, novelty; Silhouette, ARI. Ghi rõ độ đo nào áp cho mô hình nào, đo trên tập nào.
   - **Thứ tự ưu tiên** và thời gian chạy ước tính trên cụm (4 core, 3GB mỗi worker); việc gì làm ở `--local` 10% trước.
   - Thí nghiệm đối chứng ALS trên ratings gốc: đưa vào thiết kế như một tùy chọn (D06).
2. **Kiểm tra `scripts/01_ingest.sh`:** đọc lại script, chưa cần chạy vì HDFS đã có dữ liệu.

## Việc còn treo
- [ ] Kiểm tra tay 100 món trong `data/output/features_check_sample.csv` (Hậu 50, Ngọc 50), điền cột `kiem_tra`, rồi tính độ chính xác cho báo cáo. **Mẫu đã chốt theo hash (24/10), có thể bắt đầu điền.** Chạy lại 03 vẫn ra đúng 100 món này, nhưng file sẽ bị ghi đè nên cần sao lưu cột đã điền trước khi chạy.
- [ ] Ratings gốc: đã **tạm gác lại**. Cần quyết định có chạy thí nghiệm đối chứng ALS hay không (khoảng 15 phút công, kế hoạch khuyến nghị có).
- [ ] Ảnh chụp UI cho báo cáo: **để cuối dự án, làm cùng lúc với đo hiệu năng**. Lấy từ History Server http://localhost:18080 (các app 02–06; với 05 thì chụp thêm tab Storage và tab SQL) và HDFS UI (`/data/curated`, `/data/events`, `/data/results/analysis`). `docs/images/` đang trống.
- [x] Chốt mẫu kiểm tra tay theo hash: đã chạy lại 03 trên cụm (24/10).
- [ ] HDFS: các file do Spark ghi có replication 3, cụm chỉ có 2 datanode nên thiếu 64 bản sao. Không mất block nào. Đề xuất sửa trong LAST_RUN (câu hỏi 1).
- [ ] `/data/events/events_csv` (1,4GB) đã cũ so với events hiện tại (LAST_RUN, câu hỏi 2).
- [ ] Repo GitHub và `git config`: tạm chưa làm, theo quyết định của nhóm (tác giả commit đang là `Admin`).
- [ ] Ngọc: dựng notebook biểu đồ từ `data/output/analysis/*.json`, làm nền cho trang "Hành vi ăn uống" của dashboard.
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
