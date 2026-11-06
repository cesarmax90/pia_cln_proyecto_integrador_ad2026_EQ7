"""Autorización por política: qué rol puede invocar cada caso de uso (no confundir con autenticación).

Los umbrales de negocio (48 h, 29 min...) viven en el dominio; aquí solo se verifica el rol.
"""
from __future__ import annotations

from ..domain.comun import PermisoDenegado, Rol
from .puertos import Actor

R = Rol
TODOS = frozenset(Rol)
OPERATIVOS = frozenset({R.AGENTE, R.ADMINISTRACION})

PERMISOS: dict[str, frozenset[Rol]] = {
    "buscar_disponibilidad": TODOS,
    "consultar_catalogo": TODOS,
    "crear_reservacion": frozenset({R.CLIENTE, R.AGENTE, R.ADMINISTRACION}),
    "cancelar_reservacion": frozenset({R.CLIENTE, R.AGENTE, R.ADMINISTRACION, R.SISTEMA}),
    "liberar_no_shows": frozenset({R.SISTEMA, R.ADMINISTRACION}),
    "responder_upgrade": frozenset({R.CLIENTE, R.AGENTE}),
    "otorgar_upgrade_cortesia": frozenset({R.ADMINISTRACION}),
    "iniciar_entrega": OPERATIVOS,
    "registrar_inspeccion": frozenset({R.PATIO, R.AGENTE, R.ADMINISTRACION}),
    "firmar_inspeccion_entrega": frozenset({R.CLIENTE, R.AGENTE}),
    "consultar_evidencia": OPERATIVOS,
    "abrir_contrato": OPERATIVOS,
    "extender_renta": OPERATIVOS,
    "aprobar_extension": frozenset({R.ADMINISTRACION}),
    "procesar_devolucion": OPERATIVOS,
    "agregar_conductor": OPERATIVOS,
    "consultar_contrato": frozenset({R.CLIENTE, R.AGENTE, R.ADMINISTRACION, R.PATIO}),
    "aprobar_cargo_danio": frozenset({R.ADMINISTRACION}),
    "disputar_cargo": frozenset({R.CLIENTE, R.AGENTE, R.ADMINISTRACION}),
    "resolver_disputa": frozenset({R.ADMINISTRACION}),
    "liberar_depositos": frozenset({R.SISTEMA, R.ADMINISTRACION}),
    "consultar_liquidacion": frozenset({R.CLIENTE, R.AGENTE, R.ADMINISTRACION}),
    "marcar_vehiculo_listo": frozenset({R.LIMPIEZA, R.PATIO, R.ADMINISTRACION}),
    "consultar_flota": frozenset({R.AGENTE, R.PATIO, R.LIMPIEZA, R.ADMINISTRACION}),
    "generar_reporte": frozenset({R.ADMINISTRACION}),
}


def exigir(actor: Actor, caso_uso: str) -> None:
    permitidos = PERMISOS[caso_uso]
    if actor.rol not in permitidos:
        nombres = ", ".join(sorted(r.value for r in permitidos))
        raise PermisoDenegado(f"El rol {actor.rol.value} no puede ejecutar '{caso_uso}'. Roles permitidos: {nombres}")


def exigir_propietario(actor: Actor, cliente_id: str) -> None:
    """Un cliente solo opera sobre sus propios recursos."""
    if actor.rol == Rol.CLIENTE and actor.id != cliente_id:
        raise PermisoDenegado("Un cliente solo puede operar sobre sus propias reservaciones y contratos")
