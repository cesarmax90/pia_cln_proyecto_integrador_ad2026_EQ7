"""Endpoints REST de NovaRent con documentación clara y modelos explicativos en español."""
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


# ====================================================================================
# 1. CATÁLOGO
# ====================================================================================

@router.get(
    "/categorias",
    tags=["1. Catálogo de Vehículos"],
    response_model=list[e.CategoriaOut],
    summary="Consultar tipos de autos, precios por día y depósitos",
    description="""
### ¿Qué hace esta consulta?
Muestra todas las gamas de vehículos disponibles junto con su costo por día, depósito en garantía requerido y kilómetros libres diarios.

* **Requisito:** Haz clic en **Authorize** arriba y usa `X-Actor-Id: AGE-01` y `X-Rol: AGENTE` (o `CLIENTE`).
    """,
    response_description="Listado con todas las categorías activas y tarifas vigentes en MXN",
)
def listar_categorias(actor: Actor = A, s: Servicios = S):
    return [
        {
            "id": c.id,
            "nombre": c.nombre,
            "nivel": c.nivel,
            "tarifa_diaria": c.tarifa_diaria.monto,
            "deposito": c.deposito.monto,
            "km_incluido_por_dia": c.km_incluido_por_dia,
            "habilitada": c.habilitada,
        }
        for c in s.catalogo.listar_categorias(actor)
    ]


@router.get(
    "/sucursales",
    tags=["1. Catálogo de Vehículos"],
    response_model=list[e.SucursalOut],
    summary="Consultar sedes y sucursales de entrega",
    description="Obtiene las sucursales oficiales de NovaRent donde se pueden recoger o devolver unidades.",
    response_description="Lista de sucursales autorizadas",
)
def listar_sucursales(actor: Actor = A, s: Servicios = S):
    return [{"id": x.id, "nombre": x.nombre} for x in s.catalogo.listar_sucursales(actor)]


@router.get(
    "/clientes/{cliente_id}",
    tags=["1. Catálogo de Vehículos"],
    response_model=e.ClienteOut,
    summary="Consultar expediente de un cliente",
    description="""
Verifica si el cliente está activo, la fecha de caducidad de su licencia y si cuenta con categoría frecuente.

* **Seguridad:** Un `CLIENTE` solo puede consultar su propio registro. Roles como `AGENTE` o `ADMINISTRACION` pueden consultar a cualquiera.
    """,
    response_description="Ficha del arrendatario con estatus operativo",
)
def obtener_cliente(cliente_id: str, actor: Actor = A, s: Servicios = S):
    c = s.catalogo.obtener_cliente(actor, cliente_id)
    return {
        "id": c.id,
        "nombre": c.nombre,
        "frecuente": c.frecuente,
        "activo": c.activo,
        "licencia_vigencia": c.licencia.vigencia,
        "tarjeta_ultimos4": c.metodo_pago.ultimos4 if c.metodo_pago else None,
    }


# ====================================================================================
# 2. RESERVACIONES
# ====================================================================================

@router.get(
    "/disponibilidad",
    tags=["2. Reservaciones"],
    response_model=list[dto.DisponibilidadDTO],
    summary="US01 · Consultar disponibilidad de autos en fechas",
    description="Calcula en tiempo real cuántas unidades libres hay por categoría en la sucursal seleccionada sin cruces de horario.",
    response_description="Inventario disponible por categoría en el rango de fechas",
)
def buscar_disponibilidad(
    sucursal_id: str = Query(..., examples=["SUC-APODACA"], description="Código de la sucursal"),
    inicio: datetime = Query(..., examples=["2026-11-06T09:00:00Z"], description="Inicio de la renta"),
    fin: datetime = Query(..., examples=["2026-11-08T09:00:00Z"], description="Fin de la renta"),
    categoria_id: str | None = Query(None, examples=["REN-P001"], description="Categoría específica (opcional)"),
    actor: Actor = A,
    s: Servicios = S,
):
    return s.reservaciones.buscar_disponibilidad(actor, sucursal_id, inicio, fin, categoria_id)


