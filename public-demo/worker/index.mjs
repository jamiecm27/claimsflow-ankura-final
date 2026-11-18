import { geminiRoute } from './gemini.mjs';
import { assets, claims } from './assets.mjs';

export default {
  async fetch(request, env) {
    const pathname = new URL(request.url).pathname;
    if (pathname.startsWith('/api/gemini/')) return geminiRoute(request, env, claims, assets);
    if (request.method !== 'GET' && request.method !== 'HEAD') return new Response('Method not allowed', { status: 405 });
    let path;
    try { path = decodeURIComponent(pathname); }
    catch { return new Response('Invalid path', { status: 400 }); }
    if (path.endsWith('/')) path += 'index.html';
    if (path === '/claims-inbox') return Response.redirect(new URL('/claims-inbox/', request.url), 308);
    const asset = Object.hasOwn(assets, path) ? assets[path] : null;
    if (!asset) return new Response('Not found', { status: 404 });
    return new Response(request.method === 'HEAD' ? null : Uint8Array.from(atob(asset.data), char => char.charCodeAt(0)), {
      headers: {
        'Content-Type': asset.mime,
        'Cache-Control': path.startsWith('/assets/') ? 'public, max-age=31536000, immutable' : 'no-cache',
        'X-Content-Type-Options': 'nosniff',
      },
    });
  },
};
