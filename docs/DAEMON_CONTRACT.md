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

### `GET /launch?token=<launch_token>[&api_base=<url>]`

Consumes a one-time launch token and spawns a DCC with:

- `ZENO_API_BASE_URL`
- `ZENO_LAUNCH_CONTEXT`

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
2. Call daemon `GET /launch?token=...`.
3. If daemon unreachable, optional fallback to `zeno://`.
