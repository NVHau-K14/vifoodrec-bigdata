// danh-gia.js - trang Danh gia mo hinh: E23 (xep hang, KTC), E24 (RMSE, ALS, LSH, FP-Growth, doi chung, thoi gian,
// hieu nang Spark 1 / 2 worker x 10 / 50 / 100% - D17)

import { getJSON, shared, qs, fmtFixed, fmtNum, fmtPct, fmtRatio, fmtSeconds, fmtInt } from './api.js';
import { load, hbars, segmented, esc, showEmpty } from './components.js';
import { C, lines, groupedBars, hGroupedBars } from './charts.js';

const $ = (id) => document.getElementById(id);
const METRICS = ['ndcg@10', 'p@10', 'r@10', 'ap@10', 'ndcg@5', 'p@5', 'r@5', 'ap@5'];
const METRIC_LABEL = { ndcg: 'NDCG', p: 'Precision', r: 'Recall', ap: 'MAP' };
const mLabel = (m) => { const [k, n] = m.split('@'); return `${METRIC_LABEL[k]}@${n}`; };
const rank = { view: 'test', group: 'tất cả', metric: 'ndcg@10' };
const details = shared('/eval/details');

$('metric').innerHTML = METRICS.map((m) => `<option value="${m}">${mLabel(m)}</option>`).join('');
$('metric').addEventListener('change', (e) => { rank.metric = e.target.value; loadRanking(); });
segmented($('seg-view'), [{ value: 'test', label: 'Test (09/2026)' }, { value: 'val', label: 'Val (08/2026)' }], 'test',
  (v) => { rank.view = v; loadRanking(); }, 'Tập đánh giá');
segmented($('seg-group'), ['tất cả', 'ấm', 'ít', 'lạnh'].map((g) => ({ value: g, label: g[0].toUpperCase() + g.slice(1) })),
  'tất cả', (v) => { rank.group = v; loadRanking(); }, 'Nhóm người dùng');

function loadRanking() {
  load($('ranking'), async (el) => {
    const r = await getJSON(`/eval/ranking${qs({ view: rank.view, variant: 'chính', group: rank.group })}`);
    const rows = r.rows.map((x) => ({ label: x.label, value: x.metrics[rank.metric], text: fmtFixed(x.metrics[rank.metric], 4),
      tone: x.kind === 'chính' ? '' : 'neutral' })).sort((a, b) => b.value - a.value);
    $('rank-note').textContent = `${mLabel(rank.metric)}, ${fmtInt(r.rows[0]?.metrics.n_users)} người dùng`;
    el.dataset.state = 'ready';
    el.innerHTML = hbars(rows);
  });
}
loadRanking();

load($('ci'), async (el) => {
  const r = await getJSON(`/eval/ranking${qs({ view: 'test', variant: 'chính', group: 'tất cả' })}`);
  const sign = (v) => (v > 0 ? '+' : '') + fmtFixed(v, 4);
  el.dataset.state = 'ready';
  el.innerHTML = `<div class="scroll-x"><table class="tbl"><thead><tr><th>So sánh</th><th>Hiệu</th><th>KTC 95%</th><th>Kết luận</th></tr></thead>
    <tbody>${r.ci95.map((c) => {
      const sig = c.ci95[0] > 0 || c.ci95[1] < 0;
      const verdict = !sig ? 'chưa phân biệt' : c.hieu > 0 ? 'vế trái tốt hơn' : 'vế trái kém hơn';
      return `<tr><td>${esc(c.label)}</td><td>${sign(c.hieu)}</td><td>[${fmtFixed(c.ci95[0], 4)}; ${fmtFixed(c.ci95[1], 4)}]</td><td>${verdict}</td></tr>`;
    }).join('')}</tbody></table></div>`;
});

