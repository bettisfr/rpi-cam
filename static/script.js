const socket = io();  // Connect to the WebSocket server
const gallery = document.querySelector('#gallery');  // Select gallery container

// Fetch and display all images from the server
function loadGalleryImages() {
    fetch('/get-images')
        .then(response => response.json())
        .then(images => {
            console.log("Fetched images:", images); // Debugging

            gallery.innerHTML = ""; // Clear gallery before adding new images

            images.forEach(imageData => {
                addImageToGallery(imageData, false); // Add image without real-time effect
            });
        })
        .catch(error => console.error('Error fetching images:', error));
}

// Add an image to the gallery with optional real-time effect
function addImageToGallery(imageData, isRealTime = true) {
    console.log("Adding image:", imageData.filename); // Debugging

    const div = document.createElement('div');
    div.classList.add('col');

    // Image element with lazy loading
    const img = document.createElement('img');
    img.classList.add('image-gallery-img');
    img.dataset.src = `/static/uploads/${imageData.filename}`; // Lazy load source
    img.alt = imageData.filename;
    img.style.visibility = 'hidden'; // Hide until loaded

    // Metadata section
    const metadataDiv = document.createElement('div');
    metadataDiv.classList.add('image-metadata');
    metadataDiv.innerHTML = `
        <strong>${imageData.filename}</strong><br>
        Temperature: ${imageData.metadata?.temperature ?? 'N/A'} °C<br>
        Pressure: ${imageData.metadata?.pressure ?? 'N/A'} hPa<br>
        Humidity: ${imageData.metadata?.humidity ?? 'N/A'} %<br>
        GPS: (${imageData.metadata?.latitude ?? 'N/A'}, ${imageData.metadata?.longitude ?? 'N/A'})<br>
        ${isRealTime ? '<em>Uploaded just now</em>' : ''}
    `;

    div.appendChild(img);
    div.appendChild(metadataDiv);

    if (isRealTime) {
        gallery.prepend(div);  // Add new images to the top
    } else {
        gallery.appendChild(div); // Add fetched images to the end
    }

    lazyLoadImage(img);
}

// Lazy loading for images (loads only when they are near the viewport)
function lazyLoadImage(img) {
    const observer = new IntersectionObserver((entries, observer) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.src = entry.target.dataset.src;  // Load image
                entry.target.onload = () => entry.target.style.visibility = 'visible'; // Show after loading
                observer.unobserve(entry.target); // Stop observing after loading
            }
        });
    }, { rootMargin: '100px' }); // Load images slightly before they appear on screen

    observer.observe(img);
}

// Listen for real-time image uploads via WebSockets
socket.on('new_image', (data) => {
    addImageToGallery(data, true); // Add new image to gallery
});

// Load all images when the page loads
loadGalleryImages();
