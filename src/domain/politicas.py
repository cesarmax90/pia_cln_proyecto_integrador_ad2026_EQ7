"""Domain Services / Policies: reglas paramétricas que cambian por configuración."""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal

from .comun import ReglaNegocioViolada, Rol
from .especificaciones import (
    CancelacionSinPenalizacion,
    CombustibleFaltante,
    ContextoCancelacion,
    ContextoExtension,
    ContextoRetraso,
    DevolucionTardia,
    ExtensionConAnticipacion,
    ExtensionDentroDelLimiteDelAgente,
    NoShowVencido,
)
from .valores import CondicionesContrato, DiferenciasInspeccion, Dinero


@dataclass(frozen=True)
class ParametrosNegocio:
    """Parámetros del BRD/ACT-F03. Se cargan desde variables de entorno (12-Factor)."""

    tolerancia_retraso_min: int = 29
    tarifa_km_excedente: Dinero = field(default_factory=lambda: Dinero(Decimal("3")))
    umbral_combustible_octavos: int = 1
    # SUPUESTO: la tarifa por octavo está "por definir" en ACT-F03; validar con el negocio.
    tarifa_por_octavo: Dinero = field(default_factory=lambda: Dinero(Decimal("50")))
    limite_extension_agente_horas: int = 48
    anticipacion_extension_horas: int = 2
    horas_cancelacion_gratuita: int = 24
    horas_no_show: int = 2
    dias_habiles_liberacion_deposito: int = 5
    # SUPUESTO: penalización por cancelación tardía / no-show = N días de tarifa.
    dias_penalizacion: int = 1
    edad_minima_sin_recargo: int = 25


# --------------------------------------------------------------------------- cancelación
@dataclass(frozen=True)
class ResultadoCancelacion:
    penalizada: bool
    penalizacion: Dinero


class PoliticaCancelacion:
    def __init__(self, p: ParametrosNegocio):
        self.p = p
        self._gratis = CancelacionSinPenalizacion(p.horas_cancelacion_gratuita)
        self._no_show = NoShowVencido(p.horas_no_show)

    def evaluar(self, inicio: datetime, ahora: datetime, tarifa_diaria: Dinero) -> ResultadoCancelacion:
        if self._gratis.es_satisfecha_por(ContextoCancelacion(inicio, ahora)):
            return ResultadoCancelacion(False, Dinero.cero())
        return ResultadoCancelacion(True, tarifa_diaria.por(self.p.dias_penalizacion))

    def no_show_vencido(self, inicio: datetime, ahora: datetime) -> bool:
        return self._no_show.es_satisfecha_por(ContextoCancelacion(inicio, ahora))


# --------------------------------------------------------------------------- extensión
class DecisionExtension:
    APROBAR = "APROBAR"
    REQUIERE_ADMINISTRACION = "REQUIERE_ADMINISTRACION"


class PoliticaExtension:
    """Quién autoriza una extensión: el agente hasta 48 h; más de 48 h, Administración."""

    def __init__(self, p: ParametrosNegocio):
        self.p = p
        self._anticipacion = ExtensionConAnticipacion(p.anticipacion_extension_horas)
        self._limite = ExtensionDentroDelLimiteDelAgente(p.limite_extension_agente_horas)

    def decidir(self, rol: Rol, horas: int, fin_actual: datetime, ahora: datetime) -> str:
        if horas <= 0:
            raise ReglaNegocioViolada("Las horas de extensión deben ser positivas")
        contexto = ContextoExtension(fin_actual, horas, ahora)
        if not self._anticipacion.es_satisfecha_por(contexto):
            raise ReglaNegocioViolada(
                f"La extensión debe solicitarse con al menos {self.p.anticipacion_extension_horas} h "
                "de anticipación al vencimiento"
            )
        if rol == Rol.ADMINISTRACION or self._limite.es_satisfecha_por(contexto):
            return DecisionExtension.APROBAR
        return DecisionExtension.REQUIERE_ADMINISTRACION


# --------------------------------------------------------------------------- upgrade
class PoliticaUpgrade:
    """La categoría superior es la habilitada con el menor nivel mayor al actual."""

    @staticmethod
    def categoria_superior(actual, categorias):
        candidatas = [c for c in categorias if c.habilitada and c.nivel > actual.nivel]
        return min(candidatas, key=lambda c: c.nivel) if candidatas else None


# --------------------------------------------------------------------------- cargos
@dataclass(frozen=True)
class CargoPropuesto:
    tipo: str
    monto: Dinero
    descripcion: str


class PoliticaCargos:
    def __init__(self, p: ParametrosNegocio):
        self.p = p
        self._tardia = DevolucionTardia(p.tolerancia_retraso_min)
        self._combustible = CombustibleFaltante(p.umbral_combustible_octavos)

    def cargo_retraso(self, c: CondicionesContrato) -> CargoPropuesto | None:
        if c.devolucion_real is None:
            raise ReglaNegocioViolada("No hay devolución real registrada")
        fin = c.periodo_pactado.fin
        if not self._tardia.es_satisfecha_por(ContextoRetraso(fin, c.devolucion_real)):
            return None
        retraso = c.devolucion_real - fin
        horas = math.ceil(retraso / timedelta(hours=1))
        tarifa_hora = c.tarifa_diaria.dividido_entre(24)
        monto = min(tarifa_hora.por(horas), c.tarifa_diaria)  # tope: 1 día de tarifa
        return CargoPropuesto("RETRASO", monto, f"Devolución tardía: {horas} h cobradas (tope 1 día)")

    def cargo_kilometraje(self, d: DiferenciasInspeccion, c: CondicionesContrato) -> CargoPropuesto | None:
        incluido = c.km_incluido_por_dia * c.periodo_pactado.dias
        excedente = d.km_recorridos - incluido
        if excedente <= 0:
            return None
        monto = self.p.tarifa_km_excedente.por(excedente)
        return CargoPropuesto("KILOMETRAJE", monto, f"{excedente} km excedentes sobre {incluido} km incluidos")

    def cargo_combustible(self, d: DiferenciasInspeccion) -> CargoPropuesto | None:
        if not self._combustible.es_satisfecha_por(d):
            return None
        monto = self.p.tarifa_por_octavo.por(d.octavos_faltantes)
        return CargoPropuesto("COMBUSTIBLE", monto, f"Faltan {d.octavos_faltantes}/8 de tanque")

    def calcular(self, d: DiferenciasInspeccion, c: CondicionesContrato) -> list[CargoPropuesto]:
        propuestos = [
            self.cargo_retraso(c),
            self.cargo_kilometraje(d, c),
            self.cargo_combustible(d),
        ]
        return [x for x in propuestos if x is not None]


# --------------------------------------------------------------------------- disponibilidad
class ServicioDisponibilidad:
    """Servicio de dominio: ¿hay unidad? y ¿cuál se asigna?"""

    @staticmethod
    def unidades_disponibles(flota_total: int, reservaciones_traslapadas: int, contratos_traslapados: int) -> int:
        return max(0, flota_total - reservaciones_traslapadas - contratos_traslapados)

    @staticmethod
    def hay_unidad(flota_total: int, reservaciones_traslapadas: int, contratos_traslapados: int) -> bool:
        return ServicioDisponibilidad.unidades_disponibles(
            flota_total, reservaciones_traslapadas, contratos_traslapados
        ) > 0

    @staticmethod
    def asignar_unidad(vehiculos_disponibles):
        """Elige la unidad con menor kilometraje (rotación pareja de la flota)."""
        if not vehiculos_disponibles:
            return None
        return min(vehiculos_disponibles, key=lambda v: (v.kilometraje.valor, v.id))
