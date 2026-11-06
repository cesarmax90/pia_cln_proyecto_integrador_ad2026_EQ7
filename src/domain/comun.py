"""Piezas comunes del dominio: roles, errores y base de agregados."""
from __future__ import annotations

from enum import Enum


class Rol(str, Enum):
    CLIENTE = "CLIENTE"
    AGENTE = "AGENTE"
    PATIO = "PATIO"
    LIMPIEZA = "LIMPIEZA"
    ADMINISTRACION = "ADMINISTRACION"
    SISTEMA = "SISTEMA"


class ErrorDominio(Exception):
    """Base de todos los errores de negocio. El dominio no conoce HTTP."""

    codigo = "error_dominio"

    def __init__(self, mensaje: str):
        super().__init__(mensaje)
        self.mensaje = mensaje


class ErrorValidacion(ErrorDominio):
    """Dato mal formado (valor fuera de rango, formato inválido)."""

    codigo = "validacion"


class ReglaNegocioViolada(ErrorDominio):
    """El dato es válido pero una regla del negocio lo rechaza."""

    codigo = "regla_negocio"


class TransicionInvalida(ErrorDominio):
    """La máquina de estados no permite la transición solicitada."""

    codigo = "transicion_invalida"


class PermisoDenegado(ErrorDominio):
    """El rol del actor no puede ejecutar la operación."""

    codigo = "permiso_denegado"


class NoEncontrado(ErrorDominio):
    codigo = "no_encontrado"


class ConflictoDisponibilidad(ErrorDominio):
    """No hay unidad (ni categoría superior) para atender la solicitud."""

    codigo = "sin_disponibilidad"


class RaizAgregado:
    """Mezcla para agregados: acumula eventos de dominio fuera de los campos persistidos."""

    def registrar_evento(self, evento) -> None:
        self.__dict__.setdefault("_eventos", []).append(evento)

    def recoger_eventos(self) -> list:
        eventos = self.__dict__.get("_eventos", [])
        self.__dict__["_eventos"] = []
        return eventos


def exigir_rol(rol: Rol, permitidos: set[Rol], accion: str) -> None:
    if rol not in permitidos:
        nombres = ", ".join(sorted(r.value for r in permitidos))
        raise PermisoDenegado(f"El rol {rol.value} no puede {accion}; se requiere: {nombres}")
