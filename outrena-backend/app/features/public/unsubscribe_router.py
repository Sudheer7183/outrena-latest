

# """
# unsubscribe_router.py — Public one-click unsubscribe endpoint.

# One-click unsubscribe without login, token-verified.

# Endpoints:
#     POST /public/unsubscribe
#         JSON body:
#         {
#             "token": "...",
#             "tenant_slug": "acme"
#         }

#     GET /public/unsubscribe
#         Query params:
#             ?token=...&tenant_slug=...

# Important:
#     Prospect updates use fully schema-qualified table names.

#     ConsentLog insertion is performed inside a SAVEPOINT so that a
#     ConsentLog failure does NOT abort/rollback the main Prospect update.
# """

# from __future__ import annotations

# from datetime import datetime, timezone

# import structlog
# from fastapi import APIRouter, HTTPException, Query, status
# from fastapi.responses import HTMLResponse, JSONResponse
# from pydantic import BaseModel
# from sqlalchemy import text

# from app.core.database import AsyncSessionLocal

# logger = structlog.get_logger(__name__)

# router = APIRouter(prefix="/public", tags=["Public"])


# class UnsubscribeRequest(BaseModel):
#     token: str
#     tenant_slug: str


# def _schema_name(tenant_slug: str) -> str:
#     """
#     Convert tenant slug to PostgreSQL schema name.

#     Example:
#         acme -> tenant_acme
#         my-company -> tenant_my_company
#     """
#     return f"tenant_{tenant_slug.replace('-', '_')}"


# async def _process_unsubscribe(token: str, tenant_slug: str) -> dict:
#     """
#     Process an unsubscribe request.

#     Flow:

#         1. Validate request
#         2. Resolve tenant schema
#         3. Log database identity
#         4. Find prospect
#         5. Log current prospect state
#         6. Check idempotency
#         7. Update Prospect
#         8. Verify UPDATE result
#         9. Insert ConsentLog inside SAVEPOINT
#         10. Commit Prospect transaction
#         11. Verify persisted state after commit
#         12. Return success
#     """

#     # ============================================================
#     # 1. Validate input
#     # ============================================================

#     logger.info(
#         "unsubscribe.request_received",
#         tenant_slug=tenant_slug,
#         token_present=bool(token),
#         token_length=len(token) if token else 0,
#     )

#     if not token or not tenant_slug:
#         logger.warning(
#             "unsubscribe.invalid_request",
#             tenant_slug=tenant_slug,
#             token_present=bool(token),
#         )

#         raise HTTPException(
#             status_code=status.HTTP_400_BAD_REQUEST,
#             detail="token and tenant_slug are required",
#         )

#     # ============================================================
#     # 2. Resolve tenant schema
#     # ============================================================

#     schema = _schema_name(tenant_slug)

#     logger.info(
#         "unsubscribe.schema_resolved",
#         tenant_slug=tenant_slug,
#         schema=schema,
#     )

#     async with AsyncSessionLocal() as db:

#         try:
#             # ========================================================
#             # 3. Database identity
#             #
#             # This is important to determine exactly which PostgreSQL
#             # database/server the backend is connected to.
#             # ========================================================

#             logger.info(
#                 "unsubscribe.database_identity_check_start",
#                 tenant_slug=tenant_slug,
#                 schema=schema,
#             )

#             db_info_result = await db.execute(
#                 text(
#                     """
#                     SELECT
#                         current_database() AS database,
#                         current_user AS db_user,
#                         current_schema() AS current_schema,
#                         current_setting('search_path') AS search_path,
#                         inet_server_addr() AS server_ip,
#                         inet_server_port() AS server_port,
#                         pg_backend_pid() AS backend_pid
#                     """
#                 )
#             )

#             db_info = db_info_result.mappings().first()

#             logger.info(
#                 "unsubscribe.database_identity",
#                 tenant_slug=tenant_slug,
#                 schema=schema,
#                 database=(
#                     db_info["database"]
#                     if db_info
#                     else None
#                 ),
#                 db_user=(
#                     db_info["db_user"]
#                     if db_info
#                     else None
#                 ),
#                 current_schema=(
#                     db_info["current_schema"]
#                     if db_info
#                     else None
#                 ),
#                 search_path=(
#                     db_info["search_path"]
#                     if db_info
#                     else None
#                 ),
#                 server_ip=(
#                     str(db_info["server_ip"])
#                     if db_info and db_info["server_ip"]
#                     else None
#                 ),
#                 server_port=(
#                     db_info["server_port"]
#                     if db_info
#                     else None
#                 ),
#                 backend_pid=(
#                     db_info["backend_pid"]
#                     if db_info
#                     else None
#                 ),
#             )

#             # ========================================================
#             # 4. Find prospect by unsubscribe token
#             # ========================================================

#             logger.info(
#                 "unsubscribe.prospect_lookup_start",
#                 tenant_slug=tenant_slug,
#                 schema=schema,
#             )

#             result = await db.execute(
#                 text(
#                     f'''
#                     SELECT
#                         id,
#                         "firstName",
#                         "email",
#                         suppressed,
#                         consent_status,
#                         "suppressedAt",
#                         "updatedAt"
#                     FROM "{schema}"."Prospect"
#                     WHERE "unsubscribeToken" = :token
#                     LIMIT 1
#                     '''
#                 ),
#                 {
#                     "token": token,
#                 },
#             )

#             row = result.mappings().first()

#             # ========================================================
#             # 5. Prospect not found
#             # ========================================================

#             if row is None:

#                 logger.warning(
#                     "unsubscribe.token_not_found",
#                     tenant_slug=tenant_slug,
#                     schema=schema,
#                 )

#                 # Don't reveal whether token is valid.
#                 return {
#                     "unsubscribed": True,
#                     "message": "You have been unsubscribed.",
#                 }

#             # ========================================================
#             # 6. Extract prospect information
#             # ========================================================

#             prospect_id = row["id"]
#             first_name = row.get("firstName") or "there"

#             logger.info(
#                 "unsubscribe.prospect_found",
#                 tenant_slug=tenant_slug,
#                 schema=schema,
#                 prospect_id=prospect_id,
#                 first_name=first_name,
#                 email=row.get("email"),
#                 suppressed=row.get("suppressed"),
#                 consent_status=row.get("consent_status"),
#                 suppressed_at=row.get("suppressedAt"),
#                 updated_at=row.get("updatedAt"),
#             )

#             # ========================================================
#             # 7. Log state BEFORE update
#             # ========================================================

#             logger.info(
#                 "unsubscribe.before_update_state",
#                 tenant_slug=tenant_slug,
#                 schema=schema,
#                 prospect_id=prospect_id,
#                 suppressed=row.get("suppressed"),
#                 consent_status=row.get("consent_status"),
#                 suppressed_at=row.get("suppressedAt"),
#                 updated_at=row.get("updatedAt"),
#             )

#             # ========================================================
#             # 8. Idempotency
#             # ========================================================

#             if row.get("consent_status") == "withdrawn":

