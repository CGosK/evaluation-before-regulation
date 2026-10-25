"""
LLM provider clients for the pricing agents.

Hackathon standard: all model calls go through the shared endpoint (**Nebius AI Studio** by default; see
the repo-root ``compute.env`` / ``poseidon_compute``). The default model is the thesis model,
``mistralai/Mistral-Large-Instruct-2411``; pass any other model id with ``MODEL_NAME`` / ``--model``.
To run with a model Nebius doesn't serve, use the one entry point ``poseidon-run`` (it hosts it on
Modal or fails loudly). No model is ever substituted.

The thesis's direct Mistral-SDK path (``LLM_PROVIDER=mistral``) and other OpenAI-compatible endpoints are
kept as opt-in alternatives for reproduction or debugging, but participants should not need them.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, List, Optional

from poseidon_compute import make_client, resolve_model, endpoint_kind, base_url

Message = Dict[str, str]


@dataclass
class Preset:
    base_url: str
    key_env: str
    default_model: str
    needs_key: bool = True
    supports_seed: bool = False


# The thesis used Mistral Large 24.11. Nebius (the default endpoint) serves open-weight models by their
# Hugging Face repo id, so the default here is that HF-cased id — the same model the thesis used, and
# ungated on HF so it can also be Modal-hosted if Nebius doesn't serve it. Pass any other model with
# --model / MODEL_NAME.
THESIS_MODEL = "mistralai/Mistral-Large-Instruct-2411"

PRESETS: Dict[str, Preset] = {
    # Opt-in OpenRouter preset (fallback for closed models / models Nebius doesn't serve).
    # The standard path is the shared compute.env config (Nebius default); see the module docstring.
    "openrouter": Preset(
        "https://openrouter.ai/api/v1",
        "OPENROUTER_API_KEY",
        THESIS_MODEL,
        supports_seed=True,
    ),
    # Alternatives (not needed for the hackathon)
    "openai": Preset(
        "https://api.openai.com/v1", "OPENAI_API_KEY", "gpt-4.1-mini", supports_seed=True
    ),
    "google": Preset(
        "https://generativelanguage.googleapis.com/v1beta/openai/",
        "GOOGLE_API_KEY",
        "gemini-2.5-flash",
    ),
    "mistral-compat": Preset(
        "https://api.mistral.ai/v1", "MISTRAL_API_KEY", "mistral-small-latest"
    ),
    "ollama": Preset("http://localhost:11434/v1", "OLLAMA_API_KEY", "llama3.2:3b", needs_key=False),
    # Generic: set LLM_BASE_URL and LLM_API_KEY yourself.
    "openai-compatible": Preset("", "LLM_API_KEY", "", needs_key=False),
}


class FatalProviderError(RuntimeError):
    """Model not found / bad request / bad key: retrying cannot help, abort the run."""


class Provider:
    """Minimal interface every provider implements."""

    name: str = "unknown"
    model_name: str = "unknown"
    #: hosted APIs are rate limited by the Experiment; local servers are not
    is_remote: bool = True

    async def complete(
        self, messages: List[Message], temperature: float, seed: Optional[int]
    ) -> str:
        raise NotImplementedError


class MistralProvider(Provider):
    """Original thesis path: the official Mistral SDK."""

    name = "mistral"

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or os.getenv("MISTRAL_API_KEY")
        if not self.api_key:
            raise ValueError("MISTRAL_API_KEY is not set (LLM_PROVIDER=mistral)")
        self.model_name = model or os.getenv("MODEL_NAME") or "mistral-large-2411"

    async def complete(self, messages, temperature, seed):
        from mistralai import Mistral

        async with Mistral(api_key=self.api_key) as client:
            kwargs = {}
            if seed is not None:
                kwargs["random_seed"] = seed
            response = await client.chat.complete_async(
                model=self.model_name,
                messages=messages,
                temperature=temperature,
                response_format={"type": "json_object"},
                **kwargs,
            )
        return response.choices[0].message.content


class OpenAICompatibleProvider(Provider):
    """OpenAI, Gemini, OpenRouter, Mistral's REST API, Ollama, LM Studio, vLLM..."""

    def __init__(
        self,
        preset: str = "openai",
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        if preset not in PRESETS:
            raise ValueError(f"Unknown provider {preset!r}. Choose from {sorted(PRESETS)}")
        p = PRESETS[preset]
        self.name = preset
        self.base_url = base_url or os.getenv("LLM_BASE_URL") or p.base_url
        if not self.base_url:
            raise ValueError("LLM_BASE_URL must be set for provider 'openai-compatible'")
        # The client authenticates with the key from the shared compute.env (via make_client() /
        # llm_config, Nebius or OpenRouter), which fails loudly if none is set. This field is only a
        # diagnostic hint for the preset; it is not what authenticates the client.
        self.api_key = api_key or os.getenv(p.key_env)  # diagnostics only; real key comes from llm_config
        # Route the explicit --model / MODEL_NAME through resolve_model too (not just the preset
        # default), so the LLM_MODEL override, retired-pin upgrades and OpenRouter id-casing apply to it.
        self.model_name = resolve_model(model or os.getenv("MODEL_NAME") or p.default_model)
        if not self.model_name:
            raise ValueError("MODEL_NAME must be set for provider 'openai-compatible'")
        self.supports_seed = p.supports_seed
        self.is_remote = "localhost" not in self.base_url and "127.0.0.1" not in self.base_url

        # The default 'openrouter' preset routes through the shared compute.env config (Nebius by
        # default). The opt-in presets (openai / google / mistral-compat / ollama / openai-compatible)
        # name a DIFFERENT endpoint, so honor their resolved base_url/key instead of silently rerouting
        # everything to the shared endpoint (which also makes is_remote above load-bearing again).
        if preset == "openrouter":
            self._client = make_client(async_=True)
        else:
            from openai import AsyncOpenAI

            self._client = AsyncOpenAI(base_url=self.base_url, api_key=self.api_key or "EMPTY")
        self._json_mode = True  # drop response_format if the model rejects it

    async def complete(self, messages, temperature, seed):
        kwargs = {}
        if seed is not None and self.supports_seed:
            kwargs["seed"] = seed
        if self._json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        from openai import AuthenticationError, BadRequestError, NotFoundError, PermissionDeniedError

        fatal = (NotFoundError, AuthenticationError, PermissionDeniedError)
        try:
            response = await self._client.chat.completions.create(
                model=self.model_name, messages=messages, temperature=temperature, **kwargs
            )
        except fatal as e:
            raise FatalProviderError(
                f"{self.model_name}: {e}. Check the model id and your NEBIUS_API_KEY in the repo-root "
                f"compute.env. If the model isn't on Nebius, run via `poseidon-run --model "
                f"{self.model_name} -- <cmd>` to host it on Modal (or fail with a clear reason)."
            ) from e
        except BadRequestError as e:
            if self._json_mode and "response_format" in str(e).lower():
                self._json_mode = False  # model does not support JSON mode; rely on the prompt
                kwargs.pop("response_format")
                response = await self._client.chat.completions.create(
                    model=self.model_name, messages=messages, temperature=temperature, **kwargs
                )
            else:
                raise FatalProviderError(f"{self.model_name}: {e}") from e
        if not response.choices:
            raise RuntimeError(f"{self.model_name}: empty response")
        return strip_code_fence(response.choices[0].message.content or "")


# Claude list prices, $ per million tokens (input, output), from the claude-api skill's model table
# (cached 2026-10-06). Output includes thinking tokens, which are billed as output.
CLAUDE_PRICES = {
    "claude-fable-5-1": (10.0, 50.0),
    "claude-opus-5-5": (4.0, 20.0),
    "claude-sonnet-5-5": (2.0, 10.0),
    "claude-haiku-5-5": (0.10, 0.50),
    "claude-haiku-4-5": (1.00, 5.00),
}
# A subscription usage limit pauses a headless call: poll every 5 minutes, for up to 8 hours.
LIMIT_POLL_SECONDS = int(os.getenv("CLAUDE_LIMIT_POLL_SECONDS", "300"))
LIMIT_WAIT_HOURS = float(os.getenv("CLAUDE_LIMIT_WAIT_HOURS", "8"))
# Plan allowance only. With CLAUDE_PAUSE_FILE set, a call that hits a usage limit, or that was paid from usage
# credits (Claude Code reports usage.fallback_credit), pauses every process sharing the file for
# LIMIT_POLL_SECONDS. When a pause ends, one process probes with a single call; the rest wait until it clears.
PAUSE_FILE = os.getenv("CLAUDE_PAUSE_FILE")


def _paused_until() -> Optional[float]:
    import json

    try:
        return json.loads(open(PAUSE_FILE).read())["until"]
    except (FileNotFoundError, ValueError, KeyError):
        return None


async def _pause_gate() -> bool:
    """Wait out a shared pause. True if this call is the one probe allowed when the pause ends."""
    import asyncio
    import time

    if not PAUSE_FILE:
        return False
    while True:
        until = _paused_until()
        if until is None:
            return False
        if time.time() < until:
            await asyncio.sleep(min(60.0, until - time.time() + 1))
            continue
        lock = PAUSE_FILE + ".probe"
        try:
            os.close(os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY))
            return True
        except FileExistsError:
            if time.time() - os.path.getmtime(lock) > 600:  # a probe that died without reporting
                os.unlink(lock)
            await asyncio.sleep(5)


