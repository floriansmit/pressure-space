import { createReadStream, statSync } from "node:fs";
import { createServer } from "node:http";
import { extname, join, normalize } from "node:path";

const port = Number(process.argv[2] || 4176);
const root = join(import.meta.dirname, "..", "dist");
const types = { ".css": "text/css", ".html": "text/html", ".js": "text/javascript", ".json": "application/json", ".png": "image/png", ".svg": "image/svg+xml" };

createServer((request, response) => {
  const pathname = decodeURIComponent(new URL(request.url, `http://${request.headers.host}`).pathname);
  const relative = normalize(pathname === "/" ? "index.html" : pathname.replace(/^\/+/, ""));
  const file = join(root, relative);
  if (!file.startsWith(root)) { response.writeHead(403).end("Forbidden"); return; }
  try {
    if (!statSync(file).isFile()) throw new Error("Not a file");
    response.writeHead(200, {
      "Content-Type": types[extname(file)] || "application/octet-stream",
      "Cache-Control": "no-store, no-cache, must-revalidate, proxy-revalidate",
      Pragma: "no-cache",
      Expires: "0",
    });
    createReadStream(file).pipe(response);
  } catch {
    response.writeHead(404, { "Cache-Control": "no-store" }).end("Not found");
  }
}).listen(port, "127.0.0.1", () => console.log(`DECODE Pressure preview: http://127.0.0.1:${port}/ (cache disabled)`));
