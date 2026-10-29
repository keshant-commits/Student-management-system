# Student Management System

A Management system for student with the help of APAAR ID.

## Structure
- `backend/` FastAPI backend (auth, RBAC, validation engine, ML anomaly detection, signed records)
- `frontend/` React + Vite + Tailwind dashboard
- `mock-apaar-service/` Mock APAAR registry
- `sample-data/` Demo CSV files
- `docs/` Architecture, API, security docs
- `scripts/` Setup, seeding, key generation


## Docker Development Setup

1. Copy `.env.example` to `.env`:

   ```powershell
   Copy-Item .env.example .env
   ```

2. Replace placeholder values in `.env` with local development-only values.

3. Start services:

   ```powershell
   docker compose up -d --build
   ```

4. Check status:

   ```powershell
   docker compose ps
   ```

5. Stop services:

   ```powershell
   docker compose down
   ```
