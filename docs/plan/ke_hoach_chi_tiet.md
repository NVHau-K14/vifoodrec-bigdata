**KẾ HOẠCH CHI TIẾT THỰC HIỆN ĐỒ ÁN**

Môn Nhập môn Big Data

**Đề tài: PHÂN TÍCH HÀNH VI ĂN UỐNG VÀ GỢI Ý MÓN ĂN**

*Nhóm: Nguyễn Văn Hậu – Hứa Quách Như Ngọc*

# **1. Các quyết định đã thống nhất**

|                     |                                                                                                                                                                |
| ------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Hạng mục**        | **Quyết định**                                                                                                                                                 |
| Đề tài              | Phân tích hành vi ăn uống và gợi ý món ăn (đề tài tự đề xuất, đã được duyệt)                                                                                   |
| Dữ liệu             | ViFoodRec (thuần tiếng Việt): foods.csv 4.000 món + 2 file thô Cooky (4.296 món) và Món Ngon Mỗi Ngày (1.213 món) + ratings.csv gốc (182.678 dòng, 101 user)   |
| Hướng xử lý dữ liệu | Hướng C: giữ ViFoodRec làm kho món ăn, tự sinh dữ liệu hành vi người dùng có cấu trúc (mô phỏng) ở quy mô lớn; ratings gốc giữ lại để làm thí nghiệm đối chứng |
| Lưu trữ             | HDFS (dữ liệu thô, dữ liệu đã xử lý dạng Parquet, dữ liệu hành vi) + MongoDB (dữ liệu phục vụ dashboard: món ăn, kết quả gợi ý, thống kê)                      |
| Xử lý               | Apache Spark (PySpark): Spark SQL/DataFrame, Spark MLlib (ALS, TF-IDF, LSH, FP-Growth, K-means), Structured Streaming (phần nâng cao)                          |
| Mô hình gợi ý       | Hybrid: lọc cộng tác ALS + gợi ý theo nội dung (TF-IDF/LSH) + độ phổ biến theo ngữ cảnh; có bộ lọc chay/calo/thời gian nấu và xử lý cold-start                 |
| Sản phẩm demo       | Dashboard HTML/CSS/JavaScript (ECharts) + API Python (FastAPI) đọc MongoDB; có mục gợi ý món ăn ngay trên dashboard. Không dùng Streamlit.                     |
| Môi trường          | Windows 11 25H2, RAM 24GB, Docker Desktop (WSL2)                                                                                                               |
| Phân công           | Chia đều 50/50 giữa Nguyễn Văn Hậu và Hứa Quách Như Ngọc                                                                                                       |
| Mục tiêu            | Điểm tối đa: làm đầy đủ phần hybrid và các phần nâng cao                                                                                                       |

# **2. Nhận xét bộ dữ liệu và cách xử lý**

## **2.1. Kết quả kiểm tra ban đầu**

  - **Phần văn bản là dữ liệu thật** (tên món, mô tả, nguyên liệu, cách
    làm, tags, link ảnh) cào từ Cooky và Món Ngon Mỗi Ngày. Đây là tài
    sản chính của đồ án.

  - **Ratings gốc là nhiễu ngẫu nhiên:** 11 mức điểm 0–5 phân bố đều
    (\~16.500 lượt mỗi mức); điểm trung bình mọi user ≈ 2,5 (độ lệch
    0,04); chia đôi dữ liệu thì điểm trung bình từng món giữa hai nửa có
    tương quan −0,03; tương quan giữa các user ≈ 0,03.

  - **Chỉ số dinh dưỡng là số ngẫu nhiên:** calories phân bố đều 180–600
    và không tương quan với fat/protein (r ≈ 0), trái với thực tế.

  - **Nhãn dish\_type không đáng tin:** chỉ có Món mặn/Món chay, nhiều
    món uống, món ngọt bị gán “Món mặn”.

  - **Lỗi nhỏ:** foodId = 4000 xuất hiện 47 lần trong ratings nhưng
    không có trong foods.csv; 103 tên món bị trùng.

  - **Quy mô nhỏ** (\~20MB, 101 user), không có timestamp/ngữ cảnh →
    chưa thể hiện được tính chất Big Data và “hành vi”.

