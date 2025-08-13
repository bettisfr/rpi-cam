// script.js

const gallery = document.querySelector('#gallery');  // Container for the cards

// Fetch and display all images from the server
async function loadGalleryImages() {
    try {
        const resp = await fetch('/get-images');
        const images = await resp.json();

        gallery.innerHTML = ''; // Clear gallery before adding new images
        images.forEach(imageData => {
            addImageToGallery(imageData, /*isRealtime=*/false);
        });
    } catch (err) {
        console.error('Error fetching images:', err);
    }
}

// Add an image card to the gallery
function addImageToGallery(imageData, isRealtime = false) {
    // imageData comes from /get-images or /receive response
    // Expected fields: { filename, url, upload_time, metadata: { captured_at } }

    const div = document.createElement('div');
    div.classList.add('col');

    // Image element with lazy loading
    const img = document.createElement('img');
    img.classList.add('image-gallery-img');
    // Use the URL provided by the server (already includes dated subfolder)
    img.dataset.src = imageData.url;
    img.alt = imageData.filename;
    img.style.visibility = 'hidden'; // Hide until loaded

    // Metadata block
    const meta = imageData.metadata || {};
    const capturedAt = meta.captured_at || '';
    const uploadedAt = imageData.upload_time || '';

    const metadataDiv = document.createElement('div');
    metadataDiv.classList.add('image-metadata');
    metadataDiv.innerHTML = `
        <strong>${escapeHtml(imageData.filename)}</strong><br>
        ${capturedAt ? `Captured: ${escapeHtml(capturedAt)}<br>` : ''}
        ${uploadedAt ? `Uploaded: ${escapeHtml(uploadedAt)}<br>` : ''}
        ${isRealtime ? '<em>Uploaded just now</em>' : ''}
    `;

    div.appendChild(img);
    div.appendChild(metadataDiv);

    if (isRealtime) {
        gallery.prepend(div);   // Newest first if real-time (kept for future use)
    } else {
        gallery.appendChild(div);
    }

    lazyLoadImage(img);
}

// Simple HTML escape for safety
function escapeHtml(str) {
    return String(str)
      .replaceAll('&', '&amp;')
      .replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;')
      .replaceAll("'", '&#39;');
}

// Lazy loading via IntersectionObserver
function lazyLoadImage(img) {
    const observer = new IntersectionObserver((entries, obs) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.src = entry.target.dataset.src;
                entry.target.onload = () => { entry.target.style.visibility = 'visible'; };
                obs.unobserve(entry.target);
            }
        });
    }, { rootMargin: '100px' });

    observer.observe(img);
}

// Initial load (and optional periodic refresh if you like)
// Call loadGalleryImages() again on a timer if you want auto-refresh without websockets.
// setInterval(loadGalleryImages, 30000);
loadGalleryImages();
