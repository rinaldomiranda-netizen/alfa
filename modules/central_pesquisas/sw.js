/* Central de Pesquisas — funcionamento sem internet.
 * Guarda as telas do sistema no aparelho. Os DADOS nunca passam por aqui (vão direto ao banco, com login);
 * entrevistas feitas sem internet ficam na fila do aparelho e são enviadas pela própria tela quando a conexão volta. */
const VERSAO = "cp-2026.10.10-1";
const TELAS = ["./", "index.html", "manifest.webmanifest", "css/estilo.css", "aparencia.css", "css/moderno.css",
  "js/config.js", "js/nucleo.js", "js/usuarios.js", "js/pesquisas.js", "js/regioes.js", "js/entrevista.js", "js/painel.js",
  "js/app.js", "js/moderno.js", "js/iniciar.js", "aparencia.js", "icones/icone-192.png", "icones/icone-512.png", "icones/favicon.png",
  "lib/supabase-2.45.4.js", "lib/xlsx-0.18.5.min.js"];

self.addEventListener("install", e => {
  e.waitUntil((async () => {
    const c = await caches.open(VERSAO);
    await c.addAll(TELAS.map(u => new Request(u, { cache: "reload" })));
    await self.skipWaiting();
  })());
});
self.addEventListener("activate", e => {
  e.waitUntil((async () => {
    for (const k of await caches.keys()) if (k !== VERSAO) await caches.delete(k);
    await self.clients.claim();
  })());
});
self.addEventListener("fetch", e => {
  const req = e.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  // Banco e login: sempre direto, nunca guardado
  if (/supabase\.(co|in)$/.test(url.hostname)) return;
  if (url.origin !== self.location.origin) return;
  {
    // telas: tenta a versão mais nova; sem internet usa a guardada
    e.respondWith((async () => {
      const c = await caches.open(VERSAO);
      try {
        const r = await fetch(req);
        if (r.ok) c.put(req, r.clone());
        return r;
      } catch (_) {
        return (await c.match(req, { ignoreSearch: true })) || (req.mode === "navigate" ? c.match("index.html") : Response.error());
      }
    })());
  }
});
