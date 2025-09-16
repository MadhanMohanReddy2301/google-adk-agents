from __future__ import annotations
import os
from typing import Any, Dict, List, Optional
from datetime import datetime, date, time
from decimal import Decimal
from dotenv import load_dotenv

load_dotenv()

# BigQuery import is optional at module load-time; raise at runtime if methods are called.
try:
    from google.cloud import bigquery
    from google.api_core.exceptions import GoogleAPICallError, NotFound
except Exception:
    bigquery = None  # type: ignore
    GoogleAPICallError = Exception
    NotFound = Exception

# Optional env-default project
DEFAULT_PROJECT = os.getenv("BQ_PROJECT")

from mcp.server.fastmcp import FastMCP

NAME = "BigQueryTool"
HOST = "0.0.0.0"
PORT = 8080

mcp = FastMCP(NAME, host=HOST, port=PORT)


# ----------------------
# Serialization utilities
# ----------------------
def json_serializable_default(obj: Any) -> Any:
    if isinstance(obj, (datetime, date, time)):
        try:
            return obj.isoformat()
        except Exception:
            return str(obj)
    if isinstance(obj, Decimal):
        try:
            return float(obj)
        except Exception:
            return str(obj)
    if isinstance(obj, (bytes, bytearray)):
        try:
            return obj.decode("utf-8")
        except Exception:
            return str(obj)
    return str(obj)


def normalize_value(v: Any) -> Any:
    if v is None or isinstance(v, (str, int, float, bool)):
        return v
    if isinstance(v, (datetime, date, time)):
        return v.isoformat()
    if isinstance(v, Decimal):
        try:
            return float(v)
        except Exception:
            return str(v)
    if isinstance(v, (bytes, bytearray)):
        try:
            return v.decode("utf-8")
        except Exception:
            return str(v)
    # Mapping-like
    if hasattr(v, "items"):
        try:
            return {str(k): normalize_value(val) for k, val in v.items()}
        except Exception:
            return str(v)
    # Sequence-like
    if isinstance(v, (list, tuple)):
        return [normalize_value(i) for i in v]
    # BigQuery Row-like
    try:
        if hasattr(v, "to_dict"):
            return normalize_value(v.to_dict())
        if hasattr(v, "_asdict"):
            return normalize_value(dict(v._asdict()))
    except Exception:
        pass
    try:
        return str(v)
    except Exception:
        return None


# ----------------------
# BigQuery MCP plugin
# ----------------------
class BigQueryPlugin:
    """
    MCP plugin exposing BigQuery operations over SSE.

    Tools:
      - handle_command(cmd: dict) -> dispatches to select/dml/insert_rows
      - run_query(sql: str, max_results: Optional[int] | None) -> returns rows
      - run_dml(sql: str) -> returns rows_affected or job metadata
      - insert_rows(table: str, rows: List[dict]) -> inserts rows via insert_rows_json
    """

    @staticmethod
    def _ensure_bigquery_available():
        if bigquery is None:
            raise RuntimeError("google.cloud.bigquery is not available. Install google-cloud-bigquery")
    @staticmethod
    def _get_client(project: Optional[str] = None) -> "bigquery.Client":
        BigQueryPlugin._ensure_bigquery_available()
        proj = project or DEFAULT_PROJECT or None
        if proj:
            return bigquery.Client(project=proj)
        return bigquery.Client()

    @staticmethod
    def display_runtime_info():
        """Print the server runtime info to the console."""
        if HOST == "0.0.0.0":
            print(f"{NAME} : Server running on IP: localhost and Port: {PORT}")
            print(f"{NAME} : Server running on IP: 127.0.0.1 and Port: {PORT}")
        print(f"{NAME} : Server running on IP: {HOST} and Port: {PORT}")
        return {"ok": True, "host": HOST, "port": PORT}


    @staticmethod
    @mcp.tool()
    def run_query(sql: str) -> Dict[str, Any]:
        """Run a SELECT query and return normalized rows."""
        try:
            client = BigQueryPlugin._get_client()
            job = client.query(sql)
            rows = job.result(timeout=60)
            out: List[Dict[str, Any]] = []
            count = 0
            for row in rows:
                try:
                    row_dict = dict(row.items())
                except Exception:
                    if hasattr(row, "_asdict"):
                        row_dict = dict(row._asdict())
                    else:
                        row_dict = {k: normalize_value(getattr(row, k, None)) for k in getattr(row, "_fields", [])}
                normalized = {k: normalize_value(v) for k, v in row_dict.items()}
                out.append(normalized)
                count += 1

            return {"ok": True, "rows": out}
        except GoogleAPICallError as e:
            return {"ok": False, "error": f"BigQuery API error: {e}"}
        except Exception as e:
            return {"ok": False, "error": f"unexpected error: {e}"}
    @staticmethod
    @mcp.tool()
    def run_dml( sql: str, ) -> Dict[str, Any]:
        """Run a DML statement (INSERT/UPDATE). Returns job metadata."""
        try:
            client = BigQueryPlugin._get_client()
            job = client.query(sql)
            _ = job.result(timeout=60)
            return {"ok": True, "rows_affected": getattr(job, "num_dml_affected_rows", None)}
        except GoogleAPICallError as e:
            return {"ok": False, "error": f"BigQuery API error: {e}"}
        except Exception as e:
            return {"ok": False, "error": str(e)}
    @staticmethod
    @mcp.tool()
    def insert_rows(table: str, rows: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Insert JSON-serializable rows into a table using insert_rows_json.

        `table` should be a table ref like project.dataset.table or dataset.table if
        project is provided.
        """
        try:
            client = BigQueryPlugin._get_client()
            errors = client.insert_rows_json(table, rows)
            if errors:
                return {"ok": False, "errors": errors}
            return {"ok": True, "inserted": len(rows)}
        except NotFound:
            return {"ok": False, "error": f"table not found: {table}"}
        except GoogleAPICallError as e:
            return {"ok": False, "error": f"BigQuery API error: {e}"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def run(self, transport: str = "sse"):
        """Start the MCP server and print runtime info."""
        self.display_runtime_info()
        mcp.run(transport=transport)


if __name__ == "__main__":
    server = BigQueryPlugin()
    server.run()
