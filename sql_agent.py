import os
import re
from datetime import datetime
from decimal import Decimal
from typing import Optional

from dotenv import load_dotenv
from sqlalchemy import create_engine, inspect, text

load_dotenv()

MAX_ROWS = 1000


# ============================================================
# 1. READ-ONLY SQL SAFETY
# ============================================================

DESTRUCTIVE_PATTERN = re.compile(
    r"\b(DROP|DELETE|UPDATE|INSERT|ALTER|TRUNCATE|REPLACE|"
    r"GRANT|REVOKE|CREATE)\b",
    re.IGNORECASE,
)


def is_destructive(query_text: str) -> bool:
    """Reject destructive SQL operations."""
    return bool(DESTRUCTIVE_PATTERN.search(query_text or ""))


def validate_sql(sql_text: str) -> Optional[str]:
    """
    Validate generated SQL before execution.
    Returns an error message when invalid; otherwise returns None.
    """
    if not sql_text or not sql_text.strip():
        return "Empty SQL statement."

    clean_sql = sql_text.strip()
    sql_no_semi = clean_sql.rstrip(";").strip()

    # Only allow read-oriented query types.
    if not re.match(
        r"^(SELECT|WITH|EXPLAIN|PRAGMA|SHOW|DESC|DESCRIBE)\b",
        sql_no_semi,
        re.IGNORECASE,
    ):
        return "Only read-oriented SQL queries are permitted."

    if is_destructive(sql_no_semi):
        return "Destructive SQL operations are not permitted."

    # Only one statement allowed (blocks "SELECT 1; SELECT ..." tricks).
    if ";" in sql_no_semi:
        return "Multiple SQL statements are not permitted."

    # Reject incomplete numeric literals, such as 8.
    if re.search(r"\b\d+\.(?!\d)", sql_no_semi):
        return "Malformed SQL: Incomplete numeric literal. Execution halted."

    # Reject dangling SQL clauses.
    if re.search(
        r"\b(WHERE|AND|OR|ON|SET|BY|HAVING|ORDER BY|GROUP BY)\s*$",
        sql_no_semi,
        re.IGNORECASE,
    ):
        return "Malformed SQL: query ends with an incomplete clause. Execution halted."

    # Reject dangling operators.
    if re.search(r"(<=|>=|!=|<>|=|<|>|\+|-|/|,)\s*$", sql_no_semi):
        return "Malformed SQL: query ends with an incomplete operator. Execution halted."

    # Reject incomplete LIMIT clauses.
    if re.search(r"\bLIMIT\s*$", sql_no_semi, re.IGNORECASE):
        return "Malformed SQL: LIMIT is missing its row count."

    # Reject a bare column following AND/OR, e.g.
    # WHERE cgpa > 8 AND attendance_percentage
    if re.search(
        r"\b(?:AND|OR)\s+[`\"A-Za-z_][\w`\"]*\s*$",
        sql_no_semi,
        re.IGNORECASE,
    ):
        return "Malformed SQL: a filter condition is incomplete."

    # Check parentheses.
    if sql_no_semi.count("(") != sql_no_semi.count(")"):
        return "Malformed SQL: unbalanced parentheses."

    # Basic SELECT validation.
    if re.match(r"^SELECT\b", sql_no_semi, re.IGNORECASE):
        if not re.search(r"\bFROM\b", sql_no_semi, re.IGNORECASE):
            return "Malformed SQL: SELECT query is missing FROM."

        if re.search(r"\bWHERE\s*(?:;|$)", sql_no_semi, re.IGNORECASE):
            return "Malformed SQL: WHERE has no condition."

    return None


def find_unknown_tables(sql_text: str, schema: dict) -> list:
    """
    Return table names used in FROM/JOIN that do NOT exist in the
    active database schema. This stops table hallucinations.
    """
    known = {t.lower() for t in schema}
    cleaned = re.sub(r"EXTRACT\s*\([^)]*\)", " ", sql_text, flags=re.IGNORECASE)
    cleaned = re.sub(r"SUBSTRING\s*\([^)]*\)", " ", cleaned, flags=re.IGNORECASE)

    ctes = {
        m.lower()
        for m in re.findall(r"\b([A-Za-z_]\w*)\s+AS\s*\(", cleaned, re.IGNORECASE)
    }
    used = re.findall(
        r"\b(?:FROM|JOIN)\s+(?:[`\"\[]?\w+[`\"\]]?\.)?[`\"\[]?([A-Za-z_]\w*)",
        cleaned,
        re.IGNORECASE,
    )
    return sorted({u for u in used if u.lower() not in known and u.lower() not in ctes})


# ============================================================
# 2. DATABASE VERIFICATION
# ============================================================

def verify_active_database(
    conn,
    db_type: str,
    expected_db_name: str = None,
) -> str:
    """Verify that the connection points to the expected database."""
    db_type_lower = (db_type or "").lower()
    active_db = None

    if db_type_lower == "mysql":
        active_db = conn.execute(text("SELECT DATABASE()")).scalar()

    elif db_type_lower == "postgresql":
        active_db = conn.execute(text("SELECT current_database()")).scalar()

    elif db_type_lower == "mssql":
        active_db = conn.execute(text("SELECT DB_NAME()")).scalar()

    elif db_type_lower == "sqlite":
        active_db = expected_db_name or "sqlite"

    else:
        try:
            active_db = conn.execute(text("SELECT DATABASE()")).scalar()
        except Exception:
            active_db = expected_db_name or "connected_db"

    if (
        expected_db_name
        and active_db
        and db_type_lower != "sqlite"
        and active_db.strip().lower() != expected_db_name.strip().lower()
    ):
        raise ValueError(
            f"Database verification failed. Expected '{expected_db_name}', "
            f"but connected to '{active_db}'."
        )

    return active_db or expected_db_name or "unknown"


# ============================================================
# 3. SCHEMA DISCOVERY
# ============================================================

