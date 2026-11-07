# Pruebas de reglas de negocio (Unidad 5 · Paso 9 / E9)

Adaptación del laboratorio guiado de la Unidad 5 a las reglas reales de NovaRent. Las pruebas ejercitan el código de `src/` (no una copia) y se ejecutan junto con el resto de la suite y del CI.

| Entregable E9 | Dónde está |
| :--- | :--- |
| Matriz CSV (19 casos: 5 éxito, 6 error, 8 límite) | [`matriz_casos_u5.csv`](matriz_casos_u5.csv) |
| Pruebas ejecutables | [`tests/test_u5_matriz_casos.py`](../tests/test_u5_matriz_casos.py) |
| Cobertura | `pytest --cov=src` (el CI la exige ≥ 80 % y publica el reporte HTML como artefacto) |
| Decisiones de diseño | Este documento |

## Reglas seleccionadas

| Regla | Historias · reglas BRD | Componente | Casos |
| :--- | :--- | :--- | :--- |
| R1 · Cargo por kilometraje excedente (200 km/día, $3/km) | US14 · RN-03, RN-04 | `PoliticaCargos.cargo_kilometraje`, `Kilometraje.recorrido_desde` | CP-U5-01 a 04 |
| R2 · Autorización de extensiones por rol (agente hasta 48 h, ≥ 2 h de anticipación) | US11, US12 · RN-07, RN-08, RN-09 | `PoliticaExtension.decidir` | CP-U5-05 a 09 |
| R3 · Cancelación gratuita (≥ 24 h) y no-show (2 h) | US03, US04 · RN-01, RN-02 | `PoliticaCancelacion`, `Reservacion.cancelar` / `liberar_por_no_show` | CP-U5-10 a 15 |
| Persistencia | Transversal (Unit of Work) | `UnidadTrabajoSQL` + repositorios SQLAlchemy | CP-U5-16, 17 |
| Servicio externo (pasarela de pago) | Necesidad N6 (depósito de garantía) | `ContratoAppService.abrir_contrato` + `PasarelaPago` | CP-U5-18, 19 |

Los valores salen del BRD y de `ParametrosNegocio`; no se inventaron reglas nuevas.

## Decisiones de diseño

- **Pruebas sobre el código real.** Se importan las políticas, agregados y servicios de `src/`. Así, un cambio en una regla rompe estas pruebas y el CI lo bloquea. Se verificó con mutaciones temporales (límite del agente 48→47 h, tarifa $3→$4, cancelación gratuita 24→12 h): cada una hizo fallar los casos esperados.
- **Un caso de éxito, uno de error y al menos un límite por regla.** Los límites cubren los valores exactos del BRD: 600 km y 601 km, 48 h y 49 h, 2 h de anticipación, 24 h y 23 h 59 min, 2 h de no-show.
- **Fechas fijas.** Todo recibe `ahora` explícito (`RelojFijo`/constantes), de modo que ningún resultado depende del reloj.
- **Error de la regla de kilometraje.** `PoliticaCargos` no valida kilómetros negativos (un excedente ≤ 0 simplemente no genera cargo); la validación real vive en `Kilometraje.recorrido_desde`, por eso CP-U5-02 prueba ahí el rechazo de un odómetro final menor al inicial.
- **Persistencia sin tocar datos reales.** CP-U5-16 y 17 usan la Unit of Work con la base de pruebas (SQLite en memoria; PostgreSQL en el CI). Cada prueba lee en una transacción nueva para comprobar lo realmente persistido.
- **Mock de la pasarela.** `Mock(spec=[...])` sustituye al puerto `PasarelaPago`; se verifica con qué argumentos se llamó y que no se libera ningún depósito. No existe cobro real. En el rechazo (CP-U5-19) se comprueba que no queda un contrato persistido, porque `abrir_contrato` retiene el depósito antes de guardar y todo ocurre en una sola transacción: esto evita el riesgo de consistencia que el laboratorio señala (confirmar sin pago exitoso).
- **Sin pruebas E2E reales.** La API ya tiene pruebas de integración en `tests/test_api.py`; no se simula una interfaz gráfica que no existe.

## Ejecución

```bash
ruff check src tests scripts
pytest tests/test_u5_matriz_casos.py -v          # solo los 19 casos de E9
pytest --cov=src --cov-report=term-missing --cov-report=html --cov-fail-under=80
```
