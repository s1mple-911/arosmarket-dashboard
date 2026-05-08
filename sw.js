// AROS Market Service Worker
// Versiyani har push'da o'zgartiring (cache reset)
const CACHE_VERSION = 'aros-v3';
const STATIC_CACHE = CACHE_VERSION + '-static';

// Sahifalar (cache qilinadi)
const STATIC_ASSETS = [
  './',
  './login.html',
  './index-dev.html',
  './ceo-dev.html',
  './bugalter.html',
  './hodim-dev.html',
  './manifest.json'
];

// Install — staticfayllarni cache'ga qo'shish
self.addEventListener('install', function(event) {
  event.waitUntil(
    caches.open(STATIC_CACHE).then(function(cache) {
      return cache.addAll(STATIC_ASSETS).catch(function(err){
        console.log('[SW] Cache failed for some assets:', err);
      });
    })
  );
  self.skipWaiting();
});

// Activate — eski cache'larni tozalash
self.addEventListener('activate', function(event) {
  event.waitUntil(
    caches.keys().then(function(cacheNames) {
      return Promise.all(
        cacheNames.filter(function(name) {
          return name.indexOf(CACHE_VERSION) === -1;
        }).map(function(name) {
          return caches.delete(name);
        })
      );
    })
  );
  self.clients.claim();
});

// Fetch strategiya:
// - n8n webhook'lari: faqat tarmoq (cache qilmaymiz, fresh data kerak)
// - HTML/JS/CSS: cache-first, keyin network (offline'da ham ishlaydi)
self.addEventListener('fetch', function(event) {
  var url = event.request.url;
  
  // n8n va aros API — har doim network
  if (url.indexOf('n8n.arosmarket.com') !== -1 || 
      url.indexOf('api.aros.uz') !== -1 ||
      url.indexOf('api.telegram.org') !== -1) {
    return; // Default browser behavior (network)
  }
  
  // Faqat GET requestlarni cache qilamiz
  if (event.request.method !== 'GET') return;
  
  // HTML/JS/CSS: cache-first
  event.respondWith(
    caches.match(event.request).then(function(cached) {
      if (cached) {
        // Background'da freshini olish (stale-while-revalidate)
        fetch(event.request).then(function(response) {
          if (response && response.ok) {
            caches.open(STATIC_CACHE).then(function(cache) {
              cache.put(event.request, response);
            });
          }
        }).catch(function(){});
        return cached;
      }
      // Cache'da yo'q — network
      return fetch(event.request).then(function(response) {
        if (response && response.ok) {
          var clone = response.clone();
          caches.open(STATIC_CACHE).then(function(cache) {
            cache.put(event.request, clone);
          });
        }
        return response;
      }).catch(function() {
        // Offline + cache'da yo'q
        return new Response('Offline', { status: 503 });
      });
    })
  );
});
