"""
Validates LLM-generated SQL before execution.
Prevents destructive operations and injection patterns.
NatWest is a bank — demonstrating security awareness matters.
"""

import re


BLOCKED_KEYWORDS = [
    "DROP", "DELETE", "TRUNCATE", "ALTER", "CREATE", "INSERT",
    "UPDATE", "GRANT", "REVOKE", "EXEC", "EXECUTE",
    "INTO OUTFILE", "LOAD_FILE",
]

ALLOWED_FIRST_KEYWORDS = ["SELECT", "WITH"]


def sanitize_sql(sql: str) -> dict:
    """
    Validate that LLM-generated SQL is safe to execute.

    Returns:
        {"safe": True, "sql": cleaned_sql} or
        {"safe": False, "reason": "explanation of why it was blocked"}
    """
    if not sql or not sql.strip():
        return {"safe": False, "reason": "Empty query"}

    cleaned = sql.strip()
    # Remove markdown backticks if LLM wrapped it
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[-1] if "\n" in cleaned else cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    cleaned = cleaned.strip().rstrip(";")

    upper = cleaned.upper().strip()

    # Must start with SELECT or WITH
    first_word = upper.split()[0] if upper.split() else ""
    if first_word not in ALLOWED_FIRST_KEYWORDS:
        return {"safe": False, "reason": f"Query must start with SELECT or WITH, got: {first_word}"}

    # Check for blocked keywords (whole word match)
    for keyword in BLOCKED_KEYWORDS:
        pattern = r'\b' + re.escape(keyword) + r'\b'
        if re.search(pattern, upper):
            return {"safe": False, "reason": f"Blocked operation detected: {keyword}"}

    # No multiple statements
    if ";" in cleaned:
        return {"safe": False, "reason": "Multiple statements not allowed"}

    # No comment injection
    if "--" in cleaned or "/*" in cleaned:
        return {"safe": False, "reason": "SQL comments not allowed in generated queries"}

    return {"safe": True, "sql": cleaned}