@router.post(
    "/reservaciones",
    tags=["2. Reservaciones"],
    status_code=201,
    response_model=dto.ReservacionDTO,
    summary="US02 · Crear una nueva solicitud de renta",
    description="Registra la reservación en estado **SOLICITADA**, aplicando las precondiciones de cliente activo y disponibilidad.",
    response_description="Datos de la reservación creada con folio asignado",
)
def crear_reservacion(cuerpo: e.ReservacionIn, actor: Actor = A, s: Servicios = S):
    return s.reservaciones.crear_reservacion(
        actor, cuerpo.cliente_id, cuerpo.categoria_id, cuerpo.sucursal_id, cuerpo.inicio, cuerpo.fin
    )


@router.get(
    "/reservaciones/{folio}",
    tags=["2. Reservaciones"],
    response_model=dto.ReservacionDTO,
    summary="Consultar estado de una reservación por folio",
    description="Obtiene el estatus en la máquina de estados (SOLICITADA, CONFIRMADA, etc.) y los importes calculados.",
    response_description="Detalle completo de la reservación",
)
def obtener_reservacion(folio: str, actor: Actor = A, s: Servicios = S):
    return s.reservaciones.obtener_reservacion(actor, folio)


@router.post(
    "/reservaciones/{folio}/cancelar",
    tags=["2. Reservaciones"],
    response_model=dto.CancelacionDTO,
    summary="US03 · Cancelar reservación",
    description="Transiciona la reserva a CANCELADA. Si se efectúa con ≥24 horas de antelación es gratis ($0 penalización).",
    response_description="Comprobante de cancelación e importe de penalización",
)
def cancelar_reservacion(folio: str, actor: Actor = A, s: Servicios = S):
    return s.reservaciones.cancelar_reservacion(actor, folio)


@router.post(
    "/reservaciones/liberar-no-shows",
    tags=["2. Reservaciones"],
    response_model=e.ResumenLiberacionOut,
    summary="US04 · Liberar reservaciones de clientes que no llegaron (Job)",
    description="Proceso batch automático que cancela las reservas vencidas y libera los autos bloqueados.",
    response_description="Cantidad de reservaciones no-show canceladas",
)
def liberar_no_shows(actor: Actor = A, s: Servicios = S):
    return {"liberadas": s.reservaciones.liberar_no_shows(actor)}


@router.post(
    "/reservaciones/{folio}/upgrade/respuesta",
    tags=["2. Reservaciones"],
    response_model=dto.ReservacionDTO,
    summary="US09 · Responder ofrecimiento de auto de gama superior",
    description="El cliente decide si acepta un auto de mejor categoría sin costo, entra a lista de espera o cancela con reembolso.",
    response_description="Reservación actualizada con la elección del cliente",
)
def responder_upgrade(folio: str, cuerpo: e.UpgradeRespuestaIn, actor: Actor = A, s: Servicios = S):
    return s.reservaciones.responder_upgrade(actor, folio, cuerpo.respuesta)


@router.post(
    "/reservaciones/{folio}/upgrade/cortesia",
    tags=["2. Reservaciones"],
    response_model=dto.ReservacionDTO,
    summary="US10 · Otorgar auto de categoría superior por cortesía",
    description="Acción exclusiva de `ADMINISTRACION` para mejorar la gama del auto sin cargo adicional.",
    response_description="Reservación con upgrade aplicado",
)
def upgrade_cortesia(folio: str, actor: Actor = A, s: Servicios = S):
    return s.reservaciones.otorgar_upgrade_cortesia(actor, folio)


# ====================================================================================
# 3. ENTREGA Y CONTRATOS
# ====================================================================================

@router.post(
    "/reservaciones/{folio}/entrega",
    tags=["3. Entrega de Vehículo"],
    response_model=dto.EntregaDTO,
    summary="US05/US08 · Iniciar entrega y asignar auto en mostrador",
    description="El agente valida la licencia de conducir del cliente y asigna la unidad física que saldrá de patio.",
    response_description="Comprobante de asignación física de la unidad",
)
def iniciar_entrega(folio: str, cuerpo: e.EntregaIn, actor: Actor = A, s: Servicios = S):
    return s.entrega.iniciar_entrega(actor, folio, cuerpo.licencia_numero)


@router.post(
    "/inspecciones/entrega",
    tags=["3. Entrega de Vehículo"],
    status_code=201,
    response_model=dto.InspeccionDTO,
    summary="US06 · Registrar inspección física de salida",
    description="Personal de patio registra el nivel de gasolina en octavos (0-8), kilometraje inicial y fotos de daños previos.",
    response_description="Checklist inicial registrado",
)
def registrar_inspeccion_entrega(cuerpo: e.InspeccionEntregaIn, actor: Actor = A, s: Servicios = S):
    return s.inspecciones.registrar_inspeccion_entrega(
        actor,
        cuerpo.folio,
        cuerpo.vehiculo_id,
        cuerpo.combustible_octavos,
        cuerpo.kilometraje,
        _fotos(cuerpo.fotos),
        _danios(cuerpo.danios),
    )


