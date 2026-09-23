from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .agents import ReferenceCommerceAgent, RegressionAgent
from .runner import run_suite
from .scenarios import load_scenarios
from .tools import TOOL_SCHEMAS

app = FastAPI(title="ToolReliability", version="0.1.0", description="CI/CD evaluation for tool-using AI agents")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"], allow_methods=["*"], allow_headers=["*"])
SCENARIOS = Path(__file__).resolve().parents[1] / "scenarios" / "commerce.yaml"


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.get("/api/tools")
def tools():
    return [{"name": name, **schema} for name, schema in TOOL_SCHEMAS.items()]


@app.get("/api/scenarios")
def scenarios():
    return load_scenarios(SCENARIOS)


@app.post("/api/runs")
async def create_run(agent: str = "reference"):
    adapters = {"reference": ReferenceCommerceAgent(), "regression": RegressionAgent()}
    if agent not in adapters:
        raise HTTPException(400, "agent must be reference or regression")
    return await run_suite(load_scenarios(SCENARIOS), adapters[agent])

