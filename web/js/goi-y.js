// goi-y.js - trang Goi y mon: E17 user mau, E18 ho so, E19 goi y user co san, E20 user moi, E12 tim mon, E13 chi tiet

import { getJSON, shared, postJSON, qs, fmtInt, fmtRatio, fmtNum } from './api.js';
import { load, showEmpty, showLoading, showError, segmented, filterBar, dishCard, dishImg, dishThumb, dishChips,
         hbars, miniList, SOURCE_LEGEND, esc } from './components.js';

const $ = (id) => document.getElementById(id);
const GROUP_LABEL = { 'ấm': 'ấm – nhiều lịch sử', 'ít': 'ít lịch sử', 'lạnh': 'lạnh – chưa có lịch sử' };
const MAX_CHOSEN = 10;
const cap = (s) => (s ? s[0].toUpperCase() + s.slice(1) : s);

const state = {
  mode: 'existing',
  userId: null,
  filters: { veg: false, quick: false, not_spicy: false, meal: null, category: null },
  chosen: [],          // [{food_id, dish_name, image_link, dish_category}]
  region: null, age: null,
  selected: null,
};
let ctrl = null;       // AbortController cua request goi y dang chay
let summaryEl = null;

const meta = shared('/meta/filters');
const demo = shared('/users/demo');

// ---------- Che do ----------
segmented($('mode'), [{ value: 'existing', label: 'Người dùng có sẵn' }, { value: 'new', label: 'Người dùng mới' }],
  'existing', (v) => {
    state.mode = v;
    $('user-form').hidden = v !== 'existing';
    $('tb-note').hidden = v !== 'existing';
    $('side').hidden = v !== 'existing';
    $('newuser').hidden = v !== 'new';
    refreshRecs();
  }, 'Cách gợi ý');

// ---------- Menu user mau (E17): theo nhom am / it / lanh va theo persona (chi de kiem chung) ----------
function demoOption(u, prefix = '') {
  return `<option value="${u.user_id}">${esc(prefix)}#${u.user_id} · ${esc(u.region)}, ${esc(u.age_group)} tuổi</option>`;
}

async function loadDemo() {
  const sel = $('demo-select');
  try {
    const d = await demo();
    const groups = Object.entries(d.by_group).map(([g, us]) =>
      `<optgroup label="Nhóm ${esc(GROUP_LABEL[g] || g)}">${us.map((u) => demoOption(u)).join('')}</optgroup>`).join('');
    const personas = `<optgroup label="Theo persona – chỉ để kiểm chứng">${d.by_persona.map((p) =>
      p.users.map((u) => demoOption(u, `${cap(p.persona)} – `)).join('')).join('')}</optgroup>`;
    sel.innerHTML = `<option value="">Chọn user mẫu…</option>${groups}${personas}`;
    sel.value = state.userId ? String(state.userId) : '';
    return d;
  } catch (e) {
    sel.innerHTML = '<option value="">Không tải được user mẫu</option>';
    return null;
  }
}

$('demo-select').addEventListener('change', (e) => {
  const v = Number(e.target.value);
  if (v) selectUser(v);
});

$('user-form').addEventListener('submit', (e) => {
  e.preventDefault();
  const v = Number($('user-input').value);
  if (v > 0) selectUser(v);
});

function selectUser(id) {
  if (!id) return;
  state.userId = id;
  state.selected = null;
  $('user-input').value = id;
  const sel = $('demo-select');
  sel.value = [...sel.options].some((o) => o.value === String(id)) ? String(id) : '';
  $('detail-card').hidden = true;
  history.replaceState(null, '', `?user=${id}`);
  loadProfile();
  refreshRecs();
}

