# A2A endpoints

Every endpoint the A2A handler exposes. Served on port 7870 by default.

## Well-known paths

| Path | Returns |
|---|---|
| `GET /.well-known/agent-card.json` | The agent card as JSON |
| `GET /.well-known/agent.json` | Alias for the card; some clients expect this path |

Both paths return identical content. Serving both is a spec compatibility hedge — early A2A clients (including older `@a2a-js/sdk` versions) probed different paths.

## JSON-RPC methods (POST /a2a)

All methods use JSON-RPC 2.0 envelopes:

```json
{
  "jsonrpc": "2.0",
  "id": "<caller-chosen>",
  "method": "<name>",
  "params": { ... }
}
```

### `message/send` — blocking

Submit a message and wait for the terminal task. Returns the full Task object including artifacts.

```json
{
  "method": "message/send",
  "params": {
    "message": {
      "role": "user",
      "parts": [{"text": "summarize https://example.com"}]
    },
    "metadata": {"skill": "summarize_pr"}
  }
}
```

Result shape:

```json
{
  "result": {
    "kind": "task",
    "id": "<task-id>",
    "contextId": "<ctx-id>",
    "status": {"state": "completed"},
    "artifacts": [...],
    "data": {
      "usage": {"input_tokens": 1200, "output_tokens": 340, "total_tokens": 1540},
      "durationMs": 4230
    }
  }
}
```

The `kind: "task"` discriminator is required — `@a2a-js/sdk` routes by it.

### `message/stream` — SSE

Same as `message/send` but streams frames as the run progresses. One SSE event per frame. Every frame carries a `kind` discriminator:

| `kind` | When emitted |
|---|---|
| `task` | First frame — initial task state |
| `status-update` | State transitions, tool-start / tool-end progress |
| `artifact-update` | Streaming partial outputs |

Consumers must check `kind` before interpreting fields — without it, `@a2a-js/sdk`'s `for await` loop silently skips frames.

### `tasks/get`

```json
{"method": "tasks/get", "params": {"id": "<task-id>"}}
```

Returns the current state of a task. Use to poll when push notifications aren't wired.

### `tasks/resubscribe`

```json
{"method": "tasks/resubscribe", "params": {"id": "<task-id>"}}
```

SSE stream of remaining frames for an in-flight task. Lets a consumer reconnect after a network blip without losing events.

### `tasks/cancel`

```json
{"method": "tasks/cancel", "params": {"id": "<task-id>"}}
```

Transitions the task to `canceled` if it's still running. No-op on terminal tasks.

### `tasks/pushNotificationConfig/{set,get,list,delete}`

Register webhooks for terminal task delivery.

```json
{
  "method": "tasks/pushNotificationConfig/set",
  "params": {
    "taskId": "<task-id>",
    "pushNotificationConfig": {
      "url": "https://consumer/callback/abc",
      "token": "shared-secret"
    }
  }
}
```

The handler accepts both token shapes the A2A spec permits:

| Shape | JSON |
|---|---|
| Top-level `token` (what `@a2a-js/sdk` serializes by default) | `{"url": "...", "token": "..."}` |
| Structured `authentication.credentials` (RFC-8821) | `{"url": "...", "authentication": {"schemes": ["Bearer"], "credentials": "..."}}` |

Both produce `Authorization: Bearer <token>` on outgoing webhook POSTs. When both are present, top-level wins.

## REST aliases

Thin REST wrappers are also exposed for non-JSON-RPC clients:

| Method + Path | Equivalent to |
|---|---|
| `POST /a2a/tasks/:taskId/pushNotificationConfig` | `tasks/pushNotificationConfig/set` |
| `GET /a2a/tasks/:taskId/pushNotificationConfig` | `tasks/pushNotificationConfig/list` |
| `GET /a2a/tasks/:taskId` | `tasks/get` |

Same semantics, same token-shape parsing, same SSRF guarding.

## SSRF guard

Outgoing webhook URLs are resolved once and checked against an allowlist before the handler accepts a push config. By default, private IP ranges (RFC1918 + loopback + link-local) are refused.

To permit trusted docker-network hostnames, set:

```bash
PUSH_NOTIFICATION_ALLOWED_HOSTS=workstacean,automaker-server
PUSH_NOTIFICATION_ALLOWED_CIDRS=10.0.0.0/8,172.16.0.0/12
```

Hosts in `PUSH_NOTIFICATION_ALLOWED_HOSTS` bypass the DNS check entirely.

## Extension advertisement

The card's `capabilities.extensions` array declares protocol extensions the agent implements. See [Extensions reference](/reference/extensions) for the ones the template ships.
