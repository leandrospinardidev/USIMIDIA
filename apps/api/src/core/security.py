from enum import StrEnum
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status


class UserRole(StrEnum):
    ADMIN = "admin"
    PCP = "pcp"
    OPERADOR = "operador"
    COMPRAS = "compras"


def get_current_role(x_user_role: Annotated[str | None, Header()] = None) -> UserRole:
    if not x_user_role:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Cabecalho X-User-Role nao informado.",
        )

    try:
        return UserRole(x_user_role.lower())
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Perfil invalido: {x_user_role}.",
        ) from exc


def require_roles(*roles: UserRole):
    def _checker(role: UserRole = Depends(get_current_role)) -> UserRole:
        if role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Perfil sem permissao para este recurso.",
            )
        return role

    return _checker
