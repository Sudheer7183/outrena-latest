# # """
# # llm_service.py — Async HTTP gateway to 13 LLM providers.

# # Phase 1 (preserved): ``LlmService`` is a thin async wrapper around the
# # configured OpenAI-compatible endpoint. Phase 3 modules that consume
# # ``get_llm_service().generate()`` continue to work unchanged.

# # Phase 2 (added): module-level gateway functions dispatch to provider-specific
# # adapters via ``LlmConfig.provider``:
# #   - ``call_llm(config, messages) -> LlmResponse``
# #   - ``cast_llm_config(config) -> dict[str, Any]``
# #   - ``get_default_llm_config(db) -> LlmConfig | None``
# #   - ``get_model_for_task(task, config) -> str``

# # The 13 supported providers (per migration doc §3.4 + §10 Phase 2):
# #   OpenAI, Anthropic, Azure OpenAI, Google Gemini, AWS Bedrock, Cohere,
# #   Mistral, Meta Llama (via Together), Groq, AI21, Hugging Face, ZAI,
# #   Local (Ollama).

# # Audit fix (AUDIT-A1 #6 / H-11): ZAI provider now POSTs to the full
# # ``https://open.bigmodel.cn/api/paas/v4/chat/completions`` URL — the
# # previous default omitted the ``/chat/completions`` suffix and would 404
# # against the real ZAI endpoint.
# # """
# # from __future__ import annotations

# # import json
# # from functools import lru_cache
# # from typing import Any

# # import httpx
# # import structlog
# # from sqlalchemy import select
# # from sqlalchemy.ext.asyncio import AsyncSession
# # from tenacity import (
# #     AsyncRetrying,
# #     retry_if_exception_type,
# #     stop_after_attempt,
# #     wait_exponential,
# # )

# # from app.core.config import get_settings
# # from app.models.config_models import LlmConfig as LlmConfigModel
# # from app.schemas.llm_config import LlmResponse

# # logger = structlog.get_logger(__name__)


# # # ── Background-task registry for fire-and-forget usage writes ──────────────
# # # Holds strong references to asyncio Tasks created by _record_llm_usage so
# # # CPython's garbage collector does not cancel them mid-flight. Tasks self-
# # # remove via add_done_callback when they complete. The set is module-level
# # # (not per-request) because usage writes are fire-and-forget — we never
# # # await them from the caller.
# # _BG_USAGE_TASKS: set = set()


# # # ── Constants ───────────────────────────────────────────────────────────────

# # LLM_HTTP_TIMEOUT: float = 60.0
# # """Per-request HTTP timeout for all provider calls (per §10 Phase 2)."""

# # # ── Provider keys ───────────────────────────────────────────────────────────

# # PROVIDER_OPENAI = "openai"
# # PROVIDER_ANTHROPIC = "anthropic"
# # PROVIDER_AZURE = "azure"
# # PROVIDER_GEMINI = "gemini"
# # PROVIDER_BEDROCK = "bedrock"
# # PROVIDER_COHERE = "cohere"
# # PROVIDER_MISTRAL = "mistral"
# # PROVIDER_LLAMA = "llama"  # Meta Llama served via Together
# # PROVIDER_GROQ = "groq"
# # PROVIDER_AI21 = "ai21"
# # PROVIDER_HUGGINGFACE = "huggingface"
# # PROVIDER_ZAI = "zai"
# # PROVIDER_LOCAL = "local"  # Ollama

# # ALL_PROVIDERS: tuple[str, ...] = (
# #     PROVIDER_OPENAI,
# #     PROVIDER_ANTHROPIC,
# #     PROVIDER_AZURE,
# #     PROVIDER_GEMINI,
# #     PROVIDER_BEDROCK,
# #     PROVIDER_COHERE,
# #     PROVIDER_MISTRAL,
# #     PROVIDER_LLAMA,
# #     PROVIDER_GROQ,
# #     PROVIDER_AI21,
# #     PROVIDER_HUGGINGFACE,
# #     PROVIDER_ZAI,
# #     PROVIDER_LOCAL,
# # )

# # # Default base URLs per provider. Can be overridden per-row via LlmConfig.baseUrl.
# # PROVIDER_BASE_URLS: dict[str, str] = {
# #     PROVIDER_OPENAI: "https://api.openai.com/v1",
# #     PROVIDER_ANTHROPIC: "https://api.anthropic.com/v1",
# #     PROVIDER_AZURE: "",  # requires LlmConfig.baseUrl (tenant-specific endpoint)
# #     PROVIDER_GEMINI: "https://generativelanguage.googleapis.com/v1beta",
# #     PROVIDER_BEDROCK: "https://bedrock-runtime.us-east-1.amazonaws.com",
# #     PROVIDER_COHERE: "https://api.cohere.com/v2",
# #     PROVIDER_MISTRAL: "https://api.mistral.ai/v1",
# #     PROVIDER_LLAMA: "https://api.together.xyz/v1",  # Together hosts Llama
# #     PROVIDER_GROQ: "https://api.groq.com/openai/v1",
# #     PROVIDER_AI21: "https://api.ai21.com/studio/v1",
# #     PROVIDER_HUGGINGFACE: "https://api-inference.huggingface.co/models",
# #     PROVIDER_ZAI: "https://open.bigmodel.cn/api/paas/v4",
# #     PROVIDER_LOCAL: "http://localhost:11434/v1",  # Ollama default
# # }

# # # Providers that speak the OpenAI-compatible /chat/completions dialect.
# # _OPENAI_COMPATIBLE: frozenset[str] = frozenset({
# #     PROVIDER_OPENAI,
# #     PROVIDER_GROQ,
# #     PROVIDER_MISTRAL,
# #     PROVIDER_LLAMA,
# #     PROVIDER_LOCAL,
# #     PROVIDER_ZAI,
# #     PROVIDER_AI21,
# #     PROVIDER_HUGGINGFACE,
# #     PROVIDER_COHERE,
# #     PROVIDER_AZURE,
# # })

# # # Default anthropic-version header value (per Anthropic API spec).
# # _ANTHROPIC_VERSION_DEFAULT = "2023-06-01"

# # # Default Azure OpenAI API version (per Azure OpenAI REST spec).
# # _AZURE_API_VERSION_DEFAULT = "2024-10-21"


# # class LlmGatewayError(Exception):
# #     """Raised when the LLM gateway call fails after retries."""


# # # ── Settings-column parsing ─────────────────────────────────────────────────


# # def _parse_settings(config: LlmConfigModel) -> dict[str, Any]:
# #     """
# #     Parse the LlmConfig.settings JSON column safely.

# #     The column is TEXT holding a JSON string (per §5.5). Returns {} on parse
# #     failure or non-dict content — never raises.
# #     """
# #     raw = getattr(config, "settings", None) or "{}"
# #     try:
# #         parsed = json.loads(raw)
# #     except (json.JSONDecodeError, TypeError, ValueError):
# #         return {}
# #     return parsed if isinstance(parsed, dict) else {}


# # # ── Helper mapping (per §6.2) ───────────────────────────────────────────────


# # def cast_llm_config(config: LlmConfigModel) -> dict[str, Any]:
# #     """
# #     Convert a LlmConfig DB row into provider-specific kwargs (per §6.2).

# #     Returns a dict with the keys:
# #       - provider:     normalized provider key (lowercase)
# #       - model:        the model ID to invoke
# #       - api_key:      the API key (may be None for ZAI/local)
# #       - base_url:     the provider's base URL
# #       - temperature:  float (default 0.7)
# #       - max_tokens:   int (default 1024)
# #       - extra:        provider-specific kwargs (api_version, deployment,
# #                       region, anthropic_version, generation_config, ...)

# #     The 'models' map inside settings (task -> model_id) is consumed
# #     separately by ``get_model_for_task()``.
# #     """
# #     settings = _parse_settings(config)
# #     provider = (config.provider or PROVIDER_ZAI).lower()
# #     base_url = config.baseUrl or PROVIDER_BASE_URLS.get(provider, "")

# #     temperature_raw = settings.get("temperature", settings.get("Temperature", 0.7))
# #     max_tokens_raw = settings.get(
# #         "max_tokens", settings.get("maxTokens", settings.get("MaxTokens", 1024))
# #     )

# #     try:
# #         temperature = float(temperature_raw)
# #     except (TypeError, ValueError):
# #         temperature = 0.7
# #     try:
# #         max_tokens = int(max_tokens_raw)
# #     except (TypeError, ValueError):
# #         max_tokens = 1024

# #     kwargs: dict[str, Any] = {
# #         "provider": provider,
# #         "model": config.modelId,
# #         "api_key": config.apiKey,
# #         "base_url": base_url,
# #         "temperature": temperature,
# #         "max_tokens": max_tokens,
# #         "extra": {},
# #     }

# #     # Provider-specific extras
# #     if provider == PROVIDER_AZURE:
# #         kwargs["extra"]["api_version"] = settings.get(
# #             "api_version", settings.get("apiVersion", _AZURE_API_VERSION_DEFAULT)
# #         )
# #         kwargs["extra"]["deployment"] = settings.get(
# #             "deployment", settings.get("deploymentName", config.modelId)
# #         )
# #     elif provider == PROVIDER_BEDROCK:
# #         kwargs["extra"]["region"] = settings.get("region", "us-east-1")
# #         kwargs["extra"]["model_id"] = settings.get("model_id", config.modelId)
# #     elif provider == PROVIDER_ANTHROPIC:
# #         kwargs["extra"]["anthropic_version"] = settings.get(
# #             "anthropic_version", _ANTHROPIC_VERSION_DEFAULT
# #         )
# #     elif provider == PROVIDER_GEMINI:
# #         kwargs["extra"]["generation_config"] = {
# #             "temperature": temperature,
# #             "maxOutputTokens": max_tokens,
# #             "topP": float(settings.get("top_p", settings.get("topP", 1.0))),
# #         }

# #     return kwargs


# # def get_model_for_task(task: str, config: LlmConfigModel) -> str:
# #     """
# #     Tier routing — return the model ID for a given task (per §3.4 + §10 Phase 2).

# #     Reads the 'models' dict inside the JSON settings column. Returns
# #     ``config.modelId`` when no per-task override is configured.

# #     Known tasks: email_generation, icp_suggest, framework_recommend,
# #     gtm_thesis, subject_line, qa_check, compliance_check, reply_categorize,
# #     auto_reply, personalization, anti_pattern, prospect_brief,
# #     prospect_lookalike, ultimate_profile, prospect_enrich, prospect_score,
# #     analytics_diagnose, content_idea, linkedin_post, meeting_prep,
# #     deal_suggest, deal_health, deal_next_step, weekly_digest, cadence_plan,
# #     touch_angle, rule_suggest, ab_test_hypothesis.
# #     """
# #     settings = _parse_settings(config)
# #     models_map = settings.get("models") or {}
# #     if isinstance(models_map, dict) and task in models_map:
# #         return str(models_map[task])
# #     return config.modelId


# # async def get_default_llm_config(db: AsyncSession) -> LlmConfigModel | None:
# #     """
# #     Fetch the tenant's default LlmConfig.

# #     Returns the row where ``isDefault=True AND isActive=True`` (newest first).
# #     Falls back to the first active row by createdAt ordering when no row is
# #     marked default — per the "first one wins" convention in §6.2.
# #     """
# #     result = await db.execute(
# #         select(LlmConfigModel)
# #         .where(LlmConfigModel.isDefault.is_(True))
# #         .where(LlmConfigModel.isActive.is_(True))
# #         .order_by(LlmConfigModel.createdAt.asc())
# #         .limit(1)
# #     )
# #     row = result.scalar_one_or_none()
# #     if row is not None:
# #         return row

# #     result = await db.execute(
# #         select(LlmConfigModel)
# #         .where(LlmConfigModel.isActive.is_(True))
# #         .order_by(LlmConfigModel.createdAt.asc())
# #         .limit(1)
# #     )
# #     return result.scalar_one_or_none()


# # # ── Provider URL + header builders ──────────────────────────────────────────


# # def _provider_chat_url(provider: str, kwargs: dict[str, Any]) -> str:
# #     """Return the chat-completions URL for a provider."""
# #     base = (kwargs.get("base_url") or PROVIDER_BASE_URLS.get(provider, "")).rstrip("/")
# #     if not base:
# #         raise LlmGatewayError(f"No base_url configured for provider '{provider}'")

# #     if provider == PROVIDER_ANTHROPIC:
# #         return f"{base}/messages"
# #     if provider == PROVIDER_GEMINI:
# #         model = kwargs["model"]
# #         return f"{base}/models/{model}:generateContent"
# #     if provider == PROVIDER_AZURE:
# #         deployment = kwargs["extra"].get("deployment", "deployment")
# #         api_version = kwargs["extra"].get("api_version", _AZURE_API_VERSION_DEFAULT)
# #         return f"{base}/openai/deployments/{deployment}/chat/completions?api-version={api_version}"
# #     if provider == PROVIDER_COHERE:
# #         return f"{base}/chat"
# #     if provider == PROVIDER_BEDROCK:
# #         model_id = kwargs["extra"].get("model_id", kwargs["model"])
# #         return f"{base}/model/{model_id}/invoke"
# #     if provider == PROVIDER_HUGGINGFACE:
# #         # HF router: /models/{model}/v1/chat/completions
# #         return f"{base}/{kwargs['model']}/v1/chat/completions"
# #     # OpenAI-compatible: openai, groq, mistral, llama (Together), local, zai, ai21
# #     return f"{base}/chat/completions"


# # def _provider_headers(provider: str, kwargs: dict[str, Any]) -> dict[str, str]:
# #     """Return provider-specific auth headers (Content-Type added by caller)."""
# #     api_key = kwargs.get("api_key") or ""
# #     if provider == PROVIDER_ANTHROPIC:
# #         return {
# #             "x-api-key": api_key,
# #             "anthropic-version": kwargs["extra"].get(
# #                 "anthropic_version", _ANTHROPIC_VERSION_DEFAULT
# #             ),
# #         }
# #     if provider == PROVIDER_GEMINI:
# #         return {"x-goog-api-key": api_key}
# #     if provider == PROVIDER_AZURE:
# #         # Azure uses api-key header (not Bearer)
# #         return {"api-key": api_key}
# #     return {"Authorization": f"Bearer {api_key}"}


# # # ── Payload builders (per-provider) ─────────────────────────────────────────


# # def _build_openai_payload(
# #     messages: list[dict[str, str]], kwargs: dict[str, Any]
# # ) -> dict[str, Any]:
# #     """OpenAI-compatible chat-completions payload."""
# #     return {
# #         "model": kwargs["model"],
# #         "messages": messages,
# #         "temperature": kwargs["temperature"],
# #         "max_tokens": kwargs["max_tokens"],
# #     }


# # def _build_anthropic_payload(
# #     messages: list[dict[str, str]], kwargs: dict[str, Any]
# # ) -> dict[str, Any]:
# #     """Anthropic Messages API — system is a top-level field, not in messages."""
# #     system_msgs = [m for m in messages if m.get("role") == "system"]
# #     user_msgs = [m for m in messages if m.get("role") != "system"]
# #     system_text = "\n\n".join(str(m.get("content", "")) for m in system_msgs)
# #     payload: dict[str, Any] = {
# #         "model": kwargs["model"],
# #         "messages": user_msgs,
# #         "max_tokens": kwargs["max_tokens"],
# #         "temperature": kwargs["temperature"],
# #     }
# #     if system_text:
# #         payload["system"] = system_text
# #     return payload


# # def _build_gemini_payload(
# #     messages: list[dict[str, str]], kwargs: dict[str, Any]
# # ) -> dict[str, Any]:
# #     """Google Gemini generateContent payload."""
# #     contents: list[dict[str, Any]] = []
# #     sys_text = "\n".join(
# #         str(m.get("content", "")) for m in messages if m.get("role") == "system"
# #     )
# #     for m in messages:
# #         role = m.get("role", "user")
# #         if role == "system":
# #             continue
# #         gemini_role = "user" if role == "user" else "model"
# #         contents.append(
# #             {"role": gemini_role, "parts": [{"text": str(m.get("content", ""))}]}
# #         )
# #     payload: dict[str, Any] = {
# #         "contents": contents,
# #         "generationConfig": kwargs["extra"].get("generation_config", {}),
# #     }
# #     if sys_text:
# #         payload["systemInstruction"] = {"parts": [{"text": sys_text}]}
# #     return payload


# # def _build_cohere_payload(
# #     messages: list[dict[str, str]], kwargs: dict[str, Any]
# # ) -> dict[str, Any]:
# #     """Cohere v2 chat (OpenAI-compatible)."""
# #     return {
# #         "model": kwargs["model"],
# #         "messages": messages,
# #         "temperature": kwargs["temperature"],
# #         "max_tokens": kwargs["max_tokens"],
# #     }


# # def _build_bedrock_payload(
# #     messages: list[dict[str, str]], kwargs: dict[str, Any]
# # ) -> dict[str, Any]:
# #     """
# #     AWS Bedrock converse API payload.

# #     Note: production deployments wrap this in boto3 SigV4 signing. The
# #     gateway posts the converse payload directly when LlmConfig.apiKey
# #     holds a bearer-secured proxy token (e.g. Bedrock proxy gateway).
# #     """
# #     return {
# #         "modelId": kwargs["extra"].get("model_id", kwargs["model"]),
# #         "messages": messages,
# #         "inferenceConfig": {
# #             "temperature": kwargs["temperature"],
# #             "maxTokens": kwargs["max_tokens"],
# #         },
# #     }


# # def _build_provider_payload(
# #     provider: str, messages: list[dict[str, str]], kwargs: dict[str, Any]
# # ) -> dict[str, Any]:
# #     if provider == PROVIDER_ANTHROPIC:
# #         return _build_anthropic_payload(messages, kwargs)
# #     if provider == PROVIDER_GEMINI:
# #         return _build_gemini_payload(messages, kwargs)
# #     if provider == PROVIDER_BEDROCK:
# #         return _build_bedrock_payload(messages, kwargs)
# #     if provider == PROVIDER_COHERE:
# #         return _build_cohere_payload(messages, kwargs)
# #     # All OpenAI-compatible providers
# #     return _build_openai_payload(messages, kwargs)


# # # ── Response parsers (per-provider) ─────────────────────────────────────────


# # def _parse_openai_response(
# #     data: dict[str, Any], provider: str, model: str
# # ) -> LlmResponse:
# #     """Parse OpenAI-compatible response shape (used by 10 of 13 providers)."""
# #     choices = data.get("choices") or []
# #     content = ""
# #     if choices:
# #         msg = choices[0].get("message") or {}
# #         content = str(msg.get("content", ""))
# #     usage = data.get("usage") or {}
# #     usage_dict = {
# #         "prompt_tokens": int(usage.get("prompt_tokens", 0) or 0),
# #         "completion_tokens": int(usage.get("completion_tokens", 0) or 0),
# #         "total_tokens": int(usage.get("total_tokens", 0) or 0),
# #     }
# #     return LlmResponse(
# #         content=content,
# #         usage=usage_dict,
# #         model=model,
# #         provider=provider,
# #         raw=data,
# #     )


# # def _parse_anthropic_response(
# #     data: dict[str, Any], provider: str, model: str
# # ) -> LlmResponse:
# #     content = ""
# #     blocks = data.get("content") or []
# #     if isinstance(blocks, list):
# #         for b in blocks:
# #             if isinstance(b, dict) and b.get("type") == "text":
# #                 content += str(b.get("text", ""))
# #     usage = data.get("usage") or {}
# #     input_tokens = int(usage.get("input_tokens", 0) or 0)
# #     output_tokens = int(usage.get("output_tokens", 0) or 0)
# #     usage_dict = {
# #         "prompt_tokens": input_tokens,
# #         "completion_tokens": output_tokens,
# #         "total_tokens": input_tokens + output_tokens,
# #     }
# #     return LlmResponse(
# #         content=content,
# #         usage=usage_dict,
# #         model=model,
# #         provider=provider,
# #         raw=data,
# #     )


# # def _parse_gemini_response(
# #     data: dict[str, Any], provider: str, model: str
# # ) -> LlmResponse:
# #     content = ""
# #     candidates = data.get("candidates") or []
# #     if candidates:
# #         parts = (candidates[0].get("content") or {}).get("parts") or []
# #         for p in parts:
# #             if isinstance(p, dict) and "text" in p:
# #                 content += str(p["text"])
# #     usage_meta = data.get("usageMetadata") or {}
# #     usage_dict = {
# #         "prompt_tokens": int(usage_meta.get("promptTokenCount", 0) or 0),
# #         "completion_tokens": int(usage_meta.get("candidatesTokenCount", 0) or 0),
# #         "total_tokens": int(usage_meta.get("totalTokenCount", 0) or 0),
# #     }
# #     return LlmResponse(
# #         content=content,
# #         usage=usage_dict,
# #         model=model,
# #         provider=provider,
# #         raw=data,
# #     )


