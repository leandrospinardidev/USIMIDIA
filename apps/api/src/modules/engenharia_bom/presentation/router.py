from fastapi import APIRouter

router = APIRouter(prefix="/engenharia-bom", tags=["Engenharia BOM"])


@router.get("/ping")
def ping_engenharia_bom() -> dict[str, str]:
    return {"module": "engenharia_bom", "status": "ok"}