## **2.2. Cách biến điểm yếu thành điểm cộng**

  - **Thí nghiệm đối chứng:** chạy ALS trên ratings gốc, so với baseline
    ngẫu nhiên → chứng minh bằng số liệu rằng dữ liệu gốc không có tín
    hiệu (RMSE ≈ 1,58 = độ lệch chuẩn phân phối đều). Đây là phần “đánh
    giá chất lượng dữ liệu” rất thuyết phục khi phản biện.

  - **Sinh dữ liệu hành vi có cấu trúc** dựa trên đặc trưng thật của món
    ăn (nguyên liệu, cách nấu, tags) → mô hình có tín hiệu để học, và vì
    biết “sự thật gốc” (khẩu vị thật của từng user mô phỏng) nên có thể
    kiểm chứng mô hình có học đúng hay không.

  - **Ghi rõ trong báo cáo** đâu là dữ liệu thật, đâu là dữ liệu mô
    phỏng, lý do và giới hạn. Không trình bày dữ liệu mô phỏng như dữ
    liệu thật.

  - **Dinh dưỡng:** chỉ dùng để lọc và minh họa, không rút ra kết luận
    dinh dưỡng; nêu trong phần hạn chế.

**Khuyến nghị:** nhắn giảng viên một tin ngắn rằng nhóm giữ nguyên đề
tài và dữ liệu ViFoodRec, nhưng bổ sung dữ liệu hành vi mô phỏng vì
ratings gốc không có tín hiệu. Có xác nhận trước sẽ an toàn hơn khi bảo
vệ.

# **3. Thiết kế bộ dữ liệu hành vi mô phỏng**

## **3.1. Làm giàu đặc trưng món ăn (từ dữ liệu thật)**

  - **Nhóm đạm chính:** gà, bò, heo, vịt, cá, tôm/mực/hải sản, trứng,
    đậu hũ/chay… (trích từ nguyên liệu + tags bằng từ điển từ khóa).

  - **Cách chế biến:** chiên, xào, hấp, luộc, nướng, kho, rim, hầm,
    trộn/gỏi…

  - **Nhóm món:** canh/súp, lẩu, món kho, món xào, bánh, chè/tráng
    miệng, đồ uống, gỏi/salad, cháo, bún/phở/mì…

  - **Cờ đặc tính:** món chay (sửa lại từ tags/nguyên liệu), cay, món
    nhanh (≤ 20 phút), món Tết/món mùa lạnh/món mùa nóng.

  - **Kết quả:** bảng dish\_features (Parquet trên HDFS), dùng chung cho
    phân tích, sinh dữ liệu và mô hình content-based.

## **3.2. Người dùng mô phỏng**

Quy mô đề xuất: **50.000 người dùng**, mỗi người thuộc một “persona”
(nhóm khẩu vị) cộng thêm sai khác cá nhân:

|                       |                                                           |
| --------------------- | --------------------------------------------------------- |
| **Persona**           | **Đặc điểm sở thích**                                     |
| Người ăn chay         | Rất thích món chay, gần như không chọn món có thịt        |
| Tập gym               | Ưu tiên món giàu đạm (gà, bò, trứng), ít đồ ngọt          |
| Ăn kiêng              | Ưu tiên món ít calo, hấp/luộc/gỏi, tránh chiên            |
| Mê hải sản            | Ưu tiên tôm, mực, cá, lẩu hải sản                         |
| Người bận rộn         | Ưu tiên món nấu nhanh, ít bước                            |
| Hảo ngọt              | Thích chè, bánh, đồ uống                                  |
| Gia đình truyền thống | Cơm nhà: canh, kho, xào; nấu nhiều vào bữa tối, cuối tuần |
| Thích món cay/nhậu    | Món cay, nướng, lẩu, cuối tuần và buổi tối                |

Thuộc tính người dùng: nhóm tuổi, vùng miền (Bắc/Trung/Nam), giới tính,
ngày đăng ký. Persona thật được lưu riêng làm “sự thật gốc” để kiểm
chứng.

