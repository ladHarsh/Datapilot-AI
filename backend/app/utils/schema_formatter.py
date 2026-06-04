"""
schema_formatter.py — SQL AI Analytics Platform.

Converts raw database schema dictionaries into different textual
representations optimized for prompt injection, debugging, and display.

Author : Member 2 — AI/LLM Engineer
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def to_compact_text(schema: Dict[str, Any]) -> str:
    """Convert schema to compact single-line text for tight token budgets.

    Example output:
        users(id PK, email, name, created_at) | orders(id PK, user_id FK, total, status)
    """
    parts: List[str] = []
    for table in schema.get("tables", []):
        name = table["name"]
        col_parts: List[str] = []
        for col in table.get("columns", []):
            tag = " PK" if col.get("primary_key") else ""
            # Check if it's a FK column
            fk_cols = {fk["column"] for fk in table.get("foreign_keys", [])}
            if col["name"] in fk_cols:
                tag += " FK"
            col_parts.append(f"{col['name']}{tag}")
        parts.append(f"{name}({', '.join(col_parts)})")
    return " | ".join(parts)


def to_verbose_text(schema: Dict[str, Any]) -> str:
    """Convert schema to verbose multi-line format for full context prompts.

    Example output:
        TABLE: users
          - id INT [PK] NOT NULL
          - email VARCHAR(255) NOT NULL
        RELATIONSHIPS:
          orders.user_id → users.id
    """
    lines: List[str] = []
    for table in schema.get("tables", []):
        lines.append(f"TABLE: {table['name']}")
        fk_cols = {fk["column"] for fk in table.get("foreign_keys", [])}
        for col in table.get("columns", []):
            tags: List[str] = []
            if col.get("primary_key"):
                tags.append("PK")
            if col["name"] in fk_cols:
                tags.append("FK")
            if not col.get("nullable", True):
                tags.append("NOT NULL")
            tag_str = f" [{', '.join(tags)}]" if tags else ""
            lines.append(f"  - {col['name']} {col.get('type', '')}{tag_str}")
        lines.append("")

    # Relationships
    rels: List[str] = []
    for table in schema.get("tables", []):
        for fk in table.get("foreign_keys", []):
            rels.append(
                f"  {table['name']}.{fk['column']} → "
                f"{fk['references_table']}.{fk['references_column']}"
            )
    if rels:
        lines.append("RELATIONSHIPS:")
        lines.extend(rels)

    return "\n".join(lines)


def to_table_list(schema: Dict[str, Any]) -> List[str]:
    """Return a flat list of table names from the schema."""
    return [t["name"] for t in schema.get("tables", [])]


def to_column_map(schema: Dict[str, Any]) -> Dict[str, List[str]]:
    """Return a dict of {table_name: [column_names]} for quick lookup."""
    return {
        t["name"]: [c["name"] for c in t.get("columns", [])]
        for t in schema.get("tables", [])
    }


def filter_tables(schema: Dict[str, Any], table_names: List[str]) -> Dict[str, Any]:
    """Return a filtered schema containing only the specified tables."""
    lower_names = {n.lower() for n in table_names}
    filtered = [
        t for t in schema.get("tables", [])
        if t["name"].lower() in lower_names
    ]
    return {"tables": filtered}


def validate_schema(schema: Dict[str, Any]) -> List[str]:
    """Return a list of validation errors for a schema dict.

    Returns an empty list if the schema is valid.
    """
    errors: List[str] = []
    if not isinstance(schema, dict):
        return ["Schema must be a dictionary."]
    tables = schema.get("tables")
    if not tables or not isinstance(tables, list):
        errors.append("Schema must have a 'tables' key with a non-empty list.")
        return errors
    for i, table in enumerate(tables):
        if "name" not in table:
            errors.append(f"Table at index {i} is missing 'name'.")
        if "columns" not in table or not table["columns"]:
            errors.append(f"Table '{table.get('name', i)}' has no columns.")
    return errors
