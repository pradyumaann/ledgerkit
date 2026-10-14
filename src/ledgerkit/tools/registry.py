"""The tool registry: the single entry point every interface (REST, CLI, and later the
Claude agent and MCP server) uses to read or change the books.

The registry, not the individual tools, enforces validation, the approval gate for
agents, one transaction per call, and the audit log.
"""

import datetime as dt
import json
from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from ledgerkit.errors import DomainError
from ledgerkit.models import AuditLog, PendingAction
from ledgerkit.money import Minor, from_minor
from ledgerkit.services.company import get_company
from ledgerkit.tools.context import Actor, ToolContext


class ToolInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    input_model: type[ToolInput]
    handler: Callable[[ToolContext, Any], Any]
    mutating: bool
    requires_approval: bool

    def schema(self) -> dict:
        """The shape the Claude API and MCP both use to describe a tool."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_model.model_json_schema(),
        }


def encode(value: Any, decimals: int) -> Any:
    """Make a handler's return value JSON-safe. Money becomes a decimal string."""
    if isinstance(value, Minor):
        return str(from_minor(value, decimals))
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dt.datetime):
        # Timestamps are stored in UTC; SQLite returns them without the offset.
        return (value if value.tzinfo else value.replace(tzinfo=dt.UTC)).isoformat()
    if isinstance(value, dt.date):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: encode(item, decimals) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [encode(item, decimals) for item in value]
    return value


def _error(code: str, message: str, details: Any = None) -> dict:
    error = {"code": code, "message": message}
    if details is not None:
        error["details"] = details
    return {"status": "error", "error": error}


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def tool(
        self,
        *,
        name: str,
        description: str,
        input_model: type[ToolInput],
        mutating: bool = False,
        requires_approval: bool = False,
    ):
        if requires_approval and not mutating:
            raise ValueError(f"Tool {name}: only mutating tools can require approval.")

        def decorator(handler):
            if name in self._tools:
                raise ValueError(f"Tool {name} is registered twice.")
            self._tools[name] = Tool(
                name, " ".join(description.split()), input_model, handler, mutating, requires_approval
            )
            return handler

        return decorator

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def list(self) -> list[Tool]:
        return sorted(self._tools.values(), key=lambda t: t.name)

    def call(self, session_factory: sessionmaker[Session], name: str, raw_input: dict | None, actor: Actor) -> dict:
        """Run a tool and return {"status": "ok" | "pending_approval" | "error", ...}.

        Business-rule failures come back as status "error"; they are not raised.
        """
        tool = self._tools.get(name)
        if tool is None:
            return _error("unknown_tool", f"There is no tool named '{name}'.", {"available": sorted(self._tools)})
        try:
            params = tool.input_model.model_validate(raw_input or {})
        except ValidationError as exc:
            details = json.loads(exc.json(include_url=False, include_input=False))
            summary = "; ".join(f"{'.'.join(str(p) for p in d['loc']) or 'input'}: {d['msg']}" for d in details)
            return _error("invalid_input", f"Invalid input for {name}: {summary}", details)
        audit_input = params.model_dump(mode="json", exclude_none=True)

        session = session_factory()
        try:
            company = get_company(session)
            if tool.requires_approval and actor.type == "agent":
                action = PendingAction(tool=name, input=audit_input, requested_by=actor.label)
                session.add(action)
                session.flush()
                data = {
                    "pending_action_id": action.id,
                    "message": f"{name} was NOT executed. It is waiting for a human to approve it "
                    f"(pending action {action.id}). Tell the user what you requested and why.",
                }
                self._audit(session, actor, name, "pending_approval", audit_input, data)
                session.commit()
                return {"status": "pending_approval", "data": data}

            ctx = ToolContext(session=session, actor=actor, company=company, registry=self)
            data = encode(tool.handler(ctx, params), company.currency_decimals)
            if tool.mutating:
                self._audit(session, actor, name, "ok", audit_input, data)
                session.commit()
            return {"status": "ok", "data": data}
        except (DomainError, IntegrityError) as exc:
            session.rollback()
            if isinstance(exc, DomainError):
                result = _error(exc.code, exc.message, exc.details)
            else:
                result = _error("conflict", f"The database rejected this change: {exc.orig}")
            if tool.mutating:
                self._audit(session, actor, name, "error", audit_input, result["error"])
                session.commit()
            return result
        finally:
            session.close()

    @staticmethod
    def _audit(session: Session, actor: Actor, tool: str, status: str, input_: dict, result: Any) -> None:
        session.add(
            AuditLog(actor_type=actor.type, actor_id=actor.id, tool=tool, status=status, input=input_, result=result)
        )


registry = ToolRegistry()