def discover_schema(engine, db_type: str = "") -> dict:
    """Return table names and column names/types."""
    schema = {}
    db_type_lower = (db_type or "").lower()

    if db_type_lower == "mysql":
        try:
            with engine.connect() as conn:
                result = conn.execute(
                    text("""
                        SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE
                        FROM INFORMATION_SCHEMA.COLUMNS
                        WHERE TABLE_SCHEMA = DATABASE()
                        ORDER BY TABLE_NAME, ORDINAL_POSITION
                    """)
                )

                for table_name, col_name, data_type in result:
                    schema.setdefault(table_name, []).append({
                        "name": col_name,
                        "type": str(data_type).lower(),
                    })

                if schema:
                    return schema

        except Exception:
            pass

    try:
        inspector = inspect(engine)

        for table_name in inspector.get_table_names():
            schema[table_name] = [
                {
                    "name": column["name"],
                    "type": str(column["type"]).lower(),
                }
                for column in inspector.get_columns(table_name)
            ]

    except Exception as exc:
        print(f"Schema discovery error: {exc}")

    return schema


def get_distinct_values(
    engine,
    table: str,
    column: str,
    limit: int = 15,
) -> list:
    """Get sample distinct values from a column."""
    try:
        preparer = engine.dialect.identifier_preparer
        safe_table = preparer.quote(table)
        safe_column = preparer.quote(column)

        if engine.dialect.name == "mssql":
            query = text(
                f"SELECT DISTINCT TOP {int(limit)} {safe_column} "
                f"FROM {safe_table} WHERE {safe_column} IS NOT NULL"
            )
        else:
            query = text(
                f"SELECT DISTINCT {safe_column} "
                f"FROM {safe_table} "
                f"WHERE {safe_column} IS NOT NULL "
                f"LIMIT {int(limit)}"
            )

        with engine.connect() as conn:
            return [
                str(row[0])
                for row in conn.execute(query).fetchall()
                if row[0] is not None
            ]

    except Exception:
        return []


# ============================================================
# 4. CHECK THAT REQUESTED FILTERS WERE NOT OMITTED
# ============================================================

def validate_requested_conditions(
    question: str,
    generated_sql: str,
    schema: dict,
    target_table: str,
) -> Optional[str]:
    """
    Ensure important conditions explicitly requested in natural
    language appear in the generated SQL.
    """
    q = question.lower()
    sql = generated_sql.lower()

    columns = {c["name"].lower() for c in schema.get(target_table, [])}

    asks_zero_backlogs = bool(
        re.search(r"\b(?:zero|no|without)\s+backlogs?\b", q)
        or re.search(r"\bbacklogs?\s*(?:=|is|equal to)\s*0\b", q)
    )

    if asks_zero_backlogs and "backlogs" in columns:
        has_backlog_filter = bool(
            re.search(r"\bbacklogs?\b\s*(?:=|<=|<)\s*0\b", sql)
            or re.search(r"\bbacklogs?\b\s+IS\s+NULL\b", sql)
        )

        if not has_backlog_filter:
            return (
                "SQL generation omitted the requested zero-backlogs "
                "condition. Expected a backlogs = 0 filter."
            )

    cgpa_requested = re.search(
        r"\bcgpa\b\s*(?:above|greater than|more than|>|below|less than|<|>=|<=)"
        r"\s*\d+(?:\.\d+)?",
        q,
    )

    if cgpa_requested and "cgpa" in columns:
        if not re.search(r"\bcgpa\b\s*(?:>|<|>=|<=|=)\s*\d", sql):
            return "SQL generation omitted the requested CGPA filter."

    attendance_requested = re.search(
        r"\b(?:attendance_percentage|attendance)\b\s*"
        r"(?:above|greater than|more than|>|below|less than|<|>=|<=)"
        r"\s*\d+(?:\.\d+)?\s*%?",
        q,
    )

    if attendance_requested:
        attendance_column = (
            "attendance_percentage"
            if "attendance_percentage" in columns
            else "attendance" if "attendance" in columns else None
        )

        if attendance_column and not re.search(
            rf"\b{re.escape(attendance_column)}\b\s*(?:>|<|>=|<=|=)\s*\d",
            sql,
        ):
            return "SQL generation omitted the requested attendance filter."

    return None


# ============================================================
# 5. TABLE RESOLUTION (schema-first)
# ============================================================
# Looks at the ACTUAL tables/columns of the connected DB and scores them.
# Keywords only add weight to tables that really exist.

# entity -> (weight, keywords). An entity applies to tables whose name contains it.
ENTITY_INTENTS = {
    "student": (5, [
        "student", "students", "cgpa", "marks", "semester", "roll_number",
        "graduation_year", "backlogs", "register_number", "roll number",
        "register number", "reg no", "roll no", "reg_no", "roll_no",
        "registration number",
    ]),
    "employee": (5, [
        "employee", "employees", "salary", "staff", "worker", "workers",
        "leaves", "job_role", "hire_date",
    ]),
    "project": (5, ["project", "projects", "task", "tasks"]),
    "course": (5, ["course", "courses", "credits", "syllabus"]),
    "department": (2, ["department", "departments"]),
    "expense": (5, ["expense", "expenses"]),
    "asset": (5, ["asset", "assets", "office_assets"]),
}

UNAVAILABLE_ENTITIES = [
    "professor", "professors", "teacher", "teachers", "faculty",
    "customer", "customers", "order", "orders", "invoice", "invoices",
    "sales", "product", "products", "inventory",
]

# Phrases that mean "list the tables in this database".
TABLE_LIST_PHRASES = {
    "show tables", "list tables", "tables", "get tables",
    "show all tables", "list all tables", "get all tables",
}


def _has_word(text_lower: str, word: str) -> bool:
    """Whole-word match (so 'order by' / 'bookmarks' don't trigger false hits)."""
    return bool(
        re.search(
            rf"(?<![a-z0-9_]){re.escape(word.lower())}(?![a-z0-9_])",
            text_lower,
        )
    )