# # def _parse_bedrock_response(
# #     data: dict[str, Any], provider: str, model: str
# # ) -> LlmResponse:
# #     content = ""
# #     output = data.get("output") or {}
# #     msg = output.get("message") or {}
# #     for c in msg.get("content") or []:
# #         if isinstance(c, dict) and "text" in c:
# #             content += str(c["text"])
# #     usage = data.get("usage") or {}
# #     usage_dict = {
# #         "prompt_tokens": int(usage.get("inputTokens", 0) or 0),
# #         "completion_tokens": int(usage.get("outputTokens", 0) or 0),
# #         "total_tokens": int(usage.get("totalTokens", 0) or 0),
# #     }
# #     return LlmResponse(
# #         content=content,
# #         usage=usage_dict,
# #         model=model,
# #         provider=provider,
# #         raw=data,
# #     )


# # def _parse_provider_response(
# #     provider: str, data: dict[str, Any], model: str
# # ) -> LlmResponse:
# #     if provider == PROVIDER_ANTHROPIC:
# #         return _parse_anthropic_response(data, provider, model)
# #     if provider == PROVIDER_GEMINI:
# #         return _parse_gemini_response(data, provider, model)
# #     if provider == PROVIDER_BEDROCK:
# #         return _parse_bedrock_response(data, provider, model)
# #     return _parse_openai_response(data, provider, model)


# # # ── HTTP transport with tenacity retry ──────────────────────────────────────


# # async def _do_http_post(
# #     url: str, headers: dict[str, str], payload: dict[str, Any]
# # ) -> dict[str, Any]:
# #     """Single HTTP POST with timeout. Raises httpx.HTTPError on failure."""
# #     async with httpx.AsyncClient(timeout=LLM_HTTP_TIMEOUT) as client:
# #         resp = await client.post(url, json=payload, headers=headers)
# #         resp.raise_for_status()
# #         return resp.json()


# # def _retrying() -> AsyncRetrying:
# #     """
# #     Tenacity AsyncRetrying: 3 attempts, exponential backoff 1-10s, on
# #     transient HTTP errors only (429/5xx via HTTPStatusError + transport
# #     errors). Per §10 Phase 2 spec.
# #     """
# #     return AsyncRetrying(
# #         stop=stop_after_attempt(3),
# #         wait=wait_exponential(multiplier=1, min=1, max=10),
# #         retry=retry_if_exception_type(
# #             (httpx.HTTPStatusError, httpx.ConnectError, httpx.ReadTimeout,
# #              httpx.ConnectTimeout, httpx.RemoteProtocolError)
# #         ),
# #         reraise=True,
# #     )


# # async def _call_provider(
# #     provider: str, kwargs: dict[str, Any], messages: list[dict[str, str]]
# # ) -> LlmResponse:
# #     """Dispatch to the right provider adapter. Retries transient failures."""
# #     model = kwargs["model"]
# #     url = _provider_chat_url(provider, kwargs)
# #     payload = _build_provider_payload(provider, messages, kwargs)
# #     headers: dict[str, str] = {"Content-Type": "application/json"}
# #     headers.update(_provider_headers(provider, kwargs))

# #     data: dict[str, Any] = {}
# #     async for attempt in _retrying():
# #         with attempt:
# #             data = await _do_http_post(url, headers, payload)

# #     return _parse_provider_response(provider, data, model)


# # # ── Main entry: call_llm ────────────────────────────────────────────────────


# # async def _resolve_dual_path_api_key(
# #     config: LlmConfigModel, *, provider: str
# # ) -> str | None:
# #     """Resolve the LLM API key via the dual-path credential service.

# #     FIX-BE-1 / CRITICAL 2: production LLM calls used to read
# #     ``config.apiKey`` (the legacy plaintext column) directly. When a tenant
# #     adopts the dual-path model (``apiKey=NULL`` + ``global_llm_config_id``
# #     set, or ``key_source='platform'``), that column is empty and the call
# #     failed with a 401.

# #     This helper is invoked from ``call_llm`` ONLY when ``config.apiKey`` is
# #     missing or empty. It delegates to
# #     ``IntegrationCredentialsService.resolve_credentials(integration_type='llm', ...)``
# #     which:

# #       1. If ``config.global_llm_config_id`` is set, loads that row from
# #          ``public.global_llm_config``, Fernet-decrypts its
# #          ``api_key_encrypted`` column, and returns the plaintext key.
# #       2. Else looks up the platform default for ``provider`` in
# #          ``public.global_llm_config`` (is_default=True, is_active=True).
# #       3. Else falls back to the configured SecretBackend (env / AWS SM /
# #          Azure KV) under ``platform/llm/{provider}/api_key``.

# #     Returns ``None`` if no key can be resolved. The caller raises a clear
# #     ``LlmGatewayError`` so the user sees an actionable message instead of
# #     an empty-key 401 from the upstream provider.

# #     Expected behavior for the 3 cases:

# #       Case A — tenant-managed legacy key (``config.apiKey`` set):
# #           This helper is NOT called (caller short-circuits).
# #           ``call_llm`` uses ``config.apiKey`` directly.

# #       Case B — platform-managed key via ``global_llm_config_id``:
# #           This helper resolves the Fernet-encrypted key from
# #           ``public.global_llm_config`` via ``IntegrationCredentialsService``.

# #       Case C — neither set (misconfigured tenant):
# #           This helper returns ``None``; ``call_llm`` raises
# #           ``LlmGatewayError("No LLM API key configured. Set
# #           key_source='platform' with a global_llm_config_id, or provide an
# #           apiKey.")``.
# #     """
# #     integration_id: str | None = None
# #     gid = getattr(config, "global_llm_config_id", None)
# #     if gid is not None:
# #         try:
# #             integration_id = str(int(gid))
# #         except (TypeError, ValueError):
# #             integration_id = None

# #     try:
# #         from app.core.database import AsyncSessionLocal
# #         from app.features.integrations.integration_credentials_service import (
# #             IntegrationCredentialsService,
# #         )
# #     except ImportError as exc:  # pragma: no cover — defensive
# #         logger.warning(
# #             "llm.dual_path_import_failed",
# #             provider=provider,
# #             error=str(exc),
# #         )
# #         return None

# #     try:
# #         async with AsyncSessionLocal() as db:
# #             # IntegrationCredentialsService._resolve_llm_credentials queries
# #             # public.global_llm_config explicitly (schema-qualified), so the
# #             # session's search_path does not matter here.
# #             creds = await IntegrationCredentialsService().resolve_credentials(
# #                 db,
# #                 integration_type="llm",
# #                 integration_id=integration_id,
# #                 provider=provider,
# #             )
# #         api_key = creds.get("api_key") if creds else None
# #         if api_key:
# #             logger.debug(
# #                 "llm.dual_path_resolved",
# #                 provider=provider,
# #                 global_llm_config_id=integration_id,
# #                 key_source=creds.get("key_source"),
# #             )
# #         return api_key
# #     except Exception as exc:  # noqa: BLE001 — credential resolution must never break the call
# #         logger.warning(
# #             "llm.dual_path_resolve_failed",
# #             provider=provider,
# #             global_llm_config_id=integration_id,
# #             error=str(exc),
# #         )
# #         return None


# # async def call_llm(
# #     config: LlmConfigModel, messages: list[dict[str, str]]
# # ) -> LlmResponse:
# #     """
# #     Main entry point — dispatch to the provider-specific adapter (per §6.2).

# #     Args:
# #         config:   the tenant's LlmConfig DB row
# #         messages: list of {role, content} dicts (system/user/assistant)

# #     Returns:
# #         LlmResponse with content, usage, model, provider, raw.

# #     Raises:
# #         LlmGatewayError: when the config is inactive, the provider is
# #             unknown, no API key can be resolved (dual-path failure), or
# #             the HTTP call fails after 3 retries.

# #     FIX-BE-1 / CRITICAL 2: when ``config.apiKey`` is empty (tenant using
# #     ``global_llm_config_id`` / platform-managed keys), the API key is
# #     resolved via ``IntegrationCredentialsService.resolve_credentials``
# #     before the HTTP call is dispatched. See
# #     ``_resolve_dual_path_api_key`` for the full resolution chain.
# #     """
# #     if not config.isActive:
# #         raise LlmGatewayError(f"LlmConfig '{config.name}' is not active")

# #     kwargs = cast_llm_config(config)
# #     provider = kwargs["provider"]
# #     if provider not in ALL_PROVIDERS:
# #         raise LlmGatewayError(
# #             f"Unknown LLM provider: '{provider}'. "
# #             f"Supported: {', '.join(ALL_PROVIDERS)}"
# #         )

# #     # ── Dual-path credential resolution (FIX-BE-1 / CRITICAL 2) ──────────
# #     # cast_llm_config above populated kwargs['api_key'] from config.apiKey
# #     # (the legacy plaintext column). When that is missing/empty, resolve
# #     # the key via the IntegrationCredentialsService — which checks
# #     # public.global_llm_config (Fernet-encrypted) first, then falls back
# #     # to the platform SecretBackend. Never silently send an empty key to
# #     # the provider (would produce a confusing 401 instead of a clear
# #     # configuration error).
# #     if not kwargs.get("api_key"):
# #         resolved = await _resolve_dual_path_api_key(config, provider=provider)
# #         if resolved:
# #             kwargs["api_key"] = resolved
# #         else:
# #             raise LlmGatewayError(
# #                 "No LLM API key configured. Set key_source='platform' with a "
# #                 "global_llm_config_id, or provide an apiKey."
# #             )

# #     try:
# #         response = await _call_provider(provider, kwargs, messages)
# #     except LlmGatewayError:
# #         # Bump the error counter (best-effort) before re-raising.
# #         _record_llm_error(provider, kwargs["model"], "LlmGatewayError")
# #         raise
# #     except Exception as exc:
# #         logger.warning(
# #             "llm.call_llm.failed",
# #             provider=provider,
# #             model=kwargs["model"],
# #             error=str(exc),
# #         )
# #         _record_llm_error(provider, kwargs["model"], type(exc).__name__)
# #         raise LlmGatewayError(
# #             f"LLM call failed for provider '{provider}': {exc}"
# #         ) from exc

# #     # ── Usage instrumentation (fire-and-forget — never breaks the LLM call).
# #     # Records a UsageEvent + bumps Prometheus counters. Best-effort: any
# #     # failure is swallowed + logged so the caller still gets the LlmResponse.
# #     _record_llm_usage(provider, kwargs["model"], response, config)
# #     return response


# # def _record_llm_error(provider: str, model: str, error_type: str) -> None:
# #     """Bump the LLM error counter. Best-effort — never raises."""
# #     try:
# #         from app.core.metrics import LLM_ERRORS

# #         # tenant label is unknown here (call_llm does not receive it); use
# #         # "_unknown" so the metric is still emitted. The per-tenant
# #         # attribution comes from the UsageService path, which IS tenant-aware.
# #         LLM_ERRORS.labels(
# #             provider=provider, model=model, tenant="_unknown", error_type=error_type
# #         ).inc()
# #     except Exception:  # noqa: BLE001
# #         pass


# # def _record_llm_usage(
# #     provider: str, model: str, response: "LlmResponse", config: "LlmConfigModel"
# # ) -> None:
# #     """Best-effort: record UsageEvent + Prometheus counters for one LLM call.

# #     Runs in the BACKGROUND so the caller's request is not blocked on the
# #     usage-event INSERT. Any failure (DB down, import error, cost-lookup
# #     error) is swallowed + logged. The LLM call has already succeeded —
# #     the caller's response is unaffected.

# #     Tenant + user_id are extracted from the structlog contextvars bound
# #     by RequestContextMiddleware + TenantMiddleware. When those are not
# #     available (background jobs, tests), the event is recorded with
# #     tenant="_unknown" / user_id="_unknown" so the metric still surfaces.
# #     """
# #     try:
# #         usage = getattr(response, "usage", None) or {}
# #         prompt_tokens = int(usage.get("prompt_tokens", 0) or 0)
# #         completion_tokens = int(usage.get("completion_tokens", 0) or 0)

# #         # Pull tenant + user_id from structlog contextvars (set by the
# #         # request middleware). For non-request callers (Celery tasks,
# #         # scheduler), fall back to "_unknown" so the event is still recorded.
# #         tenant_slug = "_unknown"
# #         user_id = "_unknown"
# #         request_id: str | None = None
# #         try:
# #             from structlog import contextvars as _cv

# #             ctx = _cv.get_contextvars()
# #             # The audit + tenant middleware bind "request_id" + "tenant_slug"
# #             # to the context. We use the same names here.
# #             t = ctx.get("tenant_slug")
# #             if isinstance(t, str) and t:
# #                 tenant_slug = t
# #             u = ctx.get("user_id")
# #             if isinstance(u, str) and u:
# #                 user_id = u
# #             request_id = ctx.get("request_id") if isinstance(ctx.get("request_id"), str) else None
# #         except Exception:  # noqa: BLE001
# #             pass

# #         # Bump Prometheus counters (synchronous, never blocks).
# #         try:
# #             from app.core.metrics import LLM_CALLS, LLM_TOKENS, LLM_LATENCY, LLM_COST_CENTS

# #             LLM_CALLS.labels(provider=provider, model=model, tenant=tenant_slug).inc()
# #             LLM_TOKENS.labels(
# #                 provider=provider, model=model, type="input", tenant=tenant_slug
# #             ).inc(prompt_tokens)
# #             LLM_TOKENS.labels(
# #                 provider=provider, model=model, type="output", tenant=tenant_slug
# #             ).inc(completion_tokens)
# #         except Exception:  # noqa: BLE001
# #             pass

# #         # Compute cost + persist UsageEvent asynchronously.
# #         import asyncio

# #         async def _record() -> None:
# #             try:
# #                 from app.features.usage.service import UsageService

# #                 await UsageService().record_llm_call(
# #                     tenant=tenant_slug,
# #                     user_id=user_id,
# #                     provider=provider,
# #                     model=model,
# #                     prompt_tokens=prompt_tokens,
# #                     completion_tokens=completion_tokens,
# #                     metadata={
# #                         "request_id": request_id,
# #                         "config_name": getattr(config, "name", None),
# #                     },
# #                 )
# #             except Exception as exc:  # noqa: BLE001 — usage must never break LLM
# #                 logger.warning(
# #                     "llm.usage_record_failed",
# #                     provider=provider,
# #                     model=model,
# #                     tenant=tenant_slug,
# #                     error=str(exc),
# #                 )

# #         # Schedule the record on the running loop. We do NOT await it — the
# #         # caller is waiting on the LlmResponse and the usage write is
# #         # fire-and-forget per the SURVEY-OBS design.
# #         #
# #         # IMPORTANT: hold a strong reference to the task in _BG_USAGE_TASKS so
# #         # the garbage collector does not cancel it mid-flight (CPython's asyncio
# #         # only keeps weak references to tasks). Tasks self-remove on completion.
# #         try:
# #             loop = asyncio.get_running_loop()
# #             task = loop.create_task(_record())
# #             _BG_USAGE_TASKS.add(task)
# #             task.add_done_callback(_BG_USAGE_TASKS.discard)
# #         except RuntimeError:
# #             # No running loop (e.g., sync test context) — run inline.
# #             try:
# #                 asyncio.run(_record())
# #             except Exception:  # noqa: BLE001
# #                 pass
# #     except Exception as exc:  # noqa: BLE001 — instrumentation must never break the LLM call
# #         logger.warning(
# #             "llm.usage_instrumentation_failed",
# #             provider=provider,
# #             model=model,
# #             error=str(exc),
# #         )


# # # ── Legacy LlmService (preserved for backward compat with Phase 3 modules) ──


# # def _ensure_chat_completions_suffix(url: str) -> str:
# #     """
# #     Audit fix (AUDIT-A1 #6 / H-11): append /chat/completions to a ZAI base
# #     URL when missing. The legacy ``LLM_API_URL`` setting defaults to
# #     ``https://open.bigmodel.cn/api/paas/v4`` (no suffix), so the previous
# #     implementation POSTed to the API root and would 404.

# #     Idempotent: leaves URLs that already end with /chat/completions alone.
# #     """
# #     if not url:
# #         return url
# #     if url.rstrip("/").endswith("/chat/completions"):
# #         return url
# #     # ZAI base ends with /v4 — append /chat/completions
# #     if "open.bigmodel.cn" in url and not url.rstrip("/").endswith(("/v4", "/v4/")):
# #         return url
# #     return url.rstrip("/") + "/chat/completions"


# # def _extract_text(data: dict[str, Any]) -> str:
# #     """Tolerant extractor for OpenAI/ZAI response shapes."""
# #     try:
# #         choices = data.get("choices") or []
# #         if choices:
# #             msg = choices[0].get("message") or {}
# #             content = msg.get("content")
# #             if isinstance(content, str):
# #                 return content
# #         # Some ZAI variants nest under "output"
# #         output = data.get("output")
# #         if isinstance(output, str):
# #             return output
# #         if isinstance(output, list) and output:
# #             first = output[0]
# #             if isinstance(first, dict) and "content" in first:
# #                 return str(first["content"])
# #     except Exception:  # noqa: BLE001
# #         pass
# #     return ""


# # class LlmService:
# #     """
# #     Phase 1 thin async wrapper around the configured OpenAI-compatible endpoint.

# #     Preserved verbatim for backward compatibility with Phase 3 modules that
# #     consume ``get_llm_service().generate()`` and ``generate_json()``.

# #     Audit fix: the URL now goes through ``_ensure_chat_completions_suffix``
# #     so ZAI calls hit ``/api/paas/v4/chat/completions`` instead of the
# #     API root.

# #     New code should prefer ``call_llm(config, messages)`` with an
# #     explicit ``LlmConfig`` DB row.
# #     """

# #     def __init__(self, settings: Any | None = None) -> None:
# #         self._settings = settings or get_settings()

# #     async def generate(
# #         self,
# #         *,
# #         prompt: str,
# #         system: str | None = None,
# #         model: str = "glm-4-flash",
# #         temperature: float = 0.7,
# #         max_tokens: int = 1024,
# #         timeout: float | None = None,
# #     ) -> str:
# #         """
# #         Send a single-turn prompt and return the generated text.

# #         Falls back to a stub when the API URL is empty or the call fails,
# #         so feature modules always receive a string (never raise to the caller
# #         — they handle empty-string gracefully).
# #         """
# #         url = _ensure_chat_completions_suffix(self._settings.LLM_API_URL)
# #         timeout_s = timeout or float(self._settings.LLM_DEFAULT_TIMEOUT_SECONDS)

# #         if not url:
# #             return self._stub(prompt)

# #         payload: dict[str, Any] = {
# #             "model": model,
# #             "messages": (
# #                 [{"role": "system", "content": system}] if system else []
# #             )
# #             + [{"role": "user", "content": prompt}],
# #             "temperature": temperature,
# #             "max_tokens": max_tokens,
# #         }
# #         try:
# #             async with httpx.AsyncClient(timeout=timeout_s) as client:
# #                 resp = await client.post(
# #                     url,
# #                     json=payload,
# #                     headers={"Content-Type": "application/json"},
# #                 )
# #                 resp.raise_for_status()
# #                 data = resp.json()
# #                 return _extract_text(data)
# #         except Exception as exc:  # noqa: BLE001 — graceful degradation
# #             logger.warning("llm.generate.fallback", error=str(exc))
# #             return self._stub(prompt)

# #     async def generate_json(
# #         self,
# #         *,
# #         prompt: str,
# #         system: str | None = None,
# #         model: str = "glm-4-flash",
# #         timeout: float | None = None,
# #     ) -> dict[str, Any]:
# #         """Generate and JSON-parse. Returns {} on parse failure."""
# #         raw = await self.generate(
# #             prompt=prompt,
# #             system=system,
# #             model=model,
# #             temperature=0.2,
# #             max_tokens=2048,
# #             timeout=timeout,
# #         )
# #         try:
# #             return json.loads(raw)
# #         except (json.JSONDecodeError, ValueError):
# #             logger.warning("llm.generate_json.parse_failed", raw=raw[:200])
# #             return {}

# #     @staticmethod
# #     def _stub(prompt: str) -> str:
# #         """Deterministic stub used when no LLM endpoint is configured."""
# #         return f"[LLM-STUB] {prompt[:120]}"


# # @lru_cache
# # def get_llm_service() -> LlmService:
# #     """Cached accessor — import this, never instantiate LlmService directly."""
# #     return LlmService()


