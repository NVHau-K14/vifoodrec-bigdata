// tong-quan.js - trang Tong quan (bo cuc ban mau canvas, D15 chinh sua a): E1, E2, E3, E6, E14, E23

import { getJSON, shared, fmtInt, fmtShort, fmtBytes, fmtPct, fmtFixed, fmtSeconds } from './api.js';
import { load, hbars, statusPill, miniList, esc, wireImgFallback } from './components.js';
import { heatmapHourDow, monthlyBars } from './charts.js';

const $ = (id) => document.getElementById(id);
const overview = shared('/overview');

load($('kpis'), async (el) => {
  const ov = await overview();
  const perUser = ov.n_users ? Math.round(ov.n_recs_rows / ov.n_users) : null;
  const k = [
    { label: 'Món ăn', value: fmtInt(ov.n_dishes), sub: 'món thật, sau làm sạch' },
    { label: 'Người dùng', value: fmtInt(ov.n_users), sub: 'mô phỏng' },
    { label: 'Sự kiện hành vi', value: fmtShort(ov.n_events), sub: `${ov.event_months.length} tháng, 4 loại sự kiện` },
    { label: 'Dữ liệu trên HDFS', value: fmtBytes(ov.hdfs_total.bytes), sub: `${fmtBytes(ov.hdfs_total.bytes_with_replicas)} tính cả 2 bản sao` },
    { label: 'Dòng gợi ý đã tính', value: fmtShort(ov.n_recs_rows), sub: `${fmtInt(perUser)} món cho mỗi người dùng` },
  ];
  el.dataset.state = 'ready';
  el.innerHTML = k.map((x) => `<div class="kpi"><div class="kpi-label">${esc(x.label)}</div>
    <div class="kpi-value">${esc(x.value)}</div><div class="kpi-sub">${esc(x.sub)}</div></div>`).join('');
});

load($('heatmap'), async (el) => {
  const h = await getJSON('/behavior/heatmap?metric=cooks');
  el.dataset.state = 'ready';
  el.innerHTML = '<div class="chart" style="height:300px"></div>';
  heatmapHourDow(el.firstElementChild, h.cells, 'lượt nấu');
}, 300);

load($('funnel'), async (el) => {
  const f = await getJSON('/behavior/funnel');
  const p = f.pairs;
  const rows = [
    { label: 'Đã xem', value: p.view, text: fmtInt(p.view), note: '100%', tone: 'slate' },
    { label: 'Đã lưu', value: p.favorite, text: fmtInt(p.favorite), note: fmtPct(f.rates.favorite_per_view_pct), tone: 'mid' },
    { label: 'Đã nấu', value: p.cook, text: fmtInt(p.cook), note: fmtPct(f.rates.cook_per_view_pct) },
    { label: 'Đã chấm', value: p.rate, text: fmtInt(p.rate), note: fmtPct(f.rates.rate_per_cook_pct), tone: 'chili' },
  ];
  el.dataset.state = 'ready';
  el.innerHTML = hbars(rows) +
    `<p class="funnel-foot">Tỷ lệ "Đã lưu" và "Đã nấu" tính trên số cặp đã xem; "Đã chấm" tính trên số cặp đã nấu.
     ${fmtPct(f.users.cooked_pct)} người dùng có ít nhất một lượt nấu.</p>`;
});

const monthly = shared('/behavior/monthly');
load($('monthly'), async (el) => {
  const m = await monthly();
  el.dataset.state = 'ready';
  el.innerHTML = '<div class="chart"></div>';
  monthlyBars(el.firstElementChild, m.months, m.tet_month);
}, 280);

load($('categories'), async (el) => {
  const m = await monthly();
  const tot = {};
  for (const r of m.by_category) tot[r.dish_category] = (tot[r.dish_category] || 0) + r.cooks;
  const all = Object.values(tot).reduce((a, b) => a + b, 0);
  const rows = Object.entries(tot).sort((a, b) => b[1] - a[1])
    .map(([c, v]) => ({ label: c, value: v, text: fmtPct((100 * v) / all) }));
  el.dataset.state = 'ready';
  el.innerHTML = hbars(rows);
});

load($('top-dishes'), async (el) => {
  const d = await getJSON('/dishes?limit=5');
  el.dataset.state = 'ready';
  el.innerHTML = miniList(d.items.map((x, i) => ({ img: x.image_link, title: `${i + 1}. ${x.dish_name}`,
    sub: x.dish_category, num: `${fmtInt(x.cooks)} lượt` })));
  wireImgFallback(el);
});

load($('models'), async (el) => {
  const r = await getJSON('/eval/ranking?view=test&variant=' + encodeURIComponent('chính'));
  const rows = r.rows.map((x) => ({ label: x.label, value: x.metrics['ndcg@10'], text: fmtFixed(x.metrics['ndcg@10'], 4),
    tone: x.kind === 'chính' ? '' : 'neutral' })).sort((a, b) => b.value - a.value);
  el.dataset.state = 'ready';
  el.innerHTML = hbars(rows) + `<p class="source">${fmtInt(r.rows[0]?.metrics.n_users)} người dùng được đánh giá. Màu xanh: mô hình chính; màu xám: mốc so sánh.</p>`;
});

load($('pipeline'), async (el) => {
  const ov = await overview();
  el.dataset.state = 'ready';
  el.innerHTML = `<ul class="steps">${ov.pipeline.map((s) => `<li><span class="k">${esc(s.step)}</span>
    <span>${esc(s.name)}</span><span class="sec">${esc(fmtSeconds(s.seconds))}</span>${statusPill(s.status)}</li>`).join('')}</ul>`;
});

load($('notes'), async (el) => {
  const ov = await overview();
  el.dataset.state = 'ready';
  el.innerHTML = `<ul class="notes">${ov.notes.map((n) => `<li>${esc(n)}</li>`).join('')}</ul>`;
});
