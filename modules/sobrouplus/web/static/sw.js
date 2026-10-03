/* Sobrou+ — service worker: app instalável, atualização automática e aviso no celular. */
const CACHE = "sobrou-v1";
const BASE = self.registration.scope;               // ex.: https://…/sobrou/
const ESSENCIAIS = ["", "painel", "entregador", "static/css/sobrou.css", "static/css/app.css", "static/css/painel.css",
  "static/js/comum.js", "static/js/app.js", "static/js/painel.js", "static/js/entregador.js", "static/js/qrcode.js",
  "static/vendor/leaflet/leaflet.js", "static/vendor/leaflet/leaflet.css", "static/img/logo.png", "static/img/logo-marca-clara.png"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(ESSENCIAIS.map((u) => BASE + u))).catch(() => null));
  self.skipWaiting();                                // versão nova entra na hora
});
self.addEventListener("activate", (e) => {
  e.waitUntil(caches.keys().then((ks) => Promise.all(ks.filter((k) => k !== CACHE).map((k) => caches.delete(k)))).then(() => self.clients.claim()));
});
/* Rede primeiro (sempre a versão mais nova); sem internet, usa a cópia guardada. A API nunca é guardada. */
self.addEventListener("fetch", (e) => {
  const u = new URL(e.request.url);
  if (e.request.method !== "GET" || u.origin !== location.origin || u.pathname.includes("/api/")) return;
  e.respondWith(fetch(e.request).then((r) => {
    if (r.ok && (u.pathname.includes("/static/") || u.pathname.includes("/fotos/") || (r.headers.get("content-type") || "").includes("text/html"))) {
      const copia = r.clone(); caches.open(CACHE).then((c) => c.put(e.request, copia));
    }
    return r;
  }).catch(() => caches.match(e.request).then((r) => r || caches.match(BASE))));
});
self.addEventListener("push", (e) => {
  let d = {};
  try { d = e.data.json(); } catch (x) { d = { texto: e.data ? e.data.text() : "" }; }
  e.waitUntil(self.registration.showNotification(d.titulo || "Sobrou+", {
    body: d.texto || "", icon: BASE + "static/img/icone-192.png", badge: BASE + "static/img/icone-192.png",
    data: { link: d.link || "" }, vibrate: [120, 60, 120],
  }));
});
self.addEventListener("notificationclick", (e) => {
  e.notification.close();
  const alvo = BASE + (e.notification.data.link || "").replace(/^\//, "");
  e.waitUntil(self.clients.matchAll({ type: "window" }).then((ws) => {
    for (const w of ws) if (w.url.startsWith(BASE)) { w.focus(); return w.navigate(alvo); }
    return self.clients.openWindow(alvo);
  }));
});