def _pause_report(probe: bool, reason: Optional[str]) -> None:
    """reason set: (re)start the shared pause. Either way a probe releases its lock; a clean probe ends the pause."""
    import json
    import time

    if not PAUSE_FILE:
        return
    if reason:
        with open(PAUSE_FILE, "w") as fh:
            fh.write(json.dumps({"until": time.time() + LIMIT_POLL_SECONDS, "reason": reason[:200]}))
    elif probe and os.path.exists(PAUSE_FILE):
        os.unlink(PAUSE_FILE)
    if probe and os.path.exists(PAUSE_FILE + ".probe"):
        os.unlink(PAUSE_FILE + ".probe")

# Models with no effort setting (manual thinking budgets only). CLAUDE_EFFORT is ignored for them, so a
# value inherited from the shell is neither sent nor logged.
NO_EFFORT = {"claude-haiku-4-5"}


class RefusalError(RuntimeError):
    """The model declined (stop_reason "refusal"). Retried like any failed call, and logged."""


def log_usage(record: dict) -> None:
    """Append one call's usage to the JSONL file named by CLAUDE_USAGE_LOG, if set."""
    path = os.getenv("CLAUDE_USAGE_LOG")
    if path:
        import json

        with open(path, "a") as fh:
            fh.write(json.dumps(record) + "\n")


