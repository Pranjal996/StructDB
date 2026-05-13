"""
database_manager.py
Top-level manager for StructDB: users, databases, query dispatch,
transactions (BEGIN/COMMIT/ROLLBACK), CSV import, and index creation.
"""

import json
import hashlib
import os
import csv
import copy
from datetime import datetime

import database
import query_parser


class DatabaseManager:
    """Manages multiple databases, user accounts, and query execution."""

    def __init__(self, data_dir='structdb_data'):
        self.data_dir         = data_dir
        self.users_file       = os.path.join(data_dir, 'users.json')
        self.databases        = {}
        self.users            = {}
        self.current_user     = None
        self.current_database = None
        self.query_history    = []

        # ── transaction state ────────────────────────────────────────────────
        self._in_transaction  = False
        self._tx_snapshot     = None   # deep copy of DB before BEGIN

        os.makedirs(data_dir, exist_ok=True)
        self.load_users()
        self.load_databases()

    # ══════════════════════════════════════════════════════════════════════════
    #  Auth
    # ══════════════════════════════════════════════════════════════════════════

    def _hash(self, pw):
        return hashlib.sha256(pw.encode()).hexdigest()

    def register_user(self, username, password, role='user'):
        if not username or not password:
            raise ValueError("Username and password required")
        if not username.isalnum():
            raise ValueError("Username must be alphanumeric")
        if username in self.users:
            raise ValueError("Username already exists")
        self.users[username] = {
            'password': self._hash(password), 'role': role,
            'created_at': datetime.now().isoformat(), 'databases': []
        }
        self.save_users()
        return f"User '{username}' registered successfully"

    def login(self, username, password):
        if username not in self.users:
            raise ValueError("Invalid username or password")
        if self.users[username]['password'] != self._hash(password):
            raise ValueError("Invalid username or password")
        self.current_user = username
        self.load_databases()
        return f"Welcome, {username}!"

    def logout(self):
        self.current_user     = None
        self.current_database = None
        self.databases        = {}
        self._in_transaction  = False
        self._tx_snapshot     = None
        return "Logged out successfully"

    # ══════════════════════════════════════════════════════════════════════════
    #  Database management
    # ══════════════════════════════════════════════════════════════════════════

    def _require_user(self):
        if not self.current_user:
            raise ValueError("Please login first")

    def create_database(self, db_name, password=None):
        self._require_user()
        if not db_name or not db_name.isalnum():
            raise ValueError("Database name must be alphanumeric")
        full = f"{self.current_user}_{db_name}"
        if full in self.databases:
            raise ValueError(f"Database '{db_name}' already exists")
        new_db = database.Database(db_name, self.current_user)
        self.databases[full] = {'database': new_db,
                                'password_hash': self._hash(password) if password else None,
                                'owner': self.current_user}
        self.users[self.current_user]['databases'].append(full)
        self.save_database(full)
        self.save_users()
        return f"Database '{db_name}' created successfully"

    def drop_database(self, db_name):
        self._require_user()
        full = f"{self.current_user}_{db_name}"
        if full not in self.users[self.current_user]['databases']:
            raise ValueError(f"Database '{db_name}' does not exist or not owned by you")
        self.databases.pop(full, None)
        self.users[self.current_user]['databases'].remove(full)
        db_file = os.path.join(self.data_dir, f'{full}.json')
        if os.path.exists(db_file):
            os.remove(db_file)
        if self.current_database == full:
            self.current_database = None
        self.save_users()
        return f"Database '{db_name}' dropped successfully"

    def use_database(self, db_name, password=None):
        self._require_user()
        full = f"{self.current_user}_{db_name}"
        if full not in self.users[self.current_user]['databases']:
            raise ValueError(f"Database '{db_name}' does not exist")
        if full not in self.databases:
            self._load_single_database(full)
        info = self.databases[full]
        if info['password_hash']:
            if not password:
                raise ValueError("Database password required")
            if self._hash(password) != info['password_hash']:
                raise ValueError("Incorrect database password")
        self.current_database = full
        return f"Now using database '{db_name}'"

    def get_current_database(self):
        if not self.current_database:
            raise ValueError("No database selected. Run USE database_name first")
        if self.current_database not in self.databases:
            raise ValueError("Current database not loaded. Run USE again")
        return self.databases[self.current_database]['database']

    def list_databases(self):
        if not self.current_user:
            return []
        result = []
        for full in self.users[self.current_user]['databases']:
            if full in self.databases:
                db   = self.databases[full]['database']
                info = self.databases[full]
                result.append({'name': db.name, 'tables': len(db.tables),
                               'created_at': db.created_at,
                               'has_password': info['password_hash'] is not None})
            else:
                name = full.split('_', 1)[1] if '_' in full else full
                result.append({'name': name, 'tables': 'N/A',
                               'created_at': 'N/A', 'has_password': 'N/A',
                               'status': 'Error: Missing file'})
        return result

    # ══════════════════════════════════════════════════════════════════════════
    #  Transaction support
    # ══════════════════════════════════════════════════════════════════════════

    def begin_transaction(self):
        if self._in_transaction:
            raise ValueError("Transaction already active. COMMIT or ROLLBACK first")
        db = self.get_current_database()
        self._tx_snapshot    = copy.deepcopy(db.to_dict())
        self._in_transaction = True
        return "Transaction started. Changes will not be saved until COMMIT."

    def commit_transaction(self):
        if not self._in_transaction:
            raise ValueError("No active transaction")
        self._in_transaction = False
        self._tx_snapshot    = None
        self.save_database(self.current_database)
        return "Transaction committed and saved to disk."

    def rollback_transaction(self):
        if not self._in_transaction:
            raise ValueError("No active transaction")
        # Restore DB from snapshot
        snap = self._tx_snapshot
        restored = database.Database.from_dict(snap)
        self.databases[self.current_database]['database'] = restored
        self._in_transaction = False
        self._tx_snapshot    = None
        return "Transaction rolled back. All changes since BEGIN have been undone."

    # ══════════════════════════════════════════════════════════════════════════
    #  CSV import
    # ══════════════════════════════════════════════════════════════════════════

    def import_from_csv(self, table_name, filepath):
        """
        Import a CSV file as a new table.
        First row is treated as column headers.
        Existing table will be overwritten.
        """
        db = self.get_current_database()

        # Resolve path
        if not os.path.isabs(filepath):
            filepath = os.path.join(self.data_dir, filepath)
        if not os.path.exists(filepath):
            raise ValueError(f"File not found: {filepath}")

        with open(filepath, newline='', encoding='utf-8') as f:
            reader  = csv.DictReader(f)
            rows    = list(reader)
            headers = reader.fieldnames

        if not headers:
            raise ValueError("CSV file has no headers")

        # Drop existing table if present
        if table_name in db.tables:
            db.drop_table(table_name)

        col_defs = [{'name': h, 'definition': 'TEXT'} for h in headers]
        db.create_table(table_name, col_defs)

        for row in rows:
            values = [row.get(h, '') for h in headers]
            try:
                db.insert_record(table_name, values)
            except Exception:
                pass   # skip duplicate PK rows silently

        self.save_database(self.current_database)
        return f"Imported {len(rows)} rows into '{table_name}' from {os.path.basename(filepath)}"

    # ══════════════════════════════════════════════════════════════════════════
    #  Query execution
    # ══════════════════════════════════════════════════════════════════════════

    def execute_query(self, query):
        self._require_user()
        try:
            parsed = query_parser.QueryParser.parse(query)
            self.query_history.append({'query': query,
                                       'timestamp': datetime.now().isoformat()})
            qt = parsed['type']

            # ── transactions ──────────────────────────────────────────────
            if qt == 'BEGIN':     return self.begin_transaction()
            if qt == 'COMMIT':    return self.commit_transaction()
            if qt == 'ROLLBACK':  return self.rollback_transaction()

            # ── EXPLAIN ───────────────────────────────────────────────────
            if qt == 'EXPLAIN':
                db = self.get_current_database()
                return db.explain(parsed['inner'])

            # ── IMPORT ────────────────────────────────────────────────────
            if qt == 'IMPORT':
                return self.import_from_csv(parsed['table'], parsed['file'])

            # ── database level ────────────────────────────────────────────
            if qt == 'CREATE_DATABASE': return self.create_database(parsed['database'])
            if qt == 'DROP_DATABASE':   return self.drop_database(parsed['database'])
            if qt == 'USE_DATABASE':    return self.use_database(parsed['database'])

            if qt == 'SHOW_DATABASES':
                dbs = self.list_databases()
                if not dbs:
                    return "No databases found"
                lines = ["Database Name    | Tables | Protected | Created At"]
                lines.append("-" * 60)
                for d in dbs:
                    prot = 'Yes' if d['has_password'] else 'No'
                    try:
                        dt = datetime.fromisoformat(d['created_at']).strftime('%Y-%m-%d %H:%M')
                    except Exception:
                        dt = str(d['created_at'])
                    status = f" ({d['status']})" if 'status' in d else ''
                    lines.append(f"{d['name']:<17}| {str(d['tables']):<7}| {prot:<10}| {dt}{status}")
                return '\n'.join(lines)

            # ── table level ───────────────────────────────────────────────
            db = self.get_current_database()

            if qt == 'SHOW_TABLES':
                return '\n'.join(db.tables.keys()) if db.tables else "No tables in database"

            if qt == 'DESCRIBE_TABLE':
                tn  = parsed['table']
                if tn not in db.tables:
                    raise ValueError(f"Table '{tn}' does not exist")
                t   = db.tables[tn]
                out = [f"Table: {tn}", "-" * 50,
                       f"Primary Key: {t['primary_key']}",
                       f"Total Records: {len(t['records'])}", "", "Columns:"]
                for cd in t.get('column_definitions', []):
                    pk = " (PK)" if cd['name'] == t['primary_key'] else ""
                    idx = " [B-Tree Index]" if cd['name'] in db.bt_indexes.get(tn, {}) else ""
                    out.append(f"  {cd['name']:<20} {cd['definition']}{pk}{idx}")
                return '\n'.join(out)

            if qt == 'CREATE_TABLE':
                res = db.create_table(parsed['table'], parsed['columns'])
                self._auto_save()
                return res

            if qt == 'DROP_TABLE':
                res = db.drop_table(parsed['table'])
                self._auto_save()
                return res

            if qt == 'CREATE_INDEX':
                res = db.create_index(parsed['table'], parsed['column'])
                self._auto_save()
                return res

            if qt == 'INSERT':
                res = db.insert_record(parsed['table'], parsed['values'])
                self._auto_save()
                return res

            if qt == 'SELECT':
                recs = db.select_records(parsed['table'], parsed['where'],
                                         parsed['order_by'], parsed['limit'])
                if parsed['columns'] and recs:
                    recs = [{c: r.get(c) for c in parsed['columns']} for r in recs]
                return recs

            if qt == 'JOIN_SELECT':
                recs = db.join_tables(parsed['table1'], parsed['table2'],
                                      parsed['join_on'], parsed['where'],
                                      parsed['order_by'], parsed['limit'])
                if parsed['columns'] and recs:
                    recs = [{c: r.get(c) for c in parsed['columns']} for r in recs]
                return recs

            if qt == 'AGGREGATE':
                val = db.get_aggregate(parsed['table'], parsed['function'],
                                       parsed['column'], parsed['where'])
                return f"{parsed['function'].upper()}({parsed['column'] or '*'}): {val}"

            if qt == 'UPDATE':
                res = db.update_records(parsed['table'], parsed['set'], parsed['where'])
                self._auto_save()
                return res

            if qt == 'DELETE':
                res = db.delete_records(parsed['table'], parsed['where'])
                self._auto_save()
                return res

            raise ValueError(f"Unknown query type: {qt}")

        except ValueError as e:
            raise ValueError(f"Query Error: {e}")
        except Exception as e:
            raise RuntimeError(f"Unexpected Error: {e}")

    def _auto_save(self):
        """Save to disk only when NOT inside an open transaction."""
        if not self._in_transaction:
            self.save_database(self.current_database)

    # ══════════════════════════════════════════════════════════════════════════
    #  CSV export
    # ══════════════════════════════════════════════════════════════════════════

    def export_to_csv(self, table_name, filename):
        db = self.get_current_database()
        if table_name not in db.tables:
            raise ValueError(f"Table '{table_name}' does not exist")
        recs = db.select_records(table_name)
        if not recs:
            raise ValueError(f"Table '{table_name}' has no records to export")
        if not filename.lower().endswith('.csv'):
            filename += '.csv'
        filepath = os.path.join(self.data_dir, filename)
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=list(recs[0].keys()))
            writer.writeheader()
            writer.writerows(recs)
        return f"Exported {len(recs)} records to {filepath}"

    # ══════════════════════════════════════════════════════════════════════════
    #  Persistence
    # ══════════════════════════════════════════════════════════════════════════

    def save_database(self, full_name):
        if full_name not in self.databases:
            return
        info    = self.databases[full_name]
        db_file = os.path.join(self.data_dir, f'{full_name}.json')
        try:
            with open(db_file, 'w') as f:
                json.dump({'database': info['database'].to_dict(),
                           'password_hash': info['password_hash'],
                           'owner': info['owner']}, f, indent=2)
        except Exception as e:
            print(f"Error saving database: {e}")

    def _load_single_database(self, full_name):
        db_file = os.path.join(self.data_dir, f'{full_name}.json')
        if not os.path.exists(db_file):
            return
        try:
            with open(db_file) as f:
                data = json.load(f)
            if 'database' in data and 'owner' in data:
                db_obj = database.Database.from_dict(data['database'])
                self.databases[full_name] = {
                    'database':      db_obj,
                    'password_hash': data.get('password_hash'),
                    'owner':         data['owner']
                }
        except Exception as e:
            print(f"Error loading database '{full_name}': {e}")

    def load_databases(self):
        self.databases = {}
        if not self.current_user:
            return
        for full in self.users.get(self.current_user, {}).get('databases', []):
            self._load_single_database(full)

    def save_users(self):
        try:
            with open(self.users_file, 'w') as f:
                json.dump(self.users, f, indent=2)
        except Exception as e:
            print(f"Error saving users: {e}")

    def load_users(self):
        if os.path.exists(self.users_file):
            try:
                with open(self.users_file) as f:
                    self.users = json.load(f)
            except Exception:
                self._create_default_admin()
        else:
            self._create_default_admin()

    def _create_default_admin(self):
        print("Creating default admin user  (username: admin  password: admin123)")
        self.users = {'admin': {'password': self._hash('admin123'), 'role': 'admin',
                                'created_at': datetime.now().isoformat(), 'databases': []}}
        self.save_users()