## **3.3. Sự kiện hành vi**

  - **Loại sự kiện:** view (xem), favorite (lưu), cook (nấu), rate (chấm
    điểm 0,5–5).

  - **Thời gian:** 12 tháng; có khung bữa (sáng/trưa/tối/khuya), ngày
    trong tuần, mùa (lẩu tăng mùa lạnh, chè tăng mùa nóng, món Tết tăng
    tháng 1–2).

  - **Cách sinh:** điểm hợp khẩu vị = trọng số persona × đặc trưng món +
    thưởng theo ngữ cảnh thời gian + độ phổ biến (phân phối Zipf) +
    nhiễu; chọn món bằng lấy mẫu softmax; điểm rating suy ra từ điểm
    hợp khẩu vị.

  - **Phễu hành vi:** view nhiều → favorite ít hơn → cook ít hơn → rate
    ít nhất (giống thực tế).

  - **Quy mô mục tiêu:** \~20–30 triệu sự kiện (khoảng 1,5–3GB CSV),
    chia partition theo tháng trên HDFS. Có tham số để tăng/giảm quy mô.

  - **Sinh bằng chính Spark** (sinh phân tán theo partition) để thể hiện
    xử lý song song, kèm seed cố định để tái lập kết quả.

# **4. Kiến trúc hệ thống và luồng dữ liệu**

## **4.1. Các container Docker**

|                              |                                                  |                 |
| ---------------------------- | ------------------------------------------------ | --------------- |
| **Dịch vụ**                  | **Vai trò**                                      | **RAM dự kiến** |
| namenode                     | Quản lý metadata HDFS                            | 1GB             |
| datanode1, datanode2         | Lưu block dữ liệu, replication = 2               | 1GB × 2         |
| spark-master                 | Điều phối job Spark                              | 1GB             |
| spark-worker1, spark-worker2 | Thực thi job (mỗi worker 2 core, 3GB)            | 3–4GB × 2       |
| jupyter (pyspark)            | Viết và chạy notebook, nộp job lên Spark cluster | 2GB             |
| mongodb (+ mongo-express)    | Lưu dữ liệu phục vụ dashboard                    | 1GB             |
| api (FastAPI) + web tĩnh     | Cung cấp API và trang dashboard HTML             | 0,5GB           |

Tổng khoảng 14–16GB. Cần cấu hình file .wslconfig cho WSL2 dùng tối đa
\~16GB RAM để Windows còn đủ bộ nhớ.

## **4.2. Luồng dữ liệu**

  - **Bước 1 – Nạp:** CSV thô (Cooky, MNMN, foods, ratings) → HDFS
    /data/raw.

  - **Bước 2 – Làm sạch (Spark):** chuẩn hóa Unicode tiếng Việt (NFC),
    bỏ khoảng trắng thừa, tách danh sách nguyên liệu và bỏ định lượng,
    chuẩn hóa khẩu phần sang số người, gộp 2 nguồn và khử trùng lặp theo
    tên món đã chuẩn hóa, sửa nhãn chay, loại foodId không tồn tại →
    /data/curated (Parquet).

  - **Bước 3 – Làm giàu đặc trưng:** sinh dish\_features (mục 3.1).

  - **Bước 4 – Sinh dữ liệu hành vi:** users + events → /data/events
    (Parquet, partition theo tháng).

  - **Bước 5 – Phân tích hành vi (Spark SQL):** tổng hợp theo thời gian,
    bữa, mùa, vùng miền, persona.

  - **Bước 6 – Mô hình:** ALS, content-based, FP-Growth, K-means,
    hybrid; đánh giá.

  - **Bước 7 – Xuất kết quả:** ghi vào MongoDB (foods, recommendations,
    similar\_dishes, stats, rules, segments, metrics).

  - **Bước 8 – Phục vụ:** FastAPI đọc MongoDB → dashboard HTML/ECharts.

  - **Nâng cao – Streaming:** Spark Structured Streaming đọc các file sự
    kiện mới đổ vào HDFS /data/stream, cập nhật “món đang thịnh hành”
    theo cửa sổ thời gian vào MongoDB, dashboard tự làm mới.

