from fastapi import APIRouter

from modules.cadastro.presentation.router import router as cadastro_router
from modules.engenharia_bom.presentation.router import router as engenharia_bom_router
from modules.estoque_retalhos.presentation.router import router as estoque_router
from modules.mes_apontamentos.presentation.router import router as mes_router
from modules.orcamentos.presentation.router import router as orcamentos_router
from modules.ordens_producao.presentation.router import router as ordens_router

api_router = APIRouter()

api_router.include_router(cadastro_router)
api_router.include_router(engenharia_bom_router)
api_router.include_router(estoque_router)
api_router.include_router(orcamentos_router)
api_router.include_router(ordens_router)
api_router.include_router(mes_router)
