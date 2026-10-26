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
- **Mẫu kiểm tra tay ở bước 03:** chọn theo `xxhash64(food_id, 42)` thay vì `rand(42)`. Đã kiểm tra: chia 1 hay 7 partition đều ra đúng 100 món như nhau. Ngày 24/10 đã chạy lại 03 trên cụm để ghi mẫu theo hash. `dish_features` giống hệt bản trước (schema trùng, `exceptAll` ra 0 dòng ở cả hai chiều), nên không cần chạy lại 04 và 05.
- **Ảnh chụp UI:** để cuối dự án, chụp cùng lúc với phần đo hiệu năng (lấy từ History Server).

## D12. Thiết kế bước 06 đã chốt (24/10)
Bản đề xuất nằm trong LAST_RUN (commit `c276f42`), chat góp ý 9 điểm (a–i), người dùng trả lời 7 câu hỏi. Bản chốt như sau.

**Hạ tầng (làm ngay):**
- `get_spark()` đặt `spark.hadoop.dfs.replication=2`. Đã chạy `hdfs dfs -setrep -R -w 2 /data`; fsck: HEALTHY, thiếu 0 bản sao.
- Đã xóa `/data/events/events_csv` (bản cũ). Khi đo hiệu năng sẽ sinh lại bằng `04 --csv`.

**File:** module dùng chung `src/rec_common.py`, cùng các file `06a_split`, `06b_als`, `06c_content`, `06f_hybrid`, `06d_fpgrowth`, `06e_kmeans`, `06g_control`. Viết và chạy theo thứ tự đó, mỗi file chạy `--local` (bản 10%) trước rồi mới lên cụm.
- Bảng trung gian ghi vào `/data/results/models/<bảng>_<view>`.
- Model Spark lưu vào `/data/models/`.
- Report: `data/output/model_<x>_report.json`.

**Hai "view" dữ liệu (sửa đổi a):**
| view | lịch sử (dùng để fit) | tháng đánh giá | dùng cho |
|---|---|---|---|
| `val` | train: 10/2025–07/2026 | 08/2026 | dò tham số |
| `test` | train + val: 10/2025–08/2026 | 09/2026 | kết quả cuối, gợi ý cuối cho MongoDB |

- 06a ghi riêng cho từng view mọi thứ phụ thuộc lịch sử: ma trận implicit, ratings, `user_groups`, các bảng popularity, đặc trưng user, tập đáp án.
- **Nhóm user** được định nghĩa một lần trong 06a, theo số sự kiện trong lịch sử của view: **lạnh** = 0, **ít** = 1–19, **ấm** ≥ 20. Luật cold-start của hybrid dùng đúng nhóm này. Số user lạnh ở test được tính lại theo train + val.

**Giao thức đánh giá (câu hỏi 4, sửa đổi b, g):**
- Món liên quan = các món user nấu trong tháng đánh giá. User được đánh giá = user có ít nhất 1 lượt nấu trong tháng đó.
- **Mọi mô hình xếp hạng chấm trên cùng tập user.** Mô hình không có gợi ý cho một user thì user đó nhận danh sách rỗng, điểm bằng 0. Hybrid có luật dùng popularity thay, ghi rõ.
- Báo cáo theo nhóm: tất cả user, ấm, ít, lạnh. Bảng phụ chỉ gồm user ấm.
- Bảng chính không loại món đã gặp. Biến thể "khám phá" bỏ món user đã nấu trong lịch sử ra khỏi cả danh sách gợi ý lẫn tập đáp án; user không còn món đáp án nào thì bị loại khỏi biến thể này.
- Độ đo P@K, R@K, NDCG@K, MAP@K (K = 5, 10) tính **cho từng user** bằng hàm mảng của Spark SQL (`transform`, `aggregate`). Kết quả được kiểm tra lại với `RankingEvaluator`. MAP@K chia cho min(K, số món đáp án), giống Spark.
- Lưu NDCG@10 của từng user. Các so sánh chính báo **khoảng tin cậy 95%** của hiệu số ghép cặp theo user: trung bình ± 1,96·sd/√n.
- **RMSE/MAE** báo trên **phần dòng chung**, tức các dòng mà mọi mô hình đều dự đoán được (ALS bỏ user/món không có trong lịch sử). Có thêm biến thể "ALS, thiếu thì dùng bias" trên toàn bộ dòng.
- Ngoài độ chính xác: coverage, novelty (−log₂ tỷ trọng lượt nấu trong lịch sử), diversity (1 − Jaccard trung bình giữa các cặp món trong top 10, dùng tập token của 06c). Tất cả tính trên test ở 06f.

**06b — baseline và ALS (sửa đổi e, câu hỏi 5):**
- Baseline: random (chọn món bằng hash, có seed), popularity chung, **popularity 2 tháng cuối của lịch sử**, popularity theo (vùng, nhóm tuổi), **"nấu lại"** (món user đã nấu nhiều nhất trong lịch sử, thiếu thì bổ sung bằng popularity chung).
- Rating: trung bình chung, bias baseline (λ ∈ {5, 10, 25}), ALS explicit (rank {16, 32, 64} × regParam {0,05; 0,1; 0,2}). Tự dò trên val, không dùng TrainValidationSplit vì nó chia ngẫu nhiên.
- ALS implicit: độ tin cậy `log1p(1·view + 3·favorite + 5·cook)`. Dò lần lượt alpha {5, 20, 40} → rank {32, 64} → regParam {0,01; 0,1}, chọn theo NDCG@10 trên mẫu 10.000 user của val.
- **Kiểm tra độ nhạy trọng số** với tham số đã chọn: {1/3/5, 1/2/10, chỉ cook}.
- Tham số tốt nhất được fit lại trên view `test`. Lưu top 100 cho user được đánh giá; ở view `test` thì lưu cho mọi user có lịch sử.

**06c — content (sửa đổi c, d):**
- Token của món:
  - âm tiết của tên món, tags và nhãn đặc trưng, tách bằng `RegexTokenizer(pattern="[^\p{L}\p{M}]+")`;
  - mỗi nguyên liệu là 1 token, nối bằng `_` (ví dụ `hành_lá`). Bỏ gia vị (`SEASONINGS`) và stopword tự viết;
  - đặc trưng có cấu trúc thành token dạng `cat=…`, `protein=…`, `method=…`.

  Không dùng bigram ghép xuyên các trường.
- Vector: `CountVectorizer(minDF=2)` → `IDF` → `Normalizer`.
- **Độ tương tự chính xác** tính phân tán bằng chỉ mục ngược (join theo token, rồi tổng tích trọng số). Cùng phép join cho cả cosine TF-IDF và số token chung để tính Jaccard. Bảng `item_sim` lấy 50 món có cosine cao nhất cho mỗi món.
- **LSH:** `MinHashLSH` trên tập token, đo recall@20 so với Jaccard chính xác và so thời gian chạy. Không dùng `BucketedRandomProjectionLSH` trên vector thưa nhiều chiều (lý do ở góp ý c).
- Gợi ý theo nội dung: lấy 30 món nặng nhất của user trong lịch sử, score(u, i) = Σ conf_uj · sim(j, i), lưu top 100 kèm món j đóng góp nhiều nhất (dùng làm lý do gợi ý).

**06f — hybrid (sửa đổi e, f; câu hỏi 3):**
- Bốn nguồn có **cùng độ sâu 100**: ALS implicit, content, popularity theo (vùng, nhóm tuổi), nấu lại.
- Gộp bằng **weighted RRF**: score = Σ w_s / (60 + hạng_s). Trọng số α, β, γ, δ dò trên lưới bước 0,1 với tổng bằng 1 (286 tổ hợp), dùng mẫu 10.000 user của val.
  - Spark tạo bảng ứng viên. Vòng dò lưới chạy bằng numpy trên driver, vì bảng ứng viên của 10.000 user chỉ vài triệu dòng; nếu tạo 286 job Spark thì phần lớn thời gian là chi phí khởi tạo job.
- **Cold-start** theo nhóm của 06a:
  - lạnh → popularity theo (vùng, nhóm tuổi);
  - ít → so 2 phương án trên val (giữ trọng số chung, hoặc α = 0) rồi chọn phương án tốt hơn;
  - ấm → hybrid đầy đủ.
- Đánh giá cuối trên test cho mọi mô hình. Bảng tổng hợp ghi vào `models_metrics.json`.
- Gợi ý cuối: top 50 cho mọi user, kèm `reason`.
- Thí nghiệm món mới (ưu tiên thấp, làm cuối 06f): ẩn lịch sử của 300 món, fit lại ALS, đo khả năng các nguồn gợi ý ra những món đó.

**06d — FP-Growth (sửa đổi h):**
- `array_distinct` mỗi giao dịch.
- Luật nguyên liệu: chạy có và không có gia vị.
- Luật mâm cơm: fit trên lịch sử của view `test`, đánh giá hit rate@3 trên các phiên mâm cơm của tháng test. So với 2 mốc: "3 canh phổ biến nhất" và "món hay nấu cùng nhất theo nhóm món".

**06e — K-means (sửa đổi i):** đặc trưng user lấy từ lịch sử view `val` (train). KMeans và BisectingKMeans với k = 2…12, chọn k theo Silhouette. Báo ARI và NMI so với `persona_main` tại k đã chọn **và tại k = 8**.

**06g — đối chứng (câu hỏi 7):** ALS explicit trên `ratings_original`, chia ngẫu nhiên 80/20, so với trung bình chung và đoán ngẫu nhiên.

**Cấu hình phụ:**
- `get_spark()` đặt `spark.driver.memory`: 3g khi chạy local (driver kiêm executor), 2g trên cụm.
- ALS dùng thư mục checkpoint `/tmp/checkpoint` trên HDFS, hoặc `data/hdfs_local/_checkpoint` khi chạy local.