def resolve_target_table(q_lower: str, schema: dict):
    """Returns (table_name, None) or (None, error_dict)."""
    table_names = sorted(schema.keys())
    scores = {}

    for table in table_names:
        t = table.lower()
        score = 0

        # 1) Table explicitly named in the question.
        singular = t[:-1] if t.endswith("s") and len(t) > 3 else t
        if _has_word(q_lower, t) or (len(singular) > 3 and _has_word(q_lower, singular)):
            score += 10

        # 2) Entity intent, applied ONLY to tables that exist.
        for entity, (weight, keywords) in ENTITY_INTENTS.items():
            if entity in t and any(_has_word(q_lower, k) for k in keywords):
                score += weight
                if t in (entity, f"{entity}s"):
                    score += 1  # prefer the canonical table (students > student_marks)

        # 3) Column names mentioned in the question.
        for col in schema[table]:
            cname = col["name"].lower()
            if len(cname) > 2 and (
                _has_word(q_lower, cname)
                or _has_word(q_lower, cname.replace("_", " "))
            ):
                score += 2

        scores[table] = score

    best = max(scores.values(), default=0)

    if best > 0:
        winners = [t for t in table_names if scores[t] == best]
        return winners[0], None

    # Nothing in this DB matched. Is the user asking about something that
    # genuinely does not exist here?
    for entity, (_, keywords) in ENTITY_INTENTS.items():
        if entity == "department":
            continue
        if any(_has_word(q_lower, k) for k in keywords):
            return None, {
                "error": (
                    f"The selected database does not contain a '{entity}s' table. "
                    f"Available tables: {', '.join(table_names)}."
                )
            }

    for entity in UNAVAILABLE_ENTITIES:
        if re.search(rf"\b{entity}\b(?!\s+by\b)", q_lower):
            return None, {
                "error": (
                    f"The selected database does not contain a '{entity}' table. "
                    f"Available tables: {', '.join(table_names)}."
                )
            }

    if len(table_names) == 1:
        return table_names[0], None

    return None, {
        "error": (
            "Could not determine target table for the question. "
            f"Available tables: {', '.join(table_names)}."
        ),
        "fallback_ok": True,
    }


# ============================================================
# 6. RULE-BASED NATURAL-LANGUAGE-TO-SQL
# ============================================================

# Words a user may use for each output column -> actual column key.
PROJECTION_SYNONYMS = {
    "name": ["names", "name"],
    "roll_number": ["roll number", "roll_number", "roll no"],
    "department": ["department", "dept", "branch"],
    "cgpa": ["cgpa", "gpa"],
    "attendance_percentage": ["attendance percentage", "attendance_percentage", "attendance"],
    "backlogs": ["backlogs", "backlog"],
    "semester": ["semester", "sem"],
    "course": ["course"],
    "graduation_year": ["graduation year", "graduation_year"],
    "year_of_study": ["year of study", "year_of_study"],
    "email": ["email", "mail"],
    "phone": ["phone", "mobile", "contact number"],
    "gender": ["gender"],
    "city": ["city"],
    "salary": ["salary", "pay"],
}

# If a column is followed by one of these, it is a FILTER, not an output column.
_FILTER_AFTER = re.compile(
    r"^\s*(?:above|below|over|under|more|less|greater|equal|is|=|>|<|>=|<=)\b|^\s*[<>=]",
    re.IGNORECASE,
)


def _find_projection_segment(q_lower: str) -> Optional[str]:
    """Return the text after a 'show/display/list/...' verb, up to a sort clause."""
    match = re.search(
        r"\b(?:showing|shows?|displays?|display|returns?|return|lists?|list|"
        r"gives?|give\s+me|give|fetch|select)\b\s+(.+?)"
        r"(?:\b(?:ordered|order|sorted|sort|sorting|limit)\b|$)",
        q_lower,
    )
    return match.group(1) if match else None


def resolve_requested_columns(q_lower: str, col_map: dict, name_cols: list) -> Optional[list]:
    """
    Work out which OUTPUT columns the user asked for, e.g.
    'showing their names, department, CGPA, and attendance'
    -> [first_name, last_name, department, cgpa, attendance_percentage].
    Returns None when no column list is requested (caller falls back to *).
    """
    segment = _find_projection_segment(q_lower)
    if not segment:
        return None

    seg = segment.strip()
    if re.match(r"^(?:all|every|everything)\b", seg) or "*" in seg:
        return ["*"]

    found = []  # (position_in_question, column_name)
    for key, synonyms in PROJECTION_SYNONYMS.items():
        cols = name_cols if key == "name" else ([col_map[key]] if key in col_map else [])
        if not cols:
            continue

        for syn in synonyms:
            pattern = rf"(?<![a-z0-9_]){re.escape(syn)}(?![a-z0-9_])"
            matches = [
                m for m in re.finditer(pattern, seg)
                if not _FILTER_AFTER.match(seg[m.end():])
            ]
            if matches:
                for c in cols:
                    found.append((matches[0].start(), c))
                break  # first matching synonym wins for this key

    if not found:
        return None

    ordered, seen = [], set()
    for _, col in sorted(found):
        if col not in seen:
            seen.add(col)
            ordered.append(col)
    return ordered


