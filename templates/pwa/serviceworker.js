const CACHE_NAME = 'noxaintel-cache-v1';
const OFFLINE_URL = '/pwa/offline/';

const ASSETS_TO_CACHE = [
    OFFLINE_URL,
    '/pwa/manifest.json',
    'https://cdn.tailwindcss.com',
    'https://cdn.jsdelivr.net/npm/daisyui@4.12.10/dist/full.min.css',
    'https://unpkg.com/htmx.org@1.9.10',
    'https://img.icons8.com/fluency/192/000000/soccer-ball.png'
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
        caches.keys().then((cacheNames) => {
            return Promise.all(
                cacheNames.map((cacheName) => {
                    if (cacheName !== CACHE_NAME) {
                        return caches.delete(cacheName);
                    }
                })
            );
        })
    );
    self.clients.claim();
});

self.addEventListener('fetch', (event) => {
    // Skip cross-origin requests or non-GET requests
    if (event.request.method !== 'GET') return;

    event.respondWith(
        fetch(event.request)
            .then((response) => {
                // Cache successful responses for our app's pages
                if (response.status === 200 && event.request.url.startsWith(self.location.origin)) {
                    const responseClone = response.clone();
                    caches.open(CACHE_NAME).then((cache) => {
                        cache.put(event.request, responseClone);
                    });
                }
                return response;
            })
            .catch(() => {
                // If offline, check cache
                return caches.match(event.request).then((cachedResponse) => {
                    if (cachedResponse) {
                        return cachedResponse;
                    }
                    // For HTML page requests, fall back to offline page
                    if (event.request.mode === 'navigate') {
                        return caches.match(OFFLINE_URL);
                    }
                    return null;
                });
            })
    );
});

/* ── Web Push Event Listeners ── */
self.addEventListener('push', function(event) {
    if (event.data) {
        try {
            const data = event.data.json();
            const title = data.title || 'NoxaIntel Alert';
            const options = {
                body: data.body || '',
                icon: data.icon || 'https://img.icons8.com/fluency/192/000000/soccer-ball.png',
                badge: 'https://img.icons8.com/fluency/72/000000/soccer-ball.png',
                vibrate: [100, 50, 100],
                data: {
                    url: data.url || '/'
                }
            };
            event.waitUntil(
                self.registration.showNotification(title, options)
            );
        } catch (e) {
            const text = event.data.text();
            event.waitUntil(
                self.registration.showNotification('NoxaIntel Alert', {
                    body: text,
                    icon: 'https://img.icons8.com/fluency/192/000000/soccer-ball.png',
                    data: {
                        url: '/'
                    }
                })
            );
        }
    }
});

self.addEventListener('notificationclick', function(event) {
    event.notification.close();
    event.waitUntil(
        clients.matchAll({ type: 'window', includeUncontrolled: true }).then(function(clientList) {
            const targetUrl = event.notification.data ? event.notification.data.url : '/';
            // If absolute URL, compare relative or just find match
            const fullTargetUrl = new URL(targetUrl, self.location.origin).href;
            for (let i = 0; i < clientList.length; i++) {
                let client = clientList[i];
                if (client.url === fullTargetUrl && 'focus' in client) {
                    return client.focus();
                }
            }
            if (clients.openWindow) {
                return clients.openWindow(targetUrl);
            }
        })
    );
});