## D13. Bước 06: điều chỉnh khi cài đặt và phát hiện từ kết quả (24/10)
**Điều chỉnh so với D12:**
- **Lưới alpha của ALS implicit có thêm giá trị 1.** Khi chạy local, alpha tốt nhất (5) nằm đúng biên dưới của lưới {5, 20, 40}. Trên cụm, alpha = 1 thắng (NDCG@10 0,1541 so với 0,1506 của alpha = 5), nên **lại nằm ở biên dưới**. Rank tốt nhất là 64, cũng là biên trên. Xem câu hỏi trong LAST_RUN.
- **TF-IDF của content tính bằng Spark SQL ở dạng dài** (món, token, trọng số), với công thức giống `IDF` của Spark (tf nhị phân, idf = log((N+1)/(df+1)), chuẩn hóa L2). Cách này giúp tính độ tương tự chính xác bằng join trên chỉ mục ngược mà không cần UDF. `CountVectorizer(minDF=2)` quyết định từ điển. Pipeline `CountVectorizer → IDF → Normalizer` vẫn được fit và lưu lại; trên 30 món mẫu, sai khác lớn nhất so với cách tính SQL là 1,1e-16.
- Độ đo xếp hạng tự viết bằng hàm mảng Spark SQL (để có giá trị cho từng user) **khớp hoàn toàn** với `RankingEvaluator` ở cả 4 độ đo (NDCG@10, P@10, MAP@10, R@10 của ALS trên test).
- `SEASONINGS` chuyển vào `rec_common.py`, dùng chung cho 06c và 06d.

**Phát hiện (dữ liệu mô phỏng):**
- **Content xếp hạng rất kém** (NDCG@10 0,0095, thấp hơn cả popularity). Món content gợi ý có hạng phổ biến trung vị 1.598, trong khi món user thật sự nấu có hạng trung vị 410. Lý do: bộ sinh chọn món theo Zipf và thành phần ẩn, còn content bỏ qua độ phổ biến. Đổi lại, content có coverage 77% và novelty cao nhất.
- **Hybrid dò ra β (content) = 0 và γ (popularity) = 0**, chọn α = 0,8, δ (nấu lại) = 0,2. Hệ quả:
  - trong thí nghiệm món mới, hybrid ra 0, chỉ content tìm lại được món bị ẩn (recall@100 = 10,25%);
  - `recs_final` có lý do gợi ý gần như chỉ là "als" (2.408.650 dòng) và "pop" (91.350 dòng, của user lạnh). Không có dòng nào mang lý do "content" hay "nấu lại".

  Xem câu hỏi trong LAST_RUN.
- Ở biến thể khám phá, ALS (0,0934) nhỉnh hơn hybrid (0,0905), vì thành phần "nấu lại" không giúp gì khi đã bỏ món cũ.
- MinHashLSH với 10 bảng băm đạt recall@20 = 0,993, nhưng ở quy mô 5.499 món thì tính chính xác (37 giây) **không chậm hơn** LSH (14–36 giây). Lợi thế của LSH chỉ thể hiện khi danh mục món lớn hơn nhiều; báo cáo cần nói rõ điều này.

**Bổ sung 25/10, theo 3 câu trả lời của người dùng:**
- **Lưới ALS implicit mở rộng một lần, sẽ không mở rộng thêm:** alpha {0,25; 0,5; 1; 5; 20; 40}, rank {32, 64, 128}, regParam cố định 0,1. Luật: rank 128 chỉ được chọn nếu hơn rank 64 ít nhất 0,003 NDCG@10 trên val.
  - Theo alpha (rank 32): 0,25 → 0,1433; 0,5 → 0,1485; **1 → 0,1541**; 5 → 0,1506; 20 → 0,1118; 40 → 0,0808. Alpha 1 là đỉnh thật, không còn nằm ở biên lưới.
  - Theo rank (alpha 1): 32 → 0,1541; 64 → 0,1591; 128 → 0,1623. Rank 128 hơn rank 64 0,0032, đạt ngưỡng, nên **chọn rank 128**. Ở local (bản 10%) mức chênh chỉ 0,0029 nên local giữ rank 64; luật đã chạy đúng ở cả hai chiều.
  - Độ nhạy trọng số tại tham số chọn: 1/3/5 → 0,1623; 1/2/10 → 0,1620; chỉ cook → 0,1328.
  - Kết quả trên test: ALS 0,1539 (trước đó 0,1508); hybrid 0,1588 (trước đó 0,1564). Trọng số hybrid mới: ALS 0,9, nấu lại 0,1.
- **"hybrid + content 2 vị trí" (`hybrid_c2`):**
  - Vị trí 1–8 lấy từ hybrid.
  - Vị trí 9: món content user chưa nấu, xếp theo điểm content × log1p(lượt nấu trong lịch sử).
  - Vị trí 10: món content user chưa nấu và có ít tương tác (lượt nấu ≤ phân vị 20% của các món: 43 ở view test, 38 ở view val), xếp theo điểm content. Không có món nào như vậy thì lấy món thứ hai của vị trí 9.
  - Lý do gợi ý: "Giống món X bạn đã nấu", với X là món đã nấu có độ tương tự cao nhất. Có 96,67% vị trí content tìm được món đã nấu; số còn lại ghi "bạn đã xem".
  - `recs_final` lấy từ `hybrid_c2`. Bảng đánh giá báo cả hai phiên bản.
  - Trên test: NDCG@10 0,1495 so với 0,1588 của hybrid, hiệu −0,0092 [−0,0096; −0,0089]. Coverage 58,0% so với 41,3%. Novelty 9,91 so với 9,13. Diversity 0,849 so với 0,854. Recall món mới @10 1,80% so với 0.
  - **Đánh đổi:** mất khoảng 6% NDCG@10 để gợi ý được món mới và có lý do gợi ý dạng "giống món X". Báo cáo nêu rõ điều này.
- **K-means:** dashboard dùng **k = 8**; `/data/models/kmeans` là model k = 8. `user_clusters` có cột `cluster_k3`, `cluster_k8`, `cluster_k11`. `cluster_profile` có hồ sơ cho cả 3 giá trị k.
  - k = 3: Silhouette 0,227, ARI 0,285, NMI 0,365.
  - k = 8: Silhouette 0,174, ARI 0,418, NMI 0,442.
  - k = 11: Silhouette 0,184, ARI 0,504, NMI 0,512.

## D14. Thiết kế bước 07: xuất MongoDB (25/10)
Bản đề xuất ở LAST_RUN ngày 25/10, chốt với 7 câu trả lời và 6 sửa đổi của người dùng.

**Nguyên tắc:**
- MongoDB chỉ là **tầng phục vụ** cho API và dashboard. Sự kiện thô và các bảng trung gian của bước 06 (`implicit_*`, `recs_<model>_*`, `eval_*`) vẫn chỉ nằm trên HDFS.
- Mốc thời gian của dashboard là **01/09/2026**: `recs_final`, `users.history` và `users.profile` dùng lịch sử đến hết 08/2026 (view test).
- `_id` là khóa nghiệp vụ (`food_id`, `user_id`, hoặc chuỗi khóa như `"k8_c5"`). Các bảng không có khóa tự nhiên (luật, bảng phân tích) dùng ObjectId và được sắp xếp trước khi ghi.

**Các câu trả lời:**
1. **`recs`: 1 document/user** với mảng `items` gồm 50 món (`rank, food_id, score, source, because_food_id`). Bỏ chuỗi `reason` và `reason_type`; API sinh câu lý do từ `source` và tên món `because_food_id`. Đo trên mẫu: 4.052 B/user, so với 8.956 B khi giữ chuỗi. API chỉ hiện "Giống món X" khi `source = "content_slot"`.
2. **Ghi bằng `pymongo`:** `recs` và `users` ghi bằng `foreachPartition` từ executor (8 partition, lô 1.000 document, `insert_many(ordered=False)`); bảng nhỏ `collect()` về driver. Mọi collection ghi vào `<tên>__staging`, kiểm tra số document, tạo index, rồi `renameCollection(dropTarget=True)`. Không dùng MongoDB Spark Connector.
3. **Bỏ bộ lọc calo.** Thay "thời gian nấu" bằng `is_quick`. Bộ lọc còn: chay, món nhanh, không cay, bữa, nhóm món. `dishes.nutrition` vẫn được lưu nhưng dashboard không hiển thị.
4. **Xuất persona thật** vào `users.truth` và `clusters.persona_kiem_chung`, chỉ để kiểm chứng. **Endpoint gợi ý của bước 08 không được trả trường `truth`.**
5. **Có `users.test_cooks`:** các món user thật sự nấu tháng 09/2026, dùng để dashboard đánh dấu gợi ý "trúng".
6. **`mongo-express`:** cổng 8090 trên máy (8081 đã dùng cho UI của `spark-worker-1`). Tài khoản đặt trong `.env` (`ME_CONFIG_*`).
7. **`users.history`:** tối đa 10 món, xếp theo `n_cook` giảm dần; bằng nhau thì món có lần nấu gần nhất đứng trước, sau đó theo `food_id`. Lần nấu gần nhất tính từ sự kiện `cook`, vì `last_ts` của `implicit_test` là sự kiện cuối thuộc mọi loại.

**Sửa đổi:**
- **a. Múi giờ:** timestamp đổi sang chuỗi bằng `date_format` trong Spark, theo múi giờ phiên Spark. `get_spark()` đã đặt `Asia/Ho_Chi_Minh` từ bước 02, và các bước 04, 05 cũng dùng múi giờ này nên không phải sửa. Report kiểm tra lại: giờ của mọi lượt nấu phải nằm trong khung `meal_slot` mà bước 04 đã gán.
- **b. Chuyển kiểu:** dùng `asDict(recursive=True)`, ép `DecimalType` sang `double` (trong Spark, Python kiểm tra lại một lần nữa), `NaN` thành `null`. Kiểu `date` đổi thành chuỗi `"yyyy-MM-dd"` ngay trong Spark.
- **c. Lỗi khi ghi:** gặp `BulkWriteError` thì chỉ bỏ qua khi **mọi** mục trong `writeErrors` có mã 11000 (trùng khóa do Spark chạy lại task) và không có `writeConcernErrors`. Các trường hợp khác dừng job.
- **d. Bù món khi bộ lọc làm danh sách gợi ý ngắn đi (API bước 08):** truy vấn `dishes` với cùng bộ lọc, bỏ các món đã có trong danh sách, xếp theo `stats.cook_rank`. **Không dùng `popular`.** Report ghi `explain()` của truy vấn này.
- **e. Tìm món (API bước 08):** dùng `$regex` trên `name_search` (có index thường). Text index trên `name_search` và `dish_name` giữ lại để minh họa.
- **f. `overview` ghi chú** rằng `dishes.stats` là thống kê cả năm mô phỏng (10/2025–09/2026, gồm cả tháng val và test). Nó chỉ dùng để mô tả, không phải dữ liệu mà mô hình đã thấy.

