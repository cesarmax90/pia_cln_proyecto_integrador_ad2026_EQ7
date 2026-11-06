# Business Requirements Document (BRD) · NovaRent

> Documento de análisis de la Unidad 2, integrado al PIA. Se conserva el contenido del equipo y se añade el **Anexo A** (reglas operativas con sus valores) y el **Anexo C** (supuestos agregados en el PIA). Los cambios respecto a U2 están en la sección *Control de cambios*.

| Dato | Valor |
| :--- | :--- |
| Curso | Componentes de Lógica de Negocio · FIME-UANL |
| Caso | Caso 07 · NovaRent (renta de automóviles por día) |
| Documentos relacionados | [Historias de usuario y Gherkin](historias_usuario.md) · [BPMN](bpmn.md) · [Glosario](glosario.md) · [Arquitectura](architecture/README.md) · [Trazabilidad](trazabilidad.md) |

## 1. Contexto
NovaRent renta automóviles por día en varias sucursales. La reservación garantiza **categoría, no unidad**. El proceso central cubre reservación, entrega, devolución y cálculo de cargos adicionales (combustible, kilometraje, retraso, daños). El detalle operativo (tiempos, límites y montos) proviene de una entrevista simulada con el stakeholder (ver Anexo A).

## 2. Problema / Oportunidad
**Problema.** La disponibilidad real de vehículos no está actualizada, los daños iniciales se documentan de forma inconsistente y esto genera reclamaciones de clientes por cargos. La coordinación entre devolución, limpieza y siguiente renta es manual y lenta.

**Oportunidad.** Un proceso digitalizado de checklist con evidencia, cálculo automático de cargos y visibilidad en tiempo real de la flota reduce reclamaciones y mejora la rotación de vehículos.

## 3. Stakeholders
| Stakeholder | Responsabilidad | Rol en el sistema |
| :--- | :--- | :--- |
| Cliente | Renta el vehículo, paga cargos, puede disputar cobros | `CLIENTE` |
| Agente de renta | Atiende mostrador, valida datos, entrega y recibe la unidad | `AGENTE` |
| Personal de patio | Inspecciona físicamente el vehículo y captura el checklist | `PATIO` |
| Limpieza | Prepara la unidad para la siguiente renta | `LIMPIEZA` |
| Administración | Autoriza excepciones, cargos y cortesías; genera reportes | `ADMINISTRACION` |
| Gerencia de sucursal | Define políticas y da seguimiento a KPIs | (usa los reportes) |
| Sistema | Jobs programados (no-show, liberación de depósitos) | `SISTEMA` |

## 4. Alcance
| Tipo | Concepto | Detalle |
| :--- | :--- | :--- |
| Dentro | Reservación | Gestión de categorías, fechas y sucursales |
| Dentro | Entrega y devolución | Registros con checklist digital y evidencia fotográfica |
| Dentro | Cálculo de cargos | Kilometraje excedente, faltante de combustible y retardo |
| Dentro | Gestión de excepciones | Falta de unidad, upgrades, extensiones y disputas por daños |
| Dentro | Depósito de garantía | Retención en tarjeta y proceso de liberación |
| Dentro | Reportes | Ocupación de flota, ingresos y tiempo de rotación |
| Fuera | Facturación | Comprobantes fiscales electrónicos |
| Fuera | Lealtad | Programas de fidelización (salvo la prioridad de asignación) |
| Fuera | Mantenimiento | Gestión preventiva de la flota |
| Fuera | Telemetría | Integración GPS en tiempo real (fase futura) |

## 5. Necesidades del negocio
| Código | Necesidad | Impacto clave |
| :--- | :--- | :--- |
| N1 | Visibilidad en tiempo real de disponibilidad por categoría y sucursal | Optimiza el inventario activo y previene sobreventas |
| N2 | Documentación confiable de daños (fotos con sello de tiempo) | Respaldo probatorio y menos discrepancias con el cliente |
| N3 | Cálculo automático de cargos (combustible, km, retrasos) | Elimina errores manuales y da transparencia al cobro final |
| N4 | Manejo estructurado de la excepción "categoría sin unidad" | Garantía de servicio (upgrades, listas de espera o reembolsos) |
| N5 | Autorización por rol para cancelaciones, upgrades y extensiones | Gobierno de decisiones operativas y control de riesgo financiero |
| N6 | Registro y liberación oportuna del depósito de garantía | Cumple los tiempos prometidos y mejora la experiencia |
| N7 | Coordinación entre devolución, limpieza y nueva disponibilidad | Minimiza el tiempo de inactividad (rotación) |
| N8 | Reducción de reclamaciones por cargos disputados | Conciliación objetiva basada en evidencias auditables |
| N9 | Reportes de ocupación, ingresos y rotación de flota | Soporte a decisiones estratégicas y comerciales |
| N10 | Trazabilidad completa del ciclo de vida de la renta | Auditoría desde la reservación hasta el cierre formal |

