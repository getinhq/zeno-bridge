# Zeno Bridge Daemon Contract

Canonical browser-to-bridge protocol for web launch.

## Base URL

- Default: `http://127.0.0.1:17373`
- Override with env:
  - `ZENO_BRIDGE_DAEMON_HOST`
  - `ZENO_BRIDGE_DAEMON_PORT`

## Endpoints

### `GET /health`

Liveness probe.

Response:

```json
{ "ok": true }
```

### `GET /status`

Returns daemon metadata for UI diagnostics.

Response:

```json
{
  "ok": true,
  "service": "zeno-bridge-daemon",
  "version": "0.1.0",
  "host": "127.0.0.1",
  "port": 17373
}
```

### `POST /launch`

Consumes a one-time launch token and spawns a DCC with:

- `ZENO_API_BASE_URL`
- `ZENO_LAUNCH_CONTEXT`

Request (must be `Content-Type: application/json`, max 4 KB):

```json
{ "token": "<launch_token>" }
```

Rules:

- The `Origin` header must be in the allowlist (`allowed_origins` in config, or
  `ZENO_BRIDGE_ALLOWED_ORIGINS`; default `http://localhost:5173`, `http://127.0.0.1:5173`).
  Other origins get `403` and no CORS headers. Requests with no `Origin` (local CLI tools) are allowed.
- The API base URL is **never** taken from the request. It comes from `ZENO_API_BASE_URL`,
  then `api_base_url` in config, then `http://127.0.0.1:8000`.
- `GET /launch` returns `405`.

Success:

```json
{ "ok": true }
```

Failure:

```json
{ "detail": "..." }
```

## Web client behavior

1. Mint token via `POST /api/v1/launch-tokens`.
2. Call daemon `POST /launch` with `{"token": "..."}`.
3. If daemon unreachable, optional fallback to `zeno://`.
