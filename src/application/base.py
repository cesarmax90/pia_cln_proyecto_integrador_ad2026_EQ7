"""Utilidades comunes de los Application Services."""
from __future__ import annotations

import base64
import binascii

from ..domain.comun import ErrorValidacion
from ..domain.valores import EvidenciaFoto
from .puertos import Contexto


def contrato_id_de(folio: str) -> str:
    """El folio del contrato se deriva del de la reservación (1 reservación -> 1 contrato).

    Permite que la inspección de entrega referencie el contrato antes de su apertura.
    """
    return f"CTR-{folio}"


def folio_de(contrato_id: str) -> str:
    return contrato_id.removeprefix("CTR-")


def liquidacion_id_de(contrato_id: str) -> str:
    return f"LIQ-{folio_de(contrato_id)}"


class ServicioBase:
    def __init__(self, ctx: Contexto):
        self.ctx = ctx

    def _publicar(self, uow) -> None:
        """Los eventos se publican DESPUÉS del commit; cada handler abre su propia transacción."""
        self.ctx.bus.publicar(uow.eventos)

    def _guardar_fotos(self, carpeta: str, fotos, ahora) -> tuple[EvidenciaFoto, ...]:
        evidencias = []
        for f in fotos:
            try:
                contenido = base64.b64decode(f.contenido_base64 or "", validate=True)
            except (binascii.Error, ValueError) as exc:
                raise ErrorValidacion(f"La foto {f.nombre!r} no es base64 válido") from exc
            nombre_unico = f"{self.ctx.ids.nuevo('FOT')}_{f.nombre}"  # nunca se sobrescribe evidencia
            uri = self.ctx.almacen.guardar(carpeta, nombre_unico, contenido)
            evidencias.append(EvidenciaFoto(uri, ahora))  # sello de tiempo del servidor
        return tuple(evidencias)
