# Curavit — Modern Medicine Tracker (with Caregiver Mode)

Curavit is a production-grade medication management and care team web application built with a **React + Vite** frontend, subtle **React Bits** animations, **Recharts** analytics, and a **Python / Flask** REST API backed by an ACID-compliant **SQLite** database.

Curavit includes a complete, secure **Caregiver Mode** allowing patients to authorize trusted family members, nurses, or caregivers to monitor their medication adherence, review recorded doses, view daily summaries, and help log or correct doses under strict, least-privilege permission controls.

---

## Visual Design Direction & Palette

Designed with a calm, premium healthcare aesthetic:

- **Background**: Warm Off-White (`#F7F7F2`)
- **Primary Accent**: Sage Green (`#829477`)
- **Soft Accent**: Lavender (`#E8E2F5`)
- **Text**: Charcoal (`#303730`)
- **Cards**: White (`#FFFFFF`) with subtle neutral borders (`#E5E5DF`)
- **Status Colors**: Muted Green (Taken), Warm Amber (Overdue/Warning), Muted Red (Missed), Soft Blue (Upcoming)
- **Dark Mode**: Fully supported with deep charcoal surfaces and soft contrast tones.

---

## User Roles & Caregiver Mode Architecture

Curavit enforces strict, server-side Role-Based Access Control (RBAC) with cryptographic tokens and object-level authorization (IDOR prevention):

### 1. Patient Role
- **Owner of medication records and prescription data.**
- Manages medicines, dosage regimens, schedules, and reminders.
- Can invite trusted family members or caregivers by email with custom, granular permissions.
- Can view all active caregivers, inspect their granted permissions, and immediately revoke access at any time.
- Reviews an unalterable audit trail of caregiver activities and dose records.

### 2. Caregiver Role
- Authenticated user authorized by one or more patients.
- Can switch between authorized patients with an active patient selector.
- **Overview & Daily Summary**:
  - Live summary of total scheduled, taken, pending, overdue, and skipped doses.
  - Weekly adherence rates (if `view_adherence` permission is granted).
- **Today's Patient Schedule**:
  - Medicine name, dosage, time, and physician instructions.
  - Can record doses as taken or skipped **only** if the patient explicitly granted `record_doses`.
  - Can correct dose mistakes **only** if explicitly granted `correct_doses`, requiring a mandatory clinical reason and logging a tamper-resistant audit trail.
- **Strict Clinical Safety Boundaries**:
  - Caregivers can **never** add new prescriptions, alter prescribed dosages, change medication schedules, change patient credentials, or export/restore patient databases.

---

## Granular Permissions System

Patients control access on a per-caregiver basis with least-privilege defaults:

| Permission | Description | Default |
| :--- | :--- | :--- |
| `view_medicines` | View prescribed medications, dosages, and instructions | Granted |
| `view_schedule` | View daily scheduled dose times and current statuses | Granted |
| `view_history` | Inspect past historical intake logs and dose records | Disabled |
| `view_adherence` | View 7-day adherence percentages and trend analytics | Disabled |
| `record_doses` | Mark scheduled doses as taken or skipped on patient's behalf | Disabled |
| `correct_doses` | Correct misrecorded doses with mandatory recorded reasons | Disabled (Requires `record_doses`) |

---

## Security, Authentication & Session Handling

- **Password Hashing**: Secure PBKDF2 with SHA-256 password hashing via `werkzeug.security`. Passwords are never stored in plaintext.
- **Session Tokens**: Cryptographically secure 256-bit session tokens (`secrets.token_hex(32)`). Raw tokens are never stored in the database; only SHA-256 hashes are persisted, with automatic 7-day expiration.
- **Browser Storage Security**: Tokens are maintained in `sessionStorage` and React memory, never persisted in localStorage.
- **Object-Level Authorization**: Every endpoint verifies resource ownership (`g.current_user['id'] == patient_id`) or validates an active relationship in `caregiver_relationships`. URL tampering (IDOR) is strictly rejected with HTTP 403 Forbidden.
- **Single-Use Cryptographic Invitations**: Secure URL-safe invitation tokens (`secrets.token_urlsafe(32)`) hashed in the database, with single-use consumption and automatic expiration.
- **Safe Legacy Onboarding**: When upgrading an existing single-user installation, unassigned local records remain protected. The primary patient can link them via the onboarding checkbox or `/api/auth/claim-legacy`.

