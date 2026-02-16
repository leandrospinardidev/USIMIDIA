from fastapi import APIRouter

router = APIRouter(prefix="/orcamentos", tags=["Orcamentos"])


@router.get("/ping")
def ping_orcamentos() -> dict[str, str]:
    return {"module": "orcamentos", "status": "ok"}