def generate_schema_aware_sql(
    engine,
    schema: dict,
    question: str,
    db_type: str = "",
) -> dict:
    """Generate schema-aware SQL for a natural-language question."""

    q_raw = (question or "").strip()
    table_names = list(schema.keys())

    if not table_names:
        return {"error": "Selected database contains no tables."}

    # Allow explicitly supplied read-only SQL.
    raw_prefixes = (
        "select ",
        "with ",
        "explain ",
        "pragma ",
        "desc ",
        "describe ",
        "show tables",
        "show databases",
        "show columns",
        "show create",
        "show collation",
        "show status",
    )

    is_table_list_request = (
        re.sub(r"[\.\?!;]+$", "", q_raw).strip().lower() in TABLE_LIST_PHRASES
    )

    if q_raw.lower().startswith(raw_prefixes) and not is_table_list_request:
        validation_error = validate_sql(q_raw)

        if validation_error:
            return {"error": validation_error}

        return {"sql": q_raw}

    q_stripped = re.sub(r"[\.\?!;]+$", "", q_raw).strip()
    q_lower = q_stripped.lower()

    # Show available tables.
    if q_lower in TABLE_LIST_PHRASES:
        table_list = "\n".join(f"- {t}" for t in table_names)
        dialect = (db_type or "").lower()

        if dialect == "mysql":
            metadata_sql = "SHOW TABLES"
        elif dialect == "postgresql":
            metadata_sql = (
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public'"
            )
        elif dialect == "mssql":
            metadata_sql = "SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES"
        else:
            metadata_sql = "SELECT name FROM sqlite_master WHERE type='table';"

        return {
            "sql": metadata_sql,
            "direct_result": f"Available tables:\n{table_list}",
        }

    table_names_lower = {t.lower(): t for t in table_names}

    # ---- TABLE SELECTION (schema-first) ----
    target_table, table_error = resolve_target_table(q_lower, schema)

    if table_error:
        return table_error

    cols = schema.get(target_table, [])
    col_names = [c["name"] for c in cols]
    col_map = {c["name"].lower(): c["name"] for c in cols}

    def get_name_columns() -> Optional[list]:
        """Resolve the column(s) representing name in the target table."""
        if "first_name" in col_map and "last_name" in col_map:
            return [col_map["first_name"], col_map["last_name"]]
        elif "student_name" in col_map:
            return [col_map["student_name"]]
        elif "employee_name" in col_map:
            return [col_map["employee_name"]]
        elif "full_name" in col_map:
            return [col_map["full_name"]]
        elif "name" in col_map:
            return [col_map["name"]]
        elif "first_name" in col_map:
            return [col_map["first_name"]]
        return None

    # --------------------------------------------------------
    # Case 0: Lookup by Register Number, Roll Number, ID, or Code
    # (value must contain a digit, so "regarding", "ids", "roll"
    #  are not captured as fake register numbers/IDs.)
    # --------------------------------------------------------
    reg_match = re.search(
        r"\b(?:register|reg|roll|registration)"
        r"(?:[_\s]*(?:number|no\.?|num\.?))?"
        r"\s*(?:is|=|:)?\s*#?\s*['\"]?"
        r"((?=[A-Za-z0-9_\-]*\d)[A-Za-z0-9_\-]+)['\"]?",
        q_raw,
        re.IGNORECASE,
    )

    id_match = re.search(
        r"\b(?:student\s+|employee\s+|project\s+|course\s+|task\s+|department\s+)?"
        r"(?:id|identifier|code)\s*(?:is|=|number)?\s*#?\s*['\"]?"
        r"((?=[A-Za-z0-9_\-]*\d)[A-Za-z0-9_\-]+)['\"]?\b",
        q_raw,
        re.IGNORECASE,
    )

    lookup_val = None
    lookup_col = None

    if reg_match:
        lookup_val = reg_match.group(1).strip()
        reg_candidates = [
            "roll_number", "register_number", "reg_no", "roll_no",
            "registration_no", "registration_number", "reg_num", "rollno",
            "regno", "registerno", "registernumber", "student_id", "id",
        ]
        lookup_col = next(
            (col_map[c.lower()] for c in reg_candidates if c.lower() in col_map),
            None,
        )
        if not lookup_col:
            return {
                "error": (
                    f"The table '{target_table}' does not contain a register number "
                    f"or roll number column. Available columns: {', '.join(col_names)}."
                )
            }

    elif id_match:
        lookup_val = id_match.group(1).strip()
        id_candidates = [
            f"{target_table.rstrip('s')}_id",
            "student_id", "employee_id", "project_id", "course_id",
            "task_id", "department_id", "id", "employee_code",
        ]
        lookup_col = next(
            (col_map[c.lower()] for c in id_candidates if c.lower() in col_map),
            None,
        )

    if lookup_col and lookup_val:
        safe_val = lookup_val.replace("'", "''")

        asks_name = bool(
            re.search(
                r"\b(?:names?|full_name|student_name|first_name|last_name)\b",
                q_lower,
            )
        )

        if asks_name:
            name_cols = get_name_columns()
            selected_cols = name_cols if name_cols else ["*"]
        else:
            requested_cols = []
            for col_cand in [
                "email", "cgpa", "department", "salary", "phone",
                "attendance_percentage", "semester", "year_of_study",
                "graduation_year", "course",
            ]:
                if col_cand in col_map and re.search(rf"\b{col_cand}\b", q_lower):
                    requested_cols.append(col_map[col_cand])

            selected_cols = requested_cols if requested_cols else ["*"]

        return {
            "sql": (
                f"SELECT {', '.join(selected_cols)} "
                f"FROM {target_table} "
                f"WHERE {lookup_col} = '{safe_val}' LIMIT 1;"
            )
        }

    # --------------------------------------------------------
    # Case 1: Count grouped by department/course/etc.
    # --------------------------------------------------------
    is_count_group = (
        any(p in q_lower for p in ["count", "total number of", "how many", "number of"])
        and any(p in q_lower for p in ["each", "by", "per", "group by"])
    )

    if is_count_group:
        group_col = None

        for candidate in [
            "department", "dept", "course", "gender",
            "year_of_study", "city", "state", "status", "role",
        ]:
            if candidate in col_map and (
                candidate in q_lower
                or f"each {candidate}" in q_lower
                or f"by {candidate}" in q_lower
                or f"per {candidate}" in q_lower
            ):
                group_col = col_map[candidate]
                break

        if not group_col:
            for low_name, actual_name in col_map.items():
                if (
                    f"each {low_name}" in q_lower
                    or f"by {low_name}" in q_lower
                    or f"per {low_name}" in q_lower
                ):
                    group_col = actual_name
                    break

        if (
            not group_col
            and target_table.lower() == "employees"
            and "departments" in table_names_lower
        ):
            dept_cols = {c["name"].lower(): c["name"] for c in schema.get("departments", [])}
            emp_cols = {c["name"].lower(): c["name"] for c in schema.get("employees", [])}
            dept_pk = dept_cols.get("department_id", dept_cols.get("id", "department_id"))
            emp_fk = emp_cols.get("department_id", emp_cols.get("dept_id", "department_id"))
            dept_name_col = dept_cols.get("department_name", dept_cols.get("name", "department_name"))
            emp_pk = emp_cols.get("employee_id", emp_cols.get("id", "employee_id"))
            return {
                "sql": (
                    f"SELECT d.{dept_name_col}, COUNT(e.{emp_pk}) AS total_employees "
                    f"FROM departments d LEFT JOIN employees e ON e.{emp_fk} = d.{dept_pk} "
                    f"GROUP BY d.{dept_pk}, d.{dept_name_col} "
                    f"ORDER BY total_employees DESC;"
                )
            }

        if group_col:
            alias = f"total_{target_table}"
            order_dir = (
                "ASC"
                if "lowest to highest" in q_lower or "ascending" in q_lower
                else "DESC"
            )

            return {
                "sql": (
                    f"SELECT {group_col}, COUNT(*) AS {alias} "
                    f"FROM {target_table} "
                    f"GROUP BY {group_col} "
                    f"ORDER BY {alias} {order_dir};"
                )
            }

    # --------------------------------------------------------
    # Case 1b: "which department has the highest/lowest average cgpa"
    # --------------------------------------------------------
    which_avg = re.search(
        r"\bwhich\s+(\w+)\b.*\b(highest|lowest|best|worst|top)\b.*\b(?:average|avg|mean)\b",
        q_lower,
    )

    if which_avg:
        group_col = col_map.get(which_avg.group(1))
        metric_col = None

        for candidate in ["cgpa", "salary", "marks", "attendance_percentage", "attendance"]:
            if candidate in col_map and candidate in q_lower:
                metric_col = col_map[candidate]
                break

        if group_col and metric_col:
            direction = "ASC" if which_avg.group(2) in ("lowest", "worst") else "DESC"
            alias = f"avg_{metric_col}"
            return {
                "sql": (
                    f"SELECT {group_col}, ROUND(AVG({metric_col}), 2) AS {alias} "
                    f"FROM {target_table} "
                    f"GROUP BY {group_col} "
                    f"ORDER BY {alias} {direction} LIMIT 1;"
                )
            }

    # --------------------------------------------------------
    # Case 2: Average grouped by a column.
    # --------------------------------------------------------
    is_avg_group = (
        any(p in q_lower for p in ["average", "avg", "mean"])
        and any(p in q_lower for p in ["each", "by", "per", "group by"])
    )

    if is_avg_group:
        group_col = None

        for candidate in [
            "department", "dept", "course", "gender",
            "year_of_study", "semester", "city", "state",
        ]:
            if candidate in col_map and candidate in q_lower:
                group_col = col_map[candidate]
                break

        metric_col = None
        for candidate in ["cgpa", "salary", "marks", "attendance_percentage", "attendance"]:
            if candidate in col_map and candidate in q_lower:
                metric_col = col_map[candidate]
                break

        if not metric_col:
            metric_col = col_map.get("cgpa") or col_map.get("salary")

        if group_col and metric_col:
            alias = f"avg_{metric_col}"
            direction = (
                "ASC"
                if "lowest to highest" in q_lower or "ascending" in q_lower
                else "DESC"
            )

            return {
                "sql": (
                    f"SELECT {group_col}, ROUND(AVG({metric_col}), 2) AS {alias} "
                    f"FROM {target_table} "
                    f"GROUP BY {group_col} "
                    f"ORDER BY {alias} {direction};"
                )
            }

    # --------------------------------------------------------
    # Case 3: Overall average.
    # --------------------------------------------------------
    is_simple_avg = (
        any(p in q_lower for p in ["average", "avg", "mean"])
        and not any(p in q_lower for p in ["each", "by", "per", "group by"])
    )

    if is_simple_avg:
        metric_col = None

        for candidate in ["cgpa", "salary", "marks", "attendance_percentage", "attendance"]:
            if candidate in col_map and candidate in q_lower:
                metric_col = col_map[candidate]
                break

        if not metric_col:
            metric_col = col_map.get("cgpa") or col_map.get("salary")

        if metric_col:
            return {
                "sql": (
                    f"SELECT ROUND(AVG({metric_col}), 2) AS average_{metric_col} "
                    f"FROM {target_table};"
                )
            }

    # --------------------------------------------------------
    # Case 4: Overall count.
    # --------------------------------------------------------
    is_simple_count = (
        any(p in q_lower for p in ["how many", "total number of", "count", "total count"])
        and not any(p in q_lower for p in ["each", "by", "per", "group by"])
    )

    if is_simple_count:
        return {
            "sql": f"SELECT COUNT(*) AS total_{target_table} FROM {target_table};"
        }

    # --------------------------------------------------------
    # Case 5: Filter conditions.
    # --------------------------------------------------------
    where_conditions = []

    dept_col = col_map.get("department", col_map.get("dept"))

    if dept_col:
        distinct_depts = get_distinct_values(engine, target_table, dept_col)

        if "cse" in q_lower or "computer science" in q_lower:
            matched = [
                d for d in distinct_depts
                if d.lower() in {"cse", "computer science"}
                or "computer" in d.lower()
            ]

            if matched:
                terms = " OR ".join(
                    f"{dept_col} = '{d.replace(chr(39), chr(39) * 2)}'"
                    for d in matched
                )
                where_conditions.append(f"({terms})")
            else:
                where_conditions.append(
                    f"({dept_col} = 'Computer Science' OR {dept_col} = 'CSE')"
                )

        else:
            for department in distinct_depts:
                if department.lower() in q_lower:
                    safe_value = department.replace("'", "''")
                    where_conditions.append(f"{dept_col} = '{safe_value}'")
                    break

    numeric_patterns = [
        (r"\b(?:cgpa|score|marks)\b\s*(?:above|>|>=|greater than|more than)\s*(\d+(?:\.\d+)?)",
         "cgpa", ">"),
        (r"\b(?:cgpa|score|marks)\b\s*(?:below|<|<=|less than)\s*(\d+(?:\.\d+)?)",
         "cgpa", "<"),
        (r"\b(?:attendance_percentage|attendance)\b\s*(?:above|>|>=|greater than|more than)\s*(\d+(?:\.\d+)?)\s*%?",
         "attendance_percentage", ">"),
        (r"\b(?:attendance_percentage|attendance)\b\s*(?:below|<|<=|less than)\s*(\d+(?:\.\d+)?)\s*%?",
         "attendance_percentage", "<"),
        (r"\b(?:salary|earning)\b\s*(?:more than|>|>=|above|greater than)\s*(\d+(?:\.\d+)?)",
         "salary", ">"),
        (r"\b(?:salary|earning)\b\s*(?:less than|<|<=|below)\s*(\d+(?:\.\d+)?)",
         "salary", "<"),
        (r"\bbacklogs?\s*(?:=|is|equal to)\s*(\d+)\b", "backlogs", "="),
        (r"\b(?:zero|no|without)\s+backlogs?\b", "backlogs", "=", "0"),
        (r"\b(?:graduation_year|year)\s*=\s*(\d+)", "graduation_year", "="),
    ]

    for pattern in numeric_patterns:
        regex, target_col_hint, operator, *fixed_value = pattern
        match = re.search(regex, q_lower)

        if not match:
            continue

        actual_col = col_map.get(target_col_hint)

        if not actual_col:
            continue

        value = fixed_value[0] if fixed_value else match.group(1)

        condition = f"{actual_col} {operator} {value}"
        if condition.lower() not in {c.lower() for c in where_conditions}:
            where_conditions.append(condition)

    # Office management database join: employees in Finance department
    if (
        target_table.lower() == "employees"
        and "finance" in q_lower
        and "departments" in table_names_lower
    ):
        dept_cols = {c["name"].lower(): c["name"] for c in schema.get("departments", [])}
        emp_cols = {c["name"].lower(): c["name"] for c in schema.get("employees", [])}
        dept_pk = dept_cols.get("department_id", dept_cols.get("id", "department_id"))
        emp_fk = emp_cols.get("department_id", emp_cols.get("dept_id", "department_id"))
        dept_name_col = dept_cols.get("department_name", dept_cols.get("name", "department_name"))
        return {
            "sql": (
                f"SELECT e.*, d.{dept_name_col} "
                f"FROM employees e "
                f"JOIN departments d ON e.{emp_fk} = d.{dept_pk} "
                f"WHERE LOWER(d.{dept_name_col}) LIKE '%finance%';"
            )
        }

    explicit_limit_match = re.search(r"\blimit\s+(\d+)\b", q_lower)
    explicit_limit = explicit_limit_match.group(1) if explicit_limit_match else None

    order_clause = ""

    if "top" in q_lower or "highest" in q_lower or "best" in q_lower:
        match = re.search(r"\b(?:top|first)\s+(\d+)", q_lower)
        limit_value = explicit_limit or (match.group(1) if match else "10")

        order_col = (
            col_map.get("cgpa")
            or col_map.get("salary")
            or col_map.get("attendance_percentage")
            or col_map.get("student_id")
            or col_map.get("id")
        )

        if order_col:
            order_clause = f" ORDER BY {order_col} DESC LIMIT {limit_value}"
        else:
            order_clause = f" LIMIT {limit_value}"

    elif "lowest" in q_lower or "worst" in q_lower:
        match = re.search(r"\b(?:bottom|lowest|first)\s+(\d+)", q_lower)
        limit_value = explicit_limit or (match.group(1) if match else "10")

        order_col = col_map.get("cgpa") or col_map.get("salary") or col_map.get("id")

        if order_col:
            order_clause = f" ORDER BY {order_col} ASC LIMIT {limit_value}"

    elif explicit_limit:
        order_clause = f" LIMIT {explicit_limit}"

    # "sorted by cgpa", "ordered by name descending"
    sort_match = re.search(
        r"\b(?:sorted|ordered|order|sort)\s+by\s+([a-z_ ]+?)"
        r"(?:\s+(asc|ascending|desc|descending))?\s*(?:$|limit\b)",
        q_lower,
    )

    if sort_match and not order_clause:
        sort_col = col_map.get(sort_match.group(1).strip().replace(" ", "_"))

        if sort_col:
            if sort_match.group(2):
                direction = "ASC" if sort_match.group(2).startswith("asc") else "DESC"
            else:
                numeric_cols = {"cgpa", "salary", "marks", "attendance_percentage"}
                direction = "DESC" if sort_col.lower() in numeric_cols else "ASC"

            order_clause = f" ORDER BY {sort_col} {direction}"

    where_clause = (
        f" WHERE {' AND '.join(where_conditions)}" if where_conditions else ""
    )

    is_broad_listing = bool(
        q_lower in {
            "show all students", "list all students", "get all students",
            "show students", "list students", "get students", "all students",
            "select all students", "show all records", "show records",
            "all records", "show table students", "display students",
            "show all employees", "list employees", "show employees",
            "show courses", "list courses", "show all courses",
            "show projects", "list projects", "show all projects",
            "show departments", "list departments", "show all departments",
            "show all", "list all", "get all", "all",
        }
        or re.match(
            r"^(?:show|list|get|display|view|fetch|select)\s+(?:all\s+)?"
            r"(?:records\s+from\s+|rows\s+from\s+)?([a-z_]+)"
            r"(?:\s+table)?(?:\s+limit\s+\d+)?$",
            q_lower,
        )
        or (explicit_limit and not where_conditions)
    )

    # Specific question whose filters could not be parsed -> let the
    # grounded LLM fallback try (instead of silently returning SELECT *).
    if not where_conditions and not is_broad_listing and not order_clause:
        specific_intent_indicators = [
            "who", "which", "where", "whose", "with", "having",
            "named", "called", "register", "roll", "reg", "score",
            "marks", "grade", "subject", "salary", "earning", "above",
            "below", "greater", "less", "more than", "equal", "filter",
            "find", "search", "lookup", "backlog", "gender", "year",
            "semester", "details", "info", "is there", "any", "what is",
            "what are", "give me",
        ]
        if any(w in q_lower for w in specific_intent_indicators):
            return {
                "error": (
                    f"Could not generate SQL query for question: '{question}'. "
                    "The requested conditions, filters, or entity attributes could "
                    "not be resolved against the database schema."
                ),
                "fallback_ok": True,
            }

    # Output projection: honour the columns the user asked to see.
    name_cols_now = get_name_columns() or []
    requested_cols = resolve_requested_columns(q_lower, col_map, name_cols_now)

    if requested_cols and requested_cols != ["*"]:
        selected_cols = requested_cols

        # "top 3 students by cgpa" -> also show who the student is
        table_lower = target_table.lower()
        entity_mentioned = (
            _has_word(q_lower, table_lower)
            or _has_word(q_lower, table_lower.rstrip("s"))
        )
        has_name = any(c in selected_cols for c in name_cols_now)

        if name_cols_now and entity_mentioned and not has_name:
            selected_cols = name_cols_now + selected_cols
    else:
        selected_cols = ["*"]

    sql = f"SELECT {', '.join(selected_cols)} FROM {target_table}{where_clause}{order_clause}"

    # Add the default row limit unless the query already has a LIMIT.
    if "LIMIT" not in order_clause:
        sql += " LIMIT 100"

    sql += ";"

    return {"sql": sql}


