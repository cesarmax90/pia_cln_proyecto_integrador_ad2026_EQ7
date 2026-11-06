"""Repositorios SQLAlchemy: traducen entre Aggregates del dominio y tablas (patrón Repository)."""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import func, insert, select, update
from sqlalchemy.orm import Session

from ..domain.catalogo import CategoriaVehiculo, Cliente, Empleado, Sucursal
from ..domain.comun import NoEncontrado
from ..domain.contrato import ContratoRenta, EstadoContrato
from ..domain.inspeccion import InspeccionVehiculo, TipoInspeccion
from ..domain.limpieza import EstadoTarea, TareaLimpieza
from ..domain.liquidacion import EstadoDeposito, Liquidacion
from ..domain.reservacion import ESTADOS_ACTIVOS, EstadoReservacion, Reservacion
from ..domain.valores import PeriodoRenta
from ..domain.vehiculo import EstadoVehiculo, Vehiculo
from . import db
from .serializacion import codificar, decodificar

# Estados que comprometen una unidad de la categoría en un periodo
ESTADOS_COMPROMETEN = (
    EstadoReservacion.CREADA.value, EstadoReservacion.UPGRADE_OFRECIDO.value, EstadoReservacion.UPGRADE_ACEPTADO.value,
)


class RepositorioDocumento:
    tabla = None
    clase = None
    etiqueta = "Registro"
    atributo_id = "id"

    def __init__(self, session: Session, uow):
        self.s = session
        self.uow = uow

    def _columnas(self, agregado) -> dict:
        return {}

    def _id(self, agregado) -> str:
        return getattr(agregado, self.atributo_id)

    def obtener(self, id_: str):
        fila = self.s.execute(select(self.tabla.c.datos).where(self.tabla.c.id == id_)).scalar_one_or_none()
        if fila is None:
            raise NoEncontrado(f"{self.etiqueta} {id_} no existe")
        return decodificar(self.clase, fila)

    def existe(self, id_: str) -> bool:
        return self.s.execute(select(self.tabla.c.id).where(self.tabla.c.id == id_)).first() is not None

    def guardar(self, agregado) -> None:
        id_ = self._id(agregado)
        valores = {"datos": codificar(agregado), **self._columnas(agregado)}
        if self.existe(id_):
            self.s.execute(update(self.tabla).where(self.tabla.c.id == id_).values(**valores))
        else:
            self.s.execute(insert(self.tabla).values(id=id_, **valores))
        self.uow.registrar(agregado)

    def _listar(self, consulta) -> list:
        return [decodificar(self.clase, d) for d in self.s.execute(consulta).scalars()]


class RepositorioClientes(RepositorioDocumento):
    tabla, clase, etiqueta = db.clientes, Cliente, "Cliente"

    def _columnas(self, c):
        return {"activo": c.activo, "frecuente": c.frecuente}


class RepositorioCategorias(RepositorioDocumento):
    tabla, clase, etiqueta = db.categorias, CategoriaVehiculo, "Categoría"

    def _columnas(self, c):
        return {"nivel": c.nivel, "habilitada": c.habilitada}

    def listar(self) -> list[CategoriaVehiculo]:
        return self._listar(select(self.tabla.c.datos).order_by(self.tabla.c.nivel))


class RepositorioSucursales(RepositorioDocumento):
    tabla, clase, etiqueta = db.sucursales, Sucursal, "Sucursal"

    def _columnas(self, s):
        return {"nombre": s.nombre}

    def listar(self) -> list[Sucursal]:
        return self._listar(select(self.tabla.c.datos).order_by(self.tabla.c.id))


class RepositorioEmpleados(RepositorioDocumento):
    tabla, clase, etiqueta = db.empleados, Empleado, "Empleado"

    def _columnas(self, e):
        return {"rol": e.rol.value, "sucursal_id": e.sucursal_id}


class RepositorioVehiculos(RepositorioDocumento):
    tabla, clase, etiqueta = db.vehiculos, Vehiculo, "Vehículo"

    def _columnas(self, v):
        return {"categoria_id": v.categoria_id, "sucursal_id": v.sucursal_id, "estado": v.estado.value}

    def contar_flota(self, categoria_id: str, sucursal_id: str) -> int:
        t = self.tabla
        return self.s.execute(
            select(func.count()).select_from(t).where(t.c.categoria_id == categoria_id, t.c.sucursal_id == sucursal_id)
        ).scalar_one()

    def buscar_disponibles(self, categoria_id: str, sucursal_id: str) -> list[Vehiculo]:
        t = self.tabla
        return self._listar(
            select(t.c.datos).where(
                t.c.categoria_id == categoria_id, t.c.sucursal_id == sucursal_id,
                t.c.estado == EstadoVehiculo.DISPONIBLE.value,
            )
        )

    def listar_por_sucursal(self, sucursal_id: str) -> list[Vehiculo]:
        return self._listar(select(self.tabla.c.datos).where(self.tabla.c.sucursal_id == sucursal_id))


