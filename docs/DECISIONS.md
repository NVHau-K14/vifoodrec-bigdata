# Các quyết định thiết kế

Ghi lại **vì sao** chọn cách làm. Mỗi quyết định có ngày, lý do và hệ quả.
Nội dung dùng trực tiếp cho báo cáo và phần trả lời phản biện. Quyết định mới thêm vào cuối file.

---

## D01. Chỉ dùng ViFoodRec, bỏ hướng ghép Food.com (trước 23/10/2026)
Nhóm từng thử ghép Food.com (tiếng Anh) với ViFoodRec. Hai bộ khác ngôn ngữ, khác cấu trúc nên phát sinh lỗi liên tục, hướng này đã hủy. Không dùng lại container hay code của hướng cũ.

## D02. Hướng C: món ăn thật + hành vi mô phỏng (23/10)
**Bối cảnh:** ratings gốc của ViFoodRec là nhiễu ngẫu nhiên:
- 11 mức điểm phân bố đều;
- điểm trung bình của mọi user đều khoảng 2,5;
- chia đôi dữ liệu thì tương quan giữa hai nửa là −0,03.

Dinh dưỡng cũng là số ngẫu nhiên: calories không tương quan với fat hay protein. Dữ liệu chỉ khoảng 20MB và 101 user.

**Quyết định:** giữ phần văn bản thật (tên món, nguyên liệu, cách làm, tags, ảnh) làm danh mục món. Tự sinh dữ liệu hành vi có quy luật ở quy mô lớn, dựa trên đặc trưng thật của món.

**Hệ quả:**
- Báo cáo phải ghi rõ đâu là dữ liệu thật, đâu là mô phỏng.
- Có "sự thật gốc" (persona) để kiểm chứng mô hình, ví dụ đo ARI cho K-means.
- Dinh dưỡng chỉ dùng để lọc và minh họa.

## D03. Hạ tầng: HDFS thật + Spark Standalone trên Docker (23/10)
Cụm gồm 1 NameNode + 2 DataNode (replication 2), 1 master + 2 worker (2 core, 3GB mỗi worker), Jupyter làm driver, MongoDB cho dashboard. Spark đọc và ghi qua `hdfs://namenode:8020` chứ không đọc file local, để đáp ứng tiêu chí lưu trữ và xử lý phân tán.

Image Spark (`vifood-spark:4.2.0`) dùng chung cho master, worker và jupyter để cùng phiên bản Python. Dashboard viết bằng HTML/CSS/JS + ECharts, có FastAPI, **không dùng Streamlit**.

## D04. Làm sạch lại từ dữ liệu thô: clean v2 (23/10)
**Không dùng `foods.csv` của tác giả làm dữ liệu chính**, vì bước làm sạch gốc gây lỗi:
- 2.842/4.000 món bị chèn sai chữ "muỗng" (ví dụ "muỗnguỗng");
- gộp mất phân biệt muỗng canh (M) với muỗng cà phê (m);
- 263 món mất dấu thanh vì xóa dấu tổ hợp thay vì chuẩn hóa NFC;
- chỉ giữ 4.000/5.509 dòng;
- 4 món bị nhân đôi;
- tên món viết hoa lỗi ("SữA Chua TráI Cây").

**Clean v2** (`src/02_clean.py`):
- **Món và id:** 5.499 món. 3.996 món giữ `food_id` cũ, ghép theo `image_link` và tên món. 1.503 món mới mang id 4001–5503. Riêng "Bánh xèo Nhật Bản" có 2 công thức cùng tên: chọn bản giống bản gốc nhất bằng khoảng cách Levenshtein trên phần cách làm.
- **Món bị nhân đôi:** các id 1154–1157 gộp về id nhỏ hơn.
- **Ratings:** chuyển về id chính. User chấm cả hai bản thì lấy trung bình, làm tròn 0,5. Bỏ 47 dòng có `foodId = 4000`. Còn lại 182.556 dòng.
- **Cột mới:**
  - `ingredient_list`: mảng nguyên liệu, đã bỏ định lượng và thương hiệu;
  - `preparation`, `serving_tips`, `tips`: chỉ món MNMN có;
  - `source`, `source_stt`, `in_original_clean`;
  - `dup_name_group`: 372 dòng trùng tên nhưng khác công thức, giữ cả hai.
- **Khẩu phần:** "0 người" và "150 người" được đặt rỗng (8 món).
- **Giữ nguyên nhưng không đáng tin:** dinh dưỡng, `cooking_time`, `dish_type`. Riêng `dish_type` được sửa ở D05.

