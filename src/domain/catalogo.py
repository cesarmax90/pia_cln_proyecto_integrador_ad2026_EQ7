"""Entidades de catálogo y Cliente: Cliente, CategoriaVehiculo, Sucursal, Empleado."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from .comun import ErrorValidacion, RaizAgregado, Rol
from .especificaciones import ContextoCliente, cliente_apto
from .valores import Dinero, Licencia, MetodoPagoRef


@dataclass
class Cliente(RaizAgregado):
    id: str
    nombre: str
    fecha_nacimiento: date
    licencia: Licencia
    metodo_pago: MetodoPagoRef | None = None
    frecuente: bool = False
    activo: bool = True

    def __post_init__(self):
        if not self.id or not self.nombre:
            raise ErrorValidacion("El cliente requiere id y nombre")

    def edad_en(self, fecha: date) -> int:
        nacio = self.fecha_nacimiento
        return fecha.year - nacio.year - ((fecha.month, fecha.day) < (nacio.month, nacio.day))

    def es_conductor_joven(self, fecha: date, edad_minima: int = 25) -> bool:
        return self.edad_en(fecha) < edad_minima

    def contexto(self, fecha_renta: date) -> ContextoCliente:
        return ContextoCliente(
            licencia_vigencia=self.licencia.vigencia,
            tiene_tarjeta_valida=self.metodo_pago is not None,
            activo=self.activo,
            fecha_renta=fecha_renta,
        )

    def puede_rentar(self, fecha_renta: date) -> bool:
        return cliente_apto().es_satisfecha_por(self.contexto(fecha_renta))

    def motivos_no_apto(self, fecha_renta: date) -> list[str]:
        return cliente_apto().fallas(self.contexto(fecha_renta))


@dataclass
class CategoriaVehiculo(RaizAgregado):
    id: str
    nombre: str
    nivel: int
    tarifa_diaria: Dinero
    deposito: Dinero
    km_incluido_por_dia: int = 200
    habilitada: bool = True

    def __post_init__(self):
        if self.nivel < 1:
            raise ErrorValidacion("El nivel de categoría debe ser >= 1")
        if self.km_incluido_por_dia <= 0:
            raise ErrorValidacion("El kilometraje incluido por día debe ser positivo")


@dataclass
class Sucursal(RaizAgregado):
    id: str
    nombre: str


@dataclass
class Empleado(RaizAgregado):
    id: str
    nombre: str
    rol: Rol
    sucursal_id: str
