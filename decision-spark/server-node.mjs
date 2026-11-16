import { createServer as createHttpServer, request as httpRequest, Agent as HttpAgent } from 'node:http';
import { readFile } from 'node:fs/promises';
import { join, extname, normalize } from 'node:path';

const PORT = process.env.PORT || 3000;
const API_TARGET = process.env.VITE_API_BASE_URL || 'http://localhost:8000';
const CLIENT_DIR = join(process.cwd(), 'dist', 'client');

// Fresh connection per proxied request: avoids stale keep-alive sockets that
// produce intermittent 502s after long-running responses (reports, PDFs...).
const backendAgent = new HttpAgent({ keepAlive: false, maxSockets: 32 });

const MIME_TYPES = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'application/javascript; charset=utf-8',
  '.mjs': 'application/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.gif': 'image/gif',
  '.svg': 'image/svg+xml',
  '.ico': 'image/x-icon',
  '.woff': 'font/woff',
  '.woff2': 'font/woff2',
  '.ttf': 'font/ttf',
  '.map': 'application/json',
  '.txt': 'text/plain; charset=utf-8',
};

async function serveStatic(nodeReq, nodeRes) {
  let urlPath = decodeURIComponent(new URL(nodeReq.url, `http://localhost:${PORT}`).pathname);
  if (urlPath === '/' || urlPath === '/index.html') {
    urlPath = '/index.html';
  }
  if (urlPath.startsWith('/assets/')) {
    const filePath = normalize(join(CLIENT_DIR, urlPath));
    if (!filePath.startsWith(CLIENT_DIR)) {
      nodeRes.writeHead(403);
      return nodeRes.end('Forbidden');
    }
    return sendFile(filePath, nodeRes);
  }
  if (urlPath === '/logo.png' || urlPath === '/favicon.png' || urlPath === '/favicon.ico') {
    return sendFile(join(CLIENT_DIR, urlPath.replace('/', '')), nodeRes);
  }
  return null;
}

async function sendFile(filePath, nodeRes) {
  try {
    const data = await readFile(filePath);
    const ext = extname(filePath).toLowerCase();
    nodeRes.writeHead(200, {
      'Content-Type': MIME_TYPES[ext] || 'application/octet-stream',
      'Cache-Control': ext === '.html' ? 'no-cache' : 'public, max-age=31536000, immutable',
    });
    nodeRes.end(data);
    return true;
  } catch {
    nodeRes.writeHead(404);
    nodeRes.end('Not Found');
    return false;
  }
}

let serverModule;
async function getServer() {
  if (!serverModule) {
    serverModule = await import('./dist/server/server.js');
  }
  return serverModule.default ?? serverModule;
}

function proxyToBackend(nodeReq, nodeRes) {
  const target = new URL(nodeReq.url, API_TARGET);
  const chunks = [];
  nodeReq.on('data', (c) => chunks.push(c));
  nodeReq.on('end', () => {
    const body = Buffer.concat(chunks);
    const headers = { ...nodeReq.headers };
    headers.host = nodeReq.headers.host;
    headers.connection = 'close';
    const proxyReq = httpRequest(
      target,
      {
        method: nodeReq.method,
        headers,
        agent: backendAgent,
        timeout: 120000,
      },
      (proxyRes) => {
        nodeRes.writeHead(proxyRes.statusCode, proxyRes.headers);
        proxyRes.pipe(nodeRes);
      },
    );
    proxyReq.on('error', (e) => {
      console.error('Proxy error:', e.message);
      if (nodeRes.headersSent) {
        nodeRes.destroy();
        return;
      }
      nodeRes.writeHead(502);
      nodeRes.end('Bad Gateway');
    });
    proxyReq.on('timeout', () => {
      console.error('Proxy timeout for', nodeReq.url);
      proxyReq.destroy(new Error('timeout'));
    });
    if (body.length) proxyReq.write(body);
    proxyReq.end();
  });
}

const httpServer = createHttpServer(async (nodeReq, nodeRes) => {
  try {
    if (nodeReq.url.startsWith('/api/') || nodeReq.url.startsWith('/media/')) {
      return proxyToBackend(nodeReq, nodeRes);
    }

    const served = await serveStatic(nodeReq, nodeRes);
    if (served) return;

    const url = new URL(nodeReq.url, `http://localhost:${PORT}`);

    let body = undefined;
    if (['POST', 'PUT', 'PATCH'].includes(nodeReq.method)) {
      const chunks = [];
      for await (const chunk of nodeReq) chunks.push(chunk);
      body = new Uint8Array(Buffer.concat(chunks));
    }

    const headers = new Headers();
    for (const [key, value] of Object.entries(nodeReq.headers)) {
      if (value) headers.set(key, Array.isArray(value) ? value.join(', ') : value);
    }

    const webRequest = new Request(url.toString(), {
      method: nodeReq.method,
      headers,
      body: body && nodeReq.method !== 'GET' && nodeReq.method !== 'HEAD' ? body : undefined,
    });

    const server = await getServer();
    const response = await server.fetch(webRequest, process.env, {});

    nodeRes.writeHead(response.status, Object.fromEntries(response.headers.entries()));

    if (response.body) {
      const reader = response.body.getReader();
      const pump = async () => {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          nodeRes.write(value instanceof Uint8Array ? value : new Uint8Array(value));
        }
        nodeRes.end();
      };
      await pump();
    } else {
      nodeRes.end();
    }
  } catch (error) {
    console.error('Server error:', error);
    if (nodeRes.headersSent) {
      nodeRes.destroy();
    } else {
      nodeRes.writeHead(500, { 'Content-Type': 'text/plain' });
      nodeRes.end('Internal Server Error');
    }
  }
});

httpServer.listen(PORT, () => {
  console.log(`DécisioBI server running on port ${PORT} → API proxy: ${API_TARGET}`);
});
