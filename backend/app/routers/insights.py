from fastapi import APIRouter

from .. import analytics

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("")
def full():
    return analytics.full_report()


@router.get("/summary")
def summary():
    return analytics.summary()


@router.get("/worn")
def worn(limit: int = 10):
    return {"most_worn": analytics.most_worn(limit), "least_worn": analytics.least_worn(limit)}


@router.get("/neglected")
def neglected(days: int = 90, limit: int = 20):
    return {"days": days, "items": analytics.neglected(days, limit)}


@router.get("/colours")
def colours():
    return {"colours": analytics.colour_distribution()}


@router.get("/combinations")
def combinations(limit: int = 10):
    return {"combinations": analytics.top_combinations(limit)}


@router.get("/value")
def value(limit: int = 10):
    return {"best": analytics.cost_per_wear(limit, best=True),
            "worst": analytics.cost_per_wear(limit, best=False)}


@router.get("/wash")
def wash_stats():
    return analytics.wash_stats()


@router.get("/timeline")
def timeline(weeks: int = 12):
    return {"timeline": analytics.wear_timeline(weeks)}


@router.get("/gaps")
def gaps():
    return {"gaps": analytics.gaps()}
