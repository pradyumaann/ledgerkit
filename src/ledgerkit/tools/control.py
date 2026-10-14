"""Human approval of actions requested by an agent."""

from typing import Literal

from pydantic import Field
from sqlalchemy import select

from ledgerkit.errors import DomainError
from ledgerkit.models import ActionStatus, AuditLog, PendingAction
from ledgerkit.models.base import utcnow
from ledgerkit.tools import serializers
from ledgerkit.tools.context import ToolContext
from ledgerkit.tools.registry import ToolInput, registry


def _pending(ctx: ToolContext, action_id: int) -> PendingAction:
    if ctx.actor.type != "user":
        raise DomainError("forbidden", "Only a human user can approve or reject a pending action.")
    action = ctx.session.get(PendingAction, action_id)
    if action is None:
        raise DomainError("not_found", f"Pending action {action_id} was not found. Use list_pending_approvals.")
    if action.status != ActionStatus.PENDING:
        raise DomainError("invalid_status", f"Pending action {action_id} was already {action.status}.")
    return action


class ListPendingApprovals(ToolInput):
    status: ActionStatus = ActionStatus.PENDING
    limit: int = Field(50, ge=1, le=500)


@registry.tool(
    name="list_pending_approvals",
    description="List actions an agent has requested that need a human decision, oldest first, "
    "with the tool and the exact input each would run.",
    input_model=ListPendingApprovals,
)
def list_pending_approvals(ctx: ToolContext, p: ListPendingApprovals):
    found = ctx.session.scalars(
        select(PendingAction).where(PendingAction.status == p.status).order_by(PendingAction.id).limit(p.limit)
    )
    return {"actions": [serializers.pending_action(a) for a in found]}


class ApproveAction(ToolInput):
    action_id: int


@registry.tool(
    name="approve_action",
    description="Approve a pending action and run it now. Only a human user can do this. If the action "
    "fails, it stays pending and the error is returned.",
    input_model=ApproveAction,
    mutating=True,
)
def approve_action(ctx: ToolContext, p: ApproveAction):
    action = _pending(ctx, p.action_id)
    tool = ctx.registry.get(action.tool)
    if tool is None:
        raise DomainError("unknown_tool", f"The tool '{action.tool}' no longer exists. Reject this action.")
    result = tool.handler(ctx, tool.input_model.model_validate(action.input))
    action.status = ActionStatus.APPROVED
    action.decided_by = ctx.actor.label
    action.decided_at = utcnow()
    return {"action": serializers.pending_action(action), "result": result}


class RejectAction(ToolInput):
    action_id: int
    reason: str | None = Field(None, max_length=500)


@registry.tool(
    name="reject_action",
    description="Reject a pending action so that it never runs. Only a human user can do this.",
    input_model=RejectAction,
    mutating=True,
)
def reject_action(ctx: ToolContext, p: RejectAction):
    action = _pending(ctx, p.action_id)
    action.status = ActionStatus.REJECTED
    action.decided_by = ctx.actor.label
    action.decided_at = utcnow()
    action.reason = p.reason
    return serializers.pending_action(action)


class ListAuditLog(ToolInput):
    tool: str | None = Field(None, description="Only calls to this tool.")
    actor_type: Literal["user", "agent", "system"] | None = None
    status: Literal["ok", "error", "pending_approval"] | None = None
    limit: int = Field(100, ge=1, le=500)


@registry.tool(
    name="list_audit_log",
    description="List recorded calls that changed or tried to change data, newest first: who made the "
    "call, the tool, its input, and whether it succeeded, failed or was held for approval.",
    input_model=ListAuditLog,
)
def list_audit_log(ctx: ToolContext, p: ListAuditLog):
    stmt = select(AuditLog).order_by(AuditLog.id.desc()).limit(p.limit)
    if p.tool:
        stmt = stmt.where(AuditLog.tool == p.tool)
    if p.actor_type:
        stmt = stmt.where(AuditLog.actor_type == p.actor_type)
    if p.status:
        stmt = stmt.where(AuditLog.status == p.status)
    found = list(ctx.session.scalars(stmt))
    return {
        "entries": [
            {
                "id": row.id,
                "at": row.at,
                "actor": f"{row.actor_type}:{row.actor_id}",
                "tool": row.tool,
                "status": row.status,
                "input": row.input,
                "result": row.result,
            }
            for row in found
        ],
        "truncated": len(found) == p.limit,
    }
