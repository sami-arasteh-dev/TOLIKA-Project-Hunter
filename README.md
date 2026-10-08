# TOLIKA Project Hunter

A monolithic Flask-based sales management and AI analysis system tailored for construction, hospitality, and commercial decoration projects. TOLIKA Project Hunter provides comprehensive CRUD operations for projects, contacts, activities, and tasks, alongside an integrated LLM pipeline for generating strategic recommendations, network visualizations, and campaign plans.

## 📋 Table of Contents
- [Features](#features)
- [Architecture & Tech Stack](#architecture--tech-stack)
- [Prerequisites](#prerequisites)
- [Installation & Setup](#installation--setup)
- [Configuration](#configuration)
- [Usage & API Endpoints](#usage--api-endpoints)
- [Data Import/Export](#data-importexport)
- [Project Structure](#project-structure)
- [Technical Notes](#technical-notes)
- [License](#license)

## ✨ Features
- **RESTful API:** Full CRUD for projects, contacts, activities, tasks, analyses, and saved recommendations.
- **Composite Scoring Algorithm:** Deterministic scoring (0–100) based on budget, stage, contract status, team access, and material-specific opportunities.
- **AI-Driven Analysis:** Configurable LLM integration generates structured outputs including network graphs, recommendations, campaigns, risks, and priority actions.
- **Sales Pipeline Board:** Kanban-style visualization across stages: Lead → Opportunity → Meeting → Scope → Proposal → Negotiation → Contract.
- **Activity & Task Tracking:** Log interactions, set next actions, and monitor overdue tasks with automatic project timestamp updates.
- **Data Import/Export:** Bulk import via JSON, CSV, or XLSX; export datasets to JSON for archival or reporting.
- **Configurable LLM Settings:** Adjust base URL, API key, model, temperature, max tokens, and system prompts via UI or database.
- **Responsive RTL Interface:** Professional Persian-language frontend built with vanilla HTML/CSS/JS and SVG graph rendering.

## 🏗 Architecture & Tech Stack
| Layer | Technology |
|-------|------------|
| Backend | Python 3.8+, Flask |
| Database | SQLite3 (`tolika_sales.sqlite3`) |
| AI Integration | `openai` library (OpenAI-compatible endpoints) |
| Data Processing | `openpyxl`, `csv`, `json` |
| Frontend | Vanilla JavaScript, HTML5, CSS3, SVG |
| Architecture | Monolithic Flask app + SPA frontend |

## 📦 Prerequisites
- Python 3.8 or higher
- `pip` package manager
- SQLite3 (bundled with Python)
- OpenAI-compatible API endpoint (e.g., local LLM gateway, third-party provider)

## 🛠 Installation & Setup
1. Clone or extract the project directory.
2. Install dependencies:
   ```bash
   pip install flask openai openpyxl
   ```
3. Initialize the application:
   ```bash
   python app.py
   ```
4. Access the interface at `http://127.0.0.1:8500`.

The application automatically creates the SQLite database and required tables on first run.

## ⚙️ Configuration
- **LLM Settings:** Navigate to the `Settings` tab in the UI to configure `base_url`, `api_key`, `model`, `temperature`, `max_tokens`, and `system_prompt`.
- **API Key Masking:** The UI masks stored API keys (`********`) for security.
- **Web Signals Flag:** The `web_enabled` setting controls whether external web signals are requested during AI analysis (default: `1`).
- **Database:** All data persists in `tolika_sales.sqlite3`. No external database server is required.

## 🌐 Usage & API Endpoints
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | Serves the main SPA interface |
| `GET/POST` | `/api/projects` | List or create projects |
| `PUT` | `/api/projects/<id>` | Update a project |
| `DELETE` | `/api/projects/<id>` | Delete a project |
| `GET` | `/api/dashboard` | Return metrics, top projects, and overdue tasks |
| `GET/POST` | `/api/contacts` | List or create contacts |
| `GET/POST` | `/api/activities` | List or log activities |
| `GET/POST/PUT` | `/api/tasks` | Manage tasks |
| `GET/POST` | `/api/settings` | Retrieve or update LLM/configuration settings |
| `POST` | `/api/analyze` | Trigger AI analysis for a project or full pipeline |
| `GET` | `/api/analyses` | List historical analyses |
| `POST` | `/api/recommendations/save` | Save AI-generated recommendations |
| `GET` | `/api/recommendations/saved` | Retrieve saved recommendations |
| `GET` | `/api/export/<kind>` | Download JSON export (`projects`, `activities`, `analyses`) |
| `POST` | `/api/import` | Bulk import projects via file upload |

## 📥 Data Import/Export
- **Import:** Supports `.json`, `.csv`, and `.xlsx` files. The importer maps standard and Persian field names (e.g., `نام پروژه` → `name`, `ارزش احتمالی` → `estimated_value`).
- **Export:** Generates timestamped JSON files in the `exports/` directory and triggers a browser download.

## 📁 Project Structure
```
tolika_project/
├── app.py              # Flask backend, DB schema, API routes, AI engine
├── index.html          # Single-page frontend, UI, routing, SVG rendering
├── tolika_sales.sqlite3 # SQLite database (auto-generated)
└── exports/            # Directory for generated JSON exports
```

## 🔍 Technical Notes
- **Scoring Logic:** The `score()` function calculates a weighted composite: `0.20*100 + 0.15*wood + 0.10*metal + 0.15*contract + 0.15*access + 0.10*stage + 0.10*budget + 0.05*fit`.
- **AI Parsing Fallback:** The `analyze()` function attempts strict JSON parsing first, then falls back to regex extraction (`\{.*\}`) if the LLM wraps output in markdown code blocks.
- **Foreign Keys:** `PRAGMA foreign_keys=ON` is enabled. `ON DELETE CASCADE` applies to contacts/activities/tasks; `ON DELETE SET NULL` applies to analyses.
- **Security:** API keys are stored in plaintext in SQLite. The UI masks them on retrieval. No authentication middleware is implemented; intended for internal/private network use.
- **File Upload Limit:** `MAX_CONTENT_LENGTH` is set to 25MB.

## 📜 License
This project is provided as an open-source enterprise demo. Use, modification, and distribution are permitted under standard open-source practices. No warranty is provided for production deployment without additional security hardening and access controls.
