"""
Curavit — Medicine Tracker Server
Production-grade Flask REST API with SQLite persistence, transaction safety,
granular caregiver access control, patient care teams, secure authentication,
idempotent scheduling, safe dose corrections, audit trails, and data recovery.
"""

import sys
import os
import json
import re
import sqlite3
import shutil
import hashlib
import secrets
from datetime import datetime, timedelta
from functools import wraps
from contextlib import contextmanager
from flask import Flask, render_template, request, jsonify, g
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash

# Configure UTF-8 encoding on Windows consoles
if sys.platform == 'win32':
    try:
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8')
        if hasattr(sys.stderr, 'reconfigure'):
            sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Initialize Flask application
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'curavit-healthcare-secret-key-development-only-2026')

# Security & CORS configuration
DEFAULT_ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5174",
    "http://localhost:5000",
    "http://127.0.0.1:5000",
]
custom_origins = os.environ.get("ALLOWED_ORIGINS")
allowed_origins = [o.strip() for o in custom_origins.split(",")] if custom_origins else DEFAULT_ALLOWED_ORIGINS
CORS(app, resources={r"/api/*": {"origins": allowed_origins}}, supports_credentials=True)

# Validation constants
EMAIL_REGEX = re.compile(r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$')
TIME_REGEX = re.compile(r'^([01]\d|2[0-3]):([0-5]\d)$')
DATE_REGEX = re.compile(r'^\d{4}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])$')
VALID_FREQUENCIES = {'daily', 'weekly', 'as_needed'}
VALID_STATUSES = {'pending', 'taken', 'skipped', 'missed'}
VALID_ROLES = {'patient', 'caregiver', 'both'}
VALID_CAREGIVER_PERMISSIONS = {
    'view_medicines',
    'view_schedule',
    'view_history',
    'view_adherence',
    'record_doses',
    'correct_doses',
}
DEFAULT_CAREGIVER_PERMISSIONS = ['view_medicines', 'view_schedule']
MAX_NAME_LEN = 120
MAX_DOSAGE_LEN = 60
MAX_TEXT_LEN = 500


class DatabaseManager:
    def __init__(self, db_path=None):
        self._db_path = db_path

    @property
    def db_path(self):
        if self._db_path:
            return self._db_path
        return os.environ.get('MEDICINE_DB_PATH', 'medicines.db')

    def set_db_path(self, path):
        self._db_path = path

    def get_raw_connection(self):
        conn = sqlite3.connect(self.db_path, timeout=10.0, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA journal_mode = WAL;')
        conn.execute('PRAGMA busy_timeout = 5000;')
        conn.execute('PRAGMA foreign_keys = ON;')
        return conn

    @contextmanager
    def get_connection(self):
        """Context manager providing automatic transaction commit and rollback."""
        conn = self.get_raw_connection()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def init_db(self):
        """Idempotent database initialization and schema migration."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # 1. Users table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    email TEXT UNIQUE NOT NULL COLLATE NOCASE,
                    password_hash TEXT NOT NULL,
                    role TEXT DEFAULT 'patient',
                    status TEXT DEFAULT 'active',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # 2. Sessions table (for server-managed tokens)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    token_hash TEXT UNIQUE NOT NULL,
                    user_id INTEGER NOT NULL,
                    expires_at TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )
            ''')

            # 3. Medicines table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS medicines (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    name TEXT NOT NULL,
                    dosage TEXT NOT NULL,
                    times_per_day INTEGER DEFAULT 1,
                    schedule TEXT NOT NULL,
                    start_date TEXT NOT NULL,
                    end_date TEXT,
                    frequency TEXT DEFAULT 'daily',
                    instructions TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    is_active BOOLEAN DEFAULT 1,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )
            ''')

            # Backward-compatible check for user_id in medicines
            cursor.execute("PRAGMA table_info(medicines)")
            med_cols = [col[1] for col in cursor.fetchall()]
            if 'user_id' not in med_cols:
                cursor.execute("ALTER TABLE medicines ADD COLUMN user_id INTEGER")

            # 4. Logs table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    medicine_id INTEGER,
                    medicine_name TEXT NOT NULL,
                    dosage TEXT NOT NULL,
                    scheduled_time TEXT,
                    taken_time TEXT,
                    status TEXT DEFAULT 'pending',
                    notes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )
            ''')

            # Backward-compatible checks for logs columns
            cursor.execute("PRAGMA table_info(logs)")
            log_cols = [col[1] for col in cursor.fetchall()]
            if 'updated_at' not in log_cols:
                cursor.execute("ALTER TABLE logs ADD COLUMN updated_at TEXT")
                cursor.execute("UPDATE logs SET updated_at = COALESCE(created_at, CURRENT_TIMESTAMP)")
            if 'user_id' not in log_cols:
                cursor.execute("ALTER TABLE logs ADD COLUMN user_id INTEGER")

            # 5. Dose Audit Logs table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS dose_audit_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    log_id INTEGER NOT NULL,
                    patient_id INTEGER,
                    actor_id INTEGER,
                    actor_name TEXT,
                    actor_role TEXT,
                    action TEXT NOT NULL,
                    previous_status TEXT,
                    new_status TEXT,
                    reason TEXT,
                    timestamp TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            cursor.execute("PRAGMA table_info(dose_audit_logs)")
            audit_cols = [col[1] for col in cursor.fetchall()]
            for col_name, col_type in [
                ('patient_id', 'INTEGER'),
                ('actor_id', 'INTEGER'),
                ('actor_name', 'TEXT'),
                ('actor_role', 'TEXT')
            ]:
                if col_name not in audit_cols:
                    cursor.execute(f"ALTER TABLE dose_audit_logs ADD COLUMN {col_name} {col_type}")

            # 6. Caregiver Relationships table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS caregiver_relationships (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    patient_id INTEGER NOT NULL,
                    caregiver_id INTEGER NOT NULL,
                    status TEXT DEFAULT 'active',
                    permissions TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    accepted_at TEXT,
                    revoked_at TEXT,
                    FOREIGN KEY (patient_id) REFERENCES users(id) ON DELETE CASCADE,
                    FOREIGN KEY (caregiver_id) REFERENCES users(id) ON DELETE CASCADE,
                    UNIQUE(patient_id, caregiver_id)
                )
            ''')

            # 7. Caregiver Invitations table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS caregiver_invitations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    patient_id INTEGER NOT NULL,
                    invited_email TEXT NOT NULL COLLATE NOCASE,
                    token_hash TEXT UNIQUE NOT NULL,
                    raw_token TEXT,
                    permissions TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    expires_at TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    accepted_at TEXT,
                    FOREIGN KEY (patient_id) REFERENCES users(id) ON DELETE CASCADE
                )
            ''')

            # 8. Caregiver Activity Logs table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS caregiver_activity_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    patient_id INTEGER NOT NULL,
                    actor_id INTEGER NOT NULL,
                    actor_name TEXT NOT NULL,
                    actor_role TEXT NOT NULL,
                    action TEXT NOT NULL,
                    details TEXT,
                    timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (patient_id) REFERENCES users(id) ON DELETE CASCADE,
                    FOREIGN KEY (actor_id) REFERENCES users(id) ON DELETE CASCADE
                )
            ''')

            # 9. Settings table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS settings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    key TEXT NOT NULL,
                    value TEXT NOT NULL,
                    UNIQUE(user_id, key)
                )
            ''')

            # Backward-compatible check for user_id in settings
            cursor.execute("PRAGMA table_info(settings)")
            settings_cols = [col[1] for col in cursor.fetchall()]
            if 'user_id' not in settings_cols:
                cursor.execute("ALTER TABLE settings ADD COLUMN user_id INTEGER")

            # Default global settings
            cursor.execute('''
                INSERT OR IGNORE INTO settings (user_id, key, value) 
                VALUES 
                (NULL, 'notifications_enabled', 'true'),
                (NULL, 'snooze_duration', '10'),
                (NULL, 'language', 'en'),
                (NULL, 'reminder_lead_time', '5'),
                (NULL, 'theme', 'light')
            ''')

            # 10. Performance & Constraint Indexes
            cursor.execute('''
                CREATE UNIQUE INDEX IF NOT EXISTS idx_logs_med_sched 
                ON logs(medicine_id, scheduled_time) 
                WHERE medicine_id IS NOT NULL AND scheduled_time IS NOT NULL;
            ''')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_logs_sched_time ON logs(scheduled_time);')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_logs_user_id ON logs(user_id);')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_meds_user_id ON medicines(user_id);')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_audit_log_id ON dose_audit_logs(log_id);')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_sessions_token ON sessions(token_hash);')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_caregiver_patient ON caregiver_relationships(patient_id);')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_caregiver_user ON caregiver_relationships(caregiver_id);')

        print("Database schema verified and initialized.")


db_manager = DatabaseManager()


# -----------------------------------------------------------------------------
# Authentication & Authorization Helpers
# -----------------------------------------------------------------------------

def hash_token(raw_token):
    return hashlib.sha256(raw_token.encode('utf-8')).hexdigest()


def get_auth_token():
    auth_header = request.headers.get('Authorization', '')
    if auth_header.startswith('Bearer '):
        return auth_header[7:].strip()
    return request.cookies.get('curavit_session')


def require_auth(f):
    """Protects endpoints by validating the bearer token or session cookie."""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = get_auth_token()
        if not token:
            return jsonify({'status': 'error', 'message': 'Authentication required', 'code': 'UNAUTHORIZED'}), 401

        token_h = hash_token(token)
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT u.id, u.name, u.email, u.role, u.status, s.expires_at
                FROM sessions s
                JOIN users u ON s.user_id = u.id
                WHERE s.token_hash = ? AND s.expires_at > ?
            ''', (token_h, now_str))
            user = cursor.fetchone()

            if not user or user['status'] != 'active':
                return jsonify({'status': 'error', 'message': 'Session expired or invalid', 'code': 'UNAUTHORIZED'}), 401

            g.current_user = dict(user)
            g.current_token = token

        return f(*args, **kwargs)
    return decorated


def resolve_patient_context(req_patient_id=None, required_permission=None):
    """
    Resolves patient data ownership and validates caregiver authorization.
    Returns: (target_patient_id, relationship_dict_or_none, error_response_tuple_or_none)
    """
    user_id = g.current_user['id']

    # If no patient_id specified or matches current user, caller is the patient
    if req_patient_id is None or str(req_patient_id).strip() == '' or int(req_patient_id) == user_id:
        return user_id, None, None

    target_id = int(req_patient_id)

    # Caller is a caregiver requesting another patient's data
    with db_manager.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM caregiver_relationships 
            WHERE patient_id = ? AND caregiver_id = ? AND status = 'active'
        ''', (target_id, user_id))
        rel = cursor.fetchone()

        if not rel:
            return None, None, (jsonify({
                'status': 'error',
                'message': 'Access denied: You are not an active authorized caregiver for this patient',
                'code': 'FORBIDDEN'
            }), 403)

        rel_dict = dict(rel)
        try:
            permissions = json.loads(rel_dict['permissions']) if rel_dict['permissions'] else []
        except Exception:
            permissions = []
        rel_dict['permissions_list'] = permissions

        if required_permission and required_permission not in permissions:
            return None, None, (jsonify({
                'status': 'error',
                'message': f'Access denied: You do not have the required "{required_permission}" permission for this patient',
                'code': 'INSUFFICIENT_PERMISSIONS'
            }), 403)

        return target_id, rel_dict, None


# -----------------------------------------------------------------------------
# Scheduling & Synchronization Engine
# -----------------------------------------------------------------------------

def normalize_time_str(time_str):
    if not time_str:
        return ""
    parts = time_str.strip().split(':')
    if len(parts) >= 2:
        return f"{int(parts[0]):02d}:{int(parts[1]):02d}"
    return time_str.strip()


def sync_daily_schedules(target_date_str=None, patient_id=None, conn=None):
    """
    Idempotently generates dose records for active medicines on target_date_str.
    Supports single patient or all active patients.
    """
    if not target_date_str:
        target_date_str = datetime.now().strftime('%Y-%m-%d')

    try:
        target_date = datetime.strptime(target_date_str, '%Y-%m-%d').date()
    except ValueError:
        return

    target_weekday = target_date.weekday()

    def _sync(c):
        cursor = c.cursor()
        query = 'SELECT id, user_id, name, dosage, schedule, start_date, end_date, frequency FROM medicines WHERE is_active = 1'
        params = []
        if patient_id is not None:
            query += ' AND (user_id = ? OR user_id IS NULL)'
            params.append(patient_id)

        cursor.execute(query, params)
        active_medicines = cursor.fetchall()

        for med in active_medicines:
            med_id = med['id']
            med_user_id = med['user_id']
            name = med['name']
            dosage = med['dosage']
            schedule_json = med['schedule']
            start_str = med['start_date']
            end_str = med['end_date']
            freq = (med['frequency'] or 'daily').lower().strip()

            if start_str:
                try:
                    start_date = datetime.strptime(start_str, '%Y-%m-%d').date()
                    if target_date < start_date:
                        continue
                except ValueError:
                    continue

            if end_str:
                try:
                    end_date = datetime.strptime(end_str, '%Y-%m-%d').date()
                    if target_date > end_date:
                        continue
                except ValueError:
                    pass

            if freq == 'as_needed':
                continue
            elif freq == 'weekly':
                try:
                    start_date = datetime.strptime(start_str, '%Y-%m-%d').date()
                    if target_weekday != start_date.weekday():
                        continue
                except Exception:
                    continue

            try:
                time_slots = json.loads(schedule_json) if schedule_json else []
            except Exception:
                time_slots = []

            for slot in time_slots:
                slot_clean = normalize_time_str(slot)
                if not slot_clean:
                    continue
                scheduled_timestamp = f"{target_date_str} {slot_clean}"

                cursor.execute('''
                    INSERT OR IGNORE INTO logs 
                        (user_id, medicine_id, medicine_name, dosage, scheduled_time, status, created_at, updated_at)
                    VALUES 
                        (?, ?, ?, ?, ?, 'pending', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ''', (med_user_id, med_id, name, dosage, scheduled_timestamp))

    if conn is not None:
        _sync(conn)
    else:
        with db_manager.get_connection() as c:
            _sync(c)


# -----------------------------------------------------------------------------
# Input Validation Helpers
# -----------------------------------------------------------------------------

def validate_medicine_payload(data, is_update=False):
    if not isinstance(data, dict):
        return None, "Invalid JSON object"

    name = str(data.get('name', '')).strip()
    dosage = str(data.get('dosage', '')).strip()

    if not is_update or 'name' in data:
        if not name:
            return None, "Medicine name is required"
        if len(name) > MAX_NAME_LEN:
            return None, f"Medicine name cannot exceed {MAX_NAME_LEN} characters"

    if not is_update or 'dosage' in data:
        if not dosage:
            return None, "Dosage is required"
        if len(dosage) > MAX_DOSAGE_LEN:
            return None, f"Dosage cannot exceed {MAX_DOSAGE_LEN} characters"

    times_per_day = data.get('times_per_day', 1)
    try:
        times_per_day = int(times_per_day)
        if not (1 <= times_per_day <= 6):
            return None, "times_per_day must be an integer between 1 and 6"
    except (ValueError, TypeError):
        return None, "times_per_day must be an integer"

    frequency = str(data.get('frequency', 'daily')).strip().lower()
    if frequency not in VALID_FREQUENCIES:
        frequency = 'daily'

    schedule = data.get('schedule', [])
    if frequency != 'as_needed':
        if not isinstance(schedule, list):
            return None, "schedule must be a list of time strings"
        if len(schedule) != times_per_day:
            return None, f"Expected {times_per_day} schedule time slot(s), got {len(schedule)}"
        cleaned_schedule = []
        for slot in schedule:
            slot_str = normalize_time_str(str(slot))
            if not TIME_REGEX.match(slot_str):
                return None, f"Invalid time format '{slot}'. Use 24-hour HH:MM format (e.g. 08:30)"
            cleaned_schedule.append(slot_str)
        schedule = cleaned_schedule
    else:
        schedule = ['12:00']

    start_date = str(data.get('start_date', '')).strip()
    if not is_update or 'start_date' in data:
        if not start_date or not DATE_REGEX.match(start_date):
            return None, "start_date must be in YYYY-MM-DD format"

    end_date = str(data.get('end_date', '')).strip()
    if end_date:
        if not DATE_REGEX.match(end_date):
            return None, "end_date must be in YYYY-MM-DD format"
        if start_date and end_date < start_date:
            return None, "end_date cannot be earlier than start_date"

    instructions = str(data.get('instructions', '')).strip()
    if len(instructions) > MAX_TEXT_LEN:
        return None, f"Instructions cannot exceed {MAX_TEXT_LEN} characters"

    return {
        'name': name,
        'dosage': dosage,
        'times_per_day': times_per_day,
        'schedule': schedule,
        'start_date': start_date,
        'end_date': end_date,
        'frequency': frequency,
        'instructions': instructions
    }, None


# -----------------------------------------------------------------------------
# Authentication Routes
# -----------------------------------------------------------------------------

@app.route('/api/auth/setup-status')
def get_setup_status():
    """Checks whether the system has users and whether unassigned legacy data exists."""
    try:
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM users')
            user_count = cursor.fetchone()[0]

            cursor.execute('SELECT COUNT(*) FROM medicines WHERE user_id IS NULL')
            legacy_meds = cursor.fetchone()[0]

            cursor.execute('SELECT COUNT(*) FROM logs WHERE user_id IS NULL')
            legacy_logs = cursor.fetchone()[0]

        return jsonify({
            'has_users': user_count > 0,
            'user_count': user_count,
            'has_legacy_data': (legacy_meds > 0 or legacy_logs > 0),
            'has_legacy_records': (legacy_meds > 0 or legacy_logs > 0),
            'legacy_medicines_count': legacy_meds,
            'legacy_logs_count': legacy_logs
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': 'Unable to check system setup status'}), 500


@app.route('/api/auth/register', methods=['POST'])
def register():
    try:
        data = request.get_json(force=True, silent=True)
        if not isinstance(data, dict):
            return jsonify({'status': 'error', 'message': 'Invalid JSON body'}), 400

        name = str(data.get('name', '')).strip()
        email = str(data.get('email', '')).strip().lower()
        password = str(data.get('password', ''))
        role = str(data.get('role', 'patient')).strip().lower()
        claim_legacy = bool(data.get('claim_legacy', False))

        if not name or len(name) > MAX_NAME_LEN:
            return jsonify({'status': 'error', 'message': 'Name is required (max 120 characters)'}), 400

        if not email or not EMAIL_REGEX.match(email):
            return jsonify({'status': 'error', 'message': 'A valid email address is required'}), 400

        if len(password) < 8:
            return jsonify({'status': 'error', 'message': 'Password must be at least 8 characters long'}), 400

        if role not in VALID_ROLES:
            role = 'patient'

        password_hash = generate_password_hash(password, method='pbkdf2:sha256:600000')

        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT id FROM users WHERE email = ?', (email,))
            if cursor.fetchone():
                return jsonify({'status': 'error', 'message': 'An account with this email already exists'}), 409

            cursor.execute('''
                INSERT INTO users (name, email, password_hash, role, status)
                VALUES (?, ?, ?, ?, 'active')
            ''', (name, email, password_hash, role))
            user_id = cursor.lastrowid

            # Safe migration of legacy records if requested
            if claim_legacy:
                cursor.execute('UPDATE medicines SET user_id = ? WHERE user_id IS NULL', (user_id,))
                cursor.execute('UPDATE logs SET user_id = ? WHERE user_id IS NULL', (user_id,))
                cursor.execute('UPDATE settings SET user_id = ? WHERE user_id IS NULL', (user_id,))
                cursor.execute('UPDATE dose_audit_logs SET patient_id = ? WHERE patient_id IS NULL', (user_id,))

            # Issue secure session token
            raw_token = secrets.token_hex(32)
            token_h = hash_token(raw_token)
            expires_at = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S')

            cursor.execute('''
                INSERT INTO sessions (token_hash, user_id, expires_at)
                VALUES (?, ?, ?)
            ''', (token_h, user_id, expires_at))

        return jsonify({
            'status': 'success',
            'message': 'Account created successfully',
            'token': raw_token,
            'user': {
                'id': user_id,
                'name': name,
                'email': email,
                'role': role
            }
        }), 201

    except Exception as e:
        return jsonify({'status': 'error', 'message': 'Registration failed'}), 500


@app.route('/api/auth/login', methods=['POST'])
def login():
    try:
        data = request.get_json(force=True, silent=True)
        if not isinstance(data, dict):
            return jsonify({'status': 'error', 'message': 'Invalid JSON body'}), 400

        email = str(data.get('email', '')).strip().lower()
        password = str(data.get('password', ''))

        if not email or not password:
            return jsonify({'status': 'error', 'message': 'Email and password are required'}), 400

        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM users WHERE email = ?', (email,))
            user = cursor.fetchone()

            if not user or not check_password_hash(user['password_hash'], password):
                return jsonify({'status': 'error', 'message': 'Invalid email or password'}), 401

            if user['status'] != 'active':
                return jsonify({'status': 'error', 'message': 'Account has been deactivated'}), 403

            raw_token = secrets.token_hex(32)
            token_h = hash_token(raw_token)
            expires_at = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S')

            cursor.execute('''
                INSERT INTO sessions (token_hash, user_id, expires_at)
                VALUES (?, ?, ?)
            ''', (token_h, user['id'], expires_at))

        return jsonify({
            'status': 'success',
            'message': 'Login successful',
            'token': raw_token,
            'user': {
                'id': user['id'],
                'name': user['name'],
                'email': user['email'],
                'role': user['role']
            }
        })

    except Exception as e:
        return jsonify({'status': 'error', 'message': 'Login failed'}), 500


@app.route('/api/auth/logout', methods=['POST'])
@require_auth
def logout():
    try:
        token_h = hash_token(g.current_token)
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM sessions WHERE token_hash = ?', (token_h,))
        return jsonify({'status': 'success', 'message': 'Logged out successfully'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': 'Logout failed'}), 500


@app.route('/api/auth/me')
@require_auth
def get_current_user():
    return jsonify({
        'status': 'success',
        'user': {
            'id': g.current_user['id'],
            'name': g.current_user['name'],
            'email': g.current_user['email'],
            'role': g.current_user['role']
        }
    })


@app.route('/api/auth/claim-legacy', methods=['POST'])
@require_auth
def claim_legacy_records():
    """Allows an authenticated patient to safely claim unassigned local records."""
    try:
        user_id = g.current_user['id']
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute('SELECT COUNT(*) FROM medicines WHERE user_id IS NULL')
            unassigned_meds = cursor.fetchone()[0]

            cursor.execute('UPDATE medicines SET user_id = ? WHERE user_id IS NULL', (user_id,))
            cursor.execute('UPDATE logs SET user_id = ? WHERE user_id IS NULL', (user_id,))
            cursor.execute('UPDATE settings SET user_id = ? WHERE user_id IS NULL', (user_id,))
            cursor.execute('UPDATE dose_audit_logs SET patient_id = ? WHERE patient_id IS NULL', (user_id,))

        return jsonify({
            'status': 'success',
            'message': f'Successfully claimed {unassigned_meds} local medication records',
            'claimed_count': unassigned_meds
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': 'Failed to claim local records'}), 500


# -----------------------------------------------------------------------------
# Caregiver Team & Invitation Management Endpoints (Patient Perspective)
# -----------------------------------------------------------------------------

@app.route('/api/caregiver-team')
@require_auth
def get_caregiver_team():
    """Returns active caregivers, pending invitations, and recent team activity for patient."""
    patient_id = g.current_user['id']
    try:
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()

            # Active caregivers
            cursor.execute('''
                SELECT r.id as relationship_id, r.caregiver_id, u.name as caregiver_name, 
                       u.email as caregiver_email, r.permissions, r.status, r.created_at, r.accepted_at
                FROM caregiver_relationships r
                JOIN users u ON r.caregiver_id = u.id
                WHERE r.patient_id = ? AND r.status = 'active'
                ORDER BY r.accepted_at DESC
            ''', (patient_id,))
            active_caregivers = []
            for row in cursor.fetchall():
                try:
                    perms = json.loads(row['permissions']) if row['permissions'] else []
                except Exception:
                    perms = []
                active_caregivers.append({
                    'id': row['relationship_id'],
                    'relationship_id': row['relationship_id'],
                    'caregiver_id': row['caregiver_id'],
                    'name': row['caregiver_name'],
                    'caregiver_name': row['caregiver_name'],
                    'caregiver_email': row['caregiver_email'],
                    'permissions': perms,
                    'status': row['status'],
                    'created_at': row['created_at'],
                    'accepted_at': row['accepted_at']
                })

            # Pending and historical invitations
            now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute('''
                SELECT id, invited_email, permissions, status, expires_at, created_at, raw_token
                FROM caregiver_invitations
                WHERE patient_id = ?
                ORDER BY id DESC
            ''', (patient_id,))
            invitations = []
            for row in cursor.fetchall():
                try:
                    perms = json.loads(row['permissions']) if row['permissions'] else []
                except Exception:
                    perms = []
                inv_status = row['status']
                if inv_status == 'pending' and row['expires_at'] < now_str:
                    inv_status = 'expired'

                invitations.append({
                    'id': row['id'],
                    'invited_email': row['invited_email'],
                    'permissions': perms,
                    'status': inv_status,
                    'expires_at': row['expires_at'],
                    'created_at': row['created_at'],
                    'invite_token': row['raw_token'] if inv_status == 'pending' else None
                })

            # Recent activity logs
            cursor.execute('''
                SELECT id, actor_name, actor_role, action, details, timestamp
                FROM caregiver_activity_logs
                WHERE patient_id = ?
                ORDER BY id DESC LIMIT 20
            ''', (patient_id,))
            activity_logs = [dict(row) for row in cursor.fetchall()]

        return jsonify({
            'status': 'success',
            'caregivers': active_caregivers,
            'invitations': invitations,
            'recent_activity': activity_logs
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': 'Failed to retrieve care team'}), 500


@app.route('/api/caregiver-team/invite', methods=['POST'])
@require_auth
def invite_caregiver():
    """Generates a secure, cryptographically random, expiring caregiver invitation."""
    patient_id = g.current_user['id']
    try:
        data = request.get_json(force=True, silent=True)
        if not isinstance(data, dict):
            return jsonify({'status': 'error', 'message': 'Invalid JSON body'}), 400

        invited_email = str(data.get('invited_email') or data.get('email') or '').strip().lower()
        permissions = data.get('permissions', DEFAULT_CAREGIVER_PERMISSIONS)

        if not invited_email or not EMAIL_REGEX.match(invited_email):
            return jsonify({'status': 'error', 'message': 'A valid email address is required'}), 400

        if invited_email == g.current_user['email'].lower():
            return jsonify({'status': 'error', 'message': 'You cannot invite yourself as a caregiver'}), 400

        if not isinstance(permissions, list):
            return jsonify({'status': 'error', 'message': 'Permissions must be a list of permission strings'}), 400

        # Filter and validate permissions
        valid_perms = [p for p in permissions if p in VALID_CAREGIVER_PERMISSIONS]
        if 'correct_doses' in valid_perms and 'record_doses' not in valid_perms:
            valid_perms.append('record_doses')

        with db_manager.get_connection() as conn:
            cursor = conn.cursor()

            # Check if this user is already an active caregiver
            cursor.execute('''
                SELECT r.id FROM caregiver_relationships r
                JOIN users u ON r.caregiver_id = u.id
                WHERE r.patient_id = ? AND u.email = ? AND r.status = 'active'
            ''', (patient_id, invited_email))
            if cursor.fetchone():
                return jsonify({'status': 'error', 'message': f'{invited_email} is already an active caregiver on your team'}), 400

            # Check if an active unexpired pending invitation already exists for this email
            now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute('''
                SELECT id FROM caregiver_invitations
                WHERE patient_id = ? AND invited_email = ? AND status = 'pending' AND expires_at > ?
            ''', (patient_id, invited_email, now_str))
            if cursor.fetchone():
                return jsonify({'status': 'error', 'message': f'A pending invitation already exists for {invited_email}. Please cancel it before re-inviting.'}), 400

            raw_token = secrets.token_urlsafe(32)
            token_h = hash_token(raw_token)
            expires_at = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S')

            cursor.execute('''
                INSERT INTO caregiver_invitations (patient_id, invited_email, token_hash, raw_token, permissions, status, expires_at)
                VALUES (?, ?, ?, ?, ?, 'pending', ?)
            ''', (patient_id, invited_email, token_h, raw_token, json.dumps(valid_perms), expires_at))
            invitation_id = cursor.lastrowid

            # Log audit activity
            cursor.execute('''
                INSERT INTO caregiver_activity_logs (patient_id, actor_id, actor_name, actor_role, action, details)
                VALUES (?, ?, ?, 'patient', 'invite_created', ?)
            ''', (patient_id, patient_id, g.current_user['name'], f"Invited {invited_email} with permissions: {', '.join(valid_perms)}"))

        return jsonify({
            'status': 'success',
            'message': f'Invitation generated for {invited_email}',
            'invite_token': raw_token,
            'invite_link': f"/accept-invite?token={raw_token}",
            'invitation': {
                'id': invitation_id,
                'invited_email': invited_email,
                'permissions': valid_perms,
                'expires_at': expires_at,
                'invite_token': raw_token,
                'invite_link': f"/accept-invite?token={raw_token}"
            }
        }), 201

    except Exception as e:
        return jsonify({'status': 'error', 'message': 'Failed to create caregiver invitation'}), 500


@app.route('/api/caregiver-team/invitations/<int:inv_id>', methods=['DELETE'])
@require_auth
def cancel_invitation(inv_id):
    """Cancels a pending caregiver invitation."""
    patient_id = g.current_user['id']
    try:
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM caregiver_invitations WHERE id = ? AND patient_id = ?
            ''', (inv_id, patient_id))
            inv = cursor.fetchone()
            if not inv:
                return jsonify({'status': 'error', 'message': 'Invitation not found'}), 404

            cursor.execute("UPDATE caregiver_invitations SET status = 'cancelled' WHERE id = ?", (inv_id,))

            cursor.execute('''
                INSERT INTO caregiver_activity_logs (patient_id, actor_id, actor_name, actor_role, action, details)
                VALUES (?, ?, ?, 'patient', 'invite_cancelled', ?)
            ''', (patient_id, patient_id, g.current_user['name'], f"Cancelled invitation for {inv['invited_email']}"))

        return jsonify({'status': 'success', 'message': 'Invitation cancelled'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': 'Failed to cancel invitation'}), 500


@app.route('/api/caregiver-team/caregivers/<int:relationship_id>', methods=['DELETE'])
@require_auth
def revoke_caregiver(relationship_id):
    """Immediately revokes a caregiver's access to patient records."""
    patient_id = g.current_user['id']
    try:
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT r.*, u.name as caregiver_name, u.email as caregiver_email
                FROM caregiver_relationships r
                JOIN users u ON r.caregiver_id = u.id
                WHERE r.id = ? AND r.patient_id = ?
            ''', (relationship_id, patient_id))
            rel = cursor.fetchone()
            if not rel:
                return jsonify({'status': 'error', 'message': 'Caregiver relationship not found'}), 404

            now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute('''
                UPDATE caregiver_relationships 
                SET status = 'revoked', revoked_at = ? 
                WHERE id = ?
            ''', (now_str, relationship_id))

            cursor.execute('''
                INSERT INTO caregiver_activity_logs (patient_id, actor_id, actor_name, actor_role, action, details)
                VALUES (?, ?, ?, 'patient', 'caregiver_revoked', ?)
            ''', (patient_id, patient_id, g.current_user['name'], f"Revoked caregiver access for {rel['caregiver_name']} ({rel['caregiver_email']})"))

        return jsonify({'status': 'success', 'message': 'Caregiver access has been immediately revoked'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': 'Failed to revoke caregiver'}), 500


@app.route('/api/caregiver-team/caregivers/<int:relationship_id>/permissions', methods=['PUT'])
@require_auth
def update_caregiver_permissions(relationship_id):
    """Updates granular permissions for an authorized caregiver."""
    patient_id = g.current_user['id']
    try:
        data = request.get_json(force=True, silent=True)
        if not isinstance(data, dict):
            return jsonify({'status': 'error', 'message': 'Invalid JSON body'}), 400

        permissions = data.get('permissions', [])
        if not isinstance(permissions, list):
            return jsonify({'status': 'error', 'message': 'Permissions must be a list'}), 400

        valid_perms = [p for p in permissions if p in VALID_CAREGIVER_PERMISSIONS]
        if 'correct_doses' in valid_perms and 'record_doses' not in valid_perms:
            valid_perms.append('record_doses')

        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT r.*, u.name as caregiver_name
                FROM caregiver_relationships r
                JOIN users u ON r.caregiver_id = u.id
                WHERE r.id = ? AND r.patient_id = ? AND r.status = 'active'
            ''', (relationship_id, patient_id))
            rel = cursor.fetchone()
            if not rel:
                return jsonify({'status': 'error', 'message': 'Active caregiver relationship not found'}), 404

            cursor.execute('''
                UPDATE caregiver_relationships 
                SET permissions = ?
                WHERE id = ?
            ''', (json.dumps(valid_perms), relationship_id))

            cursor.execute('''
                INSERT INTO caregiver_activity_logs (patient_id, actor_id, actor_name, actor_role, action, details)
                VALUES (?, ?, ?, 'patient', 'permissions_updated', ?)
            ''', (patient_id, patient_id, g.current_user['name'], f"Updated permissions for {rel['caregiver_name']}: {', '.join(valid_perms)}"))

        return jsonify({'status': 'success', 'message': 'Caregiver permissions updated', 'permissions': valid_perms})
    except Exception as e:
        return jsonify({'status': 'error', 'message': 'Failed to update permissions'}), 500


# -----------------------------------------------------------------------------
# Invitation Verification & Acceptance Endpoints (Recipient Perspective)
# -----------------------------------------------------------------------------

@app.route('/api/caregiver-team/invitations/verify')
def verify_invitation():
    """Allows an invited recipient to inspect an invitation before authenticating/accepting."""
    token = request.args.get('token', '').strip()
    if not token:
        return jsonify({'status': 'error', 'message': 'Token parameter is required'}), 400

    token_h = hash_token(token)
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    try:
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT i.id, i.invited_email, i.permissions, i.status, i.expires_at, u.name as patient_name
                FROM caregiver_invitations i
                JOIN users u ON i.patient_id = u.id
                WHERE i.token_hash = ?
            ''', (token_h,))
            inv = cursor.fetchone()

            if not inv:
                return jsonify({'status': 'error', 'message': 'Invalid or unrecognized invitation token'}), 404

            inv_status = inv['status']
            if inv_status == 'pending' and inv['expires_at'] < now_str:
                inv_status = 'expired'

            try:
                perms = json.loads(inv['permissions']) if inv['permissions'] else []
            except Exception:
                perms = []

            # Check if invited email matches an existing account
            cursor.execute('SELECT id FROM users WHERE email = ?', (inv['invited_email'],))
            is_registered = cursor.fetchone() is not None

        return jsonify({
            'status': 'success',
            'invitation': {
                'id': inv['id'],
                'patient_name': inv['patient_name'],
                'invited_email': inv['invited_email'],
                'permissions': perms,
                'status': inv_status,
                'expires_at': inv['expires_at'],
                'is_registered': is_registered
            }
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': 'Failed to verify invitation'}), 500


@app.route('/api/caregiver-team/accept-invite', methods=['POST'])
@require_auth
def accept_invitation():
    """Authenticated user accepts a valid caregiver invitation."""
    user_id = g.current_user['id']
    user_email = g.current_user['email'].lower()

    try:
        data = request.get_json(force=True, silent=True)
        if not isinstance(data, dict):
            return jsonify({'status': 'error', 'message': 'Invalid JSON body'}), 400

        token = str(data.get('invite_token') or data.get('token') or '').strip()
        if not token:
            return jsonify({'status': 'error', 'message': 'Invitation token is required'}), 400

        token_h = hash_token(token)
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM caregiver_invitations WHERE token_hash = ?
            ''', (token_h,))
            inv = cursor.fetchone()

            if not inv:
                return jsonify({'status': 'error', 'message': 'Invalid invitation token'}), 404

            if inv['status'] != 'pending':
                return jsonify({'status': 'error', 'message': f"Invitation is no longer pending (status: {inv['status']})"}), 400

            if inv['expires_at'] < now_str:
                cursor.execute("UPDATE caregiver_invitations SET status = 'expired' WHERE id = ?", (inv['id'],))
                return jsonify({'status': 'error', 'message': 'This invitation has expired'}), 400

            if inv['patient_id'] == user_id:
                return jsonify({'status': 'error', 'message': 'You cannot accept an invitation to care for yourself'}), 400

            # If user's email does not match invited email, verify user confirms
            if inv['invited_email'].lower() != user_email:
                return jsonify({
                    'status': 'error',
                    'message': f"This invitation was addressed to {inv['invited_email']}. You are logged in as {user_email}."
                }), 403

            patient_id = inv['patient_id']

            # Insert or activate relationship
            cursor.execute('''
                INSERT INTO caregiver_relationships (patient_id, caregiver_id, status, permissions, accepted_at)
                VALUES (?, ?, 'active', ?, ?)
                ON CONFLICT(patient_id, caregiver_id) DO UPDATE SET
                    status = 'active',
                    permissions = excluded.permissions,
                    accepted_at = excluded.accepted_at,
                    revoked_at = NULL
            ''', (patient_id, user_id, inv['permissions'], now_str))

            # Mark invitation accepted
            cursor.execute('''
                UPDATE caregiver_invitations 
                SET status = 'accepted', accepted_at = ?
                WHERE id = ?
            ''', (now_str, inv['id']))

            # Update caregiver's user role if currently only patient
            if g.current_user['role'] == 'patient':
                cursor.execute("UPDATE users SET role = 'both' WHERE id = ?", (user_id,))

            # Log activity
            cursor.execute('''
                INSERT INTO caregiver_activity_logs (patient_id, actor_id, actor_name, actor_role, action, details)
                VALUES (?, ?, ?, 'caregiver', 'invite_accepted', ?)
            ''', (patient_id, user_id, g.current_user['name'], f"Accepted caregiver invitation and joined care team"))

        return jsonify({
            'status': 'success',
            'message': 'Caregiver invitation accepted! You can now monitor this patient.',
            'patient_id': patient_id
        })

    except Exception as e:
        return jsonify({'status': 'error', 'message': 'Failed to accept invitation'}), 500


