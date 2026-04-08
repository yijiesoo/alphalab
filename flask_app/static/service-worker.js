/**
 * Service Worker for alphalab
 * Handles background sync, offline support, and periodic cache updates
 */

const CACHE_NAME = 'alphalab-v1';
const ASSETS_TO_CACHE = [
    '/',
    '/static/style.css',
    '/static/chart.min.js',
    '/templates/index.html'
];

// Install event - cache assets
self.addEventListener('install', (event) => {
    console.log('[Service Worker] Installing...');
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => {
            console.log('[Service Worker] Caching app assets');
            return cache.addAll(ASSETS_TO_CACHE).catch(err => {
                console.warn('[Service Worker] Cache addAll error:', err);
                // Don't fail installation if some assets can't be cached
            });
        })
    );
    self.skipWaiting();
});

// Activate event - clean up old caches
self.addEventListener('activate', (event) => {
    console.log('[Service Worker] Activating...');
    event.waitUntil(
        caches.keys().then((cacheNames) => {
            return Promise.all(
                cacheNames.map((cacheName) => {
                    if (cacheName !== CACHE_NAME) {
                        console.log('[Service Worker] Deleting old cache:', cacheName);
                        return caches.delete(cacheName);
                    }
                })
            );
        })
    );
    self.clients.claim();
});

// Fetch event - network first, fallback to cache
self.addEventListener('fetch', (event) => {
    // Skip non-GET requests
    if (event.request.method !== 'GET') {
        return;
    }

    // Skip API calls with ?refresh=true (user wants fresh data)
    if (event.request.url.includes('?refresh=true')) {
        return;
    }

    event.respondWith(
        fetch(event.request)
            .then((response) => {
                // Cache successful API responses
                if (response.ok && event.request.url.includes('/api/')) {
                    const responseClone = response.clone();
                    caches.open(CACHE_NAME).then((cache) => {
                        cache.put(event.request, responseClone);
                    });
                }
                return response;
            })
            .catch(() => {
                // Fallback to cache when offline
                return caches.match(event.request).then((cached) => {
                    return cached || new Response('Offline - data unavailable', {
                        status: 503,
                        statusText: 'Service Unavailable'
                    });
                });
            })
    );
});

// Background sync - refresh watchlist periodically
self.addEventListener('sync', (event) => {
    if (event.tag === 'refresh-watchlist') {
        console.log('[Service Worker] Background sync: refreshing watchlist');
        event.waitUntil(refreshWatchlist());
    }
});

// Periodic background sync - refresh data every 10 minutes
self.addEventListener('periodicsync', (event) => {
    if (event.tag === 'refresh-analysis') {
        console.log('[Service Worker] Periodic sync: refreshing analysis data');
        event.waitUntil(refreshAnalysisData());
    }
});

async function refreshWatchlist() {
    try {
        // Fetch user's watchlist
        const response = await fetch('/api/watchlist');
        if (response.ok) {
            const data = await response.json();
            const tickers = data.tickers || [];
            
            // Refresh data for each watched stock
            for (const ticker of tickers.slice(0, 5)) { // Limit to 5 to avoid overload
                try {
                    await fetch(`/api/analyze?ticker=${ticker}`);
                    console.log(`[Service Worker] Refreshed ${ticker}`);
                } catch (err) {
                    console.warn(`[Service Worker] Failed to refresh ${ticker}:`, err);
                }
            }
            
            // Notify all clients that data was updated
            const clients = await self.clients.matchAll();
            clients.forEach(client => {
                client.postMessage({
                    type: 'WATCHLIST_REFRESHED',
                    timestamp: new Date().toISOString()
                });
            });
        }
    } catch (err) {
        console.warn('[Service Worker] Watchlist refresh failed:', err);
    }
}

async function refreshAnalysisData() {
    try {
        // Get currently viewed ticker from storage
        const cache = await caches.open(CACHE_NAME);
        const keys = await cache.keys();
        
        // Find API responses and refresh them
        const apiKeys = keys.filter(req => req.url.includes('/api/analyze'));
        
        for (const request of apiKeys.slice(0, 3)) { // Limit to 3 to avoid overload
            try {
                const response = await fetch(request);
                if (response.ok) {
                    await cache.put(request, response);
                    console.log(`[Service Worker] Updated cache for ${request.url}`);
                }
            } catch (err) {
                console.warn(`[Service Worker] Failed to refresh ${request.url}:`, err);
            }
        }
        
        // Notify all clients
        const clients = await self.clients.matchAll();
        clients.forEach(client => {
            client.postMessage({
                type: 'ANALYSIS_REFRESHED',
                timestamp: new Date().toISOString()
            });
        });
    } catch (err) {
        console.warn('[Service Worker] Analysis refresh failed:', err);
    }
}
