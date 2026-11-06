# Adaptación del paquete de datos del PIA

El paquete (`datos/`) describe un modelo de **renta de equipos** con una regla de estados genérica. El propio LEEME lo califica de "modelo de pruebas propuesto" y exige que el PIA se derive del BRD, las historias, el BPMN y el diseño DDD del equipo; si difieren, hay que **documentar las diferencias y adaptar fixtures y oráculos**. Este documento cumple esa instrucción (ver también [ADR-010](architecture/ADR-010-adaptacion-del-paquete-de-datos.md)).

## 1. Diferencias entre el paquete y NovaRent
| Tema | Paquete de datos | NovaRent (BRD, U2/U3) | Decisión |
| :--- | :--- | :--- | :--- |
| Giro | Renta de equipos (proyectores, laptops…) | Renta de **automóviles** por día | Se usa el giro del BRD |
| Recurso | Equipo con `precio_mxn` y `capacidad_o_stock` | Categoría de vehículo con tarifa diaria + unidades físicas | `precio_mxn` → tarifa diaria; `stock` → unidades (tope de 8 por categoría en la demo) |
| Operación | Solicitud con líneas (recurso × cantidad) | Reservación de **una** categoría por periodo | Las líneas se usan solo para validar `Dinero` y las Specifications |
| Estados | SOLICITADA → APROBADA → ENTREGADA → DEVUELTA / CANCELADA | Reservación (7 estados), Contrato (3), Vehículo (4), Cargo (4) | El flujo del paquete se ejecuta con la misma `MaquinaEstados` genérica |
| "Autorización" | Bandera `autorizado` | Roles con reglas por caso de uso (agente ≤ 48 h, Administración > 48 h…) | Se implementa la autorización por rol del BRD |
| Cliente preferente | `es_preferente` | Cliente frecuente (prioridad de asignación) | `es_preferente` → `Cliente.frecuente` |
| Cliente inactivo | `activo = 0` | No apto para rentar | `activo = 0` → cliente inactivo **con licencia vencida** |
| Depósito, km, combustible, retraso | No aparecen | Núcleo del negocio | Se implementan según BRD |

## 2. Correspondencia de entidades y estados
| Paquete | NovaRent |
| :--- | :--- |
| `actores.csv` | `Cliente` (+ empleados demo `AGE-01`, `PAT-01`, `LIM-01`, `ADM-01`) |
| `catalogo.csv` | `CategoriaVehiculo` (nivel por orden de precio) y flota de `Vehiculo` |
| `ciudad` | `Sucursal` |
| `operaciones.csv` + `detalle_operaciones.csv` | Modelo de validación `OperacionPaquete` (`src/validacion_paquete/modelo.py`) |
| SOLICITADA | `Reservacion` CREADA |
| APROBADA | Entrega validada (cliente apto + checklist firmado); no es un estado propio |
| ENTREGADA | `ContratoRenta` ABIERTO |
| DEVUELTA | `ContratoRenta` DEVUELTO |
| CANCELADA | `Reservacion` CANCELADA |

## 3. Cómo se usa el paquete
| Paso de la secuencia del paquete | Implementación |
| :--- | :--- |
| 1. Abrir actores y catálogo; revisar IDs y tipos | `infrastructure/datos_demo.py` (carga con `CARGAR_DATOS_DEMO=true`) |
| 2. Importar operaciones y detalle con claves foráneas | `validacion_paquete/ejecutor.py::cargar_operaciones` |
| 3. Total = Σ precio × cantidad con `Decimal` | `OperacionPaquete.total()` sobre `Dinero`; verificado contra un cálculo independiente (`test_totales_con_decimal_coinciden_con_el_oraculo`) |
| 4. Ejecutar `casos_prueba.csv` y anotar resultado y evidencia | `python -m src.validacion_paquete.ejecutor` → `docs/evidencias/casos_prueba_resultados.csv` |
| 5. Ejecutar `transiciones_prueba.csv` | Mismo comando → `docs/evidencias/transiciones_prueba_resultados.csv` |
| 6. Pruebas unitarias e integración, cobertura ≥ 80 % | `pytest --cov=src` |
| 7. API REST, OpenAPI, Docker Compose, CI/CD | `src/api`, `docs/api/openapi.json`, `docker-compose.yml`, `.github/workflows/ci.yml` |
| 8. Matriz BRD → regla → componente → prueba | [trazabilidad.md](trazabilidad.md) |

## 4. Oráculos adaptados
Los resultados esperados están reservados al docente, así que las pruebas usan un **oráculo independiente**: la regla se vuelve a calcular directamente sobre los CSV (sin usar las clases del proyecto) y se compara con el resultado de las Specifications (`tests/test_paquete_datos.py`).

| Caso | Regla | Oráculo independiente | Implementación bajo prueba |
| :--- | :--- | :--- | :--- |
| `validar_operacion` | `puede_procesarse` | `actor.activo` y `≥ 1 línea` y `autorizado` | `ActorActivo & OperacionConLineas & OperacionAutorizada` |
| `evaluar_beneficio` | `beneficio_referencia` | `preferente` y `Σ precio×cantidad ≥ 1500` y `no promoción` | `ActorPreferente & TotalMinimo(1500) & ~PromocionActiva` |

Valor límite: el total es **inclusivo** en 1,500.00 (1,500.00 cumple; 1,499.99 no).

## 5. Resultados de la ejecución
| Conjunto | Resultado |
| :--- | :--- |
| 120 casos | 53 CUMPLE y 67 NO_CUMPLE; 0 diferencias contra el oráculo independiente |
| `validar_operacion` (60) | 42 CUMPLE · 18 NO_CUMPLE |
| `evaluar_beneficio` (60) | 11 CUMPLE · 49 NO_CUMPLE |
| 20 transiciones | 12 válidas (`aprobar` → APROBADA, `cancelar` → CANCELADA, `completar` → DEVUELTA, ×4 cada una) y 8 rechazadas con `TransicionInvalida` (`repetir_aprobacion` y `saltar_estado`, ×4 cada una) |

Cada fila de los CSV de resultados incluye la columna `evidencia` con el contexto evaluado (por ejemplo `actor=REN-C001 activo=1 preferente=0; lineas=2; autorizado=1; promocion=0; total=8070.00 MXN; falla: preferente`).

### Interpretación de las acciones de transición
| Acción | Secuencia aplicada desde SOLICITADA | Resultado |
| :--- | :--- | :--- |
| `aprobar` | aprobar | APROBADA |
| `cancelar` | cancelar | CANCELADA |
| `completar` | aprobar → entregar → devolver | DEVUELTA |
| `repetir_aprobacion` | aprobar → aprobar | `TransicionInvalida` en la segunda; el estado final conserva APROBADA |
| `saltar_estado` | entregar | `TransicionInvalida`; el estado final conserva SOLICITADA |

> La interpretación de `completar`, `repetir_aprobacion` y `saltar_estado` es nuestra (el paquete solo da el nombre de la acción); está a revisión del docente.