## D05. Đặc trưng món bằng từ điển + luật ưu tiên (23/10)
Không có nhãn để huấn luyện, nên trích thuộc tính bằng từ điển từ khóa, chỉ dùng hàm Spark (`regexp_instr`, `rlike`), không dùng UDF.

**Luật ưu tiên:**
- Tìm trong tên món trước, rồi mới tới nguyên liệu. Nếu tên có nhiều từ khóa, từ khóa xuất hiện sớm nhất thắng.
- Trước khi so khớp, thay các cụm dễ nhầm: "trứng gà" → trứng, "nấm đùi gà" → nấm, "hạt nêm vị gà" → gia vị, "mắm tôm" → mắm…
- "thịt", "bì", "lòng", "sườn" không rõ loại thì tính là heo, nhưng xét sau cùng.

**Luật cho từng cột:**
- **`main_protein`:**
  - món ngọt và đồ uống → "không";
  - món mặn không có đạm → "rau củ".
- **Chay:** tên hoặc tags có "chay", hoặc không có nguyên liệu động vật (kể cả nước mắm và trứng).
- **`is_quick`:** xếp hạng riêng trong từng nguồn, vì Cooky viết cách làm dài hơn MNMN nhiều. Món nhanh = nằm trong top 40% ít chữ nhất và top 50% ít nguyên liệu nhất.
- **`season`:** người dùng từng định bỏ, sau đó quyết định **giữ**. Mùa "nóng" chỉ gán cho đồ uống, chè/tráng miệng, gỏi/salad, hoặc tên món nói rõ (giải nhiệt, canh chua…).

**Kết quả:**
- So với nhãn gốc (theo `features_report.json` trên cụm): có 1.217 món ghi "Món mặn" thực ra là món ngọt, 381 món là món chay, 235 món là đồ uống. Ngoài ra 19 món ghi "Món chay" thực ra là món ngọt.
- Sai sót còn lại được đo bằng 100 món kiểm tra tay.

## D06. Ratings gốc: tạm gác lại (23/10)
Không dùng ratings gốc cho phân tích hay gợi ý. Có thể chạy một lần thí nghiệm đối chứng (ALS trên ratings gốc, dự kiến RMSE khoảng 1,58, ngang đoán ngẫu nhiên) để trả lời câu hỏi "sao không dùng ratings có sẵn". Chưa chốt có làm hay không.

## D07. Thiết kế bộ sinh hành vi (23/10)
- **Phạm vi:** 01/10/2025–30/09/2026, có Tết 17/02/2026. 50.000 user, seed 2026.
- **Persona:** 8 persona, mỗi user có 1 persona chính và 1 persona phụ (trọng số 0,5). Loại các cặp mâu thuẫn chay + hải sản và chay + nhậu. Thuộc tính user: vùng miền (Bắc 35%, Trung 20%, Nam 45%), nhóm tuổi, giới tính và khung bữa ưa thích phụ thuộc persona.
- **Điểm hợp khẩu vị** là tổng các thành phần:
  - trọng số persona (cộng ảnh hưởng vùng miền, tuổi, nhiễu cá nhân 0,35) nhân với đặc trưng món;
  - 0,7 × tích vector ẩn k=8. Đây là thành phần chỉ lọc cộng tác học được, giúp hybrid có ý nghĩa;
  - −0,45 × log(hạng phổ biến), theo phân phối Zipf;
  - 0,3 × chất lượng ẩn của món;
  - ngữ cảnh: bữa, mùa theo vùng, cuối tuần hay ngày thường.
- **Chọn món xem:** lấy mẫu softmax không lặp (Gumbel top-k).
- **Phễu hành vi:**
  - lưu món: xác suất tăng theo độ hợp khẩu vị;
  - phiên nấu: xác suất phụ thuộc persona, cao hơn vào cuối tuần;
  - 25% số lần nấu là nấu lại món đã lưu;
  - "mâm cơm" trưa/tối: món chính + canh (50% là canh quen cố định của món đó) + rau (35%). Mục đích là để FP-Growth có luật tìm ra.
- **Rating:** mỗi món chỉ chấm một lần, sau khi nấu. Điểm = 3,7 + 1,0·(z − 2,2) + 0,4·chất lượng + độ khắt khe của user + nhiễu 0,4, làm tròn 0,5, trong khoảng [0,5; 5].
  - Lần đầu viết với hệ số 0,6·z thì ALS thua baseline bias. Sau khi tăng thành phần khẩu vị cá nhân, ALS mới thắng.
