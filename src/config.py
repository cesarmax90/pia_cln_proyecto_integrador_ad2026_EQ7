"""Configuración 12-Factor: todo se lee de variables de entorno (ver .env.example)."""
from __future__ import annotations

from decimal import Decimal

from pydantic_settings import BaseSettings, SettingsConfigDict

from .domain.politicas import ParametrosNegocio
from .domain.valores import Dinero


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./novarent.db"
    entorno: str = "desarrollo"
    cargar_datos_demo: bool = True
    ruta_datos: str = "datos"
    evidencias_dir: str | None = None
    permitir_reloj_simulado: bool = False

    # Parámetros de negocio (BRD / ACT-F03)
    tolerancia_retraso_min: int = 29
    tarifa_km_excedente: Decimal = Decimal("3")
    umbral_combustible_octavos: int = 1
    tarifa_por_octavo: Decimal = Decimal("50")
    limite_extension_agente_horas: int = 48
    anticipacion_extension_horas: int = 2
    horas_cancelacion_gratuita: int = 24
    horas_no_show: int = 2
    dias_habiles_liberacion_deposito: int = 5
    dias_penalizacion: int = 1

    def parametros_negocio(self) -> ParametrosNegocio:
        return ParametrosNegocio(
            tolerancia_retraso_min=self.tolerancia_retraso_min,
            tarifa_km_excedente=Dinero(self.tarifa_km_excedente),
            umbral_combustible_octavos=self.umbral_combustible_octavos,
            tarifa_por_octavo=Dinero(self.tarifa_por_octavo),
            limite_extension_agente_horas=self.limite_extension_agente_horas,
            anticipacion_extension_horas=self.anticipacion_extension_horas,
            horas_cancelacion_gratuita=self.horas_cancelacion_gratuita,
            horas_no_show=self.horas_no_show,
            dias_habiles_liberacion_deposito=self.dias_habiles_liberacion_deposito,
            dias_penalizacion=self.dias_penalizacion,
        )
