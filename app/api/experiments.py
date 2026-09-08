from fastapi import APIRouter, HTTPException, Depends
from app.schemas import ExperimentRunRequest, ExperimentResultOut
from experiments.run_experiment import ExperimentRunner
import os
import pandas as pd

router = APIRouter(tags=["Experiments & Baseline Benchmarking"])

@router.post("/experiments/run", response_model=ExperimentResultOut)
def run_experiment_endpoint(req: ExperimentRunRequest):
    """Trigger reproducible experiment comparing Baseline vs HybridFlowGuard."""
    try:
        results = ExperimentRunner.run(scenario=req.scenario, num_flows=req.num_flows)
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Experiment execution failed: {str(e)}")

@router.get("/experiments/results")
def get_experiment_results():
    """Retrieve historical experiment benchmark runs."""
    results_file = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "experiments", "results.csv")
    if not os.path.exists(results_file):
        # Run a default experiment to produce initial results if none exists
        res = ExperimentRunner.run("90% congestion")
        return [res]
    
    try:
        df = pd.read_csv(results_file)
        return df.to_dict(orient="records")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read experiment results: {str(e)}")