**Điều chỉnh nhỏ khi cài đặt:** tên trường trong `reports` có dấu chấm (ví dụ `"4.0"` trong phân bố rating) được đổi dấu chấm thành dấu phẩy (`"4,0"`). Tên có `@` (`ndcg@10`) giữ nguyên, vì MongoDB cho phép ký tự này. Bản thiết kế ghi sẽ đổi thành `ndcg_10`, nhưng điều đó không cần thiết.

**Khi cài đặt và chạy (25/10):**
- **Kiểm tra múi giờ đổi sang giờ bắt đầu phiên.** Lần chạy local đầu tiên kiểm tra giờ của từng lượt nấu và thấy 42.799 lượt nằm ngoài khung `meal_slot`. Nguyên nhân không phải múi giờ: bước 04 chọn giờ **bắt đầu phiên** trong khung `[h0, h1)` (`04_simulate.py:409`), còn các sự kiện sau trong phiên có thể lấn sang giờ kế tiếp (sáng sang 9h, trưa sang 13h, tối sang 20h, khuya qua 0h). Vì vậy đổi sang kiểm tra giờ của sự kiện đầu tiên trong mỗi phiên. Trên cụm, cả 4.929.272 phiên đều nằm đúng khung. Nếu múi giờ lệch 7 tiếng thì gần như phiên nào cũng sai, nên phép kiểm tra này vẫn bắt được lỗi múi giờ.
- `storageSize` ngay sau khi ghi bằng 0, vì WiredTiger chưa checkpoint. Do đó `collStats` được đọc ở cuối job, sau lệnh `fsync`.
- Không xuất `dish_type` (nhãn gốc không đáng tin, đã có `dish_type_fixed`). Trong `metrics`, document con `metrics` bỏ 4 khóa lặp lại với document cha (`view, model, variant, group`).
- `users` thực tế là 1.075 B/doc (53,8 MB), lớn hơn con số 858 B trong bản thiết kế, vì có thêm `group`, `test_cooks` và `truth`.

## D15. Thiết kế bước 08: FastAPI + dashboard (25/10)
Bản đề xuất ở LAST_RUN ngày 25/10 (mục A–H), chốt với 5 câu trả lời và 2 chỉnh sửa của người dùng.

**Nguyên tắc (giữ như bản đề xuất):**
- Một service `api` (FastAPI, image `python:3.12-slim`, cổng 8000, RAM 512 MB) phục vụ cả `/api/...` và `web/` tĩnh cùng origin, nên không cần CORS. Tài liệu schema ở `/docs` (OpenAPI).
- API chỉ đọc MongoDB. Database lấy từ `MONGO_DB` (compose: `API_DB`, mặc định `vifood`; phát triển dùng `vifood_local`).
- API trả số thô, frontend định dạng. Không trả `score` của gợi ý, không trả `nutrition`. Endpoint gợi ý và hồ sơ user (E18, E19, E20) **không trả `truth`**.
- Collection nhỏ được cache trong RAM (TTL 10 phút). `recs`, `users`, bù món, tìm món, `similar` luôn đọc MongoDB.
- Bộ lọc món: chay, món nhanh, không cay, bữa (`meal_types`: sáng, trưa, tối, ăn vặt), nhóm món. Bữa mặc định "Tất cả", không tự đặt theo `pref_slot` (có "khuya", không khớp `meal_types`).
- Tìm món: chuẩn hóa NFC → chữ thường → `VN_FROM`/`VN_TO` của 07 → `[^a-z0-9]+` thành dấu cách, rồi `re.escape` và `$regex` trên `name_search`.
- Claude viết toàn bộ code, chia 2 đợt (LAST_RUN mục H). Tên thành viên không xuất hiện trong code, API, dashboard (quy tắc trong CLAUDE.md).

**Các câu trả lời:**
1. **`because_cooked`:** 07 thêm trường `because_cooked` (bool) vào phần tử `content_slot` của `recs.items`, chỉ phần tử này có trường đó. Giá trị lấy từ câu lý do của `recs_final` (06f ghi "… bạn đã nấu" khi món lý do là món đã nấu). Chạy lại `07 --only recs`.
2. **Câu lý do:**
   - `als`: "Người có khẩu vị giống bạn cũng hay nấu món này";
   - `content_slot`: "Giống món {tên} bạn đã nấu" (`because_cooked = true`) hoặc "Giống món {tên} bạn đã xem";
   - `pop`: "Đang được nhiều người {tuổi} tuổi ở miền {vùng} nấu" (đúng câu 06f, vì `pop` là phổ biến theo vùng-tuổi);
   - `fill` (món bù khi lọc): "Được nấu nhiều trong danh mục"; có bộ lọc thì nêu bộ lọc, vd "Món chay, món nhanh được nấu nhiều trong danh mục". Món bù xếp theo `stats.cook_rank` toàn danh mục, nên không nói "ở vùng của bạn".
3. **Thư viện:** ECharts 5.5.1; font Be Vietnam Pro 400/500/600/700 với đủ 3 subset latin, latin-ext, vietnamese (`@fontsource/be-vietnam-pro@5.2.8`), tải bằng `scripts/08_fetch_vendor.sh` và commit vào git.
4. **Thêm `web/js/components.js`** cho thẻ món, thanh lọc, viên trạng thái, khung tải/lỗi/rỗng.
5. **Mục tiêu độ trễ giữ nguyên** (cache p95 < 10 ms; E12, E13, E18, E19 p95 < 50 ms; E20 p95 < 80 ms). Báo cáo ghi số đo thật.

Skill `vifood-dashboard` đã sửa theo câu 2, 3, 4 (mục 1 và mục 5).

**Chỉnh sửa:**
- **a. Trang Tổng quan giữ bố cục bản mẫu canvas:** KPI, heatmap giờ × thứ, phễu, lượt nấu theo tháng (Tết, val, test), tỷ trọng nhóm món, top 5 món, NDCG@10 các mô hình, kiến trúc và tiến độ pipeline. Trang dùng lại E1, E2, E3, E6, E23, và E14 cho top 5 món (xếp theo `stats.cook_rank`, cả năm mô phỏng). Các trang chi tiết vẫn có bản đầy đủ.
- **b. User mẫu theo persona:** E17 trả thêm 2 user cho mỗi `persona_main` (8 persona), kèm `verify_only: true`. Trang Gợi ý có hàng nút chọn user mẫu theo persona. E18 và E19 vẫn không trả `truth`. `test_privacy` chỉ cho phép E15 và E17 có persona.

**Khi cài đặt đợt 1 (25/10):**
- **`because_cooked` lấy từ câu lý do của `recs_final`**, vì bảng này không giữ cờ `because_is_cooked` của 06f. Không phải chạy lại 06f. Trên cụm: 93.137 true, 3.209 false (96,67%, khớp `content_slot_because_cooked_pct` 96,7% của 06f). `recs` tăng từ 202,6 lên 204,3 MB.
- **`07 --only` gộp report:** chạy một phần thì `export_report.json` gộp vào report cũ của cùng database (thêm `partial_runs`), không ghi đè số liệu của 25 collection còn lại.
- **Câu lý do món bù rút gọn:** "Món chay, bữa sáng, đồ uống được nấu nhiều trong danh mục" thay cho "món cho bữa sáng, món nhóm đồ uống" (quá dài trên thẻ món).
- **E17 bỏ 5 user mẫu theo hash** của bước 07. Chỉ giữ 3 user/nhóm và 2 user/persona, chọn theo `user_id` nhỏ nhất (có ≥ 3 món trong `history`, trừ nhóm lạnh).
- **Top 5 món ở Tổng quan dùng E14** (`/api/dishes?limit=5`, xếp theo `stats.cook_rank`, ghi "cả năm mô phỏng").
- **Khoảng tin cậy ở trang Đánh giá hiện bằng bảng**, không vẽ biểu đồ: 7 phép so sánh có độ lớn chênh nhau tới 30 lần nên biểu đồ điểm–vạch không đọc được. Chú thích ghi đúng cách tính của `rec_common.paired_ci`: hiệu ghép cặp theo user, ±1,96 × sai số chuẩn (không phải bootstrap).
- **Recall món mới** lấy từ `model_hybrid_report.cold_items.by_source` (tên nguồn đổi sang tên mô hình: als → als_implicit, rep → nau_lai). Các mô hình phổ biến không có số này.
- **4 trang của đợt 2 là trang khung** ghi "Trang đang được xây dựng", để liên kết trên thanh bên không trả 404.
- **pytest:** 2 phép so khớp chính xác giữa các collection (tổng lượt nấu theo tháng bằng `overview`; NDCG của hybrid bằng `models_metrics`) chỉ chạy với `--db vifood`. Ở `vifood_local`, các bảng `analysis_*` lệch `overview` 1.145 lượt nấu (235.981 so với 237.126), và `reports` là file của lần chạy trên cụm trong khi `metrics` là kết quả local (NDCG hybrid 0,1588 so với 0,1577).

