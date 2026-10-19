# Curavit — Modern Medicine Tracker

Curavit is a modern, full-stack medication management web application built with a **React + Vite** frontend, subtle **React Bits** animations, **Recharts** analytics, and a **Python / Flask** REST API with SQLite database persistence.

---

## 🎨 Visual Design Direction & Palette

Designed with a calm, premium healthcare aesthetic:

- **Background**: Warm Off-White (`#F7F7F2`)
- **Primary Accent**: Sage Green (`#829477`)
- **Soft Accent**: Lavender (`#E8E2F5`)
- **Text**: Charcoal (`#303730`)
- **Cards**: White (`#FFFFFF`) with subtle neutral borders (`#E5E5DF`)
- **Status Colors**: Muted Green (Taken), Warm Amber (Overdue/Warning), Muted Red (Missed), Soft Blue (Upcoming)
- **Dark Mode**: Fully supported with deep charcoal surfaces and soft contrast tones.

---

## 🚀 Key Features

### 1. Dashboard
- **Welcome Banner**: Dynamic time-based greeting, date display, daily completion progress bar, and animated **Aurora** gradient with **BlurText**.
- **Metrics Cards**: Active medicines, Doses taken today, Pending/Upcoming, and 7-Day adherence percentage using **SpotlightCard** and **CountUp** numerical animations.
- **Today's Medication Schedule**: Chronological timeline showing dose status (Taken, Scheduled, Overdue, Skipped).
- **Quick Dose Actions**: "Take Dose", "Snooze" (+10 min), and "Skip Dose" with immediate state reflection and backend synchronization.

### 2. My Medicines
- Filterable and searchable medication catalog.
- Filter by frequency (Daily, Weekly, As-Needed) and sort alphabetically or by start date.
- **Add / Edit Medicine Modal**:
  - Medicine name, dosage, frequency, start date, optional end date.
  - Dynamically configurable schedule time inputs matching doses per day.
  - Special instructions and notes.
- Deactivate medications with a confirmation dialog while safely preserving all historical logs.

### 3. Dose History
- Chronological table of all recorded intakes and scheduled events.
- Filter by date range (Today, 7 days, 30 days, 90 days), status, or individual medicine.
- Real-time search and pagination.
- **Log Extra Dose**: Support for ad-hoc / PRN doses taken on demand.

### 4. Analytics
- **7-Day Trend Chart**: Recharts bar chart showing daily doses taken vs. scheduled.
- **Dose Distribution**: Donut chart illustrating proportions of taken, skipped, and missed doses.
- **Medication Adherence Breakdown**: Individual adherence rates per prescribed medicine.
- Accurate calculations excluding future scheduled doses from denominators.

### 5. Settings & Backups
- In-app reminder toggles, configurable snooze duration (5m, 10m, 15m, 30m), reminder lead times, and language selector.
- Live theme toggle: Light (Sage & Off-White) and Dark (Charcoal).
- **Database Backup Export**: Download a full JSON dump (`/api/export`) of all medicines, logs, and user preferences.
- Live backend connectivity and health check indicator (`/api/health`).

---

## ⚙️ Tech Stack

### Frontend (`/frontend`)
- **Framework**: React 19 + Vite
- **Routing**: React Router DOM (v7)
- **Icons**: Lucide React
- **Charts**: Recharts
- **React Bits Components**:
  - `PillNav`: Animated pill indicator navigation
  - `CountUp`: Eased numerical counter animations (reduced-motion safe)
  - `SpotlightCard`: Cursor-following radial light glow
  - `BlurText`: Smooth blur-in text entrance
  - `Aurora`: Low-opacity ambient background glow
- **Styling**: Vanilla CSS Design System with CSS Custom Properties and responsive breakpoints.

### Backend (`/Medicine Tracker`)
- **Framework**: Python, Flask, Flask-CORS
- **Database**: SQLite (`medicines.db`)
- **Key Enhancements**:
  - **Idempotent Schedule Sync**: Recurring daily dose generation respecting start dates, end dates, and frequencies without duplicate creation.
  - **Safe Database Management**: Preserves existing database records on startup using `CREATE TABLE IF NOT EXISTS`.
  - **Windows UTF-8 Safe**: Configured `sys.stdout` and `sys.stderr` streams for emoji and Unicode stability.
  - **Analytics API**: Aggregates 7-day adherence metrics and per-medication statistics.

---

## 🏃 Running the Application

### Prerequisites
- Python 3.10+ (with `flask` and `flask-cors`)
- Node.js 18+ and npm

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
> The React dashboard runs at **http://localhost:5173**

---

## 🌐 Environment Variables

| Variable | Default | Description |
|---|---|---|
| `VITE_API_BASE_URL` | `http://localhost:5000` | Backend API base URL for fetch requests |

---

## 📋 API Endpoints Summary

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/medicines` | List all active medications |
| `POST` | `/api/medicines` | Add a new medication |
| `PUT` | `/api/medicines/<id>` | Update medication details & schedule |
| `DELETE` | `/api/medicines/<id>` | Deactivate medication (preserves history) |
| `GET` | `/api/today-schedule` | Get today's scheduled doses |
| `GET` | `/api/logs` | Fetch dose history logs with filters |
| `POST` | `/api/logs` | Log dose intake, skip, or snooze |
| `GET` | `/api/statistics` | Dashboard summary metrics |
| `GET` | `/api/analytics` | 7-day adherence trend and breakdown |
| `GET` | `/api/settings` | Retrieve user settings |
| `POST` | `/api/settings` | Update user settings |
| `GET` | `/api/export` | Download full JSON database backup |
| `GET` | `/api/health` | Server connectivity check |
