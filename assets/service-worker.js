const CACHE_NAME = "weather-station-cache-v1";
const urlsToCache = [
  "/",
  "/assets/manifest.json",
  // Add additional assets if needed (CSS, JS, icons, etc.)
];

self.addEventListener("install", event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => cache.addAll(urlsToCache))
  );
});

self.addEventListener("fetch", event => {
  event.respondWith(
    caches.match(event.request)
      .then(response => response || fetch(event.request))
  );
});