#                 logger.info(
#                     "unsubscribe.already_withdrawn",
#                     tenant_slug=tenant_slug,
#                     schema=schema,
#                     prospect_id=prospect_id,
#                     suppressed=row.get("suppressed"),
#                     consent_status=row.get("consent_status"),
#                     suppressed_at=row.get("suppressedAt"),
#                 )

#                 return {
#                     "unsubscribed": True,
#                     "message": (
#                         f"Hi {first_name}, "
#                         "you were already unsubscribed."
#                     ),
#                 }

#             # ========================================================
#             # 9. Prepare timestamp
#             # ========================================================

#             now = datetime.now(timezone.utc)

#             logger.info(
#                 "unsubscribe.update_start",
#                 tenant_slug=tenant_slug,
#                 schema=schema,
#                 prospect_id=prospect_id,
#                 new_suppressed=True,
#                 new_consent_status="withdrawn",
#                 timestamp=now,
#             )

#             # ========================================================
#             # 10. Update Prospect
#             #
#             # RETURNING gives us the actual row PostgreSQL changed.
#             # ========================================================

#             update_result = await db.execute(
#                 text(
#                     f'''
#                     UPDATE "{schema}"."Prospect"
#                     SET
#                         consent_status = :status,
#                         suppressed = true,
#                         "suppressedAt" = :now,
#                         "updatedAt" = :now
#                     WHERE id = :id
#                     RETURNING
#                         id,
#                         "firstName",
#                         "email",
#                         suppressed,
#                         consent_status,
#                         "suppressedAt",
#                         "updatedAt"
#                     '''
#                 ),
#                 {
#                     "status": "withdrawn",
#                     "now": now,
#                     "id": prospect_id,
#                 },
#             )

#             updated_row = update_result.mappings().first()

#             rows_updated = (
#                 1
#                 if updated_row is not None
#                 else 0
#             )

#             # ========================================================
#             # 11. Log UPDATE result
#             # ========================================================

#             logger.info(
#                 "unsubscribe.update_result",
#                 tenant_slug=tenant_slug,
#                 schema=schema,
#                 prospect_id=prospect_id,
#                 rows_updated=rows_updated,
#                 updated_row=(
#                     dict(updated_row)
#                     if updated_row
#                     else None
#                 ),
#             )

#             # ========================================================
#             # 12. Ensure UPDATE actually returned a row
#             # ========================================================

#             if updated_row is None:

#                 logger.error(
#                     "unsubscribe.update_returned_no_row",
#                     tenant_slug=tenant_slug,
#                     schema=schema,
#                     prospect_id=prospect_id,
#                     rows_updated=rows_updated,
#                 )

#                 raise RuntimeError(
#                     "Prospect UPDATE returned no row"
#                 )

#             # ========================================================
#             # 13. Log state AFTER UPDATE
#             # ========================================================

#             logger.info(
#                 "unsubscribe.after_update_state",
#                 tenant_slug=tenant_slug,
#                 schema=schema,
#                 prospect_id=prospect_id,
#                 suppressed=updated_row.get("suppressed"),
#                 consent_status=updated_row.get("consent_status"),
#                 suppressed_at=updated_row.get("suppressedAt"),
#                 updated_at=updated_row.get("updatedAt"),
#             )

#             # ========================================================
#             # 14. Validate UPDATE result
#             # ========================================================

#             if updated_row.get("suppressed") is not True:

#                 logger.error(
#                     "unsubscribe.update_suppressed_MISMATCH",
#                     tenant_slug=tenant_slug,
#                     schema=schema,
#                     prospect_id=prospect_id,
#                     expected=True,
#                     actual=updated_row.get("suppressed"),
#                 )

#                 raise RuntimeError(
#                     "Prospect UPDATE did not set suppressed=true"
#                 )

#             if updated_row.get("consent_status") != "withdrawn":

#                 logger.error(
#                     "unsubscribe.update_consent_MISMATCH",
#                     tenant_slug=tenant_slug,
#                     schema=schema,
#                     prospect_id=prospect_id,
#                     expected="withdrawn",
#                     actual=updated_row.get("consent_status"),
#                 )

#                 raise RuntimeError(
#                     "Prospect UPDATE did not set consent_status=withdrawn"
#                 )

#             logger.info(
#                 "unsubscribe.update_values_verified",
#                 tenant_slug=tenant_slug,
#                 schema=schema,
#                 prospect_id=prospect_id,
#                 suppressed=updated_row.get("suppressed"),
#                 consent_status=updated_row.get("consent_status"),
#             )

#             # ========================================================
#             # 15. Pre-commit verification
#             # ========================================================

#             logger.info(
#                 "unsubscribe.pre_commit_verification_start",
#                 tenant_slug=tenant_slug,
#                 schema=schema,
#                 prospect_id=prospect_id,
#             )

#             pre_commit_result = await db.execute(
#                 text(
#                     f'''
#                     SELECT
#                         id,
#                         "firstName",
#                         "email",
#                         suppressed,
#                         consent_status,
#                         "suppressedAt",
#                         "updatedAt"
#                     FROM "{schema}"."Prospect"
#                     WHERE id = :id
#                     '''
#                 ),
#                 {
#                     "id": prospect_id,
#                 },
#             )

#             pre_commit_row = (
#                 pre_commit_result.mappings().first()
#             )

#             logger.info(
#                 "unsubscribe.pre_commit_verification",
#                 tenant_slug=tenant_slug,
#                 schema=schema,
#                 prospect_id=prospect_id,
#                 verified_row=(
#                     dict(pre_commit_row)
#                     if pre_commit_row
#                     else None
#                 ),
#             )

#             if pre_commit_row is None:

#                 logger.error(
#                     "unsubscribe.pre_commit_row_missing",
#                     tenant_slug=tenant_slug,
#                     schema=schema,
#                     prospect_id=prospect_id,
#                 )

#                 raise RuntimeError(
#                     "Prospect disappeared before commit"
#                 )

#             if pre_commit_row["suppressed"] is not True:

#                 logger.error(
#                     "unsubscribe.pre_commit_suppressed_MISMATCH",
#                     tenant_slug=tenant_slug,
#                     schema=schema,
#                     prospect_id=prospect_id,
#                     expected=True,
#                     actual=pre_commit_row["suppressed"],
#                 )

#                 raise RuntimeError(
#                     "suppressed value changed before commit"
#                 )

#             if pre_commit_row["consent_status"] != "withdrawn":

#                 logger.error(
#                     "unsubscribe.pre_commit_consent_MISMATCH",
#                     tenant_slug=tenant_slug,
#                     schema=schema,
#                     prospect_id=prospect_id,
#                     expected="withdrawn",
#                     actual=pre_commit_row["consent_status"],
#                 )

#                 raise RuntimeError(
#                     "consent_status changed before commit"
#                 )

#             logger.info(
#                 "unsubscribe.pre_commit_values_verified",
#                 tenant_slug=tenant_slug,
#                 schema=schema,
#                 prospect_id=prospect_id,
#                 suppressed=pre_commit_row["suppressed"],
#                 consent_status=pre_commit_row["consent_status"],
#             )

