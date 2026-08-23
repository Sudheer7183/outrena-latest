# # """
# # mailbridge_client.py — HTTP client for the MailBridge tenancy API.

# # Centralizes all outbound HTTP calls to the MailBridge instance so every
# # feature (send, templates, tracking, account connection) uses the same
# # auth, URL resolution, timeout, and error handling.

# # MailBridge API reference (tenancy mode):
# #   POST   /platform/register                — bootstrap a new tenant
# #   POST   /connect/{provider}/start         — identity propagation (get OAuth URL)
# #   GET    /auth/mail-accounts               — list connected mail accounts
# #   POST   /outbound/send                    — send a single email
# #   POST   /outbound/reply                   — reply in thread
# #   POST   /outbound/sequence/start          — start a follow-up sequence
# #   GET    /templates                        — list templates
# #   POST   /templates                        — create template
# #   GET    /templates/{name}                 — get one template
# #   PUT    /templates/{name}                 — update template
# #   DELETE /templates/{name}                 — delete template
# #   POST   /templates/{name}/preview         — preview template
# #   POST   /templates/{name}/render          — render template
# #   GET    /tracking/{message_id}            — get tracking status
# #   GET    /tracking/sequence/{id}           — sequence tracking
# #   GET    /tracking/suppression             — list suppressed emails
# #   POST   /tracking/suppression             — add to suppression
# #   DELETE /tracking/suppression/{email}     — remove from suppression
# #   POST   /webhook/delivery                 — delivery status webhook
# # """
# # from __future__ import annotations

# # from typing import Any

# # import httpx
# # import structlog

# # from app.core.config import get_settings

# # logger = structlog.get_logger(__name__)


# # class MailBridgeClient:
# #     """Async HTTP client for MailBridge tenancy API calls."""

# #     def __init__(
# #         self,
# #         base_url: str = "",
# #         api_key: str = "",
# #         timeout: float = 30.0,
# #     ) -> None:
# #         settings = get_settings()
# #         self.base_url = (base_url or settings.MAILBRIDGE_DEFAULT_URL).rstrip("/")
# #         self.api_key = api_key or settings.MAILBRIDGE_API_KEY
# #         self.timeout = timeout or float(settings.MAILBRIDGE_TIMEOUT_SECONDS)

# #     def _headers(self, extra: dict[str, str] | None = None) -> dict[str, str]:
# #         h: dict[str, str] = {"Content-Type": "application/json"}
# #         if self.api_key:
# #             h["Authorization"] = f"Bearer {self.api_key}"
# #         if extra:
# #             h.update(extra)
# #         return h

# #     async def _request(
# #         self,
# #         method: str,
# #         path: str,
# #         *,
# #         json: Any = None,
# #         params: dict[str, str] | None = None,
# #         extra_headers: dict[str, str] | None = None,
# #     ) -> dict[str, Any]:
# #         """Make an HTTP request to MailBridge and return the parsed JSON."""
# #         if not self.base_url:
# #             raise RuntimeError("MailBridge base URL is not configured")
# #         url = f"{self.base_url}{path}"
# #         async with httpx.AsyncClient(timeout=self.timeout) as client:
# #             resp = await client.request(
# #                 method,
# #                 url,
# #                 json=json,
# #                 params=params,
# #                 headers=self._headers(extra_headers),
# #             )
# #             if resp.status_code >= 400:
# #                 logger.warning(
# #                     "mailbridge_client.error",
# #                     method=method,
# #                     path=path,
# #                     status=resp.status_code,
# #                     body=resp.text[:500],
# #                 )
# #                 resp.raise_for_status()
# #             if resp.status_code == 204:
# #                 return {}
# #             return resp.json()

# #     # ── Platform Registration ──────────────────────────────────────────────

# #     async def register_platform(
# #         self, name: str, slug: str | None = None, admin_secret: str = ""
# #     ) -> dict[str, Any]:
# #         """POST /platform/register — bootstrap Outrena as a MailBridge tenant.

# #         Returns: {tenant_id, name, slug, api_key}
# #         The api_key is the mb_live_... credential to store in MailBridgeConfig.
# #         """
# #         settings = get_settings()
# #         secret = admin_secret or settings.MAILBRIDGE_PLATFORM_ADMIN_SECRET
# #         payload: dict[str, Any] = {"name": name}
# #         if slug:
# #             payload["slug"] = slug
# #         return await self._request(
# #             "POST",
# #             "/platform/register",
# #             json=payload,
# #             extra_headers={"X-Platform-Admin-Secret": secret},
# #         )

# #     # ── Account Connection (Identity Propagation) ──────────────────────────

# #     async def connect_start(
# #         self,
# #         provider: str,
# #         external_user_id: str,
# #         return_url: str | None = None,
# #     ) -> dict[str, Any]:
# #         """POST /auth/connect/{provider}/start — get OAuth authorize URL.

