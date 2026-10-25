// hanh-vi.js - trang Hanh vi an uong: E2 heatmap, E3 theo thang / mua / nhom mon, E4 mon theo bua, E5 lift,
// E6 pheu, E7 thoi quen nau (bang buoc 05, du lieu hanh vi mo phong)

import { getJSON, shared, qs, fmtInt, fmtPct, fmtNum } from './api.js';
import { load, hbars, miniList, segmented, esc, MONTH_LEGEND } from './components.js';
import { C, heatmapHourDow, monthlyBars, multiLines, stacked100, divergingHeatmap, simpleBars } from './charts.js';

const $ = (id) => document.getElementById(id);
const monthLabel = (s) => { const [y, m] = s.split('-'); return `${m}/${y.slice(2)}`; };
const cap = (s) => (s ? s[0].toUpperCase() + s.slice(1) : s);

// ---------- Heatmap gio x thu (E2) ----------
let heatMetric = 'cooks';
const HEAT_NAME = { cooks: 'lượt nấu', views: 'lượt xem' };
segmented($('heat-metric'), [{ value: 'cooks', label: 'Lượt nấu' }, { value: 'views', label: 'Lượt xem' }], 'cooks',
  (v) => { heatMetric = v; loadHeat(); }, 'Chỉ số');
function loadHeat() {
  load($('heatmap'), async (el) => {
    const h = await getJSON(`/behavior/heatmap${qs({ metric: heatMetric })}`);
    el.dataset.state = 'ready';
    el.innerHTML = '<div class="chart" style="height:300px"></div>';
    heatmapHourDow(el.firstElementChild, h.cells, HEAT_NAME[heatMetric]);
    $('heat-top').textContent = `Đông nhất: ${h.top.slice(0, 3).map((c) => `${c.dow_vn} ${c.hour}h (${fmtInt(c.value)})`).join(', ')}. Nguồn: analysis_heatmap_hour_dow (bước 05).`;
  }, 300);
}
loadHeat();

// ---------- Pheu (E6): thanh ngang + bang theo nhom mon ----------
const funnel = shared('/behavior/funnel');
load($('funnel'), async (el) => {
  const f = await funnel();
  const p = f.pairs;
  el.dataset.state = 'ready';
  el.innerHTML = hbars([
    { label: 'Đã xem', value: p.view, text: fmtInt(p.view), note: '100%', tone: 'slate' },
    { label: 'Đã lưu', value: p.favorite, text: fmtInt(p.favorite), note: fmtPct(f.rates.favorite_per_view_pct), tone: 'mid' },
    { label: 'Đã nấu', value: p.cook, text: fmtInt(p.cook), note: fmtPct(f.rates.cook_per_view_pct) },
    { label: 'Đã chấm', value: p.rate, text: fmtInt(p.rate), note: fmtPct(f.rates.rate_per_cook_pct), tone: 'chili' },
  ]) + `<p class="source">"Đã lưu", "Đã nấu" tính trên số cặp đã xem; "Đã chấm" tính trên số cặp đã nấu.
    ${fmtPct(f.users.cooked_pct)} người dùng có ít nhất một lượt nấu, ${fmtPct(f.users.rated_pct)} có chấm điểm.</p>`;
});
load($('funnel-table'), async (el) => {
  const f = await funnel();
  const rows = [...f.by_category].sort((a, b) => b.cook_per_view_pct - a.cook_per_view_pct);
  el.dataset.state = 'ready';
  el.innerHTML = `<table class="tbl" style="min-width:560px"><thead><tr><th>Nhóm món</th><th>Lưu / xem</th><th>Nấu / xem</th>
    <th>Chấm / nấu</th><th>Điểm trung bình</th><th>Cặp đã nấu</th></tr></thead><tbody>
    ${rows.map((r) => `<tr><td>${esc(cap(r.dish_category))}</td><td>${fmtPct(r.favorite_per_view_pct)}</td>
      <td>${fmtPct(r.cook_per_view_pct)}</td><td>${fmtPct(r.rate_per_cook_pct)}</td><td>${fmtNum(r.avg_rating, 2)}</td>
      <td>${fmtInt(r.cook_pairs)}</td></tr>`).join('')}
    <tr><th>Tất cả</th><th>${fmtPct(f.rates.favorite_per_view_pct)}</th><th>${fmtPct(f.rates.cook_per_view_pct)}</th>
      <th>${fmtPct(f.rates.rate_per_cook_pct)}</th><th>${fmtNum(f.rates.avg_rating, 2)}</th><th>${fmtInt(f.pairs.cook)}</th></tr>
    </tbody></table><p class="source">Xếp theo tỷ lệ nấu / xem. Nguồn: <code>analysis_funnel_by_category</code>.</p>`;
});