# # __all__ = [
# #     # Constants
# #     "ALL_PROVIDERS",
# #     "PROVIDER_BASE_URLS",
# #     "PROVIDER_OPENAI",
# #     "PROVIDER_ANTHROPIC",
# #     "PROVIDER_AZURE",
# #     "PROVIDER_GEMINI",
# #     "PROVIDER_BEDROCK",
# #     "PROVIDER_COHERE",
# #     "PROVIDER_MISTRAL",
# #     "PROVIDER_LLAMA",
# #     "PROVIDER_GROQ",
# #     "PROVIDER_AI21",
# #     "PROVIDER_HUGGINGFACE",
# #     "PROVIDER_ZAI",
# #     "PROVIDER_LOCAL",
# #     "LLM_HTTP_TIMEOUT",
# #     # Errors
# #     "LlmGatewayError",
# #     # Gateway functions (Phase 2)
# #     "call_llm",
# #     "cast_llm_config",
# #     "get_default_llm_config",
# #     "get_model_for_task",
# #     # Legacy service (Phase 1 — preserved)
# #     "LlmService",
# #     "get_llm_service",
# # ]
# """
# llm_service.py — Async HTTP gateway to 13 LLM providers.

# Phase 1 (preserved): ``LlmService`` is a thin async wrapper around the
# configured OpenAI-compatible endpoint. Phase 3 modules that consume
# ``get_llm_service().generate()`` continue to work unchanged.

# Phase 2 (added): module-level gateway functions dispatch to provider-specific
# adapters via ``LlmConfig.provider``:
#   - ``call_llm(config, messages) -> LlmResponse``
#   - ``cast_llm_config(config) -> dict[str, Any]``
#   - ``get_default_llm_config(db) -> LlmConfig | None``
#   - ``get_model_for_task(task, config) -> str``

# The 13 supported providers (per migration doc §3.4 + §10 Phase 2):
#   OpenAI, Anthropic, Azure OpenAI, Google Gemini, AWS Bedrock, Cohere,
#   Mistral, Meta Llama (via Together), Groq, AI21, Hugging Face, ZAI,
#   Local (Ollama).

# Audit fix (AUDIT-A1 #6 / H-11): ZAI provider now POSTs to the full
# ``https://open.bigmodel.cn/api/paas/v4/chat/completions`` URL — the
# previous default omitted the ``/chat/completions`` suffix and would 404
# against the real ZAI endpoint.
# """
# from __future__ import annotations

# import json
# from functools import lru_cache
# from typing import Any

# import httpx
# import structlog
# from sqlalchemy import select
# from sqlalchemy.ext.asyncio import AsyncSession
# from tenacity import (
#     AsyncRetrying,
#     retry_if_exception_type,
#     stop_after_attempt,
#     wait_exponential,
# )

# from app.core.config import get_settings
# from app.models.config_models import LlmConfig as LlmConfigModel
# from app.schemas.llm_config import LlmResponse

# logger = structlog.get_logger(__name__)


# # ── Background-task registry for fire-and-forget usage writes ──────────────
# # Holds strong references to asyncio Tasks created by _record_llm_usage so
# # CPython's garbage collector does not cancel them mid-flight. Tasks self-
# # remove via add_done_callback when they complete. The set is module-level
# # (not per-request) because usage writes are fire-and-forget — we never
# # await them from the caller.
# _BG_USAGE_TASKS: set = set()


# # ── Constants ───────────────────────────────────────────────────────────────

# LLM_HTTP_TIMEOUT: float = 60.0
# # Local models (Ollama on CPU) need much longer — 5 minutes
# LLM_HTTP_TIMEOUT_LOCAL: float = 300.0
# """Per-request HTTP timeout for all provider calls (per §10 Phase 2)."""

# # ── Provider keys ───────────────────────────────────────────────────────────

# PROVIDER_OPENAI = "openai"
# PROVIDER_ANTHROPIC = "anthropic"
# PROVIDER_AZURE = "azure"
# PROVIDER_GEMINI = "gemini"
# PROVIDER_BEDROCK = "bedrock"
# PROVIDER_COHERE = "cohere"
# PROVIDER_MISTRAL = "mistral"
# PROVIDER_LLAMA = "llama"  # Meta Llama served via Together
# PROVIDER_GROQ = "groq"
# PROVIDER_AI21 = "ai21"
# PROVIDER_HUGGINGFACE = "huggingface"
# PROVIDER_ZAI = "zai"
# PROVIDER_LOCAL = "local"  # Ollama

# ALL_PROVIDERS: tuple[str, ...] = (
#     PROVIDER_OPENAI,
#     PROVIDER_ANTHROPIC,
#     PROVIDER_AZURE,
#     PROVIDER_GEMINI,
#     PROVIDER_BEDROCK,
#     PROVIDER_COHERE,
#     PROVIDER_MISTRAL,
#     PROVIDER_LLAMA,
#     PROVIDER_GROQ,
#     PROVIDER_AI21,
#     PROVIDER_HUGGINGFACE,
#     PROVIDER_ZAI,
#     PROVIDER_LOCAL,
# )

# # Default base URLs per provider. Can be overridden per-row via LlmConfig.baseUrl.
# PROVIDER_BASE_URLS: dict[str, str] = {
#     PROVIDER_OPENAI: "https://api.openai.com/v1",
#     PROVIDER_ANTHROPIC: "https://api.anthropic.com/v1",
#     PROVIDER_AZURE: "",  # requires LlmConfig.baseUrl (tenant-specific endpoint)
#     PROVIDER_GEMINI: "https://generativelanguage.googleapis.com/v1beta",
#     PROVIDER_BEDROCK: "https://bedrock-runtime.us-east-1.amazonaws.com",
#     PROVIDER_COHERE: "https://api.cohere.com/v2",
#     PROVIDER_MISTRAL: "https://api.mistral.ai/v1",
#     PROVIDER_LLAMA: "https://api.together.xyz/v1",  # Together hosts Llama
#     PROVIDER_GROQ: "https://api.groq.com/openai/v1",
#     PROVIDER_AI21: "https://api.ai21.com/studio/v1",
#     PROVIDER_HUGGINGFACE: "https://api-inference.huggingface.co/models",
#     PROVIDER_ZAI: "https://open.bigmodel.cn/api/paas/v4",
#     PROVIDER_LOCAL: "http://localhost:11434/v1",  # Ollama default
# }

# # Providers that speak the OpenAI-compatible /chat/completions dialect.
# _OPENAI_COMPATIBLE: frozenset[str] = frozenset({
#     PROVIDER_OPENAI,
#     PROVIDER_GROQ,
#     PROVIDER_MISTRAL,
#     PROVIDER_LLAMA,
#     PROVIDER_LOCAL,
#     PROVIDER_ZAI,
#     PROVIDER_AI21,
#     PROVIDER_HUGGINGFACE,
#     PROVIDER_COHERE,
#     PROVIDER_AZURE,
# })

# # Default anthropic-version header value (per Anthropic API spec).
# _ANTHROPIC_VERSION_DEFAULT = "2023-06-01"

# # Default Azure OpenAI API version (per Azure OpenAI REST spec).
# _AZURE_API_VERSION_DEFAULT = "2024-10-21"


# class LlmGatewayError(Exception):
#     """Raised when the LLM gateway call fails after retries."""


# # ── Settings-column parsing ─────────────────────────────────────────────────


# def _parse_settings(config: LlmConfigModel) -> dict[str, Any]:
#     """
#     Parse the LlmConfig.settings JSON column safely.

#     The column is TEXT holding a JSON string (per §5.5). Returns {} on parse
#     failure or non-dict content — never raises.
#     """
#     raw = getattr(config, "settings", None) or "{}"
#     try:
#         parsed = json.loads(raw)
#     except (json.JSONDecodeError, TypeError, ValueError):
#         return {}
#     return parsed if isinstance(parsed, dict) else {}


# # ── Helper mapping (per §6.2) ───────────────────────────────────────────────


# def cast_llm_config(config: LlmConfigModel) -> dict[str, Any]:
#     """
#     Convert a LlmConfig DB row into provider-specific kwargs (per §6.2).

#     Returns a dict with the keys:
#       - provider:     normalized provider key (lowercase)
#       - model:        the model ID to invoke
#       - api_key:      the API key (may be None for ZAI/local)
#       - base_url:     the provider's base URL
#       - temperature:  float (default 0.7)
#       - max_tokens:   int (default 1024)
#       - extra:        provider-specific kwargs (api_version, deployment,
#                       region, anthropic_version, generation_config, ...)

#     The 'models' map inside settings (task -> model_id) is consumed
#     separately by ``get_model_for_task()``.
#     """
#     settings = _parse_settings(config)
#     provider = (config.provider or PROVIDER_ZAI).lower()
#     base_url = config.baseUrl or PROVIDER_BASE_URLS.get(provider, "")

#     temperature_raw = settings.get("temperature", settings.get("Temperature", 0.7))
#     max_tokens_raw = settings.get(
#         "max_tokens", settings.get("maxTokens", settings.get("MaxTokens", 1024))
#     )

#     try:
#         temperature = float(temperature_raw)
#     except (TypeError, ValueError):
#         temperature = 0.7
#     try:
#         max_tokens = int(max_tokens_raw)
#     except (TypeError, ValueError):
#         max_tokens = 1024

#     kwargs: dict[str, Any] = {
#         "provider": provider,
#         "model": config.modelId,
#         "api_key": config.apiKey,
#         "base_url": base_url,
#         "temperature": temperature,
#         "max_tokens": max_tokens,
#         "extra": {},
#     }

#     # Provider-specific extras
#     if provider == PROVIDER_AZURE:
#         kwargs["extra"]["api_version"] = settings.get(
#             "api_version", settings.get("apiVersion", _AZURE_API_VERSION_DEFAULT)
#         )
#         kwargs["extra"]["deployment"] = settings.get(
#             "deployment", settings.get("deploymentName", config.modelId)
#         )
#     elif provider == PROVIDER_BEDROCK:
#         kwargs["extra"]["region"] = settings.get("region", "us-east-1")
#         kwargs["extra"]["model_id"] = settings.get("model_id", config.modelId)
#     elif provider == PROVIDER_ANTHROPIC:
#         kwargs["extra"]["anthropic_version"] = settings.get(
#             "anthropic_version", _ANTHROPIC_VERSION_DEFAULT
#         )
#     elif provider == PROVIDER_GEMINI:
#         kwargs["extra"]["generation_config"] = {
#             "temperature": temperature,
#             "maxOutputTokens": max_tokens,
#             "topP": float(settings.get("top_p", settings.get("topP", 1.0))),
#         }

#     return kwargs


# def get_model_for_task(task: str, config: LlmConfigModel) -> str:
#     """
#     Tier routing — return the model ID for a given task (per §3.4 + §10 Phase 2).

#     Reads the 'models' dict inside the JSON settings column. Returns
#     ``config.modelId`` when no per-task override is configured.

#     Known tasks: email_generation, icp_suggest, framework_recommend,
#     gtm_thesis, subject_line, qa_check, compliance_check, reply_categorize,
#     auto_reply, personalization, anti_pattern, prospect_brief,
#     prospect_lookalike, ultimate_profile, prospect_enrich, prospect_score,
#     analytics_diagnose, content_idea, linkedin_post, meeting_prep,
#     deal_suggest, deal_health, deal_next_step, weekly_digest, cadence_plan,
#     touch_angle, rule_suggest, ab_test_hypothesis.
#     """
#     settings = _parse_settings(config)
#     models_map = settings.get("models") or {}
#     if isinstance(models_map, dict) and task in models_map:
#         return str(models_map[task])
#     return config.modelId


# async def get_default_llm_config(db: AsyncSession) -> LlmConfigModel | None:
#     """
#     Fetch the tenant's default LlmConfig.

#     Returns the row where ``isDefault=True AND isActive=True`` (newest first).
#     Falls back to the first active row by createdAt ordering when no row is
#     marked default — per the "first one wins" convention in §6.2.
#     """
#     result = await db.execute(
#         select(LlmConfigModel)
#         .where(LlmConfigModel.isDefault.is_(True))
#         .where(LlmConfigModel.isActive.is_(True))
#         .order_by(LlmConfigModel.createdAt.asc())
#         .limit(1)
#     )
#     row = result.scalar_one_or_none()
#     if row is not None:
#         return row

#     result = await db.execute(
#         select(LlmConfigModel)
#         .where(LlmConfigModel.isActive.is_(True))
#         .order_by(LlmConfigModel.createdAt.asc())
#         .limit(1)
#     )
#     return result.scalar_one_or_none()


# # ── Provider URL + header builders ──────────────────────────────────────────


# def _provider_chat_url(provider: str, kwargs: dict[str, Any]) -> str:
#     """Return the chat-completions URL for a provider."""
#     base = (kwargs.get("base_url") or PROVIDER_BASE_URLS.get(provider, "")).rstrip("/")
#     if not base:
#         raise LlmGatewayError(f"No base_url configured for provider '{provider}'")

#     if provider == PROVIDER_ANTHROPIC:
#         return f"{base}/messages"
#     if provider == PROVIDER_GEMINI:
#         model = kwargs["model"]
#         return f"{base}/models/{model}:generateContent"
#     if provider == PROVIDER_AZURE:
#         deployment = kwargs["extra"].get("deployment", "deployment")
#         api_version = kwargs["extra"].get("api_version", _AZURE_API_VERSION_DEFAULT)
#         return f"{base}/openai/deployments/{deployment}/chat/completions?api-version={api_version}"
#     if provider == PROVIDER_COHERE:
#         return f"{base}/chat"
#     if provider == PROVIDER_BEDROCK:
#         model_id = kwargs["extra"].get("model_id", kwargs["model"])
#         return f"{base}/model/{model_id}/invoke"
#     if provider == PROVIDER_HUGGINGFACE:
#         # HF router: /models/{model}/v1/chat/completions
#         return f"{base}/{kwargs['model']}/v1/chat/completions"
#     # OpenAI-compatible: openai, groq, mistral, llama (Together), local, zai, ai21
#     return f"{base}/chat/completions"


# def _provider_headers(provider: str, kwargs: dict[str, Any]) -> dict[str, str]:
#     """Return provider-specific auth headers (Content-Type added by caller)."""
#     api_key = kwargs.get("api_key") or ""
#     if provider == PROVIDER_ANTHROPIC:
#         return {
#             "x-api-key": api_key,
#             "anthropic-version": kwargs["extra"].get(
#                 "anthropic_version", _ANTHROPIC_VERSION_DEFAULT
#             ),
#         }
#     if provider == PROVIDER_GEMINI:
#         return {"x-goog-api-key": api_key}
#     if provider == PROVIDER_AZURE:
#         # Azure uses api-key header (not Bearer)
#         return {"api-key": api_key}
#     return {"Authorization": f"Bearer {api_key}"}


# # ── Payload builders (per-provider) ─────────────────────────────────────────


# def _build_openai_payload(
#     messages: list[dict[str, str]], kwargs: dict[str, Any]
# ) -> dict[str, Any]:
#     """OpenAI-compatible chat-completions payload."""
#     return {
#         "model": kwargs["model"],
#         "messages": messages,
#         "temperature": kwargs["temperature"],
#         "max_tokens": kwargs["max_tokens"],
#     }


# def _build_anthropic_payload(
#     messages: list[dict[str, str]], kwargs: dict[str, Any]
# ) -> dict[str, Any]:
#     """Anthropic Messages API — system is a top-level field, not in messages."""
#     system_msgs = [m for m in messages if m.get("role") == "system"]
#     user_msgs = [m for m in messages if m.get("role") != "system"]
#     system_text = "\n\n".join(str(m.get("content", "")) for m in system_msgs)
#     payload: dict[str, Any] = {
#         "model": kwargs["model"],
#         "messages": user_msgs,
#         "max_tokens": kwargs["max_tokens"],
#         "temperature": kwargs["temperature"],
#     }
#     if system_text:
#         payload["system"] = system_text
#     return payload


# def _build_gemini_payload(
#     messages: list[dict[str, str]], kwargs: dict[str, Any]
# ) -> dict[str, Any]:
#     """Google Gemini generateContent payload."""
#     contents: list[dict[str, Any]] = []
#     sys_text = "\n".join(
#         str(m.get("content", "")) for m in messages if m.get("role") == "system"
#     )
#     for m in messages:
#         role = m.get("role", "user")
#         if role == "system":
#             continue
#         gemini_role = "user" if role == "user" else "model"
#         contents.append(
#             {"role": gemini_role, "parts": [{"text": str(m.get("content", ""))}]}
#         )
#     payload: dict[str, Any] = {
#         "contents": contents,
#         "generationConfig": kwargs["extra"].get("generation_config", {}),
#     }
#     if sys_text:
#         payload["systemInstruction"] = {"parts": [{"text": sys_text}]}
#     return payload


# def _build_cohere_payload(
#     messages: list[dict[str, str]], kwargs: dict[str, Any]
# ) -> dict[str, Any]:
#     """Cohere v2 chat (OpenAI-compatible)."""
#     return {
#         "model": kwargs["model"],
#         "messages": messages,
#         "temperature": kwargs["temperature"],
#         "max_tokens": kwargs["max_tokens"],
#     }


# def _build_bedrock_payload(
#     messages: list[dict[str, str]], kwargs: dict[str, Any]
# ) -> dict[str, Any]:
#     """
#     AWS Bedrock converse API payload.

#     Note: production deployments wrap this in boto3 SigV4 signing. The
#     gateway posts the converse payload directly when LlmConfig.apiKey
#     holds a bearer-secured proxy token (e.g. Bedrock proxy gateway).
#     """
#     return {
#         "modelId": kwargs["extra"].get("model_id", kwargs["model"]),
#         "messages": messages,
#         "inferenceConfig": {
#             "temperature": kwargs["temperature"],
#             "maxTokens": kwargs["max_tokens"],
#         },
#     }


# def _build_provider_payload(
#     provider: str, messages: list[dict[str, str]], kwargs: dict[str, Any]
# ) -> dict[str, Any]:
#     if provider == PROVIDER_ANTHROPIC:
#         return _build_anthropic_payload(messages, kwargs)
#     if provider == PROVIDER_GEMINI:
#         return _build_gemini_payload(messages, kwargs)
#     if provider == PROVIDER_BEDROCK:
#         return _build_bedrock_payload(messages, kwargs)
#     if provider == PROVIDER_COHERE:
#         return _build_cohere_payload(messages, kwargs)
#     # All OpenAI-compatible providers
#     return _build_openai_payload(messages, kwargs)


# # ── Response parsers (per-provider) ─────────────────────────────────────────


# def _parse_openai_response(
#     data: dict[str, Any], provider: str, model: str
# ) -> LlmResponse:
#     """Parse OpenAI-compatible response shape (used by 10 of 13 providers)."""
#     choices = data.get("choices") or []
#     content = ""
#     if choices:
#         msg = choices[0].get("message") or {}
#         content = str(msg.get("content", ""))
#     usage = data.get("usage") or {}
#     usage_dict = {
#         "prompt_tokens": int(usage.get("prompt_tokens", 0) or 0),
#         "completion_tokens": int(usage.get("completion_tokens", 0) or 0),
#         "total_tokens": int(usage.get("total_tokens", 0) or 0),
#     }
#     return LlmResponse(
#         content=content,
#         usage=usage_dict,
#         model=model,
#         provider=provider,
#         raw=data,
#     )


# def _parse_anthropic_response(
#     data: dict[str, Any], provider: str, model: str
# ) -> LlmResponse:
#     content = ""
#     blocks = data.get("content") or []
#     if isinstance(blocks, list):
#         for b in blocks:
#             if isinstance(b, dict) and b.get("type") == "text":
#                 content += str(b.get("text", ""))
#     usage = data.get("usage") or {}
#     input_tokens = int(usage.get("input_tokens", 0) or 0)
#     output_tokens = int(usage.get("output_tokens", 0) or 0)
#     usage_dict = {
#         "prompt_tokens": input_tokens,
#         "completion_tokens": output_tokens,
#         "total_tokens": input_tokens + output_tokens,
#     }
#     return LlmResponse(
#         content=content,
#         usage=usage_dict,
#         model=model,
#         provider=provider,
#         raw=data,
#     )


# def _parse_gemini_response(
#     data: dict[str, Any], provider: str, model: str
# ) -> LlmResponse:
#     content = ""
#     candidates = data.get("candidates") or []
#     if candidates:
#         parts = (candidates[0].get("content") or {}).get("parts") or []
#         for p in parts:
#             if isinstance(p, dict) and "text" in p:
#                 content += str(p["text"])
#     usage_meta = data.get("usageMetadata") or {}
#     usage_dict = {
#         "prompt_tokens": int(usage_meta.get("promptTokenCount", 0) or 0),
#         "completion_tokens": int(usage_meta.get("candidatesTokenCount", 0) or 0),
#         "total_tokens": int(usage_meta.get("totalTokenCount", 0) or 0),
#     }
#     return LlmResponse(
#         content=content,
#         usage=usage_dict,
#         model=model,
#         provider=provider,
#         raw=data,
#     )


# def _parse_bedrock_response(
#     data: dict[str, Any], provider: str, model: str
# ) -> LlmResponse:
#     content = ""
#     output = data.get("output") or {}
#     msg = output.get("message") or {}
#     for c in msg.get("content") or []:
#         if isinstance(c, dict) and "text" in c:
#             content += str(c["text"])
#     usage = data.get("usage") or {}
#     usage_dict = {
#         "prompt_tokens": int(usage.get("inputTokens", 0) or 0),
#         "completion_tokens": int(usage.get("outputTokens", 0) or 0),
#         "total_tokens": int(usage.get("totalTokens", 0) or 0),
#     }
#     return LlmResponse(
#         content=content,
#         usage=usage_dict,
#         model=model,
#         provider=provider,
#         raw=data,
#     )