# #         The external_user_id is the Outrena user's Keycloak UUID.
# #         MailBridge provider names: "google" (not "gmail"), "outlook".
# #         return_url: where MailBridge redirects the user's browser after
# #                     OAuth completes. Falls back to "/" if omitted.
# #         Returns: {authorize_url, state, provider}
# #         """
# #         payload: dict[str, Any] = {"external_user_id": external_user_id}
# #         if return_url:
# #             payload["return_url"] = return_url
# #         return await self._request(
# #             "POST",
# #             f"/auth/connect/{provider}/start",
# #             json=payload,
# #         )

# #     async def list_mail_accounts(
# #         self, external_user_id: str | None = None
# #     ) -> dict[str, Any]:
# #         """List connected mail accounts.

# #         When external_user_id is provided, uses GET /auth/connect/status
# #         which is the platform-facing endpoint (authenticates via API key,
# #         looks up accounts by the integrating platform's user ID).

# #         Without external_user_id, falls back to GET /auth/mail-accounts
# #         which requires a MailBridge session cookie.
# #         """
# #         if external_user_id:
# #             return await self._request(
# #                 "GET",
# #                 "/auth/connect/status",
# #                 params={"external_user_id": external_user_id},
# #             )
# #         return await self._request("GET", "/auth/mail-accounts")

# #     # ── Outbound Email ─────────────────────────────────────────────────────

# #     async def send_email(
# #         self,
# #         *,
# #         to: list[str],
# #         subject: str,
# #         body_html: str = "",
# #         body_text: str = "",
# #         external_user_id: str | None = None,
# #         cc: list[str] | None = None,
# #         bcc: list[str] | None = None,
# #         reply_to: str | None = None,
# #         thread_id: str | None = None,
# #         conversation_id: str | None = None,
# #     ) -> dict[str, Any]:
# #         """POST /outbound/send — send a single email."""
# #         payload: dict[str, Any] = {
# #             "to": to,
# #             "subject": subject,
# #             "body_html": body_html,
# #             "body_text": body_text,
# #         }
# #         if external_user_id:
# #             payload["external_user_id"] = external_user_id
# #         if cc:
# #             payload["cc"] = cc
# #         if bcc:
# #             payload["bcc"] = bcc
# #         if reply_to:
# #             payload["reply_to"] = reply_to
# #         if thread_id:
# #             payload["thread_id"] = thread_id
# #         if conversation_id:
# #             payload["conversation_id"] = conversation_id
# #         return await self._request("POST", "/outbound/send", json=payload)

# #     async def reply_in_thread(
# #         self,
# #         *,
# #         to: list[str],
# #         subject: str,
# #         body_html: str = "",
# #         body_text: str = "",
# #         thread_id: str | None = None,
# #         conversation_id: str | None = None,
# #         in_reply_to_message_id: str | None = None,
# #         external_user_id: str | None = None,
# #     ) -> dict[str, Any]:
# #         """POST /outbound/reply — reply in an existing thread."""
# #         payload: dict[str, Any] = {
# #             "to": to,
# #             "subject": subject,
# #             "body_html": body_html,
# #             "body_text": body_text,
# #         }
# #         if thread_id:
# #             payload["thread_id"] = thread_id
# #         if conversation_id:
# #             payload["conversation_id"] = conversation_id
# #         if in_reply_to_message_id:
# #             payload["in_reply_to_message_id"] = in_reply_to_message_id
# #         if external_user_id:
# #             payload["external_user_id"] = external_user_id
# #         return await self._request("POST", "/outbound/reply", json=payload)

# #     # ── Templates ──────────────────────────────────────────────────────────

# #     async def list_templates(
# #         self, *, tag: str | None = None, tone: str | None = None
# #     ) -> list[dict[str, Any]]:
# #         """GET /templates — list all templates."""
# #         params: dict[str, str] = {}
# #         if tag:
# #             params["tag"] = tag
# #         if tone:
# #             params["tone"] = tone
# #         return await self._request("GET", "/templates", params=params or None)

# #     async def create_template(self, template: dict[str, Any]) -> dict[str, Any]:
# #         """POST /templates — create a new template."""
# #         return await self._request("POST", "/templates", json=template)

# #     async def get_template(self, name: str) -> dict[str, Any]:
# #         """GET /templates/{name} — get one template."""
# #         return await self._request("GET", f"/templates/{name}")

# #     async def update_template(
# #         self, name: str, updates: dict[str, Any]
# #     ) -> dict[str, Any]:
# #         """PUT /templates/{name} — update a template."""
# #         return await self._request("PUT", f"/templates/{name}", json=updates)

# #     async def delete_template(self, name: str) -> dict[str, Any]:
# #         """DELETE /templates/{name} — delete a template."""
# #         return await self._request("DELETE", f"/templates/{name}")