load($('beyond'), async (el) => {
  const [b, k] = await Promise.all([
    getJSON(`/eval/ranking${qs({ view: 'test', variant: 'ngoài độ chính xác', group: 'tất cả' })}`),
    getJSON(`/eval/ranking${qs({ view: 'test', variant: 'khám phá', group: 'tất cả' })}`)]);
  const d = await details();
  const kd = Object.fromEntries(k.rows.map((x) => [x.model, x.metrics]));
  const rows = b.rows.slice().sort((x, y) => (x.kind === y.kind ? y.metrics.coverage_pct - x.metrics.coverage_pct : x.kind === 'chính' ? -1 : 1));
  el.dataset.state = 'ready';
  el.innerHTML = `<table class="tbl" style="min-width:640px"><thead><tr><th>Mô hình</th><th>Coverage</th><th>Novelty</th>
    <th>Diversity</th><th>NDCG@10 khám phá</th><th>Recall món mới @10</th></tr></thead><tbody>${rows.map((x) => {
      const nr = d.new_item_recall[x.model];
      return `<tr><td>${esc(x.label)}</td><td>${fmtPct(x.metrics.coverage_pct)}</td><td>${fmtNum(x.metrics.novelty, 2)}</td>
        <td>${fmtNum(x.metrics.diversity, 3)}</td><td>${fmtFixed(kd[x.model]?.['ndcg@10'], 4)}</td>
        <td>${nr == null ? '–' : fmtRatio(nr, 2)}</td></tr>`;
    }).join('')}</tbody></table>
    <p class="source">Recall món mới: 300 món bị giấu khỏi dữ liệu train, đo tỷ lệ món giấu được gợi ý trong top 10 (chỉ đo cho một số mô hình).</p>`;
});

load($('rmse'), async (el) => {
  const d = await details();
  el.dataset.state = 'ready';
  el.innerHTML = hbars(d.rmse.rows.map((r) => ({ label: r.label, value: r.rmse, text: fmtFixed(r.rmse, 3),
    tone: r.model === 'als_explicit' ? '' : 'neutral' }))) +
    `<p class="source">${fmtInt(d.rmse.n)} lượt chấm tháng test mà cả 3 mô hình đều dự đoán được.</p>`;
});

load($('als'), async (el) => {
  const d = await details();
  const g = d.als_grid;
  const byAlpha = g.filter((x) => x.rank === 32 && x.weights === '1/3/5').sort((a, b) => a.alpha - b.alpha);
  const byRank = g.filter((x) => x.alpha === 1 && x.weights === '1/3/5').sort((a, b) => a.rank - b.rank);
  const w = g.filter((x) => x.alpha === d.als_best.alpha && x.rank === d.als_best.rank);
  el.dataset.state = 'ready';
  el.innerHTML = `<div class="split"><div><p class="sub-h">Theo alpha (rank 32)</p><div class="chart chart-sm"></div></div>
    <div><p class="sub-h">Theo rank (alpha 1)</p><div class="chart chart-sm"></div></div></div>
    <p class="source">Trọng số sự kiện ở cấu hình chọn (alpha ${fmtNum(d.als_best.alpha)}, rank ${d.als_best.rank}, regParam ${fmtNum(d.als_best.regParam)}):
    ${w.map((x) => `${esc(x.weights)} = ${fmtFixed(x['ndcg@10'], 4)}`).join('; ')}.
    Hybrid dùng ALS ${fmtNum(d.hybrid_weights.als)} và nấu lại ${fmtNum(d.hybrid_weights.rep)}.</p>`;
  const [c1, c2] = el.querySelectorAll('.chart');
  lines(c1, byAlpha.map((x) => fmtNum(x.alpha)), [{ name: 'NDCG@10', data: byAlpha.map((x) => x['ndcg@10']) }],
    { yFmt: (v) => fmtFixed(v, 3), xName: 'alpha' });
  groupedBars(c2, byRank.map((x) => `rank ${x.rank}`), [{ name: 'NDCG@10', data: byRank.map((x) => x['ndcg@10']), color: C.herb }],
    { yFmt: (v) => fmtFixed(v, 3) });
}, 240);

load($('lsh'), async (el) => {
  const d = await details();
  el.dataset.state = 'ready';
  el.innerHTML = '<div class="chart chart-sm"></div>' +
    `<p class="source">${d.lsh.map((x) => `${x.numHashTables} bảng băm: ${fmtSeconds(x.seconds)}`).join('; ')}.</p>`;
  lines(el.firstElementChild, d.lsh.map((x) => `${x.numHashTables} bảng`), [{ name: 'recall@20', data: d.lsh.map((x) => x['recall@20']) }],
    { yFmt: (v) => fmtRatio(v, 0) });
}, 220);

load($('fp'), async (el) => {
  const d = await details();
  el.dataset.state = 'ready';
  el.innerHTML = hbars(d.fpgrowth_hit.map((r, i) => ({ label: r.label, value: r.value, text: fmtRatio(r.value, 1), tone: i ? 'neutral' : '' }))) +
    '<p class="source">Cho một món trong phiên nấu, đoán 3 món còn lại; tính tỷ lệ đoán trúng ít nhất một món.</p>';
});

