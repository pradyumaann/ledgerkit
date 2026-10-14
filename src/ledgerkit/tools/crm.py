"""Leads and the sales pipeline."""

import datetime as dt
from decimal import Decimal
from typing import Literal

from pydantic import Field
from sqlalchemy import select

from ledgerkit.models import OPEN_STAGES, Lead, LeadStatus, Opportunity, OpportunityStage
from ledgerkit.services import crm, lookup
from ledgerkit.tools import serializers
from ledgerkit.tools.accounting import Empty
from ledgerkit.tools.context import ToolContext
from ledgerkit.tools.registry import ToolInput, registry


class CreateLead(ToolInput):
    name: str = Field(min_length=1, max_length=200, description="The person's name.")
    company_name: str | None = None
    email: str | None = None
    phone: str | None = None
    source: str | None = Field(None, description="Where the lead came from, e.g. 'website', 'referral', 'trade show'.")
    notes: str | None = None


@registry.tool(
    name="create_lead",
    description="Record a new sales lead: someone who has shown interest but is not yet a customer.",
    input_model=CreateLead,
    mutating=True,
)
def create_lead(ctx: ToolContext, p: CreateLead):
    return serializers.lead(crm.create_lead(ctx.session, **p.model_dump()))


class ListLeads(ToolInput):
    status: LeadStatus | None = None
    limit: int = Field(50, ge=1, le=500)


@registry.tool(
    name="list_leads",
    description="List sales leads, newest first.",
    input_model=ListLeads,
)
def list_leads(ctx: ToolContext, p: ListLeads):
    stmt = select(Lead).order_by(Lead.id.desc()).limit(p.limit)
    if p.status:
        stmt = stmt.where(Lead.status == p.status)
    found = list(ctx.session.scalars(stmt))
    return {"leads": [serializers.lead(x) for x in found], "truncated": len(found) == p.limit}


class CreateOpportunity(ToolInput):
    title: str = Field(min_length=1, max_length=200, description="Short name for the deal.")
    expected_value: Decimal = Field(ge=0, description="Expected revenue if the deal is won, before tax.")
    party_id: int | None = Field(None, description="Existing customer the deal is with.")
    lead_id: int | None = Field(None, description="Lead the deal came from, if not yet a customer.")
    stage: Literal["prospecting", "proposal", "negotiation"] = "prospecting"
    probability_pct: int | None = Field(
        None, ge=0, le=100, description="Chance of winning. Defaults by stage: 10, 40 or 70."
    )
    expected_close: dt.date | None = None


@registry.tool(
    name="create_opportunity",
    description="Open a sales opportunity (a potential deal) for a customer or a lead. "
    "Give either party_id or lead_id.",
    input_model=CreateOpportunity,
    mutating=True,
)
def create_opportunity(ctx: ToolContext, p: CreateOpportunity):
    opportunity = crm.create_opportunity(
        ctx.session,
        title=p.title,
        expected_value=ctx.minor(p.expected_value),
        party=lookup.party(ctx.session, p.party_id) if p.party_id is not None else None,
        lead=lookup.lead(ctx.session, p.lead_id) if p.lead_id is not None else None,
        stage=p.stage,
        probability_pct=p.probability_pct,
        expected_close=p.expected_close,
    )
    return serializers.opportunity(opportunity)


class UpdateOpportunityStage(ToolInput):
    opportunity_id: int
    stage: OpportunityStage
    probability_pct: int | None = Field(None, ge=0, le=100, description="Defaults to the usual value for the stage.")
    lost_reason: str | None = Field(None, description="Required when the stage is 'lost'.")


@registry.tool(
    name="update_opportunity_stage",
    description="Move an opportunity to another pipeline stage, or close it as won or lost. "
    "A closed opportunity cannot be reopened.",
    input_model=UpdateOpportunityStage,
    mutating=True,
)
def update_opportunity_stage(ctx: ToolContext, p: UpdateOpportunityStage):
    opportunity = crm.update_opportunity_stage(
        ctx.session,
        lookup.opportunity(ctx.session, p.opportunity_id),
        stage=p.stage,
        probability_pct=p.probability_pct,
        lost_reason=p.lost_reason,
    )
    return serializers.opportunity(opportunity)


@registry.tool(
    name="pipeline_summary",
    description="Summarise the sales pipeline: count, expected value and probability-weighted value per "
    "stage, the win rate of closed opportunities, and the list of open opportunities.",
    input_model=Empty,
)
def pipeline_summary(ctx: ToolContext, p: Empty):
    return crm.pipeline_summary(ctx.session)


class ListOpportunities(ToolInput):
    stage: OpportunityStage | None = None
    open_only: bool = Field(False, description="Leave out opportunities already won or lost.")
    limit: int = Field(200, ge=1, le=500)


@registry.tool(
    name="list_opportunities",
    description="List sales opportunities, newest first, including closed ones unless open_only is set.",
    input_model=ListOpportunities,
)
def list_opportunities(ctx: ToolContext, p: ListOpportunities):
    stmt = select(Opportunity).order_by(Opportunity.id.desc()).limit(p.limit)
    if p.stage:
        stmt = stmt.where(Opportunity.stage == p.stage)
    if p.open_only:
        stmt = stmt.where(Opportunity.stage.in_(OPEN_STAGES))
    found = list(ctx.session.scalars(stmt))
    return {"opportunities": [serializers.opportunity(o) for o in found], "truncated": len(found) == p.limit}