**Sửa sau khi xem đợt 1 (25/10):**
- **Món đã nấu trong gợi ý:** E19 trả thêm `n_cook_before` (số lần đã nấu trước 01/09/2026) khi món nằm trong `history`; thẻ món hiện chip "Bạn đã nấu N lần" (nền `--herb-soft`), giữ nguyên chấm màu theo nguồn. `history` chỉ có 10 món nấu nhiều nhất, nên món nấu ít hơn không có chip. Món bù (`fill`) không bao giờ có, vì truy vấn bù đã loại món trong `history`.
- **Ảnh món:** không tải sẵn. Trình duyệt thường trên máy tải được `monngonmoingay.com`, còn `image.cooky.vn` (4.291/5.499 món) hết thời gian chờ. Thay vào đó: ảnh thay thế theo 10 nhóm món (nền 3 tông có sẵn + biểu tượng SVG nét mảnh + tên nhóm), bỏ ảnh thật khi lỗi hoặc quá 4 giây kể từ lúc ảnh sắp vào màn hình. Quy cách ở skill mục 4.
- **Biểu đồ theo tháng:** bỏ 3 series rỗng dùng làm chú giải (chúng chiếm chỗ trong nhóm cột, làm cột mảnh và lệch trái), chú giải viết bằng HTML (`MONTH_LEGEND`). `test_web_rules` có luật chặn series cột rỗng.
- **Bố cục trang Gợi ý:** hàng đầu gọn (chế độ, ô mã, menu "User mẫu" theo nhóm và theo persona "chỉ để kiểm chứng", nút "Xem gợi ý"), rồi bộ lọc và danh sách; hồ sơ và món hay nấu ở cột phải. Màn hẹp: thanh bên xếp mục thành hàng chip, bộ lọc thu vào nút "Bộ lọc". Đo được: ở 1440 × 1000 hàng thẻ đầu kết thúc ở 740px; ở 390px danh sách bắt đầu ở 843px.

## D16. Bước 08 đợt 2: 4 trang còn lại, nhãn cụm theo luật, đo độ trễ (25/10)
Làm theo mục H của bản thiết kế (D15). 9 endpoint mới: E4, E5, E7 (Hành vi), E8, E10, E11 (Món ăn), E15, E16 (Phân khúc), E25 (Thời gian thực). Đủ 25 endpoint E0–E26 (không có E9, E21).

**Nhãn và đề xuất cho cụm (E15, `api/labels.py`), sinh theo luật, không viết tay cho từng cụm:**
- Với mỗi k, tính z của từng đặc trưng giữa các cụm: (giá trị của cụm − trung bình các cụm) ÷ độ lệch chuẩn các cụm (không trọng số).
- **Nhãn** = 2 đặc trưng có |z| lớn nhất, mỗi đặc trưng có cụm từ "cao" và "thấp" (vd `share_lau` cao → "hay nấu lẩu", `cook_per_view` cao → "hay nấu sau khi xem", thấp → "xem nhiều, ít nấu"). 3 đặc trưng |z| lớn nhất được hiện ở thẻ cụm.
- **Đề xuất (sửa 26/10 theo góp ý của người dùng): mỗi cụm chỉ 1 câu, câu đặc trưng nhất, không cụm nào lặp câu của cụm khác** trong cùng k.
  - Ứng viên của một cụm: các đặc trưng có |z| ≥ 0,5 khớp một dòng trong bảng luật dưới.
  - Gán tham lam trên mọi cặp (cụm, câu ứng viên) theo |z| giảm dần: cụm lệch mạnh nhất ở một đặc trưng nhận câu của đặc trưng đó; câu đã gán cho cụm khác thì cụm sau xét câu tiếp theo (`labels.describe_clusters`).
  - Cụm không còn câu nào thì "Giữ gợi ý cá nhân hybrid mặc định". Với k = 3, 8, 11 hiện chưa cụm nào rơi vào trường hợp này.
  - Bản đầu lấy tối đa 2 câu mỗi cụm, nên câu "Người dùng tích cực…" và "Kích hoạt lại…" lặp ở nhiều cụm.

  | Đặc trưng | Hướng | Đề xuất |
  |---|---|---|
  | `share_chay` | cao | Ưu tiên bộ sưu tập món chay, thêm món chay mới vào gợi ý |
  | `share_nhanh` | cao | Gợi ý món nhanh, ít bước cho ngày bận rộn (bản đầu ghi "cho bữa trưa ngày thường", lệch với cụm k = 8 số 7 nấu nhiều bữa tối) |
  | `share_haisan` | cao | Đẩy món hải sản và món ăn kèm (luật FP-Growth) |
  | `share_cay` | cao | Gợi ý món cay, món nhậu vào buổi tối và cuối tuần |
  | `share_ngot` | cao | Gợi ý chè, bánh, đồ uống cho bữa phụ |
  | `share_canh` | cao | Gợi ý mâm cơm: món mặn kèm canh (luật FP-Growth) |
  | `share_lau` | cao | Gợi ý lẩu vào cuối tuần |
  | `slot_0` / `slot_1` / `slot_2` / `slot_3` | cao | Gửi gợi ý bữa sáng vào đầu ngày / bữa trưa trước giờ nấu trưa / bữa tối vào buổi chiều / món ăn khuya, món nhanh vào buổi tối muộn |
  | `share_weekend` | cao | Tập trung gợi ý vào cuối tuần |
  | `log_events`, `log_sessions` | thấp | Kích hoạt lại: gợi ý món phổ biến theo vùng-tuổi |
  | `cook_per_view` | thấp | Xem nhiều nấu ít: ưu tiên món dễ làm, ít nguyên liệu |
  | `log_events` | cao | Người dùng tích cực: giới thiệu món mới trong danh mục trước |
  | `cat_entropy` | cao / thấp | Khẩu vị đa dạng: tăng tỷ trọng món khám phá (content) / Ít loại món: gợi ý món cùng nhóm, mở rộng dần sang nhóm gần |
  | `rate_per_cook` | cao | Hay chấm điểm: mời đánh giá để cải thiện gợi ý |

- Kết quả k = 8 khớp khá tốt với persona kiểm chứng (chỉ để kiểm chứng): "Nhiều món chay · ít chấm điểm" ↔ ăn chay; "Hay nấu lẩu · thích cay" ↔ thích cay/nhậu; "Chuộng món nhanh · nấu bữa tối" ↔ bận rộn; "Nhiều món ngọt, đồ uống · ít hải sản" ↔ hảo ngọt; "Hay nấu sau khi xem · nhiều canh/súp" ↔ gia đình truyền thống. 3 cụm còn lại (nhãn về bữa và mức hoạt động) khó đối chiếu hơn. Luật không đọc persona.

**Các quyết định khác khi cài đặt:**
- **E15 `n_users` cộng từ `clusters`**, không lấy `model_kmeans_report.users`, để đúng với cả `vifood_local` (ở đó `reports` là file của cụm). Phép so với report chỉ chạy với `--db vifood`.
- **E26 được có chữ "persona"**: E26 trả nguyên file report (để gỡ lỗi, trang không gọi), và report 04, 06e có thống kê persona gộp theo cụm hoặc toàn bộ, không có persona của từng user. `test_privacy` vẫn cấm khóa `truth` ở E26.
- **E16 đọc MongoDB mỗi lần** (aggregation `$facet` trên `cluster_k8`), như thiết kế, để thể hiện index. Độ trễ tăng theo cỡ cụm (p95 56,8 ms trên `vifood`, 10,1 ms trên `vifood_local`); không có mục tiêu riêng.
- **Tra cứu món ở trang Món ăn:** khi có chữ tìm thì dùng E12 (không có bộ lọc), lọc lại 30 kết quả đầu ở trình duyệt theo đúng nghĩa bộ lọc của E14; không gõ thì dùng E14, 12 món một lần, nút "Xem thêm".
- **Đo độ trễ `vifood_local`** bằng một uvicorn tạm ở cổng 8001 trong chính container `api` (`MONGO_DB=vifood_local`), không phải dựng lại service; đo xong thì tắt.
- **Ảnh chụp 7 trang** (`docs/images/08_*_{1440,390}.png`) chụp bằng Chrome headless điều khiển qua DevTools Protocol (giả lập thiết bị, chụp toàn trang). `--window-size=390` không dùng được vì Chrome headless dựng trang rộng hơn rồi mới cắt ảnh.

## D17. Đo hiệu năng Spark: thiết kế đã chốt (26/10)
Bản đề xuất (LAST_RUN 26/10, mục A–I) được duyệt với 7 câu trả lời sau. Mục đích: đo thời gian các job 02–06 khi đổi **số worker (1 / 2)** và **quy mô dữ liệu (10 / 50 / 100%)**, không đụng dữ liệu và report của bản thật.

**Phạm vi đo (câu 2, rút gọn so với ma trận đầy đủ, khoảng 3 giờ):**

| Phần | Cấu hình | Số lần |
|---|---|---|
| Chuỗi 04 → 05 → 06a → 06b → 06c → 06d → 06e → 06f ở 100% | 1 và 2 worker | 1 |
| 05 và 06b ở 100% | 1 và 2 worker | thêm 2 lần (tổng 3, lấy trung vị, ghi min–max) |
| Chuỗi ở 50% | 2 worker | 1 |
| Chuỗi ở 10% | 1 và 2 worker | 1 |
| Danh mục: 02, 03, 06g | 1 và 2 worker | 1 |

- Không đo 07 (nút thắt là ghi MongoDB, và 07 ghi đè `vifood`).
- Không có lần làm nóng riêng. Job chỉ chạy 1 lần thì số đo là lần duy nhất; báo cáo ghi rõ điều này.

**Đổi số worker (câu 4):** chỉ dừng `spark-worker-2` (`docker stop`), không thêm cấu hình 1 worker × 4 core.
- 1 worker = 1 executor (2 core, 2 GB); 2 worker = 2 executor (4 core, 4 GB tổng). **1 worker giảm cả số core lẫn bộ nhớ executor**, report và báo cáo phải ghi rõ: speedup đo được là của "cụm 2 nút so với 1 nút", không tách riêng ảnh hưởng của core và của bộ nhớ.
- Giữ nguyên `shuffle.partitions`, bộ nhớ executor, driver ở cả hai cấu hình.
- Mọi container chạy trên cùng một máy (máy ảo Docker 8 CPU): shuffle giữa 2 worker đi qua mạng ảo, datanode là container riêng nên không có data locality.

