// Cache do layout, nunca de dados de investimentos ou notícias.
const CACHE="clara-fiis-shell-v1";
self.addEventListener("install",event=>{event.waitUntil(caches.open(CACHE).then(c=>c.addAll(["./","./index.html","./manifest.webmanifest","./icon.svg"])));self.skipWaiting();});
self.addEventListener("activate",event=>{event.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(k=>k!==CACHE).map(k=>caches.delete(k)))));self.clients.claim();});
self.addEventListener("fetch",event=>{const u=new URL(event.request.url);if(u.pathname.includes("/data/")||event.request.method!=="GET")return;if(u.origin!==self.location.origin)return;event.respondWith(fetch(event.request).catch(()=>caches.match(event.request)));});
