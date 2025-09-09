# agent_tools/traceability_tool.py
import json
import time
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

from google.cloud import bigquery
from google.cloud import logging as cloud_logging
from google.api_core.exceptions import GoogleAPICallError

# configure these constants to match your environment
BQ_PROJECT = "hackathon-471416"   # target project where dataset/table lives
BQ_DATASET = "traceability"
BQ_TABLE = "requirement_testcase_links"
BQ_TABLE_REF = f"{BQ_PROJECT}.{BQ_DATASET}.{BQ_TABLE}"  # project.dataset.table

LOGGER_NAME = "traceability_agent"  # Cloud Logging logger name

# clients (shared)
_bq_client = bigquery.Client(project=BQ_PROJECT)
_logging_client = cloud_logging.Client(project=BQ_PROJECT)
_logger = _logging_client.logger(LOGGER_NAME)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_for_test_case(req_obj: Dict[str, Any], tc: Dict[str, Any], created_by: str) -> Dict[str, Any]:
    """
    Build the BigQuery row dict for a single test case.
    Keep keys matching your table schema.
    """
    req_id = req_obj.get("req_id") or req_obj.get("requirement_id") or None
    # canonicalize some fields
    return {
        "req_id": req_id,
        "test_case_id": tc.get("test_case_id") or tc.get("id") or None,
        # store the full test case JSON as a string (or use JSON type if table column is JSON)
        "test_case_json": json.dumps(tc, ensure_ascii=False),
        "test_case_summary": tc.get("title") or tc.get("objective") or "",
        "compliance_status": tc.get("compliance_status") or tc.get("status") or None,
        "tags": json.dumps(tc.get("tags", []), ensure_ascii=False),
        "kb_refs": json.dumps(tc.get("grounding_refs", []), ensure_ascii=False),
        "source_file": req_obj.get("source_file"),
        "ingest_ts": _now_iso(),
        "created_by": created_by,
        "notes": tc.get("notes") or "",
    }


def push_traceability(req_obj: Dict[str, Any],
                      test_cases: List[Dict[str, Any]],
                      created_by: str = "TraceabilityAgent") -> Dict[str, Any]:
    """
    Insert rows for the provided test_cases into BigQuery. Uses streaming inserts (insert_rows_json).
    Returns a summary dict: {"inserted": N, "errors": [...]}
    """
    rows = [_row_for_test_case(req_obj, tc, created_by) for tc in test_cases]
    # insert_rows_json accepts list[dict] and returns list of errors (empty if success)
    try:
        errors = _bq_client.insert_rows_json(BQ_TABLE_REF, rows)  # streaming insert
    except GoogleAPICallError as e:
        # write an audit entry then re-raise
        emit_audit_entry({
            "event": "traceability_insert_failed",
            "req_id": req_obj.get("req_id"),
            "created_by": created_by,
            "error": str(e),
            "ingest_ts": _now_iso(),
            "row_count": len(rows)
        })
        raise

    # log an audit entry for successful insert (or partial success)
    audit = {
        "event": "traceability_insert",
        "req_id": req_obj.get("req_id"),
        "created_by": created_by,
        "row_count": len(rows),
        "errors": errors or [],
        "ingest_ts": _now_iso()
    }
    emit_audit_entry(audit)

    return {"inserted": len(rows) - (len(errors) if errors else 0), "errors": errors or []}


def emit_audit_entry(entry: Dict[str, Any], severity: str = "INFO") -> None:
    """
    Write a structured audit entry to Cloud Logging. These logs can be exported to BigQuery via sinks.
    """
    if "ingest_ts" not in entry:
        entry["ingest_ts"] = _now_iso()
    # Write structured entry
    _logger.log_struct(entry, severity=severity)