## 6. Restricciones
- Tiempo y alcance limitados al periodo del curso.
- Debe integrarse con el método de pago existente (no se define proveedor): se modela como **puerto** `PasarelaPago`, con un adaptador simulado.
- La retención de datos de tarjeta debe seguir buenas prácticas de seguridad: el sistema **solo guarda un token y los últimos 4 dígitos** (`MetodoPagoRef`); el número de tarjeta nunca se almacena.

## 7. Supuestos
- Cada sucursal opera su propia flota física, con visibilidad compartida entre sucursales.
- El checklist se captura desde un dispositivo móvil o tablet del personal de patio.
- Existe conexión a internet estable en sucursal.
- Los montos y tiempos provienen de la entrevista simulada y deben validarse con el negocio real antes de producción.
- La autenticación está fuera del alcance: el actor se simula con los encabezados `X-Actor-Id` y `X-Rol`; **la autorización por rol sí se aplica** en cada caso de uso.

## 8. Criterios de éxito
| Criterio | Cómo lo soporta el sistema |
| :--- | :--- |
| Reducir 30 % las reclamaciones por cargos disputados en 3 meses | Cargos automáticos (N3) + evidencia comparable (US17) |
| Disponibilidad de flota visible en tiempo real, con actualización máxima de 5 minutos | `GET /disponibilidad` consulta el estado vivo; no hay caché |
| Reducir 20 % el tiempo de rotación | Tarea de limpieza automática al devolver + reporte de rotación (US19) |
| 100 % de los checklists con evidencia fotográfica | Invariante del dominio: no existe checklist sin foto con sello de tiempo |

## Anexo A. Reglas operativas (entrevista simulada)
Consolidación de los valores del glosario y del diseño ACT-F03. Cada fila indica dónde vive la regla en el código; todos los valores son **parámetros configurables** (`.env.example`).

| ID | Regla | Valor | Parámetro | Dónde se implementa |
| :--- | :--- | :--- | :--- | :--- |
| RN-01 | Cancelación sin penalización | Con ≥ 24 h de anticipación | `HORAS_CANCELACION_GRATUITA` | `CancelacionSinPenalizacion` · `PoliticaCancelacion` |
| RN-02 | No-show | Se libera a las 2 h del inicio | `HORAS_NO_SHOW` | `NoShowVencido` · `Reservacion.liberar_por_no_show` |
| RN-03 | Kilometraje incluido | 200 km por día | `categoria.km_incluido_por_dia` | `PoliticaCargos.cargo_kilometraje` |
| RN-04 | Kilometraje excedente | $3 MXN por km | `TARIFA_KM_EXCEDENTE` | `PoliticaCargos.cargo_kilometraje` |
| RN-05 | Combustible faltante | Cargo si la diferencia es > 1/8 de tanque | `UMBRAL_COMBUSTIBLE_OCTAVOS` | `CombustibleFaltante` · `PoliticaCargos.cargo_combustible` |
| RN-06 | Devolución tardía | Tolerancia de 29 min; cobro por hora con tope de 1 día | `TOLERANCIA_RETRASO_MIN` | `DevolucionTardia` · `PoliticaCargos.cargo_retraso` |
| RN-07 | Extensión estándar | El agente aprueba hasta 48 h | `LIMITE_EXTENSION_AGENTE_HORAS` | `ExtensionDentroDelLimiteDelAgente` · `PoliticaExtension` |
| RN-08 | Extensión mayor | Más de 48 h requiere Administración | (igual) | `ContratoRenta.aprobar_extension` |
| RN-09 | Anticipación de extensión | Se solicita ≥ 2 h antes del vencimiento | `ANTICIPACION_EXTENSION_HORAS` | `ExtensionConAnticipacion` |
| RN-10 | Depósito de garantía | Se libera a 5 días hábiles de la devolución, sin incidencias | `DIAS_HABILES_LIBERACION_DEPOSITO` | `deposito_liberable()` · `CalendarioHabilMX` |
| RN-11 | Upgrade por falta de unidad | Sin costo, solo a la categoría inmediata superior | — | `PoliticaUpgrade` · `Reservacion.proponer_upgrade` |
| RN-12 | Upgrade de cortesía | Solo Administración, fuera del flujo automático | — | `Reservacion.otorgar_upgrade_cortesia` |
| RN-13 | Checklist | Fotos con sello de tiempo; firmado = inmutable | — | `InspeccionVehiculo` |
| RN-14 | Cargo por daño | El monto lo fija Administración | — | `Liquidacion.aprobar_cargo_danio` |
| RN-15 | Disputa | Se resuelve comparando la evidencia de entrega y devolución | — | `Liquidacion.resolver_disputa` · `consultar_evidencia_disputa` |
| RN-16 | Un contrato, una unidad | Solo un vehículo Disponible se asigna | — | `Vehiculo.asignar_a_entrega` |
| RN-17 | Cliente apto | Activo, licencia vigente y tarjeta válida | — | `cliente_apto()` |

