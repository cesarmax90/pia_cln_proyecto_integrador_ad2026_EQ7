"""Handlers de Domain Events (ACT-F03 §3.4). Cada handler es idempotente y abre su propia transacción."""
from __future__ import annotations

from ..domain import eventos as ev
from .contratos import ContratoAppService
from .flota import FlotaAppService, LimpiezaAppService
from .liquidaciones import LiquidacionAppService
from .puertos import Contexto
from .reservaciones import ReservacionAppService

EVENTOS_NOTIFICABLES = (
    ev.ReservacionCreada, ev.ReservacionCancelada, ev.UpgradeOfrecido, ev.RentaExtendida,
    ev.ExtensionRequiereAutorizacion, ev.CargosCalculados, ev.DisputaResuelta, ev.DepositoLiberado,
)


def registrar_handlers(
    ctx: Contexto, reservaciones: ReservacionAppService, contratos: ContratoAppService,
    liquidaciones: LiquidacionAppService, flota: FlotaAppService, limpieza: LimpiezaAppService,
) -> None:
    bus = ctx.bus
    # ContratoAbierto -> Reservacion Convertida; Vehiculo Rentado; abre Liquidacion con depósito
    bus.suscribir(ev.ContratoAbierto, lambda e: reservaciones.marcar_convertida(e.reservacion_folio))
    bus.suscribir(ev.ContratoAbierto, flota.marcar_rentado)
    bus.suscribir(ev.ContratoAbierto, liquidaciones.abrir_liquidacion)
    # VehiculoDevuelto -> calcula cargos; Vehiculo EnLimpieza; crea TareaLimpieza
    bus.suscribir(ev.VehiculoDevuelto, liquidaciones.calcular_cargos)
    bus.suscribir(ev.VehiculoDevuelto, flota.registrar_devolucion_vehiculo)
    bus.suscribir(ev.VehiculoDevuelto, limpieza.crear_tarea)
    # TareaLimpiezaCompletada -> Vehiculo Disponible
    bus.suscribir(ev.TareaLimpiezaCompletada, flota.marcar_disponible)
    # DepositoLiberado -> cierre formal del contrato (N10: trazabilidad hasta el cierre)
    bus.suscribir(ev.DepositoLiberado, lambda e: contratos.cerrar_contrato(e.contrato_id))
    # Notificaciones (puerto genérico)
    for tipo in EVENTOS_NOTIFICABLES:
        bus.suscribir(tipo, ctx.notificaciones.enviar)
