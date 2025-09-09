#!/usr/bin/env python3
# agent_tools/bigquery_tool.py
"""
BigQuery helper: run queries or fetch table rows and print JSON-serializable output.
Fixes 'Object of type datetime is not JSON serializable' by converting datetime/date/time
and other non-serializable types to JSON-friendly representations.

Usage:
  python agent_tools/bigquery_tool.py --project your-gcp-project --query "SELECT ..." --max 10
  python agent_tools/bigquery_tool.py --project your-gcp-project --table "project.dataset.table" --max 20
"""

from __future__ import annotations
import os
import sys
import json
import argparse
from typing import List, Dict, Any, Optional
from datetime import datetime, date, time
from decimal import Decimal
from google.cloud import bigquery
from google.api_core.exceptions import GoogleAPICallError, NotFound

from dotenv import load_dotenv
load_dotenv()

DEFAULT_PROJECT = os.getenv("BQ_PROJECT")  # optional default project env var


def get_bq_client(project: Optional[str] = None) -> bigquery.Client:
    """
    Create and return a BigQuery client using ADC.
    """
    proj = project or DEFAULT_PROJECT
    if proj:
        return bigquery.Client(project=proj)
    return bigquery.Client()


def json_serializable_default(obj: Any) -> Any:
    """
    json.dumps default handler for non-serializable types.
    Converts datetime/date/time/Decimal to ISO strings or native types.
    Raises TypeError for unknown types to let json.dumps fail loudly.
    """
    if isinstance(obj, (datetime, date, time)):
        # Use ISO 8601 for datetimes and dates/times
        try:
            return obj.isoformat()
        except Exception:
            return str(obj)
    if isinstance(obj, Decimal):
        # convert Decimal to float if safe; otherwise to string
        try:
            return float(obj)
        except Exception:
            return str(obj)
    # BigQuery may return protobuf types or bytes; convert bytes to utf-8 string
    if isinstance(obj, (bytes, bytearray)):
        try:
            return obj.decode("utf-8")
        except Exception:
            return str(obj)
    # Fallback: attempt to convert to string
    return str(obj)


def normalize_value(v: Any) -> Any:
    """
    Recursively normalize a value (row cell) into JSON-serializable form.
    Handles dicts, lists, bigquery Row-like objects, datetimes, Decimals, bytes, etc.
    """
    # Basic JSON-native types pass through
    if v is None or isinstance(v, (str, int, float, bool)):
        return v

    # datetime, date, time
    if isinstance(v, (datetime, date, time)):
        return v.isoformat()

    # Decimal
    if isinstance(v, Decimal):
        try:
            return float(v)
        except Exception:
            return str(v)

    # bytes / bytearray
    if isinstance(v, (bytes, bytearray)):
        try:
            return v.decode("utf-8")
        except Exception:
            return str(v)

    # Mapping-like (including bigquery Row objects that expose .items())
    if hasattr(v, "items"):
        try:
            return {str(k): normalize_value(val) for k, val in v.items()}
        except Exception:
            # fallback to string
            return str(v)

    # Sequence-like
    if isinstance(v, (list, tuple)):
        return [normalize_value(i) for i in v]

    # BigQuery-specific: Row -> dict(row)
    try:
        # Some Row objects support asdict()/to_dict() or behave like mapping
        if hasattr(v, "to_dict"):
            return normalize_value(v.to_dict())
        if hasattr(v, "_asdict"):  # namedtuple-like
            return normalize_value(dict(v._asdict()))
        if isinstance(v, tuple) and hasattr(v, "_fields"):
            return normalize_value(v._asdict())
    except Exception:
        pass

    # Unknown type: convert to string as last resort
    try:
        return str(v)
    except Exception:
        return None


def run_query(
    sql: str,
    project: Optional[str] = None,
    max_results: Optional[int] = None,
    timeout: Optional[float] = 30.0,
) -> List[Dict[str, Any]]:
    """
    Run a SQL query and return results as a list of JSON-serializable dictionaries.
    """
    client = get_bq_client(project)
    job_config = bigquery.QueryJobConfig()
    try:
        job = client.query(sql, job_config=job_config)
        rows = job.result(timeout=timeout)
        results: List[Dict[str, Any]] = []
        count = 0
        for row in rows:
            # Convert Row (Mapping) to dict and normalize values
            try:
                row_dict = dict(row.items())
            except Exception:
                # Fallback: attempt to use row as mapping
                row_dict = {k: getattr(row, k) for k in getattr(row, "_fields", [])} if hasattr(row, "_fields") else dict(row)
            normalized = {k: normalize_value(v) for k, v in row_dict.items()}
            results.append(normalized)
            count += 1
            if max_results is not None and count >= max_results:
                break
        return results
    except GoogleAPICallError as e:
        raise RuntimeError(f"BigQuery API error: {e}") from e
    except Exception as e:
        raise RuntimeError(f"Unexpected error running BigQuery query: {e}") from e


def fetch_table_rows(
    table_ref: str, project: Optional[str] = None, max_results: int = 100
) -> List[Dict[str, Any]]:
    """
    Convenience helper to fetch rows from a table using table reference string:
    example table_ref: "my-project.my_dataset.requirement_testcase_links"
    Returns list of normalized dicts.
    """
    client = get_bq_client(project)
    try:
        table = client.get_table(table_ref)  # raises NotFound if missing
    except NotFound:
        raise RuntimeError(f"Table not found: {table_ref}")
    rows = client.list_rows(table, max_results=max_results)
    results = []
    for r in rows:
        # row may be a Row object; convert to dict then normalize
        try:
            row_dict = dict(r.items())
        except Exception:
            # fallback: iterate over schema fields
            row_dict = {}
            for field in table.schema:
                try:
                    row_dict[field.name] = getattr(r, field.name)
                except Exception:
                    row_dict[field.name] = None
        normalized = {k: normalize_value(v) for k, v in row_dict.items()}
        results.append(normalized)
    return results


def _print_json_serializable(obj: Any):
    """
    Print obj as pretty JSON using the json_serializable_default fallback.
    """
    print(json.dumps(obj, indent=2, ensure_ascii=False, default=json_serializable_default))


def _parse_args():
    parser = argparse.ArgumentParser(description="Small BigQuery helper to run queries or fetch a table.")
    parser.add_argument("--project", "-p", help="GCP project id (optional)")
    parser.add_argument("--query", "-q", help="SQL query to run (standard SQL)", default=None)
    parser.add_argument("--table", "-t", help="Table ref to fetch rows (project.dataset.table)", default=None)
    parser.add_argument("--max", "-m", help="Max rows to fetch", type=int, default=100)
    return parser.parse_args()


def main():
    args = _parse_args()
    try:
        if args.query:
            rows = run_query(args.query, project=args.project, max_results=args.max)
            _print_json_serializable(rows)
        elif args.table:
            rows = fetch_table_rows(args.table, project=args.project, max_results=args.max)
            _print_json_serializable(rows)
        else:
            print("Provide --query or --table. Example: --query 'SELECT * FROM `proj.dataset.table` LIMIT 10'")
    except Exception as err:
        # Print a friendly error and exit non-zero for automation
        print("ERROR:", err)
        sys.exit(1)


if __name__ == "__main__":
    main()
