"""Ejecuta casos_prueba.csv (120) y transiciones_prueba.csv (20) y genera la evidencia por caso."""
from __future__ import annotations

import csv
from collections.abc import Iterable
from pathlib import Path

from ..domain.comun import TransicionInvalida
from ..domain.valores import Dinero
from .modelo import (
    EVENTO_POR_TRANSICION,
    FLUJO_REFERENCIA,
    ActorPaquete,
    EstadoOperacion,
    LineaPaquete,
    OperacionPaquete,
    beneficio_referencia,
    puede_procesarse,
)


def _leer(ruta: Path) -> list[dict[str, str]]:
    with ruta.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def cargar_operaciones(carpeta: str | Path) -> dict[str, OperacionPaquete]:
    carpeta = Path(carpeta)
    actores = {
        a["actor_id"]: ActorPaquete(a["actor_id"], a["activo"] == "1", a["es_preferente"] == "1")
        for a in _leer(carpeta / "actores.csv")
    }
    precios = {r["recurso_id"]: Dinero(r["precio_mxn"]) for r in _leer(carpeta / "catalogo.csv")}
    lineas: dict[str, list[LineaPaquete]] = {}
    for d in _leer(carpeta / "detalle_operaciones.csv"):
        lineas.setdefault(d["operacion_id"], []).append(
            LineaPaquete(d["recurso_id"], int(d["cantidad"]), precios[d["recurso_id"]])
        )
    return {
        o["operacion_id"]: OperacionPaquete(
            o["operacion_id"], actores[o["actor_id"]], tuple(lineas.get(o["operacion_id"], [])),
            o["autorizado"] == "1", o["promocion_activa"] == "1",
        )
        for o in _leer(carpeta / "operaciones.csv")
    }


def evaluar_caso(tipo: str, op: OperacionPaquete) -> tuple[str, str]:
    """Devuelve (resultado_alumno, evidencia)."""
    spec = puede_procesarse() if tipo == "validar_operacion" else beneficio_referencia()
    if tipo not in ("validar_operacion", "evaluar_beneficio"):
        raise ValueError(f"Tipo de prueba desconocido: {tipo}")
    cumple = spec.es_satisfecha_por(op)
    contexto = (f"actor={op.actor.id} activo={int(op.actor.activo)} preferente={int(op.actor.preferente)}; "
                f"lineas={len(op.lineas)}; autorizado={int(op.autorizado)}; promocion={int(op.promocion_activa)}; "
                f"total={op.total().monto} MXN")
    if cumple:
        return "CUMPLE", contexto
    return "NO_CUMPLE", f"{contexto}; falla: {', '.join(spec.fallas(op))}"


def ejecutar_casos(carpeta: str | Path) -> list[dict[str, str]]:
    ops = cargar_operaciones(carpeta)
    filas = []
    for caso in _leer(Path(carpeta) / "casos_prueba.csv"):
        resultado, evidencia = evaluar_caso(caso["tipo_prueba"], ops[caso["operacion_id"]])
        filas.append({**caso, "resultado_alumno": resultado, "evidencia": evidencia})
    return filas


def ejecutar_accion(accion: str) -> tuple[EstadoOperacion, str]:
    """Aplica la acción sugerida a una operación SOLICITADA. Devuelve (estado_final, evento_o_excepcion)."""
    estado, eventos = EstadoOperacion.SOLICITADA, []
    secuencias = {
        "aprobar": ["aprobar"], "cancelar": ["cancelar"], "completar": ["aprobar", "entregar", "devolver"],
        "repetir_aprobacion": ["aprobar", "aprobar"], "saltar_estado": ["entregar"],
    }
    if accion not in secuencias:
        raise ValueError(f"Acción desconocida: {accion}")
    for paso in secuencias[accion]:
        try:
            estado = FLUJO_REFERENCIA.siguiente(estado, paso)
            eventos.append(EVENTO_POR_TRANSICION[paso])
        except TransicionInvalida as exc:
            return estado, f"TransicionInvalida: {exc.mensaje}"
    return estado, " -> ".join(eventos)


def ejecutar_transiciones(carpeta: str | Path) -> list[dict[str, str]]:
    filas = []
    for caso in _leer(Path(carpeta) / "transiciones_prueba.csv"):
        estado, detalle = ejecutar_accion(caso["accion_sugerida"])
        filas.append({**caso, "resultado_alumno": f"estado_final={estado.value}", "evidencia": detalle})
    return filas


def escribir_csv(ruta: Path, filas: Iterable[dict[str, str]]) -> int:
    filas = list(filas)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with ruta.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(filas[0].keys()))
        w.writeheader()
        w.writerows(filas)
    return len(filas)


def main(carpeta: str = "datos", salida: str = "docs/evidencias") -> None:
    casos, transiciones = ejecutar_casos(carpeta), ejecutar_transiciones(carpeta)
    escribir_csv(Path(salida) / "casos_prueba_resultados.csv", casos)
    escribir_csv(Path(salida) / "transiciones_prueba_resultados.csv", transiciones)
    cumplen = sum(1 for c in casos if c["resultado_alumno"] == "CUMPLE")
    print(f"{len(casos)} casos ejecutados ({cumplen} CUMPLE, {len(casos) - cumplen} NO_CUMPLE); "
          f"{len(transiciones)} transiciones ejecutadas. Evidencia en {salida}/")


if __name__ == "__main__":
    main()
