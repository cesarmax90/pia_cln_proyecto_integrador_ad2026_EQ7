# Historias de usuario y criterios de aceptación (Gherkin) · NovaRent

20 historias en 6 épicas. Cada una indica el endpoint que la expone y las pruebas automatizadas que la verifican (`tests/`). Los valores numéricos son las reglas del [BRD, Anexo A](BRD.md).

| Épica | Historias |
| :--- | :--- |
| Reservación | US01, US02, US03, US04 |
| Entrega | US05, US06, US07 |
| Excepción | US08, US09, US10 |
| Extensión | US11, US12 |
| Devolución y cargos | US13, US14, US15, US16, US17 |
| Cierre, limpieza y reportes | US18, US19, US20 |

---
## Épica Reservación

### US01 · Búsqueda de disponibilidad
**Como** cliente **quiero** consultar qué categorías hay libres por sucursal y fechas **para** decidir mi reservación.
`GET /api/v1/disponibilidad` · Pruebas: `test_servicios.py::TestReservaciones::test_disponibilidad_descuenta_reservaciones_activas`, `test_periodos_que_no_se_traslapan_no_restan`

```gherkin
# language: es
Característica: Búsqueda de disponibilidad
  Escenario: Una reservación activa descuenta una unidad
    Dado que la categoría ECO tiene 2 unidades en la sucursal Monterrey
    Y existe una reservación activa de ECO del 6 al 8 de noviembre
    Cuando el cliente consulta la disponibilidad de ECO para ese periodo
    Entonces el sistema responde 1 unidad disponible

  Escenario: Periodos que no se traslapan no restan
    Dado que existe una reservación de ECO del 6 al 8 de noviembre
    Cuando se consulta ECO del 8 al 10 de noviembre
    Entonces el sistema responde 2 unidades disponibles

  Escenario: Las categorías deshabilitadas no se ofrecen
    Cuando se consulta la disponibilidad sin indicar categoría
    Entonces solo aparecen las categorías habilitadas
```

### US02 · Generación de reservación sin asignación de unidad
**Como** cliente **quiero** reservar una categoría **para** garantizar mi renta sin que se fije una unidad física.
`POST /api/v1/reservaciones` · Pruebas: `test_sin_unidades_no_se_puede_reservar`, `test_validaciones_de_entrada`, `test_un_cliente_no_reserva_ni_consulta_a_nombre_de_otro`

```gherkin
# language: es
Característica: Generación de reservación
  Escenario: Reservación exitosa
    Dado un cliente activo y una categoría con unidades libres
    Cuando crea una reservación con inicio en el futuro
    Entonces la reservación queda CREADA con la tarifa vigente y sin vehículo asignado
    Y se emite el evento ReservacionCreada

  Escenario: Sin unidades disponibles
    Dado que la categoría ya está comprometida en ese periodo
    Cuando el cliente intenta reservar
    Entonces el sistema responde 409 sin_disponibilidad

  Escenario: Un cliente no reserva a nombre de otro
    Cuando el cliente C6 intenta reservar para el cliente C1
    Entonces el sistema responde 403 permiso_denegado
```

### US03 · Cancelación de reservación y políticas de penalización
**Como** cliente **quiero** cancelar mi reservación **para** no pagar si cambio de planes.
`POST /api/v1/reservaciones/{folio}/cancelar` · Pruebas: `test_agregados.py::TestReservacion::test_cancelacion_gratuita_con_24h_o_mas`, `test_cancelacion_tardia_penaliza_un_dia`, `test_maquina_y_especificaciones.py::test_cancelacion_gratuita_desde_24_horas`

```gherkin
# language: es
Característica: Cancelación de reservación
  Escenario: Cancelación gratuita con 24 horas o más
    Dado una reservación que inicia en 24 horas
    Cuando el cliente la cancela
    Entonces queda CANCELADA sin penalización

  Escenario: Cancelación tardía
    Dado una reservación que inicia en 23 horas
    Cuando el cliente la cancela
    Entonces queda CANCELADA con penalización de 1 día de tarifa

  Escenario: No se cancela dos veces
    Dado una reservación CANCELADA
    Cuando se intenta cancelar de nuevo
    Entonces el sistema responde 409 transicion_invalida
```

