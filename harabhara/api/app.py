"""The FastAPI app: the API under /api/v1 plus the built web app."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime
from pathlib import Path
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse, JSONResponse

from harabhara.api import ports
from harabhara.api.auth import (
    Authenticator,
    AuthError,
    SignInUnavailableError,
    TooManyAttemptsError,
)
from harabhara.api.schemas import (
    AskRequest,
    AskResponse,
    DcTotals,
    HealthResponse,
    KillSwitchRequest,
    KillSwitchResponse,
    LoginRequest,
    LoginResponse,
    OutcomeInput,
)
from harabhara.api.service import ApiError, Service
from harabhara.api.settings import ApiSettings, User
from harabhara.api.storage import Storage
from harabhara.contracts import (
    Approval,
    AuditEvent,
    FarmerVolumeForecast,
    Forecast,
    OutcomeRecord,
    PriceQuote,
    Projection,
    Role,
    Scorecard,
    Suggestion,
    SuggestionState,
)
from harabhara.settings import AppConfig, load_config
from harabhara.workflow.approvals import assert_manual_only
from harabhara.workflow.fallback import STALE_HEADER, Served

API = "/api/v1"


def _mark[T](served: Served[T], response: Response) -> list[T]:
    response.headers[STALE_HEADER] = "true" if served.stale else "false"
    return served.items


def current_user(request: Request, authorization: Annotated[str | None, Header()] = None) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "sign in first")
    try:
        user: User = request.app.state.auth.verify(authorization.removeprefix("Bearer "))
    except SignInUnavailableError as exc:
        raise HTTPException(503, "sign-in is not configured") from exc
    except AuthError as exc:
        raise HTTPException(401, "sign in again") from exc
    return user


CurrentUser = Annotated[User, Depends(current_user)]


def create_app(
    storage: Storage,
    settings: ApiSettings,
    prices: ports.PricePort | None = None,
    assistant: ports.AssistantPort | None = None,
    clock: Callable[[], datetime] | None = None,
    config: AppConfig | None = None,
    token_clock: Callable[[], float] | None = None,
) -> FastAPI:
    assert_manual_only(config or load_config())  # guardrail 1: refuse to start otherwise
    service = Service(
        storage,
        prices or ports.NotConfiguredPrices(),
        assistant or ports.NotConfiguredAssistant(),
        clock,
        (config or load_config()).modeling.pipeline.scorecard_days,
    )
    auth = Authenticator(settings, token_clock) if token_clock else Authenticator(settings)
    app = FastAPI(title="HaraBhara Fresh", docs_url=None, redoc_url=None, openapi_url=None)
    app.state.service = service
    app.state.auth = auth

    @app.exception_handler(ApiError)
    async def _api_error(_: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse({"detail": exc.detail}, status_code=exc.status)

    router = APIRouter(prefix=API)

    @router.get("/health")
    def health() -> HealthResponse:
        return service.health()

    @router.post("/auth/login")
    def login(body: LoginRequest, request: Request) -> LoginResponse:
        forwarded = request.headers.get("x-forwarded-for")
        client = (
            forwarded.split(",")[-1].strip()
            if forwarded
            else (request.client.host if request.client else "unknown")
        )
        try:
            token, user = auth.login(body.pin, client)
        except SignInUnavailableError as exc:
            raise HTTPException(503, "sign-in is not configured") from exc
        except TooManyAttemptsError as exc:
            raise HTTPException(429, "too many attempts; wait and try again") from exc
        except AuthError as exc:
            raise HTTPException(401, "wrong PIN") from exc
        return LoginResponse(
            token=token, role=user.role, actor_id=user.actor_id, store_id=user.store_id
        )

    @router.post("/admin/kill-switch")
    def kill_switch(body: KillSwitchRequest, user: CurrentUser) -> KillSwitchResponse:
        return service.set_kill_switch(user, body.on)

    @router.get("/forecasts")
    def forecasts(
        user: CurrentUser,
        response: Response,
        store_id: str | None = None,
        sku_id: str | None = None,
        on: Annotated[date | None, Query(alias="date")] = None,
    ) -> list[Forecast]:
        return _mark(service.forecasts(user, store_id, sku_id, on), response)

    @router.get("/suggestions")
    def suggestions(
        user: CurrentUser,
        response: Response,
        role: Role | None = None,
        store_id: str | None = None,
        kind: str | None = None,
        state: SuggestionState | None = None,
    ) -> list[Suggestion]:
        return _mark(service.list_suggestions(user, role, store_id, kind, state), response)

    @router.get("/suggestions/{suggestion_id}")
    def suggestion(suggestion_id: str, user: CurrentUser) -> Suggestion:
        return service.get_suggestion(user, suggestion_id)

    @router.post("/suggestions/{suggestion_id}/decision")
    def decision(suggestion_id: str, body: Approval, user: CurrentUser) -> Suggestion:
        if body.suggestion_id != suggestion_id:
            raise HTTPException(422, "suggestion_id in the body does not match the path")
        return service.decide(user, suggestion_id, body)

    @router.get("/projections")
    def projections(
        user: CurrentUser,
        response: Response,
        store_id: str | None = None,
        sku_id: str | None = None,
    ) -> list[Projection]:
        return _mark(service.projections(user, store_id, sku_id), response)

    @router.get("/dc/totals")
    def dc_totals(
        user: CurrentUser, on: Annotated[date | None, Query(alias="date")] = None
    ) -> DcTotals:
        return service.dc_totals(user, on)

    @router.get("/prices")
    def prices_route(
        user: CurrentUser, response: Response, sku_id: str | None = None
    ) -> list[PriceQuote]:
        return _mark(service.get_prices(user, sku_id), response)

    @router.get("/farmers/forecast")
    def farmers(
        user: CurrentUser, response: Response, fpo_id: str | None = None
    ) -> list[FarmerVolumeForecast]:
        return _mark(service.farmer_forecast(user, fpo_id), response)

    @router.get("/scorecard")
    def scorecard(
        user: CurrentUser, response: Response, scope: str | None = None
    ) -> list[Scorecard]:
        return _mark(service.scorecard(user, scope), response)

    @router.get("/scorecard/recorded")
    def recorded_scorecard(user: CurrentUser, response: Response) -> list[Scorecard]:
        return _mark(service.recorded_scorecard(user), response)

    @router.post("/outcomes")
    def record_outcome(body: OutcomeInput, user: CurrentUser) -> OutcomeRecord:
        return service.record_outcome(user, body)

    @router.get("/outcomes")
    def outcomes(
        user: CurrentUser,
        response: Response,
        kind: Literal["closing", "purchase"] | None = None,
        store_id: str | None = None,
        on: Annotated[date | None, Query(alias="date")] = None,
    ) -> list[OutcomeRecord]:
        return _mark(service.list_outcomes(user, kind, store_id, on), response)

    @router.post("/assistant/ask")
    def ask(body: AskRequest, user: CurrentUser) -> AskResponse:
        return service.ask(user, body.suggestion_id, body.question)

    @router.get("/audit")
    def audit_log(
        user: CurrentUser, response: Response, suggestion_id: str | None = None
    ) -> list[AuditEvent]:
        return _mark(service.audit_log(user, suggestion_id), response)

    app.include_router(router)
    _serve_static(app, settings.static_dir)
    return app


def _serve_static(app: FastAPI, static_dir: Path | None) -> None:
    """Serve the built web app; unknown paths fall back to index.html for client routing."""
    if static_dir is None or not (static_dir / "index.html").is_file():
        return
    root = static_dir.resolve()

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str) -> FileResponse:
        if path.startswith("api/"):
            raise HTTPException(404, "not found")
        candidate = (root / path).resolve()
        if path and candidate.is_file() and root in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(root / "index.html")