@router.post(
    "/inspecciones/{inspeccion_id}/firma",
    tags=["3. Entrega de Vehículo"],
    response_model=dto.InspeccionDTO,
    summary="US07 · Firma digital del cliente para cerrar inspección",
    description="El arrendatario acepta las condiciones iniciales del auto. Tras la firma, el registro queda inmutable.",
    response_description="Inspección cerrada y protegida contra modificaciones",
)
def firmar_inspeccion(inspeccion_id: str, cuerpo: e.FirmaIn, actor: Actor = A, s: Servicios = S):
    return s.inspecciones.firmar_inspeccion_entrega(actor, inspeccion_id, cuerpo.firmante)


@router.post(
    "/contratos",
    tags=["3. Entrega de Vehículo"],
    status_code=201,
    response_model=dto.ContratoDTO,
    summary="Apertura de contrato formal de arrendamiento",
    description="Crea el contrato de renta. Requiere que la inspección esté firmada y el depósito retenido.",
    response_description="Contrato oficial activo",
)
def abrir_contrato(cuerpo: e.ContratoIn, actor: Actor = A, s: Servicios = S):
    return s.contratos.abrir_contrato(
        actor,
        cuerpo.folio,
        cuerpo.vehiculo_id,
        cuerpo.inspeccion_id,
        cuerpo.cobertura_tipo,
        cuerpo.cobertura_costo_diario,
    )


@router.get(
    "/contratos/{contrato_id}",
    tags=["3. Entrega de Vehículo"],
    response_model=dto.ContratoDTO,
    summary="Consultar datos de un contrato de renta",
    description="Devuelve el auto asignado, fianza retenida, cobertura contratada y estado del contrato.",
    response_description="Detalle del contrato consultado",
)
def obtener_contrato(contrato_id: str, actor: Actor = A, s: Servicios = S):
    return s.contratos.obtener_contrato(actor, contrato_id)


@router.post(
    "/contratos/{contrato_id}/extensiones",
    tags=["3. Entrega de Vehículo"],
    status_code=201,
    response_model=dto.ExtensionDTO,
    summary="US11/US12 · Solicitar tiempo extra de uso del auto",
    description="Añade horas a la fecha de devolución. Hasta 48 h lo autoriza un agente; más de 48 h requiere visto bueno administrativo.",
    response_description="Comprobante de extensión de tiempo",
)
def extender_renta(contrato_id: str, cuerpo: e.ExtensionIn, actor: Actor = A, s: Servicios = S):
    return s.contratos.extender_renta(actor, contrato_id, cuerpo.horas)


@router.post(
    "/contratos/{contrato_id}/extensiones/{extension_id}/aprobacion",
    tags=["3. Entrega de Vehículo"],
    response_model=dto.ExtensionDTO,
    summary="US12 · Autorizar extensión extraordinaria (> 48 h)",
    description="Aprobación formal de `ADMINISTRACION` para retener la unidad por varios días extras.",
    response_description="Extensión validada y confirmada",
)
def aprobar_extension(contrato_id: str, extension_id: str, actor: Actor = A, s: Servicios = S):
    return s.contratos.aprobar_extension(actor, contrato_id, extension_id)


@router.post(
    "/contratos/{contrato_id}/conductores",
    tags=["3. Entrega de Vehículo"],
    response_model=dto.ContratoDTO,
    summary="Registrar conductor secundario autorizado",
    description="Añade a una persona adicional con licencia de conducir vigente para que el seguro lo cubra legalmente.",
    response_description="Contrato actualizado con el nuevo conductor",
)
def agregar_conductor(contrato_id: str, cuerpo: e.ConductorIn, actor: Actor = A, s: Servicios = S):
    return s.contratos.agregar_conductor_adicional(
        actor, contrato_id, cuerpo.nombre, cuerpo.licencia_numero, cuerpo.licencia_vigencia
    )


# ====================================================================================
# 4. DEVOLUCIÓN, CARGOS Y LIQUIDACIÓN
# ====================================================================================