### US04 · Gestión de no-show y liberación de reservaciones
**Como** sistema **quiero** liberar las reservaciones cuyo cliente no se presentó **para** devolver la unidad a la disponibilidad.
`POST /api/v1/reservaciones/liberar-no-shows` (job) · Pruebas: `test_job_de_no_show_libera_solo_las_vencidas`, `test_no_show_a_las_2_horas_exactas`

```gherkin
# language: es
Característica: No-show
  Escenario: Antes de 2 horas no se libera
    Dado una reservación cuyo inicio fue hace 1 hora con 59 minutos
    Cuando corre el job de no-show
    Entonces la reservación sigue CREADA

  Escenario: A las 2 horas se libera
    Dado una reservación cuyo inicio fue hace 2 horas
    Cuando corre el job de no-show
    Entonces queda LIBERADA_NO_SHOW y se emite ReservacionLiberadaPorNoShow

  Escenario: El job no repite
    Cuando el job corre por segunda vez
    Entonces no libera ninguna reservación más
```

---
## Épica Entrega

### US05 · Validación de documentos y método de pago
**Como** agente **quiero** validar licencia y tarjeta antes de entregar **para** rentar solo a clientes aptos.
`POST /api/v1/reservaciones/{folio}/entrega` · Pruebas: `test_validacion_de_documentos_y_pago`, `test_cliente_que_se_inactiva_despues_no_recibe_unidad`, `test_maquina_y_especificaciones.py::test_cliente_apto_combina_tres_reglas`

```gherkin
# language: es
Característica: Validación de documentos y método de pago
  Escenario: Licencia que no coincide
    Cuando el agente captura una licencia distinta a la del cliente
    Entonces el sistema responde 422 "no coincide"

  Escenario: Tarjeta rechazada por la pasarela
    Dado un cliente cuyo método de pago es rechazado
    Entonces el sistema responde 422 "método de pago"

  Escenario: Cliente no apto
    Dado un cliente con licencia vencida
    Entonces el sistema responde 422 "Cliente no apto" y lista LicenciaVigente

  Escenario: Cliente apto
    Dado un cliente activo, con licencia vigente y tarjeta válida
    Entonces se asigna la unidad con menos kilometraje y queda ASIGNADA
```

### US06 · Inspección previa y checklist con evidencias
**Como** personal de patio **quiero** registrar combustible, kilometraje, daños y fotos **para** documentar el estado inicial.
`POST /api/v1/inspecciones/entrega` · Pruebas: `test_inspeccion_exige_vehiculo_asignado_y_no_duplicarse`, `test_las_fotos_se_guardan_con_sello_de_tiempo_del_servidor`, `test_foto_con_base64_invalido`

```gherkin
# language: es
Característica: Checklist de entrega
  Escenario: Sin fotos no hay checklist
    Cuando el patio registra un checklist sin fotos
    Entonces el sistema responde 422 "al menos una foto"

  Escenario: Las fotos llevan sello de tiempo del servidor
    Cuando se registra un checklist con 2 fotos y 1 daño con foto
    Entonces las 3 fotos se guardan con URIs distintas y el mismo sello de tiempo del servidor

  Escenario: Solo se inspecciona un vehículo asignado
    Dado un vehículo que no está ASIGNADO a la entrega
    Entonces el sistema rechaza el checklist
```

### US07 · Aceptación y firma digital del checklist
**Como** cliente **quiero** firmar el checklist **para** dejar constancia de cómo recibo la unidad.
`POST /api/v1/inspecciones/{id}/firma` · Pruebas: `test_firma_solo_del_propietario_y_una_vez`, `test_agregados.py::TestInspeccion::test_firmar_la_hace_inmutable_y_emite_evento_de_entrega`

```gherkin
# language: es
Característica: Firma del checklist
  Escenario: Firma válida
    Cuando el titular firma el checklist de entrega
    Entonces queda firmado y se emite InspeccionEntregaFirmada

  Escenario: Un checklist firmado es inmutable
    Dado un checklist firmado
    Cuando se intenta firmar de nuevo o agregar un daño
    Entonces el sistema responde 422

  Escenario: Solo el titular firma
    Cuando otro cliente intenta firmar
    Entonces el sistema responde 403
```

