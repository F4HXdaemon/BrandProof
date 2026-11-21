from fastapi import APIRouter
from app.api.v1 import (
    health,
    auth,
    users,
    organizations,
    facts,
    guidelines,
    terms,
    rules,
    knowledge,
    documents,
    reviews,
    claims,
    findings,
    approvals,
    audit,
    dashboard,
    insights,
    evaluation,
    evidence,
    demo,
)

api_router = APIRouter()

api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(organizations.router)
api_router.include_router(facts.router)
api_router.include_router(guidelines.router)
api_router.include_router(terms.router)
api_router.include_router(rules.router)
api_router.include_router(knowledge.router)
api_router.include_router(documents.router)
api_router.include_router(evidence.router)
api_router.include_router(reviews.router)
api_router.include_router(claims.router)
api_router.include_router(findings.router)
api_router.include_router(approvals.router)
api_router.include_router(audit.router)
api_router.include_router(dashboard.router)
api_router.include_router(insights.router)
api_router.include_router(evaluation.router)
api_router.include_router(demo.router)