# #     async def preview_template(
# #         self, name: str, variables: dict[str, Any]
# #     ) -> dict[str, Any]:
# #         """POST /templates/{name}/preview — preview with sample variables."""
# #         return await self._request(
# #             "POST", f"/templates/{name}/preview", json={"variables": variables}
# #         )

# #     async def render_template(
# #         self, name: str, variables: dict[str, Any]
# #     ) -> dict[str, Any]:
# #         """POST /templates/{name}/render — render with real variables."""
# #         return await self._request(
# #             "POST", f"/templates/{name}/render", json={"variables": variables}
# #         )

# #     # ── Tracking ───────────────────────────────────────────────────────────

# #     async def get_tracking(self, message_id: str) -> dict[str, Any]:
# #         """GET /tracking/{message_id} — get tracking status for one email."""
# #         return await self._request("GET", f"/tracking/{message_id}")

# #     async def get_sequence_tracking(self, sequence_id: str) -> dict[str, Any]:
# #         """GET /tracking/sequence/{id} — tracking for all emails in a sequence."""
# #         return await self._request("GET", f"/tracking/sequence/{sequence_id}")

# #     async def list_suppression(self) -> dict[str, Any]:
# #         """GET /tracking/suppression — list suppressed email addresses."""
# #         return await self._request("GET", "/tracking/suppression")

# #     async def add_suppression(
# #         self, email: str, reason: str = "Manual suppression"
# #     ) -> dict[str, Any]:
# #         """POST /tracking/suppression — add to suppression list."""
# #         return await self._request(
# #             "POST",
# #             "/tracking/suppression",
# #             json={"email": email, "reason": reason},
# #         )

# #     async def remove_suppression(self, email: str) -> dict[str, Any]:
# #         """DELETE /tracking/suppression/{email} — remove from suppression."""
# #         return await self._request("DELETE", f"/tracking/suppression/{email}")

# #     async def post_delivery_webhook(
# #         self,
# #         message_id: str,
# #         event: str,
# #         reason: str | None = None,
# #     ) -> dict[str, Any]:
# #         """POST /webhook/delivery — send delivery status to MailBridge."""
# #         payload: dict[str, Any] = {
# #             "message_id": message_id,
# #             "event": event,
# #         }
# #         if reason:
# #             payload["reason"] = reason
# #         return await self._request("POST", "/webhook/delivery", json=payload)

# #     async def get_subject_performance(
# #         self, group: str | None = None
# #     ) -> dict[str, Any]:
# #         """GET /tracking/subject-performance — A/B subject line data."""
# #         params = {"group": group} if group else None
# #         return await self._request(
# #             "GET", "/tracking/subject-performance", params=params
# #         )


# # __all__ = ["MailBridgeClient"]

# """
# mailbridge_client.py — HTTP client for the MailBridge tenancy API.

# Centralizes all outbound HTTP calls to the MailBridge instance so every
# feature (send, templates, tracking, account connection) uses the same
# auth, URL resolution, timeout, and error handling.

# MailBridge API reference (tenancy mode):
#   POST   /platform/register                — bootstrap a new tenant
#   POST   /connect/{provider}/start         — identity propagation (get OAuth URL)
#   GET    /auth/mail-accounts               — list connected mail accounts
#   POST   /outbound/send                    — send a single email
#   POST   /outbound/reply                   — reply in thread
#   POST   /outbound/sequence/start          — start a follow-up sequence
#   GET    /templates                        — list templates
#   POST   /templates                        — create template
#   GET    /templates/{name}                 — get one template
#   PUT    /templates/{name}                 — update template
#   DELETE /templates/{name}                 — delete template
#   POST   /templates/{name}/preview         — preview template
#   POST   /templates/{name}/render          — render template
#   GET    /tracking/{message_id}            — get tracking status
#   GET    /tracking/sequence/{id}           — sequence tracking
#   GET    /tracking/suppression             — list suppressed emails
#   POST   /tracking/suppression             — add to suppression
#   DELETE /tracking/suppression/{email}     — remove from suppression
#   POST   /webhook/delivery                 — delivery status webhook
# """
# from __future__ import annotations

# from typing import Any

# import httpx
# import structlog

# from app.core.config import get_settings

# logger = structlog.get_logger(__name__)


# class MailBridgeClient:
#     """Async HTTP client for MailBridge tenancy API calls."""

#     def __init__(
#         self,
#         base_url: str = "",
#         api_key: str = "",
#         timeout: float = 30.0,
#     ) -> None:
#         settings = get_settings()
#         self.base_url = (base_url or settings.MAILBRIDGE_DEFAULT_URL).rstrip("/")
#         self.api_key = api_key or settings.MAILBRIDGE_API_KEY
#         self.timeout = timeout or float(settings.MAILBRIDGE_TIMEOUT_SECONDS)

