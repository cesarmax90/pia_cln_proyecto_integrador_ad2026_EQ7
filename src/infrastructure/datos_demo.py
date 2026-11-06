"""Carga de datos de demostración desde el paquete CSV del PIA (adaptado al dominio NovaRent).

Mapeo documentado en docs/adaptacion_paquete_datos.md:
  actores.csv   -> Cliente (preferente -> cliente frecuente; activo=0 -> cliente inactivo con licencia vencida)
  catalogo.csv  -> CategoriaVehiculo (precio_mxn -> tarifa diaria) y flota de Vehiculos (stock, con tope de demo)
  ciudad        -> Sucursal
"""
from __future__ import annotations

import csv
import unicodedata
from datetime import date, timedelta
from pathlib import Path

from ..domain.catalogo import CategoriaVehiculo, Cliente, Empleado, Sucursal
from ..domain.comun import Rol
from ..domain.valores import Dinero, Kilometraje, Licencia, MetodoPagoRef
from ..domain.vehiculo import Vehiculo

MAX_UNIDADES_DEMO_POR_CATEGORIA = 8
DIAS_DEPOSITO_DEMO = 3  # el BRD no fija el monto del depósito: demo = 3 días de tarifa


def leer_csv(ruta: Path) -> list[dict[str, str]]:
    with ruta.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _slug(texto: str) -> str:
    base = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return "SUC-" + base.strip().upper().replace(" ", "_")


def cargar_demo(uow_factory, ruta_datos: str | Path) -> dict[str, int]:
    """Idempotente: si ya hay categorías no vuelve a cargar."""
    ruta = Path(ruta_datos)
    actores = leer_csv(ruta / "actores.csv")
    catalogo = leer_csv(ruta / "catalogo.csv")
    with uow_factory() as uow:
        if uow.categorias.listar():
            return {}
        ciudades = sorted({a["ciudad"] for a in actores})
        sucursales = [Sucursal(_slug(c), c) for c in ciudades]
        for s in sucursales:
            uow.sucursales.guardar(s)

        empleados = [
            Empleado("AGE-01", "Agente de mostrador", Rol.AGENTE, sucursales[0].id),
            Empleado("PAT-01", "Personal de patio", Rol.PATIO, sucursales[0].id),
            Empleado("LIM-01", "Personal de limpieza", Rol.LIMPIEZA, sucursales[0].id),
            Empleado("ADM-01", "Administración", Rol.ADMINISTRACION, sucursales[0].id),
        ]
        for e in empleados:
            uow.empleados.guardar(e)

        for i, a in enumerate(actores):
            activo = a["activo"] == "1"
            uow.clientes.guardar(Cliente(
                id=a["actor_id"], nombre=a["nombre"], fecha_nacimiento=date(1980, 1, 1) + timedelta(days=i * 263),
                licencia=Licencia(f"LIC-{a['actor_id']}", date(2030, 12, 31) if activo else date(2025, 12, 31)),
                metodo_pago=MetodoPagoRef(f"tok_{a['actor_id']}", f"{4000 + i:04d}"),
                frecuente=a["es_preferente"] == "1", activo=activo,
            ))

        por_precio = sorted(catalogo, key=lambda r: (float(r["precio_mxn"]), r["recurso_id"]))
        niveles = {r["recurso_id"]: n for n, r in enumerate(por_precio, start=1)}
        vehiculos = 0
        for r in catalogo:
            tarifa = Dinero(r["precio_mxn"])
            categoria = CategoriaVehiculo(
                id=r["recurso_id"], nombre=f"Categoría {niveles[r['recurso_id']]:02d}", nivel=niveles[r["recurso_id"]],
                tarifa_diaria=tarifa, deposito=tarifa.por(DIAS_DEPOSITO_DEMO), habilitada=r["habilitado"] == "1",
            )
            uow.categorias.guardar(categoria)
            for n in range(min(int(r["capacidad_o_stock"]), MAX_UNIDADES_DEMO_POR_CATEGORIA)):
                uow.vehiculos.guardar(Vehiculo(
                    id=f"VEH-{r['recurso_id']}-{n + 1:02d}", placa=f"{niveles[r['recurso_id']]:02d}{n + 1:02d}-NVR",
                    categoria_id=categoria.id, sucursal_id=sucursales[n % len(sucursales)].id,
                    kilometraje=Kilometraje(1000 * (n + 1)),
                ))
                vehiculos += 1
    return {
        "sucursales": len(sucursales), "empleados": len(empleados), "clientes": len(actores),
        "categorias": len(catalogo), "vehiculos": vehiculos,
    }
