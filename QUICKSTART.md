# ExpenseGuard — Quick Start

## 1. Setup (first time only)

```bash
# Create virtual environment
python -m venv venv

# Activate (Windows)
venv\Scripts\activate

# Activate (Linux/Mac)
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create .env file
copy .env.example .env

# Edit .env and paste your Google Gemini API key:
# GOOGLE_API_KEY=your_key_here
# Get a key at: https://aistudio.google.com/app/apikey

# Seed the mock database
python -m mcp_server.seed_data
```

## 2. Run Tests

```bash
venv\Scripts\python.exe -m pytest tests/ -v
```

All **27 tests** should pass. These verify:
- Policy compliance checks (within/over limit, vendor restrictions)
- Risk escalation (duplicates, budget constraints)
- Security features (PII redaction, RBAC)
- Audit trail immutability
- Agent trace correctness (new in Phase 2)

## 3. Try the CLI

```bash
# Submit a compliant expense (auto-approved)
python cli/expenseguard.py submit \
  --employee E1001 \
  --amount 23.50 \
  --category meals \
  --vendor Chipotle \
  --date 2026-06-25

# Submit a policy violation (rejected)
python cli/expenseguard.py submit \
  --employee E1001 \
  --amount 890 \
  --category travel \
  --vendor "United Airlines" \
  --date 2026-06-25

# Submit a flagged expense (escalated to manager)
python cli/expenseguard.py submit \
  --employee E1001 \
  --amount 345 \
  --category travel \
  --vendor "Delta Airlines" \
  --date 2026-06-25

# View audit trail
python cli/expenseguard.py audit

# Review a specific expense
python cli/expenseguard.py review --id EXP-ABC123

# Look up policy rules
python cli/expenseguard.py policy --category travel --role employee
```

## 4. Run the Backend API (optional — needs Google API key)

```bash
# Start the FastAPI server
python -m uvicorn api.main:app --reload --port 8000

# In a browser, open:
# http://localhost:8000/api/health
```

Test the API:
```bash
curl -X POST http://localhost:8000/api/expenses/submit \
  -H "Content-Type: application/json" \
  -H "X-User-ID: E1001" \
  -d '{
    "employee_id": "E1001",
    "description": "Team lunch",
    "amount": 45.00,
    "category": "meals",
    "date": "2026-06-25",
    "receipt_text": "Chipotle\nTotal: $45.00"
  }'
```

## 5. Run the Frontend (optional — requires Node.js)

```bash
cd frontend
npm install
npm run dev

# Open: http://localhost:3000
# - Submit page with animated pipeline + full trace
# - Audit page with expandable Phase 2 traces
# - Review page with Approve/Reject buttons
```

## 6. Docker Deployment (single command, full stack)

```bash
# Ensure .env exists with GOOGLE_API_KEY
docker-compose up --build

# Services will be available at:
# - API: http://localhost:8000
# - Frontend: http://localhost:3000
```

## Demo Scenarios

The CLI and frontend include 7+ pre-built demo scenarios:
1. ✅ Compliant meal ($23.50) → auto-approved
2. ❌ Amount violation ($890 travel) → rejected
3. ⚠️ Pre-approval needed ($350 travel) → escalated
4. ❌ Vendor not approved (software) → rejected
5. ⚠️ Duplicate submission → escalated
6. ❌ Entertainment not covered → rejected
7. ✅ PII redaction demo (card number in receipt) → auto-approved with redacted data

## Troubleshooting

**Tests fail with "No module named 'google'"**
→ Tests run without google-genai. If you see this, the conditional import didn't work — check agents/intake.py line 14.

**"Database not found"**
→ Run: `python -m mcp_server.seed_data`

**API returns 500 "GOOGLE_API_KEY not set"**
→ Create .env file (copy .env.example) and add your API key.

**Frontend can't connect to API**
→ Ensure API is running on port 8000. Check NEXT_PUBLIC_API_URL in frontend/.env.local.
