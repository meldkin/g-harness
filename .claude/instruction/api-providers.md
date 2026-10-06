# API Providers — DeepSeek & CommandCode

> Auto-loaded when the agent needs to call external LLM APIs or switch between model providers.

## Overview

This project supports two external LLM API providers beyond the primary Copilot model:

| Provider | API Type | Base URL Env | Key Env |
|----------|----------|-------------|---------|
| **DeepSeek** | OpenAI-compatible | `DEEPSEEK_BASE_URL` | `DEEPSEEK_API_KEY` |
| **CommandCode** | OpenAI-compatible proxy | `COMMANDCODE_BASE_URL` | `COMMANDCODE_API_KEY` |
| **OpenRouter** | OpenAI-compatible proxy | fixed (`_OPENROUTER_BASE_URL`) | `OPENROUTER_API_KEY` |

Both providers expose OpenAI-compatible `/v1/chat/completions` endpoints. CommandCode proxies multiple models (Claude, GPT, Gemini, DeepSeek, Qwen, Kimi, GLM, MiniMax, Step) through a single API key.

> CommandCode is the provider this repo actually configures (see `.env`). The DeepSeek direct endpoint is optional and is **not** set in this repo's `.env`.

> Model IDs drift. CommandCode adds and retires models without notice, so treat
> `GET {COMMANDCODE_BASE_URL}/models` as the source of truth and re-verify before
> using an ID this file does not list.

## Environment Configuration

Set these environment variables before use. Never hardcode keys in source files.

```powershell
# CommandCode (the provider this repo configures)
[Environment]::SetEnvironmentVariable("COMMANDCODE_BASE_URL", "https://api.commandcode.ai/provider/v1", "User")
[Environment]::SetEnvironmentVariable("COMMANDCODE_API_KEY", "cc-your-commandcode-key", "User")

# DeepSeek direct
[Environment]::SetEnvironmentVariable("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1", "User")
[Environment]::SetEnvironmentVariable("DEEPSEEK_API_KEY", "sk-your-deepseek-key", "User")

# OpenRouter (endpoint is fixed in tools/opencode_engine.py)
[Environment]::SetEnvironmentVariable("OPENROUTER_API_KEY", "sk-or-your-key", "User")
```

After setting, restart VS Code for Copilot to pick up the new variables.

## Model Selection

### Available Models via CommandCode

The ids below were verified against `GET {COMMANDCODE_BASE_URL}/models` on
2026-10-06. The catalog is larger (84 models — Claude, GPT, Gemini, Qwen, Kimi,
GLM, MiniMax, Grok, MiMo, Step, Ling, Muse Spark, …); enumerate it with:

```powershell
Invoke-RestMethod -Uri "$env:COMMANDCODE_BASE_URL/models" `
  -Headers @{ Authorization = "Bearer $env:COMMANDCODE_API_KEY" } |
  Select-Object -ExpandProperty data | Select-Object -ExpandProperty id | Sort-Object
```

| Model ID | Family | Best For |
|----------|--------|----------|
| `deepseek/deepseek-v4-pro` | DeepSeek | Harness default for the OpenCode CLI engine (`opencode.json`) and the Kilo orchestrator (`agent.yaml`) |
| `deepseek/deepseek-v4.1-flash` | DeepSeek | Harness `small_model` (`opencode.json`) — 1M context, cheaper than pro |
| `deepseek/deepseek-v4-flash` | DeepSeek | Previous flash tier. Retired for new Claude sessions (`tools/solocode_config.py`), still served by CommandCode and used by `tools/benchmark_executors.py` |
| `gpt-5.4-mini` | OpenAI | Fast completions, simple tasks (former harness `small_model`) |
| `gpt-5.4` / `gpt-5.5` | OpenAI | Broad knowledge, explanations |
| `claude-opus-5` / `claude-sonnet-5` | Anthropic | Complex reasoning, architecture, code review |
| `google/gemini-3.5-flash` | Google | Large context analysis |
| `Qwen/Qwen3.7-Max` | Alibaba | Benchmarked in `tools/benchmark_executors.py` |
| `Qwen/Qwen3.6-Plus` | Alibaba | Cheaper Qwen tier |
| `zai-org/GLM-5` / `zai-org/GLM-5.1` | Z.ai | Benchmarked in `tools/benchmark_executors.py` |
| `moonshotai/Kimi-K3` | Moonshot | Long-context code review |
| `MiniMaxAI/MiniMax-M3` | MiniMax | General purpose |
| `deepseek/deepseek-v4.1-flash-fast` | DeepSeek | ~250-300 TPS, 1M context |
| `claude-sonnet-5-5` / `claude-opus-5-5` | Anthropic | Latest Claude flagships, 1M context |
| `z-ai/glm-5.3-flashx` | Z.ai | ~200 TPS, 1M context, multimodal |
| `meta/muse-spark-1.3` | Meta | Max reasoning effort for harder problems |
| `gpt-6-sol` / `gpt-6.1-sol` / `gpt-6-luna` | OpenAI | Latest GPT-6 family, 1.05M context |
| `inclusionai/ling-3.1-flash:free` | InclusionAI | Free, 262K context |
| `xiaomi/mimo-v2.6-pro` / `xiaomi/mimo-v2.6-flash` | Xiaomi | 1M context |
| `xai/grok-4.7` | xAI | 500K context, strong reasoning |
| `Qwen/Qwen3.8-Omni-Flash` | Alibaba | 1M context, multimodal |
| `stepfun/Step-5-Preview` | StepFun | 1M context, preview |

Each model also exposes `context_length` in the `/models` response, so read that
rather than assuming a window size.

### Available Models via DeepSeek Direct

The harness declares a self-contained `deepseek` provider in
`.opencode/opencode.json`, generated from `_DEEPSEEK_MODELS` in
`tools/opencode_engine.py` (base URL `${DEEPSEEK_BASE_URL}`, key
`DEEPSEEK_API_KEY`, both from `.env`). The `.env.template` ships
`https://api.deepseek.com/v1`.

