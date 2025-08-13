// script.js

const daysView = document.getElementById('days-view');
const daysList = document.getElementById('days-list');

const imagesView = document.getElementById('images-view');
const gallery = document.getElementById('gallery');
const currentDayEl = document.getElementById('current-day');
const backBtn = document.getElementById('back-to-days');

const imageModal = new bootstrap.Modal(document.getElementById('imageModal'));
const modalTitle = document.getElementById('modalTitle');
const modalImage = document.getElementById('modalImage');
const downloadLink = document.getElementById('downloadLink');

// ------- Days -------
async function loadDays() {
  daysList.innerHTML = '<div class="list-group-item">Loading…</div>';
  try {
    const r = await fetch('/get-days');
    const days = await r.json(); // [{day, count, latest_upload_time}]
    if (!Array.isArray(days) || days.length === 0) {
      daysList.innerHTML = '<div class="list-group-item">No images yet.</div>';
      return;
    }
    daysList.innerHTML = '';
    for (const d of days) {
      const a = document.createElement('a');
      a.href = '#';
      a.className = 'list-group-item list-group-item-action d-flex justify-content-between align-items-center';
      a.innerHTML = `
        <div>
          <div class="fw-semibold">${escapeHtml(d.day)}</div>
          <small class="text-muted">Latest: ${escapeHtml(d.latest_upload_time)}</small>
        </div>
        <span class="badge bg-primary rounded-pill">${d.count}</span>
      `;
      a.addEventListener('click', (e) => {
        e.preventDefault();
        openDay(d.day);
      });
      daysList.appendChild(a);
    }
  } catch (e) {
    daysList.innerHTML = `<div class="list-group-item text-danger">Error loading days: ${escapeHtml(String(e))}</div>`;
  }
}

function showDaysView() {
  imagesView.classList.add('d-none');
  daysView.classList.remove('d-none');
}

function showImagesView() {
  daysView.classList.add('d-none');
  imagesView.classList.remove('d-none');
}

// ------- Images for a day -------
async function openDay(yyyymmdd) {
  currentDayEl.textContent = `Day ${yyyymmdd}`;
  gallery.innerHTML = renderSkeletonCards(8); // small skeleton while loading
  showImagesView();

  try {
    const r = await fetch(`/get-images-by-day?day=${encodeURIComponent(yyyymmdd)}`);
    const images = await r.json(); // [{ filename, url, upload_time, metadata }]
    gallery.innerHTML = '';

    if (!Array.isArray(images) || images.length === 0) {
      gallery.innerHTML = '<div class="text-muted">No images found for this day.</div>';
      return;
    }

    for (const imgData of images) {
      addImageCard(imgData);
    }
  } catch (e) {
    gallery.innerHTML = `<div class="text-danger">Error loading images: ${escapeHtml(String(e))}</div>`;
  }
}

function addImageCard(imageData) {
  const card = document.createElement('article');
  card.className = 'gallery-card shadow-sm';

  // Thumb (fixed aspect ratio via CSS)
  const img = document.createElement('img');
  img.className = 'gallery-thumb';
  img.alt = imageData.filename;
  img.loading = 'lazy';
  img.dataset.src = imageData.url;   // lazy load later
  img.style.visibility = 'hidden';

  img.addEventListener('click', () => openModal(imageData));

  const body = document.createElement('div');
  body.className = 'gallery-meta';
  body.innerHTML = `
    <div class="meta-name" title="${escapeHtml(imageData.filename)}">
      ${escapeHtml(imageData.filename)}
    </div>
    <div class="meta-times">
      ${imageData.metadata?.captured_at ? `<span>Captured: ${escapeHtml(imageData.metadata.captured_at)}</span>` : ''}
      ${imageData.upload_time ? `<span>Uploaded: ${escapeHtml(imageData.upload_time)}</span>` : ''}
    </div>
    <div class="meta-actions">
      <a href="${imageData.url}" download class="btn btn-sm btn-outline-primary">Download</a>
    </div>
  `;

  card.appendChild(img);
  card.appendChild(body);
  gallery.appendChild(card);

  lazyLoadImage(img);
}

// Skeleton placeholders while loading
function renderSkeletonCards(n) {
  return Array.from({ length: n }).map(() => `
    <article class="gallery-card skeleton">
      <div class="gallery-thumb"></div>
      <div class="gallery-meta">
        <div class="skeleton-line w-80"></div>
        <div class="skeleton-line w-60"></div>
      </div>
    </article>
  `).join('');
}

// ------- Modal -------
function openModal(imageData) {
  modalTitle.textContent = imageData.filename;
  modalImage.src = imageData.url;
  downloadLink.href = imageData.url;
  downloadLink.setAttribute('download', imageData.filename);
  imageModal.show();
}

// ------- Utilities -------
function escapeHtml(str) {
  return String(str)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

function lazyLoadImage(img) {
  const obs = new IntersectionObserver((entries, observer) => {
    for (const e of entries) {
      if (e.isIntersecting) {
        e.target.src = e.target.dataset.src;
        e.target.onload = () => { e.target.style.visibility = 'visible'; };
        observer.unobserve(e.target);
      }
    }
  }, { rootMargin: '150px' });
  obs.observe(img);
}

// ------- Navigation -------
backBtn.addEventListener('click', (e) => {
  e.preventDefault();
  showDaysView();
});

// Init
loadDays();
showDaysView();
