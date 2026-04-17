# Spin up your first agent

This walks you from "I clicked Use this template" to "I have a running agent answering a web-search query". About 15 minutes, assuming Docker and a LiteLLM gateway are already set up.

## What you'll need

- A GitHub account with access to `protoLabsAI` (or your own org — the workflows gate on the repo owner; see step 7)
- Docker
- A LiteLLM gateway running somewhere reachable (the template points at `http://gateway:4000/v1`)
- A model alias in that gateway. The template's default is `protolabs/agent` — either add that alias or retarget `model.name` in step 4

## 1. Use the template

From GitHub, click **Use this template → Create a new repository** on [protoLabsAI/protoAgent](https://github.com/protoLabsAI/protoAgent). Pick a short slug like `jon` or `echo-agent` — it will end up as the image name, metric prefix, Langfuse tag, and more.

Or from the CLI:

```bash
gh repo create protoLabsAI/my-agent \
    --template protoLabsAI/protoAgent \
    --public --clone

cd my-agent
```

## 2. Rename the agent

The template uses `protoagent` as the placeholder throughout. Do a pass:

```bash
git grep -li protoagent | xargs sed -i 's/protoagent/my-agent/g'
git grep -li protoAgent | xargs sed -i 's/protoAgent/MyAgent/g'
```

Review the diff before committing — the replacement hits Dockerfile paths (`/opt/protoagent` → `/opt/my-agent`), the GHCR image path, workflow repo guards, and the Gradio UI branding. All of those want the new name.

## 3. Rewrite identity

Three files carry the agent's identity. Edit each one:

- `config/SOUL.md` — the persona doc loaded at session start. See the placeholder file itself for guidance.
- `graph/prompts.py` — the system prompt for the lead agent + subagents.
- `server.py::_build_agent_card` — the agent card served at `/.well-known/agent-card.json`. At minimum, fix `name` and `description`; revisit `skills` once you have real tools.

## 4. Point at a model

Edit `config/langgraph-config.yaml`:

```yaml
model:
  name: protolabs/my-agent   # or openai/gpt-4o, anthropic/claude-opus-4-6, etc.
  api_base: http://gateway:4000/v1
```

If you're using a gateway alias (recommended), make sure the alias is registered there before booting — swapping models later becomes a gateway edit instead of a code change.

## 5. Build and run

```bash
docker build -t my-agent:local .
docker run --rm -p 7870:7870 \
    -e AGENT_NAME=my-agent \
    -e OPENAI_API_KEY="$LITELLM_MASTER_KEY" \
    my-agent:local
```

## 6. Verify the agent is up

In another terminal:

```bash
curl http://localhost:7870/.well-known/agent-card.json | jq .name
# → "my-agent"

curl http://localhost:7870/metrics | grep my_agent_active_sessions
# → my_agent_active_sessions 0
```

Hit `http://localhost:7870` in a browser to get the Gradio chat UI. Ask it:

> What time is it in Tokyo?

If the starter tools are wired correctly, it should call `current_time`, return an ISO-8601 timestamp with the timezone offset, and explain what it found.

Then:

> Find three recent articles about the A2A protocol and summarize them.

The agent will call `web_search`, then `fetch_url` for each of the top results, and return a summary. That round-trip exercises the full tool loop + LLM call + streaming response path.

## 7. Un-freeze the release pipeline

The three release workflows (`docker-publish.yml`, `prepare-release.yml`, `release.yml`) all gate on `github.repository == 'protoLabsAI/protoAgent'`. Change that check in each file to match your repo's owner/repo before merging anything to `main`, or the release automation won't fire.

## Where to go next

- [Write your first tool](/tutorials/first-tool) — wire a custom LangChain tool into the loop
- [Add a custom skill](/guides/add-a-skill) — expose the new behaviour on the A2A agent card
- [Deploy via GHCR](/guides/deploy) — get Watchtower auto-deploying your merges