#             # ========================================================
#             # 16. ConsentLog
#             #
#             # IMPORTANT:
#             #
#             # This uses a SAVEPOINT.
#             #
#             # If ConsentLog INSERT fails:
#             #
#             #     SAVEPOINT
#             #         ↓
#             #     INSERT fails
#             #         ↓
#             #     ROLLBACK TO SAVEPOINT
#             #         ↓
#             #     Prospect UPDATE remains alive
#             #         ↓
#             #     COMMIT
#             #
#             # Without begin_nested(), a PostgreSQL error would put
#             # the entire transaction into an aborted state.
#             # ========================================================

#             logger.info(
#                 "unsubscribe.consent_log_start",
#                 tenant_slug=tenant_slug,
#                 schema=schema,
#                 prospect_id=prospect_id,
#             )

#             consent_log_inserted = False

#             try:

#                 async with db.begin_nested():

#                     consent_result = await db.execute(
#                         text(
#                             f'''
#                             INSERT INTO "{schema}"."ConsentLog"
#                             (
#                                 id,
#                                 "prospectId",
#                                 action,
#                                 "performedBy",
#                                 timestamp
#                             )
#                             VALUES
#                             (
#                                 gen_random_uuid()::text,
#                                 :pid,
#                                 'unsubscribed',
#                                 'one_click_link',
#                                 :now
#                             )
#                             '''
#                         ),
#                         {
#                             "pid": prospect_id,
#                             "now": now,
#                         },
#                     )

#                     consent_log_inserted = True

#                     logger.info(
#                         "unsubscribe.consent_log_success",
#                         tenant_slug=tenant_slug,
#                         schema=schema,
#                         prospect_id=prospect_id,
#                         rows_inserted=consent_result.rowcount,
#                     )

#             except Exception as consent_error:

#                 logger.exception(
#                     "unsubscribe.consent_log_failed",
#                     tenant_slug=tenant_slug,
#                     schema=schema,
#                     prospect_id=prospect_id,
#                     error_type=type(consent_error).__name__,
#                     error=str(consent_error),
#                 )

#                 logger.warning(
#                     "unsubscribe.consent_log_skipped_prospect_update_preserved",
#                     tenant_slug=tenant_slug,
#                     schema=schema,
#                     prospect_id=prospect_id,
#                 )

#                 # DO NOT rollback the main transaction here.
#                 #
#                 # begin_nested() already rolled back the SAVEPOINT.
#                 #
#                 # The Prospect UPDATE remains in the main transaction.

#             # ========================================================
#             # 17. Verify Prospect again after ConsentLog attempt
#             #
#             # This confirms that a ConsentLog failure did not poison
#             # the main transaction.
#             # ========================================================

#             logger.info(
#                 "unsubscribe.before_commit_final_check_start",
#                 tenant_slug=tenant_slug,
#                 schema=schema,
#                 prospect_id=prospect_id,
#                 consent_log_inserted=consent_log_inserted,
#             )

#             final_pre_commit_result = await db.execute(
#                 text(
#                     f'''
#                     SELECT
#                         id,
#                         suppressed,
#                         consent_status,
#                         "suppressedAt",
#                         "updatedAt"
#                     FROM "{schema}"."Prospect"
#                     WHERE id = :id
#                     '''
#                 ),
#                 {
#                     "id": prospect_id,
#                 },
#             )

#             final_pre_commit_row = (
#                 final_pre_commit_result.mappings().first()
#             )

#             logger.info(
#                 "unsubscribe.before_commit_final_check",
#                 tenant_slug=tenant_slug,
#                 schema=schema,
#                 prospect_id=prospect_id,
#                 final_pre_commit_row=(
#                     dict(final_pre_commit_row)
#                     if final_pre_commit_row
#                     else None
#                 ),
#             )

#             if final_pre_commit_row is None:

#                 logger.error(
#                     "unsubscribe.before_commit_prospect_missing",
#                     tenant_slug=tenant_slug,
#                     schema=schema,
#                     prospect_id=prospect_id,
#                 )

#                 raise RuntimeError(
#                     "Prospect missing before final commit"
#                 )

#             if final_pre_commit_row["suppressed"] is not True:

#                 logger.error(
#                     "unsubscribe.before_commit_suppressed_MISMATCH",
#                     tenant_slug=tenant_slug,
#                     schema=schema,
#                     prospect_id=prospect_id,
#                     expected=True,
#                     actual=final_pre_commit_row["suppressed"],
#                 )

#                 raise RuntimeError(
#                     "Prospect suppressed value is incorrect before commit"
#                 )

#             if final_pre_commit_row["consent_status"] != "withdrawn":

#                 logger.error(
#                     "unsubscribe.before_commit_consent_MISMATCH",
#                     tenant_slug=tenant_slug,
#                     schema=schema,
#                     prospect_id=prospect_id,
#                     expected="withdrawn",
#                     actual=final_pre_commit_row["consent_status"],
#                 )

#                 raise RuntimeError(
#                     "Prospect consent status is incorrect before commit"
#                 )

#             # ========================================================
#             # 18. COMMIT
#             # ========================================================

#             logger.info(
#                 "unsubscribe.commit_start",
#                 tenant_slug=tenant_slug,
#                 schema=schema,
#                 prospect_id=prospect_id,
#             )

#             await db.commit()

#             logger.info(
#                 "unsubscribe.commit_success",
#                 tenant_slug=tenant_slug,
#                 schema=schema,
#                 prospect_id=prospect_id,
#             )

#             # ========================================================
#             # 19. POST-COMMIT VERIFICATION
#             #
#             # This is the most important diagnostic query.
#             #
#             # It runs AFTER COMMIT and reads the database again.
#             # ========================================================

#             logger.info(
#                 "unsubscribe.post_commit_verification_start",
#                 tenant_slug=tenant_slug,
#                 schema=schema,
#                 prospect_id=prospect_id,
#             )

#             post_commit_result = await db.execute(
#                 text(
#                     f'''
#                     SELECT
#                         id,
#                         "firstName",
#                         "email",
#                         suppressed,
#                         consent_status,
#                         "suppressedAt",
#                         "updatedAt"
#                     FROM "{schema}"."Prospect"
#                     WHERE id = :id
#                     '''
#                 ),
#                 {
#                     "id": prospect_id,
#                 },
#             )

#             post_commit_row = (
#                 post_commit_result.mappings().first()
#             )

#             logger.info(
#                 "unsubscribe.post_commit_verification",
#                 tenant_slug=tenant_slug,
#                 schema=schema,
#                 prospect_id=prospect_id,
#                 verified_row=(
#                     dict(post_commit_row)
#                     if post_commit_row
#                     else None
#                 ),
#             )

#             # ========================================================
#             # 20. Verify persisted suppressed value
#             # ========================================================

#             if post_commit_row is None:

#                 logger.error(
#                     "unsubscribe.post_commit_row_missing",
#                     tenant_slug=tenant_slug,
#                     schema=schema,
#                     prospect_id=prospect_id,
#                 )

#             else:

#                 persisted_suppressed = (
#                     post_commit_row["suppressed"]
#                 )