---
## Épica Excepción

### US08 · Upgrade automático sin costo por falta de unidad
**Como** agente **quiero** ofrecer la categoría inmediata superior cuando no hay unidad **para** cumplir la garantía de servicio.
`POST /api/v1/reservaciones/{folio}/entrega` · Pruebas: `test_sin_unidad_se_ofrece_upgrade_sin_costo_y_conserva_la_tarifa`, `test_sin_categoria_superior_con_unidades_no_hay_upgrade`

```gherkin
# language: es
Característica: Upgrade por falta de unidad
  Escenario: Se ofrece la categoría inmediata superior
    Dado que no queda ninguna unidad ECO disponible
    Cuando el agente inicia la entrega
    Entonces la reservación pasa a UPGRADE_OFRECIDO con categoría COMP y se emite UpgradeOfrecido

  Escenario: El upgrade no cambia el precio
    Dado que el cliente acepta el upgrade
    Cuando se abre el contrato
    Entonces el contrato es de COMP pero conserva la tarifa de ECO

  Escenario: No hay categoría superior con unidades
    Entonces el sistema responde 409 sin_disponibilidad
```

### US09 · Alternativas ante rechazo de upgrade
**Como** cliente **quiero** rechazar el upgrade y elegir lista de espera o reembolso **para** no aceptar algo que no quiero.
`POST /api/v1/reservaciones/{folio}/upgrade/respuesta` · Pruebas: `test_rechazo_a_lista_de_espera_y_a_reembolso`, `test_rechazo_con_reembolso_cancela`, `test_agregados.py::test_rechazo_de_upgrade_restituye_la_categoria_reservada`

```gherkin
# language: es
Característica: Rechazo de upgrade
  Escenario: Lista de espera
    Dado un upgrade ofrecido
    Cuando el cliente responde RECHAZAR_LISTA_ESPERA
    Entonces la reservación queda EN_LISTA_ESPERA con su categoría original

  Escenario: Reembolso
    Cuando el cliente responde RECHAZAR_REEMBOLSO
    Entonces la reservación queda CANCELADA

  Escenario: Respuesta fuera del catálogo
    Cuando el cliente responde "QUIZA"
    Entonces el sistema responde 422
```

### US10 · Autorización administrativa de upgrades de cortesía
**Como** administración **quiero** otorgar un upgrade de cortesía **para** compensar a un cliente fuera del flujo automático.
`POST /api/v1/reservaciones/{folio}/upgrade/cortesia` · Pruebas: `test_upgrade_de_cortesia_lo_otorga_solo_administracion`, `test_cortesia_sin_categoria_superior`

```gherkin
# language: es
Característica: Upgrade de cortesía
  Escenario: Solo Administración lo otorga
    Cuando un agente intenta otorgar el upgrade de cortesía
    Entonces el sistema responde 403
    Cuando Administración lo otorga
    Entonces la reservación queda UPGRADE_ACEPTADO y se emite UpgradeCortesiaOtorgado con quien lo autorizó
```

---
## Épica Extensión

### US11 · Extensión estándar de contrato (hasta 48 horas)
**Como** agente **quiero** extender una renta hasta 48 h **para** atender al cliente sin trámite adicional.
`POST /api/v1/contratos/{id}/extensiones` · Pruebas: `TestExtensiones::test_hasta_48h_la_aprueba_el_agente`, `test_la_extension_no_puede_chocar_con_reservaciones_futuras`, `test_reglas_de_anticipacion`

```gherkin
# language: es
Característica: Extensión estándar
  Escenario: Hasta 48 horas la aprueba el agente
    Dado un contrato que vence en 10 horas
    Cuando el agente solicita 24 horas más
    Entonces la extensión queda APROBADA, el fin se corre 24 h y se emite RentaExtendida

  Escenario: Se pide con menos de 2 horas de anticipación
    Cuando faltan 1 hora o menos para vencer
    Entonces el sistema responde 422 "anticipación"

  Escenario: Choca con reservaciones futuras
    Dado que no queda unidad de la categoría en el nuevo lapso
    Entonces el sistema responde 409
```

