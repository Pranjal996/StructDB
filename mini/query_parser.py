"""
query_parser.py
SQL-like query parser for StructDB.

Supported statements
--------------------
  DDL  : CREATE DATABASE, DROP DATABASE, USE, SHOW DATABASES,
          CREATE TABLE, DROP TABLE, SHOW TABLES, DESCRIBE,
          CREATE INDEX ON table(col)
  DML  : INSERT INTO ... VALUES, SELECT (with JOIN, WHERE, ORDER BY, LIMIT,
          aggregate functions), UPDATE ... SET ... WHERE, DELETE FROM ... WHERE
  Util : EXPLAIN <query>, IMPORT <table> FROM '<file.csv>',
          BEGIN | COMMIT | ROLLBACK
"""

import re


class QueryParser:

    # ── top-level dispatcher ─────────────────────────────────────────────────
    @staticmethod
    def parse(query):
        q = query.strip()
        if q.endswith(';'):
            q = q[:-1].strip()
        u = q.upper()

        # ── transactions ──────────────────────────────────────────────────
        if u in ('BEGIN', 'BEGIN TRANSACTION'):
            return {'type': 'BEGIN'}
        if u == 'COMMIT':
            return {'type': 'COMMIT'}
        if u == 'ROLLBACK':
            return {'type': 'ROLLBACK'}

        # ── EXPLAIN ───────────────────────────────────────────────────────
        if u.startswith('EXPLAIN '):
            inner = q[8:].strip()
            inner_parsed = QueryParser.parse(inner)
            return {'type': 'EXPLAIN', 'inner': inner_parsed, 'raw': inner}

        # ── IMPORT ────────────────────────────────────────────────────────
        m = re.match(r'IMPORT\s+(\w+)\s+FROM\s+[\'"](.+?)[\'"]', q, re.IGNORECASE)
        if m:
            return {'type': 'IMPORT', 'table': m.group(1), 'file': m.group(2)}

        # ── CREATE INDEX ──────────────────────────────────────────────────
        m = re.match(r'CREATE\s+INDEX\s+ON\s+(\w+)\s*\(\s*(\w+)\s*\)', q, re.IGNORECASE)
        if m:
            return {'type': 'CREATE_INDEX', 'table': m.group(1), 'column': m.group(2)}

        # ── database-level ────────────────────────────────────────────────
        if u.startswith('CREATE DATABASE'):
            m = re.match(r'CREATE\s+DATABASE\s+(\w+)', q, re.IGNORECASE)
            if m:
                return {'type': 'CREATE_DATABASE', 'database': m.group(1)}

        if u.startswith('DROP DATABASE'):
            m = re.match(r'DROP\s+DATABASE\s+(\w+)', q, re.IGNORECASE)
            if m:
                return {'type': 'DROP_DATABASE', 'database': m.group(1)}

        if u.startswith('USE'):
            m = re.match(r'USE\s+(\w+)', q, re.IGNORECASE)
            if m:
                return {'type': 'USE_DATABASE', 'database': m.group(1)}

        if re.match(r'SHOW\s+DATABASES', q, re.IGNORECASE):
            return {'type': 'SHOW_DATABASES'}

        if re.match(r'SHOW\s+TABLES', q, re.IGNORECASE):
            return {'type': 'SHOW_TABLES'}

        if u.startswith(('DESC ', 'DESCRIBE ')):
            m = re.match(r'(?:DESCRIBE|DESC)\s+(\w+)', q, re.IGNORECASE)
            if m:
                return {'type': 'DESCRIBE_TABLE', 'table': m.group(1)}

        # ── table-level ───────────────────────────────────────────────────
        if u.startswith('CREATE TABLE'):
            m = re.match(r'CREATE\s+TABLE\s+(\w+)\s*\((.+)\)', q, re.IGNORECASE | re.DOTALL)
            if m:
                cols = QueryParser._parse_col_defs(m.group(2))
                if not cols:
                    raise ValueError("CREATE TABLE needs at least one column")
                return {'type': 'CREATE_TABLE', 'table': m.group(1), 'columns': cols}

        if u.startswith('DROP TABLE'):
            m = re.match(r'DROP\s+TABLE\s+(\w+)', q, re.IGNORECASE)
            if m:
                return {'type': 'DROP_TABLE', 'table': m.group(1)}

        if u.startswith('INSERT'):
            m = re.match(r'INSERT\s+INTO\s+(\w+)\s+VALUES\s*\((.+)\)', q, re.IGNORECASE | re.DOTALL)
            if m:
                return {'type': 'INSERT', 'table': m.group(1),
                        'values': QueryParser._parse_values(m.group(2))}

        if u.startswith('SELECT'):
            return QueryParser._parse_select(q)

        if u.startswith('UPDATE'):
            return QueryParser._parse_update(q)

        if u.startswith('DELETE'):
            return QueryParser._parse_delete(q)

        raise ValueError(f"Unrecognised query syntax: {q[:60]}")

    # ── SELECT (with optional JOIN) ──────────────────────────────────────────
    @staticmethod
    def _parse_select(q):
        # aggregate: SELECT COUNT/SUM/AVG/MIN/MAX(col) FROM tbl [WHERE] [ORDER BY] [LIMIT]
        agg = re.match(
            r'SELECT\s+(COUNT|SUM|AVG|MIN|MAX)\s*\(\s*(\*|\w+)\s*\)\s+FROM\s+(\w+)'
            r'(?:\s+WHERE\s+(.+?))?(?:\s+ORDER\s+BY\s+(.+?))?(?:\s+LIMIT\s+(\d+))?$',
            q, re.IGNORECASE)
        if agg:
            fn, col, tbl, wh, ob, lim = agg.groups()
            return {'type': 'AGGREGATE', 'function': fn,
                    'column': col if col != '*' else None, 'table': tbl,
                    'where': QueryParser._parse_where(wh) if wh else None}

        # JOIN: SELECT cols FROM t1 JOIN t2 ON t1.c = t2.c [WHERE] [ORDER BY] [LIMIT]
        jn = re.match(
            r'SELECT\s+(.+?)\s+FROM\s+(\w+)\s+(?:INNER\s+)?JOIN\s+(\w+)\s+ON\s+'
            r'(\w+)\.(\w+)\s*=\s*(\w+)\.(\w+)'
            r'(?:\s+WHERE\s+(.+?))?(?:\s+ORDER\s+BY\s+(.+?))?(?:\s+LIMIT\s+(\d+))?$',
            q, re.IGNORECASE)
        if jn:
            cols_s, t1, t2, lt, lc, rt, rc, wh, ob, lim = jn.groups()
            cols = None if cols_s.strip() == '*' else [c.strip() for c in cols_s.split(',')]
            return {
                'type': 'JOIN_SELECT',
                'columns': cols,
                'table1': t1, 'table2': t2,
                'join_on': (lt, lc, rt, rc),
                'where': QueryParser._parse_where(wh) if wh else None,
                'order_by': QueryParser._parse_order_by(ob) if ob else None,
                'limit': int(lim) if lim else None,
            }

        # regular SELECT
        m = re.match(
            r'SELECT\s+(.+?)\s+FROM\s+(\w+)'
            r'(?:\s+WHERE\s+(.+?))?(?:\s+ORDER\s+BY\s+(.+?))?(?:\s+LIMIT\s+(\d+))?$',
            q, re.IGNORECASE)
        if m:
            cols_s, tbl, wh, ob, lim = m.groups()
            cols = None if cols_s.strip() == '*' else [c.strip() for c in cols_s.split(',')]
            return {
                'type': 'SELECT',
                'columns': cols, 'table': tbl,
                'where': QueryParser._parse_where(wh) if wh else None,
                'order_by': QueryParser._parse_order_by(ob) if ob else None,
                'limit': int(lim) if lim else None,
            }
        raise ValueError("Invalid SELECT syntax")

    @staticmethod
    def _parse_update(q):
        m = re.match(r'UPDATE\s+(\w+)\s+SET\s+(.+?)\s+WHERE\s+(.+)$', q, re.IGNORECASE)
        if m:
            tbl, s, w = m.groups()
            return {'type': 'UPDATE', 'table': tbl,
                    'set': QueryParser._parse_set(s),
                    'where': QueryParser._parse_where(w)}
        raise ValueError("Invalid UPDATE syntax — WHERE clause required")

    @staticmethod
    def _parse_delete(q):
        m = re.match(r'DELETE\s+FROM\s+(\w+)\s+WHERE\s+(.+)$', q, re.IGNORECASE)
        if m:
            tbl, w = m.groups()
            return {'type': 'DELETE', 'table': tbl,
                    'where': QueryParser._parse_where(w)}
        raise ValueError("Invalid DELETE syntax — WHERE clause required")

    # ── clause parsers ───────────────────────────────────────────────────────
    @staticmethod
    def _parse_where(s):
        if not s:
            return None
        conditions = []
        for part in re.split(r'\s+AND\s+', s.strip(), flags=re.IGNORECASE):
            m = re.match(r'(\w+)\s*(=|!=|>=|<=|>|<)\s*(.+)', part.strip())
            if m:
                col, op, val = m.groups()
                conditions.append((col, op, QueryParser._clean_value(val.strip())))
        return conditions or None

    @staticmethod
    def _parse_set(s):
        result = {}
        for part in re.split(r',\s*(?=\w+\s*=)', s.strip()):
            m = re.match(r'(\w+)\s*=\s*(.+)', part.strip())
            if m:
                result[m.group(1)] = QueryParser._clean_value(m.group(2).strip())
        return result

    @staticmethod
    def _parse_order_by(s):
        m = re.match(r'(\w+)\s*(ASC|DESC)?', s.strip(), re.IGNORECASE)
        if m:
            col, d = m.groups()
            return (col, (d or 'ASC').upper())
        return None

    @staticmethod
    def _parse_col_defs(s):
        defs, cur, depth = [], '', 0
        for ch in s:
            if ch == '(':   depth += 1
            elif ch == ')': depth -= 1
            if ch == ',' and depth == 0:
                if cur.strip():
                    defs.append(cur.strip())
                cur = ''
            else:
                cur += ch
        if cur.strip():
            defs.append(cur.strip())

        result = []
        for d in defs:
            parts = d.strip().split(None, 1)
            if parts:
                result.append({'name': parts[0],
                               'definition': parts[1] if len(parts) > 1 else 'TEXT'})
        return result

    @staticmethod
    def _parse_values(s):
        values, cur, in_q, qc = [], '', False, None
        for ch in s:
            if ch in ('"', "'"):
                if not in_q:
                    in_q, qc = True, ch
                elif ch == qc:
                    in_q = False
                continue
            if ch == ',' and not in_q:
                if cur.strip():
                    values.append(QueryParser._clean_value(cur.strip()))
                cur = ''
            else:
                cur += ch
        if cur.strip():
            values.append(QueryParser._clean_value(cur.strip()))
        return values

    @staticmethod
    def _clean_value(v):
        v = v.strip()
        if (v.startswith("'") and v.endswith("'")) or \
           (v.startswith('"') and v.endswith('"')):
            return v[1:-1]
        if v.upper() == 'NULL':
            return None
        try:
            return float(v) if '.' in v else int(v)
        except ValueError:
            return v