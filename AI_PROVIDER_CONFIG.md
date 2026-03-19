# AI provider configuration (OpenAI vs Anthropic)

Caption and Story generation use a **single abstraction** (`services/ai_provider.py` → `chat_completion()`). The same **system prompt**, **user prompt**, **temperature**, and **max_tokens** are passed to whichever provider is configured. PDF formatting is done in code (`services/caption_pdf.py`) from the AI’s markdown output—no AI-specific config there.

---

## Where it’s configured

| What | Where |
|------|--------|
| Which provider | `config.py`: `AI_PROVIDER` (env `AI_PROVIDER`, default `openai`) |
| OpenAI model | `config.py`: `OPENAI_MODEL` (env `OPENAI_MODEL`, default `gpt-4o-mini`) |
| Anthropic model | `config.py`: `ANTHROPIC_MODEL` (env `ANTHROPIC_MODEL`, default `claude-haiku-4-5-20251001`) |
| API keys | `config.py`: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY` |
| Call site (captions) | `services/caption_generator.py`: `chat_completion(system=..., user=..., temperature=..., max_tokens=...)` |
| Call site (stories) | Same module: `_generate_stories()`, `_generate_stories_aligned()` |
| Unified call | `services/ai_provider.py`: `chat_completion()` → `_openai_completion()` or `_anthropic_completion()` |

---

## Startup validation (Railway / production)

On **every** app load (including Gunicorn on Railway), `app.py` calls `Config.validate_ai_provider_env()`:

- If `AI_PROVIDER` is set to anything other than **`anthropic`** or **`openai`** (case-insensitive), the process **exits** with a clear error — e.g. if an API key was pasted into `AI_PROVIDER`.
- If `AI_PROVIDER` looks like a key (`sk-ant…` or a long `sk-…` string), the error message explains to use **`ANTHROPIC_API_KEY`** / **`OPENAI_API_KEY`** instead.
- In **production** (`Config.is_production()`): **`ANTHROPIC_API_KEY`** is required when using Anthropic; **`OPENAI_API_KEY`** when using OpenAI or when `AI_PROVIDER` is unset (default is OpenAI). If you only use Anthropic, set **`AI_PROVIDER=anthropic`**.

`Config.validate()` (e.g. when running `python app.py`) also runs this check first.

### Optional: `AI_VENDOR` (plain text)

Set **`AI_VENDOR=anthropic`** or **`openai`** in Railway as a **non-secret** variable if you want a second, readable label next to your secrets. If it does not match the effective provider (from `AI_PROVIDER`), the app logs a **WARNING** on startup.

On every boot you also get one line: **`[Config] AI summary: ...`** showing effective provider and whether each API key env is set (never prints key values).

---

## Rules and parameters (same for both providers)

- **Captions (per chunk, 3 chunks total)**  
  - `temperature=0.6`  
  - `max_tokens=6000` (`CaptionGenerator.MAX_TOKENS_PER_CHUNK`)  
  - Retry when a chunk has empty blocks: `temperature=0.5`, same `max_tokens`.

- **Stories (30-day list)**  
  - `temperature=0.7`  
  - `max_tokens=3500`

- **Prompts**  
  - Same `system` and `user` strings for both providers (built in `caption_generator.py`). No provider-specific prompt variants.

So to “apply the same rules and configuration to Anthropic”, the code already does: both paths use the same `chat_completion(..., temperature=..., max_tokens=...)`. The only differences are:

- Which **model** is used (env: `OPENAI_MODEL` vs `ANTHROPIC_MODEL`).
- How the **response** is read (OpenAI: `choices[0].message.content`; Anthropic: `content[0].text` or all text blocks concatenated—see below).

---

## Anthropic-specific behaviour and fixes

- **Response content**  
  Anthropic can return multiple `content` blocks (e.g. text + tool use, or multiple text blocks). The code now concatenates **all text from every block** so nothing is dropped and behaviour matches “one full reply” like OpenAI.

- **Temperature**  
  Anthropic expects 0–1. We use 0.5–0.7, so no change needed.

- **max_tokens**  
  Must be within the model’s limit (e.g. 8192 for Haiku). We use 6000 (captions) and 3500 (stories), so we’re within limits.

- **Model choice**  
  If Haiku is “a little buggy” (e.g. format drift, missing blocks), try a stronger model via env, e.g.  
  `ANTHROPIC_MODEL=claude-sonnet-4-20250514`  
  or your preferred Sonnet/Opus variant. Same prompts and parameters apply; only model capability changes.

---

## Summary

- **Same rules and configuration** for captions and PDF input: one `chat_completion()` with shared prompts, temperature, and max_tokens for both OpenAI and Anthropic.
- **Anthropic** is aligned by: (1) using the same parameters, (2) concatenating all text content blocks in the response.
- **If it’s still buggy**, switch to a more capable Anthropic model (e.g. Sonnet) via `ANTHROPIC_MODEL`; no code change required.
