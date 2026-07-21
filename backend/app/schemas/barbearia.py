# Shim de compatibilidade — sera removido junto com routes/barbearias.py e
# routes/barbearia_funcionamento.py (rotas mortas, nao registradas em main.py).
from app.schemas.estabelecimento import (
    EstabelecimentoAdminCreate as BarbeariaAdminCreate,
    EstabelecimentoAdminUpdate as BarbeariaAdminUpdate,
    EstabelecimentoAdminResponse as BarbeariaAdminResponse,
    EstabelecimentoFuncionamentoDia as BarbeariaFuncionamentoDia,
    EstabelecimentoFuncionamento as BarbeariaFuncionamento,
)

__all__ = [
    "BarbeariaAdminCreate",
    "BarbeariaAdminUpdate",
    "BarbeariaAdminResponse",
    "BarbeariaFuncionamentoDia",
    "BarbeariaFuncionamento",
]