load($('control'), async (el) => {
  const d = await details();
  const c = d.control_06g;
  el.dataset.state = 'ready';
  el.innerHTML = '<div class="chart"></div>' +
    `<p class="lead">Trên ratings gốc (${fmtInt(c.rows.all)} lượt chấm, ${fmtInt(c.rows.users)} người dùng), ALS kém hơn trung bình chung ${fmtPct(Math.abs(c.als_vs_mean_pct_goc))}.
     Trên dữ liệu mô phỏng, ALS tốt hơn trung bình chung ${fmtPct(c.als_vs_mean_pct_mo_phong)}. Với ratings gốc, lọc cộng tác không học được gì hơn
     trung bình chung, vì vậy dự án dùng hành vi mô phỏng.</p>`;
  groupedBars(el.firstElementChild, c.goc.map((x) => x.label),
    [{ name: 'Ratings gốc', data: c.goc.map((x) => x.rmse), color: C.slate },
     { name: 'Mô phỏng', data: c.mo_phong.map((x) => x.rmse), color: C.herb }], { yFmt: (v) => fmtFixed(v, 2) });
}, 280);

load($('timings'), async (el) => {
  const d = await details();
  el.dataset.state = 'ready';
  el.innerHTML = hbars(d.timings.map((t) => ({ label: t.step, value: t.seconds, text: fmtSeconds(t.seconds) }))) +
    '<p class="source">Lần chạy thật, có dò tham số. So sánh 1 và 2 worker (chỉ fit một lần) ở thẻ Hiệu năng Spark.</p>';
});

// ---------- Hieu nang Spark (D17): 4 bieu do tu E24.perf ----------
const CHAIN = ['04', '05', '06a', '06b', '06c', '06d', '06e', '06f'];
const LEVEL = { s010: '10%', s050: '50%', s100: '100%' };
const levelsAll = ['s010', 's050', 's100'];
const minutes = (s) => (s == null ? null : Math.round((s / 60) * 10) / 10);