#     def _headers(self, extra: dict[str, str] | None = None) -> dict[str, str]:
#         h: dict[str, str] = {"Content-Type": "application/json"}
#         if self.api_key:
#             h["Authorization"] = f"Bearer {self.api_key}"
#         if extra:
#             h.update(extra)
#         return h

#     async def _request(
#         self,
#         method: str,
#         path: str,
#         *,
#         json: Any = None,
#         params: dict[str, str] | None = None,
#         extra_headers: dict[str, str] | None = None,
#     ) -> dict[str, Any]:
#         """Make an HTTP request to MailBridge and return the parsed JSON."""
#         if not self.base_url:
#             raise RuntimeError("MailBridge base URL is not configured")
#         url = f"{self.base_url}{path}"
#         try:
#             async with httpx.AsyncClient(timeout=self.timeout) as client:
#                 resp = await client.request(
#                     method,
#                     url,
#                     json=json,
#                     params=params,
#                     headers=self._headers(extra_headers),
#                 )
#         except httpx.ConnectError as exc:
#             raise RuntimeError(
#                 f"MailBridge server is unreachable at {self.base_url}. "
#                 "Check that MailBridge is running and MAILBRIDGE_DEFAULT_URL is correct."
#             ) from exc
#         except httpx.TimeoutException as exc:
#             raise RuntimeError(
#                 f"MailBridge request timed out ({self.timeout}s). "
#                 "The server may be overloaded or unreachable."
#             ) from exc

#         if resp.status_code >= 400:
#             logger.warning(
#                 "mailbridge_client.error",
#                 method=method,
#                 path=path,
#                 status=resp.status_code,
#                 body=resp.text[:500],
#             )
#             # Translate HTTP error codes to descriptive RuntimeErrors so
#             # callers (and ultimately the router) can surface clean messages.
#             if resp.status_code == 401:
#                 raise RuntimeError(
#                     "MailBridge returned 401 Unauthorized. "
#                     "Your MAILBRIDGE_API_KEY (mb_live_...) is missing, expired, or "
#                     "was not registered with this MailBridge instance. "
#                     "Go to Setup → MailBridge → Register Platform to generate a valid key."
#                 )
#             if resp.status_code == 403:
#                 raise RuntimeError(
#                     f"MailBridge returned 403 Forbidden for {method} {path}. "
#                     "The API key may not have permission for this operation."
#                 )
#             if resp.status_code == 404:
#                 raise RuntimeError(
#                     f"MailBridge returned 404 Not Found for {method} {path}. "
#                     "Check that the MailBridge version supports this endpoint."
#                 )
#             raise RuntimeError(
#                 f"MailBridge returned {resp.status_code} for {method} {path}: "
#                 f"{resp.text[:200]}"
#             )

#         if resp.status_code == 204:
#             return {}
#         return resp.json()

#     # ── Platform Registration ──────────────────────────────────────────────

#     async def register_platform(
#         self, name: str, slug: str | None = None, admin_secret: str = ""
#     ) -> dict[str, Any]:
#         """POST /platform/register — bootstrap Outrena as a MailBridge tenant.

#         Returns: {tenant_id, name, slug, api_key}
#         The api_key is the mb_live_... credential to store in MailBridgeConfig.
#         """
#         settings = get_settings()
#         secret = admin_secret or settings.MAILBRIDGE_PLATFORM_ADMIN_SECRET
#         payload: dict[str, Any] = {"name": name}
#         if slug:
#             payload["slug"] = slug
#         return await self._request(
#             "POST",
#             "/platform/register",
#             json=payload,
#             extra_headers={"X-Platform-Admin-Secret": secret},
#         )

#     # ── Account Connection (Identity Propagation) ──────────────────────────

#     async def connect_start(
#         self,
#         provider: str,
#         external_user_id: str,
#         return_url: str | None = None,
#     ) -> dict[str, Any]:
#         """POST /auth/connect/{provider}/start — get OAuth authorize URL.

#         The external_user_id is the Outrena user's Keycloak UUID.
#         MailBridge provider names: "google" (not "gmail"), "outlook".
#         return_url: where MailBridge redirects the user's browser after
#                     OAuth completes. Falls back to "/" if omitted.
#         Returns: {authorize_url, state, provider}
#         """
#         payload: dict[str, Any] = {"external_user_id": external_user_id}
#         if return_url:
#             payload["return_url"] = return_url
#         return await self._request(
#             "POST",
#             f"/auth/connect/{provider}/start",
#             json=payload,
#         )

#     async def list_mail_accounts(
#         self, external_user_id: str | None = None
#     ) -> dict[str, Any]:
#         """List connected mail accounts.

#         When external_user_id is provided, uses GET /auth/connect/status
#         which is the platform-facing endpoint (authenticates via API key,
#         looks up accounts by the integrating platform's user ID).

