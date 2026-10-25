# Lần chạy gần nhất – 26/10/2026

> File này được **ghi đè sau mỗi lần làm xong một yêu cầu** (xem quy tắc trong CLAUDE.md).
> Người dùng đọc nó ở bên chat claude.ai. Giữ đúng các mục bên dưới, không giới hạn độ dài.
> Dữ liệu hành vi là **mô phỏng**. Số liệu lấy từ `data/output/*_report.json` và Spark History Server (event log trong `logs/spark-events/`).
> Phần đo hiệu năng dưới đây là **bản đề xuất, chưa chạy**. Mọi con số "dự kiến" là ước tính từ thời gian đã đo, ghi rõ là ước tính.

## Yêu cầu
Trả lời 3 câu hỏi của lần trước:
1. Giữ bảng luật cụm, nhưng sửa:
   - `cook_per_view` cao hiển thị là "Hay nấu sau khi xem" (nhãn cụm 4 thành "Hay nấu sau khi xem · nhiều canh/súp");
   - mỗi cụm chỉ giữ đề xuất đặc trưng nhất, không lặp câu "Người dùng tích cực…" ở nhiều cụm;
   - cập nhật D16 và test liên quan.
2. E16 giữ đọc MongoDB mỗi lần.
3. Bước tiếp theo là **đo hiệu năng Spark**, theo kiểu thiết kế trước: viết đề xuất vào LAST_RUN, **chưa chạy**. Sau đó mới đến Structured Streaming.

## Đã làm
**Câu 1 – nhãn và đề xuất cụm** (`api/labels.py`, `api/routers/segments.py`):
- `cook_per_view` cao: "hay nấu sau khi xem" (trước là "xem là nấu").
- **Mỗi cụm 1 câu đề xuất, không cụm nào trùng câu với cụm khác trong cùng k.** Hàm mới `describe_clusters()`:
  - gom mọi cặp (cụm, câu ứng viên), chỉ lấy đặc trưng có |z| ≥ 0,5 khớp bảng luật;
  - xếp theo |z| giảm dần rồi gán tham lam: cụm lệch mạnh nhất ở một đặc trưng nhận câu của đặc trưng đó, câu đã gán thì cụm sau xét câu kế tiếp;
  - cụm không còn câu nào thì dùng "Giữ gợi ý cá nhân hybrid mặc định" (hiện chưa cụm nào rơi vào trường hợp này).
- Sửa thêm câu luật `share_nhanh`: "Gợi ý món nhanh cho bữa trưa ngày thường" thành "Gợi ý món nhanh, ít bước cho ngày bận rộn". Lý do: cụm k = 8 số 7 có nhãn "nấu bữa tối" nhưng lại nhận câu "bữa trưa".
- Kết quả k = 8:

  | Cụm | Nhãn | Đề xuất | Persona kiểm chứng (chỉ để kiểm chứng) |
  |---|---|---|---|
  | 0 | Nấu bữa trưa · ít phiên | Gửi gợi ý bữa trưa trước giờ nấu trưa | gia đình truyền thống |
  | 1 | Nấu bữa sáng · hoạt động ít | Gửi gợi ý bữa sáng vào đầu ngày | tập gym |
  | 2 | Nấu đa dạng · nhiều phiên | Khẩu vị đa dạng: tăng tỷ trọng món khám phá (content) | mê hải sản |
  | 3 | Nhiều món chay · ít chấm điểm | Ưu tiên bộ sưu tập món chay, thêm món chay mới vào gợi ý | ăn chay |
  | 4 | **Hay nấu sau khi xem** · nhiều canh/súp | Gợi ý mâm cơm: món mặn kèm canh (luật FP-Growth) | gia đình truyền thống |
  | 5 | Nhiều món ngọt, đồ uống · ít hải sản | Gợi ý chè, bánh, đồ uống cho bữa phụ | hảo ngọt |
  | 6 | Hay nấu lẩu · thích cay | Gợi ý lẩu vào cuối tuần | thích cay/nhậu |
  | 7 | Chuộng món nhanh · nấu bữa tối | Gợi ý món nhanh, ít bước cho ngày bận rộn | bận rộn |

  - k = 3 và k = 11 cũng không còn câu trùng.
  - Câu "Người dùng tích cực…" và "Kích hoạt lại…" không còn xuất hiện ở k = 8.
  - "Kích hoạt lại…" chỉ còn là ứng viên phụ, vì cụm 0, 1 lệch mạnh hơn ở bữa nấu.
