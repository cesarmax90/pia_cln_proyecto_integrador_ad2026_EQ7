"""Patrón Specification: reglas booleanas componibles con AND / OR / NOT.

Cada especificación evalúa un contexto inmutable; ``fallas`` explica qué parte
de una composición no se cumplió (útil para mensajes de error claros).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

from .valores import DiferenciasInspeccion


class Especificacion(ABC):
    nombre: str = "especificacion"

    @abstractmethod
    def es_satisfecha_por(self, candidato: Any) -> bool: ...

    def fallas(self, candidato: Any) -> list[str]:
        return [] if self.es_satisfecha_por(candidato) else [self.nombre]

    def __and__(self, otra: Especificacion) -> Especificacion:
        return Conjuncion(self, otra)

    def __or__(self, otra: Especificacion) -> Especificacion:
        return Disyuncion(self, otra)

    def __invert__(self) -> Especificacion:
        return Negacion(self)


class Conjuncion(Especificacion):
    def __init__(self, izq: Especificacion, der: Especificacion):
        self.izq, self.der = izq, der
        self.nombre = f"({izq.nombre} AND {der.nombre})"

    def es_satisfecha_por(self, candidato) -> bool:
        return self.izq.es_satisfecha_por(candidato) and self.der.es_satisfecha_por(candidato)

    def fallas(self, candidato) -> list[str]:
        return self.izq.fallas(candidato) + self.der.fallas(candidato)


class Disyuncion(Especificacion):
    def __init__(self, izq: Especificacion, der: Especificacion):
        self.izq, self.der = izq, der
        self.nombre = f"({izq.nombre} OR {der.nombre})"

    def es_satisfecha_por(self, candidato) -> bool:
        return self.izq.es_satisfecha_por(candidato) or self.der.es_satisfecha_por(candidato)

    def fallas(self, candidato) -> list[str]:
        if self.es_satisfecha_por(candidato):
            return []
        return self.izq.fallas(candidato) + self.der.fallas(candidato)


class Negacion(Especificacion):
    def __init__(self, interna: Especificacion):
        self.interna = interna
        self.nombre = f"NOT {interna.nombre}"

    def es_satisfecha_por(self, candidato) -> bool:
        return not self.interna.es_satisfecha_por(candidato)


class Predicado(Especificacion):
    """Especificación hoja definida por una función pura."""

    def __init__(self, nombre: str, funcion: Callable[[Any], bool]):
        self.nombre = nombre
        self._funcion = funcion

    def es_satisfecha_por(self, candidato) -> bool:
        return bool(self._funcion(candidato))


# --------------------------------------------------------------------------- contextos
@dataclass(frozen=True)
class ContextoCliente:
    licencia_vigencia: date
    tiene_tarjeta_valida: bool
    activo: bool
    fecha_renta: date


@dataclass(frozen=True)
class ContextoCancelacion:
    inicio_renta: datetime
    ahora: datetime


@dataclass(frozen=True)
class ContextoExtension:
    fin_actual: datetime
    horas_solicitadas: int
    ahora: datetime


@dataclass(frozen=True)
class ContextoRetraso:
    fin_pactado: datetime
    devolucion_real: datetime


@dataclass(frozen=True)
class ContextoDeposito:
    devuelta_en: datetime
    ahora: datetime
    fecha_liberacion: datetime
    tiene_incidencias: bool


# --------------------------------------------------------------------------- hojas
class LicenciaVigente(Especificacion):
    nombre = "LicenciaVigente"

    def es_satisfecha_por(self, c: ContextoCliente) -> bool:
        return c.licencia_vigencia >= c.fecha_renta


class TarjetaValida(Especificacion):
    nombre = "TarjetaValida"

    def es_satisfecha_por(self, c: ContextoCliente) -> bool:
        return c.tiene_tarjeta_valida


class ClienteActivo(Especificacion):
    nombre = "ClienteActivo"

    def es_satisfecha_por(self, c: ContextoCliente) -> bool:
        return c.activo


class CancelacionSinPenalizacion(Especificacion):
    """Cancelación gratuita: faltan al menos ``horas`` para el inicio de la renta."""

    def __init__(self, horas: int = 24):
        self.horas = horas
        self.nombre = f"CancelacionConAnticipacion>={horas}h"

    def es_satisfecha_por(self, c: ContextoCancelacion) -> bool:
        return c.inicio_renta - c.ahora >= timedelta(hours=self.horas)


class NoShowVencido(Especificacion):
    """El cliente no se presentó dentro de la ventana permitida (por defecto 2 h)."""

    def __init__(self, horas: int = 2):
        self.horas = horas
        self.nombre = f"NoShowVencido>={horas}h"

    def es_satisfecha_por(self, c: ContextoCancelacion) -> bool:
        return c.ahora >= c.inicio_renta + timedelta(hours=self.horas)


class ExtensionDentroDelLimiteDelAgente(Especificacion):
    def __init__(self, horas_maximas: int = 48):
        self.horas_maximas = horas_maximas
        self.nombre = f"ExtensionHasta{horas_maximas}h"

    def es_satisfecha_por(self, c: ContextoExtension) -> bool:
        return 0 < c.horas_solicitadas <= self.horas_maximas


class ExtensionConAnticipacion(Especificacion):
    """La extensión se solicita al menos ``horas`` antes del vencimiento."""

    def __init__(self, horas: int = 2):
        self.horas = horas
        self.nombre = f"ExtensionConAnticipacion>={horas}h"

    def es_satisfecha_por(self, c: ContextoExtension) -> bool:
        return c.fin_actual - c.ahora >= timedelta(hours=self.horas)


class DevolucionTardia(Especificacion):
    """Entrega posterior a la hora pactada más la tolerancia (29 min por defecto)."""

    def __init__(self, tolerancia_min: int = 29):
        self.tolerancia_min = tolerancia_min
        self.nombre = f"DevolucionTardia>{tolerancia_min}min"

    def es_satisfecha_por(self, c: ContextoRetraso) -> bool:
        return c.devolucion_real - c.fin_pactado > timedelta(minutes=self.tolerancia_min)


class CombustibleFaltante(Especificacion):
    """Diferencia de combustible mayor al umbral (1/8 por defecto)."""

    def __init__(self, umbral_octavos: int = 1):
        self.umbral = umbral_octavos
        self.nombre = f"CombustibleFaltante>{umbral_octavos}/8"

    def es_satisfecha_por(self, d: DiferenciasInspeccion) -> bool:
        return d.octavos_faltantes > self.umbral


class SinIncidencias(Especificacion):
    nombre = "SinIncidencias"

    def es_satisfecha_por(self, c: ContextoDeposito) -> bool:
        return not c.tiene_incidencias


class PlazoDeLiberacionCumplido(Especificacion):
    nombre = "PlazoDeLiberacionCumplido"

    def es_satisfecha_por(self, c: ContextoDeposito) -> bool:
        return c.ahora >= c.fecha_liberacion


# --------------------------------------------------------------------------- composiciones
def cliente_apto() -> Especificacion:
    """Cliente activo AND licencia vigente AND tarjeta válida."""
    return ClienteActivo() & LicenciaVigente() & TarjetaValida()


def extension_autorizable_por_agente(horas_max: int = 48, anticipacion: int = 2) -> Especificacion:
    return ExtensionConAnticipacion(anticipacion) & ExtensionDentroDelLimiteDelAgente(horas_max)


def deposito_liberable() -> Especificacion:
    return SinIncidencias() & PlazoDeLiberacionCumplido()
