from flask import Flask, render_template, request, jsonify
import sqlite3
from datetime import datetime, timedelta
from flask_cors import CORS
import os
import json

app = Flask(__name__)
CORS(app)

class DatabaseManager:
    def __init__(self):
        self.db_path = 'medicines.db'
    
    def get_connection(self):
        return sqlite3.connect(self.db_path, check_same_thread=False)
    
    def init_db(self):
        # First, remove the old database to start fresh
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
            print("🗑️ Removed old database")
        
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Create medicines table with new schema (no time column)
        cursor.execute('''
            CREATE TABLE medicines (
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
        
        # Create logs table
        cursor.execute('''
            CREATE TABLE logs (
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
        
        # Create settings table
        cursor.execute('''
            CREATE TABLE settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT UNIQUE NOT NULL,
                value TEXT NOT NULL
            )
        ''')
        
        # Insert default settings
        cursor.execute('''
            INSERT OR IGNORE INTO settings (key, value) 
            VALUES 
            ('notifications_enabled', 'true'),
            ('snooze_duration', '10'),
            ('language', 'en'),
            ('reminder_lead_time', '5')
        ''')
        
        conn.commit()
        conn.close()
        print("✅ Database initialized successfully with new schema!")

db_manager = DatabaseManager()

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/medicines', methods=['GET', 'POST'])
def handle_medicines():
    if request.method == 'GET':
        try:
            conn = db_manager.get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM medicines WHERE is_active = 1 ORDER BY name')
            medicines = []
            for row in cursor.fetchall():
                try:
                    schedule = json.loads(row[4]) if row[4] else []
                except:
                    schedule = []
                
                medicines.append({
                    'id': row[0],
                    'name': row[1],
                    'dosage': row[2],
                    'times_per_day': row[3],
                    'schedule': schedule,
                    'start_date': row[5],
                    'end_date': row[6],
                    'frequency': row[7],
                    'instructions': row[8],
                    'created_at': row[9],
                    'is_active': bool(row[10])
                })
            conn.close()
            return jsonify(medicines)
        except Exception as e:
            return jsonify({'status': 'error', 'message': str(e)}), 500
    
    elif request.method == 'POST':
        try:
            data = request.get_json()
            print("Received medicine data:", data)  # Debug log
            
            required_fields = ['name', 'dosage', 'times_per_day', 'schedule', 'start_date']
            for field in required_fields:
                if not data.get(field):
                    return jsonify({'status': 'error', 'message': f'Missing required field: {field}'}), 400
            
            # Validate schedule
            if not isinstance(data['schedule'], list):
                return jsonify({'status': 'error', 'message': 'Schedule must be a list'}), 400
            
            if len(data['schedule']) != data['times_per_day']:
                return jsonify({'status': 'error', 'message': f'Expected {data["times_per_day"]} time slots, got {len(data["schedule"])}'}), 400
            
            conn = db_manager.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO medicines (name, dosage, times_per_day, schedule, start_date, end_date, frequency, instructions)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                data['name'].strip(),
                data['dosage'].strip(),
                data['times_per_day'],
                json.dumps(data['schedule']),
                data['start_date'],
                data.get('end_date', ''),
                data.get('frequency', 'daily'),
                data.get('instructions', '')
            ))
            
            medicine_id = cursor.lastrowid
            
            # Create initial log entries for today's schedule
            today = datetime.now().strftime('%Y-%m-%d')
            for time_slot in data['schedule']:
                cursor.execute('''
                    INSERT INTO logs (medicine_id, medicine_name, dosage, scheduled_time, status)
                    VALUES (?, ?, ?, ?, ?)
                ''', (
                    medicine_id,
                    data['name'].strip(),
                    data['dosage'].strip(),
                    f"{today} {time_slot}",
                    'pending'
                ))
            
            conn.commit()
            conn.close()
            
            return jsonify({
                'status': 'success', 
                'message': 'Medicine added successfully',
                'id': medicine_id
            })
            
        except Exception as e:
            print("Error saving medicine:", str(e))  # Debug log
            return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/medicines/<int:medicine_id>', methods=['PUT', 'DELETE'])
def manage_medicine(medicine_id):
    if request.method == 'DELETE':
        try:
            conn = db_manager.get_connection()
            cursor = conn.cursor()
            cursor.execute('UPDATE medicines SET is_active = 0 WHERE id = ?', (medicine_id,))
            conn.commit()
            conn.close()
            return jsonify({'status': 'success', 'message': 'Medicine deleted successfully'})
        except Exception as e:
            return jsonify({'status': 'error', 'message': str(e)}), 500
    
    elif request.method == 'PUT':
        try:
            data = request.get_json()
            conn = db_manager.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE medicines 
                SET name = ?, dosage = ?, times_per_day = ?, schedule = ?, 
                    start_date = ?, end_date = ?, frequency = ?, instructions = ?
                WHERE id = ?
            ''', (
                data['name'].strip(),
                data['dosage'].strip(),
                data['times_per_day'],
                json.dumps(data['schedule']),
                data['start_date'],
                data.get('end_date', ''),
                data.get('frequency', 'daily'),
                data.get('instructions', ''),
                medicine_id
            ))
            
            conn.commit()
            conn.close()
            
            return jsonify({'status': 'success', 'message': 'Medicine updated successfully'})
            
        except Exception as e:
            return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/logs', methods=['GET', 'POST'])
def handle_logs():
    if request.method == 'GET':
        try:
            days = request.args.get('days', 7, type=int)
            since_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
            
            conn = db_manager.get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT l.*, m.name as medicine_name 
                FROM logs l 
                LEFT JOIN medicines m ON l.medicine_id = m.id 
                WHERE DATE(l.scheduled_time) >= ? 
                ORDER BY l.scheduled_time DESC
            ''', (since_date,))
            
            logs = []
            for row in cursor.fetchall():
                logs.append({
                    'id': row[0],
                    'medicine_id': row[1],
                    'medicine_name': row[2],
                    'dosage': row[3],
                    'scheduled_time': row[4],
                    'taken_time': row[5],
                    'status': row[6],
                    'notes': row[7],
                    'created_at': row[8]
                })
            conn.close()
            return jsonify(logs)
        except Exception as e:
            return jsonify({'status': 'error', 'message': str(e)}), 500
    
    elif request.method == 'POST':
        try:
            data = request.get_json()
            conn = db_manager.get_connection()
            cursor = conn.cursor()
            
            if 'log_id' in data:
                taken_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S') if data.get('status') == 'taken' else None
                
                cursor.execute('''
                    UPDATE logs 
                    SET taken_time = ?, status = ?, notes = ?
                    WHERE id = ?
                ''', (
                    taken_time,
                    data.get('status', 'taken'),
                    data.get('notes', ''),
                    data['log_id']
                ))
            else:
                cursor.execute('''
                    INSERT INTO logs (medicine_name, dosage, taken_time, status, notes)
                    VALUES (?, ?, ?, ?, ?)
                ''', (
                    data['medicine_name'],
                    data['dosage'],
                    datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    data.get('status', 'taken'),
                    data.get('notes', '')
                ))
            
            conn.commit()
            conn.close()
            return jsonify({'status': 'success', 'message': 'Dose logged successfully'})
        except Exception as e:
            return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/today-schedule')
def get_today_schedule():
    try:
        today = datetime.now().strftime('%Y-%m-%d')
        conn = db_manager.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT l.*, m.name as medicine_name, m.instructions
            FROM logs l
            LEFT JOIN medicines m ON l.medicine_id = m.id
            WHERE DATE(l.scheduled_time) = ? AND (m.is_active = 1 OR m.is_active IS NULL)
            ORDER BY l.scheduled_time
        ''', (today,))
        
        schedule = []
        for row in cursor.fetchall():
            schedule.append({
                'id': row[0],
                'medicine_id': row[1],
                'medicine_name': row[2],
                'dosage': row[3],
                'scheduled_time': row[4],
                'taken_time': row[5],
                'status': row[6],
                'notes': row[7],
                'created_at': row[8],
                'instructions': row[9]
            })
        
        conn.close()
        return jsonify(schedule)
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/statistics')
def get_statistics():
    try:
        conn = db_manager.get_connection()
        cursor = conn.cursor()
        
        # Get total active medicines
        cursor.execute('SELECT COUNT(*) FROM medicines WHERE is_active = 1')
        total_medicines = cursor.fetchone()[0]
        
        # Get today's logs
        today = datetime.now().strftime('%Y-%m-%d')
        cursor.execute('''
            SELECT COUNT(*) FROM logs l 
            LEFT JOIN medicines m ON l.medicine_id = m.id 
            WHERE DATE(l.scheduled_time) = ? AND (m.is_active = 1 OR m.is_active IS NULL)
        ''', (today,))
        total_today = cursor.fetchone()[0]
        
        cursor.execute('''
            SELECT COUNT(*) FROM logs l 
            LEFT JOIN medicines m ON l.medicine_id = m.id 
            WHERE DATE(l.scheduled_time) = ? AND l.status = 'taken' AND (m.is_active = 1 OR m.is_active IS NULL)
        ''', (today,))
        taken_today = cursor.fetchone()[0]
        
        # Get adherence rate (last 7 days)
        week_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        cursor.execute('''
            SELECT COUNT(*) FROM logs l 
            LEFT JOIN medicines m ON l.medicine_id = m.id 
            WHERE DATE(l.scheduled_time) >= ? AND (m.is_active = 1 OR m.is_active IS NULL)
        ''', (week_ago,))
        total_week = cursor.fetchone()[0]
        
        cursor.execute('''
            SELECT COUNT(*) FROM logs l 
            LEFT JOIN medicines m ON l.medicine_id = m.id 
            WHERE DATE(l.scheduled_time) >= ? AND l.status = 'taken' AND (m.is_active = 1 OR m.is_active IS NULL)
        ''', (week_ago,))
        taken_week = cursor.fetchone()[0]
        
        adherence_rate = round((taken_week / total_week) * 100, 2) if total_week > 0 else 0
        
        # Get upcoming doses for today
        now = datetime.now()
        cursor.execute('''
            SELECT COUNT(*) FROM logs l 
            LEFT JOIN medicines m ON l.medicine_id = m.id 
            WHERE DATE(l.scheduled_time) = ? AND l.status = 'pending' 
            AND TIME(l.scheduled_time) > TIME(?) AND (m.is_active = 1 OR m.is_active IS NULL)
        ''', (today, now.strftime('%H:%M:%S')))
        upcoming_today = cursor.fetchone()[0]
        
        conn.close()
        
        return jsonify({
            'total_medicines': total_medicines,
            'taken_today': taken_today,
            'total_today': total_today,
            'adherence_rate': adherence_rate,
            'taken_this_week': taken_week,
            'upcoming_today': upcoming_today
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
            data = request.get_json()
            conn = db_manager.get_connection()
            cursor = conn.cursor()
            
            for key, value in data.items():
                cursor.execute('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)', (key, str(value).lower()))
            
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
        
        cursor.execute('SELECT * FROM logs')
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
    # Create templates directory if it doesn't exist
    if not os.path.exists('templates'):
        os.makedirs('templates')
    
    # Initialize database - this will create a fresh database
    db_manager.init_db()
    
    print("🚀 Starting Enhanced Medicine Tracker Server...")
    print("📊 API Endpoints:")
    print("   GET  /api/medicines - List all medicines")
    print("   POST /api/medicines - Add new medicine")
    print("   PUT  /api/medicines/<id> - Update medicine")
    print("   DEL  /api/medicines/<id> - Delete medicine")
    print("   GET  /api/logs - Get medication history")
    print("   POST /api/logs - Log a dose")
    print("   GET  /api/today-schedule - Get today's schedule")
    print("   GET  /api/statistics - Get usage statistics")
    print("   GET  /api/export - Export all data")
    print("\n🌐 Server running on http://localhost:5000")
    
    app.run(debug=True, host='0.0.0.0', port=5000)