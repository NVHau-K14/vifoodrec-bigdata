// mon-an.js - trang Mon an: E8 danh muc, E10 nguyen lieu, E11 do thi nguyen lieu, E12 tim mon, E13 chi tiet,
// E14 danh sach theo bo loc, E22 gia tri bo loc. Khong hien dinh duong (nutrition la so ngau nhien, D14).

import { getJSON, shared, qs, fmtInt, fmtPct, fmtNum } from './api.js';
import { load, hbars, segmented, toggleChip, filterBar, dishCard, dishDetail, showEmpty, showError, showLoading, esc }
  from './components.js';
import { C, hGroupedBars, lines, forceGraph } from './charts.js';

const $ = (id) => document.getElementById(id);
const cap = (s) => (s ? s[0].toUpperCase() + s.slice(1) : s);
const summary = shared('/dishes/summary');

// ---------- KPI (E8) ----------
load($('kpis'), async (el) => {
  const s = await summary();
  const k = s.kpi;
  const src = Object.fromEntries(s.by_source.map((r) => [r.value, r.n_dishes]));
  const cards = [
    { label: 'Số món', value: fmtInt(k.n_dishes), sub: `Cooky ${fmtInt(src.cooky)} · Món Ngon Mỗi Ngày ${fmtInt(src.mnmn)}` },
    { label: 'Món chay', value: fmtPct(k.veg_pct), sub: 'is_vegetarian' },
    { label: 'Món nhanh', value: fmtPct(k.quick_pct), sub: 'xếp theo độ ngắn cách làm' },
    { label: 'Món cay', value: fmtPct(k.spicy_pct), sub: 'is_spicy' },
    { label: 'Nguyên liệu khác nhau', value: fmtInt(k.n_ingredients), sub: 'sau chuẩn hóa tên' },
  ];
  el.dataset.state = 'ready';
  el.innerHTML = cards.map((x) => `<div class="kpi"><div class="kpi-label">${esc(x.label)}</div>
    <div class="kpi-value">${esc(x.value)}</div><div class="kpi-sub">${esc(x.sub)}</div></div>`).join('');
});

// ---------- Danh muc va luot nau (E8) ----------
const ATTR = [['dish_category', 'Nhóm món'], ['main_method', 'Cách chế biến'], ['main_protein', 'Đạm chính']];
let attr = 'dish_category';
segmented($('cvc-attr'), ATTR.map(([v, l]) => ({ value: v, label: l })), attr, (v) => { attr = v; loadCvc(); }, 'Thuộc tính');
function loadCvc() {
  load($('cvc'), async (el) => {
    const s = await summary();
    const rows = s.catalog_vs_cooked[attr] || [];
    el.dataset.state = 'ready';
    el.innerHTML = `<div class="chart" style="height:${80 + rows.length * 34}px"></div>`;
    hGroupedBars(el.firstElementChild, rows.map((r) => cap(r.value)), [
      { name: '% số món', color: C.neutral, data: rows.map((r) => r.catalog_pct) },
      { name: '% lượt nấu', color: C.herb, data: rows.map((r) => r.cook_pct) }]);
  }, 320);
}
loadCvc();

// ---------- Duoi dai (E8) ----------
load($('longtail'), async (el) => {
  const lt = (await summary()).long_tail;
  const xs = lt.curve.map((r) => r.dish_pct);
  el.dataset.state = 'ready';
  el.innerHTML = `<div class="chart"></div>
    <p class="source">Gini lượt nấu ${fmtNum(lt.gini_cooks, 3)} (lượt xem ${fmtNum(lt.gini_views, 3)}). 1% món đầu chiếm
    ${fmtPct(lt.top1pct_dishes_cook_share_pct)}, 10% món đầu chiếm ${fmtPct(lt.top10pct_dishes_cook_share_pct)} lượt nấu.
    Nguồn: <code>analysis_long_tail_curve</code>.</p>`;
  lines(el.firstElementChild, xs.map((x) => `${x}%`), [
    { name: 'Lượt nấu', data: lt.curve.map((r) => r.cooks_cum_pct), color: C.herb },
    { name: 'Lượt xem', data: lt.curve.map((r) => r.views_cum_pct), color: C.neutral },
    { name: 'Chia đều', data: xs, color: C.line2 }],
  { yFmt: (v) => `${fmtNum(v, 0)}%`, xName: '% món (xếp theo lượt nấu giảm dần)', yMin: 0, yMax: 100 });
});

// ---------- Nguyen lieu pho bien (E10) ----------
let seasoning = false;
$('ing-ctrl').append(toggleChip('Tính cả gia vị', seasoning, (v) => { seasoning = v; loadIng(); }));
function loadIng() {
  load($('ingredients'), async (el) => {
    const rs = await getJSON(`/ingredients/top${qs({ limit: 20, seasoning })}`);
    el.dataset.state = 'ready';
    el.innerHTML = hbars(rs.map((r) => ({ label: r.ingredient, value: r.cooks, text: fmtInt(r.cooks),
      note: `${fmtInt(r.n_dishes)} món`, tone: r.is_seasoning ? 'neutral' : '' })));
  }, 400);
}
loadIng();

