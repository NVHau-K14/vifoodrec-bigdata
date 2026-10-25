// components.js - thanh phan dung chung (skill muc 4): the mon, chip loc, thanh ngang, vien trang thai,
// khung tai / loi / rong. Khong co ma mau: moi mau qua class trong theme.css.

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
export function hbars(rows, { max } = {}) {
  const m = max ?? Math.max(...rows.map((r) => r.value), 0);
  return `<div class="hbars">${rows.map((r) => {
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
export function filterBar(el, state, meta, onChange) {
  el.className = 'filters';
  el.innerHTML = '';
  const fire = () => onChange({ ...state });
  el.append(toggleChip('Chay', state.veg, (v) => { state.veg = v; fire(); }));
  el.append(toggleChip('Món nhanh', state.quick, (v) => { state.quick = v; fire(); }));
  el.append(toggleChip('Không cay', state.not_spicy, (v) => { state.not_spicy = v; fire(); }));
  const seg = document.createElement('div');
  const meals = [{ value: '', label: 'Tất cả bữa' }, ...meta.meal_types.map((m) => ({ value: m, label: m[0].toUpperCase() + m.slice(1) }))];
  segmented(seg, meals, state.meal || '', (v) => { state.meal = v || null; fire(); }, 'Bữa');
  el.append(seg);
  const wrap = document.createElement('label');
  wrap.className = 'field';
  wrap.innerHTML = `<span class="sr-only">Nhóm món</span><select><option value="">Mọi nhóm món</option>${meta.categories.map((c) => `<option value="${esc(c)}"${c === state.category ? ' selected' : ''}>${esc(c)}</option>`).join('')}</select>`;
  wrap.querySelector('select').addEventListener('change', (e) => { state.category = e.target.value || null; fire(); });
  el.append(wrap);
  const sum = document.createElement('span');
  sum.className = 'filters-summary';
  sum.setAttribute('aria-live', 'polite');
  el.append(sum);
  return sum;
}

// ---------- The mon ----------
const PH = { 'Món chay': 'ph-chay', 'Món mặn': 'ph-man', 'Món ngọt': 'ph-ngot', 'Đồ uống': 'ph-uong' };
const PLACEHOLDER = 'img/placeholder-dish.svg';

export function dishChips(d) {
  const c = [];
  if (d.is_vegetarian) c.push('Chay');
  if (d.is_quick) c.push('Món nhanh');
  if (d.is_spicy) c.push('Cay');
  if (d.meal_types?.length) c.push(d.meal_types.join(' · '));
  return c.map((x) => `<span class="chip">${esc(x)}</span>`).join('');
}

export function dishImg(d, cls = '') {
  const src = d.image_link || PLACEHOLDER;
  const ph = d.image_link ? '' : ' class="ph"';
  return `<div class="dish-img ${PH[d.dish_type_fixed] || ''} ${cls}"><img src="${esc(src)}"${ph} alt="" loading="lazy" referrerpolicy="no-referrer" data-ph></div>`;
}

// Anh loi -> placeholder (gan 1 lan cho ca vung chua)
export function wireImgFallback(root) {
  root.addEventListener('error', (e) => {
    const img = e.target;
    if (img.tagName === 'IMG' && img.hasAttribute('data-ph') && !img.src.endsWith(PLACEHOLDER)) {
      img.src = PLACEHOLDER;
      img.classList.add('ph');
    }
  }, true);
}

// item: DishCard (+ rank, reason, dot, hit). Ca the la 1 <button>
export function dishCard(item, { selected = false, showRank = true } = {}) {
  return `<button type="button" class="dish" data-id="${item.food_id}" aria-pressed="${selected}">
    <div style="position:relative">${dishImg(item)}
      ${showRank && item.rank ? `<span class="dish-rank" aria-label="Hạng ${item.rank}">${item.rank}</span>` : ''}
      ${item.hit ? '<span class="dish-tag">Đã nấu T9</span>' : ''}</div>
    <div class="dish-body">
      <span class="dish-name">${esc(item.dish_name)}</span>
      <span class="chips">${dishChips(item)}</span>
      ${item.reason ? `<span class="reason"><span class="sdot ${item.dot || 'herb'}" aria-hidden="true"></span>${esc(item.reason)}</span>` : ''}
    </div></button>`;
}

export const SOURCE_LEGEND = `<div class="legend" aria-label="Chú giải nguồn gợi ý">
  <span><span class="sdot herb" aria-hidden="true"></span>Khẩu vị giống bạn (ALS)</span>
  <span><span class="sdot chili" aria-hidden="true"></span>Khám phá (content)</span>
  <span><span class="sdot neutral" aria-hidden="true"></span>Phổ biến</span></div>`;

// Danh sach nho co anh: [{img, title, sub, num}]
export function miniList(rows) {
  return `<ul class="mini-list">${rows.map((r) => `<li class="mini">
      <img src="${esc(r.img || PLACEHOLDER)}" alt="" loading="lazy" referrerpolicy="no-referrer" data-ph>
      <span><span class="t">${esc(r.title)}</span><br><span class="s">${esc(r.sub || '')}</span></span>
      ${r.num ? `<span class="n">${esc(r.num)}</span>` : ''}</li>`).join('')}</ul>`;
}
