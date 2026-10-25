// thoi-gian-thuc.js - trang Thoi gian thuc: E25 mon thinh hanh theo cua so (collection trending).
// trending rong -> trang thai rong co huong dan; co du lieu thi goi lai moi 10 giay, dung khi tab bi an.

import { getJSON, fmtInt } from './api.js';
import { load, showEmpty, statusPill, dishCard, esc } from './components.js';
import { C, lines } from './charts.js';

const $ = (id) => document.getElementById(id);
const POLL_MS = 10000;
let timer = null;
const hhmm = (s) => (s ? String(s).replace('T', ' ').slice(0, 16) : '–');

async function refresh() {
  let data = null;
  await load($('status'), async (el) => {
    data = await getJSON('/trending?limit=10&windows=12');
    const running = data.status === 'đang chạy';
    el.dataset.state = 'ready';
    el.innerHTML = `<ul class="steps">
      <li><span>Trạng thái</span><span class="sec"></span>${statusPill(running ? 'Đang làm' : 'Chưa')}</li>
      <li><span>Tình trạng</span><span class="sec">${esc(data.status)}</span></li>
      <li><span>Cửa sổ gần nhất</span><span class="sec">${esc(hhmm(data.updated_at))}</span></li>
      <li><span>Số cửa sổ đang xem</span><span class="sec">${fmtInt(data.windows.length)}</span></li></ul>
      ${running ? `<p class="source">Tự cập nhật mỗi ${POLL_MS / 1000} giây khi tab đang mở.</p>`
        : '<p class="source">Structured Streaming chưa chạy, nên collection <code>trending</code> còn trống. Trang tự cập nhật khi có dữ liệu.</p>'}`;
  });
  if (!data) return;
  const running = data.status === 'đang chạy';
  if (!running) {
    showEmpty($('windows'), 'Chưa có cửa sổ nào. Biểu đồ sẽ hiện khi luồng Structured Streaming ghi dữ liệu vào trending.');
    showEmpty($('trending'), 'Chưa có món thịnh hành. Khi luồng chạy, đây là các món được nấu nhiều nhất trong cửa sổ gần nhất.');
  } else {
    const ws = [...data.windows].reverse();
    $('windows').dataset.state = 'ready';
    $('windows').innerHTML = '<div class="chart"></div>';
    lines($('windows').firstElementChild, ws.map((w) => hhmm(w.window_end).slice(11)),
      [{ name: 'Lượt nấu', data: ws.map((w) => w.total_cooks), color: C.herb }], { yMin: 0, yFmt: (v) => fmtInt(v) });
    const last = data.windows[0];
    $('trend-note').textContent = `cửa sổ kết thúc ${hhmm(last.window_end)}`;
    $('trending').dataset.state = 'ready';
    $('trending').innerHTML = last.items.length
      ? `<div class="dish-grid">${last.items.map((d, i) => dishCard({ ...d, rank: i + 1, note: `${fmtInt(d.cooks)} lượt nấu trong cửa sổ` })).join('')}</div>`
      : '<p class="state-msg">Cửa sổ này chưa có lượt nấu.</p>';
  }
  clearTimeout(timer);
  if (running && !document.hidden) timer = setTimeout(refresh, POLL_MS);
}

document.addEventListener('visibilitychange', () => {
  clearTimeout(timer);
  if (!document.hidden) refresh();
});
refresh();
