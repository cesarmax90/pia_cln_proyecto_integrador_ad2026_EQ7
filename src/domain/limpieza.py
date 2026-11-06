"""Aggregate TareaLimpieza: una tarea abierta por devolución."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from .comun import RaizAgregado, Rol, exigir_rol
from .eventos import TareaLimpiezaCompletada
from .maquina_estados import MaquinaEstados


class EstadoTarea(str, Enum):
    ABIERTA = "ABIERTA"
    COMPLETADA = "COMPLETADA"


MAQUINA_TAREA = MaquinaEstados("TareaLimpieza", {(EstadoTarea.ABIERTA, "completar"): EstadoTarea.COMPLETADA})


@dataclass
class TareaLimpieza(RaizAgregado):
    id: str
    vehiculo_id: str
    creada_en: datetime
    estado: EstadoTarea = EstadoTarea.ABIERTA
    empleado_id: str | None = None
    completada_en: datetime | None = None

    def completar(self, empleado_id: str, rol: Rol, ahora: datetime) -> None:
        exigir_rol(rol, {Rol.LIMPIEZA, Rol.PATIO, Rol.ADMINISTRACION}, "marcar un vehículo como listo")
        self.estado = MAQUINA_TAREA.siguiente(self.estado, "completar")
        self.empleado_id = empleado_id
        self.completada_en = ahora
        self.registrar_evento(TareaLimpiezaCompletada(ahora, self.id, self.vehiculo_id))

    @property
    def horas_de_rotacion(self) -> float | None:
        if self.completada_en is None:
            return None
        return (self.completada_en - self.creada_en).total_seconds() / 3600
