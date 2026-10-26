// thoi-gian-thuc.js - trang Thoi gian thuc: E25 mon thinh hanh theo cua so (Structured Streaming, D18).
// "1 gio qua" = cua so gan nhat co window_end <= gio mo phong; cua so dang dien ra gan nhan "dang cap nhat".
// Goi lai moi 5 giay khi luong dang chay, moi 15 giay khi chua chay / da dung (de thay luong vua bat); dung khi tab an.
// Luong da dung: bieu do ve ca doan phat lai (API bo gioi han so cua so), moc 00:00 ngay sau ghi la 24:00.

import { getJSON, fmtInt, fmtNum } from './api.js';
import { load, showEmpty, dishCard, miniList, segmented, esc } from './components.js';
import { C, lines } from './charts.js';

const $ = (id) => document.getElementById(id);
const POLL_MS = 5000;
const IDLE_POLL_MS = 15000;
// Spark UI cua luong (driver trong container jupyter, cong 4041) tren cung may voi dashboard; khong ghi cung URL
const SPARK_UI = `${location.protocol}//${location.hostname}:4041`;
const SCOPES = [{ value: 'all', label: 'Toàn quốc' }, { value: 'Bắc', label: 'Miền Bắc' },
  { value: 'Trung', label: 'Miền Trung' }, { value: 'Nam', label: 'Miền Nam' }];
let scope = 'all';
let timer = null;
const hhmm = (s) => (s ? s.slice(11, 16) : '–');
// moc ket thuc cua so / doan phat lai: 00:00 cua ngay sau ghi la 24:00 cua ngay truoc
const hhmmEnd = (s) => (s && s.slice(11, 16) === '00:00' ? '24:00' : hhmm(s));
const dmy = (s) => (s ? `${s.slice(8, 10)}/${s.slice(5, 7)}/${s.slice(0, 4)}` : '–');
const secs = (v) => (v == null ? '–' : `${fmtNum(v, 1)} giây`);
const START_HINT = 'Bật luồng bằng: bash scripts/10_stream.sh start --from 16:00 --speed 60';

function kpis(d) {
  const s = d.stream || {};
  const lat = s.latency_s || {};
  const drop = s.dropped_by_watermark || {};
  const dropAll = Object.values(drop).reduce((a, b) => a + b, 0);
  const label = { 'đang chạy': 'Đang chạy', 'đã dừng': 'Đã dừng', 'chưa chạy': 'Chưa chạy' }[d.status];
  const k = [
    { label: 'Trạng thái luồng', value: label, sub: s.batch_id != null ? `batch ${fmtInt(s.batch_id)} · trigger ${fmtNum(s.trigger_s, 1)} giây` : 'chưa có batch' },
    s.at_end
      ? { label: 'Giờ mô phỏng', value: hhmmEnd(s.replay_end), sub: `${dmy(s.replay.day)} (hết đoạn phát lại) · tốc độ ${esc(s.replay.speed)} lần` }
      : { label: 'Giờ mô phỏng', value: hhmm(s.sim_now), sub: s.replay ? `${dmy(s.sim_now)} · tốc độ ${esc(s.replay.speed)} lần` : '' },
    // da dung: so cua batch cuoi (thuong chi co tick cuoi) khong co nghia
    d.status === 'đang chạy'
      ? { label: 'Sự kiện xử lý / giây', value: fmtInt(s.processed_rows_per_s), sub: `nhận vào ${fmtInt(s.input_rows_per_s)} / giây` }
      : { label: 'Sự kiện xử lý / giây', value: '–', sub: 'luồng đã dừng' },
    { label: 'Độ trễ sự kiện → MongoDB', value: secs(lat.p50), sub: lat.p95 != null ? `p95 ${secs(lat.p95)} · cận trên ${secs(lat.bound_last)}` : '20 batch gần nhất' },
    { label: 'Sự kiện trễ bị bỏ', value: fmtInt(dropAll), sub: `quá watermark 10 phút` },
  ];
  $('kpis').innerHTML = k.map((x) => `<div class="kpi"><div class="kpi-label">${esc(x.label)}</div>
    <div class="kpi-value">${esc(x.value)}</div><div class="kpi-sub">${esc(x.sub)}</div></div>`).join('');
}

