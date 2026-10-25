// charts.js - theme ECharts "vifood" (skill muc 6) va ham ve dung chung.
// Day la 1 trong 2 file duy nhat duoc chua ma mau hex (cung theme.css).
/* global echarts */

export const C = {
  herb: '#1E6B4A', herbDark: '#134A33', herbMid: '#9CC7B0', herbSoft: '#E3F0E8',
  chili: '#C2481B', slate: '#3F4B45', neutral: '#8A958F', line2: '#CDD3CB', track: '#EEF1EC',
  surface: '#FFFFFF', ink: '#17201B', muted: '#5B6660', zero: '#F6F7F4',
  heat: ['#EEF4F0', '#6FAE8D', '#0F4A32'],
  // Thang 2 dau (lift, do lech z): thap = chili, giua = nen, cao = herb
  diverge: ['#C2481B', '#F2C9B7', '#F6F7F4', '#9CC7B0', '#134A33'],
  chiliSoft: '#FBE9E1',
};
// Nhieu series (vd 10 nhom mon): 4 mau dau phan biet ro, cac series sau dung thang herb / neutral
export const SERIES = ['#1E6B4A', '#C2481B', '#3F4B45', '#9CC7B0', '#8A958F', '#134A33', '#6FAE8D', '#B5BDB8', '#5B6660', '#CDD3CB'];

echarts.registerTheme('vifood', {
  color: ['#1E6B4A', '#C2481B', '#3F4B45', '#9CC7B0', '#8A958F', '#134A33'],
  backgroundColor: 'transparent',
  textStyle: { fontFamily: "'Be Vietnam Pro', system-ui, sans-serif", color: '#2B3530' },
  title: { show: false },
  grid: { left: 8, right: 8, top: 24, bottom: 8, containLabel: true },
  categoryAxis: { axisLine: { lineStyle: { color: '#CDD3CB' } }, axisTick: { show: false },
                  axisLabel: { color: '#5B6660', fontSize: 11 }, splitLine: { show: false } },
  valueAxis: { axisLine: { show: false }, axisLabel: { color: '#5B6660', fontSize: 11 },
               splitLine: { lineStyle: { color: '#EEF1EC' } } },
  tooltip: { backgroundColor: '#17201B', borderWidth: 0, textStyle: { color: '#FFFFFF', fontSize: 12 } },
  legend: { textStyle: { color: '#44504A', fontSize: 12 }, icon: 'roundRect', itemWidth: 10, itemHeight: 10 },
  bar: { itemStyle: { borderRadius: [6, 6, 0, 0] } },
  line: { symbol: 'none', lineStyle: { width: 2 } },
});

const nfmt = (v, d = 0) => new Intl.NumberFormat('vi-VN', { maximumFractionDigits: d }).format(v);

// Moi bieu do: theme vifood, renderer svg, tu resize theo khung
export function initChart(el) {
  const prev = echarts.getInstanceByDom(el);
  if (prev) return prev;
  const ch = echarts.init(el, 'vifood', { renderer: 'svg' });
  new ResizeObserver(() => ch.resize()).observe(el);
  return ch;
}

// Heatmap gio x thu: cells [{dow_idx 1..7, dow_vn, hour, value}]
export function heatmapHourDow(el, cells, valueName) {
  const days = [...new Map(cells.map((c) => [c.dow_idx, c.dow_vn])).entries()].sort((a, b) => a[0] - b[0]);
  const hours = Array.from({ length: 24 }, (_, h) => h);
  const max = Math.max(...cells.map((c) => c.value));
  const data = cells.map((c) => [c.hour, c.dow_idx - days[0][0], c.value]);
  const ch = initChart(el);
  ch.setOption({
    grid: { left: 8, right: 8, top: 8, bottom: 44, containLabel: true },
    tooltip: { formatter: (p) => `${days[p.value[1]][1]}, ${p.value[0]}h: ${nfmt(p.value[2])} ${valueName}` },
    xAxis: { type: 'category', data: hours, splitArea: { show: false },
             axisLabel: { interval: 2, formatter: (h) => `${h}h` } },
    yAxis: { type: 'category', data: days.map((d) => d[1]), inverse: true },
    visualMap: { type: 'continuous', min: 0, max, orient: 'horizontal', left: 'center', bottom: 0,
                 itemHeight: 160, itemWidth: 10, calculable: false, text: [nfmt(max), '0'],
                 textStyle: { color: C.muted, fontSize: 11 }, inRange: { color: C.heat },
                 outOfRange: { color: C.zero } },
    series: [{ type: 'heatmap', data: data.map((d) => ({ value: d, itemStyle: d[2] === 0 ? { color: C.zero } : undefined })),
               itemStyle: { borderRadius: 4, borderColor: C.surface, borderWidth: 3 },
               emphasis: { itemStyle: { borderColor: C.ink, borderWidth: 1 } } }],
  });
  return ch;
}