class RepositorioReservaciones(RepositorioDocumento):
    tabla, clase, etiqueta, atributo_id = db.reservaciones, Reservacion, "Reservación", "folio"

    def _columnas(self, r):
        return {
            "cliente_id": r.cliente_id, "categoria_id": r.categoria_efectiva_id, "sucursal_id": r.sucursal_id,
            "estado": r.estado.value, "inicio": r.periodo.inicio, "fin": r.periodo.fin,
        }

    def contar_traslapadas(self, categoria_id: str, sucursal_id: str, periodo: PeriodoRenta) -> int:
        t = self.tabla
        return self.s.execute(
            select(func.count()).select_from(t).where(
                t.c.estado.in_(ESTADOS_COMPROMETEN), t.c.categoria_id == categoria_id,
                t.c.sucursal_id == sucursal_id, t.c.inicio < periodo.fin, t.c.fin > periodo.inicio,
            )
        ).scalar_one()

    def buscar_vencidas_no_show(self, ahora: datetime, horas: int) -> list[str]:
        t = self.tabla
        limite = ahora - timedelta(hours=horas)
        return list(self.s.execute(
            select(t.c.id).where(t.c.estado.in_(ESTADOS_ACTIVOS), t.c.inicio <= limite).order_by(t.c.inicio)
        ).scalars())


class RepositorioContratos(RepositorioDocumento):
    tabla, clase, etiqueta = db.contratos, ContratoRenta, "Contrato"

    def _columnas(self, c):
        return {
            "reservacion_folio": c.reservacion_folio, "cliente_id": c.cliente_id, "vehiculo_id": c.vehiculo_id,
            "categoria_id": c.categoria_id, "sucursal_id": c.sucursal_id, "estado": c.estado.value,
            "inicio": c.periodo.inicio, "fin": c.periodo.fin, "monto_base": c.monto_base().monto,
        }

    def contar_traslapados(self, categoria_id: str, sucursal_id: str, periodo: PeriodoRenta) -> int:
        t = self.tabla
        return self.s.execute(
            select(func.count()).select_from(t).where(
                t.c.estado == EstadoContrato.ABIERTO.value, t.c.categoria_id == categoria_id,
                t.c.sucursal_id == sucursal_id, t.c.inicio < periodo.fin, t.c.fin > periodo.inicio,
            )
        ).scalar_one()


class RepositorioInspecciones(RepositorioDocumento):
    tabla, clase, etiqueta = db.inspecciones, InspeccionVehiculo, "Inspección"

    def _columnas(self, i):
        return {"contrato_id": i.contrato_id, "vehiculo_id": i.vehiculo_id, "tipo": i.tipo.value}

    def _por_tipo(self, contrato_id: str, tipo: TipoInspeccion):
        t = self.tabla
        datos = self.s.execute(
            select(t.c.datos).where(t.c.contrato_id == contrato_id, t.c.tipo == tipo.value)
        ).scalars().first()
        return decodificar(self.clase, datos) if datos is not None else None

    def obtener_entrega(self, contrato_id: str):
        return self._por_tipo(contrato_id, TipoInspeccion.ENTREGA)

    def obtener_devolucion(self, contrato_id: str):
        return self._por_tipo(contrato_id, TipoInspeccion.DEVOLUCION)


class RepositorioLiquidaciones(RepositorioDocumento):
    tabla, clase, etiqueta = db.liquidaciones, Liquidacion, "Liquidación"

    def _columnas(self, liq):
        return {
            "contrato_id": liq.contrato_id, "deposito_estado": liq.deposito.estado.value,
            "cargos_calculados": liq.cargos_calculados, "devuelta_en": liq.devuelta_en,
            "total_cargos": liq.total_cargos().monto,
        }

    def obtener_por_contrato(self, contrato_id: str):
        datos = self.s.execute(
            select(self.tabla.c.datos).where(self.tabla.c.contrato_id == contrato_id)
        ).scalars().first()
        return decodificar(self.clase, datos) if datos is not None else None

    def buscar_elegibles_liberar(self) -> list[str]:
        t = self.tabla
        return list(self.s.execute(
            select(t.c.id).where(t.c.deposito_estado == EstadoDeposito.RETENIDO.value, t.c.cargos_calculados.is_(True))
            .order_by(t.c.devuelta_en)
        ).scalars())


class RepositorioTareas(RepositorioDocumento):
    tabla, clase, etiqueta = db.tareas_limpieza, TareaLimpieza, "Tarea de limpieza"

    def _columnas(self, t):
        return {
            "vehiculo_id": t.vehiculo_id, "estado": t.estado.value, "creada_en": t.creada_en,
            "completada_en": t.completada_en,
        }

    def buscar_abierta_por_vehiculo(self, vehiculo_id: str):
        t = self.tabla
        datos = self.s.execute(
            select(t.c.datos).where(t.c.vehiculo_id == vehiculo_id, t.c.estado == EstadoTarea.ABIERTA.value)
        ).scalars().first()
        return decodificar(self.clase, datos) if datos is not None else None

    def listar_abiertas(self) -> list[TareaLimpieza]:
        return self._listar(
            select(self.tabla.c.datos).where(self.tabla.c.estado == EstadoTarea.ABIERTA.value)
            .order_by(self.tabla.c.creada_en)
        )
