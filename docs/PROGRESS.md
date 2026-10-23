# Tiến độ đồ án

> Cập nhật lần cuối: **24/10/2026**, sau khi chạy xong bước 05 trên cụm (trước khi sửa lỗi "hào" ở bước 03).
> File này là nguồn chính về tiến độ. Mỗi cuối phiên cập nhật bằng `/handoff`.

## Trạng thái các bước

| Bước | Trạng thái | Kết quả chính |
|---|---|---|
| Hạ tầng Docker | ✅ Xong | 8 container: HDFS 1+2, Spark 1+2, Jupyter, MongoDB. Đã chạy test 2 worker. |
| 01 Nạp HDFS | ✅ Xong | 4 CSV trong `/data/raw`. Script `scripts/01_ingest.sh` mới viết, chưa chạy lại trên cụm. |
| 02 Làm sạch (clean v2) | ✅ Xong | `foods` 5.499 món (3.996 giữ id cũ, 1.503 món mới id 4001–5503); `ratings_original` 182.556 dòng |
| 03 Đặc trưng món | ✅ Xong | `dish_features` 5.499 dòng, khớp từng giá trị với lần chạy local. Loại món: mặn 3.448, ngọt 1.236, chay 580, đồ uống 235 |
| 04 Sinh hành vi | ✅ Xong (100%) | 50.000 user (49.815 có hoạt động); **23.164.109 sự kiện**; Parquet 261MB, CSV 1,38GB; chạy 11,5 phút |
| 05 Phân tích hành vi | ✅ Xong | `src/05_analysis.py`, 14 bảng trong `/data/results/analysis` (504KB) và JSON trong `data/output/analysis/`; chạy trên cụm 104 giây |
| 06 Mô hình + đánh giá | ⬜ Chưa | |
| 07 Xuất MongoDB | ⬜ Chưa | |
| 08 FastAPI + dashboard | ⬜ Chưa | |
| Nâng cao: Structured Streaming | ⬜ Chưa | |
| Đo hiệu năng (1 vs 2 worker, 10/50/100%) | ⬜ Chưa | |
| Báo cáo Word + slide | ⬜ Chưa | |

### Số liệu bước 05 (bản chạy 24/10, **trước** khi sửa lỗi "hào"; sẽ thay sau khi chạy lại)
- Kiểm tra: đọc đủ 23.164.109 sự kiện, tổng của hai khối `cube_cook` và `monthly` khớp với bảng gốc. Bảng cơ sở chiếm 237MB trong cache.
- Phễu theo cặp user–món: 11,5% cặp đã xem được lưu, 14,1% được nấu; 45% cặp đã nấu được chấm. Tỷ lệ user: lưu 98,2%, nấu 99,0%, chấm 94,5%.
- Thời gian: lượt nấu cuối tuần gần gấp đôi ngày thường, đỉnh là CN 17–19h. Món Tết chiếm 18,6% lượt nấu tháng 2, các tháng khác khoảng 3%.
- Lift: miền Trung với món cay 1,35; nhóm 18–24 tuổi với đồ uống 2,05; nhóm 45+ với canh/súp 1,35; cuối tuần với lẩu 1,54.
- Đuôi dài: Gini lượt nấu 0,73; 10% món đầu chiếm 62,6% lượt nấu. "Canh hào thanh mát" chiếm 4,2% lượt nấu, đứng đầu cả 3 bữa.
- Tỷ lệ nấu lại cùng một món: 19,9% số cặp đã nấu.

### Số liệu bước 04 (dùng cho bước 05–06)
- Sự kiện: view 18.627.223 · cook 2.371.657 · favorite 1.396.511 · rate 768.718.
- Tỷ lệ chuyển đổi: favorite/view 7,5% · cook/view 12,7% · rate/cook 32,4%.
- Rating: trung bình 3,79, độ lệch chuẩn 1,08, có 47.078 user từng chấm. Mật độ ma trận user × món: 4,4%.
- Số user có hoạt động: tháng 08/2026 (validation) 43.010, tháng 09/2026 (test) 43.688.
- Phiên nấu kiểu "mâm cơm" (từ 2 món trở lên): 15,2%.
- Kiểm tra quy luật (theo món được nấu):
  - Persona ăn chay: 100% món chay.
  - Persona mê hải sản: 62,6% món hải sản.
  - Persona bận rộn: 92,3% món nhanh.
  - Persona thích cay/nhậu: 67% món cay.
  - Món Tết: khoảng 4% vào ngày thường, 16–22% vào tháng 2.
- Chạy thử 10% ở local: ALS explicit RMSE 0,771, tốt hơn baseline bias (0,801) và trung bình chung (1,078). ALS implicit P@10 0,024, gấp khoảng 2,5 lần popularity (0,009).

## Việc tiếp theo (theo thứ tự)
1. **Sửa lỗi "hào" (đang làm ngay sau commit này):**
   - Ở `03_features.py`, thêm vào `CONFUSING` hai luật "dầu hào" → "gia vị" và "su hào" → "rau", rồi thêm "hào" vào nhóm hải sản.
   - Ở `04_simulate.py`, kẹp `quality` vào [-2,5; 2,5].
   - Chạy lại trên cụm theo thứ tự 03 → 04 (100%) → 05, rồi sinh lại bản 10% ở local. Nhớ sao lưu và khôi phục file xuất của bản 100%.
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
  - phát hiện "Canh hào thanh mát" bị gán `main_protein` là "đậu hũ/chay" và chiếm 4,2% lượt nấu, nên phải sửa 03 và 04.
