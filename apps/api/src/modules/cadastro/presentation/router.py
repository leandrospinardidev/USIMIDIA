from typing import Annotated

from fastapi import APIRouter, Depends

from core.security import UserRole, require_roles

router = APIRouter(prefix="/cadastro", tags=["Cadastro"])


@router.get("/ping")
def ping_cadastro() -> dict[str, str]:
    return {"module": "cadastro", "status": "ok"}


@router.get("/admin-check")
def admin_check(
    _: Annotated[UserRole, Depends(require_roles(UserRole.ADMIN, UserRole.PCP))]
) -> dict[str, str]:
    return {"access": "granted"}