**Gốc dữ liệu và report riêng (câu 5):**
- `common.Paths` đọc `VIFOOD_DATA_ROOT` (mặc định `/data`) và `VIFOOD_OUTPUT_DIR` (mặc định `data/output`). Không đặt biến thì mọi thứ như cũ.
- Khi đặt `VIFOOD_DATA_ROOT`: `raw` vẫn đọc `/data/raw` (chỉ đọc), checkpoint ALS nằm trong gốc đó (`<gốc>/_checkpoint`).
- Khi đặt `VIFOOD_OUTPUT_DIR`: report và bản sao nhỏ (`processed_local` = `<thư mục>/processed`) đều ghi vào thư mục đó, không ghi đè `data/output/` và `data/processed/` của bản thật.
- `Paths.output_prod` luôn là `data/output`: `--fixed` đọc tham số đã chọn từ đây, 06g đọc số liệu mô phỏng để so sánh từ đây.
- Gốc đo: `/perf/s010`, `/perf/s050`, `/perf/s100`, `/perf/catalog`. Trước khi đo, chép `curated/` và `features/` từ `/data` sang từng gốc. Report mỗi lần chạy: `data/output/perf/<job>_<mức>_w<số worker>_r<lần>/`.
- `VIFOOD_RUN_TAG` gắn vào tên ứng dụng (vd `06b_als|s100|w1|r2`) để tìm lại trên History Server.

**Sinh 50% và 10% (câu 6):** chạy `04 --scale 0.5` và `04 --scale 0.1` vào gốc riêng. **Đây là dân số sinh mới, không phải tập con của bản 100%** (bảng users sinh tuần tự bằng một RNG với kích thước n). Phân bố persona, vùng, tuổi và cách sinh sự kiện giống nhau, nên số sự kiện tăng gần tuyến tính theo số user. Bản 100% chạy lại 04 vào `/perf/s100` (cùng seed nên ra đúng dữ liệu của `/data`).

**Chế độ `--fixed`** (chỉ fit một lần với tham số đã chọn, đọc từ `data/output/model_*_report.json`):
- 06b (câu 1): **chỉ chạy view test** (lịch sử train + val → đánh giá test), như lần fit cuối của bản thật: baseline, bias λ = `best_bias_lambda`, ALS explicit `best_als_explicit`, ALS implicit `best_als_implicit` (alpha 1, rank 128, regParam 0,1). Bỏ dò lưới và độ nhạy trọng số.
- 06c: bỏ vòng MinHash 3 / 5 / 10 bảng băm (thí nghiệm so sánh), giữ token, độ giống chính xác, gợi ý val và test.
- 06e: chỉ fit KMeans k = 3, 8, 11 (3 cột `cluster_k*` cần lưu), bỏ dò k = 2…12 và BisectingKMeans.
- 06f (câu 3): chỉ view test; trọng số lấy `best_weights` và `few_users_rule.weights` (bỏ `tune_weights`, vốn là numpy trên driver); **bỏ `test:explore_beyond`** và `cold_items`.
- 06g: bias λ và (rank, regParam) lấy từ `model_control_report.best`, bỏ lưới.

**Đo gì:** thời gian ứng dụng theo History Server (số chính), `timings_s` theo giai đoạn, và số liệu stage qua REST của History Server (shuffle đọc/ghi, phần đọc từ xa, spill, GC, thời gian CPU, số task). `common.Timer` gắn job group Spark trùng tên giai đoạn, nên số liệu stage gom được theo đúng giai đoạn của `timings_s`; 02, 03, 04 có thêm `timings_s`. Lấy mẫu `docker stats` trong lúc chạy (đỉnh RAM, CPU của worker và `jupyter`).

**Nơi lưu (câu 7):** `scripts/09_perf.py` (chạy trên máy) ghi nối tiếp `data/output/perf_runs.jsonl` (mỗi dòng một lần chạy, dừng giữa chừng thì chạy tiếp được) và tổng hợp ra `data/output/perf_report.json`. `07 --only perf` nạp vào collection `perf`. Trang Đánh giá có thẻ "Hiệu năng Spark" (E24 thêm khóa `perf`).

**Nếu 06b ở 100% với 1 worker hết bộ nhớ:** không giảm rank cho riêng một cấu hình. Ghi lại lần chạy lỗi đó, và đo speedup của 06b bằng `--quick` (cả hai cấu hình), có ghi chú.

**Khi cài đặt và chạy (26/10):**
- **Kiểm tra bản thường:** chạy 05, 06a–06g `--local` bằng code cũ (làm mốc) và code mới, không đặt biến nào: 28/28 file report giống hệt (bỏ qua khóa thời gian); `explain.txt` chỉ khác số hiệu nội bộ của Spark (`#id`, `plan_id`). Khóa `fixed` chỉ ghi vào report khi chạy `--fixed`.
- **`common.Timer`** thay cho Timer riêng của `rec_common` và hàm `step` của 05 (cùng cách in). 02, 03, 04 đánh dấu giai đoạn bằng `T.mark()` (không phải thụt lề lại cả file).
- **Tiến độ ở Tổng quan:** bước 09 là "Đo hiệu năng Spark" (trùng số với `scripts/09_perf.py`, "Xong" khi collection `perf` có doc `summary`); Structured Streaming chuyển thành bước 10.
- **Thứ tự chạy:** 3 lần 06b ở 100% / 1 worker chạy liền nhau ở bước chạy thử (bộ lọc `s100:w1:06b` khớp cả 3 lần), không xen kẽ với 2 worker như dự kiến. Ba lần này lệch nhau 5,3% (776,5–817,9 giây).
- **Lần 03 / danh mục / 1 worker:** job xong (exit 0, report đủ) nhưng event log không được đóng (còn file `appstatus`), lặp lại ở lần chạy lại; mọi lần khác đều bình thường. Thời lượng của lần này lấy từ REST của History Server: kết thúc job cuối − bắt đầu ứng dụng (38,8 giây), ghi `duration_note`. Thời gian lệnh `docker exec` khớp với lần 2 worker (42,8 so với 42,5 giây).
- **`executorCpuTime` không tính CPU của tiến trình Python** (mapInPandas, UDF), nên tỷ lệ CPU / thời gian chạy của 04 chỉ khoảng 0,07.
- **Ước tính `--plan`** sửa theo số đo thật ở 10% (chi phí cố định lớn hơn giả định 0,2 lần): kế hoạch 54 lần ước tính 3,3 giờ; thực tế 2,71 giờ chạy job (21:26–00:29, kể cả bật/tắt worker và chờ History Server).

**Kết quả chính (dữ liệu hành vi mô phỏng, chi tiết trong `perf_report.json`):**
- 100%: chuỗi 04 → 06f mất 1.702,9 giây với 2 worker, 2.309,2 giây với 1 worker: **speedup 1,36** (efficiency 0,68). Theo job: 04 1,64; 06b 1,32; 06a 1,30; 05 1,21; 06c 1,15; 06f 1,08; 06e 0,93; 06d 0,89.
- 10%: 2 worker **chậm hơn** 1 worker (chuỗi 535,8 so với 473,1 giây, speedup 0,88); danh mục 02 / 03 / 06g: 0,90 / 0,98 / 0,73.
- Theo dữ liệu (2 worker): tổng chuỗi 10% → 50% → 100% = 535,8 → 1.044,8 → 1.702,9 giây (1,95 và 3,18 lần, trong khi dữ liệu tăng 5 và 10 lần). Job tăng gần tuyến tính: 04 (5,42 lần) và 06b (5,02 lần); job khác chủ yếu là chi phí cố định (06d chỉ 1,22 lần).
- **Vì sao speedup dưới 2:** (1) tổng thời gian task tăng khi thêm worker (06b: 1.491,5 → 1.852,3 giây; 05: 179,1 → 267,2 giây) vì 2 worker dùng chung 8 CPU của máy ảo Docker với datanode và driver; (2) khoảng một nửa shuffle đọc từ worker kia qua mạng ảo (06b 1.815,5 / 3.748,1 MB); (3) phần chạy trên driver không song song được (khởi động SparkSession, `collect`, numpy); (4) job nhỏ có quá ít task để chia. Ngược lại, 1 worker có ít bộ nhớ hơn nên spill nhiều hơn (06a 7.526,9 so với 4.129,9 MB spill bộ nhớ; 04 spill 2.144 MB, 2 worker không spill).

**Bổ sung 26/10 (sáng): đo thêm 50% với 1 worker, speedup theo mức dữ liệu.**
- Người dùng chọn đo thêm chuỗi 04 → 06f ở 50% với 1 worker, 1 lần (`add("s050", 1, CHAIN)` trong `build_plan`). 8/8 lần OK; tổng 62 lần chạy, 0 lỗi. Report của 04, 05, 06b, 06f ở 50% giống hệt giữa 1 và 2 worker (bỏ qua khóa thời gian).
- `perf_report.json` thêm khóa `speedup_by_scale`: speedup của cả chuỗi và của 04, 05, 06b ở 10/50/100%. E24 trả thêm khóa này; thẻ "Hiệu năng Spark" có biểu đồ (d) speedup theo mức dữ liệu, vạch lý tưởng 2.
- Kết quả: speedup cả chuỗi **0,88 / 1,59 / 1,36** ở 10/50/100%; 04 1,03 / 2,19 / 1,64; 05 0,77 / 1,22 / 1,21; 06b 1,01 / 1,56 / 1,32. Speedup không tăng đều theo dữ liệu mà cao nhất ở 50%.
- Hai lý do (từ số liệu stage):
  - **04 ở 50% / 1 worker chậm bất thường:** giai đoạn sinh (stage mapInPandas) tốn 21,7 ms thời gian task mỗi user, so với 15,6 ms ở 100% / 1 worker, 17,9 và 18,5 ms ở 50% và 100% / 2 worker. Chỉ chạy 1 lần nên chưa tách được đây là nhiễu của máy hay thật. Bỏ 04 ra, speedup phần còn lại của chuỗi là 1,37 ở 50% và 1,23 ở 100%: vẫn cao hơn ở 50%, nhưng chênh ít hơn nhiều.
  - **Ở 100%, 2 worker tốn thêm nhiều thời gian task hơn:** 06b tổng thời gian task tăng 5,8% khi thêm worker ở 50% (910,4 → 963,1 giây) nhưng tăng 24,2% ở 100% (1.491,5 → 1.852,3 giây); GC 6,7 → 11,2 giây và đọc shuffle từ xa 1.815,5 MB ở 100%. Phần `test:als_implicit` có speedup 1,62 ở 50% và 1,39 ở 100%.