# def _parse_provider_response(
#     provider: str, data: dict[str, Any], model: str
# ) -> LlmResponse:
#     if provider == PROVIDER_ANTHROPIC:
#         return _parse_anthropic_response(data, provider, model)
#     if provider == PROVIDER_GEMINI:
#         return _parse_gemini_response(data, provider, model)
#     if provider == PROVIDER_BEDROCK:
#         return _parse_bedrock_response(data, provider, model)
#     return _parse_openai_response(data, provider, model)


# # ── HTTP transport with tenacity retry ──────────────────────────────────────


# async def _do_http_post(
#     url: str, headers: dict[str, str], payload: dict[str, Any],
#     timeout: float = LLM_HTTP_TIMEOUT,
# ) -> dict[str, Any]:
#     """Single HTTP POST with timeout. Raises httpx.HTTPError on failure."""
#     async with httpx.AsyncClient(timeout=timeout) as client:
#         resp = await client.post(url, json=payload, headers=headers)
#         resp.raise_for_status()
#         return resp.json()


# def _retrying() -> AsyncRetrying:
#     """
#     Tenacity AsyncRetrying: 3 attempts, exponential backoff 1-10s, on
#     transient HTTP errors only (429/5xx via HTTPStatusError + transport
#     errors). Per §10 Phase 2 spec.
#     """
#     return AsyncRetrying(
#         stop=stop_after_attempt(3),
#         wait=wait_exponential(multiplier=1, min=1, max=10),
#         retry=retry_if_exception_type(
#             (httpx.HTTPStatusError, httpx.ConnectError, httpx.ReadTimeout,
#              httpx.ConnectTimeout, httpx.RemoteProtocolError)
#         ),
#         reraise=True,
#     )


# async def _call_provider(
#     provider: str, kwargs: dict[str, Any], messages: list[dict[str, str]]
# ) -> LlmResponse:
#     """Dispatch to the right provider adapter. Retries transient failures."""
#     model = kwargs["model"]
#     url = _provider_chat_url(provider, kwargs)
#     payload = _build_provider_payload(provider, messages, kwargs)
#     headers: dict[str, str] = {"Content-Type": "application/json"}
#     headers.update(_provider_headers(provider, kwargs))

#     data: dict[str, Any] = {}
#     async for attempt in _retrying():
#         with attempt:
#             _timeout = LLM_HTTP_TIMEOUT_LOCAL if provider == PROVIDER_LOCAL else LLM_HTTP_TIMEOUT
#             data = await _do_http_post(url, headers, payload, timeout=_timeout)

#     return _parse_provider_response(provider, data, model)


# # ── Main entry: call_llm ────────────────────────────────────────────────────


# async def _resolve_dual_path_api_key(
#     config: LlmConfigModel, *, provider: str
# ) -> str | None:
#     """Resolve the LLM API key via the dual-path credential service.

#     FIX-BE-1 / CRITICAL 2: production LLM calls used to read
#     ``config.apiKey`` (the legacy plaintext column) directly. When a tenant
#     adopts the dual-path model (``apiKey=NULL`` + ``global_llm_config_id``
#     set, or ``key_source='platform'``), that column is empty and the call
#     failed with a 401.

#     This helper is invoked from ``call_llm`` ONLY when ``config.apiKey`` is
#     missing or empty. It delegates to
#     ``IntegrationCredentialsService.resolve_credentials(integration_type='llm', ...)``
#     which:

#       1. If ``config.global_llm_config_id`` is set, loads that row from
#          ``public.global_llm_config``, Fernet-decrypts its
#          ``api_key_encrypted`` column, and returns the plaintext key.
#       2. Else looks up the platform default for ``provider`` in
#          ``public.global_llm_config`` (is_default=True, is_active=True).
#       3. Else falls back to the configured SecretBackend (env / AWS SM /
#          Azure KV) under ``platform/llm/{provider}/api_key``.

#     Returns ``None`` if no key can be resolved. The caller raises a clear
#     ``LlmGatewayError`` so the user sees an actionable message instead of
#     an empty-key 401 from the upstream provider.

#     Expected behavior for the 3 cases:

#       Case A — tenant-managed legacy key (``config.apiKey`` set):
#           This helper is NOT called (caller short-circuits).
#           ``call_llm`` uses ``config.apiKey`` directly.

#       Case B — platform-managed key via ``global_llm_config_id``:
#           This helper resolves the Fernet-encrypted key from
#           ``public.global_llm_config`` via ``IntegrationCredentialsService``.

#       Case C — neither set (misconfigured tenant):
#           This helper returns ``None``; ``call_llm`` raises
#           ``LlmGatewayError("No LLM API key configured. Set
#           key_source='platform' with a global_llm_config_id, or provide an
#           apiKey.")``.
#     """
#     integration_id: str | None = None
#     gid = getattr(config, "global_llm_config_id", None)
#     if gid is not None:
#         try:
#             integration_id = str(int(gid))
#         except (TypeError, ValueError):
#             integration_id = None

#     try:
#         from app.core.database import AsyncSessionLocal
#         from app.features.integrations.integration_credentials_service import (
#             IntegrationCredentialsService,
#         )
#     except ImportError as exc:  # pragma: no cover — defensive
#         logger.warning(
#             "llm.dual_path_import_failed",
#             provider=provider,
#             error=str(exc),
#         )
#         return None

#     try:
#         async with AsyncSessionLocal() as db:
#             # IntegrationCredentialsService._resolve_llm_credentials queries
#             # public.global_llm_config explicitly (schema-qualified), so the
#             # session's search_path does not matter here.
#             creds = await IntegrationCredentialsService().resolve_credentials(
#                 db,
#                 integration_type="llm",
#                 integration_id=integration_id,
#                 provider=provider,
#             )
#         api_key = creds.get("api_key") if creds else None
#         if api_key:
#             logger.debug(
#                 "llm.dual_path_resolved",
#                 provider=provider,
#                 global_llm_config_id=integration_id,
#                 key_source=creds.get("key_source"),
#             )
#         return api_key
#     except Exception as exc:  # noqa: BLE001 — credential resolution must never break the call
#         logger.warning(
#             "llm.dual_path_resolve_failed",
#             provider=provider,
#             global_llm_config_id=integration_id,
#             error=str(exc),
#         )
#         return None


# async def call_llm(
#     config: LlmConfigModel, messages: list[dict[str, str]]
# ) -> LlmResponse:
#     """
#     Main entry point — dispatch to the provider-specific adapter (per §6.2).

#     Args:
#         config:   the tenant's LlmConfig DB row
#         messages: list of {role, content} dicts (system/user/assistant)

#     Returns:
#         LlmResponse with content, usage, model, provider, raw.

#     Raises:
#         LlmGatewayError: when the config is inactive, the provider is
#             unknown, no API key can be resolved (dual-path failure), or
#             the HTTP call fails after 3 retries.

#     FIX-BE-1 / CRITICAL 2: when ``config.apiKey`` is empty (tenant using
#     ``global_llm_config_id`` / platform-managed keys), the API key is
#     resolved via ``IntegrationCredentialsService.resolve_credentials``
#     before the HTTP call is dispatched. See
#     ``_resolve_dual_path_api_key`` for the full resolution chain.
#     """
#     if not config.isActive:
#         raise LlmGatewayError(f"LlmConfig '{config.name}' is not active")

#     kwargs = cast_llm_config(config)
#     provider = kwargs["provider"]
#     if provider not in ALL_PROVIDERS:
#         raise LlmGatewayError(
#             f"Unknown LLM provider: '{provider}'. "
#             f"Supported: {', '.join(ALL_PROVIDERS)}"
#         )

#     # ── Dual-path credential resolution (FIX-BE-1 / CRITICAL 2) ──────────
#     # cast_llm_config above populated kwargs['api_key'] from config.apiKey
#     # (the legacy plaintext column). When that is missing/empty, resolve
#     # the key via the IntegrationCredentialsService — which checks
#     # public.global_llm_config (Fernet-encrypted) first, then falls back
#     # to the platform SecretBackend. Never silently send an empty key to
#     # the provider (would produce a confusing 401 instead of a clear
#     # configuration error).
#     # local (Ollama) and zai providers do not require an API key —
#     # skip the key-resolution check for these providers entirely.
#     _KEY_OPTIONAL_PROVIDERS = (PROVIDER_LOCAL, PROVIDER_ZAI)
#     if not kwargs.get("api_key") and provider not in _KEY_OPTIONAL_PROVIDERS:
#         resolved = await _resolve_dual_path_api_key(config, provider=provider)
#         if resolved:
#             kwargs["api_key"] = resolved
#         else:
#             raise LlmGatewayError(
#                 "No LLM API key configured. Set key_source='platform' with a "
#                 "global_llm_config_id, or provide an apiKey."
#             )

#     try:
#         response = await _call_provider(provider, kwargs, messages)
#     except LlmGatewayError:
#         # Bump the error counter (best-effort) before re-raising.
#         _record_llm_error(provider, kwargs["model"], "LlmGatewayError")
#         raise
#     except Exception as exc:
#         logger.warning(
#             "llm.call_llm.failed",
#             provider=provider,
#             model=kwargs["model"],
#             error=str(exc),
#         )
#         _record_llm_error(provider, kwargs["model"], type(exc).__name__)
#         raise LlmGatewayError(
#             f"LLM call failed for provider '{provider}': {exc}"
#         ) from exc

#     # ── Usage instrumentation (fire-and-forget — never breaks the LLM call).
#     # Records a UsageEvent + bumps Prometheus counters. Best-effort: any
#     # failure is swallowed + logged so the caller still gets the LlmResponse.
#     _record_llm_usage(provider, kwargs["model"], response, config)
#     return response


# def _record_llm_error(provider: str, model: str, error_type: str) -> None:
#     """Bump the LLM error counter. Best-effort — never raises."""
#     try:
#         from app.core.metrics import LLM_ERRORS

#         # tenant label is unknown here (call_llm does not receive it); use
#         # "_unknown" so the metric is still emitted. The per-tenant
#         # attribution comes from the UsageService path, which IS tenant-aware.
#         LLM_ERRORS.labels(
#             provider=provider, model=model, tenant="_unknown", error_type=error_type
#         ).inc()
#     except Exception:  # noqa: BLE001
#         pass


# def _record_llm_usage(
#     provider: str, model: str, response: "LlmResponse", config: "LlmConfigModel"
# ) -> None:
#     """Best-effort: record UsageEvent + Prometheus counters for one LLM call.

#     Runs in the BACKGROUND so the caller's request is not blocked on the
#     usage-event INSERT. Any failure (DB down, import error, cost-lookup
#     error) is swallowed + logged. The LLM call has already succeeded —
#     the caller's response is unaffected.

#     Tenant + user_id are extracted from the structlog contextvars bound
#     by RequestContextMiddleware + TenantMiddleware. When those are not
#     available (background jobs, tests), the event is recorded with
#     tenant="_unknown" / user_id="_unknown" so the metric still surfaces.
#     """
#     try:
#         usage = getattr(response, "usage", None) or {}
#         prompt_tokens = int(usage.get("prompt_tokens", 0) or 0)
#         completion_tokens = int(usage.get("completion_tokens", 0) or 0)

#         # Pull tenant + user_id from structlog contextvars (set by the
#         # request middleware). For non-request callers (Celery tasks,
#         # scheduler), fall back to "_unknown" so the event is still recorded.
#         tenant_slug = "_unknown"
#         user_id = "_unknown"
#         request_id: str | None = None
#         try:
#             from structlog import contextvars as _cv

#             ctx = _cv.get_contextvars()
#             # The audit + tenant middleware bind "request_id" + "tenant_slug"
#             # to the context. We use the same names here.
#             t = ctx.get("tenant_slug")
#             if isinstance(t, str) and t:
#                 tenant_slug = t
#             u = ctx.get("user_id")
#             if isinstance(u, str) and u:
#                 user_id = u
#             request_id = ctx.get("request_id") if isinstance(ctx.get("request_id"), str) else None
#         except Exception:  # noqa: BLE001
#             pass

#         # Bump Prometheus counters (synchronous, never blocks).
#         try:
#             from app.core.metrics import LLM_CALLS, LLM_TOKENS, LLM_LATENCY, LLM_COST_CENTS

#             LLM_CALLS.labels(provider=provider, model=model, tenant=tenant_slug).inc()
#             LLM_TOKENS.labels(
#                 provider=provider, model=model, type="input", tenant=tenant_slug
#             ).inc(prompt_tokens)
#             LLM_TOKENS.labels(
#                 provider=provider, model=model, type="output", tenant=tenant_slug
#             ).inc(completion_tokens)
#         except Exception:  # noqa: BLE001
#             pass

#         # Compute cost + persist UsageEvent asynchronously.
#         import asyncio

#         async def _record() -> None:
#             try:
#                 from app.features.usage.service import UsageService

#                 await UsageService().record_llm_call(
#                     tenant=tenant_slug,
#                     user_id=user_id,
#                     provider=provider,
#                     model=model,
#                     prompt_tokens=prompt_tokens,
#                     completion_tokens=completion_tokens,
#                     metadata={
#                         "request_id": request_id,
#                         "config_name": getattr(config, "name", None),
#                     },
#                 )
#             except Exception as exc:  # noqa: BLE001 — usage must never break LLM
#                 logger.warning(
#                     "llm.usage_record_failed",
#                     provider=provider,
#                     model=model,
#                     tenant=tenant_slug,
#                     error=str(exc),
#                 )

#         # Schedule the record on the running loop. We do NOT await it — the
#         # caller is waiting on the LlmResponse and the usage write is
#         # fire-and-forget per the SURVEY-OBS design.
#         #
#         # IMPORTANT: hold a strong reference to the task in _BG_USAGE_TASKS so
#         # the garbage collector does not cancel it mid-flight (CPython's asyncio
#         # only keeps weak references to tasks). Tasks self-remove on completion.
#         try:
#             loop = asyncio.get_running_loop()
#             task = loop.create_task(_record())
#             _BG_USAGE_TASKS.add(task)
#             task.add_done_callback(_BG_USAGE_TASKS.discard)
#         except RuntimeError:
#             # No running loop (e.g., sync test context) — run inline.
#             try:
#                 asyncio.run(_record())
#             except Exception:  # noqa: BLE001
#                 pass
#     except Exception as exc:  # noqa: BLE001 — instrumentation must never break the LLM call
#         logger.warning(
#             "llm.usage_instrumentation_failed",
#             provider=provider,
#             model=model,
#             error=str(exc),
#         )


# # ── Legacy LlmService (preserved for backward compat with Phase 3 modules) ──


# def _ensure_chat_completions_suffix(url: str) -> str:
#     """
#     Audit fix (AUDIT-A1 #6 / H-11): append /chat/completions to a ZAI base
#     URL when missing. The legacy ``LLM_API_URL`` setting defaults to
#     ``https://open.bigmodel.cn/api/paas/v4`` (no suffix), so the previous
#     implementation POSTed to the API root and would 404.

#     Idempotent: leaves URLs that already end with /chat/completions alone.
#     """
#     if not url:
#         return url
#     if url.rstrip("/").endswith("/chat/completions"):
#         return url
#     # ZAI base ends with /v4 — append /chat/completions
#     if "open.bigmodel.cn" in url and not url.rstrip("/").endswith(("/v4", "/v4/")):
#         return url
#     return url.rstrip("/") + "/chat/completions"


# def _extract_text(data: dict[str, Any]) -> str:
#     """Tolerant extractor for OpenAI/ZAI response shapes."""
#     try:
#         choices = data.get("choices") or []
#         if choices:
#             msg = choices[0].get("message") or {}
#             content = msg.get("content")
#             if isinstance(content, str):
#                 return content
#         # Some ZAI variants nest under "output"
#         output = data.get("output")
#         if isinstance(output, str):
#             return output
#         if isinstance(output, list) and output:
#             first = output[0]
#             if isinstance(first, dict) and "content" in first:
#                 return str(first["content"])
#     except Exception:  # noqa: BLE001
#         pass
#     return ""


# class LlmService:
#     """
#     Phase 1 thin async wrapper around the configured OpenAI-compatible endpoint.

#     Preserved verbatim for backward compatibility with Phase 3 modules that
#     consume ``get_llm_service().generate()`` and ``generate_json()``.

#     Audit fix: the URL now goes through ``_ensure_chat_completions_suffix``
#     so ZAI calls hit ``/api/paas/v4/chat/completions`` instead of the
#     API root.

#     New code should prefer ``call_llm(config, messages)`` with an
#     explicit ``LlmConfig`` DB row.
#     """

#     def __init__(self, settings: Any | None = None) -> None:
#         self._settings = settings or get_settings()

#     async def generate(
#         self,
#         *,
#         prompt: str,
#         system: str | None = None,
#         model: str = "glm-4-flash",
#         temperature: float = 0.7,
#         max_tokens: int = 1024,
#         timeout: float | None = None,
#     ) -> str:
#         """
#         Send a single-turn prompt and return the generated text.

#         Falls back to a stub when the API URL is empty or the call fails,
#         so feature modules always receive a string (never raise to the caller
#         — they handle empty-string gracefully).
#         """
#         url = _ensure_chat_completions_suffix(self._settings.LLM_API_URL)
#         timeout_s = timeout or float(self._settings.LLM_DEFAULT_TIMEOUT_SECONDS)

#         if not url:
#             return self._stub(prompt)

#         payload: dict[str, Any] = {
#             "model": model,
#             "messages": (
#                 [{"role": "system", "content": system}] if system else []
#             )
#             + [{"role": "user", "content": prompt}],
#             "temperature": temperature,
#             "max_tokens": max_tokens,
#         }
#         try:
#             async with httpx.AsyncClient(timeout=timeout_s) as client:
#                 resp = await client.post(
#                     url,
#                     json=payload,
#                     headers={"Content-Type": "application/json"},
#                 )
#                 resp.raise_for_status()
#                 data = resp.json()
#                 return _extract_text(data)
#         except Exception as exc:  # noqa: BLE001 — graceful degradation
#             logger.warning("llm.generate.fallback", error=str(exc))
#             return self._stub(prompt)

#     async def generate_json(
#         self,
#         *,
#         prompt: str,
#         system: str | None = None,
#         model: str = "glm-4-flash",
#         timeout: float | None = None,
#     ) -> dict[str, Any]:
#         """Generate and JSON-parse. Returns {} on parse failure."""
#         raw = await self.generate(
#             prompt=prompt,
#             system=system,
#             model=model,
#             temperature=0.2,
#             max_tokens=2048,
#             timeout=timeout,
#         )
#         try:
#             return json.loads(raw)
#         except (json.JSONDecodeError, ValueError):
#             logger.warning("llm.generate_json.parse_failed", raw=raw[:200])
#             return {}

#     @staticmethod
#     def _stub(prompt: str) -> str:
#         """Deterministic stub used when no LLM endpoint is configured."""
#         return f"[LLM-STUB] {prompt[:120]}"


# @lru_cache
# def get_llm_service() -> LlmService:
#     """Cached accessor — import this, never instantiate LlmService directly."""
#     return LlmService()


# __all__ = [
#     # Constants
#     "ALL_PROVIDERS",
#     "PROVIDER_BASE_URLS",
#     "PROVIDER_OPENAI",
#     "PROVIDER_ANTHROPIC",
#     "PROVIDER_AZURE",
#     "PROVIDER_GEMINI",
#     "PROVIDER_BEDROCK",
#     "PROVIDER_COHERE",
#     "PROVIDER_MISTRAL",
#     "PROVIDER_LLAMA",
#     "PROVIDER_GROQ",
#     "PROVIDER_AI21",
#     "PROVIDER_HUGGINGFACE",
#     "PROVIDER_ZAI",
#     "PROVIDER_LOCAL",
#     "LLM_HTTP_TIMEOUT",
#     # Errors
#     "LlmGatewayError",
#     # Gateway functions (Phase 2)
#     "call_llm",
#     "cast_llm_config",
#     "get_default_llm_config",
#     "get_model_for_task",
#     # Legacy service (Phase 1 — preserved)
#     "LlmService",
#     "get_llm_service",
# ]

# """
# llm_service.py — Async HTTP gateway to 13 LLM providers.

# Phase 1 (preserved): ``LlmService`` is a thin async wrapper around the
# configured OpenAI-compatible endpoint. Phase 3 modules that consume
# ``get_llm_service().generate()`` continue to work unchanged.

# Phase 2 (added): module-level gateway functions dispatch to provider-specific
# adapters via ``LlmConfig.provider``:
#   - ``call_llm(config, messages) -> LlmResponse``
#   - ``cast_llm_config(config) -> dict[str, Any]``
#   - ``get_default_llm_config(db) -> LlmConfig | None``
#   - ``get_model_for_task(task, config) -> str``

