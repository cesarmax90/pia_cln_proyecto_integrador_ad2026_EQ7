# Matriz de trazabilidad: BRD → historia → regla → componente → prueba

Cómo leerla: cada necesidad del BRD se cubre con historias de usuario; cada historia se implementa con una o más reglas, que viven en un componente concreto y se verifican con pruebas automatizadas (`tests/`). Los ID de regla (RN-xx) están en el [BRD, Anexo A](BRD.md).

## 1. Necesidad → historias → componentes principales
| Necesidad | Historias | Reglas | Componentes principales |
| :--- | :--- | :--- | :--- |
| N1 Disponibilidad en tiempo real | US01, US08 | RN-11, RN-16 | `ServicioDisponibilidad`, `ReservacionAppService.buscar_disponibilidad`, `RepositorioReservaciones.contar_traslapadas` |
| N2 Documentación confiable de daños | US06, US07, US13 | RN-13 | `InspeccionVehiculo`, `EvidenciaFoto`, `AlmacenEvidencia` |
| N3 Cargos automáticos | US14, US15, US16 | RN-03…RN-06 | `PoliticaCargos`, `Liquidacion.calcular_cargos` |
| N4 Categoría sin unidad | US08, US09, US10 | RN-11, RN-12 | `PoliticaUpgrade`, `Reservacion` (upgrade), `EntregaAppService` |
| N5 Autorización por rol | US03, US10, US11, US12 | RN-07, RN-08, RN-12 | `application/permisos.py`, `exigir_rol` en aggregates |
| N6 Depósito de garantía | US20 | RN-10 | `Liquidacion.liberar_deposito`, `CalendarioHabilMX`, `PasarelaPago` |
| N7 Coordinación limpieza-disponibilidad | US18 | — | `TareaLimpieza`, `Vehiculo`, eventos `VehiculoDevuelto` y `TareaLimpiezaCompletada` |
| N8 Menos reclamaciones | US06, US07, US13, US17 | RN-13…RN-15 | `Liquidacion` (disputas), `consultar_evidencia_disputa` |
| N9 Reportes | US19 | — | `ReporteAppService`, `ConsultasSQL` |
| N10 Trazabilidad del ciclo de vida | US01…US20 | RN-16 | Máquinas de estados, `ContratoRenta.cerrar`, eventos de dominio |

