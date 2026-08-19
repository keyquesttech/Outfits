from fastapi import APIRouter, HTTPException

from .. import db
from ..constants import CATEGORY_LAYERS
from ..models import OutfitIn
from ..serializers import load_items, outfit_out

router = APIRouter(prefix="/api/outfits", tags=["outfits"])


def _items_for(outfit_id: int) -> list[dict]:
    ids = [r["item_id"] for r in db.query(
        "SELECT item_id FROM outfit_items WHERE outfit_id = ?", (outfit_id,)
    )]
    return load_items(ids)


def _hydrate(row: dict) -> dict:
    return outfit_out(row, _items_for(row["id"]))


@router.get("")
def list_outfits(occasion: str | None = None, favourite: bool | None = None,
                 q: str | None = None):
    sql, params, where = "SELECT * FROM outfits", [], []
    if occasion:
        where.append("occasion = ?")
        params.append(occasion)
    if favourite is not None:
        where.append("is_favourite = ?")
        params.append(int(favourite))
    if q:
        where.append("(name LIKE ? OR notes LIKE ?)")
        params += [f"%{q}%"] * 2
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY is_favourite DESC, id DESC"
    return {"outfits": [_hydrate(r) for r in db.query(sql, tuple(params))]}


@router.get("/{outfit_id}")
def get_outfit(outfit_id: int):
    row = db.query_one("SELECT * FROM outfits WHERE id = ?", (outfit_id,))
    if not row:
        raise HTTPException(404, "Outfit not found")
    return _hydrate(row)


def _write_items(outfit_id: int, item_ids: list[int]) -> None:
    db.execute("DELETE FROM outfit_items WHERE outfit_id = ?", (outfit_id,))
    rows = db.query(
        f"SELECT id, category FROM items WHERE id IN ({','.join('?' * len(item_ids))})",
        tuple(item_ids),
    ) if item_ids else []
    db.executemany(
        "INSERT OR IGNORE INTO outfit_items(outfit_id, item_id, layer) VALUES (?,?,?)",
        [(outfit_id, r["id"], CATEGORY_LAYERS.get(r["category"], "accessory")) for r in rows],
    )


@router.post("", status_code=201)
def create_outfit(payload: OutfitIn):
    outfit_id = db.execute(
        "INSERT INTO outfits(name, occasion, notes, is_favourite) VALUES (?,?,?,?)",
        (payload.name, payload.occasion, payload.notes, int(payload.is_favourite)),
    )
    _write_items(outfit_id, payload.item_ids)
    return _hydrate(db.query_one("SELECT * FROM outfits WHERE id = ?", (outfit_id,)))


@router.put("/{outfit_id}")
def update_outfit(outfit_id: int, payload: OutfitIn):
    if not db.query_one("SELECT id FROM outfits WHERE id = ?", (outfit_id,)):
        raise HTTPException(404, "Outfit not found")
    db.execute(
        "UPDATE outfits SET name = ?, occasion = ?, notes = ?, is_favourite = ? WHERE id = ?",
        (payload.name, payload.occasion, payload.notes, int(payload.is_favourite), outfit_id),
    )
    _write_items(outfit_id, payload.item_ids)
    return _hydrate(db.query_one("SELECT * FROM outfits WHERE id = ?", (outfit_id,)))


@router.post("/{outfit_id}/favourite")
def toggle_favourite(outfit_id: int):
    row = db.query_one("SELECT * FROM outfits WHERE id = ?", (outfit_id,))
    if not row:
        raise HTTPException(404, "Outfit not found")
    db.execute("UPDATE outfits SET is_favourite = ? WHERE id = ?",
               (0 if row["is_favourite"] else 1, outfit_id))
    return _hydrate(db.query_one("SELECT * FROM outfits WHERE id = ?", (outfit_id,)))


@router.delete("/{outfit_id}")
def delete_outfit(outfit_id: int):
    if not db.query_one("SELECT id FROM outfits WHERE id = ?", (outfit_id,)):
        raise HTTPException(404, "Outfit not found")
    db.execute("DELETE FROM outfits WHERE id = ?", (outfit_id,))
    return {"deleted": outfit_id}
