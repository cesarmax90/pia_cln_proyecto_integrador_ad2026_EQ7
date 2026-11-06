"""Unit of Work: una transacción de base de datos; confirma o revierte todo junto."""
from __future__ import annotations

from sqlalchemy.orm import Session, sessionmaker

from .repositorios import (
    RepositorioCategorias,
    RepositorioClientes,
    RepositorioContratos,
    RepositorioEmpleados,
    RepositorioInspecciones,
    RepositorioLiquidaciones,
    RepositorioReservaciones,
    RepositorioSucursales,
    RepositorioTareas,
    RepositorioVehiculos,
)


class UnidadTrabajoSQL:
    def __init__(self, fabrica_sesiones: sessionmaker):
        self._fabrica = fabrica_sesiones
        self._vistos: list = []
        self.eventos: list = []

    def __enter__(self) -> UnidadTrabajoSQL:
        self.session: Session = self._fabrica()
        self._vistos, self.eventos = [], []
        self.reservaciones = RepositorioReservaciones(self.session, self)
        self.clientes = RepositorioClientes(self.session, self)
        self.categorias = RepositorioCategorias(self.session, self)
        self.sucursales = RepositorioSucursales(self.session, self)
        self.empleados = RepositorioEmpleados(self.session, self)
        self.contratos = RepositorioContratos(self.session, self)
        self.inspecciones = RepositorioInspecciones(self.session, self)
        self.liquidaciones = RepositorioLiquidaciones(self.session, self)
        self.vehiculos = RepositorioVehiculos(self.session, self)
        self.tareas = RepositorioTareas(self.session, self)
        return self

    def registrar(self, agregado) -> None:
        self._vistos.append(agregado)

    def __exit__(self, tipo, valor, traza) -> None:
        try:
            if tipo is None:
                self.session.commit()
                for agregado in self._vistos:  # los eventos solo existen si el commit tuvo éxito
                    self.eventos.extend(agregado.recoger_eventos())
            else:
                self.session.rollback()
        finally:
            self.session.close()