// Cot theo thang (truc tu 0): train herbMid, thang Tet chili, val/test slate.
// Chu giai 3 mau viet bang HTML (MONTH_LEGEND trong components.js): series rong de lam chu giai
// se chiem cho trong nhom cot, lam cot manh va lech trai.
export function monthlyBars(el, months, tetMonth) {
  const color = (m) => (m.month === tetMonth ? C.chili : m.split === 'train' ? C.herbMid : C.slate);
  const label = (s) => { const [y, m] = s.split('-'); return `${m}/${y.slice(2)}`; };
  const ch = initChart(el);
  ch.setOption({
    grid: { left: 8, right: 8, top: 16, bottom: 8, containLabel: true },
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' },
               formatter: (ps) => { const m = months[ps[0].dataIndex];
                 const tag = m.split === 'train' ? 'train' : m.split;
                 return `${label(m.month)} (${tag}): ${nfmt(m.cooks)} lượt nấu`; } },
    xAxis: { type: 'category', data: months.map((m) => label(m.month)) },
    yAxis: { type: 'value', min: 0, axisLabel: { formatter: (v) => (v >= 1000 ? `${nfmt(v / 1000)}k` : v) } },
    series: [
      { name: 'Lượt nấu', type: 'bar', barWidth: '58%', barMaxWidth: 40,
        data: months.map((m) => ({ value: m.cooks, itemStyle: { color: color(m) } })) },
    ],
  });
  return ch;
}

// Duong don gian: xs, [{name, data, color}]
export function lines(el, xs, series, { yName = '', yFmt = (v) => nfmt(v, 3), xName = '', yMin, yMax, markX } = {}) {
  const ch = initChart(el);
  ch.setOption({
    grid: { left: 8, right: 16, top: 30, bottom: xName ? 24 : 8, containLabel: true },
    legend: series.length > 1 ? { top: 0, left: 0 } : undefined,
    tooltip: { trigger: 'axis', valueFormatter: yFmt },
    xAxis: { type: 'category', data: xs, name: xName, nameLocation: 'middle', nameGap: 26,
             nameTextStyle: { color: C.muted, fontSize: 11 } },
    yAxis: { type: 'value', name: yName, nameTextStyle: { color: C.muted, fontSize: 11 }, scale: yMin == null,
             min: yMin, max: yMax, axisLabel: { formatter: yFmt } },
    // markX: cac gia tri tren truc x can danh dau bang duong doc (vd k = 3, 8, 11)
    series: series.map((s, i) => ({ name: s.name, type: 'line', data: s.data, symbol: 'circle', symbolSize: 7,
                                  itemStyle: { color: s.color || C.herb }, lineStyle: { color: s.color || C.herb },
                                  markLine: i === 0 && markX ? { symbol: 'none', silent: true, label: { color: C.muted, fontSize: 11, formatter: (p) => p.value },
                                    lineStyle: { color: C.line2, type: 'dashed' }, data: markX.map((x) => ({ xAxis: x })) } : undefined })),
  }, true);
  return ch;
}

// Cot nhom: cats, [{name, data, color}]
export function groupedBars(el, cats, series, { yFmt = (v) => nfmt(v, 3), yName = '' } = {}) {
  const ch = initChart(el);
  ch.setOption({
    grid: { left: 8, right: 8, top: 36, bottom: 8, containLabel: true },
    legend: { top: 0, left: 0 },
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, valueFormatter: yFmt },
    xAxis: { type: 'category', data: cats },
    yAxis: { type: 'value', min: 0, name: yName, nameTextStyle: { color: C.muted, fontSize: 11 },
             axisLabel: { formatter: yFmt } },
    series: series.map((s) => ({ name: s.name, type: 'bar', barMaxWidth: 30, data: s.data,
                                  itemStyle: { color: s.color }, label: { show: true, position: 'top',
                                  fontSize: 11, color: C.muted, formatter: (p) => yFmt(p.value) } })),
  });
  return ch;
}

