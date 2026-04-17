# Extensions

A2A extensions the template implements. Each is either emitted, parsed, or both.

## `cost-v1`

**URI**: `https://protolabs.ai/a2a/ext/cost-v1`
**Direction**: emitted by this agent
**Declared on card**: yes (by default)

Every terminal task carries a DataPart with token usage and duration:

```json
{
  "data": {
    "usage": {
      "input_tokens": 1200,
      "output_tokens": 340,
      "total_tokens": 1540
    },
    "durationMs": 4230
  }
}
```

Captured by the `on_chat_model_end` handler in `_chat_langgraph_stream`. Requires `stream_usage=True` on the ChatOpenAI client — the template sets this in `graph/llm.py`.

**Consumers** (like Workstacean's A2AExecutor) extract this DataPart onto `result.data` and record per-(agent, skill) samples. The consumer keys on the `skill` ID from the card, so skill IDs must be stable.

`costUsd` is not captured today — deriving it from model rates is a follow-up. Consumers tolerate missing `costUsd` and can compute it from `usage` themselves.

## `effect-domain-v1`

**URI**: `https://protolabs.ai/a2a/ext/effect-domain-v1`
**Direction**: declared by this agent
**Declared on card**: no (template has no mutating skills)

Advertises per-skill world-state mutations so Workstacean's L1 planner can rank your agent against goals that target those state selectors.

```json
{
  "uri": "https://protolabs.ai/a2a/ext/effect-domain-v1",
  "params": {
    "skills": {
      "file_bug": {
        "effects": [{
          "domain": "protomaker_board",
          "path": "data.backlog_count",
          "delta": 1,
          "confidence": 0.9
        }]
      }
    }
  }
}
```

Fields:

| Field | What |
|---|---|
| `domain` | World-state selector domain the mutation targets |
| `path` | Dotted path within the domain |
| `delta` | Signed numeric delta (positive = increase) |
| `confidence` | 0–1 prior for the planner's ranking model |

Only declare effects that actually mutate shared state. Over-declaring confuses the planner into routing your agent for goals it can't move.

**Pair with runtime emission**: if you declare an effect, emit a matching `worldstate-delta-v1` DataPart when the tool succeeds at runtime (see `a2a_handler.py::TaskRecord.world_deltas`). Divergence between declared and observed mutations breaks the planner's scoring model.

See `docs/extensions/effect-domain-v1` in the [protoWorkstacean repo](https://github.com/protoLabsAI/protoWorkstacean) for the full spec.

## `worldstate-delta-v1`

**URI**: (runtime artifact only, not a card extension)
**Direction**: emitted when tools with declared effects succeed
**Declared on card**: n/a

Emitted as a DataPart on the terminal artifact:

```json
{
  "mime": "application/vnd.protolabs.worldstate-delta-v1+json",
  "data": {
    "deltas": [{
      "domain": "protomaker_board",
      "path": "data.backlog_count",
      "op": "inc",
      "value": 1
    }]
  }
}
```

The template doesn't emit this by default because the shipped tools don't mutate anything. See `a2a_handler.py::TaskRecord.add_delta` for where to hook in.

## `a2a.trace` — distributed Langfuse propagation

**Not an extension**, a protocol convention. Lives in `params.metadata`, not `capabilities.extensions`.

**Direction**: parsed by this agent (incoming)

When the caller stamps their trace context:

```json
{
  "method": "message/send",
  "params": {
    "message": {...},
    "metadata": {
      "a2a.trace": {
        "traceId": "abc123",
        "spanId": "def456"
      }
    }
  }
}
```

The agent reads it in `a2a_handler.py` and stamps `caller_trace_id` + `caller_span_id` into its own Langfuse trace metadata. Operators can then filter Langfuse by `metadata.caller_trace_id` to find every agent trace spawned from a single dispatch.

## Adding a new extension

1. Emit or parse in `a2a_handler.py` / `server.py`.
2. Declare on the card under `capabilities.extensions` with a URI consumers agree on.
3. Document the shape in this file.
4. Add a test to `tests/test_a2a_integration.py` asserting the declaration is present on the card.

## Related

- [Agent card reference](/reference/agent-card) — where extensions are declared
- [A2A endpoints](/reference/a2a-endpoints) — how artifacts reach consumers
- [Explanation: cost and trace](/explanation/cost-and-trace) — why these extensions are shaped this way
