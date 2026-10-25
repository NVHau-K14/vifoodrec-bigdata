---
name: vifood-dashboard
description: Quy ước giao diện dashboard ViFoodRec (HTML/CSS/JS thuần + ECharts, gọi FastAPI). Dùng khi viết hoặc sửa bất kỳ file nào trong web/, khi vẽ biểu đồ cho dashboard, hoặc khi thiết kế endpoint trả dữ liệu cho dashboard.
---

# Dashboard ViFoodRec

Bản mẫu đã duyệt: canvas "ViFoodRec Dashboard – bản mẫu" trên claude.ai (trang Tổng quan + Gợi ý món).
Skill này chốt **một** bộ quy ước để mọi trang trông như cùng một sản phẩm.
Đọc kèm skill `frontend-design` nếu có; khi hai skill khác nhau thì **skill này thắng**.

## 1. Công nghệ và cấu trúc

- HTML + CSS + JavaScript thuần (ES2020, không framework, không bước build). Biểu đồ: **ECharts 5**.
- Không phụ thuộc mạng khi demo: để `echarts.min.js` (bản **5.5.1**) trong `web/vendor/`, font Be Vietnam Pro (400/500/600/700, **3 subset latin, latin-ext, vietnamese**, khai báo `unicode-range` cho từng subset) trong `web/fonts/`. Subset vietnamese chỉ có các chữ có dấu, chữ a–z và số nằm trong latin, nên phải có đủ 3. Tải bằng `scripts/08_fetch_vendor.sh`. Không dùng CDN.
- FastAPI phục vụ `web/` tĩnh và API dưới `/api/...` cùng origin (không cần CORS).

```
web/
  index.html            # Tổng quan
  hanh-vi.html  mon-an.html  phan-khuc.html  goi-y.html  danh-gia.html  thoi-gian-thuc.html
  css/theme.css         # token + thành phần dùng chung (mục 2–4). Trang KHÔNG tự định nghĩa màu.
  css/<trang>.css       # chỉ bố cục riêng của trang (nếu cần)
  js/api.js             # hàm fetch dùng chung, xử lý lỗi, định dạng số
  js/charts.js          # đăng ký theme ECharts "vifood" + hàm vẽ dùng chung (heatmap, cột, thanh ngang)
  js/layout.js          # dựng thanh bên + đánh dấu trang hiện tại
  js/components.js      # thành phần dùng chung (mục 4): thẻ món, thanh lọc, viên trạng thái, khung tải/lỗi/rỗng
  js/<trang>.js
  vendor/ fonts/ img/placeholder-dish.svg
```

## 2. Token (đặt trong `:root` của theme.css, chỉ dùng qua biến)

```css
:root{
  --ground:#F4F5F2;   /* nền trang */
  --surface:#FFFFFF;  /* thẻ */
  --ink:#17201B;      /* chữ chính, thanh bên */
  --ink-2:#2B3530;    /* chữ phụ đậm */
  --muted:#5B6660;    /* chú thích (đạt 4.5:1 trên trắng) */
  --line:#E2E5E0;     /* viền thẻ */
  --line-2:#CDD3CB;   /* viền ô nhập, chip */
  --track:#EEF1EC;    /* nền thanh tiến độ, ô heatmap = 0 */
  --chip:#E7EAE4;     /* nền nhóm nút phân đoạn */

  --herb:#1E6B4A;     /* màu nhấn chính: dữ liệu, ALS, trạng thái "xong" */
  --herb-dark:#134A33;
  --herb-soft:#E3F0E8;
  --herb-mid:#9CC7B0; /* cột tháng train */
  --chili:#C2481B;    /* nhấn phụ: Tết, "Khám phá" (content), cảnh báo nhẹ */
  --chili-dark:#8E3412;
  --chili-soft:#FBE9E1;
  --slate:#3F4B45;    /* val/test, dữ liệu "giữ lại" */
  --neutral:#8A958F;  /* baseline, nguồn "phổ biến" */

  --nav:#17201B; --nav-hover:#2A3630; --nav-text:#C9D2CC; --nav-dot:#7FD1A6;

  --radius-card:16px; --radius-tile:14px; --radius-btn:10px; --radius-pill:20px;
  --gap:18px;
  --font:'Be Vietnam Pro',system-ui,sans-serif;
}
body{margin:0;background:var(--ground);color:var(--ink);font-family:var(--font);font-variant-numeric:tabular-nums}
```

- Chỉ **2 màu nhấn**: xanh `--herb` và cam `--chili`. Không thêm màu mới; cần phân biệt nhiều nhóm thì dùng thang của herb hoặc `--neutral`.
- Không gradient trang trí, không đổ bóng đậm, không emoji, không thẻ có viền trái màu.

## 3. Bố cục