- **D16** (`docs/DECISIONS.md`): sửa mô tả luật đề xuất, dòng `share_nhanh`, nhãn cụm 4.
- **Test** (`test_consistency.test_segments`): mỗi cụm đúng 1 câu đề xuất, các câu trong cùng k khác nhau. pytest trên `vifood`: **61 đạt**.
- Trang Phân khúc không phải sửa (danh sách đề xuất hiện được cả 1 câu).

**Câu 2:** giữ nguyên E16, không sửa gì.

**Câu 3:** khảo sát rồi viết bản đề xuất đo hiệu năng ở mục "Đề xuất đo hiệu năng Spark" bên dưới. Chưa chạy job nào. Các bước khảo sát:
- đọc tham số dòng lệnh của 02–06, `common.get_spark()`, `Paths`, `rec_common.setup()`;
- đọc cấu hình worker trong compose; `docker info` cho biết máy ảo Docker có 8 CPU, 17,6 GB RAM;
- thời gian từng phần trong các report;
- danh sách ứng dụng và số liệu stage trong History Server.

**Môi trường:** lúc bắt đầu phiên, cả cụm đang tắt. `docker restart api` đã vô tình bật lại `api`, nên tôi bật thêm `mongodb` (để chạy pytest) và `spark-history` (để đọc event log). Cuối phiên đã tắt lại cả 3 container này, cụm trở về trạng thái tắt như lúc đầu.

---

## Đề xuất đo hiệu năng Spark (chưa chạy)

### A. Hiện trạng (khảo sát lần này)
- **Cụm:** 2 worker, mỗi worker `--cores 2 --memory 3g` (container giới hạn 4 GB RAM, không giới hạn CPU), tức 4 khe task. Driver nằm trong `jupyter` (2 GB).
- **Cấu hình Spark** (`get_spark()`): executor 2 GB, `spark.sql.shuffle.partitions = 8`, chưa đặt `spark.cores.max`. Ở Standalone, mỗi worker chạy 1 executor 2 core, nên ứng dụng lấy cả 4 core.
- **Phần cứng thật:** máy chủ có 16 luồng; máy ảo Docker được 8 CPU, 17,6 GB RAM. Mọi container chạy trên **cùng một máy**:
  - shuffle giữa 2 worker đi qua mạng ảo của Docker, không phải mạng thật;
  - HDFS datanode là container riêng, nên cả 1 lẫn 2 worker đều không có data locality.
  Báo cáo phải nêu rõ hai điểm này khi giải thích speedup.
