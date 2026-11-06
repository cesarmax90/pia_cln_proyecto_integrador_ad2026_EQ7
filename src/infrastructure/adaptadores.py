"""Adaptadores de los puertos: reloj, ids, calendario, pasarela de pago, evidencia, bus y notificaciones."""
from __future__ import annotations

import contextvars
import itertools
import logging
import re
import uuid
from collections import defaultdict
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from ..domain.comun import ErrorValidacion, ReglaNegocioViolada
from ..domain.valores import Dinero, MetodoPagoRef, ReferenciaPago

log = logging.getLogger("novarent")


# ----------------------------------------------------------------------------- reloj
_ahora_simulado: contextvars.ContextVar[datetime | None] = contextvars.ContextVar("ahora_simulado", default=None)


class RelojSistema:
    """Hora real, con posibilidad de fijar la hora de la petición en curso (solo demos y pruebas E2E)."""

    def ahora(self) -> datetime:
        return _ahora_simulado.get() or datetime.now(UTC)

    @staticmethod
    def fijar_para_la_peticion(valor: datetime | None):
        return _ahora_simulado.set(valor)

    @staticmethod
    def restablecer(token) -> None:
        _ahora_simulado.reset(token)


class RelojFijo:
    def __init__(self, inicial: datetime):
        self._ahora = inicial

    def ahora(self) -> datetime:
        return self._ahora

    def establecer(self, valor: datetime) -> None:
        self._ahora = valor

    def avanzar(self, **kwargs) -> None:
        self._ahora += timedelta(**kwargs)


# ----------------------------------------------------------------------------- identificadores
class GeneradorIdsUuid:
    def nuevo(self, prefijo: str) -> str:
        return f"{prefijo}-{uuid.uuid4().hex[:8].upper()}"


class GeneradorIdsSecuencial:
    """Determinista: RES-0001, RES-0002... (pruebas y demos reproducibles)."""

    def __init__(self):
        self._contadores: dict[str, itertools.count] = defaultdict(lambda: itertools.count(1))

    def nuevo(self, prefijo: str) -> str:
        return f"{prefijo}-{next(self._contadores[prefijo]):04d}"


# ----------------------------------------------------------------------------- calendario
def _n_esimo_lunes(anio: int, mes: int, n: int) -> date:
    primero = date(anio, mes, 1)
    primer_lunes = primero + timedelta(days=(7 - primero.weekday()) % 7)
    return primer_lunes + timedelta(weeks=n - 1)


class CalendarioHabilMX:
    """Días hábiles: lunes a viernes, sin los días de descanso obligatorio (Ley Federal del Trabajo, art. 74)."""

    def __init__(self, festivos_extra: set[date] | None = None):
        self._extra = festivos_extra or set()

    def festivos(self, anio: int) -> set[date]:
        return {
            date(anio, 1, 1), _n_esimo_lunes(anio, 2, 1), _n_esimo_lunes(anio, 3, 3), date(anio, 5, 1),
            date(anio, 9, 16), _n_esimo_lunes(anio, 11, 3), date(anio, 12, 25),
        } | {f for f in self._extra if f.year == anio}

    def es_habil(self, dia: date) -> bool:
        return dia.weekday() < 5 and dia not in self.festivos(dia.year)

    def sumar_dias_habiles(self, desde: date, dias: int) -> date:
        if dias < 0:
            raise ErrorValidacion("Los días hábiles a sumar no pueden ser negativos")
        actual, restantes = desde, dias
        while restantes > 0:
            actual += timedelta(days=1)
            if self.es_habil(actual):
                restantes -= 1
        return actual


# ----------------------------------------------------------------------------- pasarela de pago
class PasarelaPagoSimulada:
    """Doble de la pasarela. Tokens especiales: 'rechazada' (tarjeta inválida) y 'sin_fondos' (retención fallida)."""

    def __init__(self):
        self.retenciones: list[tuple[str, Dinero, ReferenciaPago]] = []
        self.liberaciones: list[ReferenciaPago] = []
        self._contador = itertools.count(1)

    def verificar_tarjeta(self, metodo: MetodoPagoRef) -> bool:
        return "rechazada" not in metodo.token

    def retener_deposito(self, metodo: MetodoPagoRef, monto: Dinero) -> ReferenciaPago:
        if "sin_fondos" in metodo.token:
            raise ReglaNegocioViolada("El banco rechazó la retención del depósito de garantía")
        referencia = ReferenciaPago(f"PAY-{next(self._contador):06d}")
        self.retenciones.append((metodo.token, monto, referencia))
        return referencia

    def liberar_deposito(self, referencia: ReferenciaPago) -> None:
        self.liberaciones.append(referencia)


# ----------------------------------------------------------------------------- evidencia
_SEGURO = re.compile(r"[^A-Za-z0-9._-]")


class AlmacenEvidenciaMemoria:
    def __init__(self):
        self.archivos: dict[str, bytes] = {}

    def guardar(self, carpeta: str, nombre: str, contenido: bytes) -> str:
        uri = f"evidencias/{_SEGURO.sub('_', carpeta)}/{_SEGURO.sub('_', nombre)}"
        self.archivos[uri] = contenido
        return uri


class AlmacenEvidenciaDisco(AlmacenEvidenciaMemoria):
    """Escribe en disco (volumen Docker); sanea nombres para impedir path traversal."""

    def __init__(self, raiz: str | Path):
        super().__init__()
        self.raiz = Path(raiz)

    def guardar(self, carpeta: str, nombre: str, contenido: bytes) -> str:
        uri = super().guardar(carpeta, nombre, contenido)
        destino = self.raiz / uri
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(contenido)
        return uri


# ----------------------------------------------------------------------------- bus y notificaciones
class BusEventosEnMemoria:
    """Bus síncrono en proceso. Se publica después del commit; un handler que falla no revierte al emisor.

    Limitación conocida (ADR-006): sin Outbox un fallo entre commit y handler deja una reacción pendiente.
    Por eso todos los handlers son idempotentes y pueden reintentarse.
    """

    def __init__(self, propagar_errores: bool = False):
        self._handlers: dict[type, list[Callable[[Any], None]]] = defaultdict(list)
        self.propagar_errores = propagar_errores
        self.errores: list[tuple[Any, Exception]] = []
        self.historial: list[Any] = []

    def suscribir(self, tipo_evento: type, handler: Callable[[Any], None]) -> None:
        self._handlers[tipo_evento].append(handler)

    def publicar(self, eventos: list) -> None:
        for evento in eventos:
            self.historial.append(evento)
            for handler in list(self._handlers.get(type(evento), [])):
                try:
                    handler(evento)
                except Exception as exc:  # noqa: BLE001
                    self.errores.append((evento, exc))
                    log.exception("Falló el handler %s para %s", getattr(handler, "__name__", handler), evento.nombre)
                    if self.propagar_errores:
                        raise


class NotificadorRegistro:
    """Puerto de notificaciones: registra en bitácora (sustituible por correo/SMS)."""

    def __init__(self):
        self.enviadas: list[Any] = []

    def enviar(self, evento: Any) -> None:
        self.enviadas.append(evento)
        log.info("Notificación: %s", evento.nombre)
