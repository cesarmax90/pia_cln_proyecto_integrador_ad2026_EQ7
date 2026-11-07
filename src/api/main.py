"""Aplicación FastAPI. Arranque: uvicorn --factory src.api.main:crear_app"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from .. import __version__
from ..composicion import Servicios, construir_servicios
from ..config import Settings
from ..domain.comun import (
    ConflictoDisponibilidad,
    ErrorDominio,
    ErrorValidacion,
    NoEncontrado,
    PermisoDenegado,
    ReglaNegocioViolada,
    TransicionInvalida,
)
from ..infrastructure.adaptadores import RelojSistema
from ..infrastructure.datos_demo import cargar_demo
from .rutas import router

log = logging.getLogger("novarent")

# Contrato de errores (docs/api/contrato.md)
ESTADO_HTTP: list[tuple[type[ErrorDominio], int]] = [
    (NoEncontrado, 404),
    (PermisoDenegado, 403),
    (TransicionInvalida, 409),
    (ConflictoDisponibilidad, 409),
    (ReglaNegocioViolada, 422),
    (ErrorValidacion, 400),
    (ErrorDominio, 400),
]

# Definición ordenada de categorías para la interfaz interactiva
TAGS_METADATA = [
    {
        "name": "Operación",
        "description": "Monitoreo del estado del servicio, entorno de ejecución y conectividad con la base de datos.",
    },
    {
        "name": "1. Catálogo de Vehículos",
        "description": "Consulta de flotilla disponible, especificaciones técnicas y tarifas diarias en MXN.",
    },
    {
        "name": "2. Reservaciones",
        "description": "Gestión de solicitudes de renta: cotización inicial, confirmación de fechas y máquina de estados.",
    },
    {
        "name": "3. Entrega de Vehículo",
        "description": "Inspección física inicial (odómetro, combustible, daños) y firma de entrega al cliente.",
    },
    {
        "name": "4. Devolución y Liquidación",
        "description": "Recepción de la unidad, cálculo de cargos automáticos por tiempo/combustible y cierre de contrato.",
    },
]

DESCRIPCION = """
## Sistema Integral de Renta de Vehículos · NovaRent

Esta API implementa la lógica de negocio completa para el arrendamiento de unidades, aplicando arquitectura orientada al dominio (**DDD**), máquina de estados formal y especificaciones de validación.

---

### Guía rápida para probar el sistema:

1. **Monitoreo:** Ejecuta el endpoint `/salud` para verificar la conexión activa del sistema.
2. **Catálogo:** Consulta los vehículos disponibles y sus tarifas vigentes.
3. **Flujo operativo:** Realiza el ciclo completo de una unidad:
   - **SOLICITADA:** Creación de la reservación para el cliente.
   - **CONFIRMADA / APROBADA:** Validación de disponibilidad y precondiciones de pago.
   - **ENTREGADA:** Registro de inspección física y salida de patio.
   - **DEVUELTA / LIQUIDADA:** Inspección de retorno, liquidación financiera y liberación del activo.

---

### Autenticación y Perfiles:
Para ejecutar pruebas que requieren permisos específicos, utiliza el botón **Authorize** (arriba a la derecha) o envía los encabezados HTTP:
* `X-Actor-Id`: Identificador del usuario (ejemplo: `AGE-01`, `CLI-001`, `PAT-01`, `ADM-01`).
* `X-Rol`: Rol asignado (`CLIENTE`, `AGENTE`, `PATIO`, `LIMPIEZA`, `ADMINISTRACION`, `SISTEMA`).
"""


def _json(estado: int, codigo: str, detalle) -> JSONResponse:
    return JSONResponse(status_code=estado, content={"error": codigo, "detalle": detalle})


def crear_app(settings: Settings | None = None, servicios: Servicios | None = None) -> FastAPI:
    settings = settings or Settings()

    @asynccontextmanager
    async def ciclo_de_vida(app: FastAPI):
        app.state.servicios = servicios or construir_servicios(settings)
        if settings.cargar_datos_demo:
            resumen = cargar_demo(app.state.servicios.ctx.uow_factory, settings.ruta_datos)
            if resumen:
                log.info("Datos de demostración cargados: %s", resumen)
        yield

    app = FastAPI(
        title="NovaRent · Lógica de Negocio",
        version=__version__,
        description=DESCRIPCION,
        openapi_tags=TAGS_METADATA,
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=ciclo_de_vida,
    )
    app.include_router(router)

    @app.get(
        "/salud",
        tags=["Operación"],
        summary="Verificar estado operativo del sistema",
        description="Comprueba que la API y la base de datos se encuentren en línea y reporta el número de sucursales registradas.",
    )
    def salud(request: Request):
        with request.app.state.servicios.ctx.uow_factory() as uow:
            sucursales = len(uow.sucursales.listar())
        return {"estado": "ok", "version": __version__, "entorno": settings.entorno, "sucursales": sucursales}

    if settings.permitir_reloj_simulado:
        @app.middleware("http")
        async def reloj_simulado(request: Request, call_next):
            """Solo demos: 'X-Ahora: 2026-11-08T10:00:00Z' fija la hora de la petición (p. ej. devolución tardía)."""
            valor = request.headers.get("X-Ahora")
            token = None
            if valor:
                try:
                    token = RelojSistema.fijar_para_la_peticion(datetime.fromisoformat(valor.replace("Z", "+00:00")))
                except ValueError:
                    return _json(400, "validacion", "X-Ahora debe ser una fecha ISO 8601 con zona horaria")
            try:
                return await call_next(request)
            finally:
                if token is not None:
                    RelojSistema.restablecer(token)

    @app.exception_handler(ErrorDominio)
    async def error_de_dominio(_: Request, exc: ErrorDominio):
        for clase, estado in ESTADO_HTTP:
            if isinstance(exc, clase):
                return _json(estado, exc.codigo, exc.mensaje)
        return _json(400, exc.codigo, exc.mensaje)

    @app.exception_handler(StarletteHTTPException)
    async def error_http(_: Request, exc: StarletteHTTPException):
        return _json(exc.status_code, f"http_{exc.status_code}", exc.detail)

    @app.exception_handler(RequestValidationError)
    async def error_de_entrada(_: Request, exc: RequestValidationError):
        detalle = [{"campo": ".".join(str(p) for p in e["loc"]), "mensaje": e["msg"]} for e in exc.errors()]
        return _json(422, "validacion_entrada", detalle)

    @app.exception_handler(Exception)
    async def error_inesperado(_: Request, exc: Exception):
        log.exception("Error no controlado")
        return _json(500, "error_interno", "Ocurrió un error inesperado")

    return app