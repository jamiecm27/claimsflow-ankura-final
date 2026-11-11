# AI-Based Insurance Claim Extraction & Routing Agent

An intelligent insurance claim processing system that extracts, validates, classifies, and routes claim documents automatically using FastAPI and React.

---

# Features

- Upload PDF/TXT documents
- Gemini-powered field extraction and claim routing with rule fallback
- Missing field validation
- Fraud keyword detection
- Intelligent claim routing
- JSON database-backed claim history storage
- Analytics dashboard
- Modern React UI
- FastAPI backend APIs

---

# Tech Stack

## Frontend
- React.js
- Vite
- Axios
- Lucide React
- CSS3

## Backend
- FastAPI
- Python
- PyMuPDF
- Google GenAI SDK
- Regex-based extraction
- JSON file database

---

# Routing Rules

| Condition | Route |
|---|---|
| Estimated damage < $25,000 | Fast-track |
| Missing mandatory fields | Manual Review |
| Fraud keywords detected | Investigation Flag |
| Claim type = Injury | Specialist Queue |
| Otherwise | Standard Queue |

---

# Supported Documents

- PDF
- TXT

---

# Sample Documents

Sample FNOL PDFs are included in:

```text
backend/sample-docs/
```

Use these files from the upload screen to test extraction, PDF preview, Gemini routing, claim history, and dashboard analytics.

---

# Project Structure

```text
fnol-project/
│
├── backend/
│   ├── app.py
│   ├── extractor.py
│   ├── router.py
│   ├── validator.py
│   ├── database.py
│   ├── llm_extractor.py
│   ├── .env.example
│   ├── requirements.txt
│   ├── data/
│   ├── uploads/
│   └── sample-docs/
│
├── public/
├── src/
│   ├── App.jsx
│   ├── App.css
│   └── main.jsx
│
├── package.json
├── vite.config.js
├── README.md
```

---

# Backend Setup

## Navigate to backend

```bash
cd backend
```

## Create virtual environment

### Windows

```bash
python -m venv venv
venv\Scripts\activate
```

### Mac/Linux

```bash
python3 -m venv venv
source venv/bin/activate
```

## Install dependencies

```bash
pip install -r requirements.txt
```

## Run backend tests

```bash
python -m pytest
```

## Add Gemini API key

Copy the example environment file:

```bash
copy .env.example .env
```

Then set your key in `backend/.env`:

```text
GEMINI_API_KEY=your_actual_gemini_api_key
GEMINI_MODEL=gemini-2.5-flash
```

If `GEMINI_API_KEY` is missing or a Gemini call fails, the backend automatically uses the existing regex extractor and rule-based router.

## Run backend server

```bash
python -m uvicorn app:app --reload
```

Backend runs at:

```text
http://127.0.0.1:8000
```

Swagger docs:

```text
http://127.0.0.1:8000/docs
```

Processed claims are stored in:

```text
backend/data/claims.json
```

Available claim history APIs:

```text
GET /claims
DELETE /claims
GET /llm-status
POST /process-fnol
```

---

# Frontend Setup

## Install dependencies

```bash
npm install
```

## Start frontend

```bash
npm run dev
```

Frontend runs at:

```text
http://localhost:5173
```

---

# Sample Workflow

1. Upload FNOL document
2. Extract claim information
3. Validate required fields
4. Detect suspicious claims
5. Route to correct workflow
6. Store processed claim history

---

# Example JSON Output

```json
{
  "extractedFields": {
    "policyNumber": "POL12345",
    "claimType": "Vehicle",
    "estimatedDamage": "18000"
  },
  "missingFields": [],
  "recommendedRoute": "Fast-track",
  "reasoning": "Estimated damage is below $25,000.",
  "extractionMethod": "gemini",
  "llmStatus": {
    "usedGemini": true,
    "model": "gemini-2.5-flash"
  },
  "routingMethod": "gemini",
  "llmRoutingStatus": {
    "usedGemini": true,
    "model": "gemini-2.5-flash"
  }
}
```

---

# Dashboard Pages

- Upload Claim
- Processed Claims
- Fast Track Claims
- Manual Review Claims
- Investigation Claims
- Analytics Dashboard

---

# Future Improvements

- OCR support for scanned documents
- Authentication system
- Real-time analytics
- Cloud deployment
- Fraud detection ML model

---

# Author

Sanket Barde

AI & ML Engineer | Full Stack Developer