def check_budget() -> None:
    """Refuse the next call once the CLAUDE_USAGE_LOG total reaches CLAUDE_BUDGET_USD, if both are set.
    Shared by every process writing the same log, so parallel runs share one cap."""
    path, cap = os.getenv("CLAUDE_USAGE_LOG"), os.getenv("CLAUDE_BUDGET_USD")
    if not (path and cap and os.path.exists(path)):
        return
    import json

    with open(path) as fh:
        spent = sum(json.loads(line).get("cost_usd") or 0.0 for line in fh if line.strip())
    if spent >= float(cap):
        raise FatalProviderError(f"spend cap reached: ${spent:.2f} logged in {path} (CLAUDE_BUDGET_USD={cap})")


class AnthropicProvider(Provider):
    """Claude through the Anthropic API (optional extra: ``uv sync --extra claude``).

    The key comes from PRICING_ANTHROPIC_API_KEY, in the environment or the repo-root compute.env, never
    from ANTHROPIC_API_KEY, so it cannot be mistaken for a Claude Code login. No sampling parameters are
    sent (current Claude models accept only their defaults, and the SDK's API version removes them), and no
    server-side fallback is enabled: a refused call stays a refusal instead of silently running on another
    model. The answer is constrained to the agent's JSON schema with structured outputs.
    PRICING_ANTHROPIC_WORKSPACE_ID names the workspace to bill when the key is organisation-level.
    """

    name = "anthropic"
    max_attempts = 3  # each attempt is billed

    def __init__(self, model: str, api_key: Optional[str] = None, effort: Optional[str] = None):
        from anthropic import AsyncAnthropic
        from poseidon_compute import llm_config

        llm_config._load()  # also reads repo-root compute.env, where the key may live
        key = api_key or os.getenv("PRICING_ANTHROPIC_API_KEY")
        if not key:
            raise FatalProviderError(
                "PRICING_ANTHROPIC_API_KEY is not set (export it, or add it to the repo-root compute.env)"
            )
        self.model_name = model
        self.effort = None if model in NO_EFFORT else effort or os.getenv("CLAUDE_EFFORT") or None
        self.schema: Optional[dict] = None  # set by the agent from its response model
        # An organisation-level key must name the workspace to bill (wrkspc_...); a workspace key need not.
        self.workspace = os.getenv("PRICING_ANTHROPIC_WORKSPACE_ID") or None
        # SDK retries cover rate limits and overload, which are not billed; parallel runs hit them.
        # Pre-4.6 models (Claude Haiku 4.5) take a fixed thinking budget instead of an effort level.
        budget = int(os.getenv("CLAUDE_THINKING_BUDGET") or 0)  # 0 or unset: off, the API default here
        self.thinking = {"type": "enabled", "budget_tokens": budget} if budget > 0 else None
        self._client = AsyncAnthropic(api_key=key, max_retries=6)

    async def complete(self, messages, temperature, seed):
        import anthropic

        check_budget()
        system = "\n\n".join(m["content"].strip() for m in messages if m["role"] == "system")
        output_config = {}
        if self.effort:
            output_config["effort"] = self.effort
        if self.schema:
            output_config["format"] = {"type": "json_schema", "schema": self.schema}
        try:
            r = await self._client.messages.create(
                model=self.model_name,
                max_tokens=16000,
                system=system,
                messages=[m for m in messages if m["role"] != "system"],
                **({"output_config": output_config} if output_config else {}),
                **({"workspace_id": self.workspace} if self.workspace else {}),
                **({"thinking": self.thinking} if self.thinking else {}),
            )
        except (anthropic.AuthenticationError, anthropic.PermissionDeniedError,
                anthropic.NotFoundError, anthropic.BadRequestError) as e:
            hint = ("; set PRICING_ANTHROPIC_WORKSPACE_ID in compute.env to the workspace's wrkspc_ id"
                    if "workspace" in str(e) else "")
            raise FatalProviderError(f"{self.model_name}: {e}{hint}") from e
        price_in, price_out = CLAUDE_PRICES.get(self.model_name, (float("nan"), float("nan")))
        details = r.usage.output_tokens_details
        log_usage({
            "model": self.model_name, "effort": self.effort, "thinking": self.thinking, "stop_reason": r.stop_reason,
            "input_tokens": r.usage.input_tokens, "output_tokens": r.usage.output_tokens,
            "output_tokens_details": details.to_dict() if details else None,
            "cost_usd": (r.usage.input_tokens * price_in + r.usage.output_tokens * price_out) / 1e6,
            "request_id": r._request_id,
        })
        if r.stop_reason == "refusal":
            category = r.stop_details.category if r.stop_details else None
            raise RefusalError(f"{self.model_name} declined (category {category})")
        if r.stop_reason == "max_tokens":
            raise RuntimeError(f"{self.model_name}: hit max_tokens before answering")
        return strip_code_fence(next((b.text for b in r.content if b.type == "text"), ""))