// Duong nhieu series co legend bat/tat: series [{name, data, color?}], shown = ten cac series hien mac dinh
export function multiLines(el, xs, series, { shown, yFmt = (v) => nfmt(v, 1), yName = '' } = {}) {
  const ch = initChart(el);
  const selected = shown ? Object.fromEntries(series.map((s) => [s.name, shown.includes(s.name)])) : undefined;
  ch.setOption({
    grid: { left: 8, right: 16, top: 64, bottom: 8, containLabel: true },
    legend: { top: 0, left: 0, type: 'plain', selected },
    tooltip: { trigger: 'axis', valueFormatter: yFmt },
    xAxis: { type: 'category', data: xs, boundaryGap: false },
    yAxis: { type: 'value', min: 0, name: yName, nameTextStyle: { color: C.muted, fontSize: 11 }, axisLabel: { formatter: yFmt } },
    series: series.map((s, i) => ({ name: s.name, type: 'line', data: s.data, symbol: 'circle', symbolSize: 5,
                                    itemStyle: { color: s.color || SERIES[i % SERIES.length] },
                                    lineStyle: { color: s.color || SERIES[i % SERIES.length] } })),
  }, true);
  return ch;
}

// Cot chong 100%: xs (thang), series [{name, data (%), color}]
export function stacked100(el, xs, series, { yFmt = (v) => `${nfmt(v, 1)}%` } = {}) {
  const ch = initChart(el);
  // Chu giai co the xuong 2 dong o the hep: chua cho phia tren theo do rong khung
  const top = el.clientWidth < 520 ? 60 : 36;
  ch.setOption({
    grid: { left: 8, right: 8, top, bottom: 8, containLabel: true },
    legend: { top: 0, left: 0 },
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, valueFormatter: yFmt },
    xAxis: { type: 'category', data: xs },
    yAxis: { type: 'value', min: 0, max: 100, axisLabel: { formatter: (v) => `${v}%` } },
    series: series.map((s) => ({ name: s.name, type: 'bar', stack: 'all', barWidth: '62%', data: s.data,
                                 itemStyle: { color: s.color, borderRadius: 0 } })),
  }, true);
  return ch;
}

// Heatmap 2 dau: xs (cot), ys (hang), data [[xi, yi, giaTriMau, nhan, tooltip]]; center = gia tri giua thang
export function divergingHeatmap(el, xs, ys, data, { min, max, center = 0, label = true, xRotate = 0, fmtLegend = (v) => nfmt(v, 1), legendText } = {}) {
  const ch = initChart(el);
  const lo = min ?? Math.min(...data.map((d) => d[2]).filter((v) => v != null));
  const hi = max ?? Math.max(...data.map((d) => d[2]).filter((v) => v != null));
  const span = Math.max(center - lo, hi - center) || 1;
  ch.setOption({
    grid: { left: 8, right: xRotate ? 48 : 8, top: 8, bottom: 46, containLabel: true },
    tooltip: { formatter: (p) => p.data.tip ?? '' },
    xAxis: { type: 'category', data: xs, splitArea: { show: false }, axisLabel: { interval: 0, rotate: xRotate, fontSize: 11 } },
    yAxis: { type: 'category', data: ys, inverse: true, axisLabel: { fontSize: 11 } },
    visualMap: { type: 'continuous', min: center - span, max: center + span, orient: 'horizontal', left: 'center',
                 bottom: 0, itemHeight: 160, itemWidth: 10, calculable: false, dimension: 2,
                 text: legendText || [fmtLegend(center + span), fmtLegend(center - span)],
                 textStyle: { color: C.muted, fontSize: 11 }, inRange: { color: C.diverge } },
    series: [{ type: 'heatmap',
               data: data.map((d) => ({ value: [d[0], d[1], d[2] ?? '-'], tip: d[4],
                                        itemStyle: d[2] == null ? { color: C.zero } : undefined,
                                        label: { formatter: () => d[3] ?? '' } })),
               label: { show: label, fontSize: 11, color: C.ink },
               itemStyle: { borderRadius: 4, borderColor: C.surface, borderWidth: 3 },
               emphasis: { itemStyle: { borderColor: C.ink, borderWidth: 1 } } }],
  }, true);
  return ch;
}

