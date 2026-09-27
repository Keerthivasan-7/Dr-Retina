export class BodyTooLarge extends Error {}
/** Bound streamed requests before buffering, including requests without Content-Length. */
export async function readBoundedBody(request: Request, limit = 27 * 1024 * 1024): Promise<ArrayBuffer> {
  const declared = request.headers.get("content-length");
  if (declared && Number(declared) > limit) throw new BodyTooLarge();
  if (!request.body) return new ArrayBuffer(0);
  const reader = request.body.getReader();
  const chunks: Uint8Array[] = [];
  let size = 0;
  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      size += value.byteLength;
      if (size > limit) { await reader.cancel(); throw new BodyTooLarge(); }
      chunks.push(value);
    }
  } finally { reader.releaseLock(); }
  const result = new Uint8Array(size);
  let offset = 0;
  for (const chunk of chunks) { result.set(chunk, offset); offset += chunk.byteLength; }
  return result.buffer;
}