- **Phát hiện phụ ở 04:** phần sinh sự kiện (mapInPandas) chạy **2 lần** trong mỗi lần chạy 04: stage 4 (lấy mẫu cho `repartitionByRange(12, "month")`) và stage 6 (sinh thật, ghi shuffle) có thời gian task gần bằng nhau (vd 100% / 2 worker: 926,2 và 923,4 giây). Chưa sửa: sửa sẽ làm số đo 04 không còn so được với các lần đã đo (chờ người dùng quyết định).
- **Chạy lại 04 ở 50% / 1 worker thêm 2 lần (26/10 trưa, người dùng chọn):** 575,8 / 604,0 / 631,8 giây (lệch ±4,6%), trung vị vẫn là 604,0 nên speedup 04 ở 50% vẫn là 2,19. Phần sinh ở hai lần mới tốn 21,5 và 23,8 ms thời gian task mỗi user. **Lần đo ở 50% không phải nhiễu.** Điểm khác thường có thể là lần đo duy nhất ở 100% / 1 worker (15,6 ms/user, thấp nhất trong mọi cấu hình), nhưng chưa đo lại. `perf_report.json` ghi `plan.repeats_50pct_1w = {"04": 3}`; tổng 64 lần chạy.
- **Câu 12 (04 chạy phần sinh 2 lần):** người dùng chọn chỉ ghi vào báo cáo như một phát hiện tối ưu, không sửa 04.
- **Chạy lại 04 ở 100% / 1 worker thêm 2 lần (26/10 chiều, người dùng chọn):** `build_plan` thêm `add("s100", 1, ["04"], rep)` cho rep 2, 3; `perf_report.json` ghi `plan.repeats_100pct_1w = {"04": 3}`; tổng 66 lần chạy, 0 lỗi.
  - Ba lần: **864,4 / 1.230,1 / 900,4 giây** (r1 / r2 / r3). Thời gian task của giai đoạn sinh (cả 2 stage mapInPandas, `spark.by_group.generate_write`) mỗi user: 31,9 / 45,6 / 33,3 ms. Ở 50% / 1 worker con số này là 43,4 / 41,1 / 44,9 ms.
  - **r2 là ngoại lệ, không dùng để kết luận:** trong lúc r2 chạy (14:05–14:26) có việc khác chạy song song trên cùng máy (chạy 2 notebook biểu đồ bằng nbconvert trong container `jupyter`, chạy thử `01_ingest.sh` và đọc lại file trên HDFS để so checksum). r3 chạy lúc máy không làm gì khác và khớp r1 (lệch 4,2%).
  - Trung vị là 900,4 giây (r2 là lần lớn nhất nên không làm lệch trung vị). Speedup 04 ở 100% đổi từ 1,64 thành **1,71**; cả chuỗi 04 → 06f ở 100% từ 1,36 thành **1,38** (2.345,2 so với 1.702,9 giây). Ở 10% và 50% không đổi (0,88 và 1,59).
  - **Kết luận:** 04 ở 100% / 1 worker nhanh hơn thật trên mỗi user so với 50% / 1 worker (khoảng 32–33 so với 41–45 ms thời gian task của giai đoạn sinh), không phải do một lần đo may mắn. Speedup 04 cao nhất ở 50% (2,19) vì cấu hình 50% / 1 worker chậm, chứ không vì 2 worker hiệu quả hơn ở 50%. Nguyên nhân chưa tách được bằng số liệu stage hiện có; báo cáo ghi đúng như vậy.

## D18. Structured Streaming (bước 10): thiết kế đã chốt (26/10)
Người dùng chọn phương án đề xuất cho 10 câu của bản thiết kế (LAST_RUN 26/10 sáng), kèm 12 sửa đổi. Câu 12 của LAST_RUN (04 chạy phần sinh 2 lần): **chỉ ghi vào báo cáo, không sửa**.

**Thiết kế:**
- **Nguồn:** phát lại sự kiện mô phỏng của Chủ nhật 27/09/2026 (bước 04). `src/10a_stream_prep.py` lọc ngày, gán `event_id` theo thứ tự thời gian, ghi `data/stream/replay_<ngày>.jsonl.gz` và bản Parquet `/data/stream/replay/<ngày>`, tính đáp án batch.
- **Replayer:** `src/10b_replayer.py` là Python thường, không dùng Spark. Mỗi giây thật ghi 1 file JSON Lines vào `/data/stream/_staging` qua WebHDFS, rồi RENAME (nguyên tử) sang `/data/stream/incoming`. Mặc định tốc độ 60, chạy từ 16:00 khi demo; `--speed max` dùng để đo thông lượng.
- **Đến trễ và gửi lặp:** `--late 0|1|2`: 3% trễ 1–8 phút, 0,2% gửi lặp, 0,3% bị giữ 20–40 phút (chỉ ở mức 2).
- **Query:** `withWatermark("ts", 10 phút)` → `dropDuplicatesWithinWatermark(event_id)` → lọc cook/view/favorite → join broadcast `users` (lấy vùng) → `groupBy(window 60 phút trượt 15 phút, vùng, món)` → `update` → `foreachBatch`.
- **Chiều nhóm:** vùng; bữa chỉ là nhãn của cửa sổ, lấy bữa chiếm đa số theo 4 cột đếm `n_slot*` trong cùng phép tổng hợp, không nhân trạng thái.
- **Sink:** gom về driver, ghi bằng `pymongo`:
  - `trending_cells`: số đếm tuyệt đối, `_id = ws|vùng|món`, upsert. Ghi lại cùng batch cho cùng giá trị, nên idempotent;
  - `trending`: 1 doc / cửa sổ × phạm vi (toàn quốc, 3 vùng): top 20 và "tăng nhanh";
  - `stream_status`: heartbeat, watermark, độ trễ, số dòng bị bỏ.
- **Checkpoint và vận hành:**
  - checkpoint ở `/data/stream/checkpoint`, state store mặc định (HDFS-backed);
  - luồng xin `cores.max 2`, executor 1 GB, driver 1 GB, `shuffle.partitions 4`, Spark UI ở cổng 4041 (thêm vào compose);
  - bật/tắt bằng `scripts/10_stream.sh start|stop|status|reset`. Dashboard không có nút bật/tắt.

**12 sửa đổi của người dùng và cách làm:**
1. **Tick:** replayer phát sự kiện `tick` cho mỗi phút mô phỏng không có sự kiện, và một tick cuối có ts = giờ kết thúc + 75 phút, để watermark vượt mọi cửa sổ và cửa sổ cuối được chốt. Phép lọc `event_type` đặt sau `withWatermark`. Bài thử (mục "Kết quả bài thử") cho thấy phải đặt **sau cả phép khử trùng**.
2. **Bài thử `src/10t_stream_semantics.py`:** chạy local, dùng đúng `stream_query()`, đẩy 4 file nhỏ. Kết luận ở mục dưới; số liệu trong `data/output/stream_semantics_report.json`.
3. **`src/10c_stream_check.py` chạy 3 kịch bản:**
   - s1, `--late 0`: khớp tuyệt đối;
   - s2, chỉ trễ 1–8 phút và gửi lặp: khớp tuyệt đối;
   - s3, đủ cả trễ quá watermark: không ô nào vượt đáp án, và phần thiếu của mỗi (cửa sổ, vùng) ≤ số sự kiện bị giữ > 10 phút rơi vào đó.
4. **Phạm vi đáp án:** đáp án của 10a và 10c chỉ tính ts trong [`--from`, `--to`), giống đoạn replayer phát.
5. **`last_batch_id` lưu kèm `query.id`:** chạy lại từ checkpoint thì giữ nguyên id, nên bỏ qua batch đã ghi. Reset thì id mới, nên không bỏ qua batch nào.
6. **"Tăng nhanh":** so [t−60, t) với [t−120, t−60), là cửa sổ bắt đầu sớm hơn 60 phút, không chồng lên nhau. Lấy từ `trending_cells` khi ghi doc. Doc của một cửa sổ được ghi lần cuối sau khi cửa sổ trước đã chốt, nên `prev_cooks` của doc đã chốt là chính xác.
7. **Trigger là tham số:** 5 giây ở tốc độ ≤ 60, 1 giây ở tốc độ cao hơn. Bài đo thông lượng dùng 14 file, mỗi file 12 giờ, `maxFilesPerTrigger 2`, `maxBytesPerTrigger 256m`. Đổi số core, số partition hay định nghĩa cửa sổ mà checkpoint còn thì `10_stream.py` dừng và yêu cầu reset; cấu hình lưu ở `/data/stream/checkpoint_conf.json`, vì Spark giữ số partition của state store trong checkpoint.
8. **Định nghĩa độ trễ:** là độ trễ của sự kiện **mới nhất** trong batch, tính từ lúc ghi MongoDB xong trừ `emit_ts`. Cận trên cho mọi sự kiện trong batch = độ trễ đó + 1 chu kỳ trigger + 1 giây (độ mịn của file).
9. **"1 giờ qua" trên trang:** là cửa sổ gần nhất có `window_end` ≤ `sim_now` (sự kiện mới nhất đã xử lý). Cửa sổ có `window_end` > `sim_now` gắn nhãn "đang cập nhật". `final` = `window_end` ≤ watermark.
10. **Cổng:** thêm cổng 4041:4041 cho `jupyter` trong compose.
11. **Ảnh state store:** 10c đọc state store của kịch bản cuối bằng `spark.read.format("state-metadata")` và `format("statestore")` (khử trùng và tổng hợp), ở batch cuối − 30 (Spark chỉ giữ 100 phiên bản). Kết quả ghi vào `data/output/stream/statestore_sample.txt`.
12. **Đường dẫn:** dùng `/data/stream` như kế hoạch.