## 2. Historia → regla → componente → prueba → endpoint
| US | Regla | Componente (código) | Prueba automatizada | Endpoint |
| :--- | :--- | :--- | :--- | :--- |
| US01 | Disponibilidad = flota − reservas − contratos traslapados | `ServicioDisponibilidad` · `RepositorioReservaciones` | `test_servicios::TestReservaciones::test_disponibilidad_descuenta_reservaciones_activas` · `test_politicas::test_unidades_disponibles_nunca_son_negativas` | `GET /disponibilidad` |
| US02 | La reservación garantiza categoría, no unidad; cliente activo | `Reservacion.crear` | `test_sin_unidades_no_se_puede_reservar` · `test_validaciones_de_entrada` | `POST /reservaciones` |
| US03 | RN-01 cancelación gratis ≥ 24 h | `CancelacionSinPenalizacion` · `PoliticaCancelacion` · `Reservacion.cancelar` | `test_agregados::TestReservacion::test_cancelacion_*` · `test_cancelacion_gratuita_desde_24_horas` | `POST /reservaciones/{folio}/cancelar` |
| US04 | RN-02 no-show a las 2 h | `NoShowVencido` · `Reservacion.liberar_por_no_show` | `test_job_de_no_show_libera_solo_las_vencidas` · `test_no_show_a_las_2_horas_exactas` | `POST /reservaciones/liberar-no-shows` |
| US05 | RN-17 cliente apto | `cliente_apto()` (AND de 3 specs) | `test_validacion_de_documentos_y_pago` · `test_cliente_apto_combina_tres_reglas` | `POST /reservaciones/{folio}/entrega` |
| US06 | RN-13 fotos con sello de tiempo | `InspeccionVehiculo.registrar` · `EvidenciaFoto` | `test_las_fotos_se_guardan_con_sello_de_tiempo_del_servidor` · `test_sin_fotos_se_rechaza` | `POST /inspecciones/entrega` |
| US07 | RN-13 firmado = inmutable | `InspeccionVehiculo.firmar` | `test_firma_solo_del_propietario_y_una_vez` · `test_firmar_la_hace_inmutable…` | `POST /inspecciones/{id}/firma` |
| US08 | RN-11 upgrade solo a la inmediata superior, sin costo | `PoliticaUpgrade` · `Reservacion.proponer_upgrade` | `test_sin_unidad_se_ofrece_upgrade_sin_costo_y_conserva_la_tarifa` · `test_categoria_superior_es_la_habilitada…` | `POST /reservaciones/{folio}/entrega` |
| US09 | Lista de espera o reembolso | `Reservacion.rechazar_upgrade` | `test_rechazo_a_lista_de_espera_y_a_reembolso` · `test_rechazo_con_reembolso_cancela` | `POST …/upgrade/respuesta` |
| US10 | RN-12 solo Administración | `Reservacion.otorgar_upgrade_cortesia` | `test_upgrade_de_cortesia_lo_otorga_solo_administracion` | `POST …/upgrade/cortesia` |
| US11 | RN-07, RN-09 hasta 48 h, ≥ 2 h antes | `PoliticaExtension` · `ContratoRenta.solicitar_extension` | `TestExtensiones::test_hasta_48h_la_aprueba_el_agente` · `test_reglas_de_anticipacion` | `POST /contratos/{id}/extensiones` |
| US12 | RN-08 más de 48 h → Administración | `ContratoRenta.aprobar_extension` | `test_mas_de_48h_requiere_administracion` · `test_administracion_extiende_directo_y_no_se_aprueba_tarde` | `POST …/extensiones/{ext}/aprobacion` |
| US13 | Comparar devolución vs entrega | `InspeccionVehiculo.comparar_contra` | `test_comparar_detecta_km_combustible_y_danios_nuevos` · `test_precondiciones_de_la_devolucion` | `POST …/inspeccion-devolucion` |
| US14 | RN-03, RN-04 200 km/día, $3/km | `PoliticaCargos.cargo_kilometraje` | `test_politicas::TestCargoPorKilometraje` | `POST …/devolucion` |
| US15 | RN-05 > 1/8 de tanque | `CombustibleFaltante` · `PoliticaCargos.cargo_combustible` | `TestCargoPorCombustible` · `test_combustible_faltante_mayor_a_un_octavo` | `POST …/devolucion` |
| US16 | RN-06 29 min, por hora, tope 1 día | `DevolucionTardia` · `PoliticaCargos.cargo_retraso` | `TestCargoPorRetraso` · `test_devolucion_tardia_con_tolerancia_de_29_minutos` | `POST …/devolucion` |
| US17 | RN-14, RN-15 disputa con evidencia | `Liquidacion.disputar_cargo` · `resolver_disputa` | `test_disputa_y_resolucion` · `test_ciclo_completo_con_cargos_disputa_limpieza_y_deposito` | `POST …/cargos/{id}/disputa` · `/evidencia` · `/resolucion` |
| US18 | Una tarea por devolución; Limpieza libera la unidad | `TareaLimpieza` · `FlotaAppService.marcar_disponible` | `TestVehiculoYLimpieza` · `test_repetir_limpieza_y_cierre` | `POST /limpieza/tareas/{id}/completar` |
| US19 | Ocupación, ingresos y rotación | `ConsultasSQL.reporte_ocupacion` | `test_reporte_de_ocupacion_ingresos_y_rotacion` | `GET /reportes/ocupacion` |
| US20 | RN-10 5 días hábiles sin incidencias | `deposito_liberable()` · `Liquidacion.liberar_deposito` | `test_deposito_se_libera_a_5_dias_habiles_sin_incidencias` · `test_con_incidencia_el_deposito_no_se_libera` | `POST /liquidaciones/liberar-depositos` |

## 3. Seguridad de negocio (pruebas transversales)
| Riesgo | Control | Prueba |
| :--- | :--- | :--- |
| Un cliente actúa sobre recursos de otro | `exigir_propietario` | `test_un_cliente_no_reserva_ni_consulta_a_nombre_de_otro`, `test_consultar_contrato_solo_el_propietario` |
| Un rol ejecuta un caso de uso ajeno | `permisos.exigir` + `exigir_rol` en aggregates | `TestPermisosPorRol` (8 casos), `test_solo_administracion_fija_el_monto_del_danio` |
| Evidencia alterada tras firmar | Checklist inmutable | `test_firmar_la_hace_inmutable_y_emite_evento_de_entrega` |
| Evidencia sobrescrita | URIs únicas por foto | `test_las_fotos_se_guardan_con_sello_de_tiempo_del_servidor` |
| Path traversal en nombres de foto | Saneado de nombres | `test_almacen_de_evidencia_sanea_nombres` |
| Almacenar el número de tarjeta | `MetodoPagoRef` rechaza 13–19 dígitos | `test_metodo_pago_nunca_guarda_numero_de_tarjeta` |
| Cobros duplicados por eventos repetidos | Handlers idempotentes | `TestIdempotenciaDeHandlers` |
| Transacción a medias | Unit of Work con rollback | `test_rollback_ante_excepcion_no_persiste_nada`, `test_no_se_abre_dos_veces_ni_con_banco_que_rechaza` |