// ---------- Theo thang (E3): luot nau, nhom mon theo thang ----------
const monthly = shared('/behavior/monthly');
load($('monthly'), async (el) => {
  const m = await monthly();
  el.dataset.state = 'ready';
  el.innerHTML = `${MONTH_LEGEND}<div class="chart"></div>`;
  monthlyBars(el.lastElementChild, m.months, m.tet_month);
}, 280);

load($('cat-trend'), async (el) => {
  const m = await monthly();
  const months = m.months.map((x) => x.month);
  const cats = {};
  for (const r of m.by_category) (cats[r.dish_category] ??= {})[r.month] = r.cook_share_pct;
  const tot = {};
  for (const r of m.by_category) tot[r.dish_category] = (tot[r.dish_category] || 0) + r.cooks;
  const order = Object.keys(cats).sort((a, b) => tot[b] - tot[a]);
  el.dataset.state = 'ready';
  el.innerHTML = '<div class="chart" style="height:320px"></div>';
  multiLines(el.firstElementChild, months.map(monthLabel),
    order.map((c) => ({ name: cap(c), data: months.map((mm) => cats[c][mm] ?? null) })),
    { shown: order.slice(0, 4).map(cap), yFmt: (v) => `${fmtNum(v, 1)}%` });
}, 320);

// ---------- Mua (E3 theo vung) ----------
const SEASON = [['không', 'Không theo mùa', C.line2], ['lạnh', 'Món mùa lạnh', C.herb], ['nóng', 'Món mùa nóng', C.herbMid],
  ['tết', 'Món Tết', C.chili]];
let region = 'Tất cả';
segmented($('season-region'), ['Tất cả', 'Bắc', 'Trung', 'Nam'].map((r) => ({ value: r, label: r })), region,
  (v) => { region = v; loadSeason(); }, 'Vùng');
function loadSeason() {
  load($('season'), async (el) => {
    const m = await getJSON(`/behavior/monthly${qs({ region })}`);
    const months = [...new Set(m.season.map((r) => r.month))].sort();
    const val = {};
    for (const r of m.season) val[`${r.month}|${r.season}`] = r.share_pct;
    el.dataset.state = 'ready';
    el.innerHTML = '<div class="chart"></div>';
    stacked100(el.firstElementChild, months.map(monthLabel),
      SEASON.map(([k, name, color]) => ({ name, color, data: months.map((mm) => val[`${mm}|${k}`] ?? 0) })));
  }, 280);
}
loadSeason();

// ---------- Mon theo bua (E4) ----------
let slot = 'tối', by = 'cooks';
segmented($('slot-seg'), ['sáng', 'trưa', 'tối', 'khuya'].map((s) => ({ value: s, label: cap(s) })), slot,
  (v) => { slot = v; loadSlot(); }, 'Bữa');
segmented($('slot-by'), [{ value: 'cooks', label: 'Nhiều nhất' }, { value: 'lift', label: 'Đặc trưng' }], by,
  (v) => { by = v; loadSlot(); }, 'Cách xếp');
function loadSlot() {
  $('slot-note').textContent = `bữa ${slot}, cả năm mô phỏng`;
  load($('slot-dishes'), async (el) => {
    const r = await getJSON(`/behavior/top-dishes${qs({ slot, by, limit: 10 })}`);
    el.dataset.state = 'ready';
    el.innerHTML = miniList(r.items.map((x) => ({ dish: x, title: `${x.rank}. ${x.dish_name}`,
      sub: `${x.dish_category} · ${fmtPct(x.share_pct, 2)} lượt nấu của bữa`,
      num: by === 'cooks' ? `${fmtInt(x.cooks)} lượt` : `lift ${fmtNum(x.lift, 1)}` })));
  }, 300);
}
loadSlot();

// ---------- Lift theo nhom nguoi dung (E5) ----------
const GROUP_TYPES = [['region', 'Vùng'], ['age_group', 'Nhóm tuổi'], ['day_type', 'Ngày trong tuần'], ['meal_slot', 'Bữa']];
const ATTRS = [['dish_category', 'Nhóm món'], ['main_protein', 'Đạm chính'], ['main_method', 'Cách chế biến'],
  ['dish_type_fixed', 'Loại món'], ['is_quick', 'Món nhanh'], ['is_spicy', 'Món cay']];