#                 persisted_consent_status = (
#                     post_commit_row["consent_status"]
#                 )

#                 if persisted_suppressed is True:

#                     logger.info(
#                         "unsubscribe.persisted_suppressed_verified",
#                         tenant_slug=tenant_slug,
#                         schema=schema,
#                         prospect_id=prospect_id,
#                         suppressed=persisted_suppressed,
#                     )

#                 else:

#                     logger.error(
#                         "unsubscribe.persisted_suppressed_MISMATCH",
#                         tenant_slug=tenant_slug,
#                         schema=schema,
#                         prospect_id=prospect_id,
#                         expected=True,
#                         actual=persisted_suppressed,
#                     )

#                 # ====================================================
#                 # 21. Verify persisted consent status
#                 # ====================================================

#                 if persisted_consent_status == "withdrawn":

#                     logger.info(
#                         "unsubscribe.persisted_consent_verified",
#                         tenant_slug=tenant_slug,
#                         schema=schema,
#                         prospect_id=prospect_id,
#                         consent_status=persisted_consent_status,
#                     )

#                 else:

#                     logger.error(
#                         "unsubscribe.persisted_consent_MISMATCH",
#                         tenant_slug=tenant_slug,
#                         schema=schema,
#                         prospect_id=prospect_id,
#                         expected="withdrawn",
#                         actual=persisted_consent_status,
#                     )

#             # ========================================================
#             # 22. Final state summary
#             # ========================================================

#             logger.info(
#                 "unsubscribe.final_state",
#                 tenant_slug=tenant_slug,
#                 schema=schema,
#                 prospect_id=prospect_id,
#                 rows_updated=rows_updated,
#                 consent_log_inserted=consent_log_inserted,
#                 final_suppressed=(
#                     post_commit_row["suppressed"]
#                     if post_commit_row
#                     else None
#                 ),
#                 final_consent_status=(
#                     post_commit_row["consent_status"]
#                     if post_commit_row
#                     else None
#                 ),
#                 final_suppressed_at=(
#                     post_commit_row["suppressedAt"]
#                     if post_commit_row
#                     else None
#                 ),
#                 final_updated_at=(
#                     post_commit_row["updatedAt"]
#                     if post_commit_row
#                     else None
#                 ),
#             )

#             # ========================================================
#             # 23. Final success
#             # ========================================================

#             logger.info(
#                 "unsubscribe.success",
#                 tenant_slug=tenant_slug,
#                 schema=schema,
#                 prospect_id=prospect_id,
#                 rows_updated=rows_updated,
#                 consent_log_inserted=consent_log_inserted,
#             )

#             return {
#                 "unsubscribed": True,
#                 "message": (
#                     f"Hi {first_name}, "
#                     "you have been unsubscribed successfully."
#                 ),
#             }

#         except HTTPException:
#             raise

#         except Exception as exc:

#             # ========================================================
#             # 24. Unexpected failure
#             # ========================================================

#             logger.exception(
#                 "unsubscribe.failed",
#                 tenant_slug=tenant_slug,
#                 schema=schema,
#                 error_type=type(exc).__name__,
#                 error=str(exc),
#             )

#             # ========================================================
#             # 25. Rollback
#             # ========================================================

#             try:

#                 await db.rollback()

#                 logger.info(
#                     "unsubscribe.rollback_success",
#                     tenant_slug=tenant_slug,
#                     schema=schema,
#                 )

#             except Exception as rollback_error:

#                 logger.exception(
#                     "unsubscribe.rollback_failed",
#                     tenant_slug=tenant_slug,
#                     schema=schema,
#                     error_type=type(rollback_error).__name__,
#                     error=str(rollback_error),
#                 )

#             raise


# @router.post(
#     "/unsubscribe",
#     summary="One-click email unsubscribe (JSON)",
# )
# async def unsubscribe_post(
#     body: UnsubscribeRequest,
# ) -> JSONResponse:
#     """
#     One-click unsubscribe via JSON POST.

#     Sets:

#         Prospect.consent_status = 'withdrawn'
#         Prospect.suppressed = true

#     Returns 200 regardless of whether the token was found.
#     """

#     logger.info(
#         "unsubscribe.post_endpoint",
#         tenant_slug=body.tenant_slug,
#         token_present=bool(body.token),
#     )

#     result = await _process_unsubscribe(
#         body.token,
#         body.tenant_slug,
#     )

#     return JSONResponse(
#         content=result,
#         status_code=200,
#     )


# @router.get(
#     "/unsubscribe",
#     summary="One-click email unsubscribe (GET — email client support)",
# )
# async def unsubscribe_get(
#     token: str = Query(
#         ...,
#         description="Prospect unsubscribe token",
#     ),
#     tenant_slug: str = Query(
#         ...,
#         description="Tenant slug",
#     ),
# ) -> HTMLResponse:
#     """
#     One-click unsubscribe via GET.

#     Email clients that implement RFC 8058 List-Unsubscribe-Post
#     may send POST, while normal browser clicks typically use GET.
#     """

#     logger.info(
#         "unsubscribe.get_endpoint",
#         tenant_slug=tenant_slug,
#         token_present=bool(token),
#         token_length=len(token) if token else 0,
#     )

#     result = await _process_unsubscribe(
#         token,
#         tenant_slug,
#     )

#     html = f"""<!DOCTYPE html>
# <html lang="en">
# <head>
# <meta charset="UTF-8">
# <meta name="viewport" content="width=device-width, initial-scale=1.0">
# <title>Unsubscribed — OUTRENA</title>

# <style>
# body {{
#     font-family: system-ui, -apple-system, BlinkMacSystemFont,
#                  "Segoe UI", sans-serif;
#     display: flex;
#     align-items: center;
#     justify-content: center;
#     min-height: 100vh;
#     margin: 0;
#     background: #f8fafc;
# }}

# .card {{
#     background: #fff;
#     border-radius: 12px;
#     padding: 40px 48px;
#     max-width: 440px;
#     width: calc(100% - 40px);
#     text-align: center;
#     box-shadow: 0 4px 24px rgba(0, 0, 0, .08);
#     box-sizing: border-box;
# }}

# h1 {{
#     font-size: 1.4rem;
#     color: #0f172a;
#     margin: 16px 0 12px;
# }}

# p {{
#     color: #64748b;
#     line-height: 1.6;
#     margin: 0;
#     font-size: 14px;
# }}

# .success-icon {{
#     display: inline-block;
# }}
# </style>

# </head>

# <body>

# <div class="card">

# <div class="success-icon">
# <svg
#     width="48"
#     height="48"
#     viewBox="0 0 24 24"
#     fill="none"
#     stroke="#22c55e"
#     stroke-width="2"
#     stroke-linecap="round"
#     stroke-linejoin="round"
# >
#     <circle cx="12" cy="12" r="10"/>
#     <path d="m9 12 2 2 4-4"/>
# </svg>
# </div>

# <h1>You've been unsubscribed</h1>

# <p>
#     {result["message"]}
#     <br><br>
#     You will no longer receive outreach emails from this sender.
# </p>