# **5. Phân tích và mô hình**

## **5.1. Phân tích hành vi ăn uống**

  - Món/nhóm món phổ biến theo khung bữa, ngày trong tuần, tháng, mùa.

  - Khác biệt khẩu vị theo vùng miền, nhóm tuổi.

  - Phễu xem → lưu → nấu → chấm điểm; tỷ lệ chuyển đổi theo nhóm món.

  - Phân bố calo, thời gian nấu, cách chế biến của các món được nấu
    nhiều.

  - Thống kê nguyên liệu phổ biến, nguyên liệu hay đi cùng nhau.

## **5.2. Các mô hình**

|                      |                                                                                                                                                                            |                                                              |
| -------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------ |
| **Mô hình**          | **Kỹ thuật Spark**                                                                                                                                                         | **Mục đích**                                                 |
| Baseline             | Random, Popularity (Spark SQL)                                                                                                                                             | Mốc so sánh bắt buộc                                         |
| Lọc cộng tác         | ALS explicit (rating) và ALS implicit (view/cook/favorite có trọng số); CrossValidator/TrainValidationSplit dò rank, regParam, alpha                                       | Gợi ý theo hành vi người dùng tương tự                       |
| Gợi ý theo nội dung  | Tokenizer tiếng Việt (âm tiết + bigram), StopWords, HashingTF/IDF, chuẩn hóa vector, cosine; BucketedRandomProjectionLSH/MinHashLSH tìm món tương tự                       | Món tương tự, cold-start món mới/user mới                    |
| Luật kết hợp         | FP-Growth trên (1) nguyên liệu của món, (2) “bữa ăn” = các món một user nấu trong cùng ngày                                                                                | Nguyên liệu hay đi cùng; gợi ý món ăn kèm (canh + kho + xào) |
| Phân khúc người dùng | K-means/Bisecting K-means trên đặc trưng hành vi (tần suất, độ đa dạng, tỷ lệ chay, calo trung bình, khung giờ…); Silhouette chọn k                                        | Hiểu nhóm khách hàng; so với persona thật bằng ARI           |
| Hybrid               | Kết hợp có trọng số: α·ALS + β·Content + γ·Popularity theo ngữ cảnh; dò α, β, γ trên tập validation; rơi về content/popularity khi cold-start; lọc chay/calo/thời gian nấu | Mô hình chính của sản phẩm                                   |

## **5.3. Đánh giá**

  - **Chia dữ liệu theo thời gian:** 10 tháng đầu huấn luyện, tháng 11
    validation, tháng 12 kiểm tra (đúng thực tế hơn chia ngẫu nhiên).

  - **Độ đo dự đoán điểm:** RMSE, MAE.

  - **Độ đo xếp hạng:** Precision@K, Recall@K, NDCG@K, MAP@K (K = 5,
    10).

  - **Độ đo chất lượng gợi ý:** độ phủ danh mục (coverage), độ đa dạng,
    độ mới (novelty).

  - **Phân cụm:** Silhouette, ARI so với persona thật.

  - **Thí nghiệm đối chứng:** ALS trên ratings gốc ViFoodRec vs baseline
    ngẫu nhiên.

  - **Hiệu năng Big Data:** thời gian chạy với 1 vs 2 worker, các mức dữ
    liệu 10%/50%/100%, số partition; ảnh chụp Spark UI và HDFS UI.

# **6. Dashboard HTML**

