"""Tool registry: each tool calls register_tool() in its router; the home page lists them."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import APIRouter, Depends, Request

from core.auth import CurrentUser, current_user


@dataclass(frozen=True)
class Tool:
    name: str
    path: str
    roles: tuple[str, ...]
    description: str


_TOOLS: dict[str, Tool] = {}


def register_tool(name: str, path: str, roles: tuple[str, ...] | list[str], description: str):
    tool = Tool(name, path, tuple(roles), description)
    _TOOLS[path] = tool
    return tool


def all_tools() -> list[Tool]:
    return sorted(_TOOLS.values(), key=lambda t: t.name)


def visible_tools(user: CurrentUser | None) -> list[Tool]:
    return [t for t in all_tools() if user and user.has_role(*t.roles)]


router = APIRouter()


@router.get("/")
def home(request: Request, user: CurrentUser = Depends(current_user)):
    from core.ui import page

    return page(request, "home.html", tools=all_tools())
