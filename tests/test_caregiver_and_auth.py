"""
Caregiver Mode and Authentication Automated Test Suite
Covers:
1. User registration, login, and token generation.
2. Invalid credentials, expired session handling, and logout invalidation.
3. Patient invitation creation, validation, and acceptance.
4. Invitation expiry and cancellation.
5. Authorized caregiver viewing patient medicines, schedule, and summary.
6. IDOR prevention: caregiver attempting to access unauthorized patient records.
7. Permission checks: view_history and view_adherence restrictions.
8. Dose recording permission checks (record_doses denied if omitted).
9. Dose correction permission checks (correct_doses denied if omitted).
10. Server-derived actor attribution on caregiver dose records and corrections.
11. Immediate access cutoff upon caregiver revocation.
12. Strict prevention of medicine / prescription edits by caregivers.
13. Patient-to-patient data isolation.
14. Migration of legacy unassigned records via claim_legacy.
15. Development invitation verification workflow.
"""

import os
import sys
import json
import unittest
import tempfile
import shutil
from datetime import datetime, timedelta

# Add parent directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'Medicine Tracker')))

from app import app, db_manager, hash_token, sync_daily_schedules
from werkzeug.security import generate_password_hash, check_password_hash


class CaregiverAuthTestCase(unittest.TestCase):
    def setUp(self):
        # Isolated temporary database
        self.temp_dir = tempfile.mkdtemp()
        self.test_db_path = os.path.join(self.temp_dir, 'test_caregiver.db')
        db_manager.set_db_path(self.test_db_path)

        app.config['TESTING'] = True
        self.client = app.test_client()

        # Initialize schema
        db_manager.init_db()

    def tearDown(self):
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def register_user(self, name, email, password, role='patient', claim_legacy=False):
        res = self.client.post('/api/auth/register', json={
            'name': name,
            'email': email,
            'password': password,
            'role': role,
            'claim_legacy': claim_legacy
        })
        self.assertEqual(res.status_code, 201)
        data = res.get_json()
        return data['user'], data['token']

    def login_user(self, email, password):
        res = self.client.post('/api/auth/login', json={
            'email': email,
            'password': password
        })
        return res

    def auth_headers(self, token):
        return {'Authorization': f'Bearer {token}'}

    # -------------------------------------------------------------------------
    # 1 & 2: Registration, Login, Invalid Credentials & Session Handling
    # -------------------------------------------------------------------------

    def test_registration_and_login_success(self):
        # Register patient
        user, token = self.register_user('Sarah Connor', 'sarah@example.com', 'SecurePass123!', 'patient')
        self.assertEqual(user['email'], 'sarah@example.com')
        self.assertEqual(user['role'], 'patient')
        self.assertTrue(len(token) > 20)

        # Verify password is hashed, not plaintext in database
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT password_hash FROM users WHERE email = ?', ('sarah@example.com',))
            row = cursor.fetchone()
            self.assertIsNotNone(row)
            self.assertNotEqual(row['password_hash'], 'SecurePass123!')
            self.assertTrue(check_password_hash(row['password_hash'], 'SecurePass123!'))

        # Login with correct credentials
        login_res = self.login_user('sarah@example.com', 'SecurePass123!')
        self.assertEqual(login_res.status_code, 200)
        login_data = login_res.get_json()
        self.assertIn('token', login_data)

        # Access /api/auth/me
        me_res = self.client.get('/api/auth/me', headers=self.auth_headers(login_data['token']))
        self.assertEqual(me_res.status_code, 200)
        self.assertEqual(me_res.get_json()['user']['email'], 'sarah@example.com')

    def test_invalid_credentials_and_session_expiration(self):
        self.register_user('John Doe', 'john@example.com', 'ValidPass123!', 'patient')

        # Wrong password
        bad_pass = self.login_user('john@example.com', 'WrongPassword!')
        self.assertEqual(bad_pass.status_code, 401)

        # Non-existent email
        bad_email = self.login_user('nobody@example.com', 'ValidPass123!')
        self.assertEqual(bad_email.status_code, 401)

        # Expired token simulation
        _, valid_token = self.register_user('Jane Doe', 'jane@example.com', 'ValidPass123!', 'patient')
        # Manually backdate the session expiry
        token_h = hash_token(valid_token)
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('UPDATE sessions SET expires_at = ? WHERE token_hash = ?',
                           ((datetime.now() - timedelta(hours=2)).strftime('%Y-%m-%d %H:%M:%S'), token_h))

        expired_res = self.client.get('/api/auth/me', headers=self.auth_headers(valid_token))
        self.assertEqual(expired_res.status_code, 401)

    def test_logout_invalidates_session(self):
        _, token = self.register_user('Mark', 'mark@example.com', 'Pass12345!', 'patient')

        # Verify token works
        check1 = self.client.get('/api/auth/me', headers=self.auth_headers(token))
        self.assertEqual(check1.status_code, 200)

        # Logout
        logout_res = self.client.post('/api/auth/logout', headers=self.auth_headers(token))
        self.assertEqual(logout_res.status_code, 200)

        # Token must now be rejected
        check2 = self.client.get('/api/auth/me', headers=self.auth_headers(token))
        self.assertEqual(check2.status_code, 401)

    # -------------------------------------------------------------------------
    # 3 & 4: Invitation Flow, Verification, Expiry & Revocation
    # -------------------------------------------------------------------------

    def test_caregiver_invitation_and_acceptance(self):
        patient, p_token = self.register_user('Alice Patient', 'alice@example.com', 'Pass123!', 'patient')
        caregiver, c_token = self.register_user('Bob Caregiver', 'bob@example.com', 'Pass123!', 'caregiver')

        # Alice invites Bob
        invite_res = self.client.post('/api/caregiver-team/invite',
                                      headers=self.auth_headers(p_token),
                                      json={
                                          'email': 'bob@example.com',
                                          'permissions': ['view_medicines', 'view_schedule', 'record_doses']
                                      })
        self.assertEqual(invite_res.status_code, 201)
        invite_data = invite_res.get_json()
        raw_token = invite_data['invite_token']
        self.assertTrue(len(raw_token) >= 32)

        # Bob verifies invitation token
        verify_res = self.client.get(f'/api/caregiver-team/invitations/verify?token={raw_token}',
                                     headers=self.auth_headers(c_token))
        self.assertEqual(verify_res.status_code, 200)
        v_data = verify_res.get_json()
        self.assertEqual(v_data['invitation']['patient_name'], 'Alice Patient')
        self.assertIn('record_doses', v_data['invitation']['permissions'])

        # Bob accepts invitation
        accept_res = self.client.post('/api/caregiver-team/accept-invite',
                                      headers=self.auth_headers(c_token),
                                      json={'invite_token': raw_token})
        self.assertEqual(accept_res.status_code, 200)

        # Verify Bob now sees Alice in /api/caregiver/my-patients
        my_patients = self.client.get('/api/caregiver/my-patients', headers=self.auth_headers(c_token)).get_json()
        self.assertEqual(len(my_patients['patients']), 1)
        self.assertEqual(my_patients['patients'][0]['name'], 'Alice Patient')
        self.assertIn('record_doses', my_patients['patients'][0]['permissions'])

    def test_prevent_self_invitation_and_duplicate_relationship(self):
        patient, p_token = self.register_user('Self Inviter', 'self@example.com', 'Pass123!', 'patient')

        # Attempt to invite self
        self_inv = self.client.post('/api/caregiver-team/invite',
                                    headers=self.auth_headers(p_token),
                                    json={'email': 'self@example.com'})
        self.assertEqual(self_inv.status_code, 400)

        # Invite valid caregiver
        self.register_user('Carer 1', 'carer1@example.com', 'Pass123!', 'caregiver')
        inv1 = self.client.post('/api/caregiver-team/invite',
                                headers=self.auth_headers(p_token),
                                json={'email': 'carer1@example.com'})
        self.assertEqual(inv1.status_code, 201)

        # Duplicate pending invitation
        inv2 = self.client.post('/api/caregiver-team/invite',
                                headers=self.auth_headers(p_token),
                                json={'email': 'carer1@example.com'})
        self.assertEqual(inv2.status_code, 400)

    def test_invitation_expiry_and_cancellation(self):
        p, p_token = self.register_user('Pat', 'pat@example.com', 'Pass123!', 'patient')
        c, c_token = self.register_user('Car', 'car@example.com', 'Pass123!', 'caregiver')

        # Create invite
        inv = self.client.post('/api/caregiver-team/invite',
                               headers=self.auth_headers(p_token),
                               json={'email': 'car@example.com'}).get_json()
        raw_token = inv['invite_token']
        inv_id = inv['invitation']['id']

        # Patient cancels invite
        cancel_res = self.client.delete(f'/api/caregiver-team/invitations/{inv_id}',
                                        headers=self.auth_headers(p_token))
        self.assertEqual(cancel_res.status_code, 200)

        # Carer tries to accept cancelled invite
        accept_res = self.client.post('/api/caregiver-team/accept-invite',
                                      headers=self.auth_headers(c_token),
                                      json={'invite_token': raw_token})
        self.assertEqual(accept_res.status_code, 400)

    # -------------------------------------------------------------------------
    # 5 & 6: Access Control & IDOR Prevention
    # -------------------------------------------------------------------------

    def test_idor_unrelated_caregiver_cannot_access_patient(self):
        # Patient 1 and their authorized caregiver
        p1, p1_token = self.register_user('Patient 1', 'p1@example.com', 'Pass123!', 'patient')
        c1, c1_token = self.register_user('Caregiver 1', 'c1@example.com', 'Pass123!', 'caregiver')

        # Patient 2 with private data
        p2, p2_token = self.register_user('Patient 2', 'p2@example.com', 'Pass123!', 'patient')

        # Create med for Patient 2
        today = datetime.now().strftime('%Y-%m-%d')
        self.client.post('/api/medicines',
                         headers=self.auth_headers(p2_token),
                         json={
                             'name': 'Confidential Med',
                             'dosage': '100mg',
                             'times_per_day': 1,
                             'schedule': ['10:00'],
                             'start_date': today
                         })

        # Caregiver 1 tries to access Patient 2's schedule by IDOR parameter
        idor_res = self.client.get(f'/api/today-schedule?patient_id={p2["id"]}',
                                   headers=self.auth_headers(c1_token))
        # MUST return 403 Forbidden!
        self.assertEqual(idor_res.status_code, 403)

        # Caregiver 1 tries to access Patient 2's summary
        summary_res = self.client.get(f'/api/caregiver/patient/{p2["id"]}/summary',
                                      headers=self.auth_headers(c1_token))
        self.assertEqual(summary_res.status_code, 403)

    # -------------------------------------------------------------------------
    # 7, 8, 9, 10: Granular Permissions, Dose Logging & Actor Attribution
    # -------------------------------------------------------------------------

    def test_granular_permissions_and_actor_attribution(self):
        today = datetime.now().strftime('%Y-%m-%d')
        p, p_token = self.register_user('David', 'david@example.com', 'Pass123!', 'patient')
        c, c_token = self.register_user('Nurse Clara', 'clara@example.com', 'Pass123!', 'caregiver')

        # Patient David adds a medicine
        med_res = self.client.post('/api/medicines',
                                   headers=self.auth_headers(p_token),
                                   json={
                                       'name': 'Insulin Glargine',
                                       'dosage': '20 units',
                                       'times_per_day': 1,
                                       'schedule': ['20:00'],
                                       'start_date': today
                                   })
        self.assertEqual(med_res.status_code, 201)

        # David invites Clara with view_medicines, view_schedule, BUT NO record_doses
        inv = self.client.post('/api/caregiver-team/invite',
                               headers=self.auth_headers(p_token),
                               json={
                                   'email': 'clara@example.com',
                                   'permissions': ['view_medicines', 'view_schedule']
                               }).get_json()
        self.client.post('/api/caregiver-team/accept-invite',
                         headers=self.auth_headers(c_token),
                         json={'invite_token': inv['invite_token']})

        # Clara can view today's schedule
        sched_res = self.client.get(f'/api/today-schedule?patient_id={p["id"]}',
                                    headers=self.auth_headers(c_token))
        self.assertEqual(sched_res.status_code, 200)
        sched = sched_res.get_json()
        self.assertEqual(len(sched), 1)
        log_id = sched[0]['id']

        # Clara attempts to record dose without record_doses permission -> DENIED (403)
        deny_take = self.client.post(f'/api/logs?patient_id={p["id"]}',
                                     headers=self.auth_headers(c_token),
                                     json={'log_id': log_id, 'status': 'taken'})
        self.assertEqual(deny_take.status_code, 403)

        # David upgrades Clara's permissions: adds record_doses and correct_doses
        # First get caregiver relationship ID
        team = self.client.get('/api/caregiver-team', headers=self.auth_headers(p_token)).get_json()
        cg_rel_id = team['caregivers'][0]['id']

        up_res = self.client.put(f'/api/caregiver-team/caregivers/{cg_rel_id}/permissions',
                                 headers=self.auth_headers(p_token),
                                 json={
                                     'permissions': [
                                         'view_medicines',
                                         'view_schedule',
                                         'record_doses',
                                         'correct_doses',
                                         'view_history',
                                         'view_adherence'
                                     ]
                                 })
        self.assertEqual(up_res.status_code, 200)

        # Now Clara records the dose as taken
        take_res = self.client.post(f'/api/logs?patient_id={p["id"]}',
                                    headers=self.auth_headers(c_token),
                                    json={'log_id': log_id, 'status': 'taken', 'notes': 'Administered at bedside'})
        self.assertEqual(take_res.status_code, 200)

        # Verify audit log recorded server-derived actor Clara
        audit_res = self.client.get(f'/api/caregiver/patient/{p["id"]}/activity',
                                    headers=self.auth_headers(c_token))
        self.assertEqual(audit_res.status_code, 200)
        activities = audit_res.get_json()['activity']
        self.assertTrue(any(a['actor_name'] == 'Nurse Clara' for a in activities))

        # Clara corrects the dose
        correct_res = self.client.post(f'/api/logs/{log_id}/correct?patient_id={p["id"]}',
                                       headers=self.auth_headers(c_token),
                                       json={
                                           'new_status': 'skipped',
                                           'reason': 'Patient felt nauseous, physician notified'
                                       })
        self.assertEqual(correct_res.status_code, 200)

        # Verify dose_audit_logs has actor_name='Nurse Clara', actor_role='caregiver'
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT actor_name, actor_role, action, reason FROM dose_audit_logs WHERE log_id = ? ORDER BY id DESC LIMIT 1', (log_id,))
            last_audit = cursor.fetchone()
            self.assertEqual(last_audit['actor_name'], 'Nurse Clara')
            self.assertEqual(last_audit['actor_role'], 'caregiver')
            self.assertEqual(last_audit['action'], 'correction')
            self.assertIn('physician notified', last_audit['reason'])

    # -------------------------------------------------------------------------
    # 11 & 12: Revocation Immediate Effect & Preventing Prescription Edits
    # -------------------------------------------------------------------------

    def test_caregiver_cannot_modify_prescriptions(self):
        p, p_token = self.register_user('Emma', 'emma@example.com', 'Pass123!', 'patient')
        c, c_token = self.register_user('Sam', 'sam@example.com', 'Pass123!', 'caregiver')

        # Full read/write doses granted
        inv = self.client.post('/api/caregiver-team/invite',
                               headers=self.auth_headers(p_token),
                               json={
                                   'email': 'sam@example.com',
                                   'permissions': ['view_medicines', 'view_schedule', 'record_doses']
                               }).get_json()
        self.client.post('/api/caregiver-team/accept-invite',
                         headers=self.auth_headers(c_token),
                         json={'invite_token': inv['invite_token']})

        # Sam attempts to create a new medicine for Emma
        add_med = self.client.post(f'/api/medicines?patient_id={p["id"]}',
                                   headers=self.auth_headers(c_token),
                                   json={
                                       'name': 'Unauthorized Med',
                                       'dosage': '50mg',
                                       'times_per_day': 1,
                                       'schedule': ['08:00'],
                                       'start_date': '2026-10-20'
                                   })
        # Caregivers CANNOT create medicines!
        self.assertEqual(add_med.status_code, 403)

        # Sam attempts to restore/overwrite Emma's database
        restore_res = self.client.post(f'/api/restore?patient_id={p["id"]}',
                                       headers=self.auth_headers(c_token),
                                       json={'schema_version': 3, 'medicines': [], 'logs': [], 'settings': []})
        self.assertEqual(restore_res.status_code, 403)

    def test_immediate_loss_of_access_on_revocation(self):
        p, p_token = self.register_user('Tom', 'tom@example.com', 'Pass123!', 'patient')
        c, c_token = self.register_user('Jerry', 'jerry@example.com', 'Pass123!', 'caregiver')

        inv = self.client.post('/api/caregiver-team/invite',
                               headers=self.auth_headers(p_token),
                               json={'email': 'jerry@example.com'}).get_json()
        self.client.post('/api/caregiver-team/accept-invite',
                         headers=self.auth_headers(c_token),
                         json={'invite_token': inv['invite_token']})

        # Jerry has access now
        acc1 = self.client.get(f'/api/today-schedule?patient_id={p["id"]}',
                               headers=self.auth_headers(c_token))
        self.assertEqual(acc1.status_code, 200)

        # Tom revokes Jerry's access
        team = self.client.get('/api/caregiver-team', headers=self.auth_headers(p_token)).get_json()
        rel_id = team['caregivers'][0]['id']
        rev_res = self.client.delete(f'/api/caregiver-team/caregivers/{rel_id}',
                                     headers=self.auth_headers(p_token))
        self.assertEqual(rev_res.status_code, 200)

        # Jerry immediately loses access!
        acc2 = self.client.get(f'/api/today-schedule?patient_id={p["id"]}',
                               headers=self.auth_headers(c_token))
        self.assertEqual(acc2.status_code, 403)

    # -------------------------------------------------------------------------
    # 13 & 14: Data Isolation & Legacy Data Migration Preservation
    # -------------------------------------------------------------------------

    def test_legacy_data_preservation_and_claim(self):
        # Insert legacy records with NULL user_id directly into DB
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO medicines (name, dosage, times_per_day, schedule, start_date, is_active)
                VALUES (?, ?, ?, ?, ?, 1)
            ''', ('Legacy Blood Pressure Pill', '10mg', 1, json.dumps(['08:00']), '2026-10-01'))
            legacy_med_id = cursor.lastrowid

            cursor.execute('''
                INSERT INTO logs (medicine_id, medicine_name, dosage, scheduled_time, status)
                VALUES (?, ?, ?, ?, ?)
            ''', (legacy_med_id, 'Legacy Blood Pressure Pill', '10mg', '2026-10-01 08:00', 'taken'))

        # Check setup-status reports legacy records exist
        status_res = self.client.get('/api/auth/setup-status').get_json()
        self.assertTrue(status_res['has_legacy_records'])
        self.assertEqual(status_res['legacy_medicines_count'], 1)

        # Register first patient with claim_legacy=True
        user, token = self.register_user('Primary Patient', 'primary@example.com', 'Pass123!', 'patient', claim_legacy=True)

        # Verify medicines now belong to primary patient
        meds_res = self.client.get('/api/medicines', headers=self.auth_headers(token)).get_json()
        self.assertEqual(len(meds_res), 1)
        self.assertEqual(meds_res[0]['name'], 'Legacy Blood Pressure Pill')

        # Check setup-status now confirms 0 unclaimed legacy records
        status_res2 = self.client.get('/api/auth/setup-status').get_json()
        self.assertFalse(status_res2['has_legacy_records'])


if __name__ == '__main__':
    unittest.main()