// ---------- Ho so va mon hay nau (E18, khong co persona that) ----------
function loadProfile() {
  const id = state.userId;
  $('profile-note').textContent = `người dùng #${id}`;
  const user = shared(`/users/${id}`);   // 2 the dung chung 1 request; loi thi "Thu lai" goi lai
  load($('profile'), async (el) => {
    const u = await user();
    const p = u.profile || {};
    el.dataset.state = 'ready';
    const items = [['Vùng', u.region], ['Tuổi', u.age_group], ['Giới tính', u.gender],
      ['Nhóm', GROUP_LABEL[u.group] || u.group], ['Cụm (k = 8)', u.cluster_k8 ?? 'chưa có'],
      ['Bữa hay nấu', p.pref_slot || 'chưa có'], ['Lượt nấu', fmtInt(p.n_cook)], ['Lượt chấm', fmtInt(p.n_rate)]];
    const shares = [['Món chay', p.share_chay], ['Hải sản', p.share_haisan], ['Món ngọt', p.share_ngot],
      ['Món nhanh', p.share_nhanh], ['Món cay', p.share_cay]].filter((s) => s[1] != null);
    el.innerHTML = `<dl class="profile-grid">${items.map(([k, v]) => `<div><dt>${k}</dt><dd>${esc(v ?? '–')}</dd></div>`).join('')}</dl>
      ${shares.length ? `<p class="sub-h">Tỷ trọng trong các món đã nấu</p>${hbars(shares.map(([k, v]) => ({ label: k, value: v, text: fmtRatio(v, 0) })), { max: 1 })}` : ''}`;
  });
  load($('history'), async (el) => {
    const u = await user();
    el.dataset.state = 'ready';
    el.innerHTML = u.history.length
      ? miniList(u.history.map((h) => ({ dish: h, title: h.dish_name,
        sub: `lần gần nhất ${h.last_cook ? h.last_cook.slice(0, 10).split('-').reverse().join('/') : '–'}`, num: `${h.n_cook} lần` })))
      : '<p class="state-msg">Người này chưa nấu món nào trước 01/09/2026, nên gợi ý dựa vào món phổ biến và món đã xem.</p>';
  });
}

// ---------- Nguoi dung moi: tim mon, chon mon ----------
let searchTimer = null;
$('search').addEventListener('input', () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(runSearch, 250);
});

async function runSearch() {
  const q = $('search').value.trim();
  const box = $('search-results');
  if (q.length < 2) { box.innerHTML = ''; return; }
  try {
    const rs = await getJSON(`/dishes/search${qs({ q, limit: 8 })}`);
    if (!rs.length) { box.innerHTML = `<p class="state-msg">Không tìm thấy món nào có tên chứa "${esc(q)}".</p>`; return; }
    const full = state.chosen.length >= MAX_CHOSEN;
    box.innerHTML = rs.map((d) => {
      const has = state.chosen.some((c) => c.food_id === d.food_id);
      return `<button type="button" class="result-btn" data-add="${d.food_id}" ${has || full ? 'disabled' : ''}>
        ${dishThumb(d)}${esc(d.dish_name)}</button>`;
    }).join('');
    box.querySelectorAll('[data-add]').forEach((b, i) => b.addEventListener('click', () => addChosen(rs[i])));
  } catch (e) {
    box.innerHTML = `<p class="state-msg" role="alert">${esc(e.message)}</p>`;
  }
}

function addChosen(d) {
  if (state.chosen.length >= MAX_CHOSEN || state.chosen.some((c) => c.food_id === d.food_id)) return;
  state.chosen.push({ food_id: d.food_id, dish_name: d.dish_name, image_link: d.image_link, dish_category: d.dish_category });
  renderChosen();
  runSearch();
  refreshRecs();
}

function renderChosen() {
  $('chosen').innerHTML = state.chosen.length
    ? state.chosen.map((c) => `<span class="chosen-chip">${esc(c.dish_name)}<button type="button" data-rm="${c.food_id}" aria-label="Bỏ món ${esc(c.dish_name)}">×</button></span>`).join('')
    : '<p class="state-msg">Chưa chọn món nào. Gõ tên món ở trên rồi bấm để thêm.</p>';
}
$('chosen').addEventListener('click', (e) => {
  const b = e.target.closest('[data-rm]');
  if (!b) return;
  state.chosen = state.chosen.filter((c) => c.food_id !== Number(b.dataset.rm));
  renderChosen();
  runSearch();
  refreshRecs();
});
renderChosen();

