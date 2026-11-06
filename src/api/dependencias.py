"""Dependencias de FastAPI: servicios, actor simulado (encabezados) y manejo de errores."""
from __future__ import annotations

from fastapi import Depends, HTTPException, Request
from fastapi.security import APIKeyHeader

from ..application.puertos import Actor
from ..composicion import Servicios
from ..domain.comun import Rol

_id_header = APIKeyHeader(name="X-Actor-Id", scheme_name="ActorId", auto_error=False, description="Identificador del actor (simulado)")
_rol_header = APIKeyHeader(name="X-Rol", scheme_name="Rol", auto_error=False, description="Rol: CLIENTE, AGENTE, PATIO, LIMPIEZA, ADMINISTRACION o SISTEMA")


def servicios(request: Request) -> Servicios:
    return request.app.state.servicios


def actor(actor_id: str | None = Depends(_id_header), rol: str | None = Depends(_rol_header)) -> Actor:
    """La autenticación está fuera del alcance (BRD): el actor se simula con encabezados.

    La AUTORIZACIÓN sí es real: cada caso de uso verifica el rol (application/permisos.py).
    """
    if not actor_id or not rol:
        raise HTTPException(status_code=401, detail="Faltan los encabezados X-Actor-Id y X-Rol")
    try:
        return Actor(actor_id, Rol(rol.upper()))
    except ValueError:
        raise HTTPException(status_code=401, detail=f"Rol desconocido: {rol}") from None
