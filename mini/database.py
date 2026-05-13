"""
database.py
Core Database class for StructDB.
Supports tables, CRUD, aggregates, JOIN, EXPLAIN, and B-Tree secondary indexes.
"""

from datetime import datetime
import data_structures


class Database:
    """A single named database containing tables and indexes."""

    def __init__(self, name, owner):
        self.name       = name
        self.owner      = owner
        self.tables     = {}
        self.indexes    = {}        # primary key hash indexes  {table: HashTable}
        self.bt_indexes = {}        # secondary B-Tree indexes  {table: {col: BTree}}
        self.created_at = datetime.now().isoformat()

    # ══════════════════════════════════════════════════════════════════════════
    #  DDL
    # ══════════════════════════════════════════════════════════════════════════

    def create_table(self, table_name, columns, primary_key=None):
        if table_name in self.tables:
            raise ValueError(f"Table '{table_name}' already exists")

        if columns and isinstance(columns[0], dict):
            col_names = [c['name'] for c in columns]
            col_defs  = columns
        else:
            col_names = columns
            col_defs  = [{'name': c, 'definition': 'TEXT'} for c in columns]

        self.tables[table_name] = {
            'columns':            col_names,
            'column_definitions': col_defs,
            'primary_key':        primary_key or col_names[0],
            'records':            [],
            'created_at':         datetime.now().isoformat(),
        }
        self.indexes[table_name]    = data_structures.HashTable()
        self.bt_indexes[table_name] = {}
        return f"Table '{table_name}' created successfully"

    def drop_table(self, table_name):
        if table_name not in self.tables:
            raise ValueError(f"Table '{table_name}' does not exist")
        del self.tables[table_name]
        del self.indexes[table_name]
        self.bt_indexes.pop(table_name, None)
        return f"Table '{table_name}' dropped successfully"

    def create_index(self, table_name, column):
        """Build a B-Tree secondary index on *column* of *table_name*."""
        if table_name not in self.tables:
            raise ValueError(f"Table '{table_name}' does not exist")
        tbl = self.tables[table_name]
        if column not in tbl['columns']:
            raise ValueError(f"Column '{column}' not found in '{table_name}'")

        bt = data_structures.BTree()
        for rec in tbl['records']:
            val = rec.get(column)
            if val is not None:
                bt.insert(str(val), rec)

        self.bt_indexes.setdefault(table_name, {})[column] = bt
        return f"B-Tree index created on {table_name}({column})"

    # ══════════════════════════════════════════════════════════════════════════
    #  DML
    # ══════════════════════════════════════════════════════════════════════════

    def insert_record(self, table_name, values):
        if table_name not in self.tables:
            raise ValueError(f"Table '{table_name}' does not exist")
        tbl     = self.tables[table_name]
        columns = tbl['columns']
        if len(values) != len(columns):
            raise ValueError(f"Expected {len(columns)} values, got {len(values)}")

        record = dict(zip(columns, values))
        record['_created_at'] = datetime.now().isoformat()
        record['_updated_at'] = datetime.now().isoformat()

        pk_col = tbl['primary_key']
        pk_val = record[pk_col]
        if self.indexes[table_name].get(pk_val):
            raise ValueError(f"Duplicate primary key: {pk_val}")

        tbl['records'].append(record)
        self.indexes[table_name].insert(pk_val, record)

        # keep any existing B-Tree indexes up to date
        for col, bt in self.bt_indexes.get(table_name, {}).items():
            val = record.get(col)
            if val is not None:
                bt.insert(str(val), record)

        return "Record inserted successfully"

    def select_records(self, table_name, where_clause=None, order_by=None, limit=None):
        if table_name not in self.tables:
            raise ValueError(f"Table '{table_name}' does not exist")
        records = self.tables[table_name]['records'][:]
        if where_clause:
            records = [r for r in records if self._eval_where(r, where_clause)]
        if order_by:
            col, direction = order_by
            records = sorted(records, key=lambda x: x.get(col, ''),
                             reverse=(direction == 'DESC'))
        if limit:
            records = records[:limit]
        return records

    def update_records(self, table_name, set_clause, where_clause):
        if table_name not in self.tables:
            raise ValueError(f"Table '{table_name}' does not exist")
        count = 0
        for rec in self.tables[table_name]['records']:
            if self._eval_where(rec, where_clause):
                for col, val in set_clause.items():
                    rec[col] = val
                rec['_updated_at'] = datetime.now().isoformat()
                count += 1
        return f"{count} record(s) updated"

    def delete_records(self, table_name, where_clause):
        if table_name not in self.tables:
            raise ValueError(f"Table '{table_name}' does not exist")
        records   = self.tables[table_name]['records']
        to_delete = [r for r in records if self._eval_where(r, where_clause)]
        for rec in to_delete:
            records.remove(rec)
            self.indexes[table_name].delete(rec[self.tables[table_name]['primary_key']])
        return f"{len(to_delete)} record(s) deleted"

    # ── aggregates ───────────────────────────────────────────────────────────

    def get_aggregate(self, table_name, function, column, where_clause=None):
        records = self.select_records(table_name, where_clause)
        if not records:
            return 0
        fn = function.upper()
        if fn == 'COUNT':
            return len(records)
        values = [self._to_num(r.get(column, 0)) for r in records]
        if fn == 'SUM':   return sum(values)
        if fn == 'AVG':   return sum(values) / len(values)
        if fn == 'MIN':   return min(values)
        if fn == 'MAX':   return max(values)
        return None

    # ── JOIN ─────────────────────────────────────────────────────────────────

    def join_tables(self, t1, t2, join_on, where_clause=None, order_by=None, limit=None):
        """
        Nested-loop inner join.
        join_on = (left_table, left_col, right_table, right_col)
        """
        if t1 not in self.tables:
            raise ValueError(f"Table '{t1}' does not exist")
        if t2 not in self.tables:
            raise ValueError(f"Table '{t2}' does not exist")

        lt, lc, rt, rc = join_on
        recs1 = self.tables[t1]['records']
        recs2 = self.tables[t2]['records']

        merged = []
        for r1 in recs1:
            for r2 in recs2:
                if str(r1.get(lc)) == str(r2.get(rc)):
                    combined = {}
                    for k, v in r1.items():
                        combined[f"{t1}.{k}"] = v
                    for k, v in r2.items():
                        combined[f"{t2}.{k}"] = v
                    merged.append(combined)

        if where_clause:
            merged = [r for r in merged if self._eval_where(r, where_clause)]
        if order_by:
            col, direction = order_by
            merged = sorted(merged, key=lambda x: x.get(col, ''),
                            reverse=(direction == 'DESC'))
        if limit:
            merged = merged[:limit]
        return merged

    # ── EXPLAIN ──────────────────────────────────────────────────────────────

    def explain(self, parsed):
        """Return a human-readable query execution plan."""
        lines = ["╔══════════════════════════════════════════════╗",
                 "║         QUERY EXECUTION PLAN (EXPLAIN)       ║",
                 "╚══════════════════════════════════════════════╝", ""]
        qtype = parsed.get('type', '?')

        if qtype in ('SELECT', 'JOIN_SELECT'):
            tbl = parsed.get('table') or parsed.get('table1')
            n   = len(self.tables.get(tbl, {}).get('records', []))
            where = parsed.get('where')

            if qtype == 'JOIN_SELECT':
                t2  = parsed.get('table2')
                n2  = len(self.tables.get(t2, {}).get('records', []))
                lines += [
                    f"  Step 1 │ Full Table Scan  → {tbl} ({n} rows)",
                    f"  Step 2 │ Full Table Scan  → {t2} ({n2} rows)",
                    f"  Step 3 │ Nested-Loop JOIN  on {parsed['join_on'][1]} = {parsed['join_on'][3]}",
                    f"          │ Complexity: O(n×m) = O({n}×{n2}) = O({n*n2})",
                ]
            else:
                bt_cols = list(self.bt_indexes.get(tbl, {}).keys())
                if where and bt_cols:
                    used = [c for c, _, _ in where if c in bt_cols]
                    if used:
                        lines += [
                            f"  Step 1 │ B-Tree Index Scan on {tbl}({used[0]})",
                            f"          │ Complexity: O(log {n}) ≈ O({max(1, n.bit_length())})",
                        ]
                    else:
                        lines += [f"  Step 1 │ Full Table Scan on {tbl} ({n} rows)",
                                  f"          │ Complexity: O({n})"]
                else:
                    lines += [f"  Step 1 │ Full Table Scan on {tbl} ({n} rows)",
                              f"          │ No usable index — consider CREATE INDEX ON {tbl}(...)"]

            if where:
                lines.append(f"  Step ? │ Apply WHERE filter ({len(where)} condition(s))")
            if parsed.get('order_by'):
                lines.append(f"  Step ? │ Sort by {parsed['order_by'][0]} {parsed['order_by'][1]}"
                             f" — O(n log n)")
            if parsed.get('limit'):
                lines.append(f"  Step ? │ LIMIT {parsed['limit']} rows")

        elif qtype == 'INSERT':
            tbl = parsed.get('table', '?')
            lines += [f"  Step 1 │ Validate column count",
                      f"  Step 2 │ Check duplicate primary key via HashTable — O(1)",
                      f"  Step 3 │ Append to records list",
                      f"  Step 4 │ Update HashTable index — O(1)",
                      f"  Step 5 │ Update any B-Tree indexes — O(log n)"]

        elif qtype == 'UPDATE':
            tbl = parsed.get('table', '?')
            n   = len(self.tables.get(tbl, {}).get('records', []))
            lines += [f"  Step 1 │ Full Table Scan on {tbl} ({n} rows)",
                      f"  Step 2 │ Apply WHERE, mutate matching records",
                      f"  Step 3 │ Update _updated_at timestamps"]

        elif qtype == 'DELETE':
            tbl = parsed.get('table', '?')
            n   = len(self.tables.get(tbl, {}).get('records', []))
            lines += [f"  Step 1 │ Full Table Scan on {tbl} ({n} rows)",
                      f"  Step 2 │ Collect matching records",
                      f"  Step 3 │ Remove from list + HashTable index — O(1) per delete"]

        elif qtype == 'AGGREGATE':
            tbl = parsed.get('table', '?')
            fn  = parsed.get('function', '?')
            col = parsed.get('column') or '*'
            n   = len(self.tables.get(tbl, {}).get('records', []))
            lines += [f"  Step 1 │ Full Table Scan on {tbl} ({n} rows)",
                      f"  Step 2 │ Compute {fn}({col}) — O({n})"]
        else:
            lines.append(f"  No detailed plan available for {qtype}")

        lines.append("")
        lines.append("  Legend: O(1) = constant | O(log n) = B-Tree | O(n) = linear scan")
        return '\n'.join(lines)

    # ══════════════════════════════════════════════════════════════════════════
    #  Helpers
    # ══════════════════════════════════════════════════════════════════════════

    def _eval_where(self, record, where_clause):
        for col, op, val in where_clause:
            rv = record.get(col)
            rv_s, val_s = str(rv), str(val)
            rv_n, val_n = self._to_num(rv), self._to_num(val)
            if op == '='  and rv_s != val_s:           return False
            if op == '!=' and rv_s == val_s:           return False
            if op == '>'  and not (rv_n  > val_n):    return False
            if op == '<'  and not (rv_n  < val_n):    return False
            if op == '>=' and not (rv_n >= val_n):    return False
            if op == '<=' and not (rv_n <= val_n):    return False
        return True

    @staticmethod
    def _to_num(v):
        try:
            return float(v)
        except (ValueError, TypeError):
            return str(v)

    # ══════════════════════════════════════════════════════════════════════════
    #  Serialization
    # ══════════════════════════════════════════════════════════════════════════

    def to_dict(self):
        return {'name': self.name, 'owner': self.owner,
                'tables': self.tables, 'created_at': self.created_at}

    @staticmethod
    def from_dict(data):
        db = Database(data['name'], data['owner'])
        db.tables     = data.get('tables', {})
        db.created_at = data.get('created_at', datetime.now().isoformat())
        for tname, tdata in db.tables.items():
            if 'column_definitions' not in tdata:
                tdata['column_definitions'] = [
                    {'name': c, 'definition': 'TEXT'} for c in tdata.get('columns', [])]
            db.indexes[tname]    = data_structures.HashTable()
            db.bt_indexes[tname] = {}
            for rec in tdata['records']:
                pk = rec[tdata['primary_key']]
                db.indexes[tname].insert(pk, rec)
        return db