# -----------------------------------------------------------------------------
# Caregiver Portal Endpoints (Caregiver Dashboard View)
# -----------------------------------------------------------------------------

@app.route('/api/caregiver/my-patients')
@require_auth
def get_caregiver_patients():
    """Lists all patients who have granted active access to the current user."""
    caregiver_id = g.current_user['id']
    today = datetime.now().strftime('%Y-%m-%d')
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M')

    try:
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT r.id as relationship_id, r.patient_id, u.name as patient_name, 
                       u.email as patient_email, r.permissions, r.accepted_at
                FROM caregiver_relationships r
                JOIN users u ON r.patient_id = u.id
                WHERE r.caregiver_id = ? AND r.status = 'active'
                ORDER BY u.name ASC
            ''', (caregiver_id,))
            patients = []

            for row in cursor.fetchall():
                p_id = row['patient_id']
                try:
                    perms = json.loads(row['permissions']) if row['permissions'] else []
                except Exception:
                    perms = []

                # Make sure schedules are synced for this patient
                sync_daily_schedules(today, patient_id=p_id, conn=conn)

                # Compute quick summary for today
                cursor.execute('''
                    SELECT 
                        COUNT(*) as total_today,
                        COUNT(CASE WHEN l.status = 'taken' THEN 1 END) as taken_today,
                        COUNT(CASE WHEN l.status = 'skipped' THEN 1 END) as skipped_today,
                        COUNT(CASE WHEN l.status = 'pending' AND l.scheduled_time < ? THEN 1 END) as overdue_today,
                        COUNT(CASE WHEN l.status = 'pending' AND l.scheduled_time >= ? THEN 1 END) as upcoming_today
                    FROM logs l
                    WHERE l.user_id = ? AND DATE(l.scheduled_time) = ?
                ''', (now_str, now_str, p_id, today))
                stats_row = cursor.fetchone()

                patients.append({
                    'id': p_id,
                    'patient_id': p_id,
                    'name': row['patient_name'],
                    'patient_name': row['patient_name'],
                    'patient_email': row['patient_email'],
                    'relationship_id': row['relationship_id'],
                    'permissions': perms,
                    'accepted_at': row['accepted_at'],
                    'today_summary': {
                        'total_today': stats_row['total_today'] if stats_row else 0,
                        'taken_today': stats_row['taken_today'] if stats_row else 0,
                        'skipped_today': stats_row['skipped_today'] if stats_row else 0,
                        'overdue_today': stats_row['overdue_today'] if stats_row else 0,
                        'upcoming_today': stats_row['upcoming_today'] if stats_row else 0,
                    }
                })

        return jsonify({'status': 'success', 'patients': patients})

    except Exception as e:
        return jsonify({'status': 'error', 'message': 'Failed to retrieve patient list'}), 500


@app.route('/api/caregiver/patient/<int:patient_id>/summary')
@require_auth
def get_caregiver_patient_summary(patient_id):
    """Provides a detailed daily summary for an authorized caregiver."""
    target_id, rel, err = resolve_patient_context(patient_id, required_permission='view_schedule')
    if err:
        return err

    today = datetime.now().strftime('%Y-%m-%d')
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M')

    try:
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            sync_daily_schedules(today, patient_id=target_id, conn=conn)

            # Patient name
            cursor.execute('SELECT name, email FROM users WHERE id = ?', (target_id,))
            pat_user = cursor.fetchone()

            cursor.execute('''
                SELECT 
                    COUNT(*) as total_today,
                    COUNT(CASE WHEN l.status = 'taken' THEN 1 END) as taken_today,
                    COUNT(CASE WHEN l.status = 'skipped' THEN 1 END) as skipped_today,
                    COUNT(CASE WHEN l.status = 'pending' AND l.scheduled_time < ? THEN 1 END) as overdue_today,
                    COUNT(CASE WHEN l.status = 'pending' AND l.scheduled_time >= ? THEN 1 END) as upcoming_today
                FROM logs l
                WHERE l.user_id = ? AND DATE(l.scheduled_time) = ?
            ''', (now_str, now_str, target_id, today))
            sum_row = cursor.fetchone()

            # 7-day adherence if view_adherence is authorized
            adherence_rate = None
            if 'view_adherence' in rel['permissions_list']:
                week_ago = (datetime.now() - timedelta(days=6)).strftime('%Y-%m-%d')
                cursor.execute('''
                    SELECT COUNT(*) FROM logs l
                    WHERE l.user_id = ? AND DATE(l.scheduled_time) >= ? AND DATE(l.scheduled_time) <= ?
                    AND (l.status IN ('taken', 'skipped') OR (l.status = 'pending' AND l.scheduled_time < ?))
                ''', (target_id, week_ago, today, now_str))
                due_week = cursor.fetchone()[0]

                cursor.execute('''
                    SELECT COUNT(*) FROM logs l
                    WHERE l.user_id = ? AND DATE(l.scheduled_time) >= ? AND DATE(l.scheduled_time) <= ?
                    AND l.status = 'taken'
                ''', (target_id, week_ago, today))
                taken_week = cursor.fetchone()[0]
                adherence_rate = round((taken_week / due_week * 100), 1) if due_week > 0 else 100.0

            # Recent activity for this patient
            cursor.execute('''
                SELECT actor_name, actor_role, action, details, timestamp
                FROM caregiver_activity_logs
                WHERE patient_id = ?
                ORDER BY id DESC LIMIT 5
            ''', (target_id,))
            recent_activity = [dict(r) for r in cursor.fetchall()]

        return jsonify({
            'status': 'success',
            'summary': {
                'patient_id': target_id,
                'patient_name': pat_user['name'] if pat_user else 'Patient',
                'date': today,
                'generated_at': datetime.now().isoformat(),
                'total_scheduled': sum_row['total_today'],
                'doses_taken': sum_row['taken_today'],
                'doses_pending': sum_row['upcoming_today'],
                'doses_overdue': sum_row['overdue_today'],
                'doses_skipped': sum_row['skipped_today'],
                'adherence_rate': adherence_rate,
                'permissions': rel['permissions_list'],
                'recent_activity': recent_activity
            }
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': 'Failed to compile daily summary'}), 500


@app.route('/api/caregiver/patient/<int:patient_id>/activity')
@require_auth
def get_caregiver_patient_activity(patient_id):
    """Activity feed for a patient accessible to authorized caregivers."""
    target_id, rel, err = resolve_patient_context(patient_id)
    if err:
        return err

    try:
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, actor_name, actor_role, action, details, timestamp
                FROM caregiver_activity_logs
                WHERE patient_id = ?
                ORDER BY id DESC LIMIT 50
            ''', (target_id,))
            activity = [dict(r) for r in cursor.fetchall()]

        return jsonify({
            'status': 'success',
            'patient_id': target_id,
            'activity': activity
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': 'Failed to retrieve patient activity feed'}), 500


# -----------------------------------------------------------------------------
# Patient Medication Endpoints (Protected with RBAC)
# -----------------------------------------------------------------------------

@app.route('/')
def home():
    return render_template('index.html') if os.path.exists('templates/index.html') else (
        "Curavit Medicine Tracker API is running.", 200
    )


@app.route('/api/medicines', methods=['GET', 'POST'])
@require_auth
def handle_medicines():
    if request.method == 'GET':
        req_patient_id = request.args.get('patient_id')
        patient_id, rel, err = resolve_patient_context(req_patient_id, required_permission='view_medicines')
        if err:
            return err

        try:
            with db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT * FROM medicines 
                    WHERE (user_id = ? OR user_id IS NULL) AND is_active = 1 
                    ORDER BY name ASC
                ''', (patient_id,))
                rows = cursor.fetchall()
                medicines = []
                for row in rows:
                    try:
                        schedule = json.loads(row['schedule']) if row['schedule'] else []
                    except Exception:
                        schedule = []

                    medicines.append({
                        'id': row['id'],
                        'name': row['name'],
                        'dosage': row['dosage'],
                        'times_per_day': row['times_per_day'],
                        'schedule': schedule,
                        'start_date': row['start_date'],
                        'end_date': row['end_date'] or '',
                        'frequency': row['frequency'] or 'daily',
                        'instructions': row['instructions'] or '',
                        'created_at': row['created_at'],
                        'is_active': bool(row['is_active'])
                    })
                return jsonify(medicines)
        except Exception as e:
            return jsonify({'status': 'error', 'message': 'Unable to fetch medicines'}), 500

    elif request.method == 'POST':
        # ONLY patients can add their own prescriptions; caregivers are strictly forbidden
        req_patient_id = request.args.get('patient_id')
        if not req_patient_id and request.is_json:
            req_patient_id = (request.get_json(silent=True) or {}).get('patient_id')

        if req_patient_id and int(req_patient_id) != g.current_user['id']:
            return jsonify({'status': 'error', 'message': 'Caregivers cannot create prescriptions on behalf of patients', 'code': 'FORBIDDEN'}), 403

        if g.current_user.get('role') == 'caregiver':
            return jsonify({'status': 'error', 'message': 'Caregivers cannot create prescriptions', 'code': 'FORBIDDEN'}), 403

        patient_id = g.current_user['id']
        try:
            data = request.get_json(force=True, silent=True)
            validated, err = validate_medicine_payload(data)
            if err:
                return jsonify({'status': 'error', 'message': err}), 400

            with db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO medicines (user_id, name, dosage, times_per_day, schedule, start_date, end_date, frequency, instructions)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    patient_id,
                    validated['name'],
                    validated['dosage'],
                    validated['times_per_day'],
                    json.dumps(validated['schedule']),
                    validated['start_date'],
                    validated['end_date'],
                    validated['frequency'],
                    validated['instructions']
                ))
                medicine_id = cursor.lastrowid

                today = datetime.now().strftime('%Y-%m-%d')
                sync_daily_schedules(today, patient_id=patient_id, conn=conn)

            return jsonify({
                'status': 'success',
                'message': 'Medicine added successfully',
                'id': medicine_id
            }), 201

        except Exception as e:
            return jsonify({'status': 'error', 'message': 'Failed to save medication'}), 500


@app.route('/api/medicines/<int:medicine_id>', methods=['PUT', 'DELETE'])
@require_auth
def manage_medicine(medicine_id):
    if g.current_user.get('role') == 'caregiver':
        return jsonify({'status': 'error', 'message': 'Caregivers cannot modify or deactivate medications', 'code': 'FORBIDDEN'}), 403

    req_patient_id = request.args.get('patient_id')
    if req_patient_id and int(req_patient_id) != g.current_user['id']:
        return jsonify({'status': 'error', 'message': 'Caregivers cannot modify medications for patients', 'code': 'FORBIDDEN'}), 403

    patient_id = g.current_user['id']

    # Strictly patient-only; caregivers cannot edit prescriptions or dosages
    if request.method == 'DELETE':
        try:
            with db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('UPDATE medicines SET is_active = 0 WHERE id = ? AND (user_id = ? OR user_id IS NULL)', (medicine_id, patient_id))
                if cursor.rowcount == 0:
                    return jsonify({'status': 'error', 'message': 'Medicine not found or access denied'}), 404

            return jsonify({
                'status': 'success',
                'message': 'Medicine deactivated successfully. Historical logs remain preserved.'
            })
        except Exception as e:
            return jsonify({'status': 'error', 'message': 'Failed to deactivate medication'}), 500

    elif request.method == 'PUT':
        try:
            data = request.get_json(force=True, silent=True)
            if not data:
                return jsonify({'status': 'error', 'message': 'Invalid JSON body'}), 400

            with db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM medicines WHERE id = ? AND (user_id = ? OR user_id IS NULL)', (medicine_id, patient_id))
                existing = cursor.fetchone()
                if not existing:
                    return jsonify({'status': 'error', 'message': 'Medicine not found or access denied'}), 404

                merged_payload = {
                    'name': data.get('name', existing['name']),
                    'dosage': data.get('dosage', existing['dosage']),
                    'times_per_day': data.get('times_per_day', existing['times_per_day']),
                    'schedule': data.get('schedule', json.loads(existing['schedule']) if existing['schedule'] else []),
                    'start_date': data.get('start_date', existing['start_date']),
                    'end_date': data.get('end_date', existing['end_date'] or ''),
                    'frequency': data.get('frequency', existing['frequency'] or 'daily'),
                    'instructions': data.get('instructions', existing['instructions'] or '')
                }

                validated, err = validate_medicine_payload(merged_payload, is_update=True)
                if err:
                    return jsonify({'status': 'error', 'message': err}), 400

                cursor.execute('''
                    UPDATE medicines 
                    SET name = ?, dosage = ?, times_per_day = ?, schedule = ?, 
                        start_date = ?, end_date = ?, frequency = ?, instructions = ?
                    WHERE id = ?
                ''', (
                    validated['name'],
                    validated['dosage'],
                    validated['times_per_day'],
                    json.dumps(validated['schedule']),
                    validated['start_date'],
                    validated['end_date'],
                    validated['frequency'],
                    validated['instructions'],
                    medicine_id
                ))

                today = datetime.now().strftime('%Y-%m-%d')
                new_slots = [f"{today} {s}" for s in validated['schedule']]
                cursor.execute('''
                    DELETE FROM logs 
                    WHERE medicine_id = ? 
                      AND DATE(scheduled_time) = ? 
                      AND status = 'pending' 
                      AND scheduled_time NOT IN ({})
                '''.format(','.join('?' * len(new_slots)) if new_slots else "''"), [medicine_id, today] + new_slots)

                sync_daily_schedules(today, patient_id=patient_id, conn=conn)

            return jsonify({'status': 'success', 'message': 'Medicine updated successfully'})

        except Exception as e:
            return jsonify({'status': 'error', 'message': 'Failed to update medication'}), 500


# -----------------------------------------------------------------------------
# Dose Logs, Recording & Safe Corrections (with RBAC & Attribution)
# -----------------------------------------------------------------------------

@app.route('/api/logs', methods=['GET', 'POST'])
@require_auth
def handle_logs():
    if request.method == 'GET':
        req_patient_id = request.args.get('patient_id')
        patient_id, rel, err = resolve_patient_context(req_patient_id, required_permission='view_history')
        if err:
            return err

        try:
            days = request.args.get('days', 30, type=int)
            status_filter = request.args.get('status', None)
            medicine_id = request.args.get('medicine_id', type=int)

            if days is not None and days <= 0:
                days = 30

            today = datetime.now().strftime('%Y-%m-%d')
            sync_daily_schedules(today, patient_id=patient_id)

            since_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

            with db_manager.get_connection() as conn:
                cursor = conn.cursor()
                query = '''
                    SELECT l.id, l.medicine_id, 
                           COALESCE(l.medicine_name, m.name) as medicine_name, 
                           COALESCE(l.dosage, m.dosage) as dosage, 
                           l.scheduled_time, l.taken_time, 
                           l.status, l.notes, l.created_at, l.updated_at, m.instructions
                    FROM logs l 
                    LEFT JOIN medicines m ON l.medicine_id = m.id 
                    WHERE (l.user_id = ? OR l.user_id IS NULL) AND DATE(l.scheduled_time) >= ?
                '''
                params = [patient_id, since_date]

                if status_filter and status_filter.lower() in VALID_STATUSES:
                    query += ' AND l.status = ?'
                    params.append(status_filter.lower())

                if medicine_id:
                    query += ' AND l.medicine_id = ?'
                    params.append(medicine_id)

                query += ' ORDER BY l.scheduled_time DESC, l.id DESC'

                cursor.execute(query, params)
                rows = cursor.fetchall()
                logs = []
                now_str = datetime.now().strftime('%Y-%m-%d %H:%M')

                for row in rows:
                    sched_time = row['scheduled_time']
                    status = row['status']
                    is_overdue = False
                    if status == 'pending' and sched_time and sched_time[:16] < now_str:
                        is_overdue = True

                    logs.append({
                        'id': row['id'],
                        'medicine_id': row['medicine_id'],
                        'medicine_name': row['medicine_name'],
                        'dosage': row['dosage'],
                        'scheduled_time': sched_time,
                        'taken_time': row['taken_time'],
                        'status': status,
                        'is_overdue': is_overdue,
                        'notes': row['notes'] or '',
                        'created_at': row['created_at'],
                        'updated_at': row['updated_at'] if 'updated_at' in row.keys() else row['created_at'],
                        'instructions': row['instructions'] or ''
                    })

                return jsonify(logs)
        except Exception as e:
            return jsonify({'status': 'error', 'message': 'Failed to retrieve dose logs'}), 500

    elif request.method == 'POST':
        try:
            data = request.get_json(force=True, silent=True)
            if not isinstance(data, dict):
                return jsonify({'status': 'error', 'message': 'Invalid JSON body'}), 400

            req_patient_id = data.get('patient_id') or request.args.get('patient_id')
            patient_id, rel, err = resolve_patient_context(req_patient_id, required_permission='record_doses')
            if err:
                return err

            actor_id = g.current_user['id']
            actor_name = g.current_user['name']
            actor_role = 'caregiver' if actor_id != patient_id else 'patient'

            with db_manager.get_connection() as conn:
                cursor = conn.cursor()

                if 'log_id' in data:
                    try:
                        log_id = int(data['log_id'])
                    except (ValueError, TypeError):
                        return jsonify({'status': 'error', 'message': 'Invalid log_id'}), 400

                    action = data.get('action')
                    status = str(data.get('status', 'taken')).lower().strip()
                    notes = data.get('notes')

                    if notes and len(str(notes)) > MAX_TEXT_LEN:
                        return jsonify({'status': 'error', 'message': f'Notes cannot exceed {MAX_TEXT_LEN} characters'}), 400

                    # IDOR check: ensure log belongs to this patient
                    cursor.execute('SELECT scheduled_time, notes, status, medicine_name FROM logs WHERE id = ? AND (user_id = ? OR user_id IS NULL)', (log_id, patient_id))
                    current_log = cursor.fetchone()
                    if not current_log:
                        return jsonify({'status': 'error', 'message': 'Log entry not found or unauthorized'}), 404

                    cur_sched_time = current_log['scheduled_time']
                    cur_notes = current_log['notes'] or ''
                    prev_status = current_log['status']
                    updated_notes = str(notes).strip() if notes is not None else cur_notes

                    if action == 'snooze':
                        try:
                            snooze_min = int(data.get('snooze_minutes', 10))
                            if not (1 <= snooze_min <= 120):
                                return jsonify({'status': 'error', 'message': 'snooze_minutes must be between 1 and 120'}), 400
                        except (ValueError, TypeError):
                            snooze_min = 10

                        try:
                            sched_dt = datetime.strptime(cur_sched_time[:16], '%Y-%m-%d %H:%M')
                        except Exception:
                            sched_dt = datetime.now()

                        new_sched = (sched_dt + timedelta(minutes=snooze_min)).strftime('%Y-%m-%d %H:%M')
                        snooze_note = f"[Snoozed +{snooze_min}m by {actor_name}]" if actor_role == 'caregiver' else f"[Snoozed +{snooze_min}m]"
                        if snooze_note not in updated_notes:
                            updated_notes = f"{updated_notes} {snooze_note}".strip()

                        cursor.execute('''
                            UPDATE logs 
                            SET scheduled_time = ?, notes = ?, status = 'pending', updated_at = CURRENT_TIMESTAMP
                            WHERE id = ?
                        ''', (new_sched, updated_notes, log_id))

                        cursor.execute('''
                            INSERT INTO dose_audit_logs (log_id, patient_id, actor_id, actor_name, actor_role, action, previous_status, new_status, reason)
                            VALUES (?, ?, ?, ?, ?, 'snooze', ?, 'pending', ?)
                        ''', (log_id, patient_id, actor_id, actor_name, actor_role, prev_status, f"Snoozed for {snooze_min} minutes"))

                        if actor_role == 'caregiver':
                            cursor.execute('''
                                INSERT INTO caregiver_activity_logs (patient_id, actor_id, actor_name, actor_role, action, details)
                                VALUES (?, ?, ?, 'caregiver', 'dose_snoozed', ?)
                            ''', (patient_id, actor_id, actor_name, f"Snoozed {current_log['medicine_name']} by {snooze_min} min"))

                        return jsonify({
                            'status': 'success',
                            'message': f'Dose snoozed for {snooze_min} minutes',
                            'scheduled_time': new_sched
                        })

                    if status not in VALID_STATUSES:
                        return jsonify({'status': 'error', 'message': f'Invalid status. Allowed: {list(VALID_STATUSES)}'}), 400

                    taken_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S') if status == 'taken' else None
                    if actor_role == 'caregiver':
                        actor_tag = f"[Recorded by caregiver {actor_name}]"
                        if actor_tag not in updated_notes:
                            updated_notes = f"{updated_notes} {actor_tag}".strip()

                    cursor.execute('''
                        UPDATE logs 
                        SET taken_time = ?, status = ?, notes = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                    ''', (taken_time, status, updated_notes, log_id))

                    cursor.execute('''
                        INSERT INTO dose_audit_logs (log_id, patient_id, actor_id, actor_name, actor_role, action, previous_status, new_status, reason)
                        VALUES (?, ?, ?, ?, ?, 'status_change', ?, ?, ?)
                    ''', (log_id, patient_id, actor_id, actor_name, actor_role, prev_status, status, updated_notes))

                    if actor_role == 'caregiver':
                        act_action = 'dose_taken' if status == 'taken' else 'dose_skipped'
                        cursor.execute('''
                            INSERT INTO caregiver_activity_logs (patient_id, actor_id, actor_name, actor_role, action, details)
                            VALUES (?, ?, ?, 'caregiver', ?, ?)
                        ''', (patient_id, actor_id, actor_name, act_action, f"Marked {current_log['medicine_name']} as {status}"))

                    return jsonify({'status': 'success', 'message': f'Dose marked as {status}'})

                # Ad-hoc / PRN dose logging
                else:
                    medicine_name = str(data.get('medicine_name', '')).strip()
                    dosage = str(data.get('dosage', '')).strip()
                    notes = str(data.get('notes', '')).strip()

                    if not medicine_name:
                        return jsonify({'status': 'error', 'message': 'medicine_name is required'}), 400
                    if not dosage:
                        return jsonify({'status': 'error', 'message': 'dosage is required'}), 400

                    status = str(data.get('status', 'taken')).lower().strip()
                    if status not in VALID_STATUSES:
                        status = 'taken'

                    now_ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    taken_time = now_ts if status == 'taken' else None
                    med_id = data.get('medicine_id')

                    if actor_role == 'caregiver':
                        notes = f"{notes} [Logged by caregiver {actor_name}]".strip()

                    cursor.execute('''
                        INSERT INTO logs (user_id, medicine_id, medicine_name, dosage, scheduled_time, taken_time, status, notes, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    ''', (patient_id, med_id, medicine_name, dosage, now_ts, taken_time, status, notes))
                    new_log_id = cursor.lastrowid

                    cursor.execute('''
                        INSERT INTO dose_audit_logs (log_id, patient_id, actor_id, actor_name, actor_role, action, previous_status, new_status, reason)
                        VALUES (?, ?, ?, ?, ?, 'adhoc_create', NULL, ?, ?)
                    ''', (new_log_id, patient_id, actor_id, actor_name, actor_role, status, notes or 'Ad-hoc PRN dose recorded'))

                    if actor_role == 'caregiver':
                        cursor.execute('''
                            INSERT INTO caregiver_activity_logs (patient_id, actor_id, actor_name, actor_role, action, details)
                            VALUES (?, ?, ?, 'caregiver', 'dose_taken', ?)
                        ''', (patient_id, actor_id, actor_name, f"Logged extra dose of {medicine_name} ({dosage})"))

                    return jsonify({'status': 'success', 'message': 'Dose recorded successfully', 'id': new_log_id}), 201

        except Exception as e:
            return jsonify({'status': 'error', 'message': 'Failed to record dose'}), 500


@app.route('/api/logs/<int:log_id>/correct', methods=['POST'])
@require_auth
def correct_dose_log(log_id):
    """
    Safe correction workflow.
    Requires 'correct_doses' and 'record_doses' if initiated by a caregiver.
    Mandatory server-side reason and audit record.
    """
    try:
        data = request.get_json(force=True, silent=True)
        if not isinstance(data, dict):
            return jsonify({'status': 'error', 'message': 'Invalid JSON body'}), 400

        req_patient_id = data.get('patient_id') or request.args.get('patient_id')
        patient_id, rel, err = resolve_patient_context(req_patient_id, required_permission='correct_doses')
        if err:
            return err

        # Also verify caregiver has record_doses
        if rel and 'record_doses' not in rel['permissions_list']:
            return jsonify({'status': 'error', 'message': 'Dose correction requires both record_doses and correct_doses permissions', 'code': 'INSUFFICIENT_PERMISSIONS'}), 403

        new_status = str(data.get('new_status', '')).lower().strip()
        reason = str(data.get('reason', '')).strip()
        notes = data.get('notes')

        if new_status not in VALID_STATUSES:
            return jsonify({'status': 'error', 'message': f'Invalid status. Allowed: {list(VALID_STATUSES)}'}), 400

        if not reason:
            return jsonify({'status': 'error', 'message': 'A reason for correcting this dose record is required'}), 400

        actor_id = g.current_user['id']
        actor_name = g.current_user['name']
        actor_role = 'caregiver' if actor_id != patient_id else 'patient'

        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM logs WHERE id = ? AND (user_id = ? OR user_id IS NULL)', (log_id, patient_id))
            current_log = cursor.fetchone()
            if not current_log:
                return jsonify({'status': 'error', 'message': 'Dose record not found or access denied'}), 404

            prev_status = current_log['status']
            if prev_status == new_status:
                return jsonify({'status': 'error', 'message': f'Dose is already marked as {new_status}'}), 400

            taken_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S') if new_status == 'taken' else None

            cur_notes = current_log['notes'] or ''
            updated_notes = str(notes).strip() if notes is not None else cur_notes
            correction_note = f"[Correction: {prev_status}->{new_status} by {actor_name} ({actor_role}): {reason}]"
            updated_notes = f"{updated_notes} {correction_note}".strip()

            cursor.execute('''
                UPDATE logs 
                SET status = ?, taken_time = ?, notes = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (new_status, taken_time, updated_notes, log_id))

            cursor.execute('''
                INSERT INTO dose_audit_logs (log_id, patient_id, actor_id, actor_name, actor_role, action, previous_status, new_status, reason)
                VALUES (?, ?, ?, ?, ?, 'correction', ?, ?, ?)
            ''', (log_id, patient_id, actor_id, actor_name, actor_role, prev_status, new_status, reason))

            if actor_role == 'caregiver':
                cursor.execute('''
                    INSERT INTO caregiver_activity_logs (patient_id, actor_id, actor_name, actor_role, action, details)
                    VALUES (?, ?, ?, 'caregiver', 'dose_corrected', ?)
                ''', (patient_id, actor_id, actor_name, f"Corrected {current_log['medicine_name']} from {prev_status} to {new_status}: {reason}"))

        return jsonify({
            'status': 'success',
            'message': f'Dose status corrected to {new_status}',
            'new_status': new_status
        })

    except Exception as e:
        return jsonify({'status': 'error', 'message': 'Failed to correct dose entry'}), 500


# -----------------------------------------------------------------------------
# Today's Schedule, Statistics & Analytics (Protected with RBAC)
# -----------------------------------------------------------------------------

@app.route('/api/today-schedule')
@require_auth
def get_today_schedule():
    req_patient_id = request.args.get('patient_id')
    patient_id, rel, err = resolve_patient_context(req_patient_id, required_permission='view_schedule')
    if err:
        return err

    try:
        today = datetime.now().strftime('%Y-%m-%d')
        sync_daily_schedules(today, patient_id=patient_id)

        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT l.id, l.medicine_id, 
                       COALESCE(l.medicine_name, m.name) as medicine_name,
                       COALESCE(l.dosage, m.dosage) as dosage, 
                       l.scheduled_time, l.taken_time, 
                       l.status, l.notes, l.created_at, l.updated_at, m.instructions
                FROM logs l
                LEFT JOIN medicines m ON l.medicine_id = m.id
                WHERE (l.user_id = ? OR l.user_id IS NULL) AND DATE(l.scheduled_time) = ? 
                  AND (m.is_active = 1 OR m.is_active IS NULL)
                ORDER BY l.scheduled_time ASC, l.id ASC
            ''', (patient_id, today))

            rows = cursor.fetchall()
            schedule = []
            now_str = datetime.now().strftime('%Y-%m-%d %H:%M')

            for row in rows:
                sched_time = row['scheduled_time']
                status = row['status']
                is_overdue = False
                if status == 'pending' and sched_time and sched_time[:16] < now_str:
                    is_overdue = True

                schedule.append({
                    'id': row['id'],
                    'medicine_id': row['medicine_id'],
                    'medicine_name': row['medicine_name'],
                    'dosage': row['dosage'],
                    'scheduled_time': sched_time,
                    'taken_time': row['taken_time'],
                    'status': status,
                    'is_overdue': is_overdue,
                    'notes': row['notes'] or '',
                    'created_at': row['created_at'],
                    'updated_at': row['updated_at'] if 'updated_at' in row.keys() else row['created_at'],
                    'instructions': row['instructions'] or ''
                })

            return jsonify(schedule)

    except Exception as e:
        return jsonify({'status': 'error', 'message': 'Failed to retrieve today schedule'}), 500


@app.route('/api/statistics')
@require_auth
def get_statistics():
    req_patient_id = request.args.get('patient_id')
    patient_id, rel, err = resolve_patient_context(req_patient_id, required_permission='view_schedule')
    if err:
        return err

    try:
        today = datetime.now().strftime('%Y-%m-%d')
        sync_daily_schedules(today, patient_id=patient_id)

        with db_manager.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute('SELECT COUNT(*) FROM medicines WHERE (user_id = ? OR user_id IS NULL) AND is_active = 1', (patient_id,))
            total_medicines = cursor.fetchone()[0]

            cursor.execute('''
                SELECT COUNT(*) FROM logs l 
                LEFT JOIN medicines m ON l.medicine_id = m.id 
                WHERE (l.user_id = ? OR l.user_id IS NULL) AND DATE(l.scheduled_time) = ? AND (m.is_active = 1 OR m.is_active IS NULL)
            ''', (patient_id, today))
            total_today = cursor.fetchone()[0]

            cursor.execute('''
                SELECT COUNT(*) FROM logs l 
                LEFT JOIN medicines m ON l.medicine_id = m.id 
                WHERE (l.user_id = ? OR l.user_id IS NULL) AND DATE(l.scheduled_time) = ? AND l.status = 'taken' AND (m.is_active = 1 OR m.is_active IS NULL)
            ''', (patient_id, today))
            taken_today = cursor.fetchone()[0]

            cursor.execute('''
                SELECT COUNT(*) FROM logs l 
                LEFT JOIN medicines m ON l.medicine_id = m.id 
                WHERE (l.user_id = ? OR l.user_id IS NULL) AND DATE(l.scheduled_time) = ? AND l.status = 'skipped' AND (m.is_active = 1 OR m.is_active IS NULL)
            ''', (patient_id, today))
            skipped_today = cursor.fetchone()[0]

            now_str = datetime.now().strftime('%Y-%m-%d %H:%M')
            cursor.execute('''
                SELECT COUNT(*) FROM logs l 
                LEFT JOIN medicines m ON l.medicine_id = m.id 
                WHERE (l.user_id = ? OR l.user_id IS NULL) AND DATE(l.scheduled_time) = ? AND l.status = 'pending' 
                AND l.scheduled_time < ? AND (m.is_active = 1 OR m.is_active IS NULL)
            ''', (patient_id, today, now_str))
            overdue_today = cursor.fetchone()[0]

            cursor.execute('''
                SELECT COUNT(*) FROM logs l 
                LEFT JOIN medicines m ON l.medicine_id = m.id 
                WHERE (l.user_id = ? OR l.user_id IS NULL) AND DATE(l.scheduled_time) = ? AND l.status = 'pending' 
                AND l.scheduled_time >= ? AND (m.is_active = 1 OR m.is_active IS NULL)
            ''', (patient_id, today, now_str))
            upcoming_today = cursor.fetchone()[0]

            week_ago = (datetime.now() - timedelta(days=6)).strftime('%Y-%m-%d')
            cursor.execute('''
                SELECT COUNT(*) FROM logs l 
                LEFT JOIN medicines m ON l.medicine_id = m.id 
                WHERE (l.user_id = ? OR l.user_id IS NULL) AND DATE(l.scheduled_time) >= ? AND DATE(l.scheduled_time) <= ?
                AND (m.is_active = 1 OR m.is_active IS NULL)
                AND (l.status IN ('taken', 'skipped') OR (l.status = 'pending' AND l.scheduled_time < ?))
            ''', (patient_id, week_ago, today, now_str))
            due_this_week = cursor.fetchone()[0]

            cursor.execute('''
                SELECT COUNT(*) FROM logs l 
                LEFT JOIN medicines m ON l.medicine_id = m.id 
                WHERE (l.user_id = ? OR l.user_id IS NULL) AND DATE(l.scheduled_time) >= ? AND DATE(l.scheduled_time) <= ?
                AND l.status = 'taken' AND (m.is_active = 1 OR m.is_active IS NULL)
            ''', (patient_id, week_ago, today))
            taken_this_week = cursor.fetchone()[0]

            adherence_rate = round((taken_this_week / due_this_week * 100), 1) if due_this_week > 0 else 100.0

            return jsonify({
                'total_medicines': total_medicines,
                'taken_today': taken_today,
                'total_today': total_today,
                'skipped_today': skipped_today,
                'overdue_today': overdue_today,
                'upcoming_today': upcoming_today,
                'adherence_rate': adherence_rate,
                'taken_this_week': taken_this_week,
                'due_this_week': due_this_week
            })

    except Exception as e:
        return jsonify({'status': 'error', 'message': 'Failed to compute dashboard metrics'}), 500


@app.route('/api/analytics')
@require_auth
def get_analytics():
    req_patient_id = request.args.get('patient_id')
    patient_id, rel, err = resolve_patient_context(req_patient_id, required_permission='view_adherence')
    if err:
        return err

    try:
        today_dt = datetime.now()
        today = today_dt.strftime('%Y-%m-%d')
        now_ts = today_dt.strftime('%Y-%m-%d %H:%M')
        sync_daily_schedules(today, patient_id=patient_id)

        with db_manager.get_connection() as conn:
            cursor = conn.cursor()

            days_trend = []
            for i in range(6, -1, -1):
                date_obj = today_dt - timedelta(days=i)
                d_str = date_obj.strftime('%Y-%m-%d')
                display_label = date_obj.strftime('%a, %b %d') if i > 0 else "Today"

                cursor.execute('''
                    SELECT COUNT(*) FROM logs l
                    LEFT JOIN medicines m ON l.medicine_id = m.id
                    WHERE (l.user_id = ? OR l.user_id IS NULL) AND DATE(l.scheduled_time) = ? AND (m.is_active = 1 OR m.is_active IS NULL)
                ''', (patient_id, d_str))
                day_total = cursor.fetchone()[0]

                cursor.execute('''
                    SELECT COUNT(*) FROM logs l
                    LEFT JOIN medicines m ON l.medicine_id = m.id
                    WHERE (l.user_id = ? OR l.user_id IS NULL) AND DATE(l.scheduled_time) = ? AND l.status = 'taken' AND (m.is_active = 1 OR m.is_active IS NULL)
                ''', (patient_id, d_str))
                day_taken = cursor.fetchone()[0]

                cursor.execute('''
                    SELECT COUNT(*) FROM logs l
                    LEFT JOIN medicines m ON l.medicine_id = m.id
                    WHERE (l.user_id = ? OR l.user_id IS NULL) AND DATE(l.scheduled_time) = ? AND l.status = 'skipped' AND (m.is_active = 1 OR m.is_active IS NULL)
                ''', (patient_id, d_str))
                day_skipped = cursor.fetchone()[0]

                if d_str == today:
                    cursor.execute('''
                        SELECT COUNT(*) FROM logs l
                        LEFT JOIN medicines m ON l.medicine_id = m.id
                        WHERE (l.user_id = ? OR l.user_id IS NULL) AND DATE(l.scheduled_time) = ? AND l.status = 'pending' 
                        AND l.scheduled_time < ? AND (m.is_active = 1 OR m.is_active IS NULL)
                    ''', (patient_id, d_str, now_ts))
                else:
                    cursor.execute('''
                        SELECT COUNT(*) FROM logs l
                        LEFT JOIN medicines m ON l.medicine_id = m.id
                        WHERE (l.user_id = ? OR l.user_id IS NULL) AND DATE(l.scheduled_time) = ? AND l.status = 'pending' AND (m.is_active = 1 OR m.is_active IS NULL)
                    ''', (patient_id, d_str))
                day_missed = cursor.fetchone()[0]

                eligible_denominator = day_taken + day_missed + day_skipped
                day_adherence = round((day_taken / eligible_denominator * 100), 1) if eligible_denominator > 0 else (100.0 if day_total == 0 else 100.0)

                days_trend.append({
                    'date': d_str,
                    'display': display_label,
                    'short_day': date_obj.strftime('%a'),
                    'scheduled': day_total,
                    'taken': day_taken,
                    'skipped': day_skipped,
                    'missed': day_missed,
                    'adherence': day_adherence
                })

            week_ago = (today_dt - timedelta(days=6)).strftime('%Y-%m-%d')
            cursor.execute('''
                SELECT m.id, m.name, m.dosage,
                       COUNT(CASE WHEN l.status = 'taken' THEN 1 END) as taken_count,
                       COUNT(CASE WHEN l.status IN ('taken', 'skipped') OR (l.status = 'pending' AND l.scheduled_time < ?) THEN 1 END) as eligible_count
                FROM medicines m
                LEFT JOIN logs l ON m.id = l.medicine_id 
                               AND DATE(l.scheduled_time) >= ? 
                               AND DATE(l.scheduled_time) <= ?
                WHERE (m.user_id = ? OR m.user_id IS NULL) AND m.is_active = 1
                GROUP BY m.id, m.name, m.dosage
                ORDER BY m.name ASC
            ''', (now_ts, week_ago, today, patient_id))

            med_breakdown = []
            for row in cursor.fetchall():
                m_id, m_name, m_dosage, m_taken, m_eligible = row
                m_rate = round((m_taken / m_eligible * 100), 1) if m_eligible > 0 else 100.0
                med_breakdown.append({
                    'id': m_id,
                    'name': m_name,
                    'dosage': m_dosage,
                    'taken': m_taken,
                    'total': m_eligible,
                    'adherence': m_rate
                })

            total_taken_7d = sum(d['taken'] for d in days_trend)
            total_sched_7d = sum(d['scheduled'] for d in days_trend)
            total_skip_7d = sum(d['skipped'] for d in days_trend)
            total_miss_7d = sum(d['missed'] for d in days_trend)
            total_denom = total_taken_7d + total_skip_7d + total_miss_7d
            overall_adherence = round((total_taken_7d / total_denom * 100), 1) if total_denom > 0 else 100.0

            return jsonify({
                'daily_trend': days_trend,
                'medicine_breakdown': med_breakdown,
                'summary': {
                    'weekly_adherence': overall_adherence,
                    'total_taken': total_taken_7d,
                    'total_scheduled': total_sched_7d,
                    'total_skipped': total_skip_7d,
                    'total_missed': total_miss_7d
                }
            })

    except Exception as e:
        return jsonify({'status': 'error', 'message': 'Failed to compile analytics'}), 500


# -----------------------------------------------------------------------------
# Settings Endpoints (Per-User Settings)
# -----------------------------------------------------------------------------

@app.route('/api/settings', methods=['GET', 'POST'])
@require_auth
def handle_settings():
    user_id = g.current_user['id']
    if request.method == 'GET':
        try:
            with db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT key, value FROM settings WHERE user_id = ? OR user_id IS NULL ORDER BY user_id ASC', (user_id,))
                settings = {}
                for row in cursor.fetchall():
                    settings[row['key']] = row['value']
                return jsonify(settings)
        except Exception as e:
            return jsonify({'status': 'error', 'message': 'Failed to load settings'}), 500

    elif request.method == 'POST':
        try:
            data = request.get_json(force=True, silent=True)
            if not isinstance(data, dict):
                return jsonify({'status': 'error', 'message': 'Invalid JSON body'}), 400

            allowed_keys = {'notifications_enabled', 'snooze_duration', 'language', 'reminder_lead_time', 'theme'}
            with db_manager.get_connection() as conn:
                cursor = conn.cursor()
                for key, value in data.items():
                    if key in allowed_keys:
                        val_str = str(value).strip()[:100]
                        cursor.execute('''
                            INSERT INTO settings (user_id, key, value) 
                            VALUES (?, ?, ?)
                            ON CONFLICT(user_id, key) DO UPDATE SET value = excluded.value
                        ''', (user_id, key, val_str))

            return jsonify({'status': 'success', 'message': 'Settings updated successfully'})

        except Exception as e:
            return jsonify({'status': 'error', 'message': 'Failed to save settings'}), 500


# -----------------------------------------------------------------------------
# Data Backup Export & Validated Restoration (Strictly Patient-Only)
# -----------------------------------------------------------------------------

@app.route('/api/export')
@require_auth
def export_data():
    if g.current_user.get('role') == 'caregiver':
        return jsonify({'status': 'error', 'message': 'Caregivers cannot export full patient backups', 'code': 'FORBIDDEN'}), 403

    req_patient_id = request.args.get('patient_id')
    if req_patient_id and int(req_patient_id) != g.current_user['id']:
        return jsonify({'status': 'error', 'message': 'Caregivers cannot export full patient backups', 'code': 'FORBIDDEN'}), 403

    patient_id = g.current_user['id']
    try:
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute('SELECT * FROM medicines WHERE user_id = ? OR user_id IS NULL', (patient_id,))
            medicines = [dict(row) for row in cursor.fetchall()]

            cursor.execute('SELECT * FROM logs WHERE user_id = ? OR user_id IS NULL ORDER BY scheduled_time DESC', (patient_id,))
            logs = [dict(row) for row in cursor.fetchall()]

            cursor.execute('SELECT * FROM settings WHERE user_id = ? OR user_id IS NULL', (patient_id,))
            settings = [dict(row) for row in cursor.fetchall()]

            cursor.execute('SELECT * FROM dose_audit_logs WHERE patient_id = ? OR patient_id IS NULL ORDER BY id DESC', (patient_id,))
            audit_logs = [dict(row) for row in cursor.fetchall()]

            export_data = {
                'schema_version': 3,
                'exported_at': datetime.now().isoformat(),
                'patient_id': patient_id,
                'medicines': medicines,
                'logs': logs,
                'settings': settings,
                'dose_audit_logs': audit_logs
            }
            return jsonify(export_data)

    except Exception as e:
        return jsonify({'status': 'error', 'message': 'Export failed'}), 500


@app.route('/api/restore', methods=['POST'])
@require_auth
def restore_data():
    if g.current_user.get('role') == 'caregiver':
        return jsonify({'status': 'error', 'message': 'Caregivers cannot restore or overwrite databases', 'code': 'FORBIDDEN'}), 403

    req_patient_id = request.args.get('patient_id')
    if not req_patient_id and request.is_json:
        req_patient_id = (request.get_json(silent=True) or {}).get('patient_id')

    if req_patient_id and int(req_patient_id) != g.current_user['id']:
        return jsonify({'status': 'error', 'message': 'Caregivers cannot restore or overwrite patient databases', 'code': 'FORBIDDEN'}), 403

    patient_id = g.current_user['id']
    try:
        data = request.get_json(force=True, silent=True)
        if not isinstance(data, dict):
            return jsonify({'status': 'error', 'message': 'Invalid JSON document'}), 400

        medicines = data.get('medicines')
        logs = data.get('logs')
        settings = data.get('settings')

        if not isinstance(medicines, list) or not isinstance(logs, list):
            return jsonify({'status': 'error', 'message': 'Malformed backup file: missing medicines or logs arrays'}), 400

        for med in medicines:
            if not isinstance(med, dict):
                return jsonify({'status': 'error', 'message': 'Malformed medicine item'}), 400
            if not med.get('name') or not med.get('dosage'):
                return jsonify({'status': 'error', 'message': 'Invalid medicine record in backup: missing name or dosage'}), 400

        db_file = db_manager.db_path
        if os.path.exists(db_file):
            backup_filename = f"{db_file}.pre_restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}.bak"
            try:
                shutil.copy2(db_file, backup_filename)
            except Exception:
                pass

        with db_manager.get_connection() as conn:
            cursor = conn.cursor()

            # Scoped deletion: only replace THIS patient's records
            cursor.execute('DELETE FROM dose_audit_logs WHERE patient_id = ? OR patient_id IS NULL', (patient_id,))
            cursor.execute('DELETE FROM logs WHERE user_id = ? OR user_id IS NULL', (patient_id,))
            cursor.execute('DELETE FROM medicines WHERE user_id = ? OR user_id IS NULL', (patient_id,))

            for med in medicines:
                cursor.execute('''
                    INSERT INTO medicines (user_id, name, dosage, times_per_day, schedule, start_date, end_date, frequency, instructions, created_at, is_active)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    patient_id,
                    str(med.get('name', '')).strip(),
                    str(med.get('dosage', '')).strip(),
                    int(med.get('times_per_day', 1)),
                    med.get('schedule') if isinstance(med.get('schedule'), str) else json.dumps(med.get('schedule', [])),
                    str(med.get('start_date', '')).strip(),
                    med.get('end_date') or '',
                    med.get('frequency') or 'daily',
                    med.get('instructions') or '',
                    med.get('created_at') or datetime.now().isoformat(),
                    1 if med.get('is_active', 1) else 0
                ))

            for log in logs:
                cursor.execute('''
                    INSERT INTO logs (user_id, medicine_id, medicine_name, dosage, scheduled_time, taken_time, status, notes, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    patient_id,
                    log.get('medicine_id'),
                    str(log.get('medicine_name', '')).strip(),
                    str(log.get('dosage', '')).strip(),
                    log.get('scheduled_time'),
                    log.get('taken_time'),
                    log.get('status', 'pending'),
                    log.get('notes', ''),
                    log.get('created_at') or datetime.now().isoformat(),
                    log.get('updated_at') or datetime.now().isoformat()
                ))

            if isinstance(settings, list):
                for s in settings:
                    if isinstance(s, dict) and 'key' in s and 'value' in s:
                        cursor.execute('''
                            INSERT INTO settings (user_id, key, value) 
                            VALUES (?, ?, ?)
                            ON CONFLICT(user_id, key) DO UPDATE SET value = excluded.value
                        ''', (patient_id, s['key'], str(s['value'])))

        return jsonify({
            'status': 'success',
            'message': 'Database restored successfully for your patient account',
            'restored_medicines': len(medicines),
            'restored_logs': len(logs)
        })

    except Exception as e:
        return jsonify({'status': 'error', 'message': f'Restore failed: {str(e)}'}), 500


# -----------------------------------------------------------------------------
# System & Health Check
# -----------------------------------------------------------------------------

@app.route('/api/health')
def health_check():
    try:
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT 1')
            cursor.fetchone()
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'version': '2.1.0'
        })
    except Exception as e:
        return jsonify({'status': 'unhealthy', 'error': 'Database unavailable'}), 500


# -----------------------------------------------------------------------------
# Main Application Entrypoint
# -----------------------------------------------------------------------------

if __name__ == '__main__':
    if not os.path.exists('templates'):
        os.makedirs('templates')

    db_manager.init_db()
    sync_daily_schedules()

    host = os.environ.get('FLASK_HOST', '127.0.0.1')
    port = int(os.environ.get('FLASK_PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', 'False').lower() in ('true', '1')

    print(f"Starting Curavit Medicine Tracker Server with Caregiver Mode on http://{host}:{port}")
    app.run(debug=debug, host=host, port=port)
