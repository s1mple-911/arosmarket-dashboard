// AROS Market Service Worker
// HTML uchun NETWORK-FIRST: online bo'lsa har doim eng yangi versiya.
// Version faqat eski cache'larni tozalash uchun (HTML freshness'ga bog'liq emas).
const CACHE_VERSION = 'aros-v12';
const STATIC_CACHE = CACHE_VERSION + '-static';

// Offline fallback uchun minimal ro'yxat (ixtiyoriy)
const STATIC_ASSETS = [
  './manifest.json'
];

// Install — yangi SW'ni darhol faollashtirish
self.addEventListener('install', function(event) {
  event.waitUntil(
    caches.open(STATIC_CACHE).then(function(cache) {
      return cache.addAll(STATIC_ASSETS).catch(function(err){
        console.log('[SW] Cache addAll skip:', err);
      });
    })
  );
  self.skipWaiting();
});

// Activate — eski versiya cache'larini o'chirish + darhol nazoratga olish
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
    }).then(function() {
      return self.clients.claim();
    })
  );
});

// Sahifa SW'dan "darhol yangilanish"ni so'rashi uchun
self.addEventListener('message', function(event) {
  if (event.data === 'SKIP_WAITING') self.skipWaiting();
});

self.addEventListener('fetch', function(event) {
  var url = event.request.url;

  // n8n / aros / telegram API — har doim network (cache yo'q)
  if (url.indexOf('n8n.arosmarket.com') !== -1 ||
      url.indexOf('api.aros.uz') !== -1 ||
      url.indexOf('api.telegram.org') !== -1) {
    return; // brauzer default (network)
  }

  // Faqat GET
  if (event.request.method !== 'GET') return;

  // HTML/navigatsiya so'rovlarini aniqlash
  var accept = event.request.headers.get('accept') || '';
  var isHTML = event.request.mode === 'navigate'
            || accept.indexOf('text/html') !== -1
            || url.indexOf('.html') !== -1;

  if (isHTML) {
    // NETWORK-FIRST: avval tarmoqdan (yangi), faqat offline'da keshdan
    event.respondWith(
      fetch(event.request).then(function(response) {
        if (response && response.ok) {
          var clone = response.clone();
          caches.open(STATIC_CACHE).then(function(cache) { cache.put(event.request, clone); });
        }
        return response;
      }).catch(function() {
        return caches.match(event.request).then(function(cached) {
          return cached || new Response('Offline', { status: 503 });
        });
      })
    );
    return;
  }

  // Boshqa statik GET (rasm, manifest, font...): cache-first + background revalidate
  event.respondWith(
    caches.match(event.request).then(function(cached) {
      var net = fetch(event.request).then(function(response) {
        if (response && response.ok) {
          var c = response.clone();
          caches.open(STATIC_CACHE).then(function(cache) { cache.put(event.request, c); });
        }
        return response;
      }).catch(function() { return cached; });
      return cached || net;
    })
  );
});
