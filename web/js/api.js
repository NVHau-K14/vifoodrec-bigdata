// api.js - goi API cung origin, xu ly loi, dinh dang so theo vi-VN (skill muc 7)

export class ApiError extends Error {
  constructor(message, status) { super(message); this.status = status; }
}

async function request(path, opts = {}) {
  let res;
  try {
    res = await fetch(`/api${path}`, opts);
  } catch (e) {
    if (e.name === 'AbortError') throw e;
    throw new ApiError('Không kết nối được API. Kiểm tra service api đang chạy.', 0);
  }
  let body = null;
  try { body = await res.json(); } catch { /* body khong phai JSON */ }
  if (!res.ok) {
    const d = body && body.detail;
    const msg = typeof d === 'string' ? d : `API trả lỗi ${res.status}`;
    throw new ApiError(msg, res.status);
  }
  return body;
}

export function getJSON(path, { signal } = {}) {
  return request(path, { signal });
}

// Nhieu the dung chung 1 request: goi 1 lan, nhung loi thi quen di de nut "Thu lai" goi lai API
export function shared(path) {
  let p = null;
  return () => (p ??= getJSON(path).catch((e) => { p = null; throw e; }));
}

export function postJSON(path, data, { signal } = {}) {
  return request(path, { method: 'POST', headers: { 'Content-Type': 'application/json' },
                         body: JSON.stringify(data), signal });
}

// Chuoi query tu object, bo gia tri rong / false
export function qs(params) {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v === null || v === undefined || v === '' || v === false) continue;
    p.set(k, v);
  }
  const s = p.toString();
  return s ? `?${s}` : '';
}

const nf = (opts) => new Intl.NumberFormat('vi-VN', opts);
export const fmtInt = (n) => (n == null ? '–' : nf({ maximumFractionDigits: 0 }).format(n));
export const fmtNum = (n, d = 3) => (n == null ? '–' : nf({ maximumFractionDigits: d }).format(n));
export const fmtFixed = (n, d = 4) => (n == null ? '–' : nf({ minimumFractionDigits: d, maximumFractionDigits: d }).format(n));
export const fmtPct = (n, d = 1) => (n == null ? '–' : `${nf({ maximumFractionDigits: d }).format(n)}%`);
// Ty le 0..1 -> %
export const fmtRatio = (r, d = 1) => (r == null ? '–' : fmtPct(r * 100, d));

// So lon o KPI: 23.205.143 -> "23,2 tr"; 5.499 giu nguyen
export function fmtShort(n) {
  if (n == null) return '–';
  if (Math.abs(n) >= 1e9) return `${fmtNum(n / 1e9, 1)} tỷ`;
  if (Math.abs(n) >= 1e6) return `${fmtNum(n / 1e6, 1)} tr`;
  return fmtInt(n);
}

export function fmtBytes(b) {
  if (b == null) return '–';
  if (b >= 1e9) return `${fmtNum(b / 1e9, 2)} GB`;
  if (b >= 1e6) return `${fmtNum(b / 1e6, 1)} MB`;
  return `${fmtNum(b / 1e3, 0)} KB`;
}

export function fmtSeconds(s) {
  if (s == null) return '';
  if (s >= 60) return `${fmtNum(s / 60, 1)} phút`;
  return `${fmtNum(s, 1)} giây`;
}

// "2026-09-01" -> "01/09/2026"
export function fmtDate(iso) {
  if (!iso) return '–';
  const [y, m, d] = iso.slice(0, 10).split('-');
  return `${d}/${m}/${y}`;
}