**Kết quả bài thử (`10t`, Spark 4.2 local):**
- **Phép lọc `event_type` đặt ngay sau `withWatermark` bị optimizer đẩy xuống dưới `EventTimeWatermark`, tới tận nguồn JSON**, vì phép lọc không dùng cột `ts`. Bằng chứng:
  - F1 chỉ đọc 6 dòng (tick bị loại ngay khi đọc);
  - watermark sau F3 (chỉ có tick 11:30) vẫn là 10:15, chứ không lên 11:20.
  
  Hệ quả: tick vô dụng; giờ vắng thì watermark đứng yên; cửa sổ cuối không bao giờ được chốt. **Cách sửa:** lọc sau `dropDuplicatesWithinWatermark`, vì phép khử trùng có trạng thái nên chặn việc đẩy phép lọc xuống. Khi đó F1 đọc 7 dòng và watermark sau F3 là 11:20. Đổi lại, tick và sự kiện `rate` cũng vào trạng thái khử trùng (nhỏ: tối đa 1 tick mỗi phút, `rate` khoảng 3,4% sự kiện). `stream_query(filter_before_dedup=True)` giữ lại để tái hiện lỗi.
- **`dropDuplicatesWithinWatermark` tự bỏ dòng có ts < watermark** và đếm vào `numRowsDroppedByWatermark` của chính nó (`dedupeWithinWatermark`). Ở bản lọc sau khử trùng, phép khử trùng bỏ 3 dòng: id 101 (10:15 < 10:20), bản lặp của id 1 (10:00), id 104 (10:50 < 11:20). Bản lặp của id 6 (10:25 ≥ watermark) bị khử như một dòng trùng, không tính là trễ.
- **Phép tổng hợp (`stateStoreSave`) luôn bỏ 0 dòng,** vì dòng trễ đã bị lọc ở bước khử trùng.
- **Hệ quả của việc khử trùng đứng trước:** một sự kiện quá watermark bị **bỏ hoàn toàn**, kể cả khi vài cửa sổ trượt chứa nó vẫn còn mở. Ví dụ id 104 ở 10:50: cửa sổ [10:30, 11:30) và [10:45, 11:45) chưa đóng nhưng vẫn không được tính.
- **"Trễ" tính theo watermark của batch xử lý sự kiện, không theo lúc sự kiện đến.** Watermark của một batch tính từ batch trước, nên batch nhận được sự kiện trễ tới (ts lớn nhất trong batch − watermark). Ở 10c s3 (tốc độ 300, trigger 1 giây, mỗi file 5 phút mô phỏng), khoảng này có trung vị 15 phút. Khi một batch chạy quá 1 giây và gom 2 file, khoảng này lên ≥ 20 phút; sau mốc kết thúc thì hết tick nên watermark đứng yên. Vì vậy một phần sự kiện bị giữ 20–40 phút vẫn được đếm, và phần thiếu so với đáp án chỉ **nhỏ hơn hoặc bằng** số sự kiện bị giữ nhân với số cửa sổ chứa chúng (số liệu trong `stream_report.json` → `checks.scenarios.s3`).

**Khi cài đặt và chạy (26/10):**
- **Hàm dùng chung:** `stream_query()`, `aggregate()` và `window_docs()` nằm trong `src/stream_common.py`, dùng chung cho luồng, đáp án batch (10a, 10c) và bài thử 10t. Đáp án và luồng vì vậy cùng một định nghĩa cửa sổ và cùng cách xếp hạng.
- **Giờ mô phỏng trên trang:** tick cuối (giờ kết thúc + 75 phút) đẩy ts lớn nhất vượt khỏi đoạn phát lại. E25 vì vậy chặn `sim_now` ở mốc kết thúc; nếu không, "1 giờ qua" sẽ là một cửa sổ chỉ có 15 phút dữ liệu.
- **Độ trễ sự kiện → API:** `stream_status` có `data_batch_id` và `newest_emit`, chỉ đổi khi batch có dữ liệu. 10d đo độ trễ theo cặp này.
- **Lỗi đọc state store:** executor phải gọi `StateStoreCoordinator` trên driver. Phiên Spark chưa từng chạy query luồng (như phiên của 10c) thì chưa có endpoint này, và `format("statestore")` báo `CANNOT_LOAD_STATE_STORE`. Gọi `spark.streams.active` trước khi đọc là hết lỗi.
- **Tùy chọn của file source:** `maxBytesPerTrigger` là số byte nguyên và không đặt cùng `maxFilesPerTrigger` được. Bài đo thông lượng dùng `maxFilesPerTrigger 2`. Query lỗi thì `10_stream.py` thoát với mã 1, để 10c / 10d dừng ngay.
- **Đổi tên:** `api/bench_stream.py` trong bản thiết kế được gộp vào `src/10d_stream_bench.py`; nó gọi E25 qua mạng Docker (`http://api:8000`). Khóa đáp án trong `stream_prep_report.json` là `expected`, không dùng `truth`, để khỏi lẫn với persona thật.

**Kết quả chính** (dữ liệu hành vi mô phỏng; chi tiết trong `stream_report.json`):
- **10c (tốc độ 300, trigger 1 giây, 06:00–24:00, 92.302 sự kiện, đáp án 205.920 ô): cả 3 kịch bản đạt.**
  - s1: khớp tuyệt đối;
  - s2: khớp tuyệt đối (2.757 sự kiện trễ 1–8 phút, 180 bản gửi lặp);
  - s3: không ô nào vượt đáp án; thiếu 960 lượt (cửa sổ, sự kiện), ít hơn 996 lượt cửa sổ của 249 sự kiện bị giữ. Bước khử trùng bỏ 255 dòng, bước tổng hợp bỏ 0.
- **Độ trễ (10d)** = sự kiện mới nhất trong batch:

  | Lần đo | Sự kiện → MongoDB (p50 / p95) | Sự kiện → API (p50 / p95) | Batch vượt trigger |
  |---|---|---|---|
  | Tốc độ 60, trigger 5 giây | 2,25 / 2,53 giây | 2,52 / 2,85 giây | 1/38 |
  | Tốc độ 300, trigger 1 giây | 2,21 / 3,32 giây | 3,00 / 3,89 giây | 31/33 |
  | Tốc độ 1.200, trigger 1 giây | 3,31 / 8,39 giây | 3,87 / 8,75 giây | 17/17 |

  Mục tiêu p95 sự kiện → API ≤ 15 giây ở tốc độ 60: đạt.
- **Thông lượng (7 ngày, 490.570 dòng, ghi sẵn 15 file):** khoảng 4.600 dòng/giây, như nhau với 2 và 4 core (4.654 so với 4.543). Nút thắt là sink chạy trên driver:
  - 1,16 triệu lượt upsert ô vào MongoDB mất 66,4 giây trên 105,3 giây;
  - phần Spark tính và gom về driver (`collect`) mất 30,0 giây (khoảng 16.000 sự kiện/giây).
  
  Thêm core không giúp gì. Muốn nhanh hơn thì phải ghi song song từ executor (`foreachPartition`, như bước 07) hoặc chỉ ghi các ô có `cooks` > 0.

**Bổ sung 26/10 (chiều): kiểm tra replayer, phụ thuộc vào optimizer, đánh giá luồng, tách thời gian sink.**
- **Tick cuối phát sau mọi sự kiện bị giữ: đã đúng, không sửa.** `10b_replayer.py` chỉ ghi tick cuối (ts = giờ kết thúc + 75 phút) sau khi vòng phát đã đẩy hết `items`, mà `items` gồm cả sự kiện bị giữ 20–40 phút (thời điểm phát của chúng có thể sau giờ kết thúc). Lần chạy s3 của 10c (`check_s3_1026_055228`) xác nhận: 7 sự kiện bị giữ phát sau 24:00, nằm ở các batch 203–208; tick cuối là batch 209, batch có dữ liệu cuối cùng. Vì vậy không chạy lại s3.
  - Trong batch 203–208 watermark đứng ở 23:49:59 (hết tick phút sau 24:00), nên sự kiện bị giữ có ts ≥ 23:50 vẫn được đếm (batch 208: 2 sự kiện ts 23:55). Đây là lý do thứ hai khiến phần thiếu ở s3 nhỏ hơn số lượt cửa sổ của sự kiện bị giữ (960 < 996), cùng với khoảng nhận trễ theo batch đã nêu ở trên.
- **Thứ tự "lọc sau khử trùng" dựa vào hành vi của optimizer Spark 4.2.0, không phải một bảo đảm của API.** Bài thử 10t cho thấy Catalyst đẩy phép lọc không dùng `ts` xuống dưới `EventTimeWatermark`, còn phép khử trùng có trạng thái thì chặn việc đó. Phiên bản Spark khác có thể đổi quy tắc đẩy phép lọc. Vì vậy `src/10t_stream_semantics.py` là **bài thử hồi quy**: đổi phiên bản Spark (image `vifood-spark`) thì chạy lại 10t; bản dùng phải cho `tick_advances_watermark = true` và F1 đọc 7 dòng (`stream_semantics_report.json`).
- **Đánh giá luồng theo tốc độ phát lại** (số liệu lần đo 10d 26/10, `stream_report.json` → `bench`; dữ liệu `data/stream/runs/bench_*_1026_061435/`):
  - **Tốc độ 60 và 300: bền vững.** Độ trễ sự kiện → MongoDB không tăng dần theo thời gian chạy: chia các batch có dữ liệu thành 3 phần đều nhau, trung vị độ trễ ở tốc độ 300 là 2,36 / 2,38 / 1,95 giây (đầu / giữa / cuối), ở tốc độ 60 là 2,30 / 2,12 / 2,21 giây. Ở tốc độ 300, 31/33 batch chạy quá trigger 1 giây nhưng Spark gom nhiều file hơn vào batch sau và vẫn theo kịp: tốc độ xử lý (p50 854 dòng/giây) ngang tốc độ đến.
  - **Tốc độ 1.200: đã chạm trần.** Mọi batch đều chạy quá trigger (17/17, thời gian batch p50 2,59 giây, max 11,23 giây); tốc độ xử lý bị chặn quanh 3.500 dòng/giây (p95 3.442, max 3.500) trong khi giờ cao điểm đến tới 4.704 dòng/giây, nên mỗi batch phải gom phần dồn lại của batch trước. Độ trễ p95 lên 8,39 giây (so với 3,32 giây ở tốc độ 300). Trần này do sink một luồng trên driver (xem mục thông lượng), không phải do Spark tính.
