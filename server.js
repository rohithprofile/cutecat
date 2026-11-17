import { statSync, createReadStream, existsSync } from "fs";
import { extname, join, normalize } from "path";

const ROOT = import.meta.dir;
const PUBLIC_DIR = join(ROOT, "public");
const THREE_DIR = join(ROOT, "node_modules", "three");
const PORT = Number(process.env.PORT || 3456);

const MIME_TYPES = {
  ".html": "text/html; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".js": "application/javascript; charset=utf-8",
  ".mjs": "application/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".glb": "model/gltf-binary",
  ".gltf": "model/gltf+json",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".svg": "image/svg+xml",
  ".ico": "image/x-icon",
};

function safeResolve(baseDir, relPath) {
  const cleaned = normalize(relPath).replace(/^(\.\.[/\\])+/, "");
  const full = join(baseDir, cleaned);
  if (!full.startsWith(baseDir)) return null;
  return full;
}

const server = Bun.serve({
  port: PORT,
  async fetch(req) {
    const url = new URL(req.url);
    let pathname = decodeURIComponent(url.pathname);
    if (pathname === "/") pathname = "/index.html";

    let filePath = safeResolve(PUBLIC_DIR, pathname.slice(1));
    if ((!filePath || !existsSync(filePath)) && pathname.startsWith("/three/")) {
      filePath = safeResolve(THREE_DIR, pathname.slice("/three/".length));
    }

    if (!filePath || !existsSync(filePath)) {
      return new Response("Not Found", { status: 404 });
    }

    const st = statSync(filePath);
    if (st.isDirectory()) {
      return new Response("Forbidden", { status: 403 });
    }

    const ext = extname(filePath).toLowerCase();
    const contentType = MIME_TYPES[ext] || "application/octet-stream";

    return new Response(Bun.file(filePath), {
      headers: {
        "Content-Type": contentType,
        "Cache-Control": "no-store, no-cache, must-revalidate",
      },
    });
  },
});

console.log(`Cute Cat 3D server running at http://localhost:${server.port}`);
