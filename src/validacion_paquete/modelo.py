from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from ..domain.especificaciones import Especificacion
from ..domain.maquina_estados import MaquinaEstados
from ..domain.valores import Dinero


@dataclass(frozen=True)
class ActorPaquete:
    id: str
    activo: bool
    preferente: bool


@dataclass(frozen=True)
class LineaPaquete:
    recurso_id: str
    cantidad: int
    precio: Dinero


@dataclass(frozen=True)
class OperacionPaquete:
    id: str
    actor: ActorPaquete
    lineas: tuple[LineaPaquete, ...] = field(default_factory=tuple)
    autorizado: bool = False
    promocion_activa: bool = False

    def total(self) -> Dinero:
        total = Dinero.cero()
        for linea in self.lineas:
            total = total + linea.precio.por(linea.cantidad)  # Decimal, nunca float
        return total


class ActorActivo(Especificacion):
    nombre = "actor_activo"

    def es_satisfecha_por(self, op: OperacionPaquete) -> bool:
        return op.actor.activo


class OperacionConLineas(Especificacion):
    nombre = "detalle_no_vacio"

    def es_satisfecha_por(self, op: OperacionPaquete) -> bool:
        return len(op.lineas) >= 1


class OperacionAutorizada(Especificacion):
    nombre = "autorizacion"

    def es_satisfecha_por(self, op: OperacionPaquete) -> bool:
        return op.autorizado


class ActorPreferente(Especificacion):
    nombre = "preferente"

    def es_satisfecha_por(self, op: OperacionPaquete) -> bool:
        return op.actor.preferente


class TotalMinimo(Especificacion):
    def __init__(self, minimo: Dinero):
        self.minimo = minimo
        self.nombre = f"total>={minimo.monto}"

    def es_satisfecha_por(self, op: OperacionPaquete) -> bool:
        return op.total() >= self.minimo


class PromocionActiva(Especificacion):
    nombre = "promocion_activa"

    def es_satisfecha_por(self, op: OperacionPaquete) -> bool:
        return op.promocion_activa


def puede_procesarse() -> Especificacion:
    """actor activo AND operación con al menos una línea AND autorización."""
    return ActorActivo() & OperacionConLineas() & OperacionAutorizada()


def beneficio_referencia() -> Especificacion:
    """actor preferente AND total >= 1500 MXN AND NOT promoción activa."""
    return ActorPreferente() & TotalMinimo(Dinero(1500)) & ~PromocionActiva()


class EstadoOperacion(str, Enum):
    SOLICITADA = "SOLICITADA"
    APROBADA = "APROBADA"
    ENTREGADA = "ENTREGADA"
    DEVUELTA = "DEVUELTA"
    CANCELADA = "CANCELADA"


EO = EstadoOperacion
FLUJO_REFERENCIA = MaquinaEstados(
    "OperacionPaquete",
    {
        (EO.SOLICITADA, "aprobar"): EO.APROBADA,
        (EO.APROBADA, "entregar"): EO.ENTREGADA,
        (EO.ENTREGADA, "devolver"): EO.DEVUELTA,
        (EO.SOLICITADA, "cancelar"): EO.CANCELADA,
    },
)
EVENTO_POR_TRANSICION = {
    "aprobar": "OperacionAprobada", "entregar": "OperacionEntregada",
    "devolver": "OperacionDevuelta", "cancelar": "OperacionCancelada",
}
