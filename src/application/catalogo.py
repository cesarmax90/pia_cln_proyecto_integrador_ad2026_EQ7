"""Consultas de catálogo (solo lectura)."""
from __future__ import annotations

from .base import ServicioBase
from .permisos import exigir, exigir_propietario
from .puertos import Actor


class CatalogoAppService(ServicioBase):
    def listar_categorias(self, actor: Actor):
        exigir(actor, "consultar_catalogo")
        with self.ctx.uow_factory() as uow:
            return uow.categorias.listar()

    def listar_sucursales(self, actor: Actor):
        exigir(actor, "consultar_catalogo")
        with self.ctx.uow_factory() as uow:
            return uow.sucursales.listar()

    def obtener_cliente(self, actor: Actor, cliente_id: str):
        exigir(actor, "consultar_catalogo")
        exigir_propietario(actor, cliente_id)
        with self.ctx.uow_factory() as uow:
            return uow.clientes.obtener(cliente_id)
