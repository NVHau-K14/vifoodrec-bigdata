// components.js - thanh phan dung chung (skill muc 4): the mon, chip loc, thanh ngang, vien trang thai,
// khung tai / loi / rong. Khong co ma mau: moi mau qua class trong theme.css.

import { fmtInt, fmtNum, fmtRatio } from './api.js';

export function esc(s) {
  return String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

// ---------- Tai / loi / rong ----------
// body: phan tu chua noi dung cua the (khong gom tieu de)
export function showLoading(body, height = 120) {
  body.dataset.state = 'loading';
  body.innerHTML = `<div class="slot" style="min-height:${height}px" aria-hidden="true"></div><span class="sr-only">Đang tải</span>`;
}

export function showError(body, err, retry) {
  body.dataset.state = 'error';
  body.innerHTML = `<div class="state-msg" role="alert"><span>${esc(err?.message || 'Không tải được dữ liệu.')}</span></div>`;
  if (retry) {
    const b = document.createElement('button');
    b.className = 'btn';
    b.type = 'button';
    b.textContent = 'Thử lại';
    b.addEventListener('click', retry);
    body.querySelector('.state-msg').append(b);
  }
}

export function showEmpty(body, msg) {
  body.dataset.state = 'empty';
  body.innerHTML = `<div class="state-msg">${esc(msg)}</div>`;
}

export function showReady(body) {
  body.dataset.state = 'ready';
  body.innerHTML = '';
}

// Chay loader(body) voi khung tai, loi thi hien thong bao + nut Thu lai
export async function load(body, loader, height) {
  showLoading(body, height);
  try {
    await loader(body);
  } catch (e) {
    if (e.name === 'AbortError') return;
    console.error(e);
    showError(body, e, () => load(body, loader, height));
  }
}

// ---------- Thanh ngang: nhan | thanh | so ----------
// rows [{label, value, text, note, tone}]; max mac dinh = gia tri lon nhat
// wrap = true: nhan dai duoc xuong dong (cot nhan khong chiem het cho cua thanh)
export function hbars(rows, { max, wrap = false } = {}) {
  const m = max ?? Math.max(...rows.map((r) => r.value), 0);
  return `<div class="hbars${wrap ? ' wrap' : ''}">${rows.map((r) => {
    const w = m > 0 ? Math.max(0, Math.min(100, (r.value / m) * 100)) : 0;
    return `<span class="lbl">${esc(r.label)}</span>
      <span class="bar" role="img" aria-label="${esc(r.label)}: ${esc(r.text)}"><span class="fill ${r.tone || ''}" style="width:${w.toFixed(1)}%"></span></span>
      <span class="num">${esc(r.text)}${r.note ? `<small>${esc(r.note)}</small>` : ''}</span>`;
  }).join('')}</div>`;
}

// ---------- Vien trang thai ----------
const STATUS = { 'Xong': 'status-done', 'Đang làm': 'status-doing', 'Chưa': 'status-todo' };
export function statusPill(s) {
  return `<span class="status ${STATUS[s] || 'status-todo'}">${esc(s)}</span>`;
}

// ---------- Nhom nut phan doan / chip bat tat ----------
// options [{value, label}]; onChange(value)
export function segmented(el, options, value, onChange, label) {
  el.className = 'seg';
  el.setAttribute('role', 'group');
  if (label) el.setAttribute('aria-label', label);
  el.innerHTML = options.map((o) => `<button type="button" data-v="${esc(o.value)}" aria-pressed="${o.value === value}">${esc(o.label)}</button>`).join('');
  el.addEventListener('click', (e) => {
    const b = e.target.closest('button');
    if (!b) return;
    el.querySelectorAll('button').forEach((x) => x.setAttribute('aria-pressed', String(x === b)));
    onChange(b.dataset.v);
  });
}

export function toggleChip(label, pressed, onChange) {
  const b = document.createElement('button');
  b.type = 'button';
  b.className = 'chip-toggle';
  b.textContent = label;
  b.setAttribute('aria-pressed', String(pressed));
  b.addEventListener('click', () => {
    const v = b.getAttribute('aria-pressed') !== 'true';
    b.setAttribute('aria-pressed', String(v));
    onChange(v);
  });
  return b;
}

// ---------- Bo loc mon (chay / mon nhanh / khong cay / bua / nhom mon) ----------
// state {veg, quick, not_spicy, meal, category}; meta tu /api/meta/filters
// Man hep (<= 640px): cac dieu khien thu vao nut "Bo loc" (aria-expanded) de danh sach len cao hon.
let filterSeq = 0;
export function filterBar(el, state, meta, onChange) {
  el.className = 'filters';
  el.innerHTML = '';
  const id = `filters-body-${++filterSeq}`;
  const tog = document.createElement('button');
  tog.type = 'button';
  tog.className = 'btn filters-toggle';
  tog.setAttribute('aria-expanded', 'false');
  tog.setAttribute('aria-controls', id);
  const nOn = () => [state.veg, state.quick, state.not_spicy, state.meal, state.category].filter(Boolean).length;
  const label = () => { const n = nOn(); tog.textContent = n ? `Bộ lọc · ${n} đang bật` : 'Bộ lọc'; };
  tog.addEventListener('click', () => {
    const open = !el.classList.contains('open');
    el.classList.toggle('open', open);
    tog.setAttribute('aria-expanded', String(open));
  });
  const body = document.createElement('div');
  body.className = 'filters-body';
  body.id = id;
  const fire = () => { label(); onChange({ ...state }); };
  body.append(toggleChip('Chay', state.veg, (v) => { state.veg = v; fire(); }));
  body.append(toggleChip('Món nhanh', state.quick, (v) => { state.quick = v; fire(); }));
  body.append(toggleChip('Không cay', state.not_spicy, (v) => { state.not_spicy = v; fire(); }));
  const seg = document.createElement('div');
  const meals = [{ value: '', label: 'Mọi bữa' }, ...meta.meal_types.map((m) => ({ value: m, label: m[0].toUpperCase() + m.slice(1) }))];
  segmented(seg, meals, state.meal || '', (v) => { state.meal = v || null; fire(); }, 'Bữa');
  body.append(seg);
  const wrap = document.createElement('label');
  wrap.className = 'field';
  wrap.innerHTML = `<span class="sr-only">Nhóm món</span><select><option value="">Mọi nhóm món</option>${meta.categories.map((c) => `<option value="${esc(c)}"${c === state.category ? ' selected' : ''}>${esc(c)}</option>`).join('')}</select>`;
  wrap.querySelector('select').addEventListener('change', (e) => { state.category = e.target.value || null; fire(); });
  body.append(wrap);
  label();
  el.append(tog, body);
  const sum = document.createElement('span');
  sum.className = 'filters-summary';
  sum.setAttribute('aria-live', 'polite');
  el.append(sum);
  return sum;
}

// ---------- Anh mon va anh thay the (skill muc 4) ----------
// Anh thay the theo nhom mon (dish_category): nen mau + bieu tuong SVG net manh + ten nhom.
// Chi 3 tong mau tu token (herb / chili / slate tren nen chip), bieu tuong moi nhom mot khac.
const S = (d) => `<svg viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${d}</svg>`;
const ICON = {
  canh: S('<path d="M8 22h32a16 16 0 0 1-32 0Z"/><path d="M19 41h10"/><path d="M18 16c-2-2.5 2-4 0-7M24 16c-2-2.5 2-4 0-7M30 16c-2-2.5 2-4 0-7"/>'),
  chinh: S('<circle cx="25" cy="25" r="11"/><circle cx="25" cy="25" r="6.5"/><path d="M6 12v8a3 3 0 0 0 6 0v-8M9 12v26"/><path d="M42 38V12c-2.6 1.8-3.8 5.5-3.8 9.5 0 3 1.4 4.5 3.8 4.5"/>'),
  goi: S('<path d="M9 39c0-16 11-27 30-29 0 18-11 29-27 29Z"/><path d="M9 39c6-8 13-15 22-21"/><path d="M20 28l-1-7M25 24l5 1"/>'),
  banh: S('<path d="M8 22 34 12l6 10Z"/><path d="M8 22v16h32V22"/><path d="M8 30h32"/><circle cx="30" cy="8" r="2.2"/>'),
  bun: S('<path d="M7 25h34a17 17 0 0 1-34 0Z"/><path d="M18 43h12"/><path d="M26 21 38 5M31 22 43 8"/><path d="M12 25c1.5-4 4-4 5.5 0M18.5 25c1.5-4 4-4 5.5 0"/>'),
  com: S('<path d="M8 26h32a16 16 0 0 1-32 0Z"/><path d="M11 26c1-8 6.5-12 13-12s12 4 13 12"/><path d="M19 43h10"/><path d="M20 20.5h.01M25.5 18.5h.01M29 22h.01M17 24h.01"/>'),
  che: S('<path d="M9 11h30l-6 24H15Z"/><path d="M11.5 19h25M13.5 27h21"/><path d="M19 35v5h10v-5"/><path d="M16 44h16"/>'),
  uong: S('<path d="M13 15h22l-2.6 24.4a3 3 0 0 1-3 2.6h-10.8a3 3 0 0 1-3-2.6Z"/><path d="M26 15 30 5h5"/><path d="M14 23h20"/>'),
  lau: S('<path d="M8 21h32v11a8 8 0 0 1-8 8H16a8 8 0 0 1-8-8Z"/><path d="M5 21h38M8 26H4M44 26h-4"/><path d="M18 15c-2-2 2-4 0-7M24 15c-2-2 2-4 0-7M30 15c-2-2 2-4 0-7"/>'),
  anvat: S('<path d="M7 41 41 7"/><circle cx="16" cy="32" r="5"/><circle cx="24" cy="24" r="5"/><circle cx="32" cy="16" r="5"/>'),
};
const PH_GROUP = {
  'canh/súp': ['canh', 'herb'], 'món chính': ['chinh', 'chili'], 'gỏi/salad': ['goi', 'herb'],
  'bánh': ['banh', 'slate'], 'bún/phở/mì/miến': ['bun', 'chili'], 'cơm/xôi/cháo': ['com', 'slate'],
  'chè/tráng miệng': ['che', 'chili'], 'đồ uống': ['uong', 'herb'], 'lẩu': ['lau', 'chili'], 'ăn vặt': ['anvat', 'slate'],
};
const cap = (s) => (s ? s[0].toUpperCase() + s.slice(1) : s);
export const IMG_TIMEOUT_MS = 4000;

function dishPh(d) {
  const [icon, tone] = PH_GROUP[d.dish_category] || ['canh', 'slate'];
  return `<span class="dish-ph tone-${tone}" aria-hidden="true">${ICON[icon]}<span class="ph-name">${esc(cap(d.dish_category) || 'Món ăn')}</span></span>`;
}

// Khung anh 4:3: anh thay the nam duoi, anh that phu len khi tai xong (class "ok").
// Loi, thieu image_link hoac qua IMG_TIMEOUT_MS -> bo anh that, chi con anh thay the.
export function dishImg(d, cls = '') {
  const img = d.image_link
    ? `<img src="${esc(d.image_link)}" alt="" loading="lazy" referrerpolicy="no-referrer" data-ph>` : '';
  return `<span class="dish-img ${cls}">${dishPh(d)}${img}</span>`;
}

// Anh nho trong danh sach (56 x 42): cung co che, khong hien ten nhom
export const dishThumb = (d) => dishImg(d, 'thumb');

export function dishChips(d) {
  const c = [];
  if (d.is_vegetarian) c.push('Chay');
  if (d.is_quick) c.push('Món nhanh');
  if (d.is_spicy) c.push('Cay');
  if (d.meal_types?.length) c.push(d.meal_types.join(' · '));
  return c.map((x) => `<span class="chip">${esc(x)}</span>`).join('');
}

const dropImg = (img) => { img.removeAttribute('src'); img.remove(); };
const armed = new WeakSet();
const nearView = typeof IntersectionObserver === 'function' ? new IntersectionObserver((es) => {
  for (const e of es) {
    if (!e.isIntersecting) continue;
    const img = e.target;
    nearView.unobserve(img);
    // Bat dau dem khi anh sap vao man hinh (anh lazy chua tai thi chua tinh)
    if (!img.classList.contains('ok')) img._t = setTimeout(() => { if (!img.classList.contains('ok')) dropImg(img); }, IMG_TIMEOUT_MS);
  }
}, { rootMargin: '200px' }) : null;

function arm(img) {
  if (armed.has(img)) return;
  armed.add(img);
  if (img.complete && img.naturalWidth) img.classList.add('ok');
  else if (nearView) nearView.observe(img);
}

// Goi 1 lan cho ca trang (layout.js): anh tai xong thi hien, loi / qua han thi ve anh thay the
export function wireImgFallback(root) {
  if (armed.has(root)) return;
  armed.add(root);
  root.addEventListener('load', (e) => {
    const img = e.target;
    if (img.tagName === 'IMG' && img.hasAttribute('data-ph')) { clearTimeout(img._t); img.classList.add('ok'); }
  }, true);
  root.addEventListener('error', (e) => {
    const img = e.target;
    if (img.tagName === 'IMG' && img.hasAttribute('data-ph')) { clearTimeout(img._t); dropImg(img); }
  }, true);
  const scan = (n) => {
    if (n.nodeType !== 1) return;
    if (n.matches('img[data-ph]')) arm(n);
    n.querySelectorAll('img[data-ph]').forEach(arm);
  };
  scan(root);
  new MutationObserver((ms) => ms.forEach((m) => m.addedNodes.forEach(scan))).observe(root, { childList: true, subtree: true });
}

// item: DishCard (+ rank, reason, dot, hit, n_cook_before, note). Ca the la 1 <button>
export function dishCard(item, { selected = false, showRank = true } = {}) {
  // Chip "Ban da nau N lan" (E19 n_cook_before); nguon rep da noi dieu nay trong cau ly do
  const cooked = item.n_cook_before && item.source !== 'rep'
    ? `<span class="chip chip-cooked">Bạn đã nấu ${item.n_cook_before} lần</span>` : '';
  return `<button type="button" class="dish" data-id="${item.food_id}" aria-pressed="${selected}">
    <span class="dish-top">${dishImg(item)}
      ${showRank && item.rank ? `<span class="dish-rank" aria-label="Hạng ${item.rank}">${item.rank}</span>` : ''}
      ${item.hit ? '<span class="dish-tag">Đã nấu T9</span>' : ''}</span>
    <span class="dish-body">
      <span class="dish-name">${esc(item.dish_name)}</span>
      <span class="chips">${cooked}${dishChips(item)}</span>
      ${item.reason ? `<span class="reason"><span class="sdot ${item.dot || 'herb'}" aria-hidden="true"></span>${esc(item.reason)}</span>` : ''}
      ${item.note ? `<span class="dish-note">${esc(item.note)}</span>` : ''}
    </span></button>`;
}

export const SOURCE_LEGEND = `<div class="legend" aria-label="Chú giải nguồn gợi ý">
  <span><span class="sdot herb" aria-hidden="true"></span>Khẩu vị giống bạn (ALS)</span>
  <span><span class="sdot chili" aria-hidden="true"></span>Khám phá (content)</span>
  <span><span class="sdot neutral" aria-hidden="true"></span>Phổ biến</span></div>`;

// Chu giai cua bieu do cot theo thang (charts.monthlyBars)
export const MONTH_LEGEND = `<div class="legend top" aria-label="Chú giải màu cột">
  <span><span class="sw mid" aria-hidden="true"></span>Train</span>
  <span><span class="sw chili" aria-hidden="true"></span>Tháng có Tết</span>
  <span><span class="sw slate" aria-hidden="true"></span>Val / test</span></div>`;

// Danh sach nho co anh: [{dish (DishCard), title, sub, num}]
export function miniList(rows) {
  return `<ul class="mini-list">${rows.map((r) => `<li class="mini">${dishThumb(r.dish)}
      <span><span class="t">${esc(r.title)}</span><br><span class="s">${esc(r.sub || '')}</span></span>
      ${r.num ? `<span class="n">${esc(r.num)}</span>` : ''}</li>`).join('')}</ul>`;
}

// ---------- Chi tiet mon (E13): anh, chip, thong ke ca nam mo phong, nguyen lieu, mon tuong tu, mon an kem ----------
export function dishDetail(d) {
  const st = d.stats || {};
  return `<div class="detail">
      <div class="detail-main">${dishImg(d)}
        <p class="chips" style="margin-top:10px">${dishChips(d)}<span class="chip">${esc(d.dish_category)}</span></p>
        <p class="sub-h">Cả năm mô phỏng</p>
        <p class="detail-text">${fmtInt(st.cooks)} lượt nấu, ${fmtInt(st.views)} lượt xem, điểm trung bình ${fmtNum(st.avg_rating, 2)} (${fmtInt(st.rates)} lượt chấm). Hạng ${fmtInt(st.cook_rank)} về lượt nấu.</p>
        <p class="sub-h">Nguyên liệu</p>
        <ul class="ing">${d.ingredient_list.map((i) => `<li>${esc(i)}</li>`).join('')}</ul>
      </div>
      <div class="detail-side">
        <p class="sub-h">Món tương tự</p>
        <div class="dish-grid">${d.similar.map((s) => dishCard(s, { showRank: false })).join('') || '<p class="state-msg">Chưa có món tương tự.</p>'}</div>
        <p class="sub-h">Món hay nấu cùng (FP-Growth)</p>
        ${d.companions.length ? miniList(d.companions.map((c) => ({ dish: c, title: c.dish_name,
            sub: `độ tin cậy ${fmtRatio(c.confidence)}, lift ${fmtNum(c.lift, 1)}`, num: '' })))
          : '<p class="state-msg">Món này chưa có luật món ăn kèm từ FP-Growth.</p>'}
      </div></div>`;
}