- **Tách thời gian ghi MongoDB trong sink (người dùng chọn: chỉ ghi vào báo cáo, không tối ưu).** `10_stream.py` bấm giờ riêng (a) upsert `trending_cells` (`cells_ms`) và (b) đọc lại ô + tính top 20 / "tăng nhanh" + ghi `trending` (`trending_ms`); `mongo_ms` = (a) + (b) như cũ. 10d cộng lại trong `sink_breakdown_s`. Chạy lại riêng bài đo thông lượng (`10d --only thr_c2,thr_c4`, 26/10 chiều; 7 ngày 21–27/09, 490.570 dòng, 15 file, 2 file mỗi trigger):

  | Core | Dòng/giây (cả lần chạy) | Tổng thời gian batch | collect | (a) upsert ô | (b) top 20 + trending | (a)/(b) | (a) trong phần ghi MongoDB |
  |---|---|---|---|---|---|---|---|
  | 2 | 6.645 | 73,8 giây | 20,5 giây | 36,6 giây | 10,6 giây | 3,45 | 77,5% |
  | 4 | 7.394 | 66,3 giây | 16,5 giây | 34,9 giây | 9,6 giây | 3,64 | 78,5% |

  - Ghi MongoDB vẫn chiếm phần lớn thời gian batch (64% và 67%), trong đó **upsert 1,16 triệu ô** là phần nặng nhất, gấp khoảng 3,5 lần phần tính top 20 và ghi `trending`. Muốn tăng thông lượng thì phải giảm hoặc song song hóa phần (a) trước (ghi từ executor bằng `foreachPartition`, hoặc bỏ các ô không có `cooks`).
  - Lần này nhanh hơn lần đo buổi sáng (4.654 và 4.543 dòng/giây; ghi MongoDB 66,4 và 70,0 giây). Code đọc / tính không đổi, chỉ thêm 2 mốc thời gian; khác biệt nằm chủ yếu ở phần ghi MongoDB (47,3 so với 66,4 giây ở 2 core), nên số tuyệt đối dao động theo tải của máy giữa các lần chạy. Kết luận về nút thắt không đổi. Với 4 core, phần collect giảm 20,5 → 16,5 giây nên lần này 4 core nhanh hơn 11%, còn phần ghi MongoDB gần như không đổi.

## D19. Kiểm tra tay 100 món: độ chính xác của đặc trưng món (26/10)
Người dùng kiểm tay xong 100 món của mẫu theo hash (D11) trong `data/output/features_check_sample.csv`: cột `kiem_tra` là "đúng" hoặc danh sách thuộc tính sai, `ghi_chu` ghi nhãn đúng. Có 2 bản:
- **bản cuối** `features_check_sample.csv`, chấm sau khi chốt cách chấm `is_spicy`: chỉ coi là cay khi món thật sự cay, không suy ra cay chỉ vì danh sách nguyên liệu có ớt hoặc tiêu;
- **bản lần 1** `features_check_sample_lan1.csv`, chấm trước khi chốt (coi có ớt là cay), còn 10 món chưa kết luận (bỏ khỏi mẫu số, n = 90).

**Quyết định: không sửa luật 03, không chạy lại pipeline.** Các lỗi tìm thấy ghi thành hướng phát triển (PROGRESS). Lý do: mỗi thay đổi luật phải chạy lại 03 → 07 (đặc trưng, sinh hành vi, phân tích, mô hình, MongoDB), và chạy lại 03 sẽ ghi đè file kiểm tra tay. Hai file kiểm tra tay đã commit; không chạy lại 03 khi chưa sao lưu chúng (CLAUDE.md).

**Độ chính xác** (`scripts/eval_features_check.py` → `data/output/features_check_report.json`; dữ liệu món là món thật):

| Thuộc tính | Bản cuối (n = 100) | Bản lần 1 (n = 90) |
|---|---|---|
| `main_protein` | 90,0% | 92,2% |
| `main_method` | **79,0%** | 85,6% |
| `dish_category` | 95,0% | 93,3% |
| `dish_type_fixed` | 97,0% | 96,7% |
| `is_vegetarian` | 90,0% | 88,9% |
| `is_spicy` | 99,0% | 58,9% |
| `is_spicy`, cách (b) (ước tính) | 84,0% | – |
| `season` | 99,0% (chỉ 27/100 món khác "không") | 100,0% |
| Món đúng cả 7 thuộc tính | **59%** | 33,3% |
| Món đúng 6 thuộc tính, bỏ `season` / bỏ `is_spicy` | 60% / 60% | 33,3% / 66,7% |

- Bản cuối: 59 món đúng hết, 33 món sai 1 thuộc tính, 6 món sai 2, 2 món sai 3. Trung bình 7 thuộc tính 92,7%.
- `is_spicy` của bản lần 1 thấp (58,9%) chỉ vì cách chấm khác (có ớt là cay), không phải luật đổi: nhãn của máy giống hệt nhau ở hai bản.
- **`is_spicy` cách (b), định nghĩa mở rộng, ước tính tự đếm từ `nguyen_lieu`, chưa kiểm từng món:** cay nếu có ớt tươi ("ớt" đứng riêng, ớt băm, ớt sừng, ớt hiểm, ớt trái), ớt khô, ớt bột, sa tế, kim chi; không tính ớt chuông, tương ớt, tiêu, mù tạt vàng. Theo (b) có 29 món cay, máy gắn cay 17 món; lệch 16 món:
  - 14 món máy ghi không cay nhưng có ớt (dòng 2, 20, 37, 39, 43, 45, 49, 55, 57, 81, 83, 94, 95, 97);
  - 1 món máy ghi cay nhưng chỉ có ớt chuông (dòng 76, Vịt Xào Ớt Chuông);
  - 1 món máy ghi cay nhưng không có nguyên liệu cay nào, chỉ có mù tạt vàng (dòng 89, Salad cam tình yêu). Món này người kiểm cũng chấm sai ở bản cuối.

**Chốt cách báo cáo (người dùng, 26/10):** số chính theo món là **đúng cả 7 thuộc tính, 59%**; ghi thêm **60% khi bỏ `season`** vì mẫu `season` nhỏ (27/100 món khác "không"). `is_spicy` cách (b) tính cả dòng 89: **84,0%, 16 lỗi**.

**Phát hiện (không sửa, xem hướng phát triển trong PROGRESS):**
- **`is_spicy`:**
  - bỏ sót ớt tươi đứng riêng: `SPICY_ING` chỉ có ớt bột, ớt khô, ớt hiểm, ớt xiêm, dầu ớt…, không có "ớt", "ớt băm", "ớt sừng";
  - nhận nhầm ớt chuông khi tên món có chữ "ớt" (`SPICY_NAME` có "ớt", dòng 76);
  - nhận nhầm mù tạt vàng (`SPICY_ING` có "mù tạt", dòng 89).
- **`is_vegetarian`:** cả 10 lỗi đều là máy ghi "chay" cho món có sản phẩm từ động vật mà luật không xét: mật ong (4 món), sữa / sữa đặc / sữa chua / sữa tươi, bơ, kem / whipping cream, phô mai, gelatine, mayonnaise. D05 định nghĩa chay là "không có nguyên liệu động vật", nhưng danh sách `ANIMAL` chỉ gồm thịt, cá, trứng, nước mắm, mỡ… Danh sách có "gelatin", nhưng luật khớp theo ranh giới từ nên không nhận "gelatine".
  - Hạt nêm không ghi "chay" không rõ nguồn gốc (thường có chiết xuất thịt), nhưng luật coi là chay (dòng 37). Người kiểm vẫn chấm đúng vì nhãn nguyên liệu không đủ để kết luận.
- **`season`:** luật gán "nóng" cho mọi món có chữ "trà" (và nước ép, sinh tố…) thuộc nhóm đồ uống, kể cả trà uống ấm (dòng 25, Trà Quế Hồng Táo, đúng là "lạnh"); chỉ "trà gừng" được tách sang "lạnh". Chỉ 27/100 món có mùa khác "không" (nóng 17, lạnh 7, tết 3), nên độ chính xác 99% của `season` có độ tin cậy thấp.
- **`main_method` thấp nhất (79%)**, vì luật chỉ dựa vào tên món và nguyên liệu, không có các bước nấu.
  - Trong 21 lỗi, 10 món đúng ra là "khác": món cuốn, nhúng, ngâm, làm lạnh, không nấu (luật gán luộc 4 lần, hấp 2 lần…);
  - 4 món đúng ra là "chiên" (vd hành phi, bánh nhãn);
  - 4 lỗi còn lại nhầm giữa hầm/nấu, luộc, kho/rim, pha/xay;
  - 3 món đúng ra là "nướng" (pizza, cuốn lá lốt nướng, bánh trung thu).
- **Bộ nhãn thiếu nhóm:** gia vị / xốt (vd Sa Tế Tỏi Ớt phải tạm xếp nhóm "lẩu", cách làm "pha/xay"), cuốn (sushi, gỏi cuốn → "khác"), ủ / ngâm (mắm tép đu đủ → "khác"). Người kiểm dùng nhãn có sẵn gần nhất, không thêm nhãn mới.
- Các lỗi khác (ít): đạm chính chọn theo nguyên liệu phụ (trứng trong bột áo, trứng trong thịt kho); bánh trung thu nhân thập cẩm và kem trái cây bị xếp món mặn / món chính.
