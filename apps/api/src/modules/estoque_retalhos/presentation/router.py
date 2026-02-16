from fastapi import APIRouter

router = APIRouter(prefix="/estoque-retalhos", tags=["Estoque e Retalhos"])


@router.get("/ping")
def ping_estoque() -> dict[str, str]:
    return {"module": "estoque_retalhos", "status": "ok"}
