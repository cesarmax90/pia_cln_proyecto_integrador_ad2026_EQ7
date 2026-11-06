"""Puertos (interfaces) que la aplicación necesita. La infraestructura los implementa (DIP)."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Protocol

from ..domain.comun import Rol
from ..domain.politicas import ParametrosNegocio, PoliticaCancelacion, PoliticaCargos, PoliticaExtension
from ..domain.valores import Dinero, MetodoPagoRef, ReferenciaPago


@dataclass(frozen=True)
class Actor:
    id: str
    rol: Rol


class Reloj(Protocol):
    def ahora(self) -> datetime: ...


class GeneradorIds(Protocol):
    def nuevo(self, prefijo: str) -> str: ...


class CalendarioHabil(Protocol):
    def sumar_dias_habiles(self, desde: date, dias: int) -> date: ...


class PasarelaPago(Protocol):
    def verificar_tarjeta(self, metodo: MetodoPagoRef) -> bool: ...
    def retener_deposito(self, metodo: MetodoPagoRef, monto: Dinero) -> ReferenciaPago: ...
    def liberar_deposito(self, referencia: ReferenciaPago) -> None: ...


class AlmacenEvidencia(Protocol):
    def guardar(self, carpeta: str, nombre: str, contenido: bytes) -> str: ...


class BusEventos(Protocol):
    def publicar(self, eventos: list) -> None: ...
    def suscribir(self, tipo_evento: type, handler: Callable[[Any], None]) -> None: ...


class Notificaciones(Protocol):
    def enviar(self, evento: Any) -> None: ...


class UnidadDeTrabajo(Protocol):
    """Una transacción. Expone un repositorio por Aggregate y recoge los eventos al confirmar."""

    reservaciones: Any
    clientes: Any
    categorias: Any
    sucursales: Any
    empleados: Any
    contratos: Any
    inspecciones: Any
    liquidaciones: Any
    vehiculos: Any
    tareas: Any
    eventos: list

    def __enter__(self) -> UnidadDeTrabajo: ...
    def __exit__(self, *args) -> None: ...


class ConsultasLectura(Protocol):
    """Read model (CQRS básico): consultas directas, sin hidratar agregados (ADR-002)."""

    def reporte_ocupacion(self, sucursal_id: str, desde: datetime, hasta: datetime) -> dict: ...


@dataclass
class Contexto:
    uow_factory: Callable[[], UnidadDeTrabajo]
    bus: BusEventos
    reloj: Reloj
    ids: GeneradorIds
    parametros: ParametrosNegocio
    pasarela: PasarelaPago
    almacen: AlmacenEvidencia
    calendario: CalendarioHabil
    consultas: ConsultasLectura
    notificaciones: Notificaciones
    politica_cancelacion: PoliticaCancelacion = field(init=False)
    politica_extension: PoliticaExtension = field(init=False)
    politica_cargos: PoliticaCargos = field(init=False)

    def __post_init__(self):
        self.politica_cancelacion = PoliticaCancelacion(self.parametros)
        self.politica_extension = PoliticaExtension(self.parametros)
        self.politica_cargos = PoliticaCargos(self.parametros)