## Anexo B. Matriz de validación y trazabilidad
Necesidad → historias de usuario → proceso BPMN. La matriz completa hasta **regla → componente → prueba** está en [trazabilidad.md](trazabilidad.md).

| Necesidad | Descripción | Historias de usuario | Proceso BPMN |
| :--- | :--- | :--- | :--- |
| N1 | Visibilidad en tiempo real de disponibilidad | US01, US08 | Reservación / Excepción |
| N2 | Documentación confiable de daños | US06, US07, US13 | Entrega / Devolución |
| N3 | Cálculo automático y transparente de cargos | US14, US15, US16 | Devolución y cargos |
| N4 | Categoría sin unidad disponible | US08, US09, US10 | Entrega (excepción) |
| N5 | Autorización controlada por rol | US03, US10, US11, US12 | Reservación / Entrega / Extensión |
| N6 | Depósito de garantía | US20 | Cierre de contrato |
| N7 | Coordinación limpieza-disponibilidad | US18 | Postdevolución |
| N8 | Reducción de reclamaciones | US06, US07, US13, US17 | Devolución / Disputa de daño |
| N9 | Reportes de negocio | US19 | Administración (reporting) |
| N10 | Trazabilidad del ciclo de vida completo | US01 a US20 | Todo el proceso |

## Anexo C. Supuestos agregados en el PIA
El BRD de U2 no fija estos valores y el código los necesita para operar. Están marcados como `SUPUESTO` en `src/domain/politicas.py`, son configurables y **deben validarse con el negocio**.

| ID | Supuesto | Valor por omisión | Motivo |
| :--- | :--- | :--- | :--- |
| S-01 | Penalización por cancelación tardía o no-show | 1 día de tarifa (`DIAS_PENALIZACION`) | U2 menciona "políticas de penalización" sin monto |
| S-02 | Tarifa por octavo de tanque faltante | $50 MXN (`TARIFA_POR_OCTAVO`) | ACT-F03 la deja "por definir" |
| S-03 | Cargo por hora de retraso | Tarifa diaria ÷ 24 por hora iniciada, tope de 1 día | U2 define "cobro por hora con tope de 1 día" sin tarifa horaria |
| S-04 | Combustible faltante | Se cobran **todos** los octavos faltantes cuando la diferencia supera 1/8 | U2 define el umbral, no la base de cobro |
| S-05 | Monto del depósito | Definido por categoría (`CategoriaVehiculo.deposito`); en datos demo, 3 días de tarifa | U2 no fija montos |
| S-06 | Días de renta facturables | Bloques de 24 h, mínimo 1 | Necesario para km incluidos y monto base |
| S-07 | Cargo por conductor joven (< 25 años) | **No implementado**: `Cliente.es_conductor_joven()` lo detecta, falta el monto | ACT-F03 lo menciona sin monto |
| S-08 | Devolución en otra sucursal | El vehículo cambia a la sucursal del contrato; no hay cargo | Fuera del detalle de U2 |

## Control de cambios respecto a U2
| Cambio | Motivo |
| :--- | :--- |
| Se añadieron Anexos A y C | El texto de U2 remite al "Anexo A" sin incluirlo; el PIA exige reglas trazables a código |
| Matriz de trazabilidad: N5 pasa de US12 a US03, US10, US11, US12 | N5 menciona cancelaciones, upgrades y extensiones |
| Matriz de trazabilidad: N6 pasa de US10, US11, US20 a US20 | US10 (upgrade de cortesía) y US11 (extensión) no tratan el depósito |
| Se agregó el rol `SISTEMA` | Los jobs de no-show y liberación de depósitos no los ejecuta una persona |
| Se agregó el estado `CERRADO` del contrato | N10 pide trazabilidad hasta el "cierre formal" |
