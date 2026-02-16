from fastapi import APIRouter

router = APIRouter(prefix="/mes-apontamentos", tags=["MES Apontamentos"])


@router.get("/ping")
def ping_mes() -> dict[str, str]:
    return {"module": "mes_apontamentos", "status": "ok"}