# ============================================================
# 7. GROUNDED LLM FALLBACK
# ============================================================
# Used ONLY when the rule-based generator cannot understand the question.
# The LLM gets the REAL schema, writes ONE SELECT, and we then:
#   - validate it (read-only, single statement, well-formed)
#   - reject it if it references any table not in this database
# We execute it ourselves, so the LLM never gets direct DB access.

def _to_text(output) -> str:
    """Claude sometimes returns a list of content blocks."""
    if isinstance(output, list):
        return "".join(
            block.get("text", "") if isinstance(block, dict) else str(block)
            for block in output
        )
    return str(output)


def _clean_llm_sql(raw: str) -> str:
    raw = (raw or "").strip()
    raw = re.sub(r"^```(?:sql)?\s*", "", raw, flags=re.IGNORECASE)
    raw = re.sub(r"\s*```$", "", raw)
    return raw.strip()


def llm_generate_sql(
    schema: dict,
    question: str,
    db_name: str,
    db_type: str = "",
) -> dict:
    if os.getenv("ENABLE_LLM_FALLBACK", "true").lower() != "true":
        return {"error": "LLM fallback is disabled."}

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return {"error": "ANTHROPIC_API_KEY is not set."}

    try:
        from langchain_anthropic import ChatAnthropic
    except ImportError:
        return {"error": "langchain_anthropic is not installed."}

    schema_text = "\n".join(
        f"- {table}({', '.join(c['name'] + ' ' + c['type'] for c in cols)})"
        for table, cols in sorted(schema.items())
    )

    system_prompt = (
        f"You are connected to the {db_type or 'SQL'} database '{db_name}'.\n"
        "The ONLY tables and columns that exist are:\n"
        f"{schema_text}\n\n"
        "Rules:\n"
        "1. Write exactly ONE read-only SELECT statement. No explanations, no markdown.\n"
        "2. Use ONLY the tables and columns listed above. Never invent tables "
        "(for example 'employees') that are not listed.\n"
        "3. Limit results to at most 100 rows unless the question is an aggregate.\n"
        "4. If the question cannot be answered from these tables, reply exactly: CANNOT_ANSWER"
    )

    try:
        llm = ChatAnthropic(
            model=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6"),
            temperature=0,
            api_key=api_key,
        )
    except Exception as exc:
        return {"error": f"LLM init failed: {exc}"}

    messages = [("system", system_prompt), ("human", question)]
    last_error = "Unknown LLM error."

    for _ in range(2):  # one retry with feedback
        try:
            reply = llm.invoke(messages)
            sql = _clean_llm_sql(_to_text(reply.content))
        except Exception as exc:
            return {"error": f"LLM call failed: {exc}"}

        if sql.upper().startswith("CANNOT_ANSWER"):
            return {
                "error": (
                    "This question cannot be answered from the tables in "
                    f"'{db_name}'. Available tables: {', '.join(sorted(schema))}."
                )
            }

        problem = validate_sql(sql)
        if not problem:
            unknown = find_unknown_tables(sql, schema)
            if unknown:
                problem = (
                    f"Table(s) {', '.join(unknown)} do not exist. "
                    f"Use only: {', '.join(sorted(schema))}."
                )

        if not problem:
            return {"sql": sql.rstrip(";") + ";"}

        last_error = problem
        messages.append(("ai", sql))
        messages.append(("human", f"That SQL was rejected: {problem} Return a corrected single SELECT."))

    return {"error": f"LLM fallback produced invalid SQL: {last_error}"}


