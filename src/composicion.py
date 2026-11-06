"""Composition Root: único lugar donde se conectan puertos con adaptadores."""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from .application.catalogo import CatalogoAppService
from .application.contratos import ContratoAppService
from .application.entrega import EntregaAppService
from .application.flota import FlotaAppService, LimpiezaAppService
from .application.handlers import registrar_handlers
from .application.inspecciones import InspeccionAppService
from .application.liquidaciones import LiquidacionAppService
from .application.puertos import Contexto
from .application.reportes import ReporteAppService
from .application.reservaciones import ReservacionAppService
from .config import Settings
from .infrastructure.adaptadores import (
    AlmacenEvidenciaDisco,
    AlmacenEvidenciaMemoria,
    BusEventosEnMemoria,
    CalendarioHabilMX,
    GeneradorIdsUuid,
    NotificadorRegistro,
    PasarelaPagoSimulada,
    RelojSistema,
)
from .infrastructure.consultas import ConsultasSQL
from .infrastructure.db import crear_esquema, crear_motor
from .infrastructure.unidad_trabajo import UnidadTrabajoSQL


@dataclass
class Servicios:
    ctx: Contexto
    motor: Engine
    reservaciones: ReservacionAppService
    entrega: EntregaAppService
    inspecciones: InspeccionAppService
    contratos: ContratoAppService
    liquidaciones: LiquidacionAppService
    flota: FlotaAppService
    limpieza: LimpiezaAppService
    reportes: ReporteAppService
    catalogo: CatalogoAppService


def construir_servicios(
    settings: Settings, *, reloj=None, ids=None, pasarela=None, almacen=None, calendario=None,
    notificaciones=None, propagar_errores_bus: bool = False,
) -> Servicios:
    motor = crear_motor(settings.database_url)
    crear_esquema(motor)
    fabrica = sessionmaker(motor, expire_on_commit=False)
    almacen = almacen or (
        AlmacenEvidenciaDisco(settings.evidencias_dir) if settings.evidencias_dir else AlmacenEvidenciaMemoria()
    )
    ctx = Contexto(
        uow_factory=lambda: UnidadTrabajoSQL(fabrica),
        bus=BusEventosEnMemoria(propagar_errores=propagar_errores_bus),
        reloj=reloj or RelojSistema(),
        ids=ids or GeneradorIdsUuid(),
        parametros=settings.parametros_negocio(),
        pasarela=pasarela or PasarelaPagoSimulada(),
        almacen=almacen,
        calendario=calendario or CalendarioHabilMX(),
        consultas=ConsultasSQL(fabrica),
        notificaciones=notificaciones or NotificadorRegistro(),
    )
    servicios = Servicios(
        ctx, motor, ReservacionAppService(ctx), EntregaAppService(ctx), InspeccionAppService(ctx),
        ContratoAppService(ctx), LiquidacionAppService(ctx), FlotaAppService(ctx), LimpiezaAppService(ctx),
        ReporteAppService(ctx), CatalogoAppService(ctx),
    )
    registrar_handlers(
        ctx, servicios.reservaciones, servicios.contratos, servicios.liquidaciones, servicios.flota, servicios.limpieza
    )
    return servicios