class ClaudeCodeProvider(Provider):
    """Claude through a headless Claude Code call (``claude -p``), billed to the Claude login that runs it
    (in a cloud session, the account's cloud usage) instead of an API key.

    The default system prompt is replaced with the agent's own, every tool and command is removed, and no
    settings, MCP servers or session history are loaded, so the call is as close to a plain Messages request
    as Claude Code allows. Claude Code still adds its structured-output step, so results are comparable
    with other runs on this path, not with AnthropicProvider runs. Opt-in: LLM_PROVIDER=claude-code.
    """

    name = "claude-code"
    max_attempts = 3  # each attempt is billed

    def __init__(self, model: str, effort: Optional[str] = None):
        import tempfile

        self.model_name = model
        self.effort = None if model in NO_EFFORT else effort or os.getenv("CLAUDE_EFFORT") or None
        self.schema: Optional[dict] = None  # set by the agent from its response model
        self.binary = os.getenv("CLAUDE_BIN", "claude")
        self._cwd = tempfile.mkdtemp(prefix="pricing-agent-")  # empty: no CLAUDE.md or project settings
        # The child must use the Claude login, never an API key, and must not think it is nested.
        # Every prompt is new, so caching would only add cache-write charges (2x input on the 1h TTL).
        self._env = {k: v for k, v in os.environ.items()
                     if k not in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "CLAUDECODE")}
        self._env["DISABLE_PROMPT_CACHING"] = "1"
        # Claude Code turns thinking on by default; CLAUDE_THINKING_BUDGET=0 switches it off, N > 0 sets it on
        # with an N-token budget, unset leaves Claude Code's default.
        budget = os.getenv("CLAUDE_THINKING_BUDGET")
        self.thinking = None if budget is None else int(budget)
        if self.thinking:
            self._env["MAX_THINKING_TOKENS"] = str(self.thinking)

    async def complete(self, messages, temperature, seed):
        import asyncio
        import json
        import tempfile

        system = "\n\n".join(m["content"].strip() for m in messages if m["role"] == "system")
        prompt = "\n\n".join(m["content"] for m in messages if m["role"] != "system")
        with tempfile.NamedTemporaryFile("w", suffix=".txt", dir=self._cwd, delete=False) as fh:
            fh.write(system)
        args = [self.binary, "-p", "--model", self.model_name, "--system-prompt-file", fh.name,
                "--tools", "", "--disable-slash-commands", "--strict-mcp-config", "--setting-sources", "",
                "--no-session-persistence", "--output-format", "json", "--max-turns", "3"]
        if self.effort:
            args += ["--effort", self.effort]
        if self.thinking is not None:
            args += ["--settings", json.dumps({"alwaysThinkingEnabled": self.thinking > 0})]
        if self.schema:
            args += ["--json-schema", json.dumps(self.schema)]
        waited = 0
        while True:
            probe = await _pause_gate()
            proc = await asyncio.create_subprocess_exec(
                *args, cwd=self._cwd, env=self._env, stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            out, err = await proc.communicate(prompt.encode())
            try:
                data = json.loads(out)
            except json.JSONDecodeError as e:
                os.unlink(fh.name)
                raise FatalProviderError(
                    f"claude -p failed ({proc.returncode}): {err.decode()[:500] or out[:500]!r}") from e
            # A usage limit ("You've hit your session limit · resets 10pm") pauses the call, not the game:
            # wait and ask again, for up to LIMIT_WAIT_HOURS, without spending one of the agent's attempts.
            limited = data.get("is_error") and "hit your" in str(data.get("result")) and "limit" in str(data.get("result"))
            credit = (data.get("usage") or {}).get("fallback_credit")
            _pause_report(probe, str(data.get("result")) if limited else f"usage credits used: {credit}" if credit else None)
            if not limited or waited >= LIMIT_WAIT_HOURS * 3600:
                break  # a call paid from credits still returns its answer; the pause stops the next ones
            log_usage({"model": self.model_name, "via": "claude-code", "limit_wait": True,
                       "config_dir": self._env.get("CLAUDE_CONFIG_DIR", "default"),
                       "result": str(data.get("result"))[:200]})
            if not PAUSE_FILE:
                await asyncio.sleep(LIMIT_POLL_SECONDS)
            waited += LIMIT_POLL_SECONDS
        os.unlink(fh.name)
        usage = data.get("usage") or {}
        log_usage({
            "model": self.model_name, "effort": self.effort, "via": "claude-code",
            # which login paid: unset means ~/.claude.json, the machine's default account
            "config_dir": self._env.get("CLAUDE_CONFIG_DIR", "default"),
            "credit_fallback": (data.get("usage") or {}).get("fallback_credit"),
            "stop_reason": data.get("subtype"), "is_error": data.get("is_error"),
            "input_tokens": sum(usage.get(k, 0) or 0 for k in
                                ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")),
            "output_tokens": usage.get("output_tokens", 0), "cost_usd": data.get("total_cost_usd") or 0.0,
            "thinking_tokens": (usage.get("output_tokens_details") or {}).get("thinking_tokens"),
            "thinking": self.thinking,
            "num_turns": data.get("num_turns"), "session_id": data.get("session_id"),
        })
        if data.get("is_error") or data.get("structured_output") is None:
            raise RefusalError(f"{self.model_name}: no structured output ({data.get('subtype')}): "
                               f"{str(data.get('result'))[:300]}")
        return json.dumps(data["structured_output"])


class StubProvider(Provider):
    """Offline stand-in that answers in the agent's JSON schema with random prices near its last one,
    so the whole pipeline can run before any paid call. Opt-in: LLM_PROVIDER=stub or --provider stub."""

    name = "stub"
    is_remote = False

    def __init__(self, model: Optional[str] = None):
        import random

        self.model_name = model or "stub"
        self.schema: Optional[dict] = None
        self._rng = random.Random(0)

    async def complete(self, messages, temperature, seed):
        import json
        import re

        prompt = messages[-1]["content"]
        last = re.search(r"My price: ([0-9.]+)", prompt)
        price = float(last.group(1)) if last else self._rng.uniform(1.5, 2.5)
        price = round(max(1.0, price * self._rng.uniform(0.97, 1.03)), 2)
        log_usage({"model": self.model_name, "stop_reason": "end_turn", "input_tokens": len(prompt) // 4,
                   "output_tokens": 60, "cost_usd": float(os.getenv("STUB_COST_USD", "0"))})
        return json.dumps({"observations": "stub", "plans": "stub plan", "insights": "stub insight",
                           "chosen_price": price})


def strip_code_fence(text: str) -> str:
    """Remove <think>...</think> blocks (reasoning models) and ```json fences around the answer."""
    if "</think>" in text:
        text = text.rsplit("</think>", 1)[1]
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`").strip()
        if text.lower().startswith("json"):
            text = text[4:].strip()
    return text


def make_provider(
    kind: Optional[str] = None, model: Optional[str] = None, api_key: Optional[str] = None
) -> Provider:
    """Build a provider from ``kind`` (or the ``LLM_PROVIDER`` env var, default openrouter).
    A ``claude-*`` model id selects the Anthropic API unless a kind is given."""
    model = model or os.getenv("MODEL_NAME")
    default = "anthropic" if model and model.startswith("claude-") else "openrouter"
    kind = (kind or os.getenv("LLM_PROVIDER", default)).lower()
    if kind == "mistral":
        return MistralProvider(api_key=api_key, model=model)
    if kind == "anthropic":
        return AnthropicProvider(model=model, api_key=api_key)
    if kind == "claude-code":
        return ClaudeCodeProvider(model=model)
    if kind == "stub":
        return StubProvider(model=model)
    return OpenAICompatibleProvider(preset=kind, model=model, api_key=api_key)


def resolve_effective_model(model: Optional[str] = None) -> str:
    """The model id a run will actually use, via the same path as ``make_provider``.

    Mirrors ``OpenAICompatibleProvider.__init__``: an explicit ``--model`` / ``MODEL_NAME``
    wins over the thesis default, and whichever id is chosen is passed through ``resolve_model``
    so ``LLM_MODEL`` overrides, retired-pin upgrades and OpenRouter id-translation are reflected.
    This keeps the pre-run cost banner honest about the resolved model (no silent swap).
    """
    model = model or os.getenv("MODEL_NAME") or THESIS_MODEL
    if model.startswith("claude-") or os.getenv("LLM_PROVIDER") == "stub":
        return model  # Anthropic API / stub: no shared-config routing or id translation
    return resolve_model(model)


def estimate_cost_note(n_calls: int, model: Optional[str] = None) -> str:
    model = resolve_effective_model(model)
    if model in CLAUDE_PRICES:
        price_in, price_out = CLAUDE_PRICES[model]
        return (f"≈ {n_calls:,} model calls with {model} via the Anthropic API "
                f"(${price_in}/${price_out} per M input/output tokens; thinking bills as output).")
    if not model.startswith("claude-") and os.getenv("LLM_PROVIDER") == "stub":
        return f"≈ {n_calls:,} stub calls (offline, free)."
    # Show the rates page for the endpoint the call will ACTUALLY use (Nebius, or OpenRouter when
    # that's the configured key), not a hardcoded provider — otherwise the banner misleads OpenRouter users.
    kind = endpoint_kind()
    if kind == "openrouter":
        rates = f"https://openrouter.ai/{model}"
    elif kind == "nebius":
        rates = "Nebius AI Studio (https://studio.nebius.com)"
    else:  # custom endpoint (e.g. a Modal-hosted model)
        rates = base_url()
    return f"≈ {n_calls:,} model calls with {model}. Per-token rates: {rates}."