// ---------- Do thi nguyen lieu (E11) ----------
let variant = 'bỏ gia vị';
segmented($('graph-variant'), [{ value: 'bỏ gia vị', label: 'Bỏ gia vị' }, { value: 'giữ gia vị', label: 'Giữ gia vị' }],
  variant, (v) => { variant = v; loadGraph(); }, 'Biến thể');
function loadGraph() {
  load($('graph'), async (el) => {
    const g = await getJSON(`/ingredients/graph${qs({ variant, limit: 80 })}`);
    if (!g.edges.length) { showEmpty(el, 'Không có luật nguyên liệu cho biến thể này.'); return; }
    el.dataset.state = 'ready';
    el.innerHTML = `<div class="chart" style="height:420px"></div>
      <p class="source">${g.nodes.length} nguyên liệu, ${g.edges.length} cạnh (lift cao nhất ${fmtNum(g.edges[0].lift, 1)}).</p>`;
    forceGraph(el.firstElementChild, g.nodes, g.edges);
  }, 420);
}
loadGraph();

// ---------- Tra cuu mon (E14, E12) ----------
const PAGE = 12;
const fstate = { veg: false, quick: false, not_spicy: false, meal: null, category: null };
let skip = 0, ctrl = null, summaryEl = null, selected = null;
const matches = (d) => (!fstate.veg || d.is_vegetarian) && (!fstate.quick || d.is_quick)
  && (!fstate.not_spicy || !d.is_spicy) && (!fstate.meal || d.meal_types.includes(fstate.meal))
  && (!fstate.category || d.dish_category === fstate.category);

shared('/meta/filters')().then((m) => {
  summaryEl = filterBar($('filters'), fstate, m, () => refresh());
  refresh();
}).catch((e) => showError($('filters'), e));

let timer = null;
$('search').addEventListener('input', () => { clearTimeout(timer); timer = setTimeout(refresh, 250); });
$('more').addEventListener('click', () => refresh(true));

async function refresh(more = false) {
  const body = $('dishes');
  if (ctrl) ctrl.abort();
  ctrl = new AbortController();
  const { signal } = ctrl;
  const q = $('search').value.trim();
  skip = more ? skip + PAGE : 0;
  if (!more) showLoading(body, 240);
  try {
    let items, total, searching = q.length >= 2;
    if (searching) {
      // E12 khong co bo loc: loc lai tren 30 ket qua dau (cung nghia voi bo loc cua E14)
      const rs = await getJSON(`/dishes/search${qs({ q, limit: 30 })}`, { signal });
      items = rs.filter(matches);
      total = items.length;
    } else {
      const r = await getJSON(`/dishes${qs({ ...fstate, skip, limit: PAGE })}`, { signal });
      items = r.items;
      total = r.total;
    }
    const html = items.map((d) => dishCard({ ...d, note: d.cooks != null ? `${fmtInt(d.cooks)} lượt nấu · hạng ${fmtInt(d.cook_rank)}` : null },
      { showRank: false, selected: d.food_id === selected })).join('');
    if (more) body.querySelector('.dish-grid').insertAdjacentHTML('beforeend', html);
    else if (!items.length) showEmpty(body, searching ? `Không có món nào tên chứa "${q}" thỏa bộ lọc.` : 'Không có món nào thỏa bộ lọc này.');
    else { body.dataset.state = 'ready'; body.innerHTML = `<div class="dish-grid">${html}</div>`; }
    const shown = body.querySelectorAll('.dish').length;
    $('more').hidden = searching || shown >= total;
    if (summaryEl) summaryEl.textContent = searching ? `${total} món khớp tên (30 kết quả đầu)` : `${fmtInt(shown)} / ${fmtInt(total)} món`;
    $('lookup-note').textContent = searching ? 'kết quả tìm theo tên, xếp theo lượt nấu' : 'xếp theo lượt nấu cả năm mô phỏng';
  } catch (e) {
    if (e.name === 'AbortError') return;
    showError(body, e, () => refresh(more));
  }
}

$('dishes').addEventListener('click', (e) => {
  const b = e.target.closest('.dish');
  if (!b) return;
  selected = Number(b.dataset.id);
  $('dishes').querySelectorAll('.dish').forEach((x) => x.setAttribute('aria-pressed', String(x === b)));
  showDetail(selected);
});
$('detail').addEventListener('click', (e) => {
  const b = e.target.closest('.dish');
  if (b) showDetail(Number(b.dataset.id));
});

// ---------- Chi tiet mon (E13) ----------
function showDetail(id) {
  const card = $('detail-card');
  card.hidden = false;
  load($('detail'), async (el) => {
    const d = await getJSON(`/dishes/${id}`);
    $('detail-title').textContent = d.dish_name;
    el.dataset.state = 'ready';
    el.innerHTML = dishDetail(d);
    card.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }, 240);
}