#         Without external_user_id, falls back to GET /auth/mail-accounts
#         which requires a MailBridge session cookie.
#         """
#         if external_user_id:
#             return await self._request(
#                 "GET",
#                 "/auth/connect/status",
#                 params={"external_user_id": external_user_id},
#             )
#         return await self._request("GET", "/auth/mail-accounts")

#     # ── Outbound Email ─────────────────────────────────────────────────────

#     async def send_email(
#         self,
#         *,
#         to: list[str],
#         subject: str,
#         body_html: str = "",
#         body_text: str = "",
#         external_user_id: str | None = None,
#         cc: list[str] | None = None,
#         bcc: list[str] | None = None,
#         reply_to: str | None = None,
#         thread_id: str | None = None,
#         conversation_id: str | None = None,
#     ) -> dict[str, Any]:
#         """POST /outbound/send — send a single email."""
#         payload: dict[str, Any] = {
#             "to": to,
#             "subject": subject,
#             "body_html": body_html,
#             "body_text": body_text,
#         }
#         if external_user_id:
#             payload["external_user_id"] = external_user_id
#         if cc:
#             payload["cc"] = cc
#         if bcc:
#             payload["bcc"] = bcc
#         if reply_to:
#             payload["reply_to"] = reply_to
#         if thread_id:
#             payload["thread_id"] = thread_id
#         if conversation_id:
#             payload["conversation_id"] = conversation_id
#         return await self._request("POST", "/outbound/send", json=payload)

#     async def reply_in_thread(
#         self,
#         *,
#         to: list[str],
#         subject: str,
#         body_html: str = "",
#         body_text: str = "",
#         thread_id: str | None = None,
#         conversation_id: str | None = None,
#         in_reply_to_message_id: str | None = None,
#         external_user_id: str | None = None,
#     ) -> dict[str, Any]:
#         """POST /outbound/reply — reply in an existing thread."""
#         payload: dict[str, Any] = {
#             "to": to,
#             "subject": subject,
#             "body_html": body_html,
#             "body_text": body_text,
#         }
#         if thread_id:
#             payload["thread_id"] = thread_id
#         if conversation_id:
#             payload["conversation_id"] = conversation_id
#         if in_reply_to_message_id:
#             payload["in_reply_to_message_id"] = in_reply_to_message_id
#         if external_user_id:
#             payload["external_user_id"] = external_user_id
#         return await self._request("POST", "/outbound/reply", json=payload)

#     # ── Templates ──────────────────────────────────────────────────────────

#     async def list_templates(
#         self, *, tag: str | None = None, tone: str | None = None
#     ) -> list[dict[str, Any]]:
#         """GET /templates — list all templates."""
#         params: dict[str, str] = {}
#         if tag:
#             params["tag"] = tag
#         if tone:
#             params["tone"] = tone
#         return await self._request("GET", "/templates", params=params or None)

#     async def create_template(self, template: dict[str, Any]) -> dict[str, Any]:
#         """POST /templates — create a new template."""
#         return await self._request("POST", "/templates", json=template)

#     async def get_template(self, name: str) -> dict[str, Any]:
#         """GET /templates/{name} — get one template."""
#         return await self._request("GET", f"/templates/{name}")

#     async def update_template(
#         self, name: str, updates: dict[str, Any]
#     ) -> dict[str, Any]:
#         """PUT /templates/{name} — update a template."""
#         return await self._request("PUT", f"/templates/{name}", json=updates)

#     async def delete_template(self, name: str) -> dict[str, Any]:
#         """DELETE /templates/{name} — delete a template."""
#         return await self._request("DELETE", f"/templates/{name}")

#     async def preview_template(
#         self, name: str, variables: dict[str, Any]
#     ) -> dict[str, Any]:
#         """POST /templates/{name}/preview — preview with sample variables."""
#         return await self._request(
#             "POST", f"/templates/{name}/preview", json={"variables": variables}
#         )

#     async def render_template(
#         self, name: str, variables: dict[str, Any]
#     ) -> dict[str, Any]:
#         """POST /templates/{name}/render — render with real variables."""
#         return await self._request(
#             "POST", f"/templates/{name}/render", json={"variables": variables}
#         )

#     # ── Tracking ───────────────────────────────────────────────────────────

#     async def get_tracking(self, message_id: str) -> dict[str, Any]:
#         """GET /tracking/{message_id} — get tracking status for one email."""
#         return await self._request("GET", f"/tracking/{message_id}")

#     async def get_sequence_tracking(self, sequence_id: str) -> dict[str, Any]:
#         """GET /tracking/sequence/{id} — tracking for all emails in a sequence."""
#         return await self._request("GET", f"/tracking/sequence/{sequence_id}")

#     async def list_suppression(self) -> dict[str, Any]:
#         """GET /tracking/suppression — list suppressed email addresses."""
#         return await self._request("GET", "/tracking/suppression")