|                           |                                                                                                                                                                  |
| ------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Trang**                 | **Nội dung**                                                                                                                                                     |
| Tổng quan                 | Thẻ số liệu (số món, user, sự kiện, dung lượng HDFS), sơ đồ kiến trúc, tình trạng pipeline                                                                       |
| Hành vi ăn uống           | Heatmap giờ × thứ, xu hướng theo tháng/mùa, top món theo bữa, so sánh vùng miền, phễu chuyển đổi                                                                 |
| Món ăn & dinh dưỡng       | Phân bố nhóm món, cách chế biến, nguyên liệu phổ biến, đồ thị mạng nguyên liệu từ FP-Growth                                                                      |
| Phân khúc người dùng      | Biểu đồ các cụm, đặc trưng từng cụm, đề xuất chiến lược                                                                                                          |
| Gợi ý món ăn              | Chọn user có sẵn hoặc chọn vài món mình thích (user mới) → danh sách món gợi ý có ảnh, lý do gợi ý, món tương tự, món ăn kèm; bộ lọc chay/calo/thời gian nấu/bữa |
| Đánh giá mô hình          | Bảng và biểu đồ so sánh các mô hình, thí nghiệm đối chứng, hiệu năng Spark                                                                                       |
| Thời gian thực (nâng cao) | Món đang thịnh hành cập nhật từ Structured Streaming                                                                                                             |

Công nghệ: HTML + CSS + JavaScript thuần, ECharts cho biểu đồ, gọi
FastAPI qua fetch. Giao diện tiếng Việt, có ảnh món từ image\_link.

# **7. Kế hoạch 10 tuần (theo mẫu của giảng viên)**

Lịch họp nhóm cố định: **tối thứ Hai và tối thứ Năm hằng tuần** (online,
45–60 phút): báo cáo việc đã làm, vướng mắc, giao việc tuần tới; biên
bản họp lưu vào thư mục chung để đưa vào báo cáo.

<table>
<tbody>
<tr class="odd">
<td><strong>Tuần</strong></td>
<td><strong>Công việc</strong></td>
<td><strong>Người phụ trách</strong></td>
<td><strong>Sản phẩm</strong></td>
</tr>
<tr class="even">
<td>1</td>
<td>Chốt đề tài, đăng ký; khảo sát ViFoodRec; lập repo GitHub, thư mục chung</td>
<td>Cả hai</td>
<td>Đề tài đã duyệt; repo</td>
</tr>
<tr class="odd">
<td>2</td>
<td><p>Dựng Docker: HDFS (1 namenode + 2 datanode), Spark (1 master + 2 worker), Jupyter, MongoDB; chạy thử job WordCount</p>
<p>Viết đặc tả dữ liệu, kiểm tra chất lượng dữ liệu gốc (các phép kiểm chứng ở mục 2.1)</p></td>
<td><p>Hậu</p>
<p>Ngọc</p></td>
<td>Cụm chạy được; báo cáo chất lượng dữ liệu</td>
</tr>
<tr class="even">
<td>3</td>
<td>Lập kế hoạch chi tiết, phân vai; thiết kế kiến trúc và luồng dữ liệu</td>
<td>Cả hai</td>
<td>Bản kế hoạch; sơ đồ kiến trúc</td>
</tr>
<tr class="odd">
<td>4</td>
<td><p>Lý thuyết HDFS, MapReduce, Spark (RDD/DataFrame/SQL), MongoDB</p>
<p>Lý thuyết hệ gợi ý: ALS, TF-IDF, cosine, LSH, FP-Growth, K-means, độ đo</p></td>
<td><p>Hậu</p>
<p>Ngọc</p></td>
<td>Tài liệu tóm tắt lý thuyết</td>
</tr>
<tr class="even">
<td>5</td>
<td><p>Nạp dữ liệu lên HDFS; pipeline làm sạch; làm giàu đặc trưng món</p>
<p>EDA trên dữ liệu món ăn; ví dụ minh họa TF-IDF, FP-Growth trên dữ liệu nhỏ</p></td>
<td><p>Hậu</p>
<p>Ngọc</p></td>
<td>Dữ liệu curated (Parquet); notebook EDA; ví dụ minh họa</td>
</tr>
<tr class="odd">
<td>6</td>
<td><p>Bộ sinh dữ liệu hành vi bằng Spark; ALS baseline + thí nghiệm đối chứng</p>
<p>Phân tích hành vi bằng Spark SQL; content-based baseline; popularity baseline</p></td>
<td><p>Hậu</p>
<p>Ngọc</p></td>
<td>Dữ liệu events trên HDFS; kết quả baseline</td>
</tr>
<tr class="even">
<td>7</td>
<td>Đánh giá sơ bộ, xác định điểm cần cải thiện; <strong>nộp báo cáo tiến độ Giai đoạn 1</strong></td>
<td>Cả hai</td>
<td>Bảng kết quả baseline; báo cáo tiến độ</td>
</tr>
<tr class="odd">
<td>8</td>
<td><p>Dò tham số ALS implicit, hybrid, xử lý cold-start; Structured Streaming; ghi kết quả vào MongoDB; FastAPI</p>
<p>FP-Growth, K-means phân khúc; dashboard HTML các trang phân tích và gợi ý</p></td>
<td><p>Hậu</p>
<p>Ngọc</p></td>
<td>Mô hình hoàn chỉnh; API; dashboard</td>
</tr>
<tr class="even">
<td>9</td>
<td><p>Đo hiệu năng Spark; hướng dẫn cài đặt/chạy; viết chương Cơ sở lý thuyết, Xây dựng ứng dụng (phần hệ thống)</p>
<p>Hoàn thiện dashboard; viết Giới thiệu, Trực quan hóa, Kết luận; làm slide</p>
<p>Rà soát chéo báo cáo; <strong>nộp Giai đoạn 2</strong></p></td>
<td><p>Hậu</p>
<p>Ngọc</p>
<p>Cả hai</p></td>
<td>Mã nguồn, báo cáo Word, slide đã nộp</td>
</tr>
<tr class="odd">
<td>10</td>
<td>Tập thuyết trình, chia phần nói, chuẩn bị câu hỏi phản biện; thuyết trình và demo</td>
<td>Cả hai</td>
<td>Buổi thuyết trình hoàn chỉnh</td>
</tr>
</tbody>
</table>

