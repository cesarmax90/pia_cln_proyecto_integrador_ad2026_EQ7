"""Serialización genérica de agregados (dataclasses) a JSON y de regreso.

Cada Aggregate se persiste como UN documento JSON (una transacción = un Aggregate), mientras que las
columnas indexadas de cada tabla sirven para consultar sin hidratar el documento (ver ADR-005).
"""
from __future__ import annotations

import dataclasses
import types
import typing
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from functools import cache
from typing import Any


def codificar(valor: Any) -> Any:
    if dataclasses.is_dataclass(valor) and not isinstance(valor, type):
        return {f.name: codificar(getattr(valor, f.name)) for f in dataclasses.fields(valor)}
    if isinstance(valor, Enum):
        return valor.value
    if isinstance(valor, Decimal):
        return str(valor)
    if isinstance(valor, datetime | date):
        return valor.isoformat()
    if isinstance(valor, list | tuple):
        return [codificar(v) for v in valor]
    return valor


@cache
def _hints(clase: type) -> dict[str, Any]:
    return typing.get_type_hints(clase)


def decodificar(tipo: Any, valor: Any) -> Any:
    if valor is None:
        return None
    origen = typing.get_origin(tipo)
    if origen in (typing.Union, types.UnionType):
        argumentos = [a for a in typing.get_args(tipo) if a is not type(None)]
        return decodificar(argumentos[0], valor)
    if origen in (list, tuple):
        argumentos = typing.get_args(tipo)
        elemento = argumentos[0] if argumentos else Any
        items = [decodificar(elemento, v) for v in valor]
        return tuple(items) if origen is tuple else items
    if isinstance(tipo, type):
        if dataclasses.is_dataclass(tipo):
            hints = _hints(tipo)
            kwargs = {f.name: decodificar(hints[f.name], valor[f.name]) for f in dataclasses.fields(tipo) if f.init}
            return tipo(**kwargs)
        if issubclass(tipo, Enum):
            return tipo(valor)
        if tipo is Decimal:
            return Decimal(valor)
        if tipo is datetime:
            return datetime.fromisoformat(valor)
        if tipo is date:
            return date.fromisoformat(valor)
    return valor