# ============================================================
# 8. FORMAT RESULTS
# ============================================================

def format_rows_as_table(columns: list, rows: list) -> str:
    """Format result rows into a readable text table."""
    if not rows:
        return "Query executed successfully. 0 rows returned."

    str_rows = [
        [str(value) if value is not None else "NULL" for value in row]
        for row in rows
    ]

    widths = [len(str(c)) for c in columns]

    for row in str_rows:
        for index, value in enumerate(row):
            if index < len(widths):
                widths[index] = min(max(widths[index], len(value)), 40)

    header = " | ".join(
        str(c)[:40].ljust(widths[i]) for i, c in enumerate(columns)
    )
    divider = "-+-".join("-" * width for width in widths)

    lines = [header, divider]

    for row in str_rows[:100]:
        lines.append(
            " | ".join(
                row[i][:40].ljust(widths[i])
                for i in range(min(len(columns), len(row)))
            )
        )

    if len(str_rows) > 100:
        lines.append(f"... ({len(str_rows) - 100} more rows)")

    return "\n".join(lines)


# ============================================================
# 9. MAIN DATABASE QUERY FUNCTION
# ============================================================

def query_database(
    connection_string: str,
    question: str,
    expected_db_name: str = None,
    db_type: str = None,
    connection_id: str = None,
) -> dict:
    """Generate, validate, execute and report a read-only query."""

    timestamp = datetime.now().isoformat()
    generated_sql = None
    active_db = expected_db_name
    engine = None

    def fail(result_text, error, **extra):
        payload = {
            "success": False,
            "result": result_text,
            "error": error,
            "query": question,
            "executed_sql": generated_sql,
            "database_name": active_db,
            "database_id": connection_id,
            "timestamp": timestamp,
        }
        payload.update(extra)
        return payload

    try:
        # Block destructive requests before connecting.
        if is_destructive(question):
            return fail(
                "Destructive operations (e.g. DROP, DELETE, UPDATE) are rejected in read-only mode.",
                "Destructive query rejected",
                executed_sql=None,
            )

        # Create connection.
        if connection_string.startswith("sqlite"):
            engine = create_engine(
                connection_string,
                connect_args={"check_same_thread": False},
            )
        else:
            engine = create_engine(connection_string, pool_pre_ping=True)

        # Verify selected database.
        with engine.connect() as conn:
            active_db = verify_active_database(conn, db_type or "", expected_db_name)

        # Discover actual schema of THIS database.
        schema = discover_schema(engine, db_type or "")

        if not schema:
            return fail(
                f"No tables were discovered in '{active_db}'.",
                "Empty schema",
                executed_sql=None,
            )

        # 1st attempt: deterministic rule-based generator (schema-first).
        result = generate_schema_aware_sql(engine, schema, question, db_type or "")
        generation_mode = "rules"

        # 2nd attempt: grounded LLM, only when rules could not understand.
        if "error" in result and result.get("fallback_ok"):
            llm_result = llm_generate_sql(schema, question, active_db, db_type or "")
            if "sql" in llm_result:
                result = llm_result
                generation_mode = "llm"
            else:
                result["error"] = f"{result['error']} (LLM fallback: {llm_result['error']})"

        if "error" in result:
            return fail(
                f"Query generation failed: {result['error']}",
                result["error"],
                executed_sql=None,
            )

        generated_sql = result["sql"]

        # Preserve the table-list response.
        if "direct_result" in result:
            return {
                "success": True,
                "result": result["direct_result"],
                "query": question,
                "executed_sql": generated_sql,
                "generation_mode": generation_mode,
                "database_name": active_db,
                "database_id": connection_id,
                "timestamp": timestamp,
            }

        # Validate syntax and read-only safety.
        validation_error = validate_sql(generated_sql)

        if validation_error:
            return fail(
                f"SQL validation failed: {validation_error}. Execution halted.",
                validation_error,
            )

        # Final guard - every table in the SQL must exist in this DB.
        unknown_tables = find_unknown_tables(generated_sql, schema)

        if unknown_tables:
            msg = (
                f"Generated SQL referenced table(s) not in '{active_db}': "
                f"{', '.join(unknown_tables)}. Available tables: {', '.join(sorted(schema))}."
            )
            return fail(msg, msg)

        # Check that explicitly requested filters were not omitted.
        table_match = re.search(
            r"\bFROM\s+[`\"]?([A-Za-z_]\w*)",
            generated_sql,
            re.IGNORECASE,
        )
        target_table = table_match.group(1) if table_match else None

        if target_table in schema:
            condition_error = validate_requested_conditions(
                question, generated_sql, schema, target_table
            )

            if condition_error:
                return fail(
                    f"SQL generation failed validation: {condition_error}",
                    condition_error,
                )

        # Execute only after validation.
        with engine.connect() as conn:
            exec_result = conn.execute(text(generated_sql))
            columns = list(exec_result.keys())
            raw_rows = exec_result.fetchmany(MAX_ROWS)

        formatted_table = format_rows_as_table(columns, raw_rows)

        result_text = (
            f"Executed SQL on [{active_db}]:\n"
            f"{generated_sql}\n"
            f"Total records returned: {len(raw_rows)}\n\n"
            f"{formatted_table}"
        )

        # Convert returned values to JSON-safe types.
        row_dicts = []

        for row in raw_rows[:200]:
            row_dict = {}

            for index, column in enumerate(columns):
                value = row[index]

                if isinstance(value, Decimal):
                    value = float(value)
                elif hasattr(value, "isoformat"):
                    value = value.isoformat()

                row_dict[column] = value

            row_dicts.append(row_dict)

        return {
            "success": True,
            "result": result_text,
            "query": question,
            "executed_sql": generated_sql,
            "generation_mode": generation_mode,
            "row_count": len(raw_rows),
            "columns": columns,
            "rows": row_dicts,
            "database_name": active_db,
            "database_id": connection_id,
            "timestamp": timestamp,
        }

    except Exception as exc:
        error_text = str(exc)

        # Redact credentials if an exception includes a connection URL.
        error_text = re.sub(r":([^@/]+)@", ":****@", error_text)

        return fail(f"Execution error on database: {error_text}", error_text)

    finally:
        if engine is not None:
            engine.dispose()