$('lift-group').innerHTML = GROUP_TYPES.map(([v, l]) => `<option value="${v}">${l}</option>`).join('');
$('lift-attr').innerHTML = ATTRS.map(([v, l]) => `<option value="${v}">${l}</option>`).join('');
$('lift-group').addEventListener('change', loadLift);
$('lift-attr').addEventListener('change', loadLift);
function loadLift() {
  const group_type = $('lift-group').value, attribute = $('lift-attr').value;
  load($('lift'), async (el) => {
    const r = await getJSON(`/behavior/lift${qs({ group_type, attribute })}`);
    const xs = r.values.map((v) => v.label);
    const xi = Object.fromEntries(r.values.map((v, i) => [v.value, i]));
    const yi = Object.fromEntries(r.groups.map((g, i) => [g, i]));
    // Mau theo log2(lift), kep trong [-1, 1] (lift 0,5 .. 2); o hien so lift that
    const data = r.cells.filter((c) => c.group_value in yi).map((c) => [xi[c.value], yi[c.group_value],
      c.lift == null ? null : Math.max(-1, Math.min(1, Math.log2(c.lift))),
      c.lift == null ? '' : fmtNum(c.lift, 2),
      `${c.group_value} · ${c.value_label}<br>lift ${c.lift == null ? '–' : fmtNum(c.lift, 2)}; ${fmtPct(c.share_pct)} lượt nấu của nhóm (chung ${fmtPct(c.overall_pct)}); ${fmtInt(c.cooks)} lượt`]);
    const w = Math.max(560, 90 + xs.length * 64);
    el.dataset.state = 'ready';
    el.innerHTML = `<div class="chart" style="min-width:${w}px;height:${110 + r.groups.length * 46}px"></div>`;
    divergingHeatmap(el.firstElementChild, xs, r.groups, data, { min: -1, max: 1, center: 0,
      xRotate: xs.length > 6 ? 30 : 0, legendText: ['nấu nhiều hơn (lift 2)', 'ít hơn (0,5)'] });
  }, 260);
}
loadLift();

// ---------- Thoi quen nau (E7) ----------
load($('habits'), async (el) => {
  const h = await getJSON('/behavior/habits');
  el.dataset.state = 'ready';
  el.innerHTML = `<div class="mini-grid">
    <div><h3>Số món mỗi phiên nấu</h3><div class="chart chart-sm" id="h-session"></div>
      <p class="source">${fmtPct(h.sessions_2plus_pct?.['Tất cả'])} phiên nấu có từ 2 món trở lên ("mâm cơm"); bữa sáng và khuya chỉ 1 món.</p></div>
    <div><h3>Tỷ lệ nấu lại cùng một món</h3><div id="h-repeat"></div></div>
    <div><h3>Số lượt nấu mỗi người dùng</h3><div class="chart chart-sm" id="h-activity"></div></div>
    <div><h3>Phân bố điểm chấm</h3><div class="chart chart-sm" id="h-rating"></div>
      <p class="source">Điểm trung bình ${fmtNum(h.rating?.mean, 3)}.</p></div></div>`;
  const slots = ['Tất cả', 'sáng', 'trưa', 'tối', 'khuya'];
  const sizes = [...new Set(h.session_size.map((r) => r.size))].sort();
  const share = {};
  for (const r of h.session_size) share[`${r.meal_slot}|${r.size}`] = r.share_pct;
  const tones = [C.herbMid, C.herb, C.herbDark];
  stacked100($('h-session'), slots.map(cap), sizes.map((s, i) => ({ name: `${s} món`, color: tones[i % 3],
    data: slots.map((sl) => share[`${sl}|${s}`] ?? 0) })));
  const all = h.repeat_by_category.find((r) => r.dish_category === 'Tất cả');
  $('h-repeat').innerHTML = hbars(h.repeat_by_category.filter((r) => r.dish_category !== 'Tất cả')
    .map((r) => ({ label: cap(r.dish_category), value: r.repeat_pct, text: fmtPct(r.repeat_pct) })))
    + `<p class="source">Tính trên cặp người dùng–món đã nấu; chung ${fmtPct(all?.repeat_pct)}.</p>`;
  simpleBars($('h-activity'), h.user_activity.map((r) => r.cooks_per_user), h.user_activity.map((r) => r.users),
    { color: C.herb, xName: 'lượt nấu / người dùng', labelFmt: (v) => fmtInt(v) });
  simpleBars($('h-rating'), h.rating_dist.map((r) => fmtNum(r.rating, 1)), h.rating_dist.map((r) => r.count),
    { color: h.rating_dist.map((r) => (r.rating >= 4 ? C.herb : r.rating >= 3 ? C.herbMid : C.neutral)),
      yFmt: (v) => (v >= 1000 ? `${fmtNum(v / 1000, 0)}k` : fmtInt(v)) });
});
