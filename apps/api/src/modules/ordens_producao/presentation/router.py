from fastapi import APIRouter

router = APIRouter(prefix="/ordens-producao", tags=["Ordens de Producao"])


@router.get("/ping")
def ping_ordens() -> dict[str, str]:
    return {"module": "ordens_producao", "status": "ok"}
