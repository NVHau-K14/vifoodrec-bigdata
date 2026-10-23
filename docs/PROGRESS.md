# Tiến độ đồ án

> Cập nhật lần cuối: **24/10/2026**, sau khi sửa lỗi "hào" (03), kẹp `quality` (04) và chạy lại 03 → 04 → 05 trên cụm.
> File này là nguồn chính về tiến độ. Mỗi cuối phiên cập nhật bằng `/handoff`.

## Trạng thái các bước

| Bước | Trạng thái | Kết quả chính |
|---|---|---|
| Hạ tầng Docker | ✅ Xong | 8 container: HDFS 1+2, Spark 1+2, Jupyter, MongoDB. Đã chạy test 2 worker. |
| 01 Nạp HDFS | ✅ Xong | 4 CSV trong `/data/raw`. Script `scripts/01_ingest.sh` mới viết, chưa chạy lại trên cụm. |
| 02 Làm sạch (clean v2) | ✅ Xong | `foods` 5.499 món (3.996 giữ id cũ, 1.503 món mới id 4001–5503); `ratings_original` 182.556 dòng |
| 03 Đặc trưng món | ✅ Xong (sửa 24/10) | `dish_features` 5.499 dòng, khớp từng giá trị với lần chạy local. Loại món: mặn 3.448, ngọt 1.236, chay 580, đồ uống 235. Đã sửa "hào" (D10) |
| 04 Sinh hành vi | ✅ Xong (100%, chạy lại 24/10) | 50.000 user (49.815 có hoạt động); **23.141.780 sự kiện**; Parquet 260MB; chạy 9,5 phút. Món đứng đầu vẫn áp đảo (D10) |
| 05 Phân tích hành vi | ✅ Xong | `src/05_analysis.py`, 14 bảng trong `/data/results/analysis` và JSON trong `data/output/analysis/`; chạy trên cụm 106 giây |
| 06 Mô hình + đánh giá | ⬜ Chưa | |
| 07 Xuất MongoDB | ⬜ Chưa | |
| 08 FastAPI + dashboard | ⬜ Chưa | |
| Nâng cao: Structured Streaming | ⬜ Chưa | |
| Đo hiệu năng (1 vs 2 worker, 10/50/100%) | ⬜ Chưa | |
| Báo cáo Word + slide | ⬜ Chưa | |

### Số liệu bước 05 (chạy lại 24/10, sau khi sửa "hào" và kẹp `quality`)
- Kiểm tra: đọc đủ 23.141.780 sự kiện, tổng của hai khối `cube_cook` và `monthly` khớp với bảng gốc. Bảng cơ sở chiếm 237MB trong cache. Chạy trên cụm 106 giây.
- Phễu theo cặp user–món: 11,5% cặp đã xem được lưu, 14,0% được nấu; 45,0% cặp đã nấu được chấm. Tỷ lệ user: lưu 98,2%, nấu 99,0%, chấm 94,5%.
- Thời gian: lượt nấu cuối tuần gần gấp đôi ngày thường, đỉnh là CN 17–19h. Món Tết chiếm 18,9% lượt nấu tháng 2, các tháng khác khoảng 3%.
- Lift: miền Trung với món cay 1,35; nhóm 18–24 tuổi với pha/xay 2,04; nhóm 45+ với canh/súp 1,34; cuối tuần với lẩu 1,55.
- Đuôi dài: Gini lượt nấu 0,73; 10% món đầu chiếm 62,5% lượt nấu. **"Canh hào thanh mát" vẫn chiếm 5,17% lượt nấu** (bản cũ 4,21%), xem D10.
- Tỷ lệ nấu lại cùng một món: 19,9% số cặp đã nấu.

### Số liệu bước 04 (bản 100% chạy lại 24/10, dùng cho bước 05–06)
- Sự kiện: view 18.621.619 · cook 2.366.696 · favorite 1.390.570 · rate 762.895.
- Tỷ lệ chuyển đổi (theo sự kiện): favorite/view 7,5% · cook/view 12,7% · rate/cook 32,2%.
- Rating: trung bình 3,78, độ lệch chuẩn 1,07, có 47.095 user từng chấm. Mật độ ma trận user × món: 4,4%.
- Số user có hoạt động: tháng 08/2026 (validation) 43.010, tháng 09/2026 (test) 43.688.
- Phiên nấu kiểu "mâm cơm" (từ 2 món trở lên): 15,0%.
- Kiểm tra quy luật (theo món được nấu):
  - Persona ăn chay: 100% món chay.
  - Persona mê hải sản: 67,7% món hải sản.
  - Persona bận rộn: 92,3% món nhanh.
  - Persona thích cay/nhậu: 68,1% món cay.
- Parquet 260MB, chạy 9,5 phút trên cụm. Bản 10% ở local (`data/hdfs_local`): 5.000 user, 2.285.167 sự kiện.
- Chạy thử 10% ở local (bản **trước** 24/10, cần chạy lại ở bước 06): ALS explicit RMSE 0,771, tốt hơn baseline bias (0,801) và trung bình chung (1,078). ALS implicit P@10 0,024, gấp khoảng 2,5 lần popularity (0,009).

## Việc tiếp theo (theo thứ tự)
1. **Quyết định cách xử lý món áp đảo** ("Canh hào thanh mát" chiếm 5,17% lượt nấu, xem D10). Nếu sửa thì sửa phần độ phổ biến ở `04_simulate.py`, ví dụ:
   - làm phẳng phần đầu của Zipf (dùng hạng tối thiểu 10 trong `pop_term`); hoặc
   - giảm hệ số của `quality` trong `pop_key`.

   Sau đó chạy lại 04 (100%) → 05 và sinh lại bản 10%. Nhớ sao lưu và khôi phục file xuất của bản 100%: `data/processed/users.*`, `users_truth.csv`, `data/output/simulate_*.json`, `events_sample.csv`.
2. **Tạo repo GitHub riêng tư và mời Ngọc.** Trước khi push, đặt `git config user.name/user.email` (hiện tác giả commit đang là `Admin`).
3. **Kiểm tra `scripts/01_ingest.sh`:** đọc lại script, chưa cần chạy vì HDFS đã có dữ liệu.
4. Bước 06: baseline (random, popularity), ALS explicit và implicit, content-based (TF-IDF + LSH), FP-Growth, K-means, hybrid.
   Chia theo thời gian: train 10/2025–07/2026, validation 08/2026, test 09/2026.

## Việc còn treo
- [ ] Kiểm tra tay 100 món trong `data/output/features_check_sample.csv` (Hậu 50, Ngọc 50), điền cột `kiem_tra`, rồi tính độ chính xác cho báo cáo.
- [ ] Ratings gốc: đã **tạm gác lại**. Cần quyết định có chạy thí nghiệm đối chứng ALS hay không (khoảng 15 phút công, kế hoạch khuyến nghị có).
- [ ] Ảnh chụp cho báo cáo: `docs/images/` đang trống. Cần chụp Spark UI (các app 02, 03, 04, 05; với 05 thì chụp thêm tab Storage và tab SQL) và HDFS UI (`/data/curated`, `/data/events`, `/data/results/analysis`).
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
