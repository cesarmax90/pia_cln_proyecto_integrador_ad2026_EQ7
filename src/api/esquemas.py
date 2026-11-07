"""Esquemas de entrada y salida documentados para Swagger UI en NovaRent."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Entrada(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ==============================================================================
# ESQUEMAS DE ENTRADA (Lo que el usuario llena en Parameters / Request Body)
# ==============================================================================

class ReservacionIn(Entrada):
    cliente_id: str = Field(
        ...,
        examples=["REN-C001"],
        description="ID del cliente registrado (REN-C001 a REN-C040)",
    )
    categoria_id: str = Field(
        ...,
        examples=["REN-P001"],
        description="Código de la categoría de vehículo (ej. REN-P001 para Sedán)",
    )
    sucursal_id: str = Field(
        ...,
        examples=["SUC-APODACA"],
        description="Sucursal de entrega pactada",
    )
    inicio: datetime = Field(
        ...,
        examples=["2026-11-06T09:00:00Z"],
        description="Fecha y hora de inicio de renta (formato ISO 8601)",
    )
    fin: datetime = Field(
        ...,
        examples=["2026-11-08T09:00:00Z"],
        description="Fecha y hora de devolución pactada",
    )


class UpgradeRespuestaIn(Entrada):
    respuesta: Literal["ACEPTAR", "RECHAZAR_LISTA_ESPERA", "RECHAZAR_REEMBOLSO"] = Field(
        ...,
        examples=["ACEPTAR"],
        description="Decisión del cliente ante oferta de cambio de gama de auto",
    )


class EntregaIn(Entrada):
    licencia_numero: str = Field(
        ...,
        examples=["LIC-REN-C001"],
        description="Número de licencia de conducir vigente para verificar en mostrador",
    )


class FotoIn(Entrada):
    nombre: str = Field(
        ...,
        examples=["frente_auto.jpg"],
        description="Nombre del archivo de fotografía de evidencia",
    )
    contenido_base64: str | None = Field(
        default=None,
        examples=[None],
        description="Cadena base64 de la imagen (opcional en entorno de prueba)",
    )


class DanioIn(Entrada):
    zona: str = Field(
        ...,
        examples=["Puerta delantera derecha"],
        description="Área del auto donde se observa el daño",
    )
    descripcion: str = Field(
        ...,
        examples=["Rayón superficial en pintura de 15 cm"],
        description="Descripción detallada del desperfecto físico",
    )
    fotos: list[FotoIn] = Field(
        default_factory=list,
        description="Fotografías de respaldo del desperfecto",
    )


class InspeccionEntregaIn(Entrada):
    folio: str = Field(
        ...,
        examples=["RES-1A2B3C4D"],
        description="Folio de la reservación aprobada que se entrega",
    )
    vehiculo_id: str = Field(
        ...,
        examples=["VEH-001"],
        description="Identificador del vehículo físico asignado en patio",
    )
    combustible_octavos: int = Field(
        ...,
        ge=0,
        le=8,
        examples=[8],
        description="Nivel de combustible en octavos (8 = Tanque lleno)",
    )
    kilometraje: int = Field(
        ...,
        ge=0,
        examples=[45200],
        description="Lectura del odómetro al momento de salir de patio",
    )
    fotos: list[FotoIn] = Field(
        ...,
        min_length=1,
        description="Fotos del estado general de la unidad al entregarse",
    )
    danios: list[DanioIn] = Field(
        default_factory=list,
        description="Daños preexistentes registrados en el checklist",
    )


class InspeccionDevolucionIn(Entrada):
    combustible_octavos: int = Field(
        ...,
        ge=0,
        le=8,
        examples=[7],
        description="Nivel de gasolina al recibir el auto (si falta se cobrará la diferencia)",
    )
    kilometraje: int = Field(
        ...,
        ge=0,
        examples=[45650],
        description="Odómetro final para validar límite de kilometraje",
    )
    fotos: list[FotoIn] = Field(
        ...,
        min_length=1,
        description="Fotos tomadas durante la recepción del vehículo",
    )
    danios: list[DanioIn] = Field(
        default_factory=list,
        description="Nuevos daños no reportados al inicio",
    )


class FirmaIn(Entrada):
    firmante: str = Field(
        ...,
        examples=["César Maximiliano Peña Mendoza"],
        description="Nombre completo de quien firma de conformidad el checklist",
    )


class ContratoIn(Entrada):
    folio: str = Field(
        ...,
        examples=["RES-1A2B3C4D"],
        description="Folio de la reservación vinculada al contrato",
    )
    vehiculo_id: str = Field(
        ...,
        examples=["VEH-001"],
        description="Identificador de la unidad entregada",
    )
    inspeccion_id: str = Field(
        ...,
        examples=["INS-ENT-001"],
        description="ID del checklist de entrega previamente firmado",
    )
    cobertura_tipo: str | None = Field(
        default="AMPLIA",
        examples=["AMPLIA"],
        description="Tipo de seguro contratado (BASICA, AMPLIA, PREMIUM)",
    )
    cobertura_costo_diario: float | None = Field(
        default=250.0,
        ge=0,
        examples=[250.0],
        description="Costo adicional diario de la cobertura",
    )


class ExtensionIn(Entrada):
    horas: int = Field(
        ...,
        gt=0,
        examples=[24],
        description="Horas adicionales de renta solicitadas",
    )


class ConductorIn(Entrada):
    nombre: str = Field(
        ...,
        examples=["María Luisa Peña"],
        description="Nombre del conductor adicional",
    )
    licencia_numero: str = Field(
        ...,
        examples=["LIC-NL-884920"],
        description="Número oficial de licencia de conducir",
    )
    licencia_vigencia: date = Field(
        ...,
        examples=["2027-10-15"],
        description="Fecha de caducidad de la licencia",
    )


class MontoDanioIn(Entrada):
    monto: Decimal = Field(
        ...,
        gt=0,
        examples=["1200.00"],
        description="Monto en MXN a cobrar por reparación del daño",
    )


class DisputaIn(Entrada):
    motivo: str = Field(
        ...,
        examples=["El rayón ya existía en la foto frontal de entrega inicial."],
        description="Motivo por el que el cliente no acepta el cobro",
    )


class ResolucionIn(Entrada):
    resolucion: Literal["CONFIRMADO", "ANULADO"] = Field(
        ...,
        examples=["CONFIRMADO"],
        description="Decisión administrativa sobre la disputa",
    )


# ==============================================================================
# ESQUEMAS DE SALIDA (Lo que Swagger muestra en Responses 200 en lugar de "string")
# ==============================================================================

class CategoriaOut(BaseModel):
    id: str = Field(..., examples=["REN-P001"], description="Identificador único del tipo de vehículo")
    nombre: str = Field(..., examples=["Sedán Económico"], description="Nombre de la categoría")
    nivel: int = Field(..., examples=[1], description="Nivel jerárquico de gama (usado para upgrades)")
    tarifa_diaria: Decimal = Field(..., examples=["850.00"], description="Tarifa base de renta por día en MXN")
    deposito: Decimal = Field(..., examples=["3000.00"], description="Fianza en garantía retenida temporalmente")
    km_incluido_por_dia: int = Field(..., examples=[200], description="Kilómetros libres diarios sin cargo extra")
    habilitada: bool = Field(..., examples=[True], description="Indica si esta gama está activa para rentar")


class SucursalOut(BaseModel):
    id: str = Field(..., examples=["SUC-APODACA"], description="Código de la sucursal")
    nombre: str = Field(..., examples=["Sucursal Apodaca Centro"], description="Nombre público de la sede")


class ClienteOut(BaseModel):
    id: str = Field(..., examples=["REN-C001"], description="Identificador único del cliente")
    nombre: str = Field(..., examples=["Juan Pérez Gómez"], description="Nombre completo del titular")
    frecuente: bool = Field(..., examples=[True], description="Tiene estatus preferente con beneficios")
    activo: bool = Field(..., examples=[True], description="Cuenta habilitada para contratar rentas")
    licencia_vigencia: date = Field(..., examples=["2027-05-20"], description="Fecha de vigencia de su licencia")
    tarjeta_ultimos4: str | None = Field(..., examples=["4321"], description="Últimos dígitos de la tarjeta guardada")


class ResumenLiberacionOut(BaseModel):
    liberadas: int = Field(..., examples=[3], description="Total de registros procesados y liberados")