#     async def add_suppression(
#         self, email: str, reason: str = "Manual suppression"
#     ) -> dict[str, Any]:
#         """POST /tracking/suppression — add to suppression list."""
#         return await self._request(
#             "POST",
#             "/tracking/suppression",
#             json={"email": email, "reason": reason},
#         )

#     async def remove_suppression(self, email: str) -> dict[str, Any]:
#         """DELETE /tracking/suppression/{email} — remove from suppression."""
#         return await self._request("DELETE", f"/tracking/suppression/{email}")

#     async def post_delivery_webhook(
#         self,
#         message_id: str,
#         event: str,
#         reason: str | None = None,
#     ) -> dict[str, Any]:
#         """POST /webhook/delivery — send delivery status to MailBridge."""
#         payload: dict[str, Any] = {
#             "message_id": message_id,
#             "event": event,
#         }
#         if reason:
#             payload["reason"] = reason
#         return await self._request("POST", "/webhook/delivery", json=payload)

#     async def get_subject_performance(
#         self, group: str | None = None
#     ) -> dict[str, Any]:
#         """GET /tracking/subject-performance — A/B subject line data."""
#         params = {"group": group} if group else None
#         return await self._request(
#             "GET", "/tracking/subject-performance", params=params
#         )


# __all__ = ["MailBridgeClient"]

