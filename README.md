<div align="center">

# 🏛️ Indian Standards Recommendation System

**An AI-powered procurement copilot for Bureau of Indian Standards (BIS) compliance**

[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-19-61DAFB?style=flat&logo=react&logoColor=black)](https://react.dev/)
[![TypeScript](https://img.shields.io/badge/TypeScript-6-3178C6?style=flat&logo=typescript&logoColor=white)](https://www.typescriptlang.org/)
[![Supabase](https://img.shields.io/badge/Supabase-PostgreSQL-3ECF8E?style=flat&logo=supabase&logoColor=white)](https://supabase.com/)
[![Groq](https://img.shields.io/badge/Groq-LLM-F55036?style=flat)](https://groq.com/)
[![License](https://img.shields.io/badge/License-MIT-blue?style=flat)](LICENSE)

</div>

---

## 📖 Overview

The **Indian Standards Recommendation System** is an intelligent AI-powered platform that helps procurement teams, engineers, and compliance officers discover, audit, and verify Bureau of Indian Standards (BIS) specifications with speed and accuracy.

Built for **Smart India Hackathon (SIH)**, the system leverages semantic search, LLM reasoning, and vector embeddings to recommend the right IS standards from a corpus of 5,500+ BIS standards — in seconds.

---

## ✨ Features

| Feature | Description |
|---|---|
| 🔍 **Semantic Search** | Vector-embedding-powered search across 5,500+ BIS standards |
| 🤖 **AI Recommendations** | Groq LLM reasoning to explain *why* a standard applies to your query |
| 📄 **Document Audit** | Upload tender PDFs/DOCX and auto-extract IS standard mentions |
| ✅ **Compliance Verification** | Cross-reference mentioned standards with the BIS database |
| 📊 **Analytics Dashboard** | Visual charts showing standard coverage and compliance gaps |
| 📥 **Export Reports** | Download audit results as PDF or Excel |

---

## 🏗️ Architecture

```
Indian-Standards-Recommendation-System/
├── backend/              # FastAPI Python backend
│   ├── app/
│   │   ├── routers/      # API route handlers (recommend, audit, bot, standards)
│   │   ├── services/     # Embedding, LLM, and retrieval services
│   │   ├── models/       # Pydantic data models
│   │   ├── parsers/      # PDF / DOCX document parsers
│   │   ├── adapters/     # External API adapters
│   │   ├── jobs/         # Async background job runner
│   │   ├── config.py     # Settings & environment config
│   │   ├── db.py         # Database connection pool
│   │   └── main.py       # FastAPI application entry point
│   ├── routes/           # Additional route definitions
│   ├── services/         # Top-level service utilities
│   ├── migrations/       # Database migration scripts
│   └── schemas.py        # Shared schemas
│
├── frontend/             # React + TypeScript + Vite UI
│   ├── src/
│   │   ├── pages/        # Route-level page components
│   │   ├── components/   # Reusable UI components
│   │   └── utils/        # Utility helpers
│   ├── public/           # Static assets
│   ├── index.html
│   ├── vite.config.ts
│   └── package.json
│
├── scripts/              # Data ingestion & utility scripts
├── tests/                # Evaluation & integration test suites
│   ├── eval/             # LLM evaluation benchmarks
│   └── fixtures/         # Test fixture files
│
├── .env.example          # Environment variable template
└── README.md
```

---

## 🛠️ Tech Stack

### Backend
- **[FastAPI](https://fastapi.tiangolo.com/)** — High-performance async Python API
- **[Supabase](https://supabase.com/)** — PostgreSQL database with vector extension (pgvector)
- **[Groq](https://groq.com/)** — Ultra-fast LLM inference for AI recommendations
- **PyTorch** — Local embedding model inference

### Frontend
- **[React 19](https://react.dev/)** + **[TypeScript](https://www.typescriptlang.org/)**
- **[Vite 8](https://vitejs.dev/)** — Lightning-fast build tool
- **[Tailwind CSS 4](https://tailwindcss.com/)** — Utility-first styling
- **[Framer Motion](https://www.framer.com/motion/)** — Smooth animations
- **[Recharts](https://recharts.org/)** — Analytics charts
- **[React Router 6](https://reactrouter.com/)** — Client-side routing

---

## 🚀 Getting Started

### Prerequisites

- Python 3.11+
- Node.js 18+
- A [Supabase](https://supabase.com/) project with pgvector enabled
- A [Groq](https://console.groq.com/) API key

---

### 1. Clone the Repository

```bash
git clone https://github.com/rajukonda767/Indian-Standards-Recommendation-System.git
cd Indian-Standards-Recommendation-System
```

---

### 2. Backend Setup

```bash
cd backend

# Create and activate a virtual environment
python -m venv venv
venv\Scripts\activate       # Windows
# source venv/bin/activate  # macOS/Linux

# Install dependencies
pip install -r requirements.txt

# Configure environment variables
cp .env.example .env
```

Edit `.env` and fill in your credentials:

```env
DATABASE_URL=postgresql://postgres.[project-ref]:[password]@aws-0-[region].pooler.supabase.com:5432/postgres
SUPABASE_URL=https://[project-ref].supabase.co
SUPABASE_ANON_KEY=your_supabase_anon_key
SUPABASE_SERVICE_ROLE_KEY=your_supabase_service_role_key
GROQ_API_KEY=your_groq_api_key
```

Start the backend server:

```bash
uvicorn app.main:app --reload --port 8000
```

The API will be available at `http://localhost:8000`  
Interactive docs: `http://localhost:8000/docs`

---

### 3. Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Start the development server
npm run dev
```

The UI will be available at `http://localhost:5173`

---

## 📡 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/recommend` | Get AI-recommended BIS standards for a query |
| `GET` | `/standards` | Search and browse standards |
| `POST` | `/audit` | Upload a document for compliance audit |
| `GET` | `/audit/{job_id}` | Poll audit job status |
| `POST` | `/bot` | Chat with the BIS standards assistant |

---

## 🧪 Running Tests

```bash
cd tests

# Run evaluation suite
python -m pytest eval/ -v

# Run a specific test
python eval/run_eval.py
```

---

## 🤝 Contributing

Contributions are welcome! Please follow these steps:

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Commit your changes: `git commit -m 'Add some feature'`
4. Push to the branch: `git push origin feature/your-feature`
5. Open a Pull Request

---

## 📄 License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

---

## 👥 Authors

- **Raju Konda** — [rajukonda767@gmail.com](mailto:rajukonda767@gmail.com)

---

<div align="center">

Built with ❤️ for Smart India Hackathon 2026

</div>
