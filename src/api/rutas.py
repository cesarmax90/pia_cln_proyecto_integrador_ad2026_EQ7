"""Endpoints REST. Cada uno traduce HTTP -> comando de aplicación -> DTO; no contiene reglas de negocio."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query

from ..application import dto
from ..application.comandos import DanioCmd, FotoCmd
from ..application.puertos import Actor
from ..composicion import Servicios
from . import esquemas as e
from .dependencias import actor as obtener_actor
from .dependencias import servicios as obtener_servicios

router = APIRouter(prefix="/api/v1")
A = Depends(obtener_actor)
S = Depends(obtener_servicios)


def _fotos(fotos) -> list[FotoCmd]:
    return [FotoCmd(f.nombre, f.contenido_base64) for f in fotos]


def _danios(danios) -> list[DanioCmd]:
    return [DanioCmd(d.zona, d.descripcion, _fotos(d.fotos)) for d in danios]


# ------------------------------------------------------------------------------------ catálogo
@router.get("/categorias", tags=["Catálogo"], summary="Lista las categorías de vehículo")
def listar_categorias(actor: Actor = A, s: Servicios = S):
    return [
        {"id": c.id, "nombre": c.nombre, "nivel": c.nivel, "tarifa_diaria": c.tarifa_diaria.monto,
         "deposito": c.deposito.monto, "km_incluido_por_dia": c.km_incluido_por_dia, "habilitada": c.habilitada}
        for c in s.catalogo.listar_categorias(actor)
    ]


@router.get("/sucursales", tags=["Catálogo"], summary="Lista las sucursales")
def listar_sucursales(actor: Actor = A, s: Servicios = S):
    return [{"id": x.id, "nombre": x.nombre} for x in s.catalogo.listar_sucursales(actor)]


@router.get("/clientes/{cliente_id}", tags=["Catálogo"], summary="Consulta un cliente (un cliente solo ve el suyo)")
def obtener_cliente(cliente_id: str, actor: Actor = A, s: Servicios = S):
    c = s.catalogo.obtener_cliente(actor, cliente_id)
    return {"id": c.id, "nombre": c.nombre, "frecuente": c.frecuente, "activo": c.activo,
            "licencia_vigencia": c.licencia.vigencia, "tarjeta_ultimos4": c.metodo_pago.ultimos4 if c.metodo_pago else None}


# ------------------------------------------------------------------------------------ reservaciones
@router.get("/disponibilidad", tags=["Reservaciones"], response_model=list[dto.DisponibilidadDTO],
            summary="US01 · Disponibilidad por sucursal, fechas y categoría")
def buscar_disponibilidad(
    sucursal_id: str, inicio: datetime, fin: datetime, categoria_id: str | None = None,
    actor: Actor = A, s: Servicios = S,
):
    return s.reservaciones.buscar_disponibilidad(actor, sucursal_id, inicio, fin, categoria_id)


@router.post("/reservaciones", tags=["Reservaciones"], status_code=201, response_model=dto.ReservacionDTO,
             summary="US02 · Genera una reservación (garantiza categoría, no unidad)")
def crear_reservacion(cuerpo: e.ReservacionIn, actor: Actor = A, s: Servicios = S):
    return s.reservaciones.crear_reservacion(
        actor, cuerpo.cliente_id, cuerpo.categoria_id, cuerpo.sucursal_id, cuerpo.inicio, cuerpo.fin
    )


@router.get("/reservaciones/{folio}", tags=["Reservaciones"], response_model=dto.ReservacionDTO,
            summary="Consulta una reservación")
def obtener_reservacion(folio: str, actor: Actor = A, s: Servicios = S):
    return s.reservaciones.obtener_reservacion(actor, folio)


@router.post("/reservaciones/{folio}/cancelar", tags=["Reservaciones"], response_model=dto.CancelacionDTO,
             summary="US03 · Cancela una reservación (gratis con ≥24 h; si no, penalización)")
def cancelar_reservacion(folio: str, actor: Actor = A, s: Servicios = S):
    return s.reservaciones.cancelar_reservacion(actor, folio)


@router.post("/reservaciones/liberar-no-shows", tags=["Reservaciones"], summary="US04 · Libera reservaciones no-show (job)")
def liberar_no_shows(actor: Actor = A, s: Servicios = S):
    return {"liberadas": s.reservaciones.liberar_no_shows(actor)}


@router.post("/reservaciones/{folio}/upgrade/respuesta", tags=["Reservaciones"], response_model=dto.ReservacionDTO,
             summary="US09 · El cliente acepta o rechaza el upgrade (lista de espera o reembolso)")
def responder_upgrade(folio: str, cuerpo: e.UpgradeRespuestaIn, actor: Actor = A, s: Servicios = S):
    return s.reservaciones.responder_upgrade(actor, folio, cuerpo.respuesta)


@router.post("/reservaciones/{folio}/upgrade/cortesia", tags=["Reservaciones"], response_model=dto.ReservacionDTO,
             summary="US10 · Administración otorga un upgrade de cortesía")
def upgrade_cortesia(folio: str, actor: Actor = A, s: Servicios = S):
    return s.reservaciones.otorgar_upgrade_cortesia(actor, folio)


# ------------------------------------------------------------------------------------ entrega
@router.post("/reservaciones/{folio}/entrega", tags=["Entrega"], response_model=dto.EntregaDTO,
             summary="US05/US08 · Valida documentos, asigna unidad u ofrece upgrade sin costo")
def iniciar_entrega(folio: str, cuerpo: e.EntregaIn, actor: Actor = A, s: Servicios = S):
    return s.entrega.iniciar_entrega(actor, folio, cuerpo.licencia_numero)


@router.post("/inspecciones/entrega", tags=["Entrega"], status_code=201, response_model=dto.InspeccionDTO,
             summary="US06 · Registra el checklist de entrega con fotos")
def registrar_inspeccion_entrega(cuerpo: e.InspeccionEntregaIn, actor: Actor = A, s: Servicios = S):
    return s.inspecciones.registrar_inspeccion_entrega(
        actor, cuerpo.folio, cuerpo.vehiculo_id, cuerpo.combustible_octavos, cuerpo.kilometraje,
        _fotos(cuerpo.fotos), _danios(cuerpo.danios),
    )


@router.post("/inspecciones/{inspeccion_id}/firma", tags=["Entrega"], response_model=dto.InspeccionDTO,
             summary="US07 · Firma digital del cliente (el checklist queda inmutable)")
def firmar_inspeccion(inspeccion_id: str, cuerpo: e.FirmaIn, actor: Actor = A, s: Servicios = S):
    return s.inspecciones.firmar_inspeccion_entrega(actor, inspeccion_id, cuerpo.firmante)


@router.post("/contratos", tags=["Contratos"], status_code=201, response_model=dto.ContratoDTO,
             summary="Abre el contrato (checklist firmado + depósito retenido)")
def abrir_contrato(cuerpo: e.ContratoIn, actor: Actor = A, s: Servicios = S):
    return s.contratos.abrir_contrato(
        actor, cuerpo.folio, cuerpo.vehiculo_id, cuerpo.inspeccion_id, cuerpo.cobertura_tipo, cuerpo.cobertura_costo_diario
    )


@router.get("/contratos/{contrato_id}", tags=["Contratos"], response_model=dto.ContratoDTO, summary="Consulta un contrato")
def obtener_contrato(contrato_id: str, actor: Actor = A, s: Servicios = S):
    return s.contratos.obtener_contrato(actor, contrato_id)


@router.post("/contratos/{contrato_id}/extensiones", tags=["Contratos"], status_code=201,
             response_model=dto.ExtensionDTO, summary="US11/US12 · Solicita extensión (≤48 h agente; >48 h Administración)")
def extender_renta(contrato_id: str, cuerpo: e.ExtensionIn, actor: Actor = A, s: Servicios = S):
    return s.contratos.extender_renta(actor, contrato_id, cuerpo.horas)


@router.post("/contratos/{contrato_id}/extensiones/{extension_id}/aprobacion", tags=["Contratos"],
             response_model=dto.ExtensionDTO, summary="US12 · Administración aprueba una extensión mayor a 48 h")
def aprobar_extension(contrato_id: str, extension_id: str, actor: Actor = A, s: Servicios = S):
    return s.contratos.aprobar_extension(actor, contrato_id, extension_id)


@router.post("/contratos/{contrato_id}/conductores", tags=["Contratos"], response_model=dto.ContratoDTO,
             summary="Agrega un conductor adicional con licencia vigente")
def agregar_conductor(contrato_id: str, cuerpo: e.ConductorIn, actor: Actor = A, s: Servicios = S):
    return s.contratos.agregar_conductor_adicional(
        actor, contrato_id, cuerpo.nombre, cuerpo.licencia_numero, cuerpo.licencia_vigencia
    )


# ------------------------------------------------------------------------------------ devolución
@router.post("/contratos/{contrato_id}/inspeccion-devolucion", tags=["Devolución y cargos"], status_code=201,
             response_model=dto.InspeccionDTO, summary="US13 · Registra el checklist de devolución")
def registrar_inspeccion_devolucion(contrato_id: str, cuerpo: e.InspeccionDevolucionIn, actor: Actor = A, s: Servicios = S):
    return s.inspecciones.registrar_inspeccion_devolucion(
        actor, contrato_id, cuerpo.combustible_octavos, cuerpo.kilometraje, _fotos(cuerpo.fotos), _danios(cuerpo.danios)
    )


@router.post("/contratos/{contrato_id}/devolucion", tags=["Devolución y cargos"], response_model=dto.ContratoDTO,
             summary="US14-US16 · Procesa la devolución y dispara el cálculo de cargos")
def procesar_devolucion(contrato_id: str, actor: Actor = A, s: Servicios = S):
    return s.contratos.procesar_devolucion(actor, contrato_id)


@router.get("/contratos/{contrato_id}/liquidacion", tags=["Devolución y cargos"], response_model=dto.LiquidacionDTO,
            summary="Consulta la liquidación (cargos y depósito)")
def obtener_liquidacion(contrato_id: str, actor: Actor = A, s: Servicios = S):
    return s.liquidaciones.obtener_liquidacion(actor, contrato_id)


@router.post("/contratos/{contrato_id}/liquidacion/cargos/{cargo_id}/aprobacion-danio",
             tags=["Devolución y cargos"], response_model=dto.LiquidacionDTO,
             summary="Administración fija el monto de un cargo por daño")
def aprobar_cargo_danio(contrato_id: str, cargo_id: str, cuerpo: e.MontoDanioIn, actor: Actor = A, s: Servicios = S):
    return s.liquidaciones.aprobar_cargo_danio(actor, contrato_id, cargo_id, cuerpo.monto)


@router.post("/contratos/{contrato_id}/liquidacion/cargos/{cargo_id}/disputa", tags=["Devolución y cargos"],
             response_model=dto.LiquidacionDTO, summary="US17 · El cliente disputa un cargo")
def disputar_cargo(contrato_id: str, cargo_id: str, cuerpo: e.DisputaIn, actor: Actor = A, s: Servicios = S):
    return s.liquidaciones.disputar_cargo(actor, contrato_id, cargo_id, cuerpo.motivo)


@router.get("/contratos/{contrato_id}/liquidacion/cargos/{cargo_id}/evidencia", tags=["Devolución y cargos"],
            response_model=dto.EvidenciaDisputaDTO, summary="US17 · Compara la evidencia de entrega y devolución")
def evidencia_disputa(contrato_id: str, cargo_id: str, actor: Actor = A, s: Servicios = S):
    return s.inspecciones.consultar_evidencia_disputa(actor, contrato_id, cargo_id)


@router.post("/contratos/{contrato_id}/liquidacion/cargos/{cargo_id}/resolucion", tags=["Devolución y cargos"],
             response_model=dto.LiquidacionDTO, summary="US17 · Administración resuelve la disputa")
def resolver_disputa(contrato_id: str, cargo_id: str, cuerpo: e.ResolucionIn, actor: Actor = A, s: Servicios = S):
    return s.liquidaciones.resolver_disputa(actor, contrato_id, cargo_id, cuerpo.resolucion)


@router.post("/liquidaciones/liberar-depositos", tags=["Devolución y cargos"],
             summary="US20 · Libera depósitos a 5 días hábiles sin incidencias (job diario)")
def liberar_depositos(actor: Actor = A, s: Servicios = S):
    return {"liberadas": s.liquidaciones.liberar_depositos(actor)}


# ------------------------------------------------------------------------------------ flota, limpieza y reportes
@router.get("/sucursales/{sucursal_id}/flota", tags=["Flota y limpieza"], response_model=dto.ResumenFlotaDTO,
            summary="Resumen de flota por estado y categoría")
def resumen_flota(sucursal_id: str, actor: Actor = A, s: Servicios = S):
    return s.flota.consultar_flota(actor, sucursal_id)


@router.get("/vehiculos/{vehiculo_id}", tags=["Flota y limpieza"], response_model=dto.VehiculoDTO,
            summary="Consulta un vehículo")
def obtener_vehiculo(vehiculo_id: str, actor: Actor = A, s: Servicios = S):
    return s.flota.obtener_vehiculo(actor, vehiculo_id)


@router.get("/limpieza/tareas", tags=["Flota y limpieza"], response_model=list[dto.TareaLimpiezaDTO],
            summary="Tareas de limpieza abiertas")
def tareas_abiertas(actor: Actor = A, s: Servicios = S):
    return s.limpieza.listar_abiertas(actor)


@router.post("/limpieza/tareas/{tarea_id}/completar", tags=["Flota y limpieza"], response_model=dto.TareaLimpiezaDTO,
             summary="US18 · Marca el vehículo como listo (vuelve a Disponible)")
def completar_tarea(tarea_id: str, actor: Actor = A, s: Servicios = S):
    return s.limpieza.marcar_vehiculo_listo(actor, tarea_id)


@router.get("/reportes/ocupacion", tags=["Reportes"], response_model=dto.ReporteOcupacionDTO,
            summary="US19 · Ocupación, ingresos y rotación de flota")
def reporte_ocupacion(
    sucursal_id: str, desde: datetime = Query(examples=["2026-11-01T00:00:00Z"]),
    hasta: datetime = Query(examples=["2026-12-01T00:00:00Z"]), actor: Actor = A, s: Servicios = S,
):
    return s.reportes.generar_reporte_ocupacion(actor, sucursal_id, desde, hasta)
