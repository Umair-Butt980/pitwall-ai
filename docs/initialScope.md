Project Name: PitWall AI
Type: Full Stack AI-Powered Portfolio Project
Architecture: Modular Monolith

===========================================
ONE LINE PITCH
===========================================
An AI-powered F1 race prediction platform 
that orchestrates multiple specialized 
LangGraph agents to analyze driver 
performance, weather, car data and race 
strategy — delivering podium predictions 
with detailed AI reasoning.

===========================================
TECH STACK
===========================================

Frontend:
- Next.js 14 (App Router)
- TypeScript
- Tailwind CSS (dark F1 themed UI)
- Recharts (probability/stats charts)
- Framer Motion (animations)
- Axios (API calls)

Backend:
- Python 3.11
- FastAPI
- LangGraph (multi-agent orchestration)
- LangChain Anthropic (Claude Sonnet 4.5)
- Motor (async MongoDB driver)
- Redis (response caching)
- Pydantic (data validation)

Database:
- MongoDB Atlas (free tier)

Cache:
- Upstash Redis (free tier)

Data Sources:
- FastF1 Python library (telemetry + historical)
- OpenF1 API (live race data)
- Jolpica/Ergast API (historical results)
- OpenWeatherMap API (weather forecasts)

DevOps:
- Docker + Docker Compose (local development)
- AWS EC2 t2.micro (backend deployment)
- Vercel (frontend deployment)
- GitHub (monorepo)

===========================================
REPOSITORY STRUCTURE
===========================================

pitwall-ai/                    ← monorepo root
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── main.py                ← FastAPI entry point
│   ├── config.py              ← env vars + settings
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── orchestrator.py    ← LangGraph workflow
│   │   ├── weather_agent.py   ← weather analysis
│   │   ├── driver_agent.py    ← driver performance
│   │   ├── car_agent.py       ← car + team analysis
│   │   ├── track_agent.py     ← circuit characteristics
│   │   ├── strategy_agent.py  ← pit stop strategy
│   │   └── prediction_agent.py← Claude final prediction
│   ├── services/
│   │   ├── __init__.py
│   │   ├── fastf1_service.py  ← FastF1 data fetching
│   │   ├── openf1_service.py  ← OpenF1 API calls
│   │   ├── ergast_service.py  ← historical results
│   │   └── weather_service.py ← OpenWeatherMap calls
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── predictions.py     ← prediction endpoints
│   │   ├── races.py           ← race data endpoints
│   │   └── drivers.py        ← driver stats endpoints
│   ├── models/
│   │   ├── __init__.py
│   │   ├── prediction.py      ← prediction schemas
│   │   └── race.py            ← race schemas
│   └── database/
│       ├── __init__.py
│       └── connection.py      ← MongoDB connection
│
├── frontend/
│   ├── Dockerfile
│   ├── package.json
│   └── src/
│       ├── app/
│       │   ├── page.tsx           ← home/race selector
│       │   ├── predict/
│       │   │   └── [race]/
│       │   │       └── page.tsx   ← prediction results
│       │   └── history/
│       │       └── page.tsx       ← past predictions
│       ├── components/
│       │   ├── RaceSelector.tsx
│       │   ├── PredictionCard.tsx
│       │   ├── DriverChart.tsx
│       │   ├── AgentStatus.tsx
│       │   └── ReasoningPanel.tsx
│       └── lib/
│           └── api.ts
│
├── docker-compose.yml
├── .env.example
└── README.md

===========================================
MULTI-AGENT ARCHITECTURE
===========================================

Flow:
User selects race → API receives request
→ LangGraph Orchestrator starts
→ 5 agents run in parallel:
   1. Weather Agent
   2. Driver Performance Agent
   3. Car Performance Agent
   4. Track Analysis Agent
   5. Strategy Agent
→ All outputs fed to Prediction Agent
→ Claude Sonnet synthesizes everything
→ Returns structured prediction

Agent Details:

1. WEATHER AGENT
   - Input: race location + date
   - Source: OpenWeatherMap API
   - Output: {
       temperature: number,
       conditions: string,
       rain_probability: number,
       wet_race_likely: boolean
     }

2. DRIVER PERFORMANCE AGENT
   - Input: race name + year
   - Source: FastF1 + Ergast
   - Output: {
       drivers: [{
         name: string,
         track_wins: number,
         track_podiums: number,
         avg_finish_position: number,
         current_form: number,
         qualifying_pace: number
       }]
     }

3. CAR PERFORMANCE AGENT
   - Input: current season + track type
   - Source: FastF1
   - Output: {
       teams: [{
         name: string,
         car_type: string,
         recent_performance: number,
         reliability_score: number
       }]
     }

4. TRACK ANALYSIS AGENT
   - Input: circuit name
   - Source: Ergast + FastF1
   - Output: {
       circuit_type: string,
       overtaking_difficulty: string,
       tire_degradation: string,
       safety_car_probability: number,
       key_characteristics: string[]
     }

