"""Escenario compartido de pruebas: datos controlados y atajos para recorrer el flujo de negocio."""
from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from src.application.comandos import DanioCmd, FotoCmd
from src.application.puertos import Actor
from src.domain.catalogo import CategoriaVehiculo, Cliente, Sucursal
from src.domain.comun import Rol
from src.domain.valores import Dinero, Kilometraje, Licencia, MetodoPagoRef
from src.domain.vehiculo import Vehiculo

AHORA = datetime(2026, 11, 5, 10, 0, tzinfo=UTC)          # jueves
INICIO = datetime(2026, 11, 6, 9, 0, tzinfo=UTC)          # viernes 09:00
AGENTE = Actor("AGE-01", Rol.AGENTE)
PATIO = Actor("PAT-01", Rol.PATIO)
LIMPIEZA = Actor("LIM-01", Rol.LIMPIEZA)
ADMIN = Actor("ADM-01", Rol.ADMINISTRACION)
SISTEMA = Actor("SYS", Rol.SISTEMA)
CLIENTE = Actor("C1", Rol.CLIENTE)
OTRO_CLIENTE = Actor("C6", Rol.CLIENTE)


def fotos(n: int = 1) -> list[FotoCmd]:
    return [FotoCmd(f"foto{i}.jpg", "eA==") for i in range(n)]


def danio(zona: str = "puerta", descripcion: str = "rayón profundo") -> DanioCmd:
    return DanioCmd(zona, descripcion, fotos())


def cliente(id_: str, token: str | None = None, vigencia: date = date(2030, 12, 31), **kw) -> Cliente:
    return Cliente(
        id=id_, nombre=f"Cliente {id_}", fecha_nacimiento=date(1990, 5, 17), licencia=Licencia(f"LIC-{id_}", vigencia),
        metodo_pago=MetodoPagoRef(token or f"tok_{id_.lower()}", "1111"), **kw,
    )


def sembrar(s) -> None:
    """Dos sucursales, tres categorías habilitadas (+1 deshabilitada), cinco unidades y seis clientes."""
    with s.ctx.uow_factory() as uow:
        for suc in (Sucursal("SUC-MTY", "Monterrey"), Sucursal("SUC-APO", "Apodaca")):
            uow.sucursales.guardar(suc)
        for id_, nivel, tarifa, hab in (("ECO", 1, 500, True), ("COMP", 2, 700, True), ("SUV", 3, 1000, True), ("PREM", 4, 2000, False)):
            uow.categorias.guardar(CategoriaVehiculo(
                id_, id_.title(), nivel, Dinero(tarifa), Dinero(tarifa * 3), habilitada=hab))
        for id_, cat, suc in (
            ("VEH-ECO-1", "ECO", "SUC-MTY"), ("VEH-ECO-2", "ECO", "SUC-MTY"), ("VEH-COMP-1", "COMP", "SUC-MTY"),
            ("VEH-SUV-1", "SUV", "SUC-MTY"), ("VEH-ECO-A", "ECO", "SUC-APO"),
        ):
            uow.vehiculos.guardar(Vehiculo(id_, f"PL-{id_}", cat, suc, Kilometraje(1000)))
        uow.clientes.guardar(cliente("C1", frecuente=True))
        uow.clientes.guardar(cliente("C2", activo=False))
        uow.clientes.guardar(cliente("C3", vigencia=date(2025, 12, 31)))
        uow.clientes.guardar(cliente("C4", token="tok_rechazada"))
        uow.clientes.guardar(cliente("C5", token="tok_sin_fondos"))
        uow.clientes.guardar(cliente("C6"))


class Flujo:
    """Atajos para avanzar el negocio paso a paso en las pruebas de servicios."""

    def __init__(self, s, reloj):
        self.s, self.reloj = s, reloj

    def reservar(self, cliente_id="C1", categoria="ECO", sucursal="SUC-MTY", inicio=INICIO, dias=2, actor=None):
        actor = actor or Actor(cliente_id, Rol.CLIENTE)
        return self.s.reservaciones.crear_reservacion(actor, cliente_id, categoria, sucursal, inicio, inicio + timedelta(days=dias))

    def entregar(self, folio, cliente_id="C1", combustible=8, km=1000, danios=()):
        """Llega el cliente a tiempo: entrega, checklist firmado. Devuelve (vehiculo_id, inspeccion)."""
        self.reloj.establecer(INICIO + timedelta(minutes=5))
        ent = self.s.entrega.iniciar_entrega(AGENTE, folio, f"LIC-{cliente_id}")
        insp = self.s.inspecciones.registrar_inspeccion_entrega(PATIO, folio, ent.vehiculo_id, combustible, km, fotos(), list(danios))
        insp = self.s.inspecciones.firmar_inspeccion_entrega(Actor(cliente_id, Rol.CLIENTE), insp.id, f"Cliente {cliente_id}")
        return ent.vehiculo_id, insp

    def abrir(self, cliente_id="C1", **kw):
        folio = self.reservar(cliente_id, **{k: v for k, v in kw.items() if k in ("categoria", "sucursal", "inicio", "dias")}).folio
        vehiculo_id, insp = self.entregar(folio, cliente_id)
        contrato = self.s.contratos.abrir_contrato(AGENTE, folio, vehiculo_id, insp.id)
        return folio, vehiculo_id, contrato

    def devolver(self, contrato, retraso=timedelta(0), combustible=8, km=1200, danios=()):
        self.reloj.establecer(contrato.fin + retraso)
        self.s.inspecciones.registrar_inspeccion_devolucion(PATIO, contrato.id, combustible, km, fotos(), list(danios))
        return self.s.contratos.procesar_devolucion(AGENTE, contrato.id)
