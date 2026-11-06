"""Comandos de entrada de la capa de aplicación."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class FotoCmd:
    nombre: str
    contenido_base64: str | None = None


@dataclass
class DanioCmd:
    zona: str
    descripcion: str
    fotos: list[FotoCmd] = field(default_factory=list)
