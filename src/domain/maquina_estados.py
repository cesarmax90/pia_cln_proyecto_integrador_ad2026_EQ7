"""Máquina de estados genérica y declarativa (patrón State Machine)."""
from __future__ import annotations

from collections.abc import Mapping
from enum import Enum

from .comun import TransicionInvalida


class MaquinaEstados:
    """Tabla de transiciones {(estado, evento): estado_destino}.

    Los agregados declaran su tabla una sola vez; el resto del código solo pide
    la siguiente transición, de modo que ninguna regla de estado queda dispersa en ``if``.
    """

    def __init__(self, nombre: str, transiciones: Mapping[tuple[Enum, str], Enum]):
        self.nombre = nombre
        self._transiciones = dict(transiciones)

    def puede(self, estado: Enum, evento: str) -> bool:
        return (estado, evento) in self._transiciones

    def siguiente(self, estado: Enum, evento: str) -> Enum:
        try:
            return self._transiciones[(estado, evento)]
        except KeyError:
            raise TransicionInvalida(
                f"{self.nombre}: no se puede '{evento}' desde el estado {estado.value}"
            ) from None

    def eventos_permitidos(self, estado: Enum) -> list[str]:
        return sorted(ev for (est, ev) in self._transiciones if est == estado)

    def estados(self) -> set[Enum]:
        origenes = {est for (est, _) in self._transiciones}
        return origenes | set(self._transiciones.values())
