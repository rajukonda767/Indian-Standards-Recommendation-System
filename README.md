# Indian-Standards-Recommendation-System

An intelligent recommendation and discovery system for Bureau of Indian Standards (BIS) specifications, codes, and compliance standards.

## Project Structure
- `backend/`: Python service for standards search, embedding retrieval, and LLM reasoning.
- `frontend/`: React + TypeScript + Vite web interface.
- `scripts/`: Data ingestion, crawling, and verification utilities.
- `tests/`: Automated evaluation and test suites.

## Getting Started

### Backend Setup
1. Navigate to `backend`:
   ```bash
   cd backend
   ```
2. Configure environment variables:
   ```bash
   cp .env.example .env
   ```

### Frontend Setup
1. Navigate to `frontend`:
   ```bash
   cd frontend
   ```
2. Install dependencies and start the dev server:
   ```bash
   npm install
   npm run dev
   ```
