// Minimal Map-backed polyfill for wasi:keyvalue/* used by wasmcp's
// composition framework. Good enough to make transpiled bundles load
// in environments (browser, node) where no real KV store exists.

const buckets = new Map(); // bucketId -> Map<string, Uint8Array>

export class Bucket {
  constructor(name) {
    this.name = name;
    if (!buckets.has(name)) buckets.set(name, new Map());
    this.store = buckets.get(name);
  }
  get(key) {
    return this.store.has(key) ? this.store.get(key) : undefined;
  }
  set(key, value) {
    this.store.set(key, value);
  }
  delete(key) {
    this.store.delete(key);
  }
  exists(key) {
    return this.store.has(key);
  }
  listKeys(cursor) {
    return { keys: Array.from(this.store.keys()), cursor: undefined };
  }
}

export function open(identifier) {
  return new Bucket(identifier);
}

// batch
export function getMany(bucket, keys) {
  return keys.map(k => [k, bucket.get(k)]);
}
export function setMany(bucket, items) {
  for (const { key, value } of items) bucket.set(key, value);
}
export function deleteMany(bucket, keys) {
  for (const k of keys) bucket.delete(k);
}

// atomics
export function increment(bucket, key, delta) {
  const cur = bucket.get(key);
  const n = cur ? Number(new TextDecoder().decode(cur)) : 0;
  const next = n + delta;
  bucket.set(key, new TextEncoder().encode(String(next)));
  return next;
}