function statusCard(el, d) {
  const s = d.stream || {};
  const r = s.replay || {};
  const drop = s.dropped_by_watermark || {};
  const rows = s.state_rows || {};
  el.dataset.state = 'ready';
  el.innerHTML = `<ul class="steps">
      <li><span>Trạng thái</span><span class="sec"></span><span class="status ${d.status === 'đang chạy' ? 'status-doing' : 'status-todo'}">${d.status === 'đang chạy' ? 'Đang chạy' : 'Đã dừng'}</span></li>
      <li><span>Nguồn</span><span class="sec">phát lại ${esc(dmy(r.day))}, ${esc(r.from || '')}–${esc(r.to || '')}</span></li>
      <li><span>Watermark</span><span class="sec">${esc(hhmm(s.watermark))} (trễ tối đa 10 phút)</span></li>
      <li><span>Batch đã ghi</span><span class="sec">${fmtInt(s.n_batches)}</span></li>
      <li><span>Bỏ ở bước khử trùng / tổng hợp</span><span class="sec">${fmtInt(drop.dedupeWithinWatermark ?? 0)} / ${fmtInt(drop.stateStoreSave ?? 0)}</span></li>
      <li><span>Dòng trạng thái</span><span class="sec">${Object.entries(rows).map(([k, v]) => `${esc(k === 'stateStoreSave' ? 'tổng hợp' : 'khử trùng')} ${fmtInt(v)}`).join(' · ') || '–'}</span></li></ul>
    <p class="source">Độ trễ là của sự kiện mới nhất trong batch, từ lúc replayer ghi file đến lúc ghi MongoDB xong; sự kiện cũ
      nhất trong batch chờ thêm tối đa 1 chu kỳ trigger + 1 giây (cận trên). Trang tự gọi lại mỗi ${POLL_MS / 1000} giây.
      ${d.status === 'đang chạy' ? `Spark UI của luồng: <a href="${SPARK_UI}/StreamingQuery/">cổng 4041</a>.` : ''}</p>
    <p class="source">Dữ liệu hành vi mô phỏng, phát lại theo đồng hồ mô phỏng.</p>`;
}

function windowsChart(el, d) {
  const sr = d.series;
  if (!sr.windows.length) {
    showEmpty(el, 'Chưa có cửa sổ nào kết thúc theo giờ mô phỏng.');
    return;
  }
  el.dataset.state = 'ready';
  const whole = d.status !== 'đang chạy' ? ' Luồng đã dừng: vẽ cả đoạn phát lại.' : '';
  el.innerHTML = `<div class="chart"></div><p class="source">Mỗi điểm là tổng lượt nấu của cửa sổ 1 giờ kết thúc lúc đó. Toàn quốc = tổng 3 vùng.${whole}</p>`;
  lines(el.firstElementChild, sr.windows.map(hhmmEnd), [
    { name: 'Toàn quốc', data: sr.all, color: C.herb, width: 3 },
    { name: 'Bắc', data: sr['Bắc'], color: C.chili },
    { name: 'Trung', data: sr.Trung, color: C.slate },
    { name: 'Nam', data: sr.Nam, color: C.herbMid },
  ], { yMin: 0, yFmt: (v) => fmtInt(v) });
}

