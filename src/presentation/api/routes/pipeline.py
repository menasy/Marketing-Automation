"""FastAPI router for pipeline execution endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status

from src.application.dto.pipeline_request import PipelineRequest
from src.application.dto.pipeline_response import PipelineResponse
from src.application.use_cases.run_pipeline import RunPipelineUseCase
from src.presentation.api.dependencies import get_run_pipeline_use_case

router = APIRouter(prefix="/api/v1/pipeline", tags=["Pipeline"])


@router.post(
    "/run",
    response_model=PipelineResponse,
    status_code=status.HTTP_200_OK,
    summary="Execute End-to-End Anomaly Detection Pipeline",
    description=(
        "Ingests Google/Meta advertising CSVs, normalizes currency/grain, "
        "computes historical rolling baseline, detects anomalies, compiles dossier, "
        "runs agent reasoning, writes deliverables, and dispatches Slack notifications."
    ),
)
async def run_pipeline(
    request: PipelineRequest,
    use_case: RunPipelineUseCase = Depends(get_run_pipeline_use_case),  # noqa: B008
) -> PipelineResponse:
    """Executes full anomaly detection pipeline asynchronously and returns summary response."""
    result = await use_case.execute(request)
    response = PipelineResponse.from_domain(result)

    if result.status == "failed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Pipeline execution failed during processing.",
        )

    return response
