/* THE DSSSB KEY — service worker.

   Everything is precached on install so the site works with no network.
   Every request is NETWORK-FIRST with the cache as fallback: the questions and
   the code that draws them always arrive together and up to date when online
   (a cache-first worker on a sister site once served new data to old code),
   and the cached copies take over when offline. */

var CACHE = 'dsssb-key-v8';
var ASSETS = [
  './', './index.html', './styles.css', './app.js', './manifest.webmanifest',
  './data-static.js', './data-hist.js', './data-pol.js', './data-geo.js', './data-eco.js',
  './data-phy.js', './data-chem.js', './data-bio.js', './data-env.js', './data-mts.js', './data-as.js', './data-prac.js',
  './fonts/literata-400.woff2', './fonts/literata-600.woff2', './fonts/literata-italic-400.woff2',
  './fonts/inter-400.woff2', './fonts/inter-600.woff2', './fonts/plexmono-400.woff2', './fonts/plexmono-500.woff2',
  './icon-192.png', './icon-512.png', './icon-maskable-512.png', './icon-180.png'
];

self.addEventListener('install', function (e) {
  e.waitUntil(
    caches.open(CACHE).then(function (cache) {
      // cache:'reload' skips the browser's HTTP cache so a fresh deploy is what gets stored.
      return Promise.all(ASSETS.map(function (url) {
        return fetch(new Request(url, { cache: 'reload' }))
          .then(function (res) { if (res.ok) return cache.put(url, res); });
      }));
    }).then(function () { return self.skipWaiting(); })
  );
});

self.addEventListener('activate', function (e) {
  e.waitUntil(
    caches.keys().then(function (keys) {
      return Promise.all(keys.map(function (k) { if (k !== CACHE) return caches.delete(k); }));
    }).then(function () { return self.clients.claim(); })
  );
});

self.addEventListener('fetch', function (e) {
  var req = e.request;
  if (req.method !== 'GET' || new URL(req.url).origin !== location.origin) return;
  /* /patwari/ is a separate site with its own worker. Never answer for it here:
     this worker stores every navigation as index.html, so the Patwari page
     would replace the Key's offline copy. */
  if (new URL(req.url).pathname.indexOf('/patwari/') !== -1) return;
  e.respondWith(
    fetch(req).then(function (res) {
      if (res && res.ok) {
        var copy = res.clone();
        caches.open(CACHE).then(function (c) { c.put(req.mode === 'navigate' ? './index.html' : req, copy); });
      }
      return res;
    }).catch(function () {
      return caches.match(req.mode === 'navigate' ? './index.html' : req).then(function (hit) {
        return hit || caches.match('./');
      });
    })
  );
});
