// phan-khuc.js - trang Phan khuc nguoi dung: E15 cum K-means (k = 3 / 8 / 11), E16 nguoi dung trong cum k = 8.
// Persona that chi xuat hien o dong "Persona kiem chung (chi de kiem chung)" (skill muc 5).

import { getJSON, shared, qs, fmtInt, fmtPct, fmtNum, fmtRatio } from './api.js';
import { load, hbars, segmented, esc } from './components.js';
import { C, lines, divergingHeatmap } from './charts.js';

const $ = (id) => document.getElementById(id);
const cap = (s) => (s ? s[0].toUpperCase() + s.slice(1) : s);
const GROUP_LABEL = { 'ấm': 'ấm – nhiều lịch sử', 'ít': 'ít lịch sử', 'lạnh': 'lạnh – chưa có lịch sử' };
const segs = {};
const seg = (k) => (segs[k] ??= shared(`/segments${qs({ k })}`));
let k = 8;

segmented($('k-seg'), [3, 8, 11].map((x) => ({ value: String(x), label: `k = ${x}` })), String(k),
  (v) => { k = Number(v); renderK(); }, 'Số cụm');

// Gia tri dac trung: ty le (0..1) hien %, con lai hien so
const fmtFeat = (f, v) => (f.startsWith('share_') || f.startsWith('slot_') || f.endsWith('_per_view') || f.endsWith('_per_cook')
  ? fmtRatio(v, 1) : fmtNum(v, 2));

function renderK() {
  load($('k-note'), async (el) => {
    const s = await seg(k)();
    const at = (kk) => s.quality.find((q) => q.algo === 'KMeans' && q.k === kk) || {};
    const b = s.best_by_silhouette || {};
    el.dataset.state = 'ready';
    el.innerHTML = `<p class="lead">${fmtInt(s.n_users)} người dùng có ít nhất một lượt nấu trong lịch sử train được phân cụm.
      Silhouette cao nhất ở k = ${b.k} (${fmtNum(b.silhouette, 3)}), nhưng ${b.k} cụm quá thô để gợi ý.
      Dashboard dùng k = ${s.dashboard_k}: Silhouette ${fmtNum(at(8).silhouette, 3)}, ARI ${fmtNum(at(8).ari, 3)},
      NMI ${fmtNum(at(8).nmi, 3)}. k = 11 cho ARI cao nhất (${fmtNum(at(11).ari, 3)}), nhưng nhiều cụm hơn thì khó đặt chiến lược riêng cho từng cụm.</p>
      <p class="source">Đang xem k = ${s.k}: ${s.clusters.length} cụm.</p>`;
  });
  load($('sizes'), async (el) => {
    const s = await seg(k)();
    const tot = s.clusters.reduce((a, c) => a + c.n_users, 0);
    el.dataset.state = 'ready';
    el.innerHTML = hbars([...s.clusters].sort((a, b) => b.n_users - a.n_users).map((c) => ({
      label: `Cụm ${c.cluster} · ${c.label}`, value: c.n_users, text: fmtInt(c.n_users), note: fmtPct((100 * c.n_users) / tot) })), { wrap: true });
  });
  load($('profile'), async (el) => {
    const s = await seg(k)();
    const feats = s.feature_names;
    const data = [];
    s.clusters.forEach((c, yi) => feats.forEach((f, xi) => {
      const z = c.z[f.feature];
      data.push([xi, yi, Math.max(-2, Math.min(2, z)), '', `Cụm ${c.cluster} · ${f.label}<br>${fmtFeat(f.feature, c.features[f.feature])}
        (trung bình các cụm ${fmtFeat(f.feature, s.feature_means[f.feature])}), z = ${fmtNum(z, 2)}`]);
    }));
    el.dataset.state = 'ready';
    el.innerHTML = `<div class="chart" style="min-width:${160 + feats.length * 30}px;height:${170 + s.clusters.length * 30}px"></div>`;
    divergingHeatmap(el.firstElementChild, feats.map((f) => f.label), s.clusters.map((c) => `Cụm ${c.cluster}`), data,
      { min: -2, max: 2, center: 0, label: false, xRotate: 40, legendText: ['cao hơn', 'thấp hơn'] });
  }, 320);
  load($('cluster-cards'), async (el) => {
    const s = await seg(k)();
    const tot = s.clusters.reduce((a, c) => a + c.n_users, 0);
    el.dataset.state = 'ready';
    el.innerHTML = `<div class="cl-grid">${s.clusters.map((c) => `<div class="cl">
      <h3>Cụm ${c.cluster}: ${esc(c.label)}</h3>
      <span class="meta">${fmtInt(c.n_users)} người dùng (${fmtPct((100 * c.n_users) / tot)})</span>
      <p class="sub-h" style="margin:4px 0 0">Đặc trưng nổi bật</p>
      <ul>${c.top_features.map((t) => `<li><span class="${t.z > 0 ? 'tag-up' : 'tag-down'}">${t.z > 0 ? 'Cao' : 'Thấp'}</span>
        ${esc(t.label.toLowerCase())}: ${fmtFeat(t.feature, c.features[t.feature])}</li>`).join('')}</ul>
      <p class="sub-h" style="margin:4px 0 0">Đề xuất</p>
      <ul>${c.strategy.map((x) => `<li>${esc(x)}</li>`).join('')}</ul>
      <span class="verify">Persona kiểm chứng (chỉ để kiểm chứng): ${esc(cap(c.persona_kiem_chung))}, ${fmtRatio(c.persona_share, 0)} người trong cụm</span>
    </div>`).join('')}</div>`;
  });
}
renderK();

