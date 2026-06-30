# AutoDev Intelligence

## GitHub Repository Analyzer & Build Feasibility Engine

A full-stack developer intelligence tool that automates evaluation of GitHub repositories for buildability, reproducibility, and scalability.

**Samsung PRISM Project**

---

### Architecture
```
Frontend (React + Vite)  →  API (FastAPI)  →  Backend (Python + Docker SDK)
                                              ↓
                                        PostgreSQL  ←→  GitHub REST API
                                              ↓
                                        Docker Sandbox  ←→  Custom Qwen (Ollama)
```

### Tech Stack
| Layer | Technology |
|-------|-----------|
| Frontend | React 18 + Vite |
| API | FastAPI |
| Backend | Python 3.11 |
| Database | PostgreSQL 16 |
| AI | Custom Qwen 2.5 Coder (Ollama) + Ollama fallback |
| Build Sandbox | Docker SDK |

---

## Quick Start

### Prerequisites
- **Python 3.11+**
- **Node.js 20+**
- **Docker Desktop** (for sandboxed builds)
- **PostgreSQL** (or use Docker Compose)
- **GitHub Personal Access Token** ([Create one](https://github.com/settings/tokens))
- **Ollama** with your custom Qwen model created from `Modelfile`

### Option 1: Docker Compose (Recommended)

```bash
# 1. Clone and enter project
cd prism2

# 2. Create .env file in project root
echo "GITHUB_TOKEN=ghp_your_token" > .env
echo "AI_PROVIDER=custom_qwen" >> .env
echo "CUSTOM_QWEN_MODEL=autodev-coder" >> .env

# 3. Start all services
docker-compose up -d

# 4. Open the dashboard
# Frontend: http://localhost:5173
# API Docs: http://localhost:8000/docs
```

### Option 2: Manual Setup

#### Backend
```bash
cd backend

# Create virtual environment
python -m venv venv
venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Create .env file
copy .env.example .env
# Edit .env with your tokens

# Run the API server
uvicorn app.main:app --reload --port 8000
```

#### Frontend
```bash
cd frontend

# Install dependencies
npm install

# Start dev server
npm run dev
```

#### PostgreSQL
```bash
# Using Docker (easiest)
docker run -d --name autodev-db \
  -e POSTGRES_USER=autodev \
  -e POSTGRES_PASSWORD=autodev \
  -e POSTGRES_DB=autodev_db \
  -p 5432:5432 \
  postgres:16-alpine
```

---

## Features

### 1. Input Processing
- Upload Excel files with GitHub repository links
- Single URL quick-analyze mode
- Automatic URL validation and deduplication

### 2. GitHub Scraping
- Repository metadata (stars, forks, description)
- Language breakdown
- Dependency file extraction
- README analysis
- CI/CD configuration detection

### 3. Tech Stack Identification
- Programming languages with percentages
- Framework detection (React, Django, Spring Boot, etc.)
- Database identification
- Structured layers: Frontend / Backend / Database / DevOps

### 4. Build Simulation
- Docker sandbox execution
- Per-language build strategies
- Build log capture
- Timeout and resource limits
- Rule-based fallback when Docker is unavailable

### 5. Feasibility Scoring
- 0-100 weighted score across 6 dimensions
- Classification: Buildable / Buildable with Fixes / Not Buildable

### 6. AI Recommendations
- Google Gemini API for smart fix suggestions
- Severity levels and effort estimates
- Specific fix commands
- Ollama fallback for offline use

### 7. Reports & Dashboard
- Interactive web dashboard with charts
- Excel report generation
- JSON data export
- Tech stack distribution trends

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/upload` | Upload Excel file |
| POST | `/api/upload/url` | Submit GitHub URL |
| GET | `/api/repositories` | List repositories |
| GET | `/api/repositories/{id}` | Get repo detail |
| POST | `/api/analyze/{id}` | Trigger analysis |
| POST | `/api/analyze/batch/{id}` | Batch analysis |
| GET | `/api/dashboard/stats` | Dashboard stats |
| GET | `/api/reports/excel` | Download report |

Full API documentation: `http://localhost:8000/docs`

---

## Team
Samsung PRISM — 5 Members, 4 Months
