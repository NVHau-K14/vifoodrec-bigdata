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
