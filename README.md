# Copilot Deep Research Showcase

A full-stack demonstration of the **Step-DeepResearch** paper's ReAct-based deep research agent. This application showcases autonomous research capabilities with reasoning, action, and reflection phases.

## Features

- 🔍 **Deep Research Engine** - ReAct loop with planning, tool execution, and reflection
- 📊 **Evidence Tracking** - Source authority ranking and cross-validation
- 📝 **Claim Verification** - Extract and verify claims from research
- 🔄 **Ablation Experiments** - Toggle reflection, authority ranking, todo state, patch editing
- 📈 **Run Comparison** - Compare metrics and claims across runs
- 📋 **Evaluation Framework** - Pairwise human evaluation of outputs

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- OpenAI API key (or compatible endpoint)

### 1. Setup Backend

```bash
cd /workspaces/Step-DeepResearch

# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -e .

# Configure environment
cp .env.example .env
# Add your OPENAI_API_KEY to .env
```

### 2. Start Backend

```bash
python -m backend.main
# Server runs on http://localhost:8001
```

### 3. Start Frontend

```bash
cd frontend
npm install
npm run dev
# Frontend runs on http://localhost:3000
```

## Architecture

```
Frontend (React)  ──WebSocket──>  Backend (FastAPI)  ──>  Agent (ReAct)
     │                                  │                      │
     └── REST API ──────────────────────┘                      │
                                                               │
                                        Tools: WebSearch, Browse, Todo, File, Reflect
```

## Ablation Experiments

Test impact of each capability:

| Toggle | Description |
|--------|-------------|
| `enable_reflection` | Self-critique and cross-validation |
| `enable_authority_ranking` | Source credibility scoring |
| `enable_todo_state` | Task tracking and planning |
| `enable_patch_editing` | Incremental document edits |

## API Endpoints

- `POST /api/runs` - Create research run
- `GET /api/runs` - List runs
- `GET /api/runs/{id}` - Run details
- `GET /api/runs/{id}/report` - Get report
- `GET /api/runs/{id}/compare/{id2}` - Compare runs
- `WS /ws/{run_id}` - Real-time events

## Credits

Based on [Step-DeepResearch](https://github.com/stepfun-ai/StepDeepResearch) paper.
