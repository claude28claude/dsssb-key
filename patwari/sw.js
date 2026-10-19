/* DUSIB Patwari Prep — service worker.

   Precaches the whole site so it works with no network.
   Same two strategies as the main site: the page and its scripts are
   network-first (an update lands on the next online visit, the cached copy
   answers when offline), the fonts and icons are stale-while-revalidate.
   Bump CACHE on any deploy that changes a file listed in ASSETS. */

var CACHE = 'patwari-v9';
var ASSETS = [
  './', './index.html', './qbank.js', './manifest.webmanifest',
  './icon-180.png', './icon-192.png', './icon-512.png',
  '../fonts/inter-400.woff2', '../fonts/inter-600.woff2',
  '../fonts/literata-400.woff2', '../fonts/literata-600.woff2',
  '../fonts/plexmono-400.woff2', '../fonts/plexmono-500.woff2'
];

/* cache: 'reload' skips the HTTP cache, so a worker installing just after a
   deploy precaches the new bytes rather than GitHub Pages' cached old ones. */
self.addEventListener('install', function (e) {
  e.waitUntil(
    caches.open(CACHE).then(function (c) {
      return Promise.all(ASSETS.map(function (url) {
        return fetch(new Request(url, { cache: 'reload' })).then(function (res) {
          if (!res || !res.ok) throw new Error('precache failed: ' + url);
          return c.put(url, res);
        });
      }));
    }).then(function () { return self.skipWaiting(); })
  );
});

self.addEventListener('activate', function (e) {
  e.waitUntil(
    caches.keys().then(function (keys) {
      return Promise.all(keys.map(function (k) {
        return (k.indexOf('patwari-') === 0 && k !== CACHE) ? caches.delete(k) : null;
      }));
    }).then(function () { return self.clients.claim(); })
  );
});

function keep(req, res) {
  if (res && res.status === 200 && res.type === 'basic') {
    var copy = res.clone();
    caches.open(CACHE).then(function (c) { c.put(req, copy); });
  }
  return res;
}

function isShell(url) {
  return /(\/|\/index\.html|\/qbank\.js)$/.test(url.pathname);
}

self.addEventListener('fetch', function (e) {
  var req = e.request, url;
  try { url = new URL(req.url); } catch (err) { return; }
  if (req.method !== 'GET' || url.origin !== self.location.origin) return;

  if (req.mode === 'navigate' || isShell(url)) {
    e.respondWith(
      fetch(req).then(function (res) { return keep(req, res); })
        .catch(function () {
          return caches.match(req, { ignoreSearch: true }).then(function (hit) {
            if (hit) return hit;
            return req.mode === 'navigate' ? caches.match('./index.html') : undefined;
          });
        })
    );
    return;
  }

  e.respondWith(
    caches.match(req).then(function (hit) {
      var net = fetch(req).then(function (res) { return keep(req, res); })
                          .catch(function () { return hit; });
      return hit || net;
    })
  );
});