Verified 2026-10-06 against `GET {DEEPSEEK_BASE_URL}/models`: the official API
serves exactly two ids. **`deepseek-v4.1-flash` is NOT on the direct API** — that
model is served by CommandCode and OpenRouter instead.

| Model ID | Best For |
|----------|----------|
| `deepseek-v4-pro` | Flagship, deep reasoning |
| `deepseek-flash` | Fast, cheap |

### Available Models via OpenRouter

The harness declares a self-contained `openrouter` provider (`_OPENROUTER_MODELS`,
base URL `https://openrouter.ai/api/v1`, key `OPENROUTER_API_KEY`). DeepSeek ids
verified against `GET https://openrouter.ai/api/v1/models` (465 models,
2026-10-06); the V4 family reports a 1,048,576-token context. `:batch` and
`~`-prefixed alias ids are excluded.

| Model ID | Best For |
|----------|----------|
| `deepseek/deepseek-v4.1-flash` | The extra route to DeepSeek V4.1 Flash |
| `deepseek/deepseek-v4-pro` | Flagship, deep reasoning |
| `deepseek/deepseek-v4-flash` | Fast, cheap |
| `deepseek/deepseek-v4-flash-vision-exp` | Multimodal (experimental) |

## API Usage Patterns

### Calling DeepSeek API (OpenAI-compatible)

Only usable when `DEEPSEEK_BASE_URL` / `DEEPSEEK_API_KEY` are set — they are not
set in this repo's `.env`.

```python
import os
import httpx

async def call_deepseek(prompt: str, system: str = "", model: str = "deepseek-chat") -> str:
    """Call DeepSeek chat completions API."""
    base_url = os.environ["DEEPSEEK_BASE_URL"]
    api_key = os.environ["DEEPSEEK_API_KEY"]

    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            f"{base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.3,
                "max_tokens": 4096,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]
```

### Calling CommandCode API (OpenAI-compatible proxy)

```python
import os
import httpx

async def call_commandcode(
    prompt: str,
    system: str = "",
    model: str = "deepseek/deepseek-v4-pro",
) -> str:
    """Call CommandCode API — proxies multiple model providers."""
    base_url = os.environ["COMMANDCODE_BASE_URL"]
    api_key = os.environ["COMMANDCODE_API_KEY"]

    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            f"{base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.3,
                "max_tokens": 4096,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]
```

## Copilot Chat Model Switching

When using Copilot Chat in VS Code, switch the active model via:
- **Command Palette** (`Ctrl+Shift+P`) → `GitHub Copilot: Switch Model`
- Or click the model name in the Copilot Chat header

Configured models are defined in `.vscode/settings.json` under `github.copilot.chat.models`.

## When to Use Which Provider

| Scenario | Provider | Model |
|----------|----------|-------|
| **Architecture design** | CommandCode | `claude-opus-5` or `claude-sonnet-5` |
| **Code review** | CommandCode | `claude-sonnet-5` or `gpt-5.5` |
| **Harness default (OpenCode / Kilo orchestrator)** | CommandCode | `deepseek/deepseek-v4-pro` |
| **Refactoring** | CommandCode | `deepseek/deepseek-v4-pro` |
| **Test generation** | CommandCode | `gpt-5.4` |
| **Complex algorithms / math** | CommandCode | `deepseek/deepseek-v4-pro` |
| **Quick edits / completions** | CommandCode | `deepseek/deepseek-v4.1-flash` or `gpt-5.4-mini` |
| **Cost-sensitive batch work** | CommandCode | `deepseek/deepseek-v4.1-flash` |
| **Long-context analysis** | CommandCode | `google/gemini-3.5-flash` or `moonshotai/Kimi-K3` |

## Error Handling

```python
import httpx

async def safe_api_call(fn, *args, **kwargs):
    """Wrapper with retry and error handling."""
    max_retries = 3
    for attempt in range(max_retries):
        try:
            return await fn(*args, **kwargs)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                # Rate limited — exponential backoff
                await asyncio.sleep(2 ** attempt)
                continue
            if e.response.status_code == 401:
                raise RuntimeError("Invalid API key — check environment variables")
            if e.response.status_code >= 500:
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
            raise
        except httpx.TimeoutException:
            if attempt < max_retries - 1:
                continue
            raise RuntimeError("API call timed out after retries")
    raise RuntimeError("API call failed after max retries")
```

## Security Rules

- **Never hardcode API keys** — always use environment variables
- **Never log API responses** that contain generated code or sensitive data
- **Validate response structure** before accessing `choices[0].message.content`
- **Set reasonable timeouts** — 120s for chat completions, 30s for embeddings
- **Rotate keys periodically** — CommandCode keys expire; regenerate via dashboard