# </div>

# </body>
# </html>
# """

#     logger.info(
#         "unsubscribe.get_response",
#         tenant_slug=tenant_slug,
#         unsubscribed=result.get("unsubscribed"),
#     )

#     return HTMLResponse(
#         content=html,
#         status_code=status.HTTP_200_OK,
#     )

"""
unsubscribe_router.py — Public one-click unsubscribe endpoint.

One-click unsubscribe without login, token-verified.

Endpoints:
    POST /public/unsubscribe
        JSON body:
        {
            "token": "...",
            "tenant_slug": "acme"
        }

    GET /public/unsubscribe
        Query params:
            ?token=...&tenant_slug=...

Important:
    Prospect updates use fully schema-qualified table names.

    ConsentLog insertion is performed inside a SAVEPOINT so that a
    ConsentLog failure does NOT abort/rollback the main Prospect update.
"""

from __future__ import annotations

from datetime import datetime, timezone

import structlog
from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from sqlalchemy import text

from app.core.database import AsyncSessionLocal

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/public", tags=["Public"])


class UnsubscribeRequest(BaseModel):
    token: str
    tenant_slug: str


def _schema_name(tenant_slug: str) -> str:
    """
    Convert tenant slug to PostgreSQL schema name.

    Example:
        acme -> tenant_acme
        my-company -> tenant_my_company
    """
    return f"tenant_{tenant_slug.replace('-', '_')}"


async def _process_unsubscribe(token: str, tenant_slug: str) -> dict:
    """
    Process an unsubscribe request.

    Flow:

        1. Validate request
        2. Resolve tenant schema
        3. Log database identity
        4. Find prospect
        5. Log current prospect state
        6. Check idempotency
        7. Update Prospect
        8. Verify UPDATE result
        9. Insert ConsentLog inside SAVEPOINT
        10. Commit Prospect transaction
        11. Verify persisted state after commit
        12. Return success
    """

    # ============================================================
    # 1. Validate input
    # ============================================================

    logger.info(
        "unsubscribe.request_received",
        tenant_slug=tenant_slug,
        token_present=bool(token),
        token_length=len(token) if token else 0,
    )

    if not token or not tenant_slug:
        logger.warning(
            "unsubscribe.invalid_request",
            tenant_slug=tenant_slug,
            token_present=bool(token),
        )

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="token and tenant_slug are required",
        )

    # ============================================================
    # 2. Resolve tenant schema
    # ============================================================

    schema = _schema_name(tenant_slug)

    logger.info(
        "unsubscribe.schema_resolved",
        tenant_slug=tenant_slug,
        schema=schema,
    )

    async with AsyncSessionLocal() as db:

        try:
            # ========================================================
            # 3. Database identity
            #
            # This is important to determine exactly which PostgreSQL
            # database/server the backend is connected to.
            # ========================================================

            logger.info(
                "unsubscribe.database_identity_check_start",
                tenant_slug=tenant_slug,
                schema=schema,
            )

            db_info_result = await db.execute(
                text(
                    """
                    SELECT
                        current_database() AS database,
                        current_user AS db_user,
                        current_schema() AS current_schema,
                        current_setting('search_path') AS search_path,
                        inet_server_addr() AS server_ip,
                        inet_server_port() AS server_port,
                        pg_backend_pid() AS backend_pid
                    """
                )
            )

            db_info = db_info_result.mappings().first()

            logger.info(
                "unsubscribe.database_identity",
                tenant_slug=tenant_slug,
                schema=schema,
                database=(
                    db_info["database"]
                    if db_info
                    else None
                ),
                db_user=(
                    db_info["db_user"]
                    if db_info
                    else None
                ),
                current_schema=(
                    db_info["current_schema"]
                    if db_info
                    else None
                ),
                search_path=(
                    db_info["search_path"]
                    if db_info
                    else None
                ),
                server_ip=(
                    str(db_info["server_ip"])
                    if db_info and db_info["server_ip"]
                    else None
                ),
                server_port=(
                    db_info["server_port"]
                    if db_info
                    else None
                ),
                backend_pid=(
                    db_info["backend_pid"]
                    if db_info
                    else None
                ),
            )

            # ========================================================
            # 4. Find prospect by unsubscribe token
            # ========================================================

            logger.info(
                "unsubscribe.prospect_lookup_start",
                tenant_slug=tenant_slug,
                schema=schema,
            )

            result = await db.execute(
                text(
                    f'''
                    SELECT
                        id,
                        "firstName",
                        "email",
                        suppressed,
                        consent_status,
                        "suppressedAt",
                        "updatedAt"
                    FROM "{schema}"."Prospect"
                    WHERE "unsubscribeToken" = :token
                    LIMIT 1
                    '''
                ),
                {
                    "token": token,
                },
            )

            row = result.mappings().first()

            # ========================================================
            # 5. Prospect not found
            # ========================================================

            if row is None:

                logger.warning(
                    "unsubscribe.token_not_found",
                    tenant_slug=tenant_slug,
                    schema=schema,
                )

                # Don't reveal whether token is valid.
                return {
                    "unsubscribed": True,
                    "message": "You have been unsubscribed.",
                }

            # ========================================================
            # 6. Extract prospect information
            # ========================================================

            prospect_id = row["id"]
            first_name = row.get("firstName") or "there"

            logger.info(
                "unsubscribe.prospect_found",
                tenant_slug=tenant_slug,
                schema=schema,
                prospect_id=prospect_id,
                first_name=first_name,
                email=row.get("email"),
                suppressed=row.get("suppressed"),
                consent_status=row.get("consent_status"),
                suppressed_at=row.get("suppressedAt"),
                updated_at=row.get("updatedAt"),
            )

            # ========================================================
            # 7. Log state BEFORE update
            # ========================================================

            logger.info(
                "unsubscribe.before_update_state",
                tenant_slug=tenant_slug,
                schema=schema,
                prospect_id=prospect_id,
                suppressed=row.get("suppressed"),
                consent_status=row.get("consent_status"),
                suppressed_at=row.get("suppressedAt"),
                updated_at=row.get("updatedAt"),
            )

            # ========================================================
            # 8. Idempotency
            # ========================================================

            if row.get("consent_status") == "withdrawn":

                logger.info(
                    "unsubscribe.already_withdrawn",
                    tenant_slug=tenant_slug,
                    schema=schema,
                    prospect_id=prospect_id,
                    suppressed=row.get("suppressed"),
                    consent_status=row.get("consent_status"),
                    suppressed_at=row.get("suppressedAt"),
                )

                return {
                    "unsubscribed": True,
                    "message": (
                        f"Hi {first_name}, "
                        "you were already unsubscribed."
                    ),
                }

            # ========================================================
            # 9. Prepare timestamp
            # ========================================================

            now = datetime.now(timezone.utc)

            logger.info(
                "unsubscribe.update_start",
                tenant_slug=tenant_slug,
                schema=schema,
                prospect_id=prospect_id,
                new_suppressed=True,
                new_consent_status="withdrawn",
                timestamp=now,
            )

            # ========================================================
            # 10. Update Prospect
            #
            # RETURNING gives us the actual row PostgreSQL changed.
            # ========================================================

            update_result = await db.execute(
                text(
                    f'''
                    UPDATE "{schema}"."Prospect"
                    SET
                        consent_status = :status,
                        suppressed = true,
                        "suppressedAt" = :now,
                        "updatedAt" = :now
                    WHERE id = :id
                    RETURNING
                        id,
                        "firstName",
                        "email",
                        suppressed,
                        consent_status,
                        "suppressedAt",
                        "updatedAt"
                    '''
                ),
                {
                    "status": "withdrawn",
                    "now": now,
                    "id": prospect_id,
                },
            )

            updated_row = update_result.mappings().first()

            rows_updated = (
                1
                if updated_row is not None
                else 0
            )

            # ========================================================
            # 11. Log UPDATE result
            # ========================================================

            logger.info(
                "unsubscribe.update_result",
                tenant_slug=tenant_slug,
                schema=schema,
                prospect_id=prospect_id,
                rows_updated=rows_updated,
                updated_row=(
                    dict(updated_row)
                    if updated_row
                    else None
                ),
            )

            # ========================================================
            # 12. Ensure UPDATE actually returned a row
            # ========================================================

            if updated_row is None:

                logger.error(
                    "unsubscribe.update_returned_no_row",
                    tenant_slug=tenant_slug,
                    schema=schema,
                    prospect_id=prospect_id,
                    rows_updated=rows_updated,
                )

                raise RuntimeError(
                    "Prospect UPDATE returned no row"
                )

            # ========================================================
            # 13. Log state AFTER UPDATE
            # ========================================================

            logger.info(
                "unsubscribe.after_update_state",
                tenant_slug=tenant_slug,
                schema=schema,
                prospect_id=prospect_id,
                suppressed=updated_row.get("suppressed"),
                consent_status=updated_row.get("consent_status"),
                suppressed_at=updated_row.get("suppressedAt"),
                updated_at=updated_row.get("updatedAt"),
            )

            # ========================================================
            # 14. Validate UPDATE result
            # ========================================================

            if updated_row.get("suppressed") is not True:

                logger.error(
                    "unsubscribe.update_suppressed_MISMATCH",
                    tenant_slug=tenant_slug,
                    schema=schema,
                    prospect_id=prospect_id,
                    expected=True,
                    actual=updated_row.get("suppressed"),
                )

                raise RuntimeError(
                    "Prospect UPDATE did not set suppressed=true"
                )

            if updated_row.get("consent_status") != "withdrawn":

                logger.error(
                    "unsubscribe.update_consent_MISMATCH",
                    tenant_slug=tenant_slug,
                    schema=schema,
                    prospect_id=prospect_id,
                    expected="withdrawn",
                    actual=updated_row.get("consent_status"),
                )

                raise RuntimeError(
                    "Prospect UPDATE did not set consent_status=withdrawn"
                )

            logger.info(
                "unsubscribe.update_values_verified",
                tenant_slug=tenant_slug,
                schema=schema,
                prospect_id=prospect_id,
                suppressed=updated_row.get("suppressed"),
                consent_status=updated_row.get("consent_status"),
            )

            # ========================================================
            # 15. Pre-commit verification
            # ========================================================

            logger.info(
                "unsubscribe.pre_commit_verification_start",
                tenant_slug=tenant_slug,
                schema=schema,
                prospect_id=prospect_id,
            )

            pre_commit_result = await db.execute(
                text(
                    f'''
                    SELECT
                        id,
                        "firstName",
                        "email",
                        suppressed,
                        consent_status,
                        "suppressedAt",
                        "updatedAt"
                    FROM "{schema}"."Prospect"
                    WHERE id = :id
                    '''
                ),
                {
                    "id": prospect_id,
                },
            )

            pre_commit_row = (
                pre_commit_result.mappings().first()
            )

            logger.info(
                "unsubscribe.pre_commit_verification",
                tenant_slug=tenant_slug,
                schema=schema,
                prospect_id=prospect_id,
                verified_row=(
                    dict(pre_commit_row)
                    if pre_commit_row
                    else None
                ),
            )

            if pre_commit_row is None:

                logger.error(
                    "unsubscribe.pre_commit_row_missing",
                    tenant_slug=tenant_slug,
                    schema=schema,
                    prospect_id=prospect_id,
                )

                raise RuntimeError(
                    "Prospect disappeared before commit"
                )

            if pre_commit_row["suppressed"] is not True:

                logger.error(
                    "unsubscribe.pre_commit_suppressed_MISMATCH",
                    tenant_slug=tenant_slug,
                    schema=schema,
                    prospect_id=prospect_id,
                    expected=True,
                    actual=pre_commit_row["suppressed"],
                )

                raise RuntimeError(
                    "suppressed value changed before commit"
                )

            if pre_commit_row["consent_status"] != "withdrawn":

                logger.error(
                    "unsubscribe.pre_commit_consent_MISMATCH",
                    tenant_slug=tenant_slug,
                    schema=schema,
                    prospect_id=prospect_id,
                    expected="withdrawn",
                    actual=pre_commit_row["consent_status"],
                )

                raise RuntimeError(
                    "consent_status changed before commit"
                )

            logger.info(
                "unsubscribe.pre_commit_values_verified",
                tenant_slug=tenant_slug,
                schema=schema,
                prospect_id=prospect_id,
                suppressed=pre_commit_row["suppressed"],
                consent_status=pre_commit_row["consent_status"],
            )

            # ========================================================
            # 16. ConsentLog
            #
            # IMPORTANT:
            #
            # This uses a SAVEPOINT.
            #
            # If ConsentLog INSERT fails:
            #
            #     SAVEPOINT
            #         ↓
            #     INSERT fails
            #         ↓
            #     ROLLBACK TO SAVEPOINT
            #         ↓
            #     Prospect UPDATE remains alive
            #         ↓
            #     COMMIT
            #
            # Without begin_nested(), a PostgreSQL error would put
            # the entire transaction into an aborted state.
            # ========================================================

            logger.info(
                "unsubscribe.consent_log_start",
                tenant_slug=tenant_slug,
                schema=schema,
                prospect_id=prospect_id,
            )

            consent_log_inserted = False

            try:

                async with db.begin_nested():

                    consent_result = await db.execute(
                        text(
                            f'''
                            INSERT INTO "{schema}"."ConsentLog"
                            (
                                id,
                                "prospectId",
                                action,
                                "performedBy",
                                timestamp
                            )
                            VALUES
                            (
                                gen_random_uuid()::text,
                                :pid,
                                'unsubscribed',
                                'one_click_link',
                                :now
                            )
                            '''
                        ),
                        {
                            "pid": prospect_id,
                            "now": now,
                        },
                    )

                    consent_log_inserted = True

                    logger.info(
                        "unsubscribe.consent_log_success",
                        tenant_slug=tenant_slug,
                        schema=schema,
                        prospect_id=prospect_id,
                        rows_inserted=consent_result.rowcount,
                    )

            except Exception as consent_error:

                logger.exception(
                    "unsubscribe.consent_log_failed",
                    tenant_slug=tenant_slug,
                    schema=schema,
                    prospect_id=prospect_id,
                    error_type=type(consent_error).__name__,
                    error=str(consent_error),
                )

                logger.warning(
                    "unsubscribe.consent_log_skipped_prospect_update_preserved",
                    tenant_slug=tenant_slug,
                    schema=schema,
                    prospect_id=prospect_id,
                )

                # DO NOT rollback the main transaction here.
                #
                # begin_nested() already rolled back the SAVEPOINT.
                #
                # The Prospect UPDATE remains in the main transaction.

            # ========================================================
            # 16b. EmailSuppression — email-level opt-out record
            #
            # WHY THIS EXISTS:
            #   Prospect.suppressed only marks the specific Prospect row
            #   whose token was in the clicked email. If the same email
            #   address exists in a second Prospect row (duplicate import,
            #   different campaign), or is imported again in the future,
            #   the suppression is silently bypassed.
            #
            #   EmailSuppression is the canonical, email-level block list
            #   for this tenant. Every send gate checks it by email address,
            #   independent of which Prospect row triggered the opt-out.
            #
            # PATTERN:
            #   Same SAVEPOINT pattern as ConsentLog above.
            #   If EmailSuppression INSERT fails (e.g. table not yet created),
            #   the Prospect UPDATE is NOT rolled back — it commits regardless.
            #
            # EMAIL VALUE:
            #   Read from the SELECT result captured earlier in step 4.
            #   Lowercased and trimmed for canonical matching. If the email
            #   is empty or None, this block is skipped silently.
            # ========================================================

            email_suppression_inserted = False
            _prospect_email = (row.get("email") or "").strip().lower()

            if _prospect_email:
                logger.info(
                    "unsubscribe.email_suppression_start",
                    tenant_slug=tenant_slug,
                    schema=schema,
                    prospect_id=prospect_id,
                    email=_prospect_email,
                )

                try:
                    async with db.begin_nested():
                        await db.execute(
                            text(
                                f'''
                                INSERT INTO "{schema}"."EmailSuppression"
                                (
                                    id,
                                    email,
                                    "suppressedAt",
                                    source,
                                    notes
                                )
                                VALUES
                                (
                                    replace(gen_random_uuid()::text, '-', ''),
                                    :email,
                                    :now,
                                    'unsubscribe_link',
                                    :notes
                                )
                                ON CONFLICT (email) DO NOTHING
                                '''
                            ),
                            {
                                "email": _prospect_email,
                                "now": now,
                                "notes": f"Unsubscribed via one-click link. ProspectId={prospect_id}",
                            },
                        )
                        email_suppression_inserted = True
                        logger.info(
                            "unsubscribe.email_suppression_success",
                            tenant_slug=tenant_slug,
                            schema=schema,
                            prospect_id=prospect_id,
                            email=_prospect_email,
                        )

                except Exception as _es_error:
                    logger.exception(
                        "unsubscribe.email_suppression_failed",
                        tenant_slug=tenant_slug,
                        schema=schema,
                        prospect_id=prospect_id,
                        email=_prospect_email,
                        error_type=type(_es_error).__name__,
                        error=str(_es_error),
                        hint="Run: alembic upgrade head (migration 0021 creates EmailSuppression)",
                    )
                    # SAVEPOINT already rolled back. Prospect UPDATE is preserved.
            else:
                logger.warning(
                    "unsubscribe.email_suppression_skipped_no_email",
                    tenant_slug=tenant_slug,
                    schema=schema,
                    prospect_id=prospect_id,
                )

            # ========================================================
            # 17. Verify Prospect again after ConsentLog attempt
            #
            # This confirms that a ConsentLog failure did not poison
            # the main transaction.
            # ========================================================

            logger.info(
                "unsubscribe.before_commit_final_check_start",
                tenant_slug=tenant_slug,
                schema=schema,
                prospect_id=prospect_id,
                consent_log_inserted=consent_log_inserted,
            )

            final_pre_commit_result = await db.execute(
                text(
                    f'''
                    SELECT
                        id,
                        suppressed,
                        consent_status,
                        "suppressedAt",
                        "updatedAt"
                    FROM "{schema}"."Prospect"
                    WHERE id = :id
                    '''
                ),
                {
                    "id": prospect_id,
                },
            )

            final_pre_commit_row = (
                final_pre_commit_result.mappings().first()
            )

            logger.info(
                "unsubscribe.before_commit_final_check",
                tenant_slug=tenant_slug,
                schema=schema,
                prospect_id=prospect_id,
                final_pre_commit_row=(
                    dict(final_pre_commit_row)
                    if final_pre_commit_row
                    else None
                ),
            )

            if final_pre_commit_row is None:

                logger.error(
                    "unsubscribe.before_commit_prospect_missing",
                    tenant_slug=tenant_slug,
                    schema=schema,
                    prospect_id=prospect_id,
                )

                raise RuntimeError(
                    "Prospect missing before final commit"
                )

            if final_pre_commit_row["suppressed"] is not True:

                logger.error(
                    "unsubscribe.before_commit_suppressed_MISMATCH",
                    tenant_slug=tenant_slug,
                    schema=schema,
                    prospect_id=prospect_id,
                    expected=True,
                    actual=final_pre_commit_row["suppressed"],
                )

                raise RuntimeError(
                    "Prospect suppressed value is incorrect before commit"
                )

            if final_pre_commit_row["consent_status"] != "withdrawn":

                logger.error(
                    "unsubscribe.before_commit_consent_MISMATCH",
                    tenant_slug=tenant_slug,
                    schema=schema,
                    prospect_id=prospect_id,
                    expected="withdrawn",
                    actual=final_pre_commit_row["consent_status"],
                )

                raise RuntimeError(
                    "Prospect consent status is incorrect before commit"
                )

            # ========================================================
            # 18. COMMIT
            # ========================================================

            logger.info(
                "unsubscribe.commit_start",
                tenant_slug=tenant_slug,
                schema=schema,
                prospect_id=prospect_id,
            )

            await db.commit()

            logger.info(
                "unsubscribe.commit_success",
                tenant_slug=tenant_slug,
                schema=schema,
                prospect_id=prospect_id,
            )

            # ========================================================
            # 19. POST-COMMIT VERIFICATION
            #
            # This is the most important diagnostic query.
            #
            # It runs AFTER COMMIT and reads the database again.
            # ========================================================

            logger.info(
                "unsubscribe.post_commit_verification_start",
                tenant_slug=tenant_slug,
                schema=schema,
                prospect_id=prospect_id,
            )

            post_commit_result = await db.execute(
                text(
                    f'''
                    SELECT
                        id,
                        "firstName",
                        "email",
                        suppressed,
                        consent_status,
                        "suppressedAt",
                        "updatedAt"
                    FROM "{schema}"."Prospect"
                    WHERE id = :id
                    '''
                ),
                {
                    "id": prospect_id,
                },
            )

            post_commit_row = (
                post_commit_result.mappings().first()
            )

            logger.info(
                "unsubscribe.post_commit_verification",
                tenant_slug=tenant_slug,
                schema=schema,
                prospect_id=prospect_id,
                verified_row=(
                    dict(post_commit_row)
                    if post_commit_row
                    else None
                ),
            )

            # ========================================================
            # 20. Verify persisted suppressed value
            # ========================================================

            if post_commit_row is None:

                logger.error(
                    "unsubscribe.post_commit_row_missing",
                    tenant_slug=tenant_slug,
                    schema=schema,
                    prospect_id=prospect_id,
                )

            else:

                persisted_suppressed = (
                    post_commit_row["suppressed"]
                )

                persisted_consent_status = (
                    post_commit_row["consent_status"]
                )

                if persisted_suppressed is True:

                    logger.info(
                        "unsubscribe.persisted_suppressed_verified",
                        tenant_slug=tenant_slug,
                        schema=schema,
                        prospect_id=prospect_id,
                        suppressed=persisted_suppressed,
                    )

                else:

                    logger.error(
                        "unsubscribe.persisted_suppressed_MISMATCH",
                        tenant_slug=tenant_slug,
                        schema=schema,
                        prospect_id=prospect_id,
                        expected=True,
                        actual=persisted_suppressed,
                    )

                # ====================================================
                # 21. Verify persisted consent status
                # ====================================================

                if persisted_consent_status == "withdrawn":

                    logger.info(
                        "unsubscribe.persisted_consent_verified",
                        tenant_slug=tenant_slug,
                        schema=schema,
                        prospect_id=prospect_id,
                        consent_status=persisted_consent_status,
                    )

                else:

                    logger.error(
                        "unsubscribe.persisted_consent_MISMATCH",
                        tenant_slug=tenant_slug,
                        schema=schema,
                        prospect_id=prospect_id,
                        expected="withdrawn",
                        actual=persisted_consent_status,
                    )

            # ========================================================
            # 22. Final state summary
            # ========================================================

            logger.info(
                "unsubscribe.final_state",
                tenant_slug=tenant_slug,
                schema=schema,
                prospect_id=prospect_id,
                rows_updated=rows_updated,
                consent_log_inserted=consent_log_inserted,
                final_suppressed=(
                    post_commit_row["suppressed"]
                    if post_commit_row
                    else None
                ),
                final_consent_status=(
                    post_commit_row["consent_status"]
                    if post_commit_row
                    else None
                ),
                final_suppressed_at=(
                    post_commit_row["suppressedAt"]
                    if post_commit_row
                    else None
                ),
                final_updated_at=(
                    post_commit_row["updatedAt"]
                    if post_commit_row
                    else None
                ),
            )

            # ========================================================
            # 23. Final success
            # ========================================================

            logger.info(
                "unsubscribe.success",
                tenant_slug=tenant_slug,
                schema=schema,
                prospect_id=prospect_id,
                rows_updated=rows_updated,
                consent_log_inserted=consent_log_inserted,
            )

            return {
                "unsubscribed": True,
                "message": (
                    f"Hi {first_name}, "
                    "you have been unsubscribed successfully."
                ),
            }

        except HTTPException:
            raise

        except Exception as exc:

            # ========================================================
            # 24. Unexpected failure
            # ========================================================

            logger.exception(
                "unsubscribe.failed",
                tenant_slug=tenant_slug,
                schema=schema,
                error_type=type(exc).__name__,
                error=str(exc),
            )

            # ========================================================
            # 25. Rollback
            # ========================================================

            try:

                await db.rollback()

                logger.info(
                    "unsubscribe.rollback_success",
                    tenant_slug=tenant_slug,
                    schema=schema,
                )

            except Exception as rollback_error:

                logger.exception(
                    "unsubscribe.rollback_failed",
                    tenant_slug=tenant_slug,
                    schema=schema,
                    error_type=type(rollback_error).__name__,
                    error=str(rollback_error),
                )

            raise


