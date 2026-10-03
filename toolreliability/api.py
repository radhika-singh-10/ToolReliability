from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .agents import ReferenceCommerceAgent, RegressionAgent
from .runner import run_suite
from .scenarios import load_scenarios
from .tools import TOOL_SCHEMAS
from .domain_tools import TOOL_REGISTRY
from .orchestrator import EvaluationHarness, HarnessPolicy
from .scenarios import available_domains, load_domain
from .storage import RunStore

app = FastAPI(title="ToolReliability", version="0.1.0", description="CI/CD evaluation for tool-using AI agents")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"], allow_methods=["*"], allow_headers=["*"])
SCENARIOS = Path(__file__).resolve().parents[1] / "scenarios" / "commerce.yaml"
SCENARIO_DIR = SCENARIOS.parent
STORE = RunStore()


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.get("/api/tools")
def tools():
    legacy = [{"name": name, **schema, "domain": "commerce"} for name, schema in TOOL_SCHEMAS.items()]
    platform = [{"name": spec.name, "domain": spec.domain, "description": spec.description,
                 "required": spec.required, "side_effecting": spec.side_effecting} for spec in TOOL_REGISTRY.values()]
    return legacy + platform


@app.get("/api/suites")
def suites():
    return [{"domain": domain, "scenario_count": len(load_domain(domain, SCENARIO_DIR))}
            for domain in available_domains(SCENARIO_DIR)]


@app.post("/api/harness/runs")
async def create_harness_run(domain: str = "data_analytics", concurrency: int = 8):
    try:
        scenarios = load_domain(domain, SCENARIO_DIR)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
    harness = EvaluationHarness(HarnessPolicy(concurrency=min(max(concurrency, 1), 32)), STORE)
    return await harness.execute(scenarios)


@app.get("/api/harness/runs")
def list_harness_runs(limit: int = 25):
    return STORE.list_runs(min(max(limit, 1), 100))


@app.get("/api/harness/runs/{run_id}")
def get_harness_run(run_id: str):
    run = STORE.get_run(run_id)
    if not run:
        raise HTTPException(404, "evaluation run not found")
    return run


@app.get("/api/scenarios")
def scenarios():
    return load_scenarios(SCENARIOS)


@app.post("/api/runs")
async def create_run(agent: str = "reference"):
    adapters = {"reference": ReferenceCommerceAgent(), "regression": RegressionAgent()}
    if agent not in adapters:
        raise HTTPException(400, "agent must be reference or regression")
    return await run_suite(load_scenarios(SCENARIOS), adapters[agent])
