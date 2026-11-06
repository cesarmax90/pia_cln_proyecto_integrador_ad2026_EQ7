# Glosario de dominio · NovaRent (lenguaje ubicuo)

Los mismos términos se usan en el negocio, los documentos y el código (clases, métodos y eventos en español).

| # | Concepto | Definición | En el código |
| :--- | :--- | :--- | :--- |
| 1 | Reservación | Compromiso del cliente para rentar una categoría de vehículo en fechas y sucursal definidas, sin unidad asignada aún | `Reservacion` |
| 2 | Categoría de vehículo | Agrupación por tamaño/tipo (económico, SUV) con tarifa y km incluido propios | `CategoriaVehiculo` |
| 3 | Unidad | Vehículo físico específico dentro de una categoría | `Vehiculo` |
| 4 | Contrato de renta | Acuerdo activo desde la entrega hasta la devolución, con fechas, cargos y condiciones | `ContratoRenta` |
| 5 | Checklist de entrega | Registro de combustible, kilometraje, daños existentes y fotos al entregar la unidad | `InspeccionVehiculo` (tipo `ENTREGA`) |
| 6 | Checklist de devolución | Registro equivalente al recibir la unidad, usado para comparar contra el de entrega | `InspeccionVehiculo` (tipo `DEVOLUCION`) |
| 7 | Kilometraje incluido | Kilómetros por día cubiertos por la tarifa base (200 km/día) | `CategoriaVehiculo.km_incluido_por_dia` |
| 8 | Kilometraje excedente | Kilómetros por encima del incluido, cobrados por km ($3 MXN/km) | `PoliticaCargos.cargo_kilometraje` |
| 9 | Depósito de garantía | Monto retenido en la tarjeta del cliente, liberado 5 días hábiles después de una devolución sin incidencias | `Deposito` (dentro de `Liquidacion`) |
| 10 | Cargo adicional | Cobro por daños, combustible faltante, kilometraje excedente o devolución tardía | `Cargo` |
| 11 | Devolución tardía | Entrega posterior a la hora pactada más 29 minutos de tolerancia | `DevolucionTardia` |
| 12 | Extensión de renta | Prolongación del contrato activo antes de su vencimiento | `Extension` |
| 13 | Conductor adicional | Persona distinta al titular autorizada a conducir la unidad | `ConductorAdicional` |
| 14 | Seguro (cobertura) | Protección opcional o incluida contra daños durante la renta | `CoberturaSeguro` |
| 15 | Upgrade de categoría | Asignación de una categoría superior a la reservada, con o sin costo según quién lo autorice | `PoliticaUpgrade` |
| 16 | Upgrade de cortesía | Upgrade sin costo autorizado por Administración fuera del flujo automático | `otorgar_upgrade_cortesia` |
| 17 | Lista de espera | Registro de un cliente que espera disponibilidad de su categoría el mismo día | `EstadoReservacion.EN_LISTA_ESPERA` |
| 18 | Sucursal | Punto físico donde se entregan y reciben vehículos | `Sucursal` |
| 19 | Disponibilidad de flota | Estado en tiempo real de las unidades libres por categoría y sucursal | `ServicioDisponibilidad` |
| 20 | Rotación de vehículo | Tiempo entre la devolución de una unidad y su disponibilidad para la siguiente renta | `TareaLimpieza.horas_de_rotacion` |
| 21 | Incidencia | Daño o anomalía detectada y documentada en un checklist | `RegistroDanio` |
| 22 | Tarifa no reembolsable | Precio reducido que no admite reembolso ante cancelación o no-show | *(fuera de alcance del PIA)* |
| 23 | Combustible faltante | Diferencia de nivel mayor a 1/8 de tanque entre entrega y devolución | `CombustibleFaltante` |
| 24 | Cliente frecuente | Cliente con historial de rentas que recibe prioridad en la asignación | `Cliente.frecuente` |
| 25 | No-show | Cliente que no se presenta a recoger el vehículo dentro de la ventana permitida (2 horas) | `NoShowVencido` |

## Términos agregados en el PIA
| Concepto | Definición | En el código |
| :--- | :--- | :--- |
| Liquidación | Cuenta final de un contrato: cargos, disputas y depósito | `Liquidacion` |
| Disputa | Objeción del cliente a un cargo, resuelta por Administración con la evidencia | `Disputa` |
| Tarea de limpieza | Trabajo abierto automáticamente al devolver una unidad; al completarse la unidad vuelve a estar disponible | `TareaLimpieza` |
| Día hábil | Lunes a viernes, sin los días de descanso obligatorio | `CalendarioHabilMX` |

> Correcciones editoriales respecto a U2: el término 17 traía un carácter ajeno al alfabeto latino ("espeга") y el 13 terminaba con doble punto.
