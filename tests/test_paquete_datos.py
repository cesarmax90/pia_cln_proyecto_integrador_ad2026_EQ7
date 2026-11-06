"""Ejecuta el paquete de datos del PIA (120 casos + 20 transiciones) contra un oráculo independiente."""
import csv
from decimal import Decimal
from pathlib import Path

import pytest

from src.domain.comun import TransicionInvalida
from src.validacion_paquete.ejecutor import (
    cargar_operaciones,
    ejecutar_accion,
    ejecutar_casos,
    ejecutar_transiciones,
    escribir_csv,
    evaluar_caso,
    main,
)
from src.validacion_paquete.modelo import FLUJO_REFERENCIA, EstadoOperacion, beneficio_referencia, puede_procesarse

DATOS = Path(__file__).resolve().parent.parent / "datos"


def leer(nombre):
    with (DATOS / nombre).open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


ACTORES = {a["actor_id"]: a for a in leer("actores.csv")}
PRECIOS = {r["recurso_id"]: Decimal(r["precio_mxn"]) for r in leer("catalogo.csv")}
OPERACIONES = {o["operacion_id"]: o for o in leer("operaciones.csv")}
DETALLE = leer("detalle_operaciones.csv")


def total_independiente(operacion_id: str) -> Decimal:
    """Oráculo: Σ precio × cantidad calculado sin usar el modelo del proyecto."""
    return sum((PRECIOS[d["recurso_id"]] * int(d["cantidad"]) for d in DETALLE if d["operacion_id"] == operacion_id), Decimal("0"))


def oraculo(tipo: str, operacion_id: str) -> bool:
    op, actor = OPERACIONES[operacion_id], ACTORES[OPERACIONES[operacion_id]["actor_id"]]
    lineas = [d for d in DETALLE if d["operacion_id"] == operacion_id]
    if tipo == "validar_operacion":
        return actor["activo"] == "1" and len(lineas) >= 1 and op["autorizado"] == "1"
    return actor["es_preferente"] == "1" and total_independiente(operacion_id) >= Decimal("1500") and op["promocion_activa"] == "0"


class TestPaqueteDeDatos:
    def test_dimensiones_del_paquete(self):
        assert (len(ACTORES), len(PRECIOS), len(OPERACIONES), len(leer("casos_prueba.csv")), len(leer("transiciones_prueba.csv"))) == (40, 20, 60, 120, 20)

    def test_totales_con_decimal_coinciden_con_el_oraculo(self):
        for op_id, op in cargar_operaciones(DATOS).items():
            assert op.total().monto == total_independiente(op_id).quantize(Decimal("0.01"))

    @pytest.mark.parametrize("caso", leer("casos_prueba.csv"), ids=lambda c: c["caso_id"])
    def test_cada_caso_coincide_con_el_oraculo(self, caso):
        resultado, evidencia = evaluar_caso(caso["tipo_prueba"], cargar_operaciones(DATOS)[caso["operacion_id"]])
        esperado = oraculo(caso["tipo_prueba"], caso["operacion_id"])
        assert (resultado == "CUMPLE") is esperado
        assert evidencia.startswith("actor=")  # la evidencia nunca queda vacía

    def test_resultado_completo_y_resumen(self):
        filas = ejecutar_casos(DATOS)
        assert len(filas) == 120 and all(f["resultado_alumno"] in ("CUMPLE", "NO_CUMPLE") for f in filas)
        assert sum(f["resultado_alumno"] == "CUMPLE" for f in filas) == 53
        assert {f["tipo_prueba"] for f in filas} == {"validar_operacion", "evaluar_beneficio"}

    def test_las_specifications_explican_la_falla(self):
        ops = cargar_operaciones(DATOS)
        inactivo = next(o for o in ops.values() if not o.actor.activo)
        assert "actor_activo" in puede_procesarse().fallas(inactivo)
        con_promocion = next(o for o in ops.values() if o.promocion_activa and o.actor.preferente and o.total().monto >= 1500)
        assert beneficio_referencia().fallas(con_promocion) == ["NOT promocion_activa"]

    def test_valor_limite_del_beneficio_es_inclusivo_en_1500(self):
        ops = cargar_operaciones(DATOS)
        base = next(iter(ops.values()))
        from dataclasses import replace

        from src.domain.valores import Dinero
        from src.validacion_paquete.modelo import ActorPaquete, LineaPaquete
        actor = ActorPaquete("A", True, True)
        justo = replace(base, actor=actor, promocion_activa=False, lineas=(LineaPaquete("R", 1, Dinero("1500.00")),))
        debajo = replace(justo, lineas=(LineaPaquete("R", 1, Dinero("1499.99")),))
        assert beneficio_referencia().es_satisfecha_por(justo) and not beneficio_referencia().es_satisfecha_por(debajo)

    def test_tipo_de_prueba_desconocido(self):
        with pytest.raises(ValueError):
            evaluar_caso("otro", next(iter(cargar_operaciones(DATOS).values())))


class TestTransiciones:
    @pytest.mark.parametrize("accion, estado, evento", [
        ("aprobar", "APROBADA", "OperacionAprobada"),
        ("cancelar", "CANCELADA", "OperacionCancelada"),
        ("completar", "DEVUELTA", "OperacionAprobada -> OperacionEntregada -> OperacionDevuelta"),
    ])
    def test_transiciones_validas(self, accion, estado, evento):
        assert ejecutar_accion(accion) == (EstadoOperacion(estado), evento)

    @pytest.mark.parametrize("accion, estado", [
        ("repetir_aprobacion", EstadoOperacion.APROBADA), ("saltar_estado", EstadoOperacion.SOLICITADA)])
    def test_transiciones_invalidas_conservan_el_estado_y_reportan_excepcion(self, accion, estado):
        final, detalle = ejecutar_accion(accion)
        assert final == estado and detalle.startswith("TransicionInvalida")

    def test_accion_desconocida(self):
        with pytest.raises(ValueError):
            ejecutar_accion("teletransportar")

    def test_las_20_transiciones_y_el_flujo_de_referencia(self):
        filas = ejecutar_transiciones(DATOS)
        assert len(filas) == 20 and sum("TransicionInvalida" in f["evidencia"] for f in filas) == 8
        with pytest.raises(TransicionInvalida):
            FLUJO_REFERENCIA.siguiente(EstadoOperacion.CANCELADA, "aprobar")
        assert FLUJO_REFERENCIA.eventos_permitidos(EstadoOperacion.SOLICITADA) == ["aprobar", "cancelar"]


def test_genera_los_csv_de_evidencia(tmp_path):
    main(str(DATOS), str(tmp_path))
    casos = list(csv.DictReader((tmp_path / "casos_prueba_resultados.csv").open(encoding="utf-8-sig")))
    trans = list(csv.DictReader((tmp_path / "transiciones_prueba_resultados.csv").open(encoding="utf-8-sig")))
    assert len(casos) == 120 and len(trans) == 20 and "PENDIENTE" not in {c["resultado_alumno"] for c in casos}
    assert escribir_csv(tmp_path / "x.csv", [{"a": "1"}]) == 1