// Cap thanh ngang nhom: cats (hang), series [{name, data, color}]
export function hGroupedBars(el, cats, series, { xFmt = (v) => `${nfmt(v, 1)}%` } = {}) {
  const ch = initChart(el);
  ch.setOption({
    grid: { left: 8, right: 40, top: 30, bottom: 8, containLabel: true },
    legend: { top: 0, left: 0 },
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, valueFormatter: xFmt },
    xAxis: { type: 'value', min: 0, axisLabel: { formatter: xFmt } },
    yAxis: { type: 'category', data: cats, inverse: true, axisLabel: { fontSize: 11 } },
    series: series.map((s) => ({ name: s.name, type: 'bar', barMaxWidth: 12, barGap: '20%', data: s.data,
                                 itemStyle: { color: s.color, borderRadius: [0, 4, 4, 0] },
                                 label: { show: true, position: 'right', fontSize: 10, color: C.muted, formatter: (p) => xFmt(p.value) } })),
  }, true);
  return ch;
}

// Cot don: cats, values, colors (mot mau hoac mang mau theo cot)
export function simpleBars(el, cats, values, { color = C.herb, yFmt = (v) => nfmt(v), labelFmt, xName = '' } = {}) {
  const ch = initChart(el);
  ch.setOption({
    grid: { left: 8, right: 8, top: 24, bottom: xName ? 24 : 8, containLabel: true },
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, valueFormatter: yFmt },
    xAxis: { type: 'category', data: cats, name: xName, nameLocation: 'middle', nameGap: 26, nameTextStyle: { color: C.muted, fontSize: 11 } },
    yAxis: { type: 'value', min: 0, axisLabel: { formatter: yFmt } },
    series: [{ type: 'bar', barWidth: '58%', barMaxWidth: 40,
               data: values.map((v, i) => ({ value: v, itemStyle: { color: Array.isArray(color) ? color[i] : color } })),
               label: labelFmt ? { show: true, position: 'top', fontSize: 10, color: C.muted, formatter: (p) => labelFmt(p.value) } : undefined }],
  }, true);
  return ch;
}

// Do thi mang nguyen lieu (FP-Growth): nodes [{name, degree}], edges [{src, dst, lift, confidence}]
export function forceGraph(el, nodes, edges) {
  const ch = initChart(el);
  const maxLift = Math.max(...edges.map((e) => e.lift), 1);
  const maxDeg = Math.max(...nodes.map((n) => n.degree), 1);
  ch.setOption({
    tooltip: { formatter: (p) => (p.dataType === 'edge'
      ? `${p.data.source} → ${p.data.target}<br>lift ${nfmt(p.data.lift, 2)}, độ tin cậy ${nfmt(100 * p.data.confidence, 1)}%`
      : `${p.data.name}: ${p.data.degree} liên kết`) },
    series: [{
      type: 'graph', layout: 'force', roam: true, draggable: true,
      force: { repulsion: 140, edgeLength: [40, 110], gravity: 0.08 },
      label: { show: true, fontSize: 11, color: C.ink, position: 'right' },
      lineStyle: { color: C.line2, curveness: 0.1, opacity: 0.9 },
      emphasis: { focus: 'adjacency', lineStyle: { color: C.herb } },
      data: nodes.map((n) => ({ name: n.name, degree: n.degree, symbolSize: 10 + 16 * (n.degree / maxDeg),
                                itemStyle: { color: C.herbSoft, borderColor: C.herb, borderWidth: 1.5 } })),
      links: edges.map((e) => ({ source: e.src, target: e.dst, lift: e.lift, confidence: e.confidence,
                                 lineStyle: { width: 1 + 4 * (e.lift / maxLift) } })),
    }],
  }, true);
  return ch;
}