- **Đường dẫn:** `Paths` cố định gốc HDFS `/data` và report ghi vào `data/output/`. Chạy đo hiệu năng mà không sửa thì sẽ ghi đè dữ liệu thật và report thật, và bước 07 / MongoDB sẽ đọc phải kết quả của mức 10%.
- **Tham số:** chỉ 04 có `--scale`. 06b–06g có `--quick` (lưới nhỏ để chạy thử), **chưa có `--fixed`**.
- **History Server REST** (`/api/v1/applications/{id}/stages`) đã thử với 05 (chạy trên cụm ngày 23/10): 250 stage, 836 task, shuffle đọc 337,0 MB / ghi 336,7 MB, spill bộ nhớ 3,76 GB / đĩa 303,5 MB, `executorRunTime` 265,6 giây, GC 7,1 giây. Có cả `shuffleRemoteBytesRead` và `shuffleLocalBytesRead`, nên tách được shuffle qua mạng. API `executors` cho số liệu từng executor (2 executor × 2 core).
- **Thời gian đã đo** (ở 100%, 2 worker; lấy từ `timings_s` / `total_seconds` của report, trừ 03 lấy từ History Server):

  | Job | Tổng | Phần chiếm nhiều thời gian |
  |---|---|---|
  | 02 | **chưa có số** (chạy trước khi bật event log, report không ghi thời gian) | – |
  | 03 | 45,5 giây (History Server, 23/10) | – |
  | 04 | 543,3 giây | – |
  | 05 | 103,7 giây | `load_cache` 28,6 |
  | 06a | 101,3 giây | – |
  | 06b | 2.756,1 giây | `val:als_implicit` 1.972,8 (dò lưới), `test:als_implicit` 505,7 |
  | 06c | 199,5 giây | `minhash` 66,8 (so sánh 3 / 5 / 10 bảng băm) |
  | 06d | 34,3 giây | – |
  | 06e | 315,0 giây | `search_k` 292,0 (22 lần fit) |
  | 06f | 1.385,5 giây | `cold_items` 805,5, `test:explore_beyond` 279,3, `tune_weights` 160,5 (numpy trên driver) |
  | 06g | 61,4 giây | – |

### B. Đo những job nào
| Job | Trục số worker (1 / 2) | Trục dữ liệu (10 / 50 / 100%) | Ghi chú |
|---|---|---|---|
| 02 Làm sạch | có | không | chỉ xử lý danh mục món (5.499 món), không phụ thuộc số user |
| 03 Đặc trưng món | có | không | như trên |
| 04 Sinh hành vi | có | **có** | lần chạy 04 đầu tiên ở mỗi mức cũng là bước sinh dữ liệu cho mức đó |
| 05 Phân tích | có | **có** | |
| 06a Chia dữ liệu | có | **có** | |
| 06b ALS + baseline | có | **có** | `--fixed` |
| 06c Content | có | **có** | `--fixed` (bỏ so sánh MinHash) |
| 06d FP-Growth | có | **có** | không có lưới |
| 06e K-means | có | **có** | `--fixed` (fit k = 3, 8, 11; bỏ dò k = 2…12 và Bisecting) |
| 06f Hybrid | có | **có** | `--fixed` (trọng số lấy từ report, bỏ `cold_items`, bỏ `explore_beyond`) |
| 06g Đối chứng | có | không | dùng ratings gốc (182.556 dòng), cố định |
| 07 Xuất MongoDB | không | không | nút thắt là ghi MongoDB chứ không phải Spark; ghi đè `vifood` |

**Sinh dữ liệu 10% và 50%:**
- Chạy `04 --scale 0.1` (5.000 user) và `04 --scale 0.5` (25.000 user) trên cụm, mỗi mức ghi vào một gốc HDFS riêng (mục D).
- Bản 50% **không phải tập con** của bản 100%. Bảng users được sinh tuần tự bằng một RNG chung với kích thước n, nên hồ sơ user 1–25.000 ở hai bản khác nhau; chỉ chuỗi sự kiện của từng user là seed theo (SEED, user_id).
- Phân bố persona, vùng, tuổi, cách sinh sự kiện thì giống nhau, nên số sự kiện tăng gần tuyến tính theo số user. Đây là cách sinh dữ liệu ở nhiều quy mô mà báo cáo có thể mô tả.
- Không dùng `data/hdfs_local` (bản 10% của chế độ local), vì dữ liệu đó nằm trên đĩa máy chứ không trên HDFS.
- **Phương án khác:** lấy mẫu 50% user theo hash từ `events` 100%. Cách này nhanh hơn và cho tập con đúng, nhưng không đo được 04 ở 50% (câu hỏi 6).

### C. Chế độ `--fixed` (chỉ fit một lần với tham số đã chọn)
Tham số đọc từ report **của bản chạy thật** (`data/output/model_*_report.json`, không phải thư mục report của lần đo), để mọi mức dữ liệu dùng cùng một bộ tham số:

| Job | `--fixed` làm gì | Thời gian dự kiến ở 100%, 2 worker (ước tính từ `timings_s`) |
|---|---|---|
| 06b | bỏ dò `G_BIAS`, `G_EXP`, `G_ALPHA × G_RANK × G_REG`, độ nhạy trọng số. Dùng `best_bias_lambda`, `best_als_explicit`, `best_als_implicit` (alpha 1, rank 128, regParam 0,1). **Chỉ chạy view test** (train + val → test), giống lần fit cuối của bản thật (câu hỏi 1) | khoảng 565 giây (`test:baselines` 40,8 + `test:rating_models` 13,2 + `test:als_implicit` 505,7 + kiểm tra 4,1) |
| 06c | giữ token, độ giống chính xác (`item_sim`, gợi ý dùng phần này), gợi ý val/test; bỏ vòng MinHash 3 / 5 / 10 bảng băm (chỉ là thí nghiệm so sánh) | khoảng 131 giây |
| 06e | fit KMeans k = 3, 8, 11 (đúng 3 cột `cluster_k3/k8/k11` cần lưu), bỏ dò k = 2…12 và BisectingKMeans | khoảng 65 giây (giả định mỗi lần fit mất như trung bình 292 / 22 = 13,3 giây) |
| 06f | trọng số lấy `best_weights` (bỏ `tune_weights`, vốn là numpy trên driver, không phải Spark); bỏ `cold_items` (`--no-cold-items` đã có), bỏ `test:explore_beyond` (câu hỏi 3) | khoảng 140 giây |
| 06g | lưới rank × regParam thay bằng tham số đã chọn | dưới 61 giây |

### D. Cách cài đặt (sửa code, chưa làm)
1. **`common.py`:**
   - `Paths` đọc biến môi trường `VIFOOD_DATA_ROOT` (mặc định `/data`) và `VIFOOD_OUTPUT_DIR` (mặc định `data/output`);
   - thêm `P.output_prod` luôn trỏ về `data/output` (để `--fixed` đọc tham số đã chọn);
   - `raw` luôn đọc `/data/raw` (chỉ đọc); checkpoint theo gốc dữ liệu.
   - Không đặt biến nào thì mọi thứ chạy như cũ.
2. **Gốc dữ liệu đo:**
   - `/perf/s010`, `/perf/s050`, `/perf/s100` cho trục dữ liệu, `/perf/catalog` cho 02, 03, 06g;
   - trước khi chạy, chép `curated/` (5,5 MB) và `features/` (0,2 MB) từ `/data` sang từng gốc;
   - report của mỗi lần chạy ghi vào `data/output/perf/<job>_<mức>_w<số worker>_r<lần>/`.
   - Bản 100% cũng chạy lại 04 vào `/perf/s100`, để không đụng `/data`.
3. **Tên ứng dụng** gắn nhãn (biến `VIFOOD_RUN_TAG`), ví dụ `06b_als|s100|w1|r2`, để tìm lại trên History Server.
4. **Giai đoạn:**
   - `rec_common.Timer` gọi thêm `sc.setJobGroup(<tên giai đoạn>)`, nên số liệu stage gom được theo đúng giai đoạn trong `timings_s`;
   - thêm Timer cho 02, 03, 04 (hiện các job này không có `timings_s`).
5. **`--fixed`** thêm vào `rec_common.setup()` và 06b, 06c, 06e, 06f, 06g như mục C.
6. **`scripts/09_perf.py`:**
   - chạy trên máy (Python chuẩn, không cần thư viện thêm), chạy lần lượt từng cấu hình bằng `docker exec jupyter ...`;
   - trước mỗi cấu hình, bật/tắt worker và chờ trang `http://localhost:8080/json/` báo đủ số worker còn sống;
   - sau mỗi ứng dụng, đọc History Server REST để lấy thời lượng, stage, executor;
   - ghi nối tiếp `data/output/perf_runs.jsonl`, mỗi dòng một lần chạy (có thể dừng giữa chừng rồi chạy tiếp);
   - cuối cùng tổng hợp ra `data/output/perf_report.json`;
   - có `--plan` để in trước danh sách lần chạy và thời gian dự kiến.

