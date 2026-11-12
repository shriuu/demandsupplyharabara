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
    DayView,
    DcOrders,
    DcTotals,
    FarmerDay,
    HealthResponse,
    HistorySeries,
    KillSwitchRequest,
    KillSwitchResponse,
    LoginRequest,
    LoginResponse,
    OrgArea,
    OrgChart,
    OrgStore,
    OutcomeInput,
    WeekHistory,
)
from harabhara.api.service import ApiError, Horizons, Service
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
from harabhara.settings.areas import load_areas
from harabhara.settings.contacts import StoreContact, load_contacts
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
    areas = load_areas()
    store_contacts = load_contacts()
    for pin_user in settings.pins.values():
        if pin_user.area_id and pin_user.area_id not in areas:
            msg = f"{pin_user.actor_id} has an unknown area {pin_user.area_id!r}"
            raise ValueError(msg)
    service = Service(
        storage,
        prices or ports.NotConfiguredPrices(),
        assistant or ports.NotConfiguredAssistant(),
        clock,
        (config or load_config()).modeling.pipeline.scorecard_days,
        store_contacts,
        (config or load_config()).feeds.mandi.buying_markets,
        areas,
        Horizons(
            (config or load_config()).rules.farmers.share_forecast_horizon_days,
            (config or load_config()).modeling.pipeline.history_days_back,
            (config or load_config()).modeling.pipeline.chart_week_days,
            (config or load_config()).modeling.pipeline.chart_month_days,
        ),
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
        area = areas.get(user.area_id) if user.area_id else None
        return LoginResponse(
            token=token,
            role=user.role,
            actor_id=user.actor_id,
            store_id=user.store_id,
            area_id=user.area_id,
            area_name=area.name if area else None,
        )

    @router.get("/auth/org")
    def org_chart() -> OrgChart:
        """Which stores report to which area manager, for the sign-in page. Carries no secrets."""
        places = {
            c.store_id: (c.name or "").removeprefix("Manager, ") or None for c in store_contacts
        }
        return OrgChart(
            areas=[
                OrgArea(
                    area_id=k,
                    name=a.name,
                    stores=[OrgStore(store_id=s, place=places.get(s)) for s in a.stores],
                )
                for k, a in areas.items()
            ]
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

    @router.get("/dc/orders")
    def dc_orders(user: CurrentUser) -> DcOrders:
        return service.dc_orders(user)

    @router.get("/history/day")
    def history_day(user: CurrentUser, on: Annotated[date, Query(alias="date")]) -> DayView:
        return service.day_view(user, on)

    @router.get("/history/series")
    def history_series(
        user: CurrentUser,
        period: Literal["week", "month"] = "week",
        store_id: str | None = None,
    ) -> HistorySeries:
        return service.history_series(user, period, store_id)

    @router.get("/farmers/day")
    def farmer_day(user: CurrentUser, on: Annotated[date, Query(alias="date")]) -> FarmerDay:
        return service.farmer_day(user, on)

    @router.get("/history/week")
    def week_history(user: CurrentUser) -> WeekHistory:
        return service.week_history(user)

    @router.get("/contacts")
    def contacts(user: CurrentUser) -> list[StoreContact]:
        return service.contacts(user)

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


_STATIC_CACHE = {True: "public, max-age=31536000, immutable", False: "no-cache"}


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
            # build output under assets/ carries a content hash in its name, so it never changes
            kept = path.startswith("assets/")
            return FileResponse(candidate, headers={"Cache-Control": _STATIC_CACHE[kept]})
        # the page itself must be re-checked every time, or a phone keeps the old version
        return FileResponse(root / "index.html", headers={"Cache-Control": _STATIC_CACHE[False]})