"""
mailbridge_client.py — HTTP client for the MailBridge tenancy API.

Centralizes all outbound HTTP calls to the MailBridge instance so every
feature (send, templates, tracking, account connection) uses the same
auth, URL resolution, timeout, and error handling.

MailBridge API reference (tenancy mode):
  POST   /platform/register                — bootstrap a new tenant
  POST   /auth/connect/{provider}/start    — identity propagation (get OAuth URL)
  GET    /auth/connect/status              — list connected accounts for a user
  GET    /auth/connect/replies             — poll for replies received by a user's mailbox
  POST   /outbound/send                    — send a single email
  POST   /outbound/reply                   — reply in thread
  GET    /templates                        — list templates
  POST   /templates                        — create template
  GET    /templates/{name}                 — get one template
  PUT    /templates/{name}                 — update template
  DELETE /templates/{name}                 — delete template
  POST   /templates/{name}/preview         — preview template
  POST   /templates/{name}/render          — render template
  GET    /tracking/{message_id}            — get tracking status
  GET    /tracking/sequence/{id}           — sequence tracking
  GET    /tracking/suppression             — list suppressed emails
  POST   /tracking/suppression             — add to suppression
  DELETE /tracking/suppression/{email}     — remove from suppression
  POST   /webhook/delivery                 — delivery status webhook
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

import httpx
import structlog

from app.core.config import get_settings

logger = structlog.get_logger(__name__)


class MailBridgeClient:
    """Async HTTP client for MailBridge tenancy API calls."""

    def __init__(
        self,
        base_url: str = "",
        api_key: str = "",
        timeout: float = 30.0,
    ) -> None:
        settings = get_settings()
        self.base_url = (base_url or settings.MAILBRIDGE_DEFAULT_URL).rstrip("/")
        self.api_key = api_key or settings.MAILBRIDGE_API_KEY
        self.timeout = timeout or float(settings.MAILBRIDGE_TIMEOUT_SECONDS)

    def _headers(self, extra: dict[str, str] | None = None) -> dict[str, str]:
        h: dict[str, str] = {"Content-Type": "application/json"}
        if self.api_key:
            h["Authorization"] = f"Bearer {self.api_key}"
        if extra:
            h.update(extra)
        return h

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: Any = None,
        params: dict[str, str] | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Make an HTTP request to MailBridge and return the parsed JSON."""
        if not self.base_url:
            raise RuntimeError("MailBridge base URL is not configured")
        url = f"{self.base_url}{path}"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.request(
                    method,
                    url,
                    json=json,
                    params=params,
                    headers=self._headers(extra_headers),
                )
        except httpx.ConnectError as exc:
            raise RuntimeError(
                f"MailBridge server is unreachable at {self.base_url}. "
                "Check that MailBridge is running and MAILBRIDGE_DEFAULT_URL is correct."
            ) from exc
        except httpx.TimeoutException as exc:
            raise RuntimeError(
                f"MailBridge request timed out ({self.timeout}s). "
                "The server may be overloaded or unreachable."
            ) from exc

        if resp.status_code >= 400:
            logger.warning(
                "mailbridge_client.error",
                method=method,
                path=path,
                status=resp.status_code,
                body=resp.text[:500],
            )
            if resp.status_code == 401:
                raise RuntimeError(
                    "MailBridge returned 401 Unauthorized. "
                    "Your MAILBRIDGE_API_KEY (mb_live_...) is missing, expired, or "
                    "was not registered with this MailBridge instance. "
                    "Go to Setup → MailBridge → Register Platform to generate a valid key."
                )
            if resp.status_code == 403:
                raise RuntimeError(
                    f"MailBridge returned 403 Forbidden for {method} {path}. "
                    "The API key may not have permission for this operation."
                )
            if resp.status_code == 404:
                raise RuntimeError(
                    f"MailBridge returned 404 Not Found for {method} {path}. "
                    "Check that the MailBridge version supports this endpoint."
                )
            raise RuntimeError(
                f"MailBridge returned {resp.status_code} for {method} {path}: "
                f"{resp.text[:200]}"
            )

        if resp.status_code == 204:
            return {}
        return resp.json()

    # ── Platform Registration ──────────────────────────────────────────────

    async def register_platform(
        self, name: str, slug: str | None = None, admin_secret: str = ""
    ) -> dict[str, Any]:
        """POST /platform/register — bootstrap Outrena as a MailBridge tenant.

        Returns: {tenant_id, name, slug, api_key}
        The api_key is the mb_live_... credential to store in MailBridgeConfig.
        """
        settings = get_settings()
        secret = admin_secret or settings.MAILBRIDGE_PLATFORM_ADMIN_SECRET
        payload: dict[str, Any] = {"name": name}
        if slug:
            payload["slug"] = slug
        return await self._request(
            "POST",
            "/platform/register",
            json=payload,
            extra_headers={"X-Platform-Admin-Secret": secret},
        )

    # ── Account Connection (Identity Propagation) ──────────────────────────

    async def connect_start(
        self,
        provider: str,
        external_user_id: str,
        return_url: str | None = None,
    ) -> dict[str, Any]:
        """POST /auth/connect/{provider}/start — get OAuth authorize URL.

        The external_user_id is the Outrena user's Keycloak UUID.
        MailBridge provider names: "google" (not "gmail"), "outlook".
        return_url: where MailBridge redirects the user's browser after
                    OAuth completes. Falls back to "/" if omitted.
        Returns: {authorize_url, state, provider}
        """
        payload: dict[str, Any] = {"external_user_id": external_user_id}
        if return_url:
            payload["return_url"] = return_url
        return await self._request(
            "POST",
            f"/auth/connect/{provider}/start",
            json=payload,
        )

    async def list_mail_accounts(
        self, external_user_id: str | None = None
    ) -> dict[str, Any]:
        """List connected mail accounts.

        When external_user_id is provided, uses GET /auth/connect/status
        which is the platform-facing endpoint (authenticates via API key,
        looks up accounts by the integrating platform's user ID).

        Without external_user_id, falls back to GET /auth/mail-accounts
        which requires a MailBridge session cookie.
        """
        if external_user_id:
            return await self._request(
                "GET",
                "/auth/connect/status",
                params={"external_user_id": external_user_id},
            )
        return await self._request("GET", "/auth/mail-accounts")

    async def get_connect_replies(
        self,
        external_user_id: str,
        sender: str,
        since: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """GET /auth/connect/replies — poll for replies to a user's mailbox.

        MailBridge's reply_recorder writes a row to reply_events whenever
        a connected mailbox receives any email. This endpoint lets Outrena
        ask "has user X's mailbox received a reply from prospect Y since
        the sequence was sent?"

        Args:
            external_user_id: Keycloak UUID of the Outrena user (same value
                used during POST /auth/connect/{provider}/start).
            sender: The prospect's email address to filter by.
            since: Only return replies received at or after this datetime
                (ISO-8601). Pass Sequence.sentAt so pre-existing inbox
                messages before the sequence was sent are excluded.

        Returns:
            List of reply event dicts, each with:
                id, mail_account_id, from_address, subject,
                message_id, received_at (ISO string)
            Empty list when no replies found — never raises on empty.
        """
        params: dict[str, str] = {
            "external_user_id": external_user_id,
            "sender": sender,
        }
        if since is not None:
            params["since"] = since.isoformat()

        data = await self._request(
            "GET",
            "/auth/connect/replies",
            params=params,
        )
        # MailBridge returns {"replies": [...]}
        replies = data.get("replies", [])
        if not isinstance(replies, list):
            return []
        return replies

    # ── Outbound Email ─────────────────────────────────────────────────────

    async def send_email(
        self,
        *,
        to: list[str],
        subject: str,
        body_html: str = "",
        body_text: str = "",
        external_user_id: str | None = None,
        cc: list[str] | None = None,
        bcc: list[str] | None = None,
        reply_to: str | None = None,
        thread_id: str | None = None,
        conversation_id: str | None = None,
    ) -> dict[str, Any]:
        """POST /outbound/send — send a single email."""
        payload: dict[str, Any] = {
            "to": to,
            "subject": subject,
            "body_html": body_html,
            "body_text": body_text,
        }
        if external_user_id:
            payload["external_user_id"] = external_user_id
        if cc:
            payload["cc"] = cc
        if bcc:
            payload["bcc"] = bcc
        if reply_to:
            payload["reply_to"] = reply_to
        if thread_id:
            payload["thread_id"] = thread_id
        if conversation_id:
            payload["conversation_id"] = conversation_id
        return await self._request("POST", "/outbound/send", json=payload)

    async def reply_in_thread(
        self,
        *,
        to: list[str],
        subject: str,
        body_html: str = "",
        body_text: str = "",
        thread_id: str | None = None,
        conversation_id: str | None = None,
        in_reply_to_message_id: str | None = None,
        external_user_id: str | None = None,
    ) -> dict[str, Any]:
        """POST /outbound/reply — reply in an existing thread."""
        payload: dict[str, Any] = {
            "to": to,
            "subject": subject,
            "body_html": body_html,
            "body_text": body_text,
        }
        if thread_id:
            payload["thread_id"] = thread_id
        if conversation_id:
            payload["conversation_id"] = conversation_id
        if in_reply_to_message_id:
            payload["in_reply_to_message_id"] = in_reply_to_message_id
        if external_user_id:
            payload["external_user_id"] = external_user_id
        return await self._request("POST", "/outbound/reply", json=payload)

    # ── Templates ──────────────────────────────────────────────────────────

    async def list_templates(
        self, *, tag: str | None = None, tone: str | None = None
    ) -> list[dict[str, Any]]:
        """GET /templates — list all templates."""
        params: dict[str, str] = {}
        if tag:
            params["tag"] = tag
        if tone:
            params["tone"] = tone
        return await self._request("GET", "/templates", params=params or None)

    async def create_template(self, template: dict[str, Any]) -> dict[str, Any]:
        """POST /templates — create a new template."""
        return await self._request("POST", "/templates", json=template)

    async def get_template(self, name: str) -> dict[str, Any]:
        """GET /templates/{name} — get one template."""
        return await self._request("GET", f"/templates/{name}")

    async def update_template(
        self, name: str, updates: dict[str, Any]
    ) -> dict[str, Any]:
        """PUT /templates/{name} — update a template."""
        return await self._request("PUT", f"/templates/{name}", json=updates)

    async def delete_template(self, name: str) -> dict[str, Any]:
        """DELETE /templates/{name} — delete a template."""
        return await self._request("DELETE", f"/templates/{name}")

    async def preview_template(
        self, name: str, variables: dict[str, Any]
    ) -> dict[str, Any]:
        """POST /templates/{name}/preview — preview with sample variables."""
        return await self._request(
            "POST", f"/templates/{name}/preview", json={"variables": variables}
        )

    async def render_template(
        self, name: str, variables: dict[str, Any]
    ) -> dict[str, Any]:
        """POST /templates/{name}/render — render with real variables."""
        return await self._request(
            "POST", f"/templates/{name}/render", json={"variables": variables}
        )

    # ── Tracking ───────────────────────────────────────────────────────────

    async def get_tracking(self, message_id: str) -> dict[str, Any]:
        """GET /tracking/{message_id} — get tracking status for one email."""
        return await self._request("GET", f"/tracking/{message_id}")

    async def get_sequence_tracking(self, sequence_id: str) -> dict[str, Any]:
        """GET /tracking/sequence/{id} — tracking for all emails in a sequence."""
        return await self._request("GET", f"/tracking/sequence/{sequence_id}")

    async def list_suppression(self) -> dict[str, Any]:
        """GET /tracking/suppression — list suppressed email addresses."""
        return await self._request("GET", "/tracking/suppression")

    async def add_suppression(
        self, email: str, reason: str = "Manual suppression"
    ) -> dict[str, Any]:
        """POST /tracking/suppression — add to suppression list."""
        return await self._request(
            "POST",
            "/tracking/suppression",
            json={"email": email, "reason": reason},
        )

    async def remove_suppression(self, email: str) -> dict[str, Any]:
        """DELETE /tracking/suppression/{email} — remove from suppression."""
        return await self._request("DELETE", f"/tracking/suppression/{email}")

    async def post_delivery_webhook(
        self,
        message_id: str,
        event: str,
        reason: str | None = None,
    ) -> dict[str, Any]:
        """POST /webhook/delivery — send delivery status to MailBridge."""
        payload: dict[str, Any] = {
            "message_id": message_id,
            "event": event,
        }
        if reason:
            payload["reason"] = reason
        return await self._request("POST", "/webhook/delivery", json=payload)

    async def get_subject_performance(
        self, group: str | None = None
    ) -> dict[str, Any]:
        """GET /tracking/subject-performance — A/B subject line data."""
        params = {"group": group} if group else None
        return await self._request(
            "GET", "/tracking/subject-performance", params=params
        )


__all__ = ["MailBridgeClient"]