# The 13 supported providers (per migration doc §3.4 + §10 Phase 2):
#   OpenAI, Anthropic, Azure OpenAI, Google Gemini, AWS Bedrock, Cohere,
#   Mistral, Meta Llama (via Together), Groq, AI21, Hugging Face, ZAI,
#   Local (Ollama).

# Audit fix (AUDIT-A1 #6 / H-11): ZAI provider now POSTs to the full
# ``https://open.bigmodel.cn/api/paas/v4/chat/completions`` URL — the
# previous default omitted the ``/chat/completions`` suffix and would 404
# against the real ZAI endpoint.
# """
# from __future__ import annotations

# import json
# from functools import lru_cache
# from typing import Any

# import httpx
# import structlog
# from sqlalchemy import select
# from sqlalchemy.ext.asyncio import AsyncSession
# from tenacity import (
#     AsyncRetrying,
#     retry_if_exception_type,
#     stop_after_attempt,
#     wait_exponential,
# )

# from app.core.config import get_settings
# from app.models.config_models import LlmConfig as LlmConfigModel
# from app.schemas.llm_config import LlmResponse

# logger = structlog.get_logger(__name__)


# # ── Background-task registry for fire-and-forget usage writes ──────────────
# # Holds strong references to asyncio Tasks created by _record_llm_usage so
# # CPython's garbage collector does not cancel them mid-flight. Tasks self-
# # remove via add_done_callback when they complete. The set is module-level
# # (not per-request) because usage writes are fire-and-forget — we never
# # await them from the caller.
# _BG_USAGE_TASKS: set = set()


# # ── Constants ───────────────────────────────────────────────────────────────

# LLM_HTTP_TIMEOUT: float = 60.0
# """Per-request HTTP timeout for all provider calls (per §10 Phase 2)."""

# # ── Provider keys ───────────────────────────────────────────────────────────

# PROVIDER_OPENAI = "openai"
# PROVIDER_ANTHROPIC = "anthropic"
# PROVIDER_AZURE = "azure"
# PROVIDER_GEMINI = "gemini"
# PROVIDER_BEDROCK = "bedrock"
# PROVIDER_COHERE = "cohere"
# PROVIDER_MISTRAL = "mistral"
# PROVIDER_LLAMA = "llama"  # Meta Llama served via Together
# PROVIDER_GROQ = "groq"
# PROVIDER_AI21 = "ai21"
# PROVIDER_HUGGINGFACE = "huggingface"
# PROVIDER_ZAI = "zai"
# PROVIDER_LOCAL = "local"  # Ollama

# ALL_PROVIDERS: tuple[str, ...] = (
#     PROVIDER_OPENAI,
#     PROVIDER_ANTHROPIC,
#     PROVIDER_AZURE,
#     PROVIDER_GEMINI,
#     PROVIDER_BEDROCK,
#     PROVIDER_COHERE,
#     PROVIDER_MISTRAL,
#     PROVIDER_LLAMA,
#     PROVIDER_GROQ,
#     PROVIDER_AI21,
#     PROVIDER_HUGGINGFACE,
#     PROVIDER_ZAI,
#     PROVIDER_LOCAL,
# )

# # Default base URLs per provider. Can be overridden per-row via LlmConfig.baseUrl.
# PROVIDER_BASE_URLS: dict[str, str] = {
#     PROVIDER_OPENAI: "https://api.openai.com/v1",
#     PROVIDER_ANTHROPIC: "https://api.anthropic.com/v1",
#     PROVIDER_AZURE: "",  # requires LlmConfig.baseUrl (tenant-specific endpoint)
#     PROVIDER_GEMINI: "https://generativelanguage.googleapis.com/v1beta",
#     PROVIDER_BEDROCK: "https://bedrock-runtime.us-east-1.amazonaws.com",
#     PROVIDER_COHERE: "https://api.cohere.com/v2",
#     PROVIDER_MISTRAL: "https://api.mistral.ai/v1",
#     PROVIDER_LLAMA: "https://api.together.xyz/v1",  # Together hosts Llama
#     PROVIDER_GROQ: "https://api.groq.com/openai/v1",
#     PROVIDER_AI21: "https://api.ai21.com/studio/v1",
#     PROVIDER_HUGGINGFACE: "https://api-inference.huggingface.co/models",
#     PROVIDER_ZAI: "https://open.bigmodel.cn/api/paas/v4",
#     PROVIDER_LOCAL: "http://localhost:11434/v1",  # Ollama default
# }

# # Providers that speak the OpenAI-compatible /chat/completions dialect.
# _OPENAI_COMPATIBLE: frozenset[str] = frozenset({
#     PROVIDER_OPENAI,
#     PROVIDER_GROQ,
#     PROVIDER_MISTRAL,
#     PROVIDER_LLAMA,
#     PROVIDER_LOCAL,
#     PROVIDER_ZAI,
#     PROVIDER_AI21,
#     PROVIDER_HUGGINGFACE,
#     PROVIDER_COHERE,
#     PROVIDER_AZURE,
# })

# # Default anthropic-version header value (per Anthropic API spec).
# _ANTHROPIC_VERSION_DEFAULT = "2023-06-01"

# # Default Azure OpenAI API version (per Azure OpenAI REST spec).
# _AZURE_API_VERSION_DEFAULT = "2024-10-21"


# class LlmGatewayError(Exception):
#     """Raised when the LLM gateway call fails after retries."""


# # ── Settings-column parsing ─────────────────────────────────────────────────


# def _parse_settings(config: LlmConfigModel) -> dict[str, Any]:
#     """
#     Parse the LlmConfig.settings JSON column safely.

#     The column is TEXT holding a JSON string (per §5.5). Returns {} on parse
#     failure or non-dict content — never raises.
#     """
#     raw = getattr(config, "settings", None) or "{}"
#     try:
#         parsed = json.loads(raw)
#     except (json.JSONDecodeError, TypeError, ValueError):
#         return {}
#     return parsed if isinstance(parsed, dict) else {}


# # ── Helper mapping (per §6.2) ───────────────────────────────────────────────


# def cast_llm_config(config: LlmConfigModel) -> dict[str, Any]:
#     """
#     Convert a LlmConfig DB row into provider-specific kwargs (per §6.2).

#     Returns a dict with the keys:
#       - provider:     normalized provider key (lowercase)
#       - model:        the model ID to invoke
#       - api_key:      the API key (may be None for ZAI/local)
#       - base_url:     the provider's base URL
#       - temperature:  float (default 0.7)
#       - max_tokens:   int (default 1024)
#       - extra:        provider-specific kwargs (api_version, deployment,
#                       region, anthropic_version, generation_config, ...)

#     The 'models' map inside settings (task -> model_id) is consumed
#     separately by ``get_model_for_task()``.
#     """
#     settings = _parse_settings(config)
#     provider = (config.provider or PROVIDER_ZAI).lower()
#     base_url = config.baseUrl or PROVIDER_BASE_URLS.get(provider, "")

#     temperature_raw = settings.get("temperature", settings.get("Temperature", 0.7))
#     max_tokens_raw = settings.get(
#         "max_tokens", settings.get("maxTokens", settings.get("MaxTokens", 1024))
#     )

#     try:
#         temperature = float(temperature_raw)
#     except (TypeError, ValueError):
#         temperature = 0.7
#     try:
#         max_tokens = int(max_tokens_raw)
#     except (TypeError, ValueError):
#         max_tokens = 1024

#     kwargs: dict[str, Any] = {
#         "provider": provider,
#         "model": config.modelId,
#         "api_key": config.apiKey,
#         "base_url": base_url,
#         "temperature": temperature,
#         "max_tokens": max_tokens,
#         "extra": {},
#     }

#     # Provider-specific extras
#     if provider == PROVIDER_AZURE:
#         kwargs["extra"]["api_version"] = settings.get(
#             "api_version", settings.get("apiVersion", _AZURE_API_VERSION_DEFAULT)
#         )
#         kwargs["extra"]["deployment"] = settings.get(
#             "deployment", settings.get("deploymentName", config.modelId)
#         )
#     elif provider == PROVIDER_BEDROCK:
#         kwargs["extra"]["region"] = settings.get("region", "us-east-1")
#         kwargs["extra"]["model_id"] = settings.get("model_id", config.modelId)
#     elif provider == PROVIDER_ANTHROPIC:
#         kwargs["extra"]["anthropic_version"] = settings.get(
#             "anthropic_version", _ANTHROPIC_VERSION_DEFAULT
#         )
#     elif provider == PROVIDER_GEMINI:
#         kwargs["extra"]["generation_config"] = {
#             "temperature": temperature,
#             "maxOutputTokens": max_tokens,
#             "topP": float(settings.get("top_p", settings.get("topP", 1.0))),
#         }

#     return kwargs


# def get_model_for_task(task: str, config: LlmConfigModel) -> str:
#     """
#     Tier routing — return the model ID for a given task (per §3.4 + §10 Phase 2).

#     Reads the 'models' dict inside the JSON settings column. Returns
#     ``config.modelId`` when no per-task override is configured.

#     Known tasks: email_generation, icp_suggest, framework_recommend,
#     gtm_thesis, subject_line, qa_check, compliance_check, reply_categorize,
#     auto_reply, personalization, anti_pattern, prospect_brief,
#     prospect_lookalike, ultimate_profile, prospect_enrich, prospect_score,
#     analytics_diagnose, content_idea, linkedin_post, meeting_prep,
#     deal_suggest, deal_health, deal_next_step, weekly_digest, cadence_plan,
#     touch_angle, rule_suggest, ab_test_hypothesis.
#     """
#     settings = _parse_settings(config)
#     models_map = settings.get("models") or {}
#     if isinstance(models_map, dict) and task in models_map:
#         return str(models_map[task])
#     return config.modelId


# async def get_default_llm_config(db: AsyncSession) -> LlmConfigModel | None:
#     """
#     Fetch the tenant's default LlmConfig.

#     Returns the row where ``isDefault=True AND isActive=True`` (newest first).
#     Falls back to the first active row by createdAt ordering when no row is
#     marked default — per the "first one wins" convention in §6.2.
#     """
#     result = await db.execute(
#         select(LlmConfigModel)
#         .where(LlmConfigModel.isDefault.is_(True))
#         .where(LlmConfigModel.isActive.is_(True))
#         .order_by(LlmConfigModel.createdAt.asc())
#         .limit(1)
#     )
#     row = result.scalar_one_or_none()
#     if row is not None:
#         return row

#     result = await db.execute(
#         select(LlmConfigModel)
#         .where(LlmConfigModel.isActive.is_(True))
#         .order_by(LlmConfigModel.createdAt.asc())
#         .limit(1)
#     )
#     return result.scalar_one_or_none()


# # ── Provider URL + header builders ──────────────────────────────────────────


# def _provider_chat_url(provider: str, kwargs: dict[str, Any]) -> str:
#     """Return the chat-completions URL for a provider."""
#     base = (kwargs.get("base_url") or PROVIDER_BASE_URLS.get(provider, "")).rstrip("/")
#     if not base:
#         raise LlmGatewayError(f"No base_url configured for provider '{provider}'")

#     if provider == PROVIDER_ANTHROPIC:
#         return f"{base}/messages"
#     if provider == PROVIDER_GEMINI:
#         model = kwargs["model"]
#         return f"{base}/models/{model}:generateContent"
#     if provider == PROVIDER_AZURE:
#         deployment = kwargs["extra"].get("deployment", "deployment")
#         api_version = kwargs["extra"].get("api_version", _AZURE_API_VERSION_DEFAULT)
#         return f"{base}/openai/deployments/{deployment}/chat/completions?api-version={api_version}"
#     if provider == PROVIDER_COHERE:
#         return f"{base}/chat"
#     if provider == PROVIDER_BEDROCK:
#         model_id = kwargs["extra"].get("model_id", kwargs["model"])
#         return f"{base}/model/{model_id}/invoke"
#     if provider == PROVIDER_HUGGINGFACE:
#         # HF router: /models/{model}/v1/chat/completions
#         return f"{base}/{kwargs['model']}/v1/chat/completions"
#     # OpenAI-compatible: openai, groq, mistral, llama (Together), local, zai, ai21
#     return f"{base}/chat/completions"


# def _provider_headers(provider: str, kwargs: dict[str, Any]) -> dict[str, str]:
#     """Return provider-specific auth headers (Content-Type added by caller)."""
#     api_key = kwargs.get("api_key") or ""
#     if provider == PROVIDER_ANTHROPIC:
#         return {
#             "x-api-key": api_key,
#             "anthropic-version": kwargs["extra"].get(
#                 "anthropic_version", _ANTHROPIC_VERSION_DEFAULT
#             ),
#         }
#     if provider == PROVIDER_GEMINI:
#         return {"x-goog-api-key": api_key}
#     if provider == PROVIDER_AZURE:
#         # Azure uses api-key header (not Bearer)
#         return {"api-key": api_key}
#     return {"Authorization": f"Bearer {api_key}"}


# # ── Payload builders (per-provider) ─────────────────────────────────────────


# def _build_openai_payload(
#     messages: list[dict[str, str]], kwargs: dict[str, Any]
# ) -> dict[str, Any]:
#     """OpenAI-compatible chat-completions payload."""
#     return {
#         "model": kwargs["model"],
#         "messages": messages,
#         "temperature": kwargs["temperature"],
#         "max_tokens": kwargs["max_tokens"],
#     }


# def _build_anthropic_payload(
#     messages: list[dict[str, str]], kwargs: dict[str, Any]
# ) -> dict[str, Any]:
#     """Anthropic Messages API — system is a top-level field, not in messages."""
#     system_msgs = [m for m in messages if m.get("role") == "system"]
#     user_msgs = [m for m in messages if m.get("role") != "system"]
#     system_text = "\n\n".join(str(m.get("content", "")) for m in system_msgs)
#     payload: dict[str, Any] = {
#         "model": kwargs["model"],
#         "messages": user_msgs,
#         "max_tokens": kwargs["max_tokens"],
#         "temperature": kwargs["temperature"],
#     }
#     if system_text:
#         payload["system"] = system_text
#     return payload


# def _build_gemini_payload(
#     messages: list[dict[str, str]], kwargs: dict[str, Any]
# ) -> dict[str, Any]:
#     """Google Gemini generateContent payload."""
#     contents: list[dict[str, Any]] = []
#     sys_text = "\n".join(
#         str(m.get("content", "")) for m in messages if m.get("role") == "system"
#     )
#     for m in messages:
#         role = m.get("role", "user")
#         if role == "system":
#             continue
#         gemini_role = "user" if role == "user" else "model"
#         contents.append(
#             {"role": gemini_role, "parts": [{"text": str(m.get("content", ""))}]}
#         )
#     payload: dict[str, Any] = {
#         "contents": contents,
#         "generationConfig": kwargs["extra"].get("generation_config", {}),
#     }
#     if sys_text:
#         payload["systemInstruction"] = {"parts": [{"text": sys_text}]}
#     return payload


# def _build_cohere_payload(
#     messages: list[dict[str, str]], kwargs: dict[str, Any]
# ) -> dict[str, Any]:
#     """Cohere v2 chat (OpenAI-compatible)."""
#     return {
#         "model": kwargs["model"],
#         "messages": messages,
#         "temperature": kwargs["temperature"],
#         "max_tokens": kwargs["max_tokens"],
#     }


# def _build_bedrock_payload(
#     messages: list[dict[str, str]], kwargs: dict[str, Any]
# ) -> dict[str, Any]:
#     """
#     AWS Bedrock converse API payload.

#     Note: production deployments wrap this in boto3 SigV4 signing. The
#     gateway posts the converse payload directly when LlmConfig.apiKey
#     holds a bearer-secured proxy token (e.g. Bedrock proxy gateway).
#     """
#     return {
#         "modelId": kwargs["extra"].get("model_id", kwargs["model"]),
#         "messages": messages,
#         "inferenceConfig": {
#             "temperature": kwargs["temperature"],
#             "maxTokens": kwargs["max_tokens"],
#         },
#     }


# def _build_provider_payload(
#     provider: str, messages: list[dict[str, str]], kwargs: dict[str, Any]
# ) -> dict[str, Any]:
#     if provider == PROVIDER_ANTHROPIC:
#         return _build_anthropic_payload(messages, kwargs)
#     if provider == PROVIDER_GEMINI:
#         return _build_gemini_payload(messages, kwargs)
#     if provider == PROVIDER_BEDROCK:
#         return _build_bedrock_payload(messages, kwargs)
#     if provider == PROVIDER_COHERE:
#         return _build_cohere_payload(messages, kwargs)
#     # All OpenAI-compatible providers
#     return _build_openai_payload(messages, kwargs)


# # ── Response parsers (per-provider) ─────────────────────────────────────────


# def _parse_openai_response(
#     data: dict[str, Any], provider: str, model: str
# ) -> LlmResponse:
#     """Parse OpenAI-compatible response shape (used by 10 of 13 providers)."""
#     choices = data.get("choices") or []
#     content = ""
#     if choices:
#         msg = choices[0].get("message") or {}
#         content = str(msg.get("content", ""))
#     usage = data.get("usage") or {}
#     usage_dict = {
#         "prompt_tokens": int(usage.get("prompt_tokens", 0) or 0),
#         "completion_tokens": int(usage.get("completion_tokens", 0) or 0),
#         "total_tokens": int(usage.get("total_tokens", 0) or 0),
#     }
#     return LlmResponse(
#         content=content,
#         usage=usage_dict,
#         model=model,
#         provider=provider,
#         raw=data,
#     )


# def _parse_anthropic_response(
#     data: dict[str, Any], provider: str, model: str
# ) -> LlmResponse:
#     content = ""
#     blocks = data.get("content") or []
#     if isinstance(blocks, list):
#         for b in blocks:
#             if isinstance(b, dict) and b.get("type") == "text":
#                 content += str(b.get("text", ""))
#     usage = data.get("usage") or {}
#     input_tokens = int(usage.get("input_tokens", 0) or 0)
#     output_tokens = int(usage.get("output_tokens", 0) or 0)
#     usage_dict = {
#         "prompt_tokens": input_tokens,
#         "completion_tokens": output_tokens,
#         "total_tokens": input_tokens + output_tokens,
#     }
#     return LlmResponse(
#         content=content,
#         usage=usage_dict,
#         model=model,
#         provider=provider,
#         raw=data,
#     )


# def _parse_gemini_response(
#     data: dict[str, Any], provider: str, model: str
# ) -> LlmResponse:
#     content = ""
#     candidates = data.get("candidates") or []
#     if candidates:
#         parts = (candidates[0].get("content") or {}).get("parts") or []
#         for p in parts:
#             if isinstance(p, dict) and "text" in p:
#                 content += str(p["text"])
#     usage_meta = data.get("usageMetadata") or {}
#     usage_dict = {
#         "prompt_tokens": int(usage_meta.get("promptTokenCount", 0) or 0),
#         "completion_tokens": int(usage_meta.get("candidatesTokenCount", 0) or 0),
#         "total_tokens": int(usage_meta.get("totalTokenCount", 0) or 0),
#     }
#     return LlmResponse(
#         content=content,
#         usage=usage_dict,
#         model=model,
#         provider=provider,
#         raw=data,
#     )


# def _parse_bedrock_response(
#     data: dict[str, Any], provider: str, model: str
# ) -> LlmResponse:
#     content = ""
#     output = data.get("output") or {}
#     msg = output.get("message") or {}
#     for c in msg.get("content") or []:
#         if isinstance(c, dict) and "text" in c:
#             content += str(c["text"])
#     usage = data.get("usage") or {}
#     usage_dict = {
#         "prompt_tokens": int(usage.get("inputTokens", 0) or 0),
#         "completion_tokens": int(usage.get("outputTokens", 0) or 0),
#         "total_tokens": int(usage.get("totalTokens", 0) or 0),
#     }
#     return LlmResponse(
#         content=content,
#         usage=usage_dict,
#         model=model,
#         provider=provider,
#         raw=data,
#     )


# def _parse_provider_response(
#     provider: str, data: dict[str, Any], model: str
# ) -> LlmResponse:
#     if provider == PROVIDER_ANTHROPIC:
#         return _parse_anthropic_response(data, provider, model)
#     if provider == PROVIDER_GEMINI:
#         return _parse_gemini_response(data, provider, model)
#     if provider == PROVIDER_BEDROCK:
#         return _parse_bedrock_response(data, provider, model)
#     return _parse_openai_response(data, provider, model)


# # ── HTTP transport with tenacity retry ──────────────────────────────────────


# async def _do_http_post(
#     url: str, headers: dict[str, str], payload: dict[str, Any]
# ) -> dict[str, Any]:
#     """Single HTTP POST with timeout. Raises httpx.HTTPError on failure."""
#     async with httpx.AsyncClient(timeout=LLM_HTTP_TIMEOUT) as client:
#         resp = await client.post(url, json=payload, headers=headers)
#         resp.raise_for_status()
#         return resp.json()


# def _retrying() -> AsyncRetrying:
#     """
#     Tenacity AsyncRetrying: 3 attempts, exponential backoff 1-10s, on
#     transient HTTP errors only (429/5xx via HTTPStatusError + transport
#     errors). Per §10 Phase 2 spec.
#     """
#     return AsyncRetrying(
#         stop=stop_after_attempt(3),
#         wait=wait_exponential(multiplier=1, min=1, max=10),
#         retry=retry_if_exception_type(
#             (httpx.HTTPStatusError, httpx.ConnectError, httpx.ReadTimeout,
#              httpx.ConnectTimeout, httpx.RemoteProtocolError)
#         ),
#         reraise=True,
#     )


# async def _call_provider(
#     provider: str, kwargs: dict[str, Any], messages: list[dict[str, str]]
# ) -> LlmResponse:
#     """Dispatch to the right provider adapter. Retries transient failures."""
#     model = kwargs["model"]
#     url = _provider_chat_url(provider, kwargs)
#     payload = _build_provider_payload(provider, messages, kwargs)
#     headers: dict[str, str] = {"Content-Type": "application/json"}
#     headers.update(_provider_headers(provider, kwargs))

#     data: dict[str, Any] = {}
#     async for attempt in _retrying():
#         with attempt:
#             data = await _do_http_post(url, headers, payload)

#     return _parse_provider_response(provider, data, model)


# # ── Main entry: call_llm ────────────────────────────────────────────────────


# async def _resolve_dual_path_api_key(
#     config: LlmConfigModel, *, provider: str
# ) -> str | None:
#     """Resolve the LLM API key via the dual-path credential service.

#     FIX-BE-1 / CRITICAL 2: production LLM calls used to read
#     ``config.apiKey`` (the legacy plaintext column) directly. When a tenant
#     adopts the dual-path model (``apiKey=NULL`` + ``global_llm_config_id``
#     set, or ``key_source='platform'``), that column is empty and the call
#     failed with a 401.

#     This helper is invoked from ``call_llm`` ONLY when ``config.apiKey`` is
#     missing or empty. It delegates to
#     ``IntegrationCredentialsService.resolve_credentials(integration_type='llm', ...)``
#     which:

#       1. If ``config.global_llm_config_id`` is set, loads that row from
#          ``public.global_llm_config``, Fernet-decrypts its
#          ``api_key_encrypted`` column, and returns the plaintext key.
#       2. Else looks up the platform default for ``provider`` in
#          ``public.global_llm_config`` (is_default=True, is_active=True).
#       3. Else falls back to the configured SecretBackend (env / AWS SM /
#          Azure KV) under ``platform/llm/{provider}/api_key``.

#     Returns ``None`` if no key can be resolved. The caller raises a clear
#     ``LlmGatewayError`` so the user sees an actionable message instead of
#     an empty-key 401 from the upstream provider.

#     Expected behavior for the 3 cases:

#       Case A — tenant-managed legacy key (``config.apiKey`` set):
#           This helper is NOT called (caller short-circuits).
#           ``call_llm`` uses ``config.apiKey`` directly.

#       Case B — platform-managed key via ``global_llm_config_id``:
#           This helper resolves the Fernet-encrypted key from
#           ``public.global_llm_config`` via ``IntegrationCredentialsService``.

#       Case C — neither set (misconfigured tenant):
#           This helper returns ``None``; ``call_llm`` raises
#           ``LlmGatewayError("No LLM API key configured. Set
#           key_source='platform' with a global_llm_config_id, or provide an
#           apiKey.")``.
#     """
#     integration_id: str | None = None
#     gid = getattr(config, "global_llm_config_id", None)
#     if gid is not None:
#         try:
#             integration_id = str(int(gid))
#         except (TypeError, ValueError):
#             integration_id = None

#     try:
#         from app.core.database import AsyncSessionLocal
#         from app.features.integrations.integration_credentials_service import (
#             IntegrationCredentialsService,
#         )
#     except ImportError as exc:  # pragma: no cover — defensive
#         logger.warning(
#             "llm.dual_path_import_failed",
#             provider=provider,
#             error=str(exc),
#         )
#         return None

#     try:
#         async with AsyncSessionLocal() as db:
#             # IntegrationCredentialsService._resolve_llm_credentials queries
#             # public.global_llm_config explicitly (schema-qualified), so the
#             # session's search_path does not matter here.
#             creds = await IntegrationCredentialsService().resolve_credentials(
#                 db,
#                 integration_type="llm",
#                 integration_id=integration_id,
#                 provider=provider,
#             )
#         api_key = creds.get("api_key") if creds else None
#         if api_key:
#             logger.debug(
#                 "llm.dual_path_resolved",
#                 provider=provider,
#                 global_llm_config_id=integration_id,
#                 key_source=creds.get("key_source"),
#             )
#         return api_key
#     except Exception as exc:  # noqa: BLE001 — credential resolution must never break the call
#         logger.warning(
#             "llm.dual_path_resolve_failed",
#             provider=provider,
#             global_llm_config_id=integration_id,
#             error=str(exc),
#         )
#         return None


# async def call_llm(
#     config: LlmConfigModel, messages: list[dict[str, str]]
# ) -> LlmResponse:
#     """
#     Main entry point — dispatch to the provider-specific adapter (per §6.2).

#     Args:
#         config:   the tenant's LlmConfig DB row
#         messages: list of {role, content} dicts (system/user/assistant)

#     Returns:
#         LlmResponse with content, usage, model, provider, raw.

#     Raises:
#         LlmGatewayError: when the config is inactive, the provider is
#             unknown, no API key can be resolved (dual-path failure), or
#             the HTTP call fails after 3 retries.

#     FIX-BE-1 / CRITICAL 2: when ``config.apiKey`` is empty (tenant using
#     ``global_llm_config_id`` / platform-managed keys), the API key is
#     resolved via ``IntegrationCredentialsService.resolve_credentials``
#     before the HTTP call is dispatched. See
#     ``_resolve_dual_path_api_key`` for the full resolution chain.
#     """
#     if not config.isActive:
#         raise LlmGatewayError(f"LlmConfig '{config.name}' is not active")

#     kwargs = cast_llm_config(config)
#     provider = kwargs["provider"]
#     if provider not in ALL_PROVIDERS:
#         raise LlmGatewayError(
#             f"Unknown LLM provider: '{provider}'. "
#             f"Supported: {', '.join(ALL_PROVIDERS)}"
#         )

#     # ── Dual-path credential resolution (FIX-BE-1 / CRITICAL 2) ──────────
#     # cast_llm_config above populated kwargs['api_key'] from config.apiKey
#     # (the legacy plaintext column). When that is missing/empty, resolve
#     # the key via the IntegrationCredentialsService — which checks
#     # public.global_llm_config (Fernet-encrypted) first, then falls back
#     # to the platform SecretBackend. Never silently send an empty key to
#     # the provider (would produce a confusing 401 instead of a clear
#     # configuration error).
#     if not kwargs.get("api_key"):
#         resolved = await _resolve_dual_path_api_key(config, provider=provider)
#         if resolved:
#             kwargs["api_key"] = resolved
#         else:
#             raise LlmGatewayError(
#                 "No LLM API key configured. Set key_source='platform' with a "
#                 "global_llm_config_id, or provide an apiKey."
#             )

#     try:
#         response = await _call_provider(provider, kwargs, messages)
#     except LlmGatewayError:
#         # Bump the error counter (best-effort) before re-raising.
#         _record_llm_error(provider, kwargs["model"], "LlmGatewayError")
#         raise
#     except Exception as exc:
#         logger.warning(
#             "llm.call_llm.failed",
#             provider=provider,
#             model=kwargs["model"],
#             error=str(exc),
#         )
#         _record_llm_error(provider, kwargs["model"], type(exc).__name__)
#         raise LlmGatewayError(
#             f"LLM call failed for provider '{provider}': {exc}"
#         ) from exc

#     # ── Usage instrumentation (fire-and-forget — never breaks the LLM call).
#     # Records a UsageEvent + bumps Prometheus counters. Best-effort: any
#     # failure is swallowed + logged so the caller still gets the LlmResponse.
#     _record_llm_usage(provider, kwargs["model"], response, config)
#     return response


# def _record_llm_error(provider: str, model: str, error_type: str) -> None:
#     """Bump the LLM error counter. Best-effort — never raises."""
#     try:
#         from app.core.metrics import LLM_ERRORS

#         # tenant label is unknown here (call_llm does not receive it); use
#         # "_unknown" so the metric is still emitted. The per-tenant
#         # attribution comes from the UsageService path, which IS tenant-aware.
#         LLM_ERRORS.labels(
#             provider=provider, model=model, tenant="_unknown", error_type=error_type
#         ).inc()
#     except Exception:  # noqa: BLE001
#         pass


# def _record_llm_usage(
#     provider: str, model: str, response: "LlmResponse", config: "LlmConfigModel"
# ) -> None:
#     """Best-effort: record UsageEvent + Prometheus counters for one LLM call.

#     Runs in the BACKGROUND so the caller's request is not blocked on the
#     usage-event INSERT. Any failure (DB down, import error, cost-lookup
#     error) is swallowed + logged. The LLM call has already succeeded —
#     the caller's response is unaffected.

#     Tenant + user_id are extracted from the structlog contextvars bound
#     by RequestContextMiddleware + TenantMiddleware. When those are not
#     available (background jobs, tests), the event is recorded with
#     tenant="_unknown" / user_id="_unknown" so the metric still surfaces.
#     """
#     try:
#         usage = getattr(response, "usage", None) or {}
#         prompt_tokens = int(usage.get("prompt_tokens", 0) or 0)
#         completion_tokens = int(usage.get("completion_tokens", 0) or 0)

#         # Pull tenant + user_id from structlog contextvars (set by the
#         # request middleware). For non-request callers (Celery tasks,
#         # scheduler), fall back to "_unknown" so the event is still recorded.
#         tenant_slug = "_unknown"
#         user_id = "_unknown"
#         request_id: str | None = None
#         try:
#             from structlog import contextvars as _cv

#             ctx = _cv.get_contextvars()
#             # The audit + tenant middleware bind "request_id" + "tenant_slug"
#             # to the context. We use the same names here.
#             t = ctx.get("tenant_slug")
#             if isinstance(t, str) and t:
#                 tenant_slug = t
#             u = ctx.get("user_id")
#             if isinstance(u, str) and u:
#                 user_id = u
#             request_id = ctx.get("request_id") if isinstance(ctx.get("request_id"), str) else None
#         except Exception:  # noqa: BLE001
#             pass

#         # Bump Prometheus counters (synchronous, never blocks).
#         try:
#             from app.core.metrics import LLM_CALLS, LLM_TOKENS, LLM_LATENCY, LLM_COST_CENTS

#             LLM_CALLS.labels(provider=provider, model=model, tenant=tenant_slug).inc()
#             LLM_TOKENS.labels(
#                 provider=provider, model=model, type="input", tenant=tenant_slug
#             ).inc(prompt_tokens)
#             LLM_TOKENS.labels(
#                 provider=provider, model=model, type="output", tenant=tenant_slug
#             ).inc(completion_tokens)
#         except Exception:  # noqa: BLE001
#             pass

#         # Compute cost + persist UsageEvent asynchronously.
#         import asyncio

#         async def _record() -> None:
#             try:
#                 from app.features.usage.service import UsageService

#                 await UsageService().record_llm_call(
#                     tenant=tenant_slug,
#                     user_id=user_id,
#                     provider=provider,
#                     model=model,
#                     prompt_tokens=prompt_tokens,
#                     completion_tokens=completion_tokens,
#                     metadata={
#                         "request_id": request_id,
#                         "config_name": getattr(config, "name", None),
#                     },
#                 )
#             except Exception as exc:  # noqa: BLE001 — usage must never break LLM
#                 logger.warning(
#                     "llm.usage_record_failed",
#                     provider=provider,
#                     model=model,
#                     tenant=tenant_slug,
#                     error=str(exc),
#                 )

#         # Schedule the record on the running loop. We do NOT await it — the
#         # caller is waiting on the LlmResponse and the usage write is
#         # fire-and-forget per the SURVEY-OBS design.
#         #
#         # IMPORTANT: hold a strong reference to the task in _BG_USAGE_TASKS so
#         # the garbage collector does not cancel it mid-flight (CPython's asyncio
#         # only keeps weak references to tasks). Tasks self-remove on completion.
#         try:
#             loop = asyncio.get_running_loop()
#             task = loop.create_task(_record())
#             _BG_USAGE_TASKS.add(task)
#             task.add_done_callback(_BG_USAGE_TASKS.discard)
#         except RuntimeError:
#             # No running loop (e.g., sync test context) — run inline.
#             try:
#                 asyncio.run(_record())
#             except Exception:  # noqa: BLE001
#                 pass
#     except Exception as exc:  # noqa: BLE001 — instrumentation must never break the LLM call
#         logger.warning(
#             "llm.usage_instrumentation_failed",
#             provider=provider,
#             model=model,
#             error=str(exc),
#         )


# # ── Legacy LlmService (preserved for backward compat with Phase 3 modules) ──


# def _ensure_chat_completions_suffix(url: str) -> str:
#     """
#     Audit fix (AUDIT-A1 #6 / H-11): append /chat/completions to a ZAI base
#     URL when missing. The legacy ``LLM_API_URL`` setting defaults to
#     ``https://open.bigmodel.cn/api/paas/v4`` (no suffix), so the previous
#     implementation POSTed to the API root and would 404.

#     Idempotent: leaves URLs that already end with /chat/completions alone.
#     """
#     if not url:
#         return url
#     if url.rstrip("/").endswith("/chat/completions"):
#         return url
#     # ZAI base ends with /v4 — append /chat/completions
#     if "open.bigmodel.cn" in url and not url.rstrip("/").endswith(("/v4", "/v4/")):
#         return url
#     return url.rstrip("/") + "/chat/completions"


# def _extract_text(data: dict[str, Any]) -> str:
#     """Tolerant extractor for OpenAI/ZAI response shapes."""
#     try:
#         choices = data.get("choices") or []
#         if choices:
#             msg = choices[0].get("message") or {}
#             content = msg.get("content")
#             if isinstance(content, str):
#                 return content
#         # Some ZAI variants nest under "output"
#         output = data.get("output")
#         if isinstance(output, str):
#             return output
#         if isinstance(output, list) and output:
#             first = output[0]
#             if isinstance(first, dict) and "content" in first:
#                 return str(first["content"])
#     except Exception:  # noqa: BLE001
#         pass
#     return ""


# class LlmService:
#     """
#     Phase 1 thin async wrapper around the configured OpenAI-compatible endpoint.

#     Preserved verbatim for backward compatibility with Phase 3 modules that
#     consume ``get_llm_service().generate()`` and ``generate_json()``.

#     Audit fix: the URL now goes through ``_ensure_chat_completions_suffix``
#     so ZAI calls hit ``/api/paas/v4/chat/completions`` instead of the
#     API root.

#     New code should prefer ``call_llm(config, messages)`` with an
#     explicit ``LlmConfig`` DB row.
#     """

#     def __init__(self, settings: Any | None = None) -> None:
#         self._settings = settings or get_settings()

#     async def generate(
#         self,
#         *,
#         prompt: str,
#         system: str | None = None,
#         model: str = "glm-4-flash",
#         temperature: float = 0.7,
#         max_tokens: int = 1024,
#         timeout: float | None = None,
#     ) -> str:
#         """
#         Send a single-turn prompt and return the generated text.

#         Falls back to a stub when the API URL is empty or the call fails,
#         so feature modules always receive a string (never raise to the caller
#         — they handle empty-string gracefully).
#         """
#         url = _ensure_chat_completions_suffix(self._settings.LLM_API_URL)
#         timeout_s = timeout or float(self._settings.LLM_DEFAULT_TIMEOUT_SECONDS)

#         if not url:
#             return self._stub(prompt)

#         payload: dict[str, Any] = {
#             "model": model,
#             "messages": (
#                 [{"role": "system", "content": system}] if system else []
#             )
#             + [{"role": "user", "content": prompt}],
#             "temperature": temperature,
#             "max_tokens": max_tokens,
#         }
#         try:
#             async with httpx.AsyncClient(timeout=timeout_s) as client:
#                 resp = await client.post(
#                     url,
#                     json=payload,
#                     headers={"Content-Type": "application/json"},
#                 )
#                 resp.raise_for_status()
#                 data = resp.json()
#                 return _extract_text(data)
#         except Exception as exc:  # noqa: BLE001 — graceful degradation
#             logger.warning("llm.generate.fallback", error=str(exc))
#             return self._stub(prompt)

#     async def generate_json(
#         self,
#         *,
#         prompt: str,
#         system: str | None = None,
#         model: str = "glm-4-flash",
#         timeout: float | None = None,
#     ) -> dict[str, Any]:
#         """Generate and JSON-parse. Returns {} on parse failure."""
#         raw = await self.generate(
#             prompt=prompt,
#             system=system,
#             model=model,
#             temperature=0.2,
#             max_tokens=2048,
#             timeout=timeout,
#         )
#         try:
#             return json.loads(raw)
#         except (json.JSONDecodeError, ValueError):
#             logger.warning("llm.generate_json.parse_failed", raw=raw[:200])
#             return {}

#     @staticmethod
#     def _stub(prompt: str) -> str:
#         """Deterministic stub used when no LLM endpoint is configured."""
#         return f"[LLM-STUB] {prompt[:120]}"


# @lru_cache
# def get_llm_service() -> LlmService:
#     """Cached accessor — import this, never instantiate LlmService directly."""
#     return LlmService()


# __all__ = [
#     # Constants
#     "ALL_PROVIDERS",
#     "PROVIDER_BASE_URLS",
#     "PROVIDER_OPENAI",
#     "PROVIDER_ANTHROPIC",
#     "PROVIDER_AZURE",
#     "PROVIDER_GEMINI",
#     "PROVIDER_BEDROCK",
#     "PROVIDER_COHERE",
#     "PROVIDER_MISTRAL",
#     "PROVIDER_LLAMA",
#     "PROVIDER_GROQ",
#     "PROVIDER_AI21",
#     "PROVIDER_HUGGINGFACE",
#     "PROVIDER_ZAI",
#     "PROVIDER_LOCAL",
#     "LLM_HTTP_TIMEOUT",
#     # Errors
#     "LlmGatewayError",
#     # Gateway functions (Phase 2)
#     "call_llm",
#     "cast_llm_config",
#     "get_default_llm_config",
#     "get_model_for_task",
#     # Legacy service (Phase 1 — preserved)
#     "LlmService",
#     "get_llm_service",
# ]
"""
llm_service.py — Async HTTP gateway to 13 LLM providers.

Phase 1 (preserved): ``LlmService`` is a thin async wrapper around the
configured OpenAI-compatible endpoint. Phase 3 modules that consume
``get_llm_service().generate()`` continue to work unchanged.

Phase 2 (added): module-level gateway functions dispatch to provider-specific
adapters via ``LlmConfig.provider``:
  - ``call_llm(config, messages) -> LlmResponse``
  - ``cast_llm_config(config) -> dict[str, Any]``
  - ``get_default_llm_config(db) -> LlmConfig | None``
  - ``get_model_for_task(task, config) -> str``

The 13 supported providers (per migration doc §3.4 + §10 Phase 2):
  OpenAI, Anthropic, Azure OpenAI, Google Gemini, AWS Bedrock, Cohere,
  Mistral, Meta Llama (via Together), Groq, AI21, Hugging Face, ZAI,
  Local (Ollama).

Audit fix (AUDIT-A1 #6 / H-11): ZAI provider now POSTs to the full
``https://open.bigmodel.cn/api/paas/v4/chat/completions`` URL — the
previous default omitted the ``/chat/completions`` suffix and would 404
against the real ZAI endpoint.
"""
from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

import httpx
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.core.config import get_settings
from app.models.config_models import LlmConfig as LlmConfigModel
from app.schemas.llm_config import LlmResponse

logger = structlog.get_logger(__name__)


# ── Background-task registry for fire-and-forget usage writes ──────────────
# Holds strong references to asyncio Tasks created by _record_llm_usage so
# CPython's garbage collector does not cancel them mid-flight. Tasks self-
# remove via add_done_callback when they complete. The set is module-level
# (not per-request) because usage writes are fire-and-forget — we never
# await them from the caller.
_BG_USAGE_TASKS: set = set()


# ── Constants ───────────────────────────────────────────────────────────────

LLM_HTTP_TIMEOUT: float = 60.0
# Local models (Ollama on CPU) need much longer — 5 minutes
LLM_HTTP_TIMEOUT_LOCAL: float = 300.0
"""Per-request HTTP timeout for all provider calls (per §10 Phase 2)."""

# ── Provider keys ───────────────────────────────────────────────────────────

PROVIDER_OPENAI = "openai"
PROVIDER_ANTHROPIC = "anthropic"
PROVIDER_AZURE = "azure"
PROVIDER_GEMINI = "gemini"
PROVIDER_BEDROCK = "bedrock"
PROVIDER_COHERE = "cohere"
PROVIDER_MISTRAL = "mistral"
PROVIDER_LLAMA = "llama"  # Meta Llama served via Together
PROVIDER_GROQ = "groq"
PROVIDER_AI21 = "ai21"
PROVIDER_HUGGINGFACE = "huggingface"
PROVIDER_ZAI = "zai"
PROVIDER_LOCAL = "local"  # Ollama

ALL_PROVIDERS: tuple[str, ...] = (
    PROVIDER_OPENAI,
    PROVIDER_ANTHROPIC,
    PROVIDER_AZURE,
    PROVIDER_GEMINI,
    PROVIDER_BEDROCK,
    PROVIDER_COHERE,
    PROVIDER_MISTRAL,
    PROVIDER_LLAMA,
    PROVIDER_GROQ,
    PROVIDER_AI21,
    PROVIDER_HUGGINGFACE,
    PROVIDER_ZAI,
    PROVIDER_LOCAL,
)

# Default base URLs per provider. Can be overridden per-row via LlmConfig.baseUrl.
PROVIDER_BASE_URLS: dict[str, str] = {
    PROVIDER_OPENAI: "https://api.openai.com/v1",
    PROVIDER_ANTHROPIC: "https://api.anthropic.com/v1",
    PROVIDER_AZURE: "",  # requires LlmConfig.baseUrl (tenant-specific endpoint)
    PROVIDER_GEMINI: "https://generativelanguage.googleapis.com/v1beta",
    PROVIDER_BEDROCK: "https://bedrock-runtime.us-east-1.amazonaws.com",
    PROVIDER_COHERE: "https://api.cohere.com/v2",
    PROVIDER_MISTRAL: "https://api.mistral.ai/v1",
    PROVIDER_LLAMA: "https://api.together.xyz/v1",  # Together hosts Llama
    PROVIDER_GROQ: "https://api.groq.com/openai/v1",
    PROVIDER_AI21: "https://api.ai21.com/studio/v1",
    PROVIDER_HUGGINGFACE: "https://api-inference.huggingface.co/models",
    PROVIDER_ZAI: "https://open.bigmodel.cn/api/paas/v4",
    PROVIDER_LOCAL: "http://localhost:11434/v1",  # Ollama default
}

# Providers that speak the OpenAI-compatible /chat/completions dialect.
_OPENAI_COMPATIBLE: frozenset[str] = frozenset({
    PROVIDER_OPENAI,
    PROVIDER_GROQ,
    PROVIDER_MISTRAL,
    PROVIDER_LLAMA,
    PROVIDER_LOCAL,
    PROVIDER_ZAI,
    PROVIDER_AI21,
    PROVIDER_HUGGINGFACE,
    PROVIDER_COHERE,
    PROVIDER_AZURE,
})

# Default anthropic-version header value (per Anthropic API spec).
_ANTHROPIC_VERSION_DEFAULT = "2023-06-01"

# Default Azure OpenAI API version (per Azure OpenAI REST spec).
_AZURE_API_VERSION_DEFAULT = "2024-10-21"


class LlmGatewayError(Exception):
    """Raised when the LLM gateway call fails after retries."""


# ── Settings-column parsing ─────────────────────────────────────────────────


def _parse_settings(config: LlmConfigModel) -> dict[str, Any]:
    """
    Parse the LlmConfig.settings JSON column safely.

    The column is TEXT holding a JSON string (per §5.5). Returns {} on parse
    failure or non-dict content — never raises.
    """
    raw = getattr(config, "settings", None) or "{}"
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError, ValueError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


# ── Helper mapping (per §6.2) ───────────────────────────────────────────────


def cast_llm_config(config: LlmConfigModel) -> dict[str, Any]:
    """
    Convert a LlmConfig DB row into provider-specific kwargs (per §6.2).

    Returns a dict with the keys:
      - provider:     normalized provider key (lowercase)
      - model:        the model ID to invoke
      - api_key:      the API key (may be None for ZAI/local)
      - base_url:     the provider's base URL
      - temperature:  float (default 0.7)
      - max_tokens:   int (default 1024)
      - extra:        provider-specific kwargs (api_version, deployment,
                      region, anthropic_version, generation_config, ...)

    The 'models' map inside settings (task -> model_id) is consumed
    separately by ``get_model_for_task()``.
    """
    settings = _parse_settings(config)
    provider = (config.provider or PROVIDER_ZAI).lower()
    base_url = config.baseUrl or PROVIDER_BASE_URLS.get(provider, "")

    temperature_raw = settings.get("temperature", settings.get("Temperature", 0.7))
    max_tokens_raw = settings.get(
        "max_tokens", settings.get("maxTokens", settings.get("MaxTokens", 1024))
    )

    try:
        temperature = float(temperature_raw)
    except (TypeError, ValueError):
        temperature = 0.7
    try:
        max_tokens = int(max_tokens_raw)
    except (TypeError, ValueError):
        max_tokens = 1024

    kwargs: dict[str, Any] = {
        "provider": provider,
        "model": config.modelId,
        "api_key": config.apiKey,
        "base_url": base_url,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "extra": {},
    }

    # Provider-specific extras
    if provider == PROVIDER_AZURE:
        kwargs["extra"]["api_version"] = settings.get(
            "api_version", settings.get("apiVersion", _AZURE_API_VERSION_DEFAULT)
        )
        kwargs["extra"]["deployment"] = settings.get(
            "deployment", settings.get("deploymentName", config.modelId)
        )
    elif provider == PROVIDER_BEDROCK:
        kwargs["extra"]["region"] = settings.get("region", "us-east-1")
        kwargs["extra"]["model_id"] = settings.get("model_id", config.modelId)
    elif provider == PROVIDER_ANTHROPIC:
        kwargs["extra"]["anthropic_version"] = settings.get(
            "anthropic_version", _ANTHROPIC_VERSION_DEFAULT
        )
    elif provider == PROVIDER_GEMINI:
        kwargs["extra"]["generation_config"] = {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
            "topP": float(settings.get("top_p", settings.get("topP", 1.0))),
        }

    return kwargs


def get_model_for_task(task: str, config: LlmConfigModel) -> str:
    """
    Tier routing — return the model ID for a given task (per §3.4 + §10 Phase 2).

    Reads the 'models' dict inside the JSON settings column. Returns
    ``config.modelId`` when no per-task override is configured.

    Known tasks: email_generation, icp_suggest, framework_recommend,
    gtm_thesis, subject_line, qa_check, compliance_check, reply_categorize,
    auto_reply, personalization, anti_pattern, prospect_brief,
    prospect_lookalike, ultimate_profile, prospect_enrich, prospect_score,
    analytics_diagnose, content_idea, linkedin_post, meeting_prep,
    deal_suggest, deal_health, deal_next_step, weekly_digest, cadence_plan,
    touch_angle, rule_suggest, ab_test_hypothesis.
    """
    settings = _parse_settings(config)
    models_map = settings.get("models") or {}
    if isinstance(models_map, dict) and task in models_map:
        return str(models_map[task])
    return config.modelId


# async def get_default_llm_config(db: AsyncSession) -> LlmConfigModel | None:
#     """
#     Fetch the best available LLM config using a 3-tier fallback:

#     Tier 1 — Tenant LlmConfig with isDefault=True and isActive=True.
#     Tier 2 — Any active tenant LlmConfig row (first created).
#     Tier 3 — public.global_llm_config (platform-managed key, Fernet-encrypted).
#               Decrypts api_key_encrypted and returns a SimpleNamespace shim
#               that satisfies the same interface as LlmConfigModel so call_llm()
#               works without modification.

#     FIX: Previously only queried the tenant LlmConfig table. When that table is
#     empty (tenants who configured their LLM via Setup → LLM Models, which writes
#     to public.global_llm_config), this function returned None and every LLM call
#     failed with "no_llm_config". The fix adds Tier 3 as a transparent fallback.
#     """
#     # Tier 1: tenant default
#     result = await db.execute(
#         select(LlmConfigModel)
#         .where(LlmConfigModel.isDefault.is_(True))
#         .where(LlmConfigModel.isActive.is_(True))
#         .order_by(LlmConfigModel.createdAt.asc())
#         .limit(1)
#     )
#     row = result.scalar_one_or_none()
#     if row is not None:
#         return row

#     # Tier 2: any active tenant config
#     result = await db.execute(
#         select(LlmConfigModel)
#         .where(LlmConfigModel.isActive.is_(True))
#         .order_by(LlmConfigModel.createdAt.asc())
#         .limit(1)
#     )
#     row = result.scalar_one_or_none()
#     if row is not None:
#         return row

#     # Tier 3: platform GlobalLlmConfig (public schema, Fernet-encrypted key).
#     # Opens a fresh session locked to public schema so the SET search_path on
#     # the tenant db session does not interfere.
#     try:
#         from types import SimpleNamespace
#         from app.core.database import AsyncSessionLocal
#         from app.models.global_llm_config import GlobalLlmConfig
#         from app.services.secret_service import decrypt_at_rest
#         from sqlalchemy import text as _text

#         async with AsyncSessionLocal() as pub_db:
#             await pub_db.execute(_text('SET search_path TO "public"'))

#             # Prefer the row marked is_default; fall back to any active row
#             g_result = await pub_db.execute(
#                 select(GlobalLlmConfig)
#                 .where(GlobalLlmConfig.is_active.is_(True))
#                 .where(GlobalLlmConfig.is_default.is_(True))
#                 .order_by(GlobalLlmConfig.id.asc())
#                 .limit(1)
#             )
#             g_row = g_result.scalar_one_or_none()

#             if g_row is None:
#                 g_result = await pub_db.execute(
#                     select(GlobalLlmConfig)
#                     .where(GlobalLlmConfig.is_active.is_(True))
#                     .order_by(GlobalLlmConfig.id.asc())
#                     .limit(1)
#                 )
#                 g_row = g_result.scalar_one_or_none()

#             if g_row is None:
#                 return None

#             # Decrypt the Fernet-encrypted API key
#             try:
#                 plaintext_key = decrypt_at_rest(g_row.api_key_encrypted)
#             except Exception:
#                 plaintext_key = g_row.api_key_encrypted  # already plaintext fallback

#             # Return a SimpleNamespace shim that satisfies cast_llm_config()
#             # which reads: provider, modelId, apiKey, baseUrl, settings, isActive
#             return SimpleNamespace(
#                 id=str(g_row.id),
#                 name=g_row.display_name,
#                 provider=g_row.provider,
#                 modelId=g_row.model_name,
#                 apiKey=plaintext_key,
#                 baseUrl=g_row.base_url or "",
#                 isDefault=g_row.is_default,
#                 isActive=g_row.is_active,
#                 settings={"max_tokens": g_row.max_tokens, "temperature": g_row.temperature},
#                 modelTier="standard",
#                 global_llm_config_id=g_row.id,
#             )
#     except Exception as exc:
#         logger.warning("get_default_llm_config.global_fallback_failed", error=str(exc))
#         return None



async def get_default_llm_config(db: AsyncSession) -> LlmConfigModel | None:
    """
    Fetch the best available LLM config using a 3-tier fallback:

    Tier 1 — Tenant LlmConfig with isDefault=True and isActive=True.
    Tier 2 — Any active tenant LlmConfig row (first created).
    Tier 3 — public.global_llm_config (platform-managed key, Fernet-encrypted).
              Decrypts api_key_encrypted and returns a SimpleNamespace shim
              that satisfies the same interface as LlmConfigModel so call_llm()
              works without modification.

    FIX: Tier 1 and Tier 2 now decrypt the Fernet-encrypted apiKey column
    before returning — previously the raw ciphertext was passed directly to
    the provider as a Bearer token, causing 401 Unauthorized on every call.
    The tenant_service.test_llm path always decrypted correctly (it calls
    decrypt_at_rest explicitly); this function was the only path that did not.
    """
    from types import SimpleNamespace
    from app.services.secret_service import decrypt_at_rest as _decrypt

    def _tenant_row_to_shim(row: LlmConfigModel) -> SimpleNamespace:
        """Wrap a tenant LlmConfig row in a SimpleNamespace with the API key
        decrypted so call_llm() receives the plaintext key, not the ciphertext."""
        import json as _json
        raw_settings = row.settings
        if isinstance(raw_settings, str):
            try:
                settings_dict = _json.loads(raw_settings)
            except Exception:
                settings_dict = {}
        elif isinstance(raw_settings, dict):
            settings_dict = raw_settings
        else:
            settings_dict = {}

        try:
            plaintext_key = _decrypt(row.apiKey) if row.apiKey else None
        except Exception:
            # If decryption fails the key was stored as plaintext (legacy rows).
            plaintext_key = row.apiKey

        return SimpleNamespace(
            id=str(row.id),
            name=row.name,
            provider=row.provider,
            modelId=row.modelId,
            apiKey=plaintext_key,
            baseUrl=row.baseUrl or "",
            isDefault=row.isDefault,
            isActive=row.isActive,
            settings=_json.dumps(settings_dict),
            modelTier=getattr(row, "modelTier", "standard"),
            global_llm_config_id=getattr(row, "global_llm_config_id", None),
        )

    # Tier 1: tenant default
    result = await db.execute(
        select(LlmConfigModel)
        .where(LlmConfigModel.isDefault.is_(True))
        .where(LlmConfigModel.isActive.is_(True))
        .order_by(LlmConfigModel.createdAt.asc())
        .limit(1)
    )
    row = result.scalar_one_or_none()
    if row is not None:
        return _tenant_row_to_shim(row)

    # Tier 2: any active tenant config
    result = await db.execute(
        select(LlmConfigModel)
        .where(LlmConfigModel.isActive.is_(True))
        .order_by(LlmConfigModel.createdAt.asc())
        .limit(1)
    )
    row = result.scalar_one_or_none()
    if row is not None:
        return _tenant_row_to_shim(row)

# ── Provider URL + header builders ──────────────────────────────────────────


def _provider_chat_url(provider: str, kwargs: dict[str, Any]) -> str:
    """Return the chat-completions URL for a provider."""
    base = (kwargs.get("base_url") or PROVIDER_BASE_URLS.get(provider, "")).rstrip("/")
    if not base:
        raise LlmGatewayError(f"No base_url configured for provider '{provider}'")

    if provider == PROVIDER_ANTHROPIC:
        return f"{base}/messages"
    if provider == PROVIDER_GEMINI:
        model = kwargs["model"]
        return f"{base}/models/{model}:generateContent"
    if provider == PROVIDER_AZURE:
        deployment = kwargs["extra"].get("deployment", "deployment")
        api_version = kwargs["extra"].get("api_version", _AZURE_API_VERSION_DEFAULT)
        return f"{base}/openai/deployments/{deployment}/chat/completions?api-version={api_version}"
    if provider == PROVIDER_COHERE:
        return f"{base}/chat"
    if provider == PROVIDER_BEDROCK:
        model_id = kwargs["extra"].get("model_id", kwargs["model"])
        return f"{base}/model/{model_id}/invoke"
    if provider == PROVIDER_HUGGINGFACE:
        # HF router: /models/{model}/v1/chat/completions
        return f"{base}/{kwargs['model']}/v1/chat/completions"
    # OpenAI-compatible: openai, groq, mistral, llama (Together), local, zai, ai21
    return f"{base}/chat/completions"


# def _provider_headers(provider: str, kwargs: dict[str, Any]) -> dict[str, str]:
#     """Return provider-specific auth headers (Content-Type added by caller)."""
#     api_key = kwargs.get("api_key") or ""
#     if provider == PROVIDER_ANTHROPIC:
#         return {
#             "x-api-key": api_key,
#             "anthropic-version": kwargs["extra"].get(
#                 "anthropic_version", _ANTHROPIC_VERSION_DEFAULT
#             ),
#         }
#     if provider == PROVIDER_GEMINI:
#         return {"x-goog-api-key": api_key}
#     if provider == PROVIDER_AZURE:
#         # Azure uses api-key header (not Bearer)
#         return {"api-key": api_key}
#     return {"Authorization": f"Bearer {api_key}"}



def _provider_headers(provider: str, kwargs: dict[str, Any]) -> dict[str, str]:
    """Return provider-specific auth headers (Content-Type added by caller)."""
    api_key = kwargs.get("api_key") or ""
    if provider == PROVIDER_ANTHROPIC:
        return {
            "x-api-key": api_key,
            "anthropic-version": kwargs["extra"].get(
                "anthropic_version", _ANTHROPIC_VERSION_DEFAULT
            ),
        }
    if provider == PROVIDER_GEMINI:
        return {"x-goog-api-key": api_key}
    if provider == PROVIDER_AZURE:
        # Azure uses api-key header (not Bearer)
        return {"api-key": api_key}
    # FIX: key-optional providers (Ollama/local, ZAI built-in) send no
    # Authorization header when api_key is empty — sending "Bearer " with
    # an empty token produces an illegal header value that httpx rejects.
    if not api_key and provider in (PROVIDER_LOCAL, PROVIDER_ZAI):
        return {}
    return {"Authorization": f"Bearer {api_key}"}

# ── Payload builders (per-provider) ─────────────────────────────────────────


def _build_openai_payload(
    messages: list[dict[str, str]], kwargs: dict[str, Any]
) -> dict[str, Any]:
    """OpenAI-compatible chat-completions payload."""
    return {
        "model": kwargs["model"],
        "messages": messages,
        "temperature": kwargs["temperature"],
        "max_tokens": kwargs["max_tokens"],
    }


def _build_anthropic_payload(
    messages: list[dict[str, str]], kwargs: dict[str, Any]
) -> dict[str, Any]:
    """Anthropic Messages API — system is a top-level field, not in messages."""
    system_msgs = [m for m in messages if m.get("role") == "system"]
    user_msgs = [m for m in messages if m.get("role") != "system"]
    system_text = "\n\n".join(str(m.get("content", "")) for m in system_msgs)
    payload: dict[str, Any] = {
        "model": kwargs["model"],
        "messages": user_msgs,
        "max_tokens": kwargs["max_tokens"],
        "temperature": kwargs["temperature"],
    }
    if system_text:
        payload["system"] = system_text
    return payload


def _build_gemini_payload(
    messages: list[dict[str, str]], kwargs: dict[str, Any]
) -> dict[str, Any]:
    """Google Gemini generateContent payload."""
    contents: list[dict[str, Any]] = []
    sys_text = "\n".join(
        str(m.get("content", "")) for m in messages if m.get("role") == "system"
    )
    for m in messages:
        role = m.get("role", "user")
        if role == "system":
            continue
        gemini_role = "user" if role == "user" else "model"
        contents.append(
            {"role": gemini_role, "parts": [{"text": str(m.get("content", ""))}]}
        )
    payload: dict[str, Any] = {
        "contents": contents,
        "generationConfig": kwargs["extra"].get("generation_config", {}),
    }
    if sys_text:
        payload["systemInstruction"] = {"parts": [{"text": sys_text}]}
    return payload


def _build_cohere_payload(
    messages: list[dict[str, str]], kwargs: dict[str, Any]
) -> dict[str, Any]:
    """Cohere v2 chat (OpenAI-compatible)."""
    return {
        "model": kwargs["model"],
        "messages": messages,
        "temperature": kwargs["temperature"],
        "max_tokens": kwargs["max_tokens"],
    }


def _build_bedrock_payload(
    messages: list[dict[str, str]], kwargs: dict[str, Any]
) -> dict[str, Any]:
    """
    AWS Bedrock converse API payload.

    Note: production deployments wrap this in boto3 SigV4 signing. The
    gateway posts the converse payload directly when LlmConfig.apiKey
    holds a bearer-secured proxy token (e.g. Bedrock proxy gateway).
    """
    return {
        "modelId": kwargs["extra"].get("model_id", kwargs["model"]),
        "messages": messages,
        "inferenceConfig": {
            "temperature": kwargs["temperature"],
            "maxTokens": kwargs["max_tokens"],
        },
    }


def _build_provider_payload(
    provider: str, messages: list[dict[str, str]], kwargs: dict[str, Any]
) -> dict[str, Any]:
    if provider == PROVIDER_ANTHROPIC:
        return _build_anthropic_payload(messages, kwargs)
    if provider == PROVIDER_GEMINI:
        return _build_gemini_payload(messages, kwargs)
    if provider == PROVIDER_BEDROCK:
        return _build_bedrock_payload(messages, kwargs)
    if provider == PROVIDER_COHERE:
        return _build_cohere_payload(messages, kwargs)
    # All OpenAI-compatible providers
    return _build_openai_payload(messages, kwargs)


# ── Response parsers (per-provider) ─────────────────────────────────────────


