"""Helpers to transform API schema payloads for the Streamlit UI."""


def schema_for_viewer(schema_payload: dict) -> dict:
    """Convert API schema `data` into {table_name: [{name, type, key}, ...]}."""
    viewer: dict = {}
    for table in schema_payload.get("tables", []):
        pk_set = set(table.get("primary_keys", []))
        fk_cols = {
            fk.get("constrained_column")
            for fk in table.get("foreign_keys", [])
            if fk.get("constrained_column")
        }
        cols = []
        for col in table.get("columns", []):
            name = col.get("name", "")
            badges = []
            if name in pk_set:
                badges.append("PK")
            if name in fk_cols:
                badges.append("FK")
            cols.append({
                "name": name,
                "type": col.get("type", ""),
                "key": " ".join(badges),
            })
        viewer[table.get("name", "unknown")] = cols
    return viewer


def build_query_suggestions(schema_payload: dict, max_suggestions: int = 10) -> list[str]:
    """Build natural-language suggestions from table/column names."""
    suggestions: list[str] = []
    numeric_types = ("int", "decimal", "float", "double", "numeric", "real", "money", "bigint")
    date_types = ("date", "time", "timestamp", "datetime")

    tables = schema_payload.get("tables", [])

    for table in tables:
        if len(suggestions) >= max_suggestions:
            break

        tname = table.get("name", "")
        columns = table.get("columns", [])
        if not tname or not columns:
            continue

        col_names = [c.get("name", "") for c in columns]
        numeric = [c["name"] for c in columns if any(t in str(c.get("type", "")).lower() for t in numeric_types)]
        dates   = [c["name"] for c in columns if any(t in str(c.get("type", "")).lower() for t in date_types)]
        text_cols = [c["name"] for c in columns if c["name"] not in numeric and c["name"] not in dates]

        # Analytics suggestions per column type
        if numeric and len(suggestions) < max_suggestions:
            suggestions.append(f"Show total {numeric[0]} from {tname}")
        if numeric and len(suggestions) < max_suggestions:
            suggestions.append(f"Show top 10 {tname} by {numeric[0]}")
        if dates and len(suggestions) < max_suggestions:
            suggestions.append(f"Show {tname} trend by month using {dates[0]}")
        if text_cols and numeric and len(suggestions) < max_suggestions:
            suggestions.append(f"Show {numeric[0]} grouped by {text_cols[0]} in {tname}")
        if text_cols and len(suggestions) < max_suggestions:
            suggestions.append(f"Count {tname} grouped by {text_cols[0]}")
        if len(suggestions) < max_suggestions:
            suggestions.append(f"Show top 10 rows from {tname}")

    # Cross-table join suggestion if multiple tables
    if len(tables) >= 2 and len(suggestions) < max_suggestions:
        t1, t2 = tables[0].get("name", ""), tables[1].get("name", "")
        suggestions.append(f"Show {t1} joined with {t2}")

    # Dedup while preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for s in suggestions:
        if s not in seen:
            seen.add(s)
            unique.append(s)
    return unique[:max_suggestions] or ["List all tables", "Show table row counts"]



def format_metric_number(value: int | float) -> str:
    """Human-readable number for metric cards."""
    n = int(value)
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 10_000:
        return f"{n / 1_000:.1f}K"
    return f"{n:,}"
