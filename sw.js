const CACHE_NAME = 'aura-os-v2';
const ASSETS_TO_CACHE = [
  '/',
  '/manifest.json',
  '/aura_icon.svg'
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(ASSETS_TO_CACHE);
    })
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.map((key) => {
          if (key !== CACHE_NAME) {
            return caches.delete(key);
          }
        })
      );
    })
  );
  self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  event.respondWith(
    fetch(event.request).catch(() => caches.match(event.request))
  );
});

// WebPush Background Notifications
self.addEventListener('push', (event) => {
  const data = event.data ? event.data.json() : { title: 'AURA Executive Alert', body: 'New system event recorded.' };
  const options = {
    body: data.body,
    icon: '/aura_icon.svg',
    badge: '/aura_icon.svg',
    vibrate: [200, 100, 200],
    data: {
      url: data.url || '/'
    }
  };
  event.waitUntil(
    self.registration.showNotification(data.title, options)
  );
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  event.waitUntil(
    clients.openWindow(event.notification.data.url)
  );
});