### E. Đổi số worker
- **Đề xuất: dừng hẳn `spark-worker-2`** (`docker stop spark-worker-2`; chạy lại thì `docker start` và chờ master thấy đủ 2 worker). 1 worker = 1 executor 2 core, 3 GB; 2 worker = 2 executor, 4 core. Đây đúng là phép so sánh "1 nút và 2 nút".
- **Không dùng `spark.cores.max = 2`:** Standalone mặc định rải executor ra mọi worker (`spreadOut`), nên `cores.max = 2` sẽ cho 2 executor × 1 core trên 2 worker, vẫn có shuffle qua mạng. Đó không phải cụm 1 nút.
- **Giữ nguyên** `shuffle.partitions = 8`, bộ nhớ executor, driver ở cả hai cấu hình. Với 4 khe, 8 partition chạy 2 đợt; với 2 khe thì 4 đợt.
- **Rủi ro:** ở 100% với 1 worker, 06b rank 128 chỉ có 1 executor 2 GB, có thể spill nhiều hoặc hết bộ nhớ. Chạy thử cấu hình này một lần trước tiên.

### F. Mỗi cấu hình chạy mấy lần, lấy số nào
- **3 lần mỗi cấu hình, lấy trung vị;** báo cáo ghi thêm khoảng nhỏ nhất – lớn nhất.
- Xen kẽ thứ tự 2 worker → 1 worker → 2 worker →…, để dao động của máy (nhiệt, tiến trình nền) không dồn vào một cấu hình.
- Mỗi mức dữ liệu chạy 1 lần làm nóng không tính. Ở 10% và 50%, lần 04 sinh dữ liệu chính là lần làm nóng. Lý do: lần đọc HDFS đầu tiên sau khi bật cụm chậm hơn vì cache đĩa trống.
- Trước khi đo, tắt kernel các notebook và không chạy job nào khác (quy tắc trong CLAUDE.md). Ghi lại `docker stats` một lần mỗi cấu hình.

### G. Đo gì
| Chỉ số | Nguồn | Ghi chú |
|---|---|---|
| Thời gian ứng dụng (giây) | History Server `duration` | số chính |
| Thời gian từng giai đoạn | `timings_s` trong report + job group | ví dụ 06b `test:als_implicit` |
| **Speedup** S = T(1 worker) ÷ T(2 worker) | tính từ trung vị | lý tưởng là 2 |
| **Efficiency** E = S ÷ 2 | | |
| Theo dữ liệu: T(50%) ÷ T(10%), T(100%) ÷ T(10%); số sự kiện / giây cho 04, 05 | | so với tỷ lệ dữ liệu 5 và 10 |
| Shuffle đọc / ghi, phần đọc từ xa (`shuffleRemoteBytesRead`) | REST `stages` | 1 worker thì phần đọc từ xa gần bằng 0 |
| Spill (bộ nhớ / đĩa), GC, `executorCpuTime ÷ executorRunTime` | REST `stages` | giải thích vì sao speedup dưới 2 |
| Số task, số stage | REST `stages` | |
| Dung lượng HDFS mỗi mức | `hdfs dfs -du` | |

### H. Bảng, biểu đồ, nơi lưu
- **File:**
  - `data/output/perf_runs.jsonl`: dữ liệu thô, mỗi dòng một lần chạy;
  - `data/output/perf_report.json`: trung vị, min/max, speedup, efficiency, shuffle theo job × mức × số worker, kèm cấu hình máy (8 CPU Docker, 2 × 2 core, executor 2 GB, `shuffle.partitions` 8);
  - ảnh History Server (Timeline, Executors của 06b ở 1 và 2 worker) trong `docs/images/09_*`.