@router.post(
    "/contratos/{contrato_id}/inspeccion-devolucion",
    tags=["4. Devolución y Liquidación"],
    status_code=201,
    response_model=dto.InspeccionDTO,
    summary="US13 · Registrar revisión física de retorno del auto",
    description="Recepción de la unidad en patio: registra gasolina restante, kilometraje final y fotos de nuevos daños si existen.",
    response_description="Checklist final registrado",
)
def registrar_inspeccion_devolucion(
    contrato_id: str, cuerpo: e.InspeccionDevolucionIn, actor: Actor = A, s: Servicios = S
):
    return s.inspecciones.registrar_inspeccion_devolucion(
        actor,
        contrato_id,
        cuerpo.combustible_octavos,
        cuerpo.kilometraje,
        _fotos(cuerpo.fotos),
        _danios(cuerpo.danios),
    )


@router.post(
    "/contratos/{contrato_id}/devolucion",
    tags=["4. Devolución y Liquidación"],
    response_model=dto.ContratoDTO,
    summary="US14-US16 · Cerrar contrato y liquidar cargos automáticos",
    description="Finaliza formalmente la renta. Calcula de forma automática horas de retraso, faltante de gasolina y kilometraje extra.",
    response_description="Contrato cerrado y enviado a liquidación financiera",
)
def procesar_devolucion(contrato_id: str, actor: Actor = A, s: Servicios = S):
    return s.contratos.procesar_devolucion(actor, contrato_id)


@router.get(
    "/contratos/{contrato_id}/liquidacion",
    tags=["4. Devolución y Liquidación"],
    response_model=dto.LiquidacionDTO,
    summary="Consultar balance económico final del contrato",
    description="Desglose financiero: total cobrado por renta, penalizaciones, fianza a reembolsar y saldo pendiente.",
    response_description="Liquidación detallada de la renta",
)
def obtener_liquidacion(contrato_id: str, actor: Actor = A, s: Servicios = S):
    return s.liquidaciones.obtener_liquidacion(actor, contrato_id)


@router.post(
    "/contratos/{contrato_id}/liquidacion/cargos/{cargo_id}/aprobacion-danio",
    tags=["4. Devolución y Liquidación"],
    response_model=dto.LiquidacionDTO,
    summary="Fijar costo de reparación de daño detectado",
    description="Permite al rol `ADMINISTRACION` ingresar la cotización real del taller mecánico para descontarla del depósito.",
    response_description="Liquidación actualizada con el costo del daño fijado",
)
def aprobar_cargo_danio(
    contrato_id: str, cargo_id: str, cuerpo: e.MontoDanioIn, actor: Actor = A, s: Servicios = S
):
    return s.liquidaciones.aprobar_cargo_danio(actor, contrato_id, cargo_id, cuerpo.monto)


@router.post(
    "/contratos/{contrato_id}/liquidacion/cargos/{cargo_id}/disputa",
    tags=["4. Devolución y Liquidación"],
    response_model=dto.LiquidacionDTO,
    summary="US17 · Impugnar formalmente un cargo retenido",
    description="El cliente abre una inconformidad con su argumento si considera que un cobro (por daño o gasolina) no procede.",
    response_description="Estado de la liquidación con la disputa abierta",
)
def disputar_cargo(contrato_id: str, cargo_id: str, cuerpo: e.DisputaIn, actor: Actor = A, s: Servicios = S):
    return s.liquidaciones.disputar_cargo(actor, contrato_id, cargo_id, cuerpo.motivo)


@router.get(
    "/contratos/{contrato_id}/liquidacion/cargos/{cargo_id}/evidencia",
    tags=["4. Devolución y Liquidación"],
    response_model=dto.EvidenciaDisputaDTO,
    summary="US17 · Comparar fotos de entrega vs devolución",
    description="Herramienta de auditoría que presenta las fotos de salida contra las de entrada para resolver una controversia.",
    response_description="Comparativa fotográfica de entrega y devolución",
)
def evidencia_disputa(contrato_id: str, cargo_id: str, actor: Actor = A, s: Servicios = S):
    return s.inspecciones.consultar_evidencia_disputa(actor, contrato_id, cargo_id)


