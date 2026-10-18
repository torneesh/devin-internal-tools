"""Platform exceptions, each mapped to a friendly HTML page with the right HTTP status."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from markupsafe import escape
from sqlalchemy.orm.exc import StaleDataError


class AppError(Exception):
    status_code = 400
    title = "Something went wrong"

    def __init__(self, message: str | None = None):
        self.message = message or self.title
        super().__init__(self.message)


class NotAuthenticated(AppError):
    status_code = 401
    title = "Please sign in"


class PermissionDenied(AppError):
    status_code = 403
    title = "Not allowed"


class NotFound(AppError):
    status_code = 404
    title = "Not found"


class StaleWrite(AppError):
    status_code = 409
    title = "This record was changed by someone else. Reload the page and try again."


class InvalidTransition(AppError):
    status_code = 409
    title = "That action isn't allowed in the record's current state"


class RuleViolation(AppError):
    status_code = 422
    title = "Business rule violated"


class ValidationError(AppError):
    status_code = 422
    title = "Invalid input"


def _render(request: Request, exc: AppError) -> HTMLResponse:
    if request.headers.get("HX-Request"):
        return HTMLResponse(
            f'<span class="error">{escape(exc.message)}</span>', status_code=exc.status_code
        )
    from core.ui import page

    return page(request, "error.html", status_code=exc.status_code, error=exc)


def install(app: FastAPI) -> None:
    @app.exception_handler(NotAuthenticated)
    async def _not_authenticated(request: Request, exc: NotAuthenticated):
        if request.headers.get("HX-Request"):
            return HTMLResponse("", status_code=401, headers={"HX-Redirect": "/login"})
        return RedirectResponse("/login", status_code=303)

    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError):
        return _render(request, exc)

    @app.exception_handler(StaleDataError)
    async def _stale(request: Request, exc: StaleDataError):
        return _render(request, StaleWrite())
