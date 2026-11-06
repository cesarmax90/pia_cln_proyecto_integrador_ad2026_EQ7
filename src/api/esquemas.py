"""Esquemas de entrada de la API (las salidas son los DTO de la capa de aplicación)."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Entrada(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ReservacionIn(Entrada):
    cliente_id: str = Field(examples=["REN-C001"])
    categoria_id: str = Field(examples=["REN-P001"])
    sucursal_id: str = Field(examples=["SUC-APODACA"])
    inicio: datetime = Field(examples=["2026-11-06T09:00:00Z"])
    fin: datetime = Field(examples=["2026-11-08T09:00:00Z"])


class UpgradeRespuestaIn(Entrada):
    respuesta: Literal["ACEPTAR", "RECHAZAR_LISTA_ESPERA", "RECHAZAR_REEMBOLSO"]


class EntregaIn(Entrada):
    licencia_numero: str = Field(examples=["LIC-REN-C001"])


class FotoIn(Entrada):
    nombre: str = Field(examples=["frente.jpg"])
    contenido_base64: str | None = Field(default=None, description="Contenido en base64 (opcional en demos)")


class DanioIn(Entrada):
    zona: str = Field(examples=["puerta delantera"])
    descripcion: str = Field(examples=["rayón profundo"])
    fotos: list[FotoIn] = Field(default_factory=list)


class InspeccionEntregaIn(Entrada):
    folio: str = Field(description="Folio de la reservación que se entrega", examples=["RES-1A2B3C4D"])
    vehiculo_id: str
    combustible_octavos: int = Field(ge=0, le=8)
    kilometraje: int = Field(ge=0)
    fotos: list[FotoIn] = Field(min_length=1)
    danios: list[DanioIn] = Field(default_factory=list)


class InspeccionDevolucionIn(Entrada):
    combustible_octavos: int = Field(ge=0, le=8)
    kilometraje: int = Field(ge=0)
    fotos: list[FotoIn] = Field(min_length=1)
    danios: list[DanioIn] = Field(default_factory=list)


class FirmaIn(Entrada):
    firmante: str = Field(examples=["Arrendatario 01"])


class ContratoIn(Entrada):
    folio: str
    vehiculo_id: str
    inspeccion_id: str
    cobertura_tipo: str | None = None
    cobertura_costo_diario: float | None = Field(default=None, ge=0)


class ExtensionIn(Entrada):
    horas: int = Field(gt=0, examples=[24])


class ConductorIn(Entrada):
    nombre: str
    licencia_numero: str
    licencia_vigencia: date


class MontoDanioIn(Entrada):
    monto: Decimal = Field(gt=0, examples=["800.00"])


class DisputaIn(Entrada):
    motivo: str = Field(examples=["El daño ya existía al recibir la unidad"])


class ResolucionIn(Entrada):
    resolucion: Literal["CONFIRMADO", "ANULADO"]
