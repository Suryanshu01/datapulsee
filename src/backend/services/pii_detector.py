"""
PII detector for DataPulse. Scans columns for sensitive data patterns.
Flagged columns have sample_values excluded from LLM prompts.
"""

from __future__ import annotations

import re
import logging
from typing import Any

import duckdb

logger = logging.getLogger(__name__)

_EMAIL_RE = re.compile(r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$')
_PHONE_RE = re.compile(r'^[\+]?[\d\s\-\(\)]{10,}$')
_AADHAAR_RE = re.compile(r'^\d{4}\s?\d{4}\s?\d{4}$')
_PAN_RE = re.compile(r'^[A-Z]{5}\d{4}[A-Z]$')


def _luhn_check(num_str: str) -> bool:
    digits = [int(d) for d in num_str if d.isdigit()]
    if len(digits) < 13 or len(digits) > 19:
        return False
    checksum = 0
    for i, d in enumerate(reversed(digits)):
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        checksum += d
    return checksum % 10 == 0


def scan_for_pii(conn, schema, table_name="dataset", sample_size=100):
    flagged = []
    string_cols = [c["column"] for c in schema if "VARCHAR" in c["type"].upper() or "TEXT" in c["type"].upper()]
    for col_name in string_cols:
        try:
            rows = conn.execute(f'SELECT DISTINCT CAST("{col_name}" AS VARCHAR) AS val FROM "{table_name}" WHERE "{col_name}" IS NOT NULL LIMIT {sample_size}').fetchdf().to_dict(orient="records")
            values = [str(r["val"]).strip() for r in rows if r["val"]]
            if not values:
                continue
            total = len(values)
            email_m = sum(1 for v in values if _EMAIL_RE.match(v))
            if email_m > total * 0.3:
                flagged.append({"column": col_name, "pii_type": "email", "confidence": "high" if email_m > total * 0.7 else "medium", "match_pct": round(email_m / total * 100)})
                continue
            phone_m = sum(1 for v in values if _PHONE_RE.match(v))
            if phone_m > total * 0.3:
                flagged.append({"column": col_name, "pii_type": "phone_number", "confidence": "high" if phone_m > total * 0.7 else "medium", "match_pct": round(phone_m / total * 100)})
                continue
            cc_m = sum(1 for v in values if _luhn_check(v))
            if cc_m > total * 0.2:
                flagged.append({"column": col_name, "pii_type": "credit_card", "confidence": "high", "match_pct": round(cc_m / total * 100)})
                continue
            name_lower = col_name.lower()
            pii_hints = {"email": "email", "phone": "phone_number", "mobile": "phone_number", "ssn": "national_id", "aadhaar": "aadhaar", "pan": "pan_card", "passport": "national_id", "card_number": "credit_card", "account_number": "account"}
            for hint, pii_type in pii_hints.items():
                if hint in name_lower:
                    flagged.append({"column": col_name, "pii_type": pii_type, "confidence": "low", "match_pct": 0, "reason": "column_name_match"})
                    break
        except Exception as exc:
            logger.debug("PII scan failed for %s: %s", col_name, exc)
    return flagged


def sanitize_semantic_layer(semantic_layer, pii_columns):
    pii_col_names = {item["column"] for item in pii_columns}
    sanitized = dict(semantic_layer)
    for group_key in ["dimensions", "time_dimensions"]:
        new_group = []
        for item in sanitized.get(group_key, []):
            item_copy = dict(item)
            if item_copy.get("column") in pii_col_names:
                item_copy.pop("sample_values", None)
                item_copy["pii_redacted"] = True
            new_group.append(item_copy)
        sanitized[group_key] = new_group
    return sanitized