- **MongoDB:** collection mới `perf` (1 doc mỗi job × mức × số worker), nạp bằng `07 --only perf`. Bước 07 đọc `perf_report.json`, không đụng các collection khác.
- **Dashboard:** E24 thêm khóa `perf`. Thẻ "Hiệu năng Spark" ở trang Đánh giá thay viên "Chưa" bằng:
  - (a) cột nhóm thời gian từng job, 1 và 2 worker, ở 100%;
  - (b) đường tổng thời gian theo mức dữ liệu 10 / 50 / 100%, 2 đường cho 1 và 2 worker;
  - (c) thanh ngang speedup từng job, có vạch lý tưởng 2.
  - Tổng quan: bước "Đo hiệu năng" trong danh sách tiến độ chuyển sang "Xong".
- **Báo cáo:**
  - bảng 1: thời gian (trung vị, min–max) job × mức × số worker;
  - bảng 2: speedup và efficiency ở 100%;
  - bảng 3: shuffle và spill của 05, 06b, 06f;
  - biểu đồ (a), (b), (c) như trên, và phân rã giai đoạn của 06b.

### I. Ước tính thời gian và thứ tự chạy
Ước tính dựa trên thời gian đã đo ở mục A (100%, 2 worker) và mục C. Giả định: 10% tốn khoảng 0,2 lần, 50% khoảng 0,55 lần thời gian ở 100% (có phần chi phí cố định như khởi động JVM, đọc danh mục); 1 worker chậm khoảng 1,8 lần 2 worker. Đây đều là ước tính.

| Phần | 2 worker, 1 lần | 1 worker, 1 lần |
|---|---|---|
| Chuỗi 04 → 06f ở 100% (04 543 + 05 104 + 06a 101 + 06b 565 + 06c 131 + 06d 34 + 06e 65 + 06f 140) | khoảng 28 phút | khoảng 50 phút |
| Chuỗi ở 50% | khoảng 15 phút | khoảng 28 phút |
| Chuỗi ở 10% | khoảng 6 phút | khoảng 10 phút |
| 02 + 03 + 06g | khoảng 3 phút (02 chưa có số) | khoảng 5 phút |
| **Cộng 1 vòng (3 mức + danh mục)** | **khoảng 52 phút** | **khoảng 93 phút** |

- **3 lần lặp:** khoảng 7,3 giờ, cộng khoảng 15 phút làm nóng và chuẩn bị dữ liệu. Có thể chia thành 3 buổi, mỗi buổi một mức dữ liệu.
- **Phương án gọn hơn (câu hỏi 2):** 3 lần ở 100%, 1 lần ở 10%, 50% và danh mục: khoảng 5,0 giờ (3 × 78 phút + 59 phút + 8 phút).

**Thứ tự đề xuất:**
1. Sửa code (mục D, C) và kiểm tra bản thường vẫn chạy y như cũ: chạy `--local` 05 và 06 rồi so report với bản trước.
2. Chạy thử ngắn: 10%, 2 worker, 1 lần cho cả chuỗi; kiểm tra `perf_runs.jsonl` và History Server.
3. Chạy thử 100%, 1 worker, chỉ 06b `--fixed` (rủi ro bộ nhớ, mục E).
4. Mức 10% (3 lần, xen kẽ) → mức 50% → mức 100%. 02, 03, 06g chạy kèm ở buổi 10%.
5. Tổng hợp `perf_report.json`, chụp ảnh History Server, `07 --only perf`, sửa E24 và thẻ trang Đánh giá, pytest.
6. Giữ `/perf` trên HDFS đến khi viết xong báo cáo; xóa khi cần chỗ. Dung lượng dự kiến khoảng 2,8 GB kể cả bản sao: (0,1 + 0,5 + 1) × 1,75 GB, trong đó 1,75 GB là events + results + models của bản thật tính cả bản sao.