- Hàng flex `flex-wrap: wrap`: thanh bên `flex: 1 1 232px` (nền `--nav`), nội dung `flex: 999 1 560px; min-width:0; padding: 32px 40px 56px`. Ở màn hẹp thanh bên tự xuống trên cùng. Không `position: sticky`, không `100vh` cho thanh bên.
- Thanh bên: logo (biểu tượng bát canh, nét `--nav-dot`) + "ViFoodRec" + dòng phụ "Hành vi ăn uống & gợi ý món"; 7 mục theo đúng thứ tự: Tổng quan, Hành vi ăn uống, Món ăn, Phân khúc người dùng, Gợi ý món, Đánh giá mô hình, Thời gian thực. Mục hiện tại: nền `--nav-hover`, chấm `--nav-dot`, `aria-current="page"`. Cuối thanh bên luôn có hộp "Dữ liệu hành vi mô phỏng".
- Đầu trang: nhãn nhỏ viết hoa màu herb (tên trang) + tiêu đề H1 32px/700 dạng **một câu nói điều trang trả lời** (vd "Hôm nay nấu gì?"), bên phải là các viên thông tin: "Mốc dữ liệu: 01/09/2026" và viên cam "Hành vi mô phỏng".
- Nội dung chia thành các hàng `section` flex-wrap, mỗi thẻ `flex: <tỷ lệ> 1 <min>px`. Thẻ: nền `--surface`, viền 1px `--line`, bo `--radius-card`, padding 22px, tiêu đề H2 17px/600, dòng chú thích 12px `--muted` canh phải tiêu đề.
- Hàng thẻ số liệu (KPI): grid `repeat(auto-fit, minmax(170px,1fr))`, nhãn 13px muted, số 28px/700, dòng phụ 12px.
- Bảng rộng hoặc heatmap: bọc trong hộp `overflow-x:auto`, đặt `min-width` cho nội dung.

## 4. Thành phần dùng chung

**Thẻ món** (trang Gợi ý, Món ăn, top món):
- Ảnh tỷ lệ 4:3 `object-fit:cover`, lấy từ `image_link`; `loading="lazy"`, `referrerpolicy="no-referrer"`; lỗi tải hoặc null thì dùng `img/placeholder-dish.svg` trên nền màu theo nhóm món (mục 6). Có 19 món không có ảnh.
- Góc trái trên: số hạng (vòng tròn 26px nền ink chữ trắng). Góc phải trên (nếu có): nhãn "Đã nấu T9" nền herb (món nằm trong `test_cooks`).
- Thân: tên món 15px/600 (tối đa 2 dòng), chip nhỏ nền `#F0F2EE` chữ 11px: "Chay", "Món nhanh", "Cay", các bữa nối bằng " · ".
- Dòng lý do: chấm 8px màu theo nguồn + câu lý do 12px (mục 5).
- Cả thẻ là một `<button>` (chọn món để xem chi tiết); thẻ đang chọn có viền 2px herb.

**Bộ lọc**: chip bật/tắt (`aria-pressed`) cao ≥40px — tắt: nền trắng viền `--line-2`; bật: nền ink chữ trắng. Bữa là nhóm nút phân đoạn trên nền `--chip`. Bên phải ghi tóm tắt: "N món từ gợi ý cá nhân · M món bù từ danh mục phổ biến".

**Thanh ngang** (tỷ trọng, độ đo mô hình): grid `nhãn | thanh | số`, thanh cao 12px trên nền `--track`.

**Viên trạng thái**: Xong (herb-soft/herb-dark), Đang làm (chili-soft/chili-dark), Chưa (track/muted).

**Trạng thái tải/lỗi/rỗng**: khung xám `--track` khi tải; lỗi API thì một dòng chữ muted trong thẻ + nút "Thử lại"; không bao giờ để thẻ trống không lời.

## 5. Gợi ý: nguồn, màu, câu lý do

| `source` | Chấm | Chú giải | Câu lý do (API sinh, đúng mẫu 06f) |
|---|---|---|---|
| `als` | `--herb` | Khẩu vị giống bạn (ALS) | "Người có khẩu vị giống bạn cũng hay nấu món này" |
| `content_slot` | `--chili` | Khám phá (content) | "Giống món {tên because_food_id} bạn đã nấu" khi `because_cooked = true`, ngược lại "…bạn đã xem" |
| `pop` | `--neutral` | Phổ biến | "Đang được nhiều người {tuổi} tuổi ở miền {vùng} nấu" (phổ biến theo vùng-tuổi, câu của 06f) |
| `fill` (món bù khi lọc) | `--neutral` | Phổ biến | "Được nấu nhiều trong danh mục"; có bộ lọc thì nêu bộ lọc, vd "Món chay, món nhanh được nấu nhiều trong danh mục" |

- Món bù xếp theo `stats.cook_rank` của **toàn danh mục, cả năm mô phỏng**, không theo vùng hay bữa, nên câu lý do không được nói "ở vùng của bạn".

