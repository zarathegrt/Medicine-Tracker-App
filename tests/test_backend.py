"""
Automated Comprehensive Test Suite for Curavit Medicine Tracker
Tests database integrity, idempotent scheduling, historical preservation,
safe dose corrections, adherence calculation accuracy, and backup/restore.
Uses an isolated temporary database to guarantee the user's actual database is never modified.
"""

import sys
import os
import json
import unittest
import tempfile
import shutil
from datetime import datetime, timedelta

# Add parent directory to sys.path so app can be imported
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'Medicine Tracker')))

from app import app, db_manager, sync_daily_schedules, hash_token
from werkzeug.security import generate_password_hash


class MedicineTrackerTestCase(unittest.TestCase):
    def setUp(self):
        # Create an isolated temporary SQLite database for testing
        self.temp_dir = tempfile.mkdtemp()
        self.test_db_path = os.path.join(self.temp_dir, 'test_medicines.db')
        db_manager.set_db_path(self.test_db_path)

        app.config['TESTING'] = True

        # Initialize the fresh test database schema
        db_manager.init_db()

        # Seed authenticated test patient
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            pwd_h = generate_password_hash('Password123!')
            cursor.execute('''
                INSERT INTO users (name, email, password_hash, role, status)
                VALUES (?, ?, ?, ?, ?)
            ''', ('Test Patient', 'patient@test.com', pwd_h, 'patient', 'active'))
            self.user_id = cursor.lastrowid

            self.token = 'test_token_patient_12345'
            token_h = hash_token(self.token)
            expires = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute('''
                INSERT INTO sessions (user_id, token_hash, expires_at)
                VALUES (?, ?, ?)
            ''', (self.user_id, token_h, expires))

        self.client = app.test_client()
        self.client.environ_base['HTTP_AUTHORIZATION'] = f'Bearer {self.token}'

    def tearDown(self):
        # Clean up temporary database directory
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    # -------------------------------------------------------------------------
    # 1. Medicine Creation, Validation & Retrieval
    # -------------------------------------------------------------------------

    def test_create_and_get_medicine(self):
        payload = {
            'name': 'Metformin',
            'dosage': '500mg',
            'times_per_day': 2,
            'schedule': ['08:00', '20:00'],
            'start_date': datetime.now().strftime('%Y-%m-%d'),
            'frequency': 'daily',
            'instructions': 'Take with meals'
        }
        res = self.client.post('/api/medicines', json=payload)
        self.assertEqual(res.status_code, 201)
        data = res.get_json()
        self.assertEqual(data['status'], 'success')
        self.assertIn('id', data)

        # Verify retrieval
        get_res = self.client.get('/api/medicines')
        self.assertEqual(get_res.status_code, 200)
        meds = get_res.get_json()
        self.assertEqual(len(meds), 1)
        self.assertEqual(meds[0]['name'], 'Metformin')
        self.assertEqual(meds[0]['dosage'], '500mg')
        self.assertEqual(meds[0]['schedule'], ['08:00', '20:00'])

    def test_medicine_validation_rejections(self):
        # Missing required fields
        res = self.client.post('/api/medicines', json={'name': ''})
        self.assertEqual(res.status_code, 400)

        # Invalid times_per_day count vs schedule slots
        res = self.client.post('/api/medicines', json={
            'name': 'Aspirin',
            'dosage': '100mg',
            'times_per_day': 2,
            'schedule': ['08:00'],  # Only 1 slot provided
            'start_date': '2026-10-20'
        })
        self.assertEqual(res.status_code, 400)

        # Invalid time format
        res = self.client.post('/api/medicines', json={
            'name': 'Aspirin',
            'dosage': '100mg',
            'times_per_day': 1,
            'schedule': ['25:99'],
            'start_date': '2026-10-20'
        })
        self.assertEqual(res.status_code, 400)

        # End date earlier than start date
        res = self.client.post('/api/medicines', json={
            'name': 'Aspirin',
            'dosage': '100mg',
            'times_per_day': 1,
            'schedule': ['08:00'],
            'start_date': '2026-10-25',
            'end_date': '2026-10-20'
        })
        self.assertEqual(res.status_code, 400)

    # -------------------------------------------------------------------------
    # 2. Historical Record Preservation & Editing
    # -------------------------------------------------------------------------

    def test_historical_preservation_on_medicine_edit(self):
        today = datetime.now().strftime('%Y-%m-%d')
        # Create initial medicine
        create_res = self.client.post('/api/medicines', json={
            'name': 'Atorvastatin Original',
            'dosage': '20mg',
            'times_per_day': 1,
            'schedule': ['21:00'],
            'start_date': today,
            'frequency': 'daily'
        })
        med_id = create_res.get_json()['id']

        # Verify today's log was created
        logs_res = self.client.get('/api/logs?days=1')
        logs = logs_res.get_json()
        self.assertEqual(len(logs), 1)
        log_id = logs[0]['id']

        # Mark dose as taken
        take_res = self.client.post('/api/logs', json={'log_id': log_id, 'status': 'taken'})
        self.assertEqual(take_res.status_code, 200)

        # Update the medicine name and dosage
        update_res = self.client.put(f'/api/medicines/{med_id}', json={
            'name': 'Atorvastatin Renamed',
            'dosage': '40mg',
            'times_per_day': 1,
            'schedule': ['21:00'],
            'start_date': today
        })
        self.assertEqual(update_res.status_code, 200)

        # CRITICAL VERIFICATION: Historical taken log MUST retain 'Atorvastatin Original' & '20mg'
        updated_logs = self.client.get('/api/logs?days=1').get_json()
        target_log = [l for l in updated_logs if l['id'] == log_id][0]
        self.assertEqual(target_log['medicine_name'], 'Atorvastatin Original')
        self.assertEqual(target_log['dosage'], '20mg')

    def test_medicine_deactivation_preserves_logs(self):
        today = datetime.now().strftime('%Y-%m-%d')
        create_res = self.client.post('/api/medicines', json={
            'name': 'Omeprazole',
            'dosage': '20mg',
            'times_per_day': 1,
            'schedule': ['07:00'],
            'start_date': today
        })
        med_id = create_res.get_json()['id']

        # Deactivate
        del_res = self.client.delete(f'/api/medicines/{med_id}')
        self.assertEqual(del_res.status_code, 200)

        # Medicine should not appear in active list
        active_meds = self.client.get('/api/medicines').get_json()
        self.assertEqual(len(active_meds), 0)

        # Historical logs must still exist
        all_logs = self.client.get('/api/logs?days=1').get_json()
        self.assertEqual(len(all_logs), 1)
        self.assertEqual(all_logs[0]['medicine_name'], 'Omeprazole')

    # -------------------------------------------------------------------------
    # 3. Schedule Idempotence & Duplicate Prevention
    # -------------------------------------------------------------------------

    def test_duplicate_prevention_on_multiple_syncs(self):
        today = datetime.now().strftime('%Y-%m-%d')
        self.client.post('/api/medicines', json={
            'name': 'Lisinopril',
            'dosage': '10mg',
            'times_per_day': 2,
            'schedule': ['09:00', '21:00'],
            'start_date': today
        })

        # Call sync 5 times consecutively
        for _ in range(5):
            sync_daily_schedules(today)

        # Check total logs for today
        schedule = self.client.get('/api/today-schedule').get_json()
        self.assertEqual(len(schedule), 2)  # Exactly 2 slots, zero duplicates!

    # -------------------------------------------------------------------------
    # 4. Date and Time Boundary Handling
    # -------------------------------------------------------------------------

    def test_start_and_end_date_boundaries(self):
        today = datetime.now().date()
        tomorrow_str = (today + timedelta(days=1)).strftime('%Y-%m-%d')
        yesterday_str = (today - timedelta(days=1)).strftime('%Y-%m-%d')

        # Medicine starting tomorrow should NOT generate doses today
        self.client.post('/api/medicines', json={
            'name': 'Future Med',
            'dosage': '10mg',
            'times_per_day': 1,
            'schedule': ['10:00'],
            'start_date': tomorrow_str
        })

        # Medicine ending yesterday should NOT generate doses today
        self.client.post('/api/medicines', json={
            'name': 'Past Med',
            'dosage': '10mg',
            'times_per_day': 1,
            'schedule': ['10:00'],
            'start_date': (today - timedelta(days=10)).strftime('%Y-%m-%d'),
            'end_date': yesterday_str
        })

        schedule = self.client.get('/api/today-schedule').get_json()
        self.assertEqual(len(schedule), 0)

    # -------------------------------------------------------------------------
    # 5. Safe Dose Correction & Audit Log Trail
    # -------------------------------------------------------------------------

    def test_dose_correction_workflow_and_audit_trail(self):
        today = datetime.now().strftime('%Y-%m-%d')
        self.client.post('/api/medicines', json={
            'name': 'Ibuprofen',
            'dosage': '400mg',
            'times_per_day': 1,
            'schedule': ['12:00'],
            'start_date': today
        })

        sched = self.client.get('/api/today-schedule').get_json()
        log_id = sched[0]['id']

        # 1. Mark as taken
        self.client.post('/api/logs', json={'log_id': log_id, 'status': 'taken'})

        # Verify taken
        log_entry = self.client.get('/api/today-schedule').get_json()[0]
        self.assertEqual(log_entry['status'], 'taken')
        self.assertIsNotNone(log_entry['taken_time'])

        # 2. User mistakenly tapped take; correct back to pending
        corr_res = self.client.post(f'/api/logs/{log_id}/correct', json={
            'new_status': 'pending',
            'reason': 'Accidental tap while unlocking phone'
        })
        self.assertEqual(corr_res.status_code, 200)

        # Verify reverted to pending and taken_time cleared
        reverted_entry = self.client.get('/api/today-schedule').get_json()[0]
        self.assertEqual(reverted_entry['status'], 'pending')
        self.assertIsNone(reverted_entry['taken_time'])

        # 3. Verify audit log entry
        export_data = self.client.get('/api/export').get_json()
        audit_logs = export_data['dose_audit_logs']
        self.assertGreaterEqual(len(audit_logs), 2)  # status_change + correction
        correction_event = [a for a in audit_logs if a['action'] == 'correction'][0]
        self.assertEqual(correction_event['previous_status'], 'taken')
        self.assertEqual(correction_event['new_status'], 'pending')
        self.assertIn('Accidental tap', correction_event['reason'])

    # -------------------------------------------------------------------------
    # 6. Adherence Calculations (Denominator Accuracy)
    # -------------------------------------------------------------------------

    def test_adherence_excludes_future_pending_doses(self):
        today = datetime.now().strftime('%Y-%m-%d')
        # Create medicine with dose at 01:00 (past) and dose at 23:59 (future)
        self.client.post('/api/medicines', json={
            'name': 'Blood Pressure Med',
            'dosage': '5mg',
            'times_per_day': 2,
            'schedule': ['01:00', '23:59'],
            'start_date': today
        })

        schedule = self.client.get('/api/today-schedule').get_json()
        morning_log = [s for s in schedule if '01:00' in s['scheduled_time']][0]

        # Take morning dose
        self.client.post('/api/logs', json={'log_id': morning_log['id'], 'status': 'taken'})

        # The 23:59 dose is in the future.
        # Adherence calculation MUST report 100% adherence (1 taken out of 1 due), NOT 50%!
        stats = self.client.get('/api/statistics').get_json()
        self.assertEqual(stats['adherence_rate'], 100.0)

        analytics = self.client.get('/api/analytics').get_json()
        today_trend = [d for d in analytics['daily_trend'] if d['date'] == today][0]
        self.assertEqual(today_trend['adherence'], 100.0)

    # -------------------------------------------------------------------------
    # 7. Backup Export & Validated Restoration
    # -------------------------------------------------------------------------

    def test_export_and_restore_workflow(self):
        today = datetime.now().strftime('%Y-%m-%d')
        self.client.post('/api/medicines', json={
            'name': 'Backup Med Test',
            'dosage': '250mg',
            'times_per_day': 1,
            'schedule': ['08:00'],
            'start_date': today
        })

        # Export data
        export_res = self.client.get('/api/export')
        self.assertEqual(export_res.status_code, 200)
        backup_json = export_res.get_json()

        self.assertIn('medicines', backup_json)
        self.assertIn('logs', backup_json)
        self.assertIn('settings', backup_json)
        self.assertEqual(backup_json['schema_version'], 3)

        # Test corrupt restore payload rejection
        corrupt_res = self.client.post('/api/restore', json={'invalid': True})
        self.assertEqual(corrupt_res.status_code, 400)

        # Test valid restore
        restore_res = self.client.post('/api/restore', json=backup_json)
        self.assertEqual(restore_res.status_code, 200)
        restore_data = restore_res.get_json()
        self.assertEqual(restore_data['status'], 'success')
        self.assertEqual(restore_data['restored_medicines'], len(backup_json['medicines']))


if __name__ == '__main__':
    unittest.main()
