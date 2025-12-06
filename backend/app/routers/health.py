from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health", summary="Simple service health check")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}