function trendingCard(d) {
  const cur = d.current;
  if (!cur) {
    $('trend-note').textContent = 'chưa có cửa sổ nào kết thúc';
    showEmpty($('trending'), 'Chưa có cửa sổ 1 giờ nào kết thúc theo giờ mô phỏng.');
    showEmpty($('rising'), 'Chưa có dữ liệu.');
    return;
  }
  $('trend-note').textContent = `${hhmm(cur.window_start)}–${hhmmEnd(cur.window_end)}${cur.meal_slot ? `, bữa ${cur.meal_slot}` : ''} · ${cur.final ? 'đã chốt' : 'chưa chốt (còn nhận sự kiện trễ)'}`;
  $('scope-note').textContent = `${fmtInt(cur.total_cooks)} lượt nấu, ${fmtInt(cur.n_dishes)} món được nấu`;
  $('trending').dataset.state = 'ready';
  $('trending').innerHTML = cur.items.length
    ? `<div class="dish-grid">${cur.items.map((x) => dishCard({ ...x,
      note: `${fmtInt(x.cooks)} lượt nấu · ${x.delta >= 0 ? 'tăng' : 'giảm'} ${fmtInt(Math.abs(x.delta))} so với 1 giờ trước` })).join('')}</div>`
    : '<p class="state-msg">Cửa sổ này chưa có lượt nấu.</p>';
  $('rising').dataset.state = 'ready';
  $('rising').innerHTML = cur.rising.length
    ? miniList(cur.rising.map((x) => ({ dish: x, title: x.dish_name, sub: `${fmtInt(x.prev_cooks)} → ${fmtInt(x.cooks)} lượt nấu`, num: `+${fmtInt(x.delta)}` })))
    : '<p class="state-msg">Không món nào tăng so với 1 giờ trước.</p>';
}

function progressList(d) {
  const ip = d.in_progress;
  // luong da dung: cac cua so nay chi co mot phan du lieu (doan phat lai ket thuc giua cua so)
  const running = d.status === 'đang chạy';
  const live = running ? 'đang cập nhật' : 'chưa đủ 1 giờ';
  $('progress-title').textContent = running ? 'Cửa sổ đang cập nhật' : 'Cửa sổ chưa đủ 1 giờ dữ liệu';
  $('progress').innerHTML = ip.length
    ? `<ul class="steps">${ip.map((w) => `<li><span>${esc(hhmm(w.window_start))}–${esc(hhmmEnd(w.window_end))}</span>
        <span class="sec">${fmtInt(w.total_cooks)} lượt nấu</span><span class="rt-live">${live}</span></li>`).join('')}</ul>`
    : '<p class="state-msg">Không có cửa sổ nào đang diễn ra.</p>';
}

async function refresh() {
  let data = null;
  await load($('status'), async (el) => {
    data = await getJSON(`/trending?scope=${encodeURIComponent(scope)}&limit=10&windows=24`);
    if (data.status === 'chưa chạy') {
      showEmpty(el, `Structured Streaming chưa chạy, collection trending còn trống. ${START_HINT}`);
      return;
    }
    statusCard(el, data);
  });
  if (!data) return;
  const day = data.stream?.replay?.day;
  $('pill-date').textContent = `Ngày phát lại: ${day ? dmy(day) : 'chưa có'}`;
  kpis(data);
  if (data.status === 'chưa chạy') {
    showEmpty($('windows'), 'Biểu đồ sẽ hiện khi luồng ghi cửa sổ đầu tiên.');
    showEmpty($('trending'), 'Khi luồng chạy, đây là các món được nấu nhiều nhất trong 1 giờ qua (giờ mô phỏng).');
    showEmpty($('rising'), 'Chưa có dữ liệu.');
    $('progress').innerHTML = '';
  } else {
    windowsChart($('windows'), data);
    trendingCard(data);
    progressList(data);
  }
  clearTimeout(timer);
  if (!document.hidden) timer = setTimeout(refresh, data.status === 'đang chạy' ? POLL_MS : IDLE_POLL_MS);
}

segmented($('scope'), SCOPES, scope, (v) => { scope = v; refresh(); }, 'Phạm vi');
document.addEventListener('visibilitychange', () => {
  clearTimeout(timer);
  if (!document.hidden) refresh();
});
refresh();
