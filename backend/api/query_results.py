"""
API endpoint for fetching cached query results.

Clients use this as a REST fallback when the WebSocket query.result event
was missed, or to re-fetch a result by its reference ID.
"""
import csv
import io
import re
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from backend.auth.dependencies import get_current_user
from backend.models.user import User
from backend.services.query_result_store import get_query_result

router = APIRouter(prefix="/query-results", tags=["query-results"])

MAX_EXPORT_BYTES = 1024 * 1024  # 1 MB cap on the generated file


def _cap_rows_by_csv_bytes(columns, rows):
    """Greedily serialize rows to CSV, stopping before the 1 MB ceiling.

    Returns (csv_text, capped_rows, truncated). The same capped_rows are reused
    for the XLSX path so both formats honour the byte budget.
    """
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(columns)
    capped_rows = []
    truncated = False
    for row in rows:
        writer.writerow(row)
        if buf.tell() > MAX_EXPORT_BYTES:
            # Roll back the row that crossed the ceiling.
            truncated = True
            break
        capped_rows.append(row)
    # Rebuild CSV from exactly the rows that fit (drops the over-budget row).
    if truncated:
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(columns)
        writer.writerows(capped_rows)
    return buf.getvalue(), capped_rows, truncated


@router.get("/{result_ref}")
async def fetch_query_result(
    result_ref: str,
    current_user: User = Depends(get_current_user),
):
    """
    Retrieve a cached query result by its reference ID.

    Results are stored for 1 hour after execution. Returns 404 if expired
    or if the result does not belong to the authenticated user.
    """
    data = get_query_result(result_ref, str(current_user.id))
    if data is None:
        raise HTTPException(status_code=404, detail="Query result not found or expired")
    return data


@router.get("/{result_ref}/export")
async def export_query_result(
    result_ref: str,
    format: str = "csv",
    current_user: User = Depends(get_current_user),
):
    """
    Download a cached query result as a CSV or Excel (.xlsx) file, capped at 1 MB.

    Rows beyond the byte ceiling are dropped (the file holds the first N rows).
    404 if the result is expired or not owned by the caller; 400 for a bad format.
    """
    if format not in ("csv", "xlsx"):
        raise HTTPException(status_code=400, detail="format must be 'csv' or 'xlsx'")

    data = get_query_result(result_ref, str(current_user.id))
    if data is None:
        raise HTTPException(status_code=404, detail="Query result not found or expired")

    columns = data.get("columns", [])
    rows = data.get("rows", [])
    csv_text, capped_rows, _ = _cap_rows_by_csv_bytes(columns, rows)

    name = re.sub(r"[^A-Za-z0-9_-]", "", data.get("label") or "") or "query-export"

    if format == "csv":
        return StreamingResponse(
            iter([csv_text]),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{name}.csv"'},
        )

    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(list(columns))
    for row in capped_rows:
        ws.append(list(row))
    out = io.BytesIO()
    wb.save(out)
    out.seek(0)
    return StreamingResponse(
        iter([out.getvalue()]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{name}.xlsx"'},
    )
