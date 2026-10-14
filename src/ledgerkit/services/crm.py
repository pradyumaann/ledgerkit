"""Leads and the opportunity pipeline."""

import datetime as dt

from sqlalchemy import select
from sqlalchemy.orm import Session

from ledgerkit.errors import DomainError
from ledgerkit.models import OPEN_STAGES, Lead, LeadStatus, Opportunity, OpportunityStage, Party
from ledgerkit.models.base import utcnow
from ledgerkit.money import Minor, pct

# Used when the caller does not give a probability.
DEFAULT_PROBABILITY = {
    OpportunityStage.PROSPECTING: 10,
    OpportunityStage.PROPOSAL: 40,
    OpportunityStage.NEGOTIATION: 70,
    OpportunityStage.WON: 100,
    OpportunityStage.LOST: 0,
}


def create_lead(session: Session, **fields) -> Lead:
    lead = Lead(status=LeadStatus.NEW, **fields)
    session.add(lead)
    session.flush()
    return lead


def create_opportunity(
    session: Session,
    *,
    title: str,
    expected_value: int,
    party: Party | None = None,
    lead: Lead | None = None,
    stage: str = OpportunityStage.PROSPECTING,
    probability_pct: int | None = None,
    expected_close: dt.date | None = None,
) -> Opportunity:
    if party is None and lead is None:
        raise DomainError("invalid_input", "An opportunity needs either a party_id (customer) or a lead_id.")
    if stage not in OPEN_STAGES:
        raise DomainError("invalid_input", "A new opportunity must start in an open stage, not won or lost.")
    opportunity = Opportunity(
        title=title,
        party_id=party.id if party else None,
        lead_id=lead.id if lead else None,
        stage=stage,
        expected_value=expected_value,
        probability_pct=DEFAULT_PROBABILITY[OpportunityStage(stage)] if probability_pct is None else probability_pct,
        expected_close=expected_close,
    )
    if lead is not None and lead.status == LeadStatus.NEW:
        lead.status = LeadStatus.QUALIFIED
    session.add(opportunity)
    session.flush()
    return opportunity


def update_opportunity_stage(
    session: Session,
    opportunity: Opportunity,
    *,
    stage: str,
    probability_pct: int | None = None,
    lost_reason: str | None = None,
) -> Opportunity:
    if opportunity.stage not in OPEN_STAGES:
        raise DomainError("invalid_status", f"Opportunity {opportunity.id} is already closed as {opportunity.stage}.")
    if stage == OpportunityStage.LOST and not lost_reason:
        raise DomainError("invalid_input", "Give a lost_reason when marking an opportunity as lost.")
    opportunity.stage = stage
    opportunity.probability_pct = (
        DEFAULT_PROBABILITY[OpportunityStage(stage)] if probability_pct is None else probability_pct
    )
    if stage in (OpportunityStage.WON, OpportunityStage.LOST):
        opportunity.probability_pct = DEFAULT_PROBABILITY[OpportunityStage(stage)]
        opportunity.closed_at = utcnow()
        opportunity.lost_reason = lost_reason if stage == OpportunityStage.LOST else None
        if opportunity.lead is not None and stage == OpportunityStage.WON:
            opportunity.lead.status = LeadStatus.CONVERTED
    session.flush()
    return opportunity


def pipeline_summary(session: Session) -> dict:
    opportunities = list(session.scalars(select(Opportunity).order_by(Opportunity.id)))
    stages = []
    for stage in OpportunityStage:
        in_stage = [o for o in opportunities if o.stage == stage]
        stages.append(
            {
                "stage": stage.value,
                "count": len(in_stage),
                "expected_value": Minor(sum(o.expected_value for o in in_stage)),
                "weighted_value": Minor(sum(o.expected_value * o.probability_pct // 100 for o in in_stage)),
            }
        )
    open_ = [o for o in opportunities if o.stage in OPEN_STAGES]
    won = sum(1 for o in opportunities if o.stage == OpportunityStage.WON)
    lost = sum(1 for o in opportunities if o.stage == OpportunityStage.LOST)
    return {
        "stages": stages,
        "open_count": len(open_),
        "open_expected_value": Minor(sum(o.expected_value for o in open_)),
        "open_weighted_value": Minor(sum(o.expected_value * o.probability_pct // 100 for o in open_)),
        "won_count": won,
        "lost_count": lost,
        "win_rate_pct": pct(won, won + lost),
        "open_opportunities": [
            {
                "id": o.id,
                "title": o.title,
                "customer": o.party.name if o.party else (o.lead.company_name or o.lead.name if o.lead else None),
                "stage": o.stage,
                "expected_value": Minor(o.expected_value),
                "probability_pct": o.probability_pct,
                "expected_close": o.expected_close,
            }
            for o in open_
        ],
    }