// ---------- Chat luong phan cum theo k (E15.quality) ----------
load($('quality'), async (el) => {
  const s = await seg(8)();
  const q = s.quality.filter((x) => x.algo === 'KMeans').sort((a, b) => a.k - b.k);
  el.dataset.state = 'ready';
  el.innerHTML = '<div class="chart"></div>';
  lines(el.firstElementChild, q.map((x) => String(x.k)), [
    { name: 'Silhouette', data: q.map((x) => x.silhouette), color: C.herb },
    { name: 'ARI (kiểm chứng)', data: q.map((x) => x.ari), color: C.chili },
    { name: 'NMI (kiểm chứng)', data: q.map((x) => x.nmi), color: C.slate }],
  { yMin: 0, xName: 'số cụm k', yFmt: (v) => fmtNum(v, 2), markX: ['3', '8', '11'] });
});

// ---------- Nguoi dung trong cum k = 8 (E16) ----------
seg(8)().then((s) => {
  $('cluster-select').innerHTML = s.clusters.map((c) => `<option value="${c.cluster}">Cụm ${c.cluster}: ${esc(c.label)}</option>`).join('');
  loadMembers();
}).catch(() => loadMembers());
$('cluster-select').addEventListener('change', loadMembers);

function loadMembers() {
  const c = Number($('cluster-select').value || 0);
  load($('members'), async (el) => {
    const r = await getJSON(`/segments/8/${c}${qs({ sample: 8 })}`);
    const bars = (rows, lab = (v) => v) => hbars(rows.map((x) => ({ label: lab(x.value), value: x.share_pct, text: fmtPct(x.share_pct),
      note: fmtInt(x.n_users) })), { max: 100 });
    el.dataset.state = 'ready';
    el.innerHTML = `<div class="mini-grid">
      <div><h3>Vùng</h3>${bars(r.by_region)}</div>
      <div><h3>Nhóm tuổi</h3>${bars(r.by_age)}</div>
      <div><h3>Nhóm theo lịch sử</h3>${bars(r.by_group, (v) => GROUP_LABEL[v] || v)}</div>
      <div><h3>Người dùng mẫu</h3><ul class="steps">${r.sample_users.map((u) => `<li>
        <a href="goi-y.html?user=${u.user_id}">#${u.user_id}</a><span>${esc(u.region)}, ${esc(u.age_group)} tuổi</span>
        <span class="sec">${fmtInt(u.n_cook)} lượt nấu</span></li>`).join('')}</ul>
        <p class="source">Bấm mã người dùng để xem gợi ý của người đó.</p></div></div>
      <p class="source">Cụm ${r.cluster} có ${fmtInt(r.n_users)} người dùng. Truy vấn <code>users</code> theo index <code>cluster_k8</code>.</p>`;
  });
}