load($('perf'), async (el) => {
  const p = (await details()).perf;
  if (!p.available) {
    showEmpty(el, 'Chưa có kết quả đo hiệu năng (collection perf trống). Chạy scripts/09_perf.py rồi 07 --only perf.');
    return;
  }
  const at = (level, w, job) => p.rows.find((r) => r.level === level && r.workers === w && r.job === job);
  const chain = (level, w) => p.chain_totals.find((c) => c.level === level && c.workers === w);
  const jobs = CHAIN.filter((j) => at('s100', 1, j) || at('s100', 2, j));
  const c1 = chain('s100', 1);
  const c2 = chain('s100', 2);
  const failed = p.rows.filter((r) => r.failed > 0)
    .map((r) => `${r.job} ở ${LEVEL[r.level] || 'danh mục'}, ${r.workers} worker (${r.failed} lần lỗi)`);
  const sp = [...p.speedup.filter((s) => s.level === 's100'), ...p.speedup.filter((s) => s.level === 'catalog')];
  const sp10 = (job) => p.speedup.find((s) => s.level === 's010' && s.job === job)?.speedup ?? null;
  const bs = p.speedup_by_scale || [];
  const bsAt = (key, level) => bs.find((b) => b.key === key && b.level === level)?.speedup ?? null;
  const bsChain = levelsAll.map((l) => bsAt('chain', l));
  // cau hinh chay nhieu lan (lay trung vi), suy tu rows: "05 ở 100% (1 và 2 worker)"
  const reps = {};
  p.rows.filter((r) => r.n_runs > 1).forEach((r) => {
    const k = `${r.job}|${r.level}`;
    (reps[k] = reps[k] || { job: r.job, level: r.level, n: r.n_runs, w: [] }).w.push(r.workers);
  });
  const repText = (lv) => Object.values(reps).filter((x) => !lv || x.level === lv)
    .map((x) => `${x.job} ở ${LEVEL[x.level]} (${x.w.sort().join(' và ')} worker, ${x.n} lần)`).join('; ');
  el.dataset.state = 'ready';
  el.innerHTML = `<p class="lead">${c1 && c2 ? `Ở 100% dữ liệu, chuỗi 04 → 06f mất ${fmtSeconds(c2.total_s)} với 2 worker và
      ${fmtSeconds(c1.total_s)} với 1 worker (speedup ${fmtFixed(c1.total_s / c2.total_s, 2)}, lý tưởng là 2).` : ''}
      1 worker giảm cả số core (4 → 2) lẫn bộ nhớ executor (4 → 2 GB). Mọi container chạy trên cùng một máy, nên shuffle giữa
      2 worker đi qua mạng ảo của Docker.${bsChain.every((v) => v != null) ? ` Speedup của cả chuỗi theo mức dữ liệu:
      ${bsChain.map((v, i) => `${fmtFixed(v, 2)} ở ${LEVEL[levelsAll[i]]}`).join(', ')}.` : ''}</p>
    <div class="mini-grid">
      <div><h3>Thời gian từng job ở 100%</h3><div class="chart" id="perf-jobs"></div>
        <p class="source">Phút, theo Spark History Server. Trung vị nhiều lần: ${esc(repText('s100'))}; còn lại 1 lần.</p></div>
      <div><h3>Tổng chuỗi 04 → 06f theo quy mô dữ liệu</h3><div class="chart" id="perf-scale"></div>
        <p class="source">10% và 50% là dân số sinh mới (04 --scale), không phải tập con của bản 100%.</p></div>
    </div>
    <div class="mini-grid">
      <div><h3>Speedup từng job: 2 worker so với 1 worker</h3><div class="chart chart-tall" id="perf-speedup"></div>
        <p class="source">T(1 worker) ÷ T(2 worker); vạch đứt là mức lý tưởng 2, dưới 1 là 1 worker nhanh hơn. Ở 10%, phần cố định
          (khởi động, đọc danh mục, lập lịch task) chiếm phần lớn thời gian nên thêm worker không có lợi.</p></div>
      <div><h3>Speedup theo quy mô dữ liệu</h3><div class="chart chart-tall" id="perf-by-scale"></div>
        <p class="source">${esc(['04', '05', '06b'].map((k) => bs.find((b) => b.key === k)?.step || k).join(' · '))}.
          T(1 worker) ÷ T(2 worker) ở từng mức; vạch đứt là mức lý tưởng 2. Trung vị nhiều lần: ${esc(repText())};
          còn lại 1 lần mỗi cấu hình.</p></div>
    </div>
    <p class="source">06b, 06c, 06e, 06f, 06g chạy --fixed (fit một lần với tham số đã chọn). Dữ liệu hành vi mô phỏng.
      ${failed.length ? `Lần lỗi: ${esc(failed.join('; '))}.` : ''}</p>`;
  const stepOf = (j) => at('s100', 2, j)?.step || at('s100', 1, j)?.step || j;
  groupedBars($('perf-jobs'), jobs, [
    { name: '1 worker', data: jobs.map((j) => minutes(at('s100', 1, j)?.median_s)), color: C.slate },
    { name: '2 worker', data: jobs.map((j) => minutes(at('s100', 2, j)?.median_s)), color: C.herb },
  ], { yFmt: (v) => fmtNum(v, 1), labelMinWidth: 520 }).setOption({ xAxis: { axisLabel: { interval: 0 } }, tooltip: { formatter: (ps) => `${esc(stepOf(ps[0].name))}<br>` +
    ps.map((x) => `${x.marker}${x.seriesName}: ${x.value == null ? 'lỗi / không đo' : `${fmtNum(x.value, 1)} phút`}`).join('<br>') } });
  lines($('perf-scale'), levelsAll.map((l) => LEVEL[l]), [
    { name: '1 worker', data: levelsAll.map((l) => minutes(chain(l, 1)?.complete ? chain(l, 1).total_s : null)), color: C.slate },
    { name: '2 worker', data: levelsAll.map((l) => minutes(chain(l, 2)?.complete ? chain(l, 2).total_s : null)), color: C.herb },
  ], { yMin: 0, yFmt: (v) => `${fmtNum(v, 1)} ph` });
  hGroupedBars($('perf-speedup'), sp.map((s) => (s.level === 'catalog' ? `${s.step} (danh mục)` : s.step)), [
    { name: '100% / danh mục', data: sp.map((s) => s.speedup), color: C.herb },
    { name: '10%', data: sp.map((s) => (s.level === 's100' ? sp10(s.job) : null)), color: C.herbMid },
  ], { xFmt: (v) => fmtFixed(v, 2), markX: [2] });
  // ten series ngan (ma job) de chu giai nam tren 1 dong o 375px; ten day du nam trong dong chu thich
  lines($('perf-by-scale'), levelsAll.map((l) => LEVEL[l]), [
    { name: 'Chuỗi 04 → 06f', data: bsChain, color: C.herb, width: 3 },
    ...['04', '05', '06b'].map((k, i) => ({ name: k, data: levelsAll.map((l) => bsAt(k, l)),
                                             color: [C.chili, C.slate, C.herbMid][i] })),
  ], { yMin: 0, yFmt: (v) => fmtFixed(v, 2), markY: [2] });
}, 280);