5. STRATEGY AGENT
   - Input: track data + tire data
   - Source: FastF1 + OpenF1
   - Output: {
       optimal_pit_windows: number[],
       tire_compounds: string[],
       undercut_opportunity: boolean,
       safety_car_impact: string
     }

6. PREDICTION AGENT (Claude Sonnet 4.5)
   - Input: all 5 agent outputs combined
   - Output: {
       winner: string,
       podium: [string, string, string],
       confidence: number,
       reasoning: string,
       alternative_scenario: string,
       driver_probabilities: [{
         driver: string,
         probability: number
       }]
     }

===========================================
API ENDPOINTS
===========================================

POST /api/predictions/predict
Body: { race: string, year: number }
Returns: full prediction object

GET /api/races
Returns: all 2026 F1 races list

GET /api/races/{race_name}/history
Returns: historical results at circuit

GET /api/predictions/history
Returns: all past predictions + accuracy

GET /api/drivers/{driver_id}/stats/{circuit}
Returns: driver stats at specific circuit

GET /health
Returns: { status: "ok" }

===========================================
MONGODB COLLECTIONS
===========================================

predictions:
{
  _id: ObjectId,
  race: string,
  year: number,
  predicted_winner: string,
  predicted_podium: string[],
  confidence: number,
  reasoning: string,
  alternative_scenario: string,
  driver_probabilities: object[],
  agents_output: object,
  actual_winner: string | null,
  was_correct: boolean | null,
  created_at: datetime
}

races:
{
  _id: ObjectId,
  name: string,
  circuit: string,
  location: string,
  country: string,
  date: datetime,
  round: number,
  year: number
}

===========================================
ENVIRONMENT VARIABLES
===========================================

# Claude API
ANTHROPIC_API_KEY=

# Weather
OPENWEATHERMAP_API_KEY=

# MongoDB
MONGODB_URL=mongodb+srv://...

# Redis
REDIS_URL=

# App
ENVIRONMENT=development
FRONTEND_URL=http://localhost:3000
BACKEND_URL=http://localhost:8000

# Frontend
NEXT_PUBLIC_API_URL=http://localhost:8000

===========================================
DOCKER COMPOSE SERVICES
===========================================

Services:
1. backend  → FastAPI app (port 8000)
2. frontend → Next.js app (port 3000)
3. redis    → Redis cache (port 6379)

MongoDB is external (Atlas free tier)
Redis can be local for dev, Upstash for prod

===========================================
FEATURES
===========================================

1. RACE PREDICTION
   - Select any 2026 F1 race
   - Trigger multi-agent analysis
   - View predicted winner + podium
   - See confidence percentage
   - Read AI reasoning explanation
   - View alternative race scenarios

2. DRIVER COMPARISON
   - Head to head at specific circuit
   - Current season form chart
   - Historical podium rate
   - Qualifying vs race pace

3. PREDICTION HISTORY
   - All past predictions stored
   - Compare prediction vs actual result
   - Overall accuracy percentage
   - Per-circuit accuracy breakdown

4. LIVE AGENT STATUS
   - Show each agent working in real time
   - Progress indicator per agent
   - Agent output summary visible

5. RACE CALENDAR
   - Full 2026 season calendar
   - Upcoming race countdown
   - Past race results

===========================================
DEPLOYMENT
===========================================

Local Development:
- Docker Compose (all services)
- .env file for secrets

Production:
- Frontend → Vercel (free)
- Backend → AWS EC2 t2.micro (free 12 months)
- Database → MongoDB Atlas (free)
- Redis → Upstash (free)

===========================================
DEVELOPMENT PHASES
===========================================

Phase 1 — Foundation:
- Repo setup + folder structure
- docker-compose.yml
- FastAPI hello world in Docker
- MongoDB connection
- Redis connection
- Next.js in Docker
- All services communicating

Phase 2 — Data Layer:
- FastF1 service
- OpenF1 service
- Ergast service
- Weather service
- Redis caching for all services

Phase 3 — AI Agents:
- LangGraph workflow skeleton
- All 6 agents implemented
- Full pipeline end to end working
- Structured outputs validated

Phase 4 — Frontend:
- Race selector
- Prediction results page
- Driver probability charts
- Agent status live display
- Prediction history
- F1 dark theme

Phase 5 — Polish + Deploy:
- Back-test against 2025 races
- Accuracy metrics
- EC2 deployment
- Vercel deployment
- Demo video
- LinkedIn post
- Resume update

===========================================
IMPORTANT NOTES FOR DEVELOPMENT
===========================================

- Developer has no prior Python experience
  → explain Python concepts as we go
  → compare with JavaScript equivalents

- Developer has no prior Docker experience
  → explain each Docker concept clearly
  → start simple, add complexity gradually

- Developer knows: React, Next.js, Node.js,
  NestJS, LangGraph, MongoDB, AWS basics

- Goal: learn Python + Docker while building
  a production-grade portfolio project

- Preferred style: concise explanations,
  no unnecessary verbosity, code first

===========================================