- Luôn hiện chú giải 3 màu dưới danh sách. Không hiện điểm số thô cho người xem.
- Bộ lọc: chay / món nhanh / không cay / bữa / nhóm món. **Không** có lọc calo hay thời gian nấu, **không** hiển thị `nutrition` (số ngẫu nhiên).
- Thiếu món sau khi lọc: bù bằng `dishes` cùng bộ lọc xếp theo `stats.cook_rank`, gắn `source="fill"` (chấm `--neutral`).
- Không bao giờ hiển thị `truth` (persona thật) ở trang Gợi ý; chỉ trang Phân khúc được dùng, có ghi "chỉ để kiểm chứng".

## 6. Biểu đồ ECharts

Đăng ký một theme duy nhất trong `js/charts.js` và mọi biểu đồ dùng `echarts.init(el, 'vifood', {renderer:'svg'})`:

```js
echarts.registerTheme('vifood', {
  color: ['#1E6B4A', '#C2481B', '#3F4B45', '#9CC7B0', '#8A958F', '#134A33'],
  backgroundColor: 'transparent',
  textStyle: { fontFamily: "'Be Vietnam Pro', system-ui, sans-serif", color: '#2B3530' },
  title: { show: false },               // tiêu đề nằm ở H2 của thẻ, không trong canvas
  grid: { left: 8, right: 8, top: 24, bottom: 8, containLabel: true },
  categoryAxis: { axisLine: { lineStyle: { color: '#CDD3CB' } }, axisTick: { show: false },
                  axisLabel: { color: '#5B6660', fontSize: 11 }, splitLine: { show: false } },
  valueAxis: { axisLine: { show: false }, axisLabel: { color: '#5B6660', fontSize: 11 },
               splitLine: { lineStyle: { color: '#EEF1EC' } } },
  tooltip: { backgroundColor: '#17201B', borderWidth: 0, textStyle: { color: '#FFFFFF', fontSize: 12 } },
  legend: { textStyle: { color: '#44504A', fontSize: 12 }, icon: 'roundRect', itemWidth: 10, itemHeight: 10 },
  bar: { itemStyle: { borderRadius: [6, 6, 0, 0] } },
  line: { symbol: 'none', lineStyle: { width: 2 } }
});
```

- **Heatmap** (giờ × thứ): `visualMap` liên tục `inRange.color: ['#EEF4F0','#6FAE8D','#0F4A32']`, ô 0 màu `#F6F7F4`, thứ tự hàng T2…CN, nhãn giờ mỗi 3 giờ, `itemStyle.borderRadius: 4`, khe 3px (borderColor = nền thẻ).
- **Cột theo tháng**: trục giá trị **bắt đầu từ 0**. Màu: train `#9CC7B0`, tháng có Tết `#C2481B`, val/test `#3F4B45`, kèm chú giải.
- **Mô hình**: thanh ngang; mô hình chính (hybrid, ALS, hybrid + content) màu herb, baseline màu neutral; kèm KTC 95% khi có.
- Đồ thị mạng nguyên liệu: `series.type:'graph'` layout `force`, nút herb-soft viền herb, cạnh `#CDD3CB` độ dày theo lift.
- Một biểu đồ = một ý; chú thích nguồn số liệu (12px muted) dưới mỗi biểu đồ. Gọi `chart.resize()` khi cửa sổ đổi cỡ.

## 7. Số liệu và chữ

- Tiếng Việt có dấu ở mọi chỗ hiển thị. Số dùng `toLocaleString('vi-VN')` (dấu chấm hàng nghìn, dấu phẩy thập phân): 23.205.143; 0,159; 14,4%. Số lớn ở KPI: "23,2 tr".
- Mọi con số lấy từ API (`overview`, `reports`, `metrics`, `analysis_*`), **không** chép cứng vào HTML.
- Luôn ghi rõ dữ liệu hành vi là **mô phỏng** (thanh bên + viên ở đầu trang). Thống kê `dishes.stats` ghi "cả năm mô phỏng".
- Không chữ giả, không lorem ipsum, không số tự bịa.

## 8. Truy cập

- Nút thật `<button>`, liên kết `<a href>`, ô nhập có `<label>`; nút chỉ có biểu tượng thì có `aria-label`. SVG trang trí `aria-hidden="true"`.
- Vùng bấm ≥ 44px (chip lọc ≥ 40px). Tương phản chữ ≥ 4.5:1 — muốn chữ nhạt hơn `--muted` thì không được.
- Hai trạng thái phân biệt bằng cả độ sáng, không chỉ bằng màu.

## 9. Kiểm tra trước khi coi một trang là xong

- Mở trang ở 1440px và 390px: không cuộn ngang toàn trang, thanh bên xuống trên ở màn hẹp.
- Tắt API: trang hiện thông báo lỗi trong thẻ, không trắng trang.
- Không có màu hex nào ngoài `theme.css` và `charts.js` (`grep -rn "#[0-9A-Fa-f]\{6\}" web/js web/*.html`).
- Đối chiếu một con số trên trang với `data/output/*.json` hoặc MongoDB.
