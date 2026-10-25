// charts.js - theme ECharts "vifood" (skill muc 6) va ham ve dung chung.
// Day la 1 trong 2 file duy nhat duoc chua ma mau hex (cung theme.css).
/* global echarts */

export const C = {
  herb: '#1E6B4A', herbDark: '#134A33', herbMid: '#9CC7B0', herbSoft: '#E3F0E8',
  chili: '#C2481B', slate: '#3F4B45', neutral: '#8A958F', line2: '#CDD3CB', track: '#EEF1EC',
  surface: '#FFFFFF', ink: '#17201B', muted: '#5B6660', zero: '#F6F7F4',
  heat: ['#EEF4F0', '#6FAE8D', '#0F4A32'],
};

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
export function lines(el, xs, series, { yName = '', yFmt = (v) => nfmt(v, 3), xName = '' } = {}) {
  const ch = initChart(el);
  ch.setOption({
    grid: { left: 8, right: 16, top: 30, bottom: xName ? 24 : 8, containLabel: true },
    legend: series.length > 1 ? { top: 0, left: 0 } : undefined,
    tooltip: { trigger: 'axis', valueFormatter: yFmt },
    xAxis: { type: 'category', data: xs, name: xName, nameLocation: 'middle', nameGap: 26,
             nameTextStyle: { color: C.muted, fontSize: 11 } },
    yAxis: { type: 'value', name: yName, nameTextStyle: { color: C.muted, fontSize: 11 }, scale: true,
             axisLabel: { formatter: yFmt } },
    series: series.map((s) => ({ name: s.name, type: 'line', data: s.data, symbol: 'circle', symbolSize: 7,
                                  itemStyle: { color: s.color || C.herb }, lineStyle: { color: s.color || C.herb } })),
  });
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
