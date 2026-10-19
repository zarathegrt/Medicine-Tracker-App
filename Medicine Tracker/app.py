import sys
import os
import json
import sqlite3
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS

if sys.platform == 'win32':
    try:
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8')
        if hasattr(sys.stderr, 'reconfigure'):
            sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

app = Flask(__name__)
# Allow CORS for development and local frontend (Vite port 5173 / Flask port 5000)
CORS(app, resources={r"/*": {"origins": "*"}})

class DatabaseManager:
    def __init__(self):
        self.db_path = 'medicines.db'
    
    def get_connection(self):
        return sqlite3.connect(self.db_path, check_same_thread=False)
    
    def init_db(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Create medicines table if not exists
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS medicines (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                dosage TEXT NOT NULL,
                times_per_day INTEGER DEFAULT 1,
                schedule TEXT NOT NULL,
                start_date TEXT NOT NULL,
                end_date TEXT,
                frequency TEXT DEFAULT 'daily',
                instructions TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT 1
            )
        ''')
        
        # Create logs table if not exists
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                medicine_id INTEGER,
                medicine_name TEXT NOT NULL,
                dosage TEXT NOT NULL,
                scheduled_time TEXT,
                taken_time TEXT,
                status TEXT DEFAULT 'pending',
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create settings table if not exists
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT UNIQUE NOT NULL,
                value TEXT NOT NULL
            )
        ''')
        
        # Insert default settings if not exists
        cursor.execute('''
            INSERT OR IGNORE INTO settings (key, value) 
            VALUES 
            ('notifications_enabled', 'true'),
            ('snooze_duration', '10'),
            ('language', 'en'),
            ('reminder_lead_time', '5'),
            ('theme', 'light')
        ''')
        
        conn.commit()
        conn.close()
        print("✅ Database initialized successfully!")

db_manager = DatabaseManager()

def sync_daily_schedules(target_date_str=None, conn=None):
    """
    Idempotently generates dose logs for all active medicines on target_date_str (YYYY-MM-DD).
    - Checks start_date, end_date, and frequency constraints.
    - Avoids duplicate logs for the same medicine and scheduled_time.
    - Preserves existing taken/skipped/custom logs.
    """
    should_close = False
    if conn is None:
        conn = db_manager.get_connection()
        should_close = True
        
    try:
        cursor = conn.cursor()
        if not target_date_str:
            target_date_str = datetime.now().strftime('%Y-%m-%d')
            
        try:
            target_date = datetime.strptime(target_date_str, '%Y-%m-%d').date()
        except ValueError:
            return
            
        target_weekday = target_date.weekday()  # 0=Monday, 6=Sunday

        cursor.execute('''
            SELECT id, name, dosage, schedule, start_date, end_date, frequency 
            FROM medicines 
            WHERE is_active = 1
        ''')
        active_medicines = cursor.fetchall()

        for med in active_medicines:
            med_id, name, dosage, schedule_json, start_str, end_str, freq = med
            
            # Check start_date
            if start_str:
                try:
                    start_date = datetime.strptime(start_str, '%Y-%m-%d').date()
                    if target_date < start_date:
                        continue
                except ValueError:
                    pass
            
            # Check end_date
            if end_str:
                try:
                    end_date = datetime.strptime(end_str, '%Y-%m-%d').date()
                    if target_date > end_date:
                        continue
                except ValueError:
                    pass

            freq = (freq or 'daily').lower().strip()
            if freq == 'as_needed':
                continue  # PRN doses are logged manually on demand
            elif freq == 'weekly':
                # Match day of week of start_date
                try:
                    start_date = datetime.strptime(start_str, '%Y-%m-%d').date()
                    if target_weekday != start_date.weekday():
                        continue
                except Exception:
                    pass

            try:
                time_slots = json.loads(schedule_json) if schedule_json else []
            except Exception:
                time_slots = []

            for slot in time_slots:
                slot_clean = slot.strip()
                scheduled_timestamp = f"{target_date_str} {slot_clean}"
                
                # Check for existing log
                cursor.execute('''
                    SELECT id FROM logs 
                    WHERE medicine_id = ? AND scheduled_time = ?
                ''', (med_id, scheduled_timestamp))
                
                if not cursor.fetchone():
                    cursor.execute('''
                        INSERT INTO logs (medicine_id, medicine_name, dosage, scheduled_time, status)
                        VALUES (?, ?, ?, ?, 'pending')
                    ''', (med_id, name, dosage, scheduled_timestamp))

        conn.commit()
    except Exception as e:
        print(f"Error syncing schedules for {target_date_str}: {e}")
    finally:
        if should_close:
            conn.close()

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/medicines', methods=['GET', 'POST'])
def handle_medicines():
    if request.method == 'GET':
        try:
            conn = db_manager.get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM medicines WHERE is_active = 1 ORDER BY name ASC')
            medicines = []
            for row in cursor.fetchall():
                try:
                    schedule = json.loads(row[4]) if row[4] else []
                except Exception:
                    schedule = []
                
                medicines.append({
                    'id': row[0],
                    'name': row[1],
                    'dosage': row[2],
                    'times_per_day': row[3],
                    'schedule': schedule,
                    'start_date': row[5],
                    'end_date': row[6] or '',
                    'frequency': row[7] or 'daily',
                    'instructions': row[8] or '',
                    'created_at': row[9],
                    'is_active': bool(row[10])
                })
            conn.close()
            return jsonify(medicines)
        except Exception as e:
            return jsonify({'status': 'error', 'message': str(e)}), 500
    
    elif request.method == 'POST':
        try:
            data = request.get_json(force=True, silent=True)
            if not data:
                return jsonify({'status': 'error', 'message': 'Invalid JSON body'}), 400
                
            required_fields = ['name', 'dosage', 'times_per_day', 'schedule', 'start_date']
            for field in required_fields:
                if field not in data or data[field] is None or str(data[field]).strip() == '':
                    return jsonify({'status': 'error', 'message': f'Missing required field: {field}'}), 400
            
            name = str(data['name']).strip()
            dosage = str(data['dosage']).strip()
            try:
                times_per_day = int(data['times_per_day'])
                if times_per_day <= 0:
                    raise ValueError
            except (ValueError, TypeError):
                return jsonify({'status': 'error', 'message': 'times_per_day must be a positive integer'}), 400

            schedule = data['schedule']
            if not isinstance(schedule, list):
                return jsonify({'status': 'error', 'message': 'schedule must be a list of time strings'}), 400
            
            if len(schedule) != times_per_day:
                return jsonify({'status': 'error', 'message': f'Expected {times_per_day} time slots, got {len(schedule)}'}), 400
            
            start_date = str(data['start_date']).strip()
            end_date = str(data.get('end_date', '')).strip()
            try:
                dt_start = datetime.strptime(start_date, '%Y-%m-%d').date()
                if end_date:
                    dt_end = datetime.strptime(end_date, '%Y-%m-%d').date()
                    if dt_end < dt_start:
                        return jsonify({'status': 'error', 'message': 'End date cannot be before start date'}), 400
            except ValueError:
                return jsonify({'status': 'error', 'message': 'Dates must be in YYYY-MM-DD format'}), 400

            frequency = str(data.get('frequency', 'daily')).strip().lower()
            if frequency not in ['daily', 'weekly', 'as_needed']:
                frequency = 'daily'
            
            instructions = str(data.get('instructions', '')).strip()

            conn = db_manager.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO medicines (name, dosage, times_per_day, schedule, start_date, end_date, frequency, instructions)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                name,
                dosage,
                times_per_day,
                json.dumps(schedule),
                start_date,
                end_date,
                frequency,
                instructions
            ))
            
            medicine_id = cursor.lastrowid
            conn.commit()
            
            # Idempotently sync today's doses for this and other medicines
            today = datetime.now().strftime('%Y-%m-%d')
            sync_daily_schedules(today, conn)
            
            conn.close()
            
            return jsonify({
                'status': 'success', 
                'message': 'Medicine added successfully',
                'id': medicine_id
            }), 201
            
        except Exception as e:
            return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/medicines/<int:medicine_id>', methods=['PUT', 'DELETE'])
def manage_medicine(medicine_id):
    if request.method == 'DELETE':
        try:
            conn = db_manager.get_connection()
            cursor = conn.cursor()
            cursor.execute('UPDATE medicines SET is_active = 0 WHERE id = ?', (medicine_id,))
            if cursor.rowcount == 0:
                conn.close()
                return jsonify({'status': 'error', 'message': 'Medicine not found'}), 404
            conn.commit()
            conn.close()
            return jsonify({'status': 'success', 'message': 'Medicine deactivated successfully'})
        except Exception as e:
            return jsonify({'status': 'error', 'message': str(e)}), 500
    
    elif request.method == 'PUT':
        try:
            data = request.get_json(force=True, silent=True)
            if not data:
                return jsonify({'status': 'error', 'message': 'Invalid JSON body'}), 400
                
            conn = db_manager.get_connection()
            cursor = conn.cursor()
            
            # Fetch existing medicine
            cursor.execute('SELECT * FROM medicines WHERE id = ?', (medicine_id,))
            existing = cursor.fetchone()
            if not existing:
                conn.close()
                return jsonify({'status': 'error', 'message': 'Medicine not found'}), 404

            name = str(data.get('name', existing[1])).strip()
            dosage = str(data.get('dosage', existing[2])).strip()
            try:
                times_per_day = int(data.get('times_per_day', existing[3]))
            except (ValueError, TypeError):
                times_per_day = existing[3]
                
            schedule = data.get('schedule')
            if schedule is None:
                try:
                    schedule = json.loads(existing[4])
                except Exception:
                    schedule = []
            elif not isinstance(schedule, list):
                conn.close()
                return jsonify({'status': 'error', 'message': 'schedule must be a list'}), 400
                
            start_date = str(data.get('start_date', existing[5])).strip()
            end_date = str(data.get('end_date', existing[6] or '')).strip()
            frequency = str(data.get('frequency', existing[7] or 'daily')).strip().lower()
            instructions = str(data.get('instructions', existing[8] or '')).strip()
            
            cursor.execute('''
                UPDATE medicines 
                SET name = ?, dosage = ?, times_per_day = ?, schedule = ?, 
                    start_date = ?, end_date = ?, frequency = ?, instructions = ?
                WHERE id = ?
            ''', (
                name,
                dosage,
                times_per_day,
                json.dumps(schedule),
                start_date,
                end_date,
                frequency,
                instructions,
                medicine_id
            ))
            
            conn.commit()
            
            # Re-sync today's schedule
            today = datetime.now().strftime('%Y-%m-%d')
            sync_daily_schedules(today, conn)
            
            conn.close()
            return jsonify({'status': 'success', 'message': 'Medicine updated successfully'})
            
        except Exception as e:
            return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/logs', methods=['GET', 'POST'])
def handle_logs():
    if request.method == 'GET':
        try:
            days = request.args.get('days', 30, type=int)
            status_filter = request.args.get('status', None)
            medicine_id = request.args.get('medicine_id', type=int)
            
            # Ensure today's schedule is generated
            today = datetime.now().strftime('%Y-%m-%d')
            sync_daily_schedules(today)
            
            since_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
            
            conn = db_manager.get_connection()
            cursor = conn.cursor()
            
            query = '''
                SELECT l.id, l.medicine_id, COALESCE(m.name, l.medicine_name) as medicine_name, 
                       COALESCE(m.dosage, l.dosage) as dosage, l.scheduled_time, l.taken_time, 
                       l.status, l.notes, l.created_at, m.instructions
                FROM logs l 
                LEFT JOIN medicines m ON l.medicine_id = m.id 
                WHERE DATE(l.scheduled_time) >= ?
            '''
            params = [since_date]
            
            if status_filter:
                query += ' AND l.status = ?'
                params.append(status_filter.lower())
                
            if medicine_id:
                query += ' AND l.medicine_id = ?'
                params.append(medicine_id)
                
            query += ' ORDER BY l.scheduled_time DESC, l.id DESC'
            
            cursor.execute(query, params)
            logs = []
            now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            for row in cursor.fetchall():
                sched_time = row[4]
                status = row[6]
                is_overdue = False
                if status == 'pending' and sched_time and sched_time < now_str:
                    is_overdue = True
                    
                logs.append({
                    'id': row[0],
                    'medicine_id': row[1],
                    'medicine_name': row[2],
                    'dosage': row[3],
                    'scheduled_time': sched_time,
                    'taken_time': row[5],
                    'status': status,
                    'is_overdue': is_overdue,
                    'notes': row[7] or '',
                    'created_at': row[8],
                    'instructions': row[9] or ''
                })
                
            conn.close()
            return jsonify(logs)
        except Exception as e:
            return jsonify({'status': 'error', 'message': str(e)}), 500
    
    elif request.method == 'POST':
        try:
            data = request.get_json(force=True, silent=True)
            if not data:
                return jsonify({'status': 'error', 'message': 'Invalid JSON body'}), 400
                
            conn = db_manager.get_connection()
            cursor = conn.cursor()
            
            if 'log_id' in data:
                log_id = data['log_id']
                action = data.get('action')
                status = data.get('status', 'taken').lower()
                notes = data.get('notes')
                
                # Retrieve current log
                cursor.execute('SELECT scheduled_time, notes, status FROM logs WHERE id = ?', (log_id,))
                current_log = cursor.fetchone()
                if not current_log:
                    conn.close()
                    return jsonify({'status': 'error', 'message': 'Log entry not found'}), 404
                    
                cur_sched_time, cur_notes, _ = current_log
                updated_notes = notes if notes is not None else (cur_notes or '')
                
                if action == 'snooze':
                    snooze_min = int(data.get('snooze_minutes', 10))
                    try:
                        sched_dt = datetime.strptime(cur_sched_time, '%Y-%m-%d %H:%M')
                    except ValueError:
                        try:
                            sched_dt = datetime.strptime(cur_sched_time, '%Y-%m-%d %H:%M:%S')
                        except Exception:
                            sched_dt = datetime.now()
                            
                    new_sched = (sched_dt + timedelta(minutes=snooze_min)).strftime('%Y-%m-%d %H:%M')
                    updated_notes = f"{updated_notes} [Snoozed +{snooze_min}m]".strip()
                    cursor.execute('''
                        UPDATE logs 
                        SET scheduled_time = ?, notes = ?, status = 'pending'
                        WHERE id = ?
                    ''', (new_sched, updated_notes, log_id))
                    
                    conn.commit()
                    conn.close()
                    return jsonify({
                        'status': 'success', 
                        'message': f'Dose snoozed for {snooze_min} minutes',
                        'scheduled_time': new_sched
                    })
                
                # Standard status update (taken / skipped / pending / missed)
                taken_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S') if status == 'taken' else None
                
                cursor.execute('''
                    UPDATE logs 
                    SET taken_time = ?, status = ?, notes = ?
                    WHERE id = ?
                ''', (
                    taken_time,
                    status,
                    updated_notes,
                    log_id
                ))
            else:
                # Ad-hoc dose logging
                medicine_name = str(data.get('medicine_name', '')).strip()
                dosage = str(data.get('dosage', '')).strip()
                if not medicine_name:
                    conn.close()
                    return jsonify({'status': 'error', 'message': 'medicine_name is required'}), 400
                    
                now_ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                status = data.get('status', 'taken').lower()
                taken_time = now_ts if status == 'taken' else None
                
                cursor.execute('''
                    INSERT INTO logs (medicine_id, medicine_name, dosage, scheduled_time, taken_time, status, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    data.get('medicine_id'),
                    medicine_name,
                    dosage,
                    now_ts,
                    taken_time,
                    status,
                    data.get('notes', '')
                ))
            
            conn.commit()
            conn.close()
            return jsonify({'status': 'success', 'message': 'Dose updated successfully'})
        except Exception as e:
            return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/today-schedule')
def get_today_schedule():
    try:
        today = datetime.now().strftime('%Y-%m-%d')
        # Idempotently ensure logs exist for today
        sync_daily_schedules(today)
        
        conn = db_manager.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT l.id, l.medicine_id, COALESCE(m.name, l.medicine_name) as medicine_name,
                   COALESCE(m.dosage, l.dosage) as dosage, l.scheduled_time, l.taken_time,
                   l.status, l.notes, l.created_at, m.instructions
            FROM logs l
            LEFT JOIN medicines m ON l.medicine_id = m.id
            WHERE DATE(l.scheduled_time) = ? AND (m.is_active = 1 OR m.is_active IS NULL)
            ORDER BY l.scheduled_time ASC
        ''', (today,))
        
        schedule = []
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        for row in cursor.fetchall():
            sched_time = row[4]
            status = row[6]
            is_overdue = False
            if status == 'pending' and sched_time and sched_time < now_str:
                is_overdue = True
                
            schedule.append({
                'id': row[0],
                'medicine_id': row[1],
                'medicine_name': row[2],
                'dosage': row[3],
                'scheduled_time': sched_time,
                'taken_time': row[5],
                'status': status,
                'is_overdue': is_overdue,
                'notes': row[7] or '',
                'created_at': row[8],
                'instructions': row[9] or ''
            })
        
        conn.close()
        return jsonify(schedule)
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/statistics')
def get_statistics():
    try:
        today = datetime.now().strftime('%Y-%m-%d')
        sync_daily_schedules(today)
        
        conn = db_manager.get_connection()
        cursor = conn.cursor()
        
        # Total active medicines
        cursor.execute('SELECT COUNT(*) FROM medicines WHERE is_active = 1')
        total_medicines = cursor.fetchone()[0]
        
        # Today's total scheduled doses
        cursor.execute('''
            SELECT COUNT(*) FROM logs l 
            LEFT JOIN medicines m ON l.medicine_id = m.id 
            WHERE DATE(l.scheduled_time) = ? AND (m.is_active = 1 OR m.is_active IS NULL)
        ''', (today,))
        total_today = cursor.fetchone()[0]
        
        # Doses taken today
        cursor.execute('''
            SELECT COUNT(*) FROM logs l 
            LEFT JOIN medicines m ON l.medicine_id = m.id 
            WHERE DATE(l.scheduled_time) = ? AND l.status = 'taken' AND (m.is_active = 1 OR m.is_active IS NULL)
        ''', (today,))
        taken_today = cursor.fetchone()[0]
        
        # Doses skipped today
        cursor.execute('''
            SELECT COUNT(*) FROM logs l 
            LEFT JOIN medicines m ON l.medicine_id = m.id 
            WHERE DATE(l.scheduled_time) = ? AND l.status = 'skipped' AND (m.is_active = 1 OR m.is_active IS NULL)
        ''', (today,))
        skipped_today = cursor.fetchone()[0]
        
        # Overdue doses today (pending and time < now)
        now_time = datetime.now().strftime('%H:%M:%S')
        cursor.execute('''
            SELECT COUNT(*) FROM logs l 
            LEFT JOIN medicines m ON l.medicine_id = m.id 
            WHERE DATE(l.scheduled_time) = ? AND l.status = 'pending' 
            AND TIME(l.scheduled_time) < TIME(?) AND (m.is_active = 1 OR m.is_active IS NULL)
        ''', (today, now_time))
        overdue_today = cursor.fetchone()[0]
        
        # Upcoming doses today (pending and time >= now)
        cursor.execute('''
            SELECT COUNT(*) FROM logs l 
            LEFT JOIN medicines m ON l.medicine_id = m.id 
            WHERE DATE(l.scheduled_time) = ? AND l.status = 'pending' 
            AND TIME(l.scheduled_time) >= TIME(?) AND (m.is_active = 1 OR m.is_active IS NULL)
        ''', (today, now_time))
        upcoming_today = cursor.fetchone()[0]
        
        # 7-day adherence rate
        # Denominator: total doses that were due (past days + today's taken/skipped/overdue)
        week_ago = (datetime.now() - timedelta(days=6)).strftime('%Y-%m-%d')
        cursor.execute('''
            SELECT COUNT(*) FROM logs l 
            LEFT JOIN medicines m ON l.medicine_id = m.id 
            WHERE DATE(l.scheduled_time) >= ? AND DATE(l.scheduled_time) <= ?
            AND (m.is_active = 1 OR m.is_active IS NULL)
            AND (l.status = 'taken' OR l.scheduled_time <= ?)
        ''', (week_ago, today, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        due_this_week = cursor.fetchone()[0]
        
        cursor.execute('''
            SELECT COUNT(*) FROM logs l 
            LEFT JOIN medicines m ON l.medicine_id = m.id 
            WHERE DATE(l.scheduled_time) >= ? AND DATE(l.scheduled_time) <= ?
            AND l.status = 'taken' AND (m.is_active = 1 OR m.is_active IS NULL)
        ''', (week_ago, today))
        taken_this_week = cursor.fetchone()[0]
        
        adherence_rate = round((taken_this_week / due_this_week * 100), 1) if due_this_week > 0 else 100.0
        
        conn.close()
        
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
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/analytics')
def get_analytics():
    try:
        today_dt = datetime.now()
        today = today_dt.strftime('%Y-%m-%d')
        sync_daily_schedules(today)
        
        conn = db_manager.get_connection()
        cursor = conn.cursor()
        
        # 7-day trend
        days_trend = []
        now_ts = today_dt.strftime('%Y-%m-%d %H:%M:%S')
        
        for i in range(6, -1, -1):
            date_obj = today_dt - timedelta(days=i)
            d_str = date_obj.strftime('%Y-%m-%d')
            display_label = date_obj.strftime('%a, %b %d') if i > 0 else "Today"
            
            # Scheduled total for day
            cursor.execute('''
                SELECT COUNT(*) FROM logs l
                LEFT JOIN medicines m ON l.medicine_id = m.id
                WHERE DATE(l.scheduled_time) = ? AND (m.is_active = 1 OR m.is_active IS NULL)
            ''', (d_str,))
            day_total = cursor.fetchone()[0]
            
            # Taken count
            cursor.execute('''
                SELECT COUNT(*) FROM logs l
                LEFT JOIN medicines m ON l.medicine_id = m.id
                WHERE DATE(l.scheduled_time) = ? AND l.status = 'taken' AND (m.is_active = 1 OR m.is_active IS NULL)
            ''', (d_str,))
            day_taken = cursor.fetchone()[0]
            
            # Skipped count
            cursor.execute('''
                SELECT COUNT(*) FROM logs l
                LEFT JOIN medicines m ON l.medicine_id = m.id
                WHERE DATE(l.scheduled_time) = ? AND l.status = 'skipped' AND (m.is_active = 1 OR m.is_active IS NULL)
            ''', (d_str,))
            day_skipped = cursor.fetchone()[0]
            
            # Missed / overdue
            if d_str == today:
                cursor.execute('''
                    SELECT COUNT(*) FROM logs l
                    LEFT JOIN medicines m ON l.medicine_id = m.id
                    WHERE DATE(l.scheduled_time) = ? AND l.status = 'pending' 
                    AND l.scheduled_time < ? AND (m.is_active = 1 OR m.is_active IS NULL)
                ''', (d_str, now_ts))
            else:
                cursor.execute('''
                    SELECT COUNT(*) FROM logs l
                    LEFT JOIN medicines m ON l.medicine_id = m.id
                    WHERE DATE(l.scheduled_time) = ? AND l.status = 'pending' AND (m.is_active = 1 OR m.is_active IS NULL)
                ''', (d_str,))
            day_missed = cursor.fetchone()[0]
            
            # Calculate adherence for past or current day
            eligible_denominator = day_taken + day_missed + day_skipped
            day_adherence = round((day_taken / eligible_denominator * 100), 1) if eligible_denominator > 0 else (100.0 if day_total == 0 else 0.0)
            
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
            
        # Medicine-by-medicine breakdown over last 7 days
        week_ago = (today_dt - timedelta(days=6)).strftime('%Y-%m-%d')
        cursor.execute('''
            SELECT m.id, m.name, m.dosage,
                   COUNT(CASE WHEN l.status = 'taken' THEN 1 END) as taken_count,
                   COUNT(l.id) as total_count
            FROM medicines m
            LEFT JOIN logs l ON m.id = l.medicine_id AND DATE(l.scheduled_time) >= ? AND DATE(l.scheduled_time) <= ?
            WHERE m.is_active = 1
            GROUP BY m.id, m.name, m.dosage
            ORDER BY m.name ASC
        ''', (week_ago, today))
        
        med_breakdown = []
        for row in cursor.fetchall():
            m_id, m_name, m_dosage, m_taken, m_total = row
            m_rate = round((m_taken / m_total * 100), 1) if m_total > 0 else 100.0
            med_breakdown.append({
                'id': m_id,
                'name': m_name,
                'dosage': m_dosage,
                'taken': m_taken,
                'total': m_total,
                'adherence': m_rate
            })
            
        # Summary counts
        total_taken_7d = sum(d['taken'] for d in days_trend)
        total_sched_7d = sum(d['scheduled'] for d in days_trend)
        total_skip_7d = sum(d['skipped'] for d in days_trend)
        total_miss_7d = sum(d['missed'] for d in days_trend)
        total_denom = total_taken_7d + total_skip_7d + total_miss_7d
        overall_adherence = round((total_taken_7d / total_denom * 100), 1) if total_denom > 0 else 100.0
        
        conn.close()
        
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
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/settings', methods=['GET', 'POST'])
def handle_settings():
    if request.method == 'GET':
        try:
            conn = db_manager.get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT key, value FROM settings')
            settings = {row[0]: row[1] for row in cursor.fetchall()}
            conn.close()
            return jsonify(settings)
        except Exception as e:
            return jsonify({'status': 'error', 'message': str(e)}), 500
    
    elif request.method == 'POST':
        try:
            data = request.get_json(force=True, silent=True)
            if not data:
                return jsonify({'status': 'error', 'message': 'Invalid JSON body'}), 400
                
            conn = db_manager.get_connection()
            cursor = conn.cursor()
            
            allowed_keys = {'notifications_enabled', 'snooze_duration', 'language', 'reminder_lead_time', 'theme'}
            for key, value in data.items():
                if key in allowed_keys:
                    cursor.execute('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)', (key, str(value).strip()))
            
            conn.commit()
            conn.close()
            return jsonify({'status': 'success', 'message': 'Settings updated successfully'})
        except Exception as e:
            return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/export')
def export_data():
    try:
        conn = db_manager.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM medicines')
        medicines = [dict(zip([column[0] for column in cursor.description], row)) for row in cursor.fetchall()]
        
        cursor.execute('SELECT * FROM logs ORDER BY scheduled_time DESC')
        logs = [dict(zip([column[0] for column in cursor.description], row)) for row in cursor.fetchall()]
        
        cursor.execute('SELECT * FROM settings')
        settings = [dict(zip([column[0] for column in cursor.description], row)) for row in cursor.fetchall()]
        
        conn.close()
        
        export_data = {
            'medicines': medicines,
            'logs': logs,
            'settings': settings,
            'exported_at': datetime.now().isoformat()
        }
        
        return jsonify(export_data)
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/health')
def health_check():
    try:
        conn = db_manager.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT 1')
        conn.close()
        return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()})
    except Exception as e:
        return jsonify({'status': 'unhealthy', 'error': str(e)}), 500

if __name__ == '__main__':
    if not os.path.exists('templates'):
        os.makedirs('templates')
    
    db_manager.init_db()
    
    # Sync today's schedules on startup
    sync_daily_schedules()
    
    print("🚀 Starting Enhanced Medicine Tracker Server...")
    print("🌐 Server running on http://localhost:5000")
    
    app.run(debug=True, host='0.0.0.0', port=5000)