---

## Key Features

### 1. Patient Dashboard
- Dynamic time-based greeting, date display, daily completion progress bar, and animated **Aurora** gradient with **BlurText**.
- Real-time dose status updates (Taken, Scheduled, Overdue, Skipped).
- Quick dose actions: Take, Snooze (+10 min), and Skip with transaction safety.

### 2. Care Team Management (`/care-team`)
- View all authorized caregivers and their active permissions.
- **Invite Caregiver Modal**: Email entry, granular permission checkboxes, and development invite link generator with one-click copy.
- Edit permissions modal to adjust access levels on the fly.
- Immediate revocation button to cut off access instantaneously.
- Activity audit feed tracking caregiver actions and permission updates.

### 3. Caregiver Dashboard (`/caregiver`)
- Patient selector dropdown for multi-patient management.
- Daily summary card with live dose counts and weekly adherence.
- Today's schedule with permission-gated actions (Take, Skip, Correct).
- Mandatory correction dialog requiring reason and stamping server-derived actor attribution.
- Recent care activity timeline.

### 4. Prescription & Medication Management (`/medicines`)
- Filterable and searchable medication catalog.
- Daily, weekly, and as-needed schedule configurations with slot validations.
- Soft-deactivation preserving all historical dose intake records.

### 5. Dose History & Audit Trail (`/history`)
- Chronological table of all recorded intakes and scheduled events.
- Audit trail detailing previous status, new status, timestamp, actor identity, and correction rationale.

### 6. Analytics (`/analytics`)
- 7-day adherence trends, dose distribution charts, and per-medication compliance rates.
- Future pending doses are excluded from adherence denominators for clinical accuracy.

---

## Tech Stack

### Frontend (`/frontend`)
- **Framework**: React 19 + Vite
- **Routing**: React Router DOM (v7)
- **Icons**: Lucide React
- **Charts**: Recharts
- **Design**: Vanilla CSS Design System with CSS Custom Properties, dark mode, and responsive layout.

### Backend (`/Medicine Tracker`)
- **Framework**: Python, Flask, Flask-CORS
- **Database**: SQLite (`medicines.db`)
- **Authentication**: PBKDF2 password hashing, SHA-256 session tokens, RBAC decorators.

---

## Running the Application

### 1. Start the Flask Backend
```bash
cd "Medicine Tracker"
py app.py
```
> The API server runs at **http://localhost:5000**

### 2. Start the React Frontend
```bash
cd frontend
npm install
npm run dev
```
> The web application runs at **http://localhost:5173**

---

## Automated Test Suite

Curavit includes automated tests executed against isolated temporary databases:

### Run Backend & Regression Tests
```bash
py -m unittest discover -s tests -p "test_backend.py"
```

### Run Caregiver Mode & Security Tests
```bash
py -m unittest discover -s tests -p "test_caregiver_and_auth.py"
```

### Run All Tests Together
```bash
py -m unittest discover -s tests
```
> **20/20 tests passing with 100% success.**

---

## Real-World Deployment Considerations

- **Email Delivery**: The development environment uses a direct single-use invitation link generator. In production, configure an SMTP provider (e.g. Amazon SES, SendGrid) and set the `SMTP_*` environment variables.
- **HTTPS & Cookies**: For internet deployments, serve over TLS/HTTPS with `Secure` and `SameSite=Strict` cookie headers.
- **Production Secret**: Set `SECRET_KEY` and `MEDICINE_DB_PATH` in environment variables before deploying to production.
