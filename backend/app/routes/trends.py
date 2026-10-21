import logging
from fastapi import APIRouter, Depends, HTTPException, Query

from app.db import pool
from app.deps import require_role

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/trends",
    tags=["trends"],
    dependencies=[Depends(require_role("supervisor", "admin"))],
)

GROUP_COLUMNS = {"product": "product", "issue": "issue", "company": "company"}


@router.get("/spikes")
def spikes(
    group_by: str = Query("product", pattern="^(product|issue|company)$"),
    window_days: int = Query(7, ge=1, le=31),
    baseline_windows: int = Query(4, ge=1, le=12),
    threshold: float = Query(1.5, ge=1.0, le=10.0),
    min_count: int = Query(30, ge=1, le=100000),
):
    column = GROUP_COLUMNS[group_by]

    sql = f"""
        WITH bounds AS (
            SELECT MAX(date_received) AS max_date, MIN(date_received) AS min_date
            FROM complaints
        ),
        counted AS (
            SELECT c.{column} AS grp,
                   ((b.max_date - c.date_received) / %s::int) AS bucket,
                   COUNT(*) AS n
            FROM complaints c
            CROSS JOIN bounds b
            WHERE c.date_received > b.max_date - (%s::int * (%s::int + 1))
            GROUP BY 1, 2
        )
        SELECT grp, bucket, n,
               (SELECT max_date FROM bounds) AS max_date,
               (SELECT min_date FROM bounds) AS min_date
        FROM counted
    """

    try:
        with pool.connection() as conn:
            rows = conn.execute(
                sql, [window_days, window_days, baseline_windows]
            ).fetchall()
    except Exception:
        logger.exception("Database error while calculating spikes")
        raise HTTPException(status_code=503, detail="Database is not available. Please try again.")

    if not rows:
        return {
            "as_of": None,
            "group_by": group_by,
            "window_days": window_days,
            "baseline_windows": baseline_windows,
            "threshold": threshold,
            "min_count": min_count,
            "enough_history": False,
            "items": [],
        }

    max_date = rows[0]["max_date"]
    min_date = rows[0]["min_date"]
    enough_history = (max_date - min_date).days + 1 >= window_days * (baseline_windows + 1)

    counts = {}
    for r in rows:
        counts.setdefault(r["grp"], {})[r["bucket"]] = r["n"]

    items = []
    for grp, by_bucket in counts.items():
        current = by_bucket.get(0, 0)
        baseline = [by_bucket.get(i, 0) for i in range(1, baseline_windows + 1)]
        baseline_avg = sum(baseline) / baseline_windows

        if baseline_avg > 0:
            change_pct = round((current / baseline_avg - 1) * 100, 1)
            is_spike = current >= min_count and current / baseline_avg >= threshold
        else:
            change_pct = None
            is_spike = current >= min_count

        items.append({
            "group": grp,
            "current": current,
            "baseline_avg": round(baseline_avg, 1),
            "change_pct": change_pct,
            "is_spike": is_spike,
        })

    items.sort(key=lambda i: (not i["is_spike"], -(i["change_pct"] if i["change_pct"] is not None else 10**9)))

    return {
        "as_of": max_date.isoformat(),
        "group_by": group_by,
        "window_days": window_days,
        "baseline_windows": baseline_windows,
        "threshold": threshold,
        "min_count": min_count,
        "enough_history": enough_history,
        "items": items,
    }
