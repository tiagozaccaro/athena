from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import StreamingResponse

from athena.jobs import Job, JobManager, JobOut

router = APIRouter(prefix="/jobs", tags=["jobs"])

SSE_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}


def manager(request: Request) -> JobManager:
    return request.app.state.jobs


def _job(request: Request, job_id: str) -> Job:
    job = manager(request).get(job_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such job")
    return job


@router.get("/{job_id}", operation_id="getJob")
def get_job(job_id: str, request: Request) -> JobOut:
    return _job(request, job_id).out()


@router.get(
    "/{job_id}/events",
    operation_id="streamJobEvents",
    response_class=StreamingResponse,
    responses={200: {"content": {"text/event-stream": {}}}},
)
def job_events(job_id: str, request: Request) -> StreamingResponse:
    """Server-Sent Events: `log` (one output line, JSON string) and a final `status`."""
    job = _job(request, job_id)
    return StreamingResponse(job.events(), media_type="text/event-stream", headers=SSE_HEADERS)
