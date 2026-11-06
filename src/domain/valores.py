"""Value Objects del dominio NovaRent (inmutables, comparados por valor)."""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

from .comun import ErrorValidacion

CENTAVOS = Decimal("0.01")


@dataclass(frozen=True, order=True)
class Dinero:
    monto: Decimal
    moneda: str = "MXN"

    def __post_init__(self):
        try:
            monto = Decimal(str(self.monto)).quantize(CENTAVOS, rounding=ROUND_HALF_UP)
        except Exception as exc:  # noqa: BLE001
            raise ErrorValidacion(f"Monto inválido: {self.monto!r}") from exc
        if monto < 0:
            raise ErrorValidacion("El dinero no admite montos negativos")
        if self.moneda != "MXN":
            raise ErrorValidacion("Solo se admite la moneda MXN")
        object.__setattr__(self, "monto", monto)

    @classmethod
    def cero(cls) -> Dinero:
        return cls(Decimal("0"))

    def __add__(self, otro: Dinero) -> Dinero:
        return Dinero(self.monto + otro.monto, self.moneda)

    def por(self, factor) -> Dinero:
        return Dinero(self.monto * Decimal(str(factor)), self.moneda)

    def dividido_entre(self, divisor: int) -> Dinero:
        if divisor <= 0:
            raise ErrorValidacion("El divisor debe ser positivo")
        return Dinero(self.monto / Decimal(divisor), self.moneda)

    def es_cero(self) -> bool:
        return self.monto == 0

    def __str__(self) -> str:
        return f"${self.monto:,.2f} {self.moneda}"


def _exigir_aware(valor: datetime, nombre: str) -> None:
    if valor.tzinfo is None or valor.utcoffset() is None:
        raise ErrorValidacion(f"{nombre} debe incluir zona horaria")


@dataclass(frozen=True)
class PeriodoRenta:
    inicio: datetime
    fin: datetime

    def __post_init__(self):
        _exigir_aware(self.inicio, "inicio")
        _exigir_aware(self.fin, "fin")
        if self.fin <= self.inicio:
            raise ErrorValidacion("El fin del periodo debe ser posterior al inicio")

    @property
    def dias(self) -> int:
        """Días de renta facturables: bloques de 24 h, mínimo 1."""
        return max(1, math.ceil((self.fin - self.inicio) / timedelta(days=1)))

    def extender(self, horas: int) -> PeriodoRenta:
        return PeriodoRenta(self.inicio, self.fin + timedelta(hours=horas))

    def se_traslapa_con(self, otro: PeriodoRenta) -> bool:
        return self.inicio < otro.fin and otro.inicio < self.fin


@dataclass(frozen=True, order=True)
class Kilometraje:
    valor: int

    def __post_init__(self):
        if not isinstance(self.valor, int) or isinstance(self.valor, bool) or self.valor < 0:
            raise ErrorValidacion("El kilometraje debe ser un entero mayor o igual a 0")

    def recorrido_desde(self, anterior: Kilometraje) -> int:
        if self.valor < anterior.valor:
            raise ErrorValidacion("El kilometraje final no puede ser menor al inicial")
        return self.valor - anterior.valor


@dataclass(frozen=True, order=True)
class NivelCombustible:
    octavos: int

    def __post_init__(self):
        if not isinstance(self.octavos, int) or isinstance(self.octavos, bool):
            raise ErrorValidacion("El nivel de combustible se expresa en octavos enteros")
        if not 0 <= self.octavos <= 8:
            raise ErrorValidacion("El nivel de combustible debe estar entre 0 y 8 octavos")

    def faltante_respecto_a(self, entrega: NivelCombustible) -> int:
        return max(0, entrega.octavos - self.octavos)


@dataclass(frozen=True)
class Licencia:
    numero: str
    vigencia: date

    def __post_init__(self):
        if not self.numero or not self.numero.strip():
            raise ErrorValidacion("La licencia requiere número")

    def vigente_en(self, fecha: date) -> bool:
        return self.vigencia >= fecha


@dataclass(frozen=True)
class MetodoPagoRef:
    token: str
    ultimos4: str

    def __post_init__(self):
        if not re.fullmatch(r"\d{4}", self.ultimos4):
            raise ErrorValidacion("ultimos4 debe tener exactamente 4 dígitos")
        if re.fullmatch(r"\d{13,19}", self.token):
            raise ErrorValidacion("Nunca se almacena el número de tarjeta; use un token")
        if not self.token:
            raise ErrorValidacion("El método de pago requiere token")


@dataclass(frozen=True)
class ReferenciaPago:
    id_externo: str

    def __post_init__(self):
        if not self.id_externo:
            raise ErrorValidacion("La referencia de pago es obligatoria")


@dataclass(frozen=True)
class EvidenciaFoto:
    uri: str
    tomada_en: datetime

    def __post_init__(self):
        if not self.uri:
            raise ErrorValidacion("La foto requiere uri")
        _exigir_aware(self.tomada_en, "El sello de tiempo de la foto")


@dataclass(frozen=True)
class RegistroDanio:
    zona: str
    descripcion: str
    fotos: tuple[EvidenciaFoto, ...] = field(default_factory=tuple)

    def __post_init__(self):
        if not self.zona or not self.descripcion:
            raise ErrorValidacion("El daño requiere zona y descripción")
        if len(self.fotos) < 1:
            raise ErrorValidacion("Todo daño registrado requiere al menos una foto")

    @property
    def clave(self) -> tuple[str, str]:
        return (self.zona.strip().lower(), self.descripcion.strip().lower())


@dataclass(frozen=True)
class FirmaDigital:
    firmante: str
    firmada_en: datetime

    def __post_init__(self):
        if not self.firmante:
            raise ErrorValidacion("La firma requiere firmante")
        _exigir_aware(self.firmada_en, "La fecha de firma")


@dataclass(frozen=True)
class Disputa:
    motivo: str
    fecha: datetime
    resolucion: str | None = None
    resuelta_por: str | None = None

    def __post_init__(self):
        if not self.motivo:
            raise ErrorValidacion("La disputa requiere motivo")


@dataclass(frozen=True)
class CoberturaSeguro:
    tipo: str
    costo_diario: Dinero


@dataclass(frozen=True)
class DiferenciasInspeccion:
    km_recorridos: int
    octavos_faltantes: int
    danios_nuevos: tuple[RegistroDanio, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class CondicionesContrato:
    periodo_pactado: PeriodoRenta
    devolucion_real: datetime | None
    km_incluido_por_dia: int
    categoria_id: str
    tarifa_diaria: Dinero