@router.post(
    "/unsubscribe",
    summary="One-click email unsubscribe (JSON)",
)
async def unsubscribe_post(
    body: UnsubscribeRequest,
) -> JSONResponse:
    """
    One-click unsubscribe via JSON POST.

    Sets:

        Prospect.consent_status = 'withdrawn'
        Prospect.suppressed = true

    Returns 200 regardless of whether the token was found.
    """

    logger.info(
        "unsubscribe.post_endpoint",
        tenant_slug=body.tenant_slug,
        token_present=bool(body.token),
    )

    result = await _process_unsubscribe(
        body.token,
        body.tenant_slug,
    )

    return JSONResponse(
        content=result,
        status_code=200,
    )


@router.get(
    "/unsubscribe",
    summary="One-click email unsubscribe (GET — email client support)",
)
async def unsubscribe_get(
    token: str = Query(
        ...,
        description="Prospect unsubscribe token",
    ),
    tenant_slug: str = Query(
        ...,
        description="Tenant slug",
    ),
) -> HTMLResponse:
    """
    One-click unsubscribe via GET.

    Email clients that implement RFC 8058 List-Unsubscribe-Post
    may send POST, while normal browser clicks typically use GET.
    """

    logger.info(
        "unsubscribe.get_endpoint",
        tenant_slug=tenant_slug,
        token_present=bool(token),
        token_length=len(token) if token else 0,
    )

    result = await _process_unsubscribe(
        token,
        tenant_slug,
    )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Unsubscribed — OUTRENA</title>

<style>
body {{
    font-family: system-ui, -apple-system, BlinkMacSystemFont,
                 "Segoe UI", sans-serif;
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 100vh;
    margin: 0;
    background: #f8fafc;
}}

.card {{
    background: #fff;
    border-radius: 12px;
    padding: 40px 48px;
    max-width: 440px;
    width: calc(100% - 40px);
    text-align: center;
    box-shadow: 0 4px 24px rgba(0, 0, 0, .08);
    box-sizing: border-box;
}}

h1 {{
    font-size: 1.4rem;
    color: #0f172a;
    margin: 16px 0 12px;
}}

p {{
    color: #64748b;
    line-height: 1.6;
    margin: 0;
    font-size: 14px;
}}

.success-icon {{
    display: inline-block;
}}
</style>

</head>

<body>

<div class="card">

<div class="success-icon">
<svg
    width="48"
    height="48"
    viewBox="0 0 24 24"
    fill="none"
    stroke="#22c55e"
    stroke-width="2"
    stroke-linecap="round"
    stroke-linejoin="round"
>
    <circle cx="12" cy="12" r="10"/>
    <path d="m9 12 2 2 4-4"/>
</svg>
</div>

<h1>You've been unsubscribed</h1>

<p>
    {result["message"]}
    <br><br>
    You will no longer receive outreach emails from this sender.
</p>

</div>

</body>
</html>
"""

    logger.info(
        "unsubscribe.get_response",
        tenant_slug=tenant_slug,
        unsubscribed=result.get("unsubscribed"),
    )

    return HTMLResponse(
        content=html,
        status_code=status.HTTP_200_OK,
    )