// ---------- Bo loc + goi y ----------
meta().then((m) => {
  summaryEl = filterBar($('filters'), state.filters, m, () => refreshRecs());
  $('nu-region').innerHTML += m.regions.map((r) => `<option value="${esc(r)}">${esc(r)}</option>`).join('');
  $('nu-age').innerHTML += m.age_groups.map((a) => `<option value="${esc(a)}">${esc(a)}</option>`).join('');
}).catch((e) => showError($('filters'), e));
$('nu-region').addEventListener('change', (e) => { state.region = e.target.value || null; refreshRecs(); });
$('nu-age').addEventListener('change', (e) => { state.age = e.target.value || null; refreshRecs(); });

async function refreshRecs() {
  const body = $('recs');
  if (ctrl) ctrl.abort();
  ctrl = new AbortController();
  const { signal } = ctrl;
  $('legend').innerHTML = '';
  $('recs-foot').textContent = '';
  if (summaryEl) summaryEl.textContent = '';
  if (state.mode === 'new' && !state.chosen.length) {
    $('recs-title').textContent = 'Món gợi ý';
    showEmpty(body, 'Chọn ít nhất một món bạn thích để xem gợi ý.');
    return;
  }
  if (state.mode === 'existing' && !state.userId) return;
  showLoading(body, 260);
  try {
    let r;
    if (state.mode === 'existing') {
      r = await getJSON(`/recs/${state.userId}${qs(state.filters)}`, { signal });
      $('recs-title').textContent = `Món gợi ý cho người dùng #${state.userId}`;
    } else {
      r = await postJSON('/recs/new-user', { food_ids: state.chosen.map((c) => c.food_id), region: state.region,
        age_group: state.age, ...state.filters }, { signal });
      $('recs-title').textContent = 'Món gợi ý từ các món bạn chọn';
    }
    renderRecs(r);
  } catch (e) {
    if (e.name === 'AbortError') return;
    showError(body, e, refreshRecs);
  }
}

function renderRecs(r) {
  const body = $('recs');
  if (!r.items.length) { showEmpty(body, 'Không có món nào thỏa bộ lọc này. Hãy bỏ bớt một điều kiện.'); return; }
  body.dataset.state = 'ready';
  body.innerHTML = `<div class="dish-grid">${r.items.map((x) => dishCard(x, { selected: x.food_id === state.selected })).join('')}</div>`;
  $('legend').innerHTML = SOURCE_LEGEND;
  const s = r.summary;
  if (summaryEl) {
    summaryEl.textContent = state.mode === 'existing'
      ? `${s.from_recs} món từ gợi ý cá nhân · ${s.from_fill} món bù từ danh mục phổ biến`
      : `${s.from_recs} món giống món bạn chọn · ${s.from_popular + s.from_fill} món phổ biến`;
  }
  if (state.mode === 'existing') {
    const cooked = r.items.filter((x) => x.n_cook_before).length;
    $('recs-foot').textContent = (s.n_test_cooks
      ? `${s.hits}/${r.items.length} món có trong lượt nấu tháng 9/2026 của người này (tháng 9 có ${s.n_test_cooks} món đã nấu). Mô hình không thấy dữ liệu tháng 9.`
      : 'Người này không có lượt nấu nào trong tháng 9/2026, nên không đối chiếu được.')
      + (cooked ? ` ${cooked} món người này đã nấu trước đó: nấu lại cũng được tính là gợi ý trúng.` : '');
  } else {
    $('recs-foot').textContent = 'Gợi ý dựa trên độ giống nhau giữa các món (TF-IDF trên nguyên liệu, cách chế biến, nhóm món).';
  }
}

$('recs').addEventListener('click', (e) => {
  const b = e.target.closest('.dish');
  if (!b) return;
  state.selected = Number(b.dataset.id);
  $('recs').querySelectorAll('.dish').forEach((x) => x.setAttribute('aria-pressed', String(x === b)));
  showDetail(state.selected);
});

// Bam mon tuong tu trong khung chi tiet -> xem chi tiet mon do
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
    const st = d.stats || {};
    el.dataset.state = 'ready';
    el.innerHTML = `<div class="detail">
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
    card.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }, 240);
}

// ---------- Khoi dong: ?user= tren URL, khong thi user am dau tien ----------
loadDemo().then((d) => {
  const fromUrl = Number(new URLSearchParams(location.search).get('user'));
  selectUser(fromUrl || d?.by_group['ấm']?.[0]?.user_id);
});