---

## Số liệu chính
- **pytest** trên `vifood`: **61 đạt** (6,7 giây), gồm `test_segments[3/8/11]` với luật mới (1 câu mỗi cụm, không trùng câu).
- **Câu đề xuất k = 8:** 8 cụm, 8 câu khác nhau (bảng ở mục "Đã làm"). k = 3: 3 câu khác nhau; k = 11: 11 câu khác nhau.
- **Khảo sát cho đo hiệu năng:**
  - máy ảo Docker: 8 CPU, 17,6 GB RAM; máy chủ 16 luồng; worker 2 × (2 core, 3 GB);
  - History Server có 38 ứng dụng (từ 23/10 18:12);
  - 05 (23/10, cụm): 108,7 giây, 250 stage, 836 task, shuffle đọc 337,0 MB, spill đĩa 303,5 MB;
  - dung lượng HDFS của bản thật (`overview.hdfs`): events 274,5 MB, results 567,3 MB, models 31,3 MB (nhân 2 khi tính bản sao).

## Lỗi / sự cố và cách xử lý
- **Cụm đang tắt khi bắt đầu phiên**, pytest đầu tiên trả 503 "Không kết nối được MongoDB". Đã bật `mongodb` rồi restart `api`. Cuối phiên đã tắt lại `api`, `mongodb`, `spark-history`.
- **Event log nén zstd** (`events_1_*.zstd`), Python trên máy không có thư viện giải nén. Vì vậy đề xuất đọc số liệu qua REST của History Server thay vì đọc file trực tiếp.
- **02 chưa có thời gian đo nào:** report không ghi thời gian, và 02 chạy trước khi bật event log. Lần đo sẽ có số này.
- **Đã kiểm tra lại một giả định:** ban đầu tôi nghĩ bản 50% của 04 là tập con của bản 100%. Đọc `make_users()` thì không phải, nên mục B ghi đúng như vậy.

## Cần người dùng quyết định
1. **06b `--fixed`** chỉ chạy view test (khoảng 9,5 phút ở 100%, 2 worker), hay chạy cả val và test với tham số đã chọn (gần gấp đôi)?
2. **Số lần lặp:** 3 lần cho mọi cấu hình (khoảng 7,3 giờ), hay 3 lần ở 100% và 1 lần ở 10% / 50% (khoảng 5,0 giờ)?
3. **06f `--fixed`** có bỏ `test:explore_beyond` không (279,3 giây ở 100%; đây là đánh giá thêm coverage / novelty / diversity, không phải bước tạo gợi ý)?
4. **Đổi số worker** bằng cách dừng `spark-worker-2` (đề xuất), hay muốn thêm cấu hình 1 worker × 4 core để tách ảnh hưởng của "số nút" và "số core"? Cấu hình này phải sửa compose cho worker 1 và khởi động lại worker.
5. **Gốc dữ liệu riêng `/perf/...`** và 2 biến môi trường mới trong `common.py` (mặc định giữ nguyên hành vi cũ): đồng ý không?
6. **Sinh 50%:** chạy `04 --scale 0.5` (đo được 04 ở 50%; dân số 25.000 user sinh mới, không phải tập con) hay lấy mẫu 50% user từ bản 100% (tập con đúng, nhanh hơn, nhưng mất điểm đo của 04)?
7. **Lưu kết quả:** collection `perf` trong MongoDB và thẻ "Hiệu năng Spark" ở trang Đánh giá như mục H: đồng ý không? 07 không nằm trong phép đo (đề xuất không đo).

Việc cần người làm (không đổi): kiểm tra tay 100 món; dựng notebook biểu đồ cho bước 05 và 06; xem lại trang Phân khúc sau khi sửa đề xuất.

## Commit
- `Buoc 08: moi cum 1 de xuat, de xuat do hieu nang` (`api/labels.py`, `api/routers/segments.py`, `api/tests/test_consistency.py`, D16, PROGRESS, file này).
