"""Domain Events (en pasado). Los emiten los agregados; los consumen handlers de aplicación."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True)
class EventoDominio:
    ocurrido_en: datetime

    @property
    def nombre(self) -> str:
        return type(self).__name__


@dataclass(frozen=True)
class ReservacionCreada(EventoDominio):
    folio: str
    cliente_id: str
    categoria_id: str
    sucursal_id: str


@dataclass(frozen=True)
class ReservacionCancelada(EventoDominio):
    folio: str
    penalizada: bool
    penalizacion: Decimal


@dataclass(frozen=True)
class ReservacionLiberadaPorNoShow(EventoDominio):
    folio: str
    categoria_id: str
    sucursal_id: str


@dataclass(frozen=True)
class UpgradeOfrecido(EventoDominio):
    folio: str
    categoria_superior_id: str


@dataclass(frozen=True)
class UpgradeRechazado(EventoDominio):
    folio: str
    opcion: str


@dataclass(frozen=True)
class UpgradeCortesiaOtorgado(EventoDominio):
    folio: str
    categoria_superior_id: str
    autorizado_por: str


@dataclass(frozen=True)
class InspeccionEntregaFirmada(EventoDominio):
    inspeccion_id: str
    contrato_id: str
    vehiculo_id: str


@dataclass(frozen=True)
class InspeccionDevolucionCompletada(EventoDominio):
    inspeccion_id: str
    contrato_id: str
    vehiculo_id: str


@dataclass(frozen=True)
class ContratoAbierto(EventoDominio):
    contrato_id: str
    reservacion_folio: str
    vehiculo_id: str
    deposito_monto: Decimal
    referencia_pago: str


@dataclass(frozen=True)
class ExtensionRequiereAutorizacion(EventoDominio):
    contrato_id: str
    extension_id: str
    horas: int


@dataclass(frozen=True)
class RentaExtendida(EventoDominio):
    contrato_id: str
    horas: int
    nuevo_fin: datetime


@dataclass(frozen=True)
class VehiculoDevuelto(EventoDominio):
    contrato_id: str
    vehiculo_id: str
    devuelta_en: datetime


@dataclass(frozen=True)
class ContratoCerrado(EventoDominio):
    contrato_id: str


@dataclass(frozen=True)
class CargosCalculados(EventoDominio):
    liquidacion_id: str
    contrato_id: str
    total: Decimal
    danios_por_aprobar: int


@dataclass(frozen=True)
class CargoDisputado(EventoDominio):
    liquidacion_id: str
    cargo_id: str
    motivo: str


@dataclass(frozen=True)
class DisputaResuelta(EventoDominio):
    liquidacion_id: str
    cargo_id: str
    resolucion: str


@dataclass(frozen=True)
class DepositoLiberado(EventoDominio):
    liquidacion_id: str
    contrato_id: str
    monto: Decimal


@dataclass(frozen=True)
class TareaLimpiezaCompletada(EventoDominio):
    tarea_id: str
    vehiculo_id: str


@dataclass(frozen=True)
class VehiculoListoParaRenta(EventoDominio):
    vehiculo_id: str
    categoria_id: str
    sucursal_id: str
