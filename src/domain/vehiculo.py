"""Aggregate Vehiculo (unidad física) y su máquina de estados."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from .comun import RaizAgregado, ReglaNegocioViolada
from .eventos import VehiculoListoParaRenta
from .maquina_estados import MaquinaEstados
from .valores import Kilometraje


class EstadoVehiculo(str, Enum):
    DISPONIBLE = "DISPONIBLE"
    ASIGNADO = "ASIGNADO"
    RENTADO = "RENTADO"
    EN_LIMPIEZA = "EN_LIMPIEZA"


E = EstadoVehiculo
MAQUINA_VEHICULO = MaquinaEstados(
    "Vehiculo",
    {
        (E.DISPONIBLE, "asignar_a_entrega"): E.ASIGNADO,
        (E.ASIGNADO, "liberar_asignacion"): E.DISPONIBLE,
        (E.ASIGNADO, "marcar_rentado"): E.RENTADO,
        (E.RENTADO, "registrar_devolucion"): E.EN_LIMPIEZA,
        (E.EN_LIMPIEZA, "marcar_disponible"): E.DISPONIBLE,
    },
)


@dataclass
class Vehiculo(RaizAgregado):
    id: str
    placa: str
    categoria_id: str
    sucursal_id: str
    kilometraje: Kilometraje
    estado: EstadoVehiculo = EstadoVehiculo.DISPONIBLE

    def asignar_a_entrega(self) -> None:
        """Invariante: solo un vehículo Disponible se asigna."""
        self.estado = MAQUINA_VEHICULO.siguiente(self.estado, "asignar_a_entrega")

    def liberar_asignacion(self) -> None:
        self.estado = MAQUINA_VEHICULO.siguiente(self.estado, "liberar_asignacion")

    def marcar_rentado(self) -> None:
        self.estado = MAQUINA_VEHICULO.siguiente(self.estado, "marcar_rentado")

    def registrar_devolucion(self, kilometraje: Kilometraje, sucursal_id: str) -> None:
        """Al devolverse pasa a EnLimpieza."""
        if kilometraje < self.kilometraje:
            raise ReglaNegocioViolada("El kilometraje de devolución no puede ser menor al registrado")
        self.estado = MAQUINA_VEHICULO.siguiente(self.estado, "registrar_devolucion")
        self.kilometraje = kilometraje
        self.sucursal_id = sucursal_id

    def marcar_disponible(self, ahora: datetime) -> None:
        self.estado = MAQUINA_VEHICULO.siguiente(self.estado, "marcar_disponible")
        self.registrar_evento(
            VehiculoListoParaRenta(ahora, self.id, self.categoria_id, self.sucursal_id)
        )
