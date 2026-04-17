# Configuration

`config/langgraph-config.yaml` is the canonical runtime config. Loaded at server boot by `graph/config.py::LangGraphConfig.from_yaml()`. All fields have defaults; the YAML only needs to override what's changing.

## Full example

```yaml
model:
  provider: openai
  name: protolabs/agent
  api_base: http://gateway:4000/v1
  api_key: ""
  temperature: 0.2
  max_tokens: 4096
  max_iterations: 50

subagents:
  worker:
    enabled: true
    tools: [echo, current_time, calculator, web_search, fetch_url]
    max_turns: 20

middleware:
  knowledge: false
  audit: true
  memory: false

knowledge:
  db_path: /sandbox/knowledge/agent.db
  embed_model: nomic-embed-text
  top_k: 5
```

## `model`

| Key | Default | What |
|---|---|---|
| `provider` | `openai` | LangChain LLM provider. The template's `graph/llm.py` only uses `openai` (via LiteLLM gateway). |
| `name` | `protolabs/agent` | Gateway alias or direct model name. |
| `api_base` | `http://gateway:4000/v1` | OpenAI-compatible endpoint. |
| `api_key` | `""` | Falls back to the `OPENAI_API_KEY` env var. |
| `temperature` | `0.2` | Sampling temperature. |
| `max_tokens` | `4096` | Per-call output cap. |
| `max_iterations` | `50` | Upper bound on tool-call loops per task. |

## `subagents`

One entry per subagent name. Each entry matches a `SubagentConfig` in `graph/subagents/config.py` and a `SubagentDef` field in `LangGraphConfig`.

| Key | Default | What |
|---|---|---|
| `enabled` | `true` | If false, the subagent is still registered but dispatches return "disabled" errors. |
| `tools` | `[]` | Allowlist. Tool names not listed here are invisible to this subagent. |
| `max_turns` | `30` | Recursion cap. |

Adding a new subagent name to the YAML requires matching entries in `graph/subagents/config.py::SUBAGENT_REGISTRY`, `graph/config.py::LangGraphConfig`, and the `from_yaml()` loop. See [Configure subagents](/guides/subagents).

## `middleware`

| Key | Default | What |
|---|---|---|
| `knowledge` | `false` | Inject retrieved knowledge into state before LLM calls. Requires a knowledge store — leave off until you add one. |
| `audit` | `true` | Append every tool call to `/sandbox/audit/audit.jsonl`. |
| `memory` | `false` | Memory middleware (experimental). Requires a knowledge store. |

## `knowledge`

Only read when `middleware.knowledge` is `true`.

| Key | Default | What |
|---|---|---|
| `db_path` | `/sandbox/knowledge/agent.db` | SQLite file path. |
| `embed_model` | `nomic-embed-text` | Embedding model. |
| `top_k` | `5` | Results per query fed into state. |

The template does not ship a knowledge store — the config keys are kept so a fork can flip the switch without rewiring every call site.
