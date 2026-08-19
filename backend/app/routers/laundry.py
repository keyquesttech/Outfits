from fastapi import APIRouter, HTTPException

from .. import db, wash
from ..models import WashIn
from ..serializers import load_items

router = APIRouter(prefix="/api/laundry", tags=["laundry"])


@router.get("/plan")
def plan():
    """Everything dirty, grouped into loads you can actually run."""
    result = wash.laundry_plan()
    result["due_soon"] = wash.due_soon(within=1)
    return result


@router.post("/wash", status_code=201)
def do_wash(payload: WashIn):
    if not payload.item_ids:
        raise HTTPException(400, "Select at least one item")
    batch_id = wash.mark_washed(
        payload.item_ids, payload.washed_on, payload.program, payload.temp_c, payload.notes
    )
    return {
        "batch_id": batch_id,
        "washed": load_items(payload.item_ids),
        "count": len(payload.item_ids),
    }


@router.get("/history")
def history(limit: int = 40):
    batches = db.query("SELECT * FROM wash_batches ORDER BY washed_on DESC, id DESC LIMIT ?",
                       (limit,))
    for batch in batches:
        ids = [r["item_id"] for r in db.query(
            "SELECT item_id FROM wash_batch_items WHERE batch_id = ?", (batch["id"],)
        )]
        batch["items"] = load_items(ids)
        batch["count"] = len(ids)
    return {"batches": batches}


@router.delete("/history/{batch_id}")
def delete_batch(batch_id: int):
    if not db.query_one("SELECT id FROM wash_batches WHERE id = ?", (batch_id,)):
        raise HTTPException(404, "Wash load not found")
    db.execute("DELETE FROM wash_batches WHERE id = ?", (batch_id,))
    return {"deleted": batch_id}