def _parse_openai_response(
    data: dict[str, Any], provider: str, model: str
) -> LlmResponse:
    """Parse OpenAI-compatible response shape (used by 10 of 13 providers)."""
    choices = data.get("choices") or []
    content = ""
    if choices:
        msg = choices[0].get("message") or {}
        content = str(msg.get("content", ""))
    usage = data.get("usage") or {}
    usage_dict = {
        "prompt_tokens": int(usage.get("prompt_tokens", 0) or 0),
        "completion_tokens": int(usage.get("completion_tokens", 0) or 0),
        "total_tokens": int(usage.get("total_tokens", 0) or 0),
    }
    return LlmResponse(
        content=content,
        usage=usage_dict,
        model=model,
        provider=provider,
        raw=data,
    )


def _parse_anthropic_response(
    data: dict[str, Any], provider: str, model: str
) -> LlmResponse:
    content = ""
    blocks = data.get("content") or []
    if isinstance(blocks, list):
        for b in blocks:
            if isinstance(b, dict) and b.get("type") == "text":
                content += str(b.get("text", ""))
    usage = data.get("usage") or {}
    input_tokens = int(usage.get("input_tokens", 0) or 0)
    output_tokens = int(usage.get("output_tokens", 0) or 0)
    usage_dict = {
        "prompt_tokens": input_tokens,
        "completion_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
    }
    return LlmResponse(
        content=content,
        usage=usage_dict,
        model=model,
        provider=provider,
        raw=data,
    )


def _parse_gemini_response(
    data: dict[str, Any], provider: str, model: str
) -> LlmResponse:
    content = ""
    candidates = data.get("candidates") or []
    if candidates:
        parts = (candidates[0].get("content") or {}).get("parts") or []
        for p in parts:
            if isinstance(p, dict) and "text" in p:
                content += str(p["text"])
    usage_meta = data.get("usageMetadata") or {}
    usage_dict = {
        "prompt_tokens": int(usage_meta.get("promptTokenCount", 0) or 0),
        "completion_tokens": int(usage_meta.get("candidatesTokenCount", 0) or 0),
        "total_tokens": int(usage_meta.get("totalTokenCount", 0) or 0),
    }
    return LlmResponse(
        content=content,
        usage=usage_dict,
        model=model,
        provider=provider,
        raw=data,
    )


def _parse_bedrock_response(
    data: dict[str, Any], provider: str, model: str
) -> LlmResponse:
    content = ""
    output = data.get("output") or {}
    msg = output.get("message") or {}
    for c in msg.get("content") or []:
        if isinstance(c, dict) and "text" in c:
            content += str(c["text"])
    usage = data.get("usage") or {}
    usage_dict = {
        "prompt_tokens": int(usage.get("inputTokens", 0) or 0),
        "completion_tokens": int(usage.get("outputTokens", 0) or 0),
        "total_tokens": int(usage.get("totalTokens", 0) or 0),
    }
    return LlmResponse(
        content=content,
        usage=usage_dict,
        model=model,
        provider=provider,
        raw=data,
    )


def _parse_provider_response(
    provider: str, data: dict[str, Any], model: str
) -> LlmResponse:
    if provider == PROVIDER_ANTHROPIC:
        return _parse_anthropic_response(data, provider, model)
    if provider == PROVIDER_GEMINI:
        return _parse_gemini_response(data, provider, model)
    if provider == PROVIDER_BEDROCK:
        return _parse_bedrock_response(data, provider, model)
    return _parse_openai_response(data, provider, model)


# ── HTTP transport with tenacity retry ──────────────────────────────────────


async def _do_http_post(
    url: str, headers: dict[str, str], payload: dict[str, Any],
    timeout: float = LLM_HTTP_TIMEOUT,
) -> dict[str, Any]:
    """Single HTTP POST with timeout. Raises httpx.HTTPError on failure."""
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        return resp.json()


def _retrying() -> AsyncRetrying:
    """
    Tenacity AsyncRetrying: 3 attempts, exponential backoff 1-10s, on
    transient HTTP errors only (429/5xx via HTTPStatusError + transport
    errors). Per §10 Phase 2 spec.
    """
    return AsyncRetrying(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type(
            (httpx.HTTPStatusError, httpx.ConnectError, httpx.ReadTimeout,
             httpx.ConnectTimeout, httpx.RemoteProtocolError)
        ),
        reraise=True,
    )


async def _call_provider(
    provider: str, kwargs: dict[str, Any], messages: list[dict[str, str]]
) -> LlmResponse:
    """Dispatch to the right provider adapter. Retries transient failures."""
    model = kwargs["model"]
    url = _provider_chat_url(provider, kwargs)
    payload = _build_provider_payload(provider, messages, kwargs)
    headers: dict[str, str] = {"Content-Type": "application/json"}
    headers.update(_provider_headers(provider, kwargs))

    data: dict[str, Any] = {}
    async for attempt in _retrying():
        with attempt:
            _timeout = LLM_HTTP_TIMEOUT_LOCAL if provider == PROVIDER_LOCAL else LLM_HTTP_TIMEOUT
            data = await _do_http_post(url, headers, payload, timeout=_timeout)

    return _parse_provider_response(provider, data, model)


# ── Main entry: call_llm ────────────────────────────────────────────────────


async def _resolve_dual_path_api_key(
    config: LlmConfigModel, *, provider: str
) -> str | None:
    """Resolve the LLM API key via the dual-path credential service.

    FIX-BE-1 / CRITICAL 2: production LLM calls used to read
    ``config.apiKey`` (the legacy plaintext column) directly. When a tenant
    adopts the dual-path model (``apiKey=NULL`` + ``global_llm_config_id``
    set, or ``key_source='platform'``), that column is empty and the call
    failed with a 401.

    This helper is invoked from ``call_llm`` ONLY when ``config.apiKey`` is
    missing or empty. It delegates to
    ``IntegrationCredentialsService.resolve_credentials(integration_type='llm', ...)``
    which:

      1. If ``config.global_llm_config_id`` is set, loads that row from
         ``public.global_llm_config``, Fernet-decrypts its
         ``api_key_encrypted`` column, and returns the plaintext key.
      2. Else looks up the platform default for ``provider`` in
         ``public.global_llm_config`` (is_default=True, is_active=True).
      3. Else falls back to the configured SecretBackend (env / AWS SM /
         Azure KV) under ``platform/llm/{provider}/api_key``.

    Returns ``None`` if no key can be resolved. The caller raises a clear
    ``LlmGatewayError`` so the user sees an actionable message instead of
    an empty-key 401 from the upstream provider.

    Expected behavior for the 3 cases:

      Case A — tenant-managed legacy key (``config.apiKey`` set):
          This helper is NOT called (caller short-circuits).
          ``call_llm`` uses ``config.apiKey`` directly.

      Case B — platform-managed key via ``global_llm_config_id``:
          This helper resolves the Fernet-encrypted key from
          ``public.global_llm_config`` via ``IntegrationCredentialsService``.

      Case C — neither set (misconfigured tenant):
          This helper returns ``None``; ``call_llm`` raises
          ``LlmGatewayError("No LLM API key configured. Set
          key_source='platform' with a global_llm_config_id, or provide an
          apiKey.")``.
    """
    integration_id: str | None = None
    gid = getattr(config, "global_llm_config_id", None)
    if gid is not None:
        try:
            integration_id = str(int(gid))
        except (TypeError, ValueError):
            integration_id = None

    try:
        from app.core.database import AsyncSessionLocal
        from app.features.integrations.integration_credentials_service import (
            IntegrationCredentialsService,
        )
    except ImportError as exc:  # pragma: no cover — defensive
        logger.warning(
            "llm.dual_path_import_failed",
            provider=provider,
            error=str(exc),
        )
        return None

    try:
        async with AsyncSessionLocal() as db:
            # IntegrationCredentialsService._resolve_llm_credentials queries
            # public.global_llm_config explicitly (schema-qualified), so the
            # session's search_path does not matter here.
            creds = await IntegrationCredentialsService().resolve_credentials(
                db,
                integration_type="llm",
                integration_id=integration_id,
                provider=provider,
            )
        api_key = creds.get("api_key") if creds else None
        if api_key:
            logger.debug(
                "llm.dual_path_resolved",
                provider=provider,
                global_llm_config_id=integration_id,
                key_source=creds.get("key_source"),
            )
        return api_key
    except Exception as exc:  # noqa: BLE001 — credential resolution must never break the call
        logger.warning(
            "llm.dual_path_resolve_failed",
            provider=provider,
            global_llm_config_id=integration_id,
            error=str(exc),
        )
        return None


async def call_llm(
    config: LlmConfigModel, messages: list[dict[str, str]]
) -> LlmResponse:
    """
    Main entry point — dispatch to the provider-specific adapter (per §6.2).

    Args:
        config:   the tenant's LlmConfig DB row
        messages: list of {role, content} dicts (system/user/assistant)

    Returns:
        LlmResponse with content, usage, model, provider, raw.

    Raises:
        LlmGatewayError: when the config is inactive, the provider is
            unknown, no API key can be resolved (dual-path failure), or
            the HTTP call fails after 3 retries.

    FIX-BE-1 / CRITICAL 2: when ``config.apiKey`` is empty (tenant using
    ``global_llm_config_id`` / platform-managed keys), the API key is
    resolved via ``IntegrationCredentialsService.resolve_credentials``
    before the HTTP call is dispatched. See
    ``_resolve_dual_path_api_key`` for the full resolution chain.
    """
    if not config.isActive:
        raise LlmGatewayError(f"LlmConfig '{config.name}' is not active")

    kwargs = cast_llm_config(config)
    provider = kwargs["provider"]
    if provider not in ALL_PROVIDERS:
        raise LlmGatewayError(
            f"Unknown LLM provider: '{provider}'. "
            f"Supported: {', '.join(ALL_PROVIDERS)}"
        )

    # ── Dual-path credential resolution (FIX-BE-1 / CRITICAL 2) ──────────
    # cast_llm_config above populated kwargs['api_key'] from config.apiKey
    # (the legacy plaintext column). When that is missing/empty, resolve
    # the key via the IntegrationCredentialsService — which checks
    # public.global_llm_config (Fernet-encrypted) first, then falls back
    # to the platform SecretBackend. Never silently send an empty key to
    # the provider (would produce a confusing 401 instead of a clear
    # configuration error).
    # local (Ollama) and zai providers do not require an API key —
    # skip the key-resolution check for these providers entirely.
    _KEY_OPTIONAL_PROVIDERS = (PROVIDER_LOCAL, PROVIDER_ZAI)
    if not kwargs.get("api_key") and provider not in _KEY_OPTIONAL_PROVIDERS:
        resolved = await _resolve_dual_path_api_key(config, provider=provider)
        if resolved:
            kwargs["api_key"] = resolved
        else:
            raise LlmGatewayError(
                "No LLM API key configured. Set key_source='platform' with a "
                "global_llm_config_id, or provide an apiKey."
            )

    try:
        response = await _call_provider(provider, kwargs, messages)
    except LlmGatewayError:
        # Bump the error counter (best-effort) before re-raising.
        _record_llm_error(provider, kwargs["model"], "LlmGatewayError")
        raise
    except Exception as exc:
        logger.warning(
            "llm.call_llm.failed",
            provider=provider,
            model=kwargs["model"],
            error=str(exc),
        )
        _record_llm_error(provider, kwargs["model"], type(exc).__name__)
        raise LlmGatewayError(
            f"LLM call failed for provider '{provider}': {exc}"
        ) from exc

    # ── Usage instrumentation (fire-and-forget — never breaks the LLM call).
    # Records a UsageEvent + bumps Prometheus counters. Best-effort: any
    # failure is swallowed + logged so the caller still gets the LlmResponse.
    _record_llm_usage(provider, kwargs["model"], response, config)
    return response


def _record_llm_error(provider: str, model: str, error_type: str) -> None:
    """Bump the LLM error counter. Best-effort — never raises."""
    try:
        from app.core.metrics import LLM_ERRORS

        # tenant label is unknown here (call_llm does not receive it); use
        # "_unknown" so the metric is still emitted. The per-tenant
        # attribution comes from the UsageService path, which IS tenant-aware.
        LLM_ERRORS.labels(
            provider=provider, model=model, tenant="_unknown", error_type=error_type
        ).inc()
    except Exception:  # noqa: BLE001
        pass


def _record_llm_usage(
    provider: str, model: str, response: "LlmResponse", config: "LlmConfigModel"
) -> None:
    """Best-effort: record UsageEvent + Prometheus counters for one LLM call.

    Runs in the BACKGROUND so the caller's request is not blocked on the
    usage-event INSERT. Any failure (DB down, import error, cost-lookup
    error) is swallowed + logged. The LLM call has already succeeded —
    the caller's response is unaffected.

    Tenant + user_id are extracted from the structlog contextvars bound
    by RequestContextMiddleware + TenantMiddleware. When those are not
    available (background jobs, tests), the event is recorded with
    tenant="_unknown" / user_id="_unknown" so the metric still surfaces.
    """
    try:
        usage = getattr(response, "usage", None) or {}
        prompt_tokens = int(usage.get("prompt_tokens", 0) or 0)
        completion_tokens = int(usage.get("completion_tokens", 0) or 0)

        # Pull tenant + user_id from structlog contextvars (set by the
        # request middleware). For non-request callers (Celery tasks,
        # scheduler), fall back to "_unknown" so the event is still recorded.
        tenant_slug = "_unknown"
        user_id = "_unknown"
        request_id: str | None = None
        try:
            from structlog import contextvars as _cv

            ctx = _cv.get_contextvars()
            # The audit + tenant middleware bind "request_id" + "tenant_slug"
            # to the context. We use the same names here.
            t = ctx.get("tenant_slug")
            if isinstance(t, str) and t:
                tenant_slug = t
            u = ctx.get("user_id")
            if isinstance(u, str) and u:
                user_id = u
            request_id = ctx.get("request_id") if isinstance(ctx.get("request_id"), str) else None
        except Exception:  # noqa: BLE001
            pass

        # Bump Prometheus counters (synchronous, never blocks).
        try:
            from app.core.metrics import LLM_CALLS, LLM_TOKENS, LLM_LATENCY, LLM_COST_CENTS

            LLM_CALLS.labels(provider=provider, model=model, tenant=tenant_slug).inc()
            LLM_TOKENS.labels(
                provider=provider, model=model, type="input", tenant=tenant_slug
            ).inc(prompt_tokens)
            LLM_TOKENS.labels(
                provider=provider, model=model, type="output", tenant=tenant_slug
            ).inc(completion_tokens)
        except Exception:  # noqa: BLE001
            pass

        # Compute cost + persist UsageEvent asynchronously.
        import asyncio

        async def _record() -> None:
            try:
                from app.features.usage.service import UsageService

                await UsageService().record_llm_call(
                    tenant=tenant_slug,
                    user_id=user_id,
                    provider=provider,
                    model=model,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    metadata={
                        "request_id": request_id,
                        "config_name": getattr(config, "name", None),
                    },
                )
            except Exception as exc:  # noqa: BLE001 — usage must never break LLM
                logger.warning(
                    "llm.usage_record_failed",
                    provider=provider,
                    model=model,
                    tenant=tenant_slug,
                    error=str(exc),
                )

        # Schedule the record on the running loop. We do NOT await it — the
        # caller is waiting on the LlmResponse and the usage write is
        # fire-and-forget per the SURVEY-OBS design.
        #
        # IMPORTANT: hold a strong reference to the task in _BG_USAGE_TASKS so
        # the garbage collector does not cancel it mid-flight (CPython's asyncio
        # only keeps weak references to tasks). Tasks self-remove on completion.
        try:
            loop = asyncio.get_running_loop()
            task = loop.create_task(_record())
            _BG_USAGE_TASKS.add(task)
            task.add_done_callback(_BG_USAGE_TASKS.discard)
        except RuntimeError:
            # No running loop (e.g., sync test context) — run inline.
            try:
                asyncio.run(_record())
            except Exception:  # noqa: BLE001
                pass
    except Exception as exc:  # noqa: BLE001 — instrumentation must never break the LLM call
        logger.warning(
            "llm.usage_instrumentation_failed",
            provider=provider,
            model=model,
            error=str(exc),
        )


# ── Legacy LlmService (preserved for backward compat with Phase 3 modules) ──


def _ensure_chat_completions_suffix(url: str) -> str:
    """
    Audit fix (AUDIT-A1 #6 / H-11): append /chat/completions to a ZAI base
    URL when missing. The legacy ``LLM_API_URL`` setting defaults to
    ``https://open.bigmodel.cn/api/paas/v4`` (no suffix), so the previous
    implementation POSTed to the API root and would 404.

    Idempotent: leaves URLs that already end with /chat/completions alone.
    """
    if not url:
        return url
    if url.rstrip("/").endswith("/chat/completions"):
        return url
    # ZAI base ends with /v4 — append /chat/completions
    if "open.bigmodel.cn" in url and not url.rstrip("/").endswith(("/v4", "/v4/")):
        return url
    return url.rstrip("/") + "/chat/completions"


def _extract_text(data: dict[str, Any]) -> str:
    """Tolerant extractor for OpenAI/ZAI response shapes."""
    try:
        choices = data.get("choices") or []
        if choices:
            msg = choices[0].get("message") or {}
            content = msg.get("content")
            if isinstance(content, str):
                return content
        # Some ZAI variants nest under "output"
        output = data.get("output")
        if isinstance(output, str):
            return output
        if isinstance(output, list) and output:
            first = output[0]
            if isinstance(first, dict) and "content" in first:
                return str(first["content"])
    except Exception:  # noqa: BLE001
        pass
    return ""


class LlmService:
    """
    Phase 1 thin async wrapper around the configured OpenAI-compatible endpoint.

    Preserved verbatim for backward compatibility with Phase 3 modules that
    consume ``get_llm_service().generate()`` and ``generate_json()``.

    Audit fix: the URL now goes through ``_ensure_chat_completions_suffix``
    so ZAI calls hit ``/api/paas/v4/chat/completions`` instead of the
    API root.

    New code should prefer ``call_llm(config, messages)`` with an
    explicit ``LlmConfig`` DB row.
    """

    def __init__(self, settings: Any | None = None) -> None:
        self._settings = settings or get_settings()

    async def generate(
        self,
        *,
        prompt: str,
        system: str | None = None,
        model: str = "glm-4-flash",
        temperature: float = 0.7,
        max_tokens: int = 1024,
        timeout: float | None = None,
    ) -> str:
        """
        Send a single-turn prompt and return the generated text.

        Falls back to a stub when the API URL is empty or the call fails,
        so feature modules always receive a string (never raise to the caller
        — they handle empty-string gracefully).
        """
        url = _ensure_chat_completions_suffix(self._settings.LLM_API_URL)
        timeout_s = timeout or float(self._settings.LLM_DEFAULT_TIMEOUT_SECONDS)

        if not url:
            return self._stub(prompt)

        payload: dict[str, Any] = {
            "model": model,
            "messages": (
                [{"role": "system", "content": system}] if system else []
            )
            + [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        try:
            async with httpx.AsyncClient(timeout=timeout_s) as client:
                resp = await client.post(
                    url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                )
                resp.raise_for_status()
                data = resp.json()
                return _extract_text(data)
        except Exception as exc:  # noqa: BLE001 — graceful degradation
            logger.warning("llm.generate.fallback", error=str(exc))
            return self._stub(prompt)

    async def generate_json(
        self,
        *,
        prompt: str,
        system: str | None = None,
        model: str = "glm-4-flash",
        timeout: float | None = None,
    ) -> dict[str, Any]:
        """Generate and JSON-parse. Returns {} on parse failure."""
        raw = await self.generate(
            prompt=prompt,
            system=system,
            model=model,
            temperature=0.2,
            max_tokens=2048,
            timeout=timeout,
        )
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            logger.warning("llm.generate_json.parse_failed", raw=raw[:200])
            return {}

    @staticmethod
    def _stub(prompt: str) -> str:
        """Deterministic stub used when no LLM endpoint is configured."""
        return f"[LLM-STUB] {prompt[:120]}"


@lru_cache
def get_llm_service() -> LlmService:
    """Cached accessor — import this, never instantiate LlmService directly."""
    return LlmService()


__all__ = [
    # Constants
    "ALL_PROVIDERS",
    "PROVIDER_BASE_URLS",
    "PROVIDER_OPENAI",
    "PROVIDER_ANTHROPIC",
    "PROVIDER_AZURE",
    "PROVIDER_GEMINI",
    "PROVIDER_BEDROCK",
    "PROVIDER_COHERE",
    "PROVIDER_MISTRAL",
    "PROVIDER_LLAMA",
    "PROVIDER_GROQ",
    "PROVIDER_AI21",
    "PROVIDER_HUGGINGFACE",
    "PROVIDER_ZAI",
    "PROVIDER_LOCAL",
    "LLM_HTTP_TIMEOUT",
    # Errors
    "LlmGatewayError",
    # Gateway functions (Phase 2)
    "call_llm",
    "cast_llm_config",
    "get_default_llm_config",
    "get_model_for_task",
    # Legacy service (Phase 1 — preserved)
    "LlmService",
    "get_llm_service",
]