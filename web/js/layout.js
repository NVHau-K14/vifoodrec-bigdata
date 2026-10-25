// layout.js - dung thanh ben (7 muc, dung thu tu skill muc 3) va vien thong tin o dau trang

import { getJSON, fmtDate } from './api.js';
import { wireImgFallback } from './components.js';

export const PAGES = [
  { href: 'index.html', label: 'Tổng quan' },
  { href: 'hanh-vi.html', label: 'Hành vi ăn uống' },
  { href: 'mon-an.html', label: 'Món ăn' },
  { href: 'phan-khuc.html', label: 'Phân khúc người dùng' },
  { href: 'goi-y.html', label: 'Gợi ý món' },
  { href: 'danh-gia.html', label: 'Đánh giá mô hình' },
  { href: 'thoi-gian-thuc.html', label: 'Thời gian thực' },
];

// Bieu tuong bat canh (trang tri)
const LOGO = `<svg width="34" height="34" viewBox="0 0 34 34" fill="none" aria-hidden="true">
  <path d="M5 16h24a12 12 0 0 1-24 0Z" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/>
  <path d="M11 30h12" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
  <path d="M13 11c-1.5-2 1.5-3 0-5M18 11c-1.5-2 1.5-3 0-5M23 11c-1.5-2 1.5-3 0-5" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>
</svg>`;

function currentPage() {
  const f = location.pathname.split('/').pop();
  return f === '' ? 'index.html' : f;
}

export function buildNav() {
  const nav = document.getElementById('nav');
  if (!nav) return;
  const cur = currentPage();
  nav.className = 'nav';
  nav.setAttribute('aria-label', 'Các trang của dashboard');
  nav.innerHTML = `
    <a class="brand" href="index.html"><span class="brand-logo">${LOGO}</span>
      <span><span class="brand-name">ViFoodRec</span><br><span class="brand-sub">Hành vi ăn uống &amp; gợi ý món</span></span></a>
    <ul class="nav-list">
      ${PAGES.map((p) => `<li><a href="${p.href}"${p.href === cur ? ' aria-current="page"' : ''}>
        <span class="dot" aria-hidden="true"></span>${p.label}</a></li>`).join('')}
    </ul>
    <div class="nav-note"><strong>Dữ liệu hành vi mô phỏng</strong>
      Món ăn là món thật (Cooky, Món Ngon Mỗi Ngày). Người dùng, lượt xem, lượt nấu và đánh giá được sinh bằng mô phỏng.</div>`;
}

// Vien o dau trang: moc du lieu (tu overview) + "Hanh vi mo phong"
export async function buildHeadPills() {
  const box = document.getElementById('head-pills');
  if (!box) return;
  box.innerHTML = '<span class="pill" id="pill-date">Mốc dữ liệu: …</span><span class="pill pill-chili">Hành vi mô phỏng</span>';
  try {
    const ov = await getJSON('/overview');
    document.getElementById('pill-date').textContent = `Mốc dữ liệu: ${fmtDate(ov.reference_date)}`;
  } catch {
    document.getElementById('pill-date').textContent = 'Mốc dữ liệu: chưa tải được';
  }
}

buildNav();
buildHeadPills();
// Anh mon tren moi trang: hien khi tai xong, loi hoac qua 4 giay thi ve anh thay the theo nhom mon
wireImgFallback(document.body);