# **8. Kế hoạch làm dồn thực tế (2 ngày code, sau đó viết báo cáo)**

Làm song song, mỗi người khoảng 6 giờ/ngày. Mọi công đoạn vẫn giữ đủ,
chỉ dồn lại. Claude có thể viết sẵn khung mã cho từng bước để rút ngắn
thời gian.

|                |                                                                                |                                                                                              |                                            |
| -------------- | ------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------- | ------------------------------------------ |
| **Buổi**       | **Hậu**                                                                        | **Ngọc**                                                                                     | **Mốc kiểm tra**                           |
| Ngày 1 – Sáng  | docker-compose: HDFS, Spark, Jupyter, MongoDB; cấu hình WSL2; nạp CSV lên HDFS | Kiểm tra chất lượng dữ liệu gốc; viết từ điển từ khóa (đạm, cách chế biến, nhóm món, cờ mùa) | HDFS UI, Spark UI hiển thị; file trên HDFS |
| Ngày 1 – Chiều | Pipeline làm sạch + làm giàu đặc trưng → Parquet                               | EDA dữ liệu món; thiết kế bảng persona và trọng số                                           | dish\_features hoàn chỉnh                  |
| Ngày 1 – Tối   | Bộ sinh dữ liệu hành vi (chạy thử 1%, rồi 100%)                                | Notebook phân tích hành vi bằng Spark SQL; xuất thống kê                                     | \~20–30 triệu sự kiện trên HDFS            |
| Ngày 2 – Sáng  | Baseline, ALS explicit/implicit, thí nghiệm đối chứng, dò tham số              | Content-based TF-IDF + LSH; FP-Growth; K-means                                               | Bảng độ đo đầu tiên                        |
| Ngày 2 – Chiều | Hybrid + cold-start + bộ lọc; ghi MongoDB; FastAPI                             | Dashboard HTML: các trang phân tích                                                          | API trả kết quả                            |
| Ngày 2 – Tối   | Structured Streaming (nâng cao); đo hiệu năng                                  | Trang gợi ý món + trang đánh giá; ráp với API                                                | Demo chạy đầu-cuối                         |
| Ngày 3 trở đi  | Viết báo cáo phần hệ thống, lý thuyết Big Data, hướng dẫn chạy                 | Viết báo cáo phần phân tích, trực quan hóa, kết luận; slide                                  | Báo cáo + slide                            |

