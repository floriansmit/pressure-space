const debugPort = Number(process.argv[2] || 9223);
const targetUrl = process.argv[3] || "http://127.0.0.1:4176/";
const target = await fetch(`http://127.0.0.1:${debugPort}/json/new?${encodeURIComponent(targetUrl)}`, { method: "PUT" }).then((response) => response.json());
const socket = new WebSocket(target.webSocketDebuggerUrl);
const pending = new Map();
let nextId = 1;

await new Promise((resolve, reject) => {
  socket.addEventListener("open", resolve, { once: true });
  socket.addEventListener("error", reject, { once: true });
});
socket.addEventListener("message", (event) => {
  const message = JSON.parse(event.data);
  if (!message.id || !pending.has(message.id)) return;
  const { resolve, reject } = pending.get(message.id);
  pending.delete(message.id);
  message.error ? reject(new Error(message.error.message)) : resolve(message.result);
});
const send = (method, params = {}) => new Promise((resolve, reject) => {
  const id = nextId++;
  pending.set(id, { resolve, reject });
  socket.send(JSON.stringify({ id, method, params }));
});
const evaluate = async (expression) => {
  const result = await send("Runtime.evaluate", { expression, returnByValue: true, awaitPromise: true });
  if (result.exceptionDetails) throw new Error(result.exceptionDetails.text);
  return result.result.value;
};

await send("Page.enable");
await send("Runtime.enable");
await send("Page.navigate", { url: targetUrl });
for (let attempt = 0; attempt < 80; attempt++) {
  if (await evaluate("document.readyState === 'complete' && document.querySelectorAll('.model-cell').length > 100")) break;
  await new Promise((resolve) => setTimeout(resolve, 100));
}
const before = await evaluate("document.getElementById('selectedName').textContent");
const hit = await evaluate(`(() => {
  for (const cell of document.querySelectorAll('.model-cell')) {
    const rect = cell.getBoundingClientRect();
    const x = rect.left + rect.width / 2, y = rect.top + rect.height / 2;
    if (rect.width > 2 && rect.height > 2 && document.elementFromPoint(x, y) === cell && cell.dataset.index !== '681') {
      return { x, y, index: Number(cell.dataset.index) };
    }
  }
  return null;
})()`);
if (!hit) throw new Error("No unobscured pressure cell was available for a real pointer click");
await send("Input.dispatchMouseEvent", { type: "mouseMoved", x: hit.x, y: hit.y });
await send("Input.dispatchMouseEvent", { type: "mousePressed", x: hit.x, y: hit.y, button: "left", clickCount: 1 });
await send("Input.dispatchMouseEvent", { type: "mouseReleased", x: hit.x, y: hit.y, button: "left", clickCount: 1 });
await new Promise((resolve) => setTimeout(resolve, 100));
const after = await evaluate("document.getElementById('selectedName').textContent");
const metadata = await evaluate(`({
  appScript: document.querySelector('script[src*="app.js"]')?.getAttribute('src'),
  zetaLabel: document.querySelector('.zeta-card small')?.textContent,
  modelVersion: document.getElementById('provenance')?.textContent,
  errors: window.__pressureErrors || []
})`);
console.log(JSON.stringify({ browser: "Chrome", before, after, clickedCell: hit.index + 1, changed: before !== after, ...metadata }, null, 2));
if (before === after || after !== `Cell ${hit.index + 1}`) process.exitCode = 1;
socket.close();
