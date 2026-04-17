---
layout: home
hero:
  name: protoAgent
  text: LangGraph + A2A template for protoLabs agents
  tagline: Fork this repo. Rewrite SOUL.md, prompts, and tools. Ship.
  actions:
    - theme: brand
      text: Spin up your first agent
      link: /tutorials/first-agent
    - theme: alt
      text: Reference
      link: /reference/

features:
  - icon: 🔌
    title: A2A out of the box
    details: JSON-RPC 2.0 over /a2a, SSE streaming, tasks/* lifecycle, push notifications, dual token-shape parsing — all spec-compliant, all already tested.
  - icon: 💰
    title: cost-v1 + trace propagation
    details: Every terminal task emits a cost-v1 DataPart with token usage and wall time. a2a.trace metadata nests this agent's Langfuse trace under the caller's.
  - icon: 🧰
    title: Free starter tools
    details: DuckDuckGo web search, URL fetch, safe calculator, and IANA-timezone clock — zero API keys, enough to demo a real research loop on a fresh clone.
  - icon: 🚀
    title: Autonomous release pipeline
    details: Merge a PR → semver bump → GHCR image → GitHub release → Discord embed. Update the repo guard in three workflow files and you're done.
---

## Documentation Structure

This site follows the [Diátaxis](https://diataxis.fr) framework:

| Section | Purpose | Start here if you… |
|---------|---------|---------------------|
| [**Tutorials**](/tutorials/) | Learning-oriented walkthroughs | Are about to fork protoAgent for the first time |
| [**How-To Guides**](/guides/) | Task-oriented procedures | Need to accomplish a specific change in a fork |
| [**Reference**](/reference/) | Technical descriptions | Need exact details on an API, config key, or extension |
| [**Explanation**](/explanation/) | Understanding-oriented discussion | Want to understand why the template is shaped this way |

## Canonical reference implementation

[protoLabsAI/quinn](https://github.com/protoLabsAI/quinn) was the first agent built on this template. When the docs here don't cover something specific, Quinn is the filled-in example to consult.
