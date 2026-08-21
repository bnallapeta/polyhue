# polyhue

A polyglot MCP server composed from three language components — Rust, Python, and TypeScript — plus a Regorus-backed authorization gate, distributed as a single WASM artifact.

Each language component returns a color from a palette unique to that language. When a phone (or browser tab) loads the audience page, it's routed to one of the components by a server-side hash, gets back an HSL color, and paints itself with that color. A separate broadcast channel can flash every connected client red simultaneously — triggered by a policy denial inside the Regorus middleware.

Built as a live demo for a talk on the WebAssembly Component Model + MCP.

## What's inside

```
polyhue/
├── components/                       # three language components + a policy gate
│   ├── color-rs/                     # Rust → red-orange palette
│   ├── color-py/                     # Python → blue palette
│   ├── color-ts/                     # TypeScript (Zod) → yellow/gold palette
│   └── policy-gate/                  # Rust + Regorus → policy denial → flash
├── audience/                         # static page + dev proxy
│   ├── index.html                    #   loads, gets a color, listens for flash
│   └── serve.py                      #   ThreadingHTTPServer: routes /color,
│                                     #   forwards /mcp, fans out /events SSE,
│                                     #   triggers Regorus denial via /trigger-denial
├── dist/                             # composed artifact lands here (gitignored)
│   └── polyhue.wasm
├── scripts/profile-sizes.py          # measure component sizes under strip passes
└── experiments/                      # parked exploratory work
    └── browser-test/                 # jco transpile experiment
```

## Prerequisites

- `rustup` (single Rust toolchain — Homebrew Rust shadows rustup if installed)
- `wasm32-wasip2` target: `rustup target add wasm32-wasip2`
- [`spin`](https://github.com/spinframework/spin) (`brew install spinframework/tap/spin`)
- [`wasmcp`](https://github.com/wasmcp/wasmcp) CLI: `cargo install --git https://github.com/wasmcp/wasmcp`
- [`wasm-tools`](https://github.com/bytecodealliance/wasm-tools) (`brew install wasm-tools`)
- Node.js 22+ (for the TypeScript component build)
- Python 3.11+ (used by `componentize-py` and the audience proxy)

## Build & run

```bash
make             # build all components + compose into dist/polyhue.wasm
make run         # start the wasmcp server (:3000) and audience proxy (:8080)
```

Then open <http://localhost:8080/> in one or more browser tabs. Each tab gets assigned a color from one of the three language palettes.

Trigger the policy denial → red-flash beat from another terminal:

```bash
curl -X POST http://localhost:8080/trigger-denial -H "X-Admin-Token: $ADMIN_TOKEN"
```

Every connected tab flashes red at once. The response tells you how many were reached and why Regorus denied.

## Endpoints (audience proxy, port 8080)

| Method | Path | Purpose |
|---|---|---|
| `GET`  | `/` | the audience page (static `index.html`) |
| `POST` | `/color` | hashes `{seed}` → picks language → calls upstream `get_color_*` tool |
| `POST` | `/mcp` | raw passthrough to the wasmcp server at `:3000/mcp` |
| `GET`  | `/events` | server-sent events stream (clients subscribe here) |
| `POST` | `/broadcast` | fan out an arbitrary event to all `/events` subscribers |
| `POST` | `/trigger-denial` | call the Regorus-gated tool; on denial, broadcast `flash` |

## Security caveats

This is a live-demo project. A few defaults that are fine for a single laptop in a controlled room, but matter the moment you put it on a real network:

- `audience/serve.py` binds to `0.0.0.0:8080`. `/broadcast`, `/trigger-denial`, and `/mcp` require an admin token in an `X-Admin-Token` header; set it with `ADMIN_TOKEN`, or a random one is generated and printed at startup. There is no unauthenticated mode — a forgotten env var generates a token rather than falling open. The audience paths (`/`, `/color`, `/events`) are deliberately open, since phones must reach them with no credential.
- **No localhost exemption, on purpose.** Behind Tailscale Funnel the proxy target is `127.0.0.1:8080`, so every public request arrives looking like it came from localhost. Trusting the source IP would expose the admin endpoints to the internet.
- The wasmcp server (Spin) runs in public mode. No auth on `/mcp` either.
- No rate limiting anywhere.

For the talk room this is intentional. For anything beyond, add a token check, restrict the listen interface, or front it with a reverse proxy that does both.

## License

Apache License 2.0. See [LICENSE](LICENSE) and [NOTICE](NOTICE).