@router.post(
    "/contratos/{contrato_id}/liquidacion/cargos/{cargo_id}/resolucion",
    tags=["4. Devolución y Liquidación"],
    response_model=dto.LiquidacionDTO,
    summary="US17 · Resolver controversia (Confirmar o anular cobro)",
    description="Resolución de `ADMINISTRACION`. Si se anula, el cobro se cancela y se reintegra al saldo a devolver.",
    response_description="Liquidación con la resolución aplicada",
)
def resolver_disputa(
    contrato_id: str, cargo_id: str, cuerpo: e.ResolucionIn, actor: Actor = A, s: Servicios = S
):
    return s.liquidaciones.resolver_disputa(actor, contrato_id, cargo_id, cuerpo.resolucion)


@router.post(
    "/liquidaciones/liberar-depositos",
    tags=["4. Devolución y Liquidación"],
    response_model=e.ResumenLiberacionOut,
    summary="US20 · Liberar fianzas bancarias tras 5 días (Job)",
    description="Proceso financiero programado. Libera los depósitos retenidos una vez cumplidos 5 días hábiles sin incidencias.",
    response_description="Total de depósitos en garantía liberados",
)
def liberar_depositos(actor: Actor = A, s: Servicios = S):
    return {"liberadas": s.liquidaciones.liberar_depositos(actor)}


# ====================================================================================
# 5. FLOTA, TALLER Y REPORTES GERENCIALES
# ====================================================================================

@router.get(
    "/sucursales/{sucursal_id}/flota",
    tags=["Flota y Reportes"],
    response_model=dto.ResumenFlotaDTO,
    summary="Consultar estatus de inventario en sucursal",
    description="Agrupa todos los vehículos de la sucursal por estado operativo (Disponible, Rentado, Limpieza, Taller).",
    response_description="Resumen de flota por categoría y estado",
)
def resumen_flota(sucursal_id: str, actor: Actor = A, s: Servicios = S):
    return s.flota.consultar_flota(actor, sucursal_id)


@router.get(
    "/vehiculos/{vehiculo_id}",
    tags=["Flota y Reportes"],
    response_model=dto.VehiculoDTO,
    summary="Consultar ficha técnica y odómetro de una unidad",
    description="Regresa placas, número de serie, modelo, nivel de combustible y kilometraje acumulado de un vehículo.",
    response_description="Ficha técnica de la unidad",
)
def obtener_vehiculo(vehiculo_id: str, actor: Actor = A, s: Servicios = S):
    return s.flota.obtener_vehiculo(actor, vehiculo_id)


@router.get(
    "/limpieza/tareas",
    tags=["Flota y Reportes"],
    response_model=list[dto.TareaLimpiezaDTO],
    summary="Listar autos pendientes de lavado y preparación",
    description="Cola de unidades que han sido devueltas por clientes y requieren sanitización antes de volver a rentarse.",
    response_description="Lista de tareas activas para el equipo de patio y limpieza",
)
def tareas_abiertas(actor: Actor = A, s: Servicios = S):
    return s.limpieza.listar_abiertas(actor)


@router.post(
    "/limpieza/tareas/{tarea_id}/completar",
    tags=["Flota y Reportes"],
    response_model=dto.TareaLimpiezaDTO,
    summary="US18 · Concluir limpieza y poner auto en Disponible",
    description="El personal marca la unidad lista; la máquina de estados la regresa automáticamente al inventario disponible.",
    response_description="Tarea concluida y unidad lista para rentar",
)
def completar_tarea(tarea_id: str, actor: Actor = A, s: Servicios = S):
    return s.limpieza.marcar_vehiculo_listo(actor, tarea_id)


@router.get(
    "/reportes/ocupacion",
    tags=["Flota y Reportes"],
    response_model=dto.ReporteOcupacionDTO,
    summary="US19 · Reporte gerencial de ocupación y facturación",
    description="Muestra el porcentaje de utilización de vehículos, total de ingresos generados y rotación en un periodo.",
    response_description="Métricas consolidadas de rentabilidad y flota",
)
def reporte_ocupacion(
    sucursal_id: str = Query(..., examples=["SUC-APODACA"], description="Sucursal a auditar"),
    desde: datetime = Query(..., examples=["2026-11-01T00:00:00Z"], description="Inicio del periodo"),
    hasta: datetime = Query(..., examples=["2026-12-01T00:00:00Z"], description="Fin del periodo"),
    actor: Actor = A,
    s: Servicios = S,
):
    return s.reportes.generar_reporte_ocupacion(actor, sucursal_id, desde, hasta)