### US12 · Autorización administrativa para extensiones mayores a 48 horas
**Como** administración **quiero** autorizar extensiones largas **para** controlar el riesgo operativo.
`POST /api/v1/contratos/{id}/extensiones/{ext}/aprobacion` · Pruebas: `test_mas_de_48h_requiere_administracion`, `test_agregados.py::TestContrato::test_extension_mayor_a_48h_queda_pendiente_y_la_aprueba_administracion`

```gherkin
# language: es
Característica: Extensión mayor a 48 horas
  Escenario: Queda pendiente
    Cuando el agente solicita 72 horas
    Entonces la extensión queda PENDIENTE, el contrato no cambia y se emite ExtensionRequiereAutorizacion

  Escenario: Solo Administración aprueba
    Cuando un agente intenta aprobarla
    Entonces el sistema responde 403
    Cuando Administración la aprueba antes del vencimiento
    Entonces el fin del contrato se corre 72 horas

  Escenario: No se aprueba una extensión vencida
    Dado que el contrato ya venció
    Entonces el sistema responde 422
```

---
## Épica Devolución y cargos

### US13 · Inspección de devolución y checklist de entrada
**Como** personal de patio **quiero** registrar el estado final **para** comparar contra la entrega.
`POST /api/v1/contratos/{id}/inspeccion-devolucion` · Pruebas: `test_precondiciones_de_la_devolucion`, `test_agregados.py::TestInspeccion::test_comparar_detecta_km_combustible_y_danios_nuevos`

```gherkin
# language: es
Característica: Checklist de devolución
  Escenario: Se compara contra la entrega
    Dado un checklist de entrega con 1000 km y 8/8 de combustible
    Cuando la devolución registra 1450 km, 5/8 y un daño nuevo
    Entonces la diferencia es 450 km, 3/8 faltantes y 1 daño nuevo

  Escenario: El kilometraje no retrocede
    Cuando la devolución registra menos km que la entrega
    Entonces el sistema responde 400

  Escenario: Sin checklist no hay devolución
    Cuando se intenta procesar la devolución sin checklist
    Entonces el sistema responde 422 "checklist de devolución"
```

### US14 · Cargo automático por kilometraje excedente
`POST /api/v1/contratos/{id}/devolucion` · Pruebas: `test_politicas.py::TestCargoPorKilometraje`

```gherkin
# language: es
Característica: Kilometraje excedente
  Esquema del escenario: 200 km por día incluidos, $3 MXN por km extra
    Dado un contrato de <dias> días
    Cuando se recorren <km> km
    Entonces el cargo por kilometraje es <cargo>
    Ejemplos:
      | dias | km  | cargo      |
      | 2    | 400 | sin cargo  |
      | 2    | 401 | $3.00      |
      | 2    | 500 | $300.00    |
```

### US15 · Cobro por faltante de combustible según tolerancia
Pruebas: `test_politicas.py::TestCargoPorCombustible`, `test_maquina_y_especificaciones.py::test_combustible_faltante_mayor_a_un_octavo`

```gherkin
# language: es
Característica: Combustible faltante
  Esquema del escenario: Sin cargo hasta 1/8 de tanque
    Cuando faltan <faltan> octavos al devolver
    Entonces el cargo por combustible es <cargo>
    Ejemplos:
      | faltan | cargo   |
      | 1      | sin cargo |
      | 2      | $100.00 |
      | 4      | $200.00 |
```

### US16 · Penalización por devolución tardía tras ventana de gracia
Pruebas: `test_politicas.py::TestCargoPorRetraso`

```gherkin
# language: es
Característica: Devolución tardía
  Esquema del escenario: 29 minutos de tolerancia, cobro por hora, tope de un día
    Dado una tarifa diaria de $480
    Cuando la unidad llega <retraso> después de la hora pactada
    Entonces el cargo por retraso es <cargo>
    Ejemplos:
      | retraso    | cargo    |
      | 29 minutos | sin cargo |
      | 30 minutos | $20.00   |
      | 61 minutos | $40.00   |
      | 40 horas   | $480.00  |
```

### US17 · Resolución de disputas por daños mediante comparación de evidencias
**Como** cliente **quiero** disputar un cargo **para** que Administración lo revise con la evidencia de entrega y devolución.
`POST …/cargos/{id}/disputa` · `GET …/cargos/{id}/evidencia` · `POST …/cargos/{id}/resolucion` · Pruebas: `test_ciclo_completo_con_cargos_disputa_limpieza_y_deposito`, `test_agregados.py::TestLiquidacion::test_disputa_y_resolucion`

```gherkin
# language: es
Característica: Disputa de cargos
  Escenario: Disputa y resolución con evidencia
    Dado un cargo por daño de $800 aprobado por Administración
    Cuando el cliente lo disputa con el motivo "ya estaba rayada"
    Entonces el cargo queda DISPUTADO y deja de sumar al total
    Y Administración compara los checklists: el daño es nuevo
    Cuando Administración resuelve ANULADO
    Entonces el cargo queda ANULADO y ya no hay incidencias

  Escenario: La resolución es definitiva
    Dado un cargo con disputa resuelta
    Cuando el cliente intenta disputarlo otra vez
    Entonces el sistema responde 422

  Escenario: Solo el propietario disputa y solo Administración resuelve
    Entonces cualquier otro rol recibe 403
```

---
## Épica Cierre, limpieza y reportes

### US18 · Vehículo disponible tras reacondicionamiento
`POST /api/v1/limpieza/tareas/{id}/completar` · Pruebas: `test_servicios.py::TestIdempotenciaDeHandlers::test_repetir_limpieza_y_cierre`, `test_agregados.py::TestVehiculoYLimpieza`

```gherkin
# language: es
Característica: Vehículo listo para rentar
  Escenario: Devolución abre la tarea de limpieza
    Cuando se procesa la devolución
    Entonces el vehículo queda EN_LIMPIEZA y se crea una tarea ABIERTA (una sola por devolución)

  Escenario: Completar la tarea libera la unidad
    Cuando Limpieza marca la tarea como completada
    Entonces el vehículo queda DISPONIBLE y se emite VehiculoListoParaRenta

  Escenario: Solo personal autorizado
    Cuando un agente intenta completar la tarea
    Entonces el sistema responde 403
```

### US19 · Reportes operativos y KPIs de flota
`GET /api/v1/reportes/ocupacion` · Pruebas: `TestConsultasYReportes::test_reporte_de_ocupacion_ingresos_y_rotacion`

```gherkin
# language: es
Característica: Reporte de ocupación, ingresos y rotación
  Escenario: Reporte de la sucursal en un rango
    Dado un contrato de $1,000 con $320.83 de cargos y una limpieza de 4 horas
    Cuando Administración pide el reporte de noviembre
    Entonces ingresos de renta = $1,000.00, ingresos por cargos = $320.83, rotación = 4.00 h
    Y la ocupación se calcula como horas-vehículo contratadas entre horas-vehículo disponibles

  Escenario: Rango inválido
    Cuando "hasta" es anterior a "desde"
    Entonces el sistema responde 400
```

### US20 · Liberación automatizada de depósitos de garantía
`POST /api/v1/liquidaciones/liberar-depositos` (job diario) · Pruebas: `test_deposito_se_libera_a_5_dias_habiles_sin_incidencias`, `test_con_incidencia_el_deposito_no_se_libera`, `test_infraestructura.py::TestCalendarioHabil`

```gherkin
# language: es
Característica: Liberación del depósito
  Escenario: A 5 días hábiles y sin incidencias
    Dado una devolución el domingo 8 de noviembre
    Cuando el job corre el jueves 12 de noviembre
    Entonces el depósito sigue RETENIDO
    Cuando el job corre el viernes 13 de noviembre
    Entonces el depósito queda LIBERADO, se libera en la pasarela y el contrato queda CERRADO

  Escenario: Con una incidencia el depósito se retiene
    Dado un cargo por daño sin resolver
    Entonces el depósito no se libera aunque pase el plazo

  Escenario: Los festivos no cuentan
    Dado que el lunes 16 de noviembre es día de descanso obligatorio
    Entonces ese día no cuenta como hábil
```