- **Mùa theo vùng:**
  - lạnh: Bắc tháng 11–2, Trung tháng 11–1, Nam tháng 12–1;
  - nóng: Bắc tháng 5–8, Trung tháng 4–8, Nam tháng 3–6;
  - cửa sổ Tết: 27/01–23/02.

  Món đặc sản vùng miền và món nước ngoài nhận dạng theo tên món.
- **Sinh phân tán:** dùng `mapInPandas` trên worker. Seed theo cặp (seed, user_id) nên kết quả giống hệt dù đổi số partition (đã kiểm tra).
- **Lưu trữ:** `users_truth` lưu riêng, mô hình không được dùng. Sự kiện ghi Parquet, chia partition theo tháng.

## D08. Cách làm việc với AI (23/10)
- Thư mục dự án là **nơi lưu chính** về tiến độ và quyết định: `CLAUDE.md`, `docs/PROGRESS.md`, `docs/DECISIONS.md`, `docs/DATA_DICTIONARY.md`. Ghi chú trên claude.ai Project chỉ trỏ về đây.
- Từ bước 05 làm bằng **tab Code (Local)** của Claude desktop. Ở đó Claude chạy được `docker exec` trên máy, tự đọc lỗi và kiểm tra kết quả.
- Dùng Git: commit sau mỗi bước, repo GitHub riêng tư. Dữ liệu lớn không đưa lên Git.
- Tài liệu viết tiếng Việt có dấu, chú thích trong code viết không dấu.

## D09. Cách làm bước 05: phân tích hành vi (23/10)
- **Phạm vi dữ liệu:** dùng cả 12 tháng, vì bước này chỉ để mô tả. Bước 06 không lấy bảng nào trong `/data/results/analysis` làm đặc trưng hay baseline, vì các bảng đó chứa cả tháng validation và test.
- **Cách xử lý:**
  - Bảng sự kiện chỉ đọc một lần, sau đó join broadcast với `users` và persist `MEMORY_AND_DISK`.
  - Tổng hợp trước, join sau: gom sự kiện theo `food_id` thành 2 khối nhỏ, `cube_cook` (bữa × loại ngày × vùng × tuổi × món) và `monthly` (tháng × vùng × món). Sau đó mới join đặc trưng món, nên phép join chạy trên vài trăm nghìn dòng chứ không phải 23 triệu.
  - Một phần viết bằng Spark SQL: heatmap, top món theo bữa, phễu (`ROLLUP`). Phần còn lại dùng DataFrame API.
- **Lift thay cho đếm thô:** so sánh giữa các nhóm (bữa, ngày thường/cuối tuần, vùng, tuổi) bằng lift = tỷ trọng trong nhóm / tỷ trọng chung, tính theo lượt nấu. Đếm thô thì nhóm đông người luôn thắng, nên không so sánh được.
- **Phễu tính theo cặp user–món,** bên cạnh phễu theo sự kiện. Một món có thể được xem nhiều lần, nên tỷ lệ cook/view tính theo sự kiện không phải tỷ lệ chuyển đổi thật.
- **Top món theo bữa có 2 kiểu xếp hạng:**
  - theo lượt nấu: món phổ biến chung, bữa nào cũng dẫn đầu;
  - theo lift: món đặc trưng của bữa, chỉ xét 200 món nấu nhiều nhất của bữa đó.
- **Nguyên liệu:** đánh dấu gia vị bằng một danh sách tay (`SEASONINGS`) để dashboard lọc bỏ được muối, đường, dầu ăn…

## D10. Sửa nhận dạng "hào" ở bước 03, kẹp `quality` ở bước 04 (24/10)
- **Lỗi phát hiện ở bước 05:** món "Canh hào thanh mát" (id 511) bị gán `main_protein` là "đậu hũ/chay", lấy theo "nấm kim châm" trong nguyên liệu. Nguyên nhân là từ điển hải sản có "hàu" nhưng không có "hào". `is_vegetarian` của món này vẫn đúng là False, nhờ nguyên liệu "hào sữa thịt" có chữ "thịt".
- **Cách sửa ở bước 03:** không thêm "hào" thẳng vào từ điển. Trước tiên thêm hai luật `CONFUSING`, "dầu hào" → "gia vị" và "su hào" → "rau", rồi mới thêm "hào" vào nhóm hải sản. Nhờ vậy các món dùng dầu hào hoặc su hào không bị coi là hải sản hay mất nhãn chay.
  - Kết quả so với bản cũ: **chỉ 1 món đổi `main_protein`** (món 511, chuyển sang "hải sản"), 0 món đổi `is_vegetarian`. "Thịt Kho Su Hào", "Cà Tím Sốt Dầu Hào", "Khổ Qua Xào Dầu Hào Chay" giữ nguyên.
  - Tác dụng phụ: `method_words` được đếm sau `CONFUSING`, nên 27 món có "su hào" trong cách làm ngắn đi 1–5 chữ. Vì `is_quick` xếp hạng trong từng nguồn, 1 món khác là "Bắp bò nhúng mẻ" (id 718) đổi `is_quick` từ False sang True. Nếu muốn tránh, có thể thay "su hào" bằng "rau củ" (giữ nguyên số chữ).
  - Mẫu kiểm tra tay `features_check_sample.csv` giữ bản cũ. Bước 03 khi chạy lại sẽ bốc mẫu khác, vì `rand(42)` phụ thuộc cách chia partition. Bản cũ không chứa món 511 hay 718 nên các giá trị trong đó vẫn đúng.