**Rủi ro thực tế:** phần dashboard và streaming dễ tràn sang ngày 3. Nếu
thiếu thời gian, ưu tiên theo thứ tự: pipeline HDFS/Spark → ALS +
content + hybrid + đánh giá → dashboard → FP-Growth/K-means → streaming.

# **9. Phân công chi tiết (50/50)**

|              |                                                              |                                                                       |
| ------------ | ------------------------------------------------------------ | --------------------------------------------------------------------- |
| **Mảng**     | **Nguyễn Văn Hậu**                                           | **Hứa Quách Như Ngọc**                                                |
| Hạ tầng      | Docker, HDFS, Spark cluster, MongoDB, FastAPI                | Cấu hình máy cá nhân chạy theo hướng dẫn, kiểm thử hướng dẫn cài đặt  |
| Dữ liệu      | Nạp HDFS, pipeline làm sạch, bộ sinh dữ liệu hành vi         | Kiểm tra chất lượng dữ liệu, từ điển đặc trưng, thiết kế persona, EDA |
| Phân tích    | Đo hiệu năng Spark                                           | Phân tích hành vi bằng Spark SQL                                      |
| Mô hình      | Baseline, ALS, thí nghiệm đối chứng, hybrid, streaming       | Content-based, LSH, FP-Growth, K-means                                |
| Đánh giá     | Độ đo RMSE/MAE, Precision/Recall/NDCG cho ALS và hybrid      | Coverage/đa dạng, Silhouette/ARI, độ đo cho content-based             |
| Sản phẩm     | API, kết nối dữ liệu MongoDB                                 | Dashboard HTML/ECharts, trang gợi ý món                               |
| Báo cáo      | Cơ sở lý thuyết Big Data, kiến trúc, mô hình, hướng dẫn chạy | Giới thiệu, dữ liệu, phân tích hành vi, trực quan hóa, kết luận       |
| Thuyết trình | Kiến trúc, mô hình, demo hệ thống                            | Bài toán, dữ liệu, kết quả phân tích, demo dashboard                  |

# **10. Cấu trúc mã nguồn dự kiến**

  - docker/ – docker-compose.yml, cấu hình Hadoop/Spark, .wslconfig mẫu

  - data/ – dữ liệu gốc ViFoodRec (hoặc script tải)

  - src/ingest – nạp dữ liệu lên HDFS

  - src/etl – làm sạch, làm giàu đặc trưng

  - src/simulate – sinh users và events

  - src/analysis – phân tích hành vi Spark SQL

  - src/models – baseline, als, content, fpgrowth, kmeans, hybrid,
    evaluate

  - src/streaming – Structured Streaming

  - src/export – ghi MongoDB

  - api/ – FastAPI

  - web/ – dashboard HTML/CSS/JS

  - notebooks/ – notebook minh họa từng bước

  - README.md – hướng dẫn cài đặt và chạy từ đầu đến cuối

# **11. Câu hỏi phản biện cần chuẩn bị**

  - Vì sao dữ liệu \~20MB mà dùng HDFS/Spark? → Dữ liệu món là gốc, dữ
    liệu hành vi hàng chục triệu sự kiện mới là phần lớn; kiến trúc mở
    rộng ngang được; có số đo hiệu năng.

  - Vì sao dùng dữ liệu mô phỏng? → Có bằng chứng định lượng ratings gốc
    là ngẫu nhiên; mô phỏng dựa trên đặc trưng thật; biết sự thật gốc
    nên kiểm chứng được mô hình.

  - Mô hình có “gian lận” vì dữ liệu do nhóm tự sinh? → Mô hình không
    thấy persona; tách theo thời gian; có nhiễu; nêu rõ giới hạn.

  - Vì sao hybrid tốt hơn từng mô hình riêng? → Bảng so sánh độ đo;
    cold-start.

  - Vì sao dùng thêm MongoDB? → Dữ liệu dạng document (món ăn có danh
    sách nguyên liệu, tags), truy vấn nhanh cho dashboard; HDFS cho lưu
    trữ khối lớn và xử lý theo lô.

  - Hạn chế: dinh dưỡng gốc không chính xác, dữ liệu hành vi là mô
    phỏng, chạy trên một máy (giả lập cụm).