- **Ở bước 04:** kẹp `quality` vào [-2,5; 2,5] ngay sau khi sinh (`CFG.quality_clip`). Bước này không dùng thêm số ngẫu nhiên nên các giá trị ngẫu nhiên khác giữ nguyên. Có 78 món bị kẹp, trong đó "Canh hào" giảm từ 3,24 xuống 2,5.
- **Kết quả: chưa đạt mục tiêu.** "Canh hào" vẫn đứng đầu với **5,17%** lượt nấu (bản cũ 4,21%).
  - Lý do: món vẫn có hạng phổ biến 1/5.499, vì `pop_key` = 0,6·quality + 0,8·nhiễu.
  - Khi đã là "hải sản", persona "mê hải sản" chọn món này nhiều hơn.
  - 81% lượt nấu của món là phiên nấu 1 món; phần đến từ "mâm cơm" chỉ khoảng 8% số canh trong mâm.
  - Muốn hết áp đảo thì phải sửa phần độ phổ biến ở bước 04. Việc này chưa quyết.

## D11. Làm phẳng phần đầu Zipf, bật History Server, mẫu kiểm tra theo hash (24/10)
- **Độ phổ biến ở bước 04:** `pop_term = −0,45·log(hạng + zipf_offset)` với `zipf_offset = 30` (trước đây là `log(hạng)`). Khi offset bằng 0, món hạng 1 hơn món hạng 30 tới 0,45·log 30 ≈ 1,5 điểm, nên chiếm áp đảo. Với offset 30, phần đầu phân phối phẳng hơn nhưng đuôi dài vẫn giữ.

  | offset | Món đứng đầu (% lượt nấu) | Gini lượt nấu | Ghi chú |
  |---|---|---|---|
  | 0 | 5,37% | 0,741 | chat thử ở quy mô 5% |
  | 10 | 2,20% | 0,724 | chat thử ở quy mô 5% |
  | 30 | 1,48% | 0,711 | chat thử ở quy mô 5%; ALS RMSE 0,807 so với bias 0,834; P@10 0,022 so với popularity 0,009 |
  | 0 (bản 100% trước đó) | 5,17% | 0,732 | chạy trên cụm (D10) |
  | **30 (bản 100% hiện tại)** | **1,44%** | **0,698** | chạy trên cụm 24/10, 23.205.143 sự kiện |

  Tác dụng phụ ở bản 100%: rating trung bình giảm từ 3,78 xuống 3,705, vì món phổ biến (có `quality` cao) không còn chiếm quá nhiều lượt chấm. Persona mê hải sản: 65,2% món hải sản (trước đó 67,7%).
- **Spark History Server:** `get_spark()` bật `spark.eventLog.enabled`, ghi vào `logs/spark-events/` trong thư mục dự án. Thư mục này mount ở mọi container và đã thêm vào `.gitignore`. Service `spark-history` (cổng 18080) đọc thư mục đó. Đặt cấu hình trong code thay vì `spark-defaults.conf` để không phải build lại image, và chạy `--local` cũng có log. Mục đích: chụp ảnh UI và đo hiệu năng sau khi job đã xong, không cần canh lúc job đang chạy ở cổng 4040.
- **Mẫu kiểm tra tay ở bước 03:** chọn theo `xxhash64(food_id, 42)` thay vì `rand(42)`. Đã kiểm tra: chia 1 hay 7 partition đều ra đúng 100 món như nhau. Chưa chạy lại 03, nên `features_check_sample.csv` hiện vẫn là mẫu cũ (`rand(42)`). Lần chạy 03 tiếp theo sẽ ghi đè bằng mẫu theo hash, gồm 100 món khác.
- **Ảnh chụp UI:** để cuối dự án, chụp cùng lúc với phần đo hiệu năng (lấy từ History Server).
