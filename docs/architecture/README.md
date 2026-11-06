# Arquitectura · NovaRent

Implementa el diseño de la Unidad 3 (ACT-F03): **Domain Model + Service Layer**, con **Repository**, **Unit of Work**, **Domain Events**, **Specification** y **State Machine**, y **consultas directas** para reportes (CQRS básico). Las decisiones están en los [ADR](#decisiones-de-arquitectura-adr).

## 1. Capas y dependencias
Las flechas son dependencias de código. **El dominio no importa nada de FastAPI, SQLAlchemy ni de la infraestructura**; la aplicación depende de *puertos* (interfaces) que la infraestructura implementa (Inversión de Dependencias).

```mermaid
flowchart TD
    API["API REST - FastAPI<br/>src/api"] --> APP["Application Services y DTOs<br/>src/application"]
    APP --> DOM["Dominio: Aggregates, Value Objects,<br/>Specifications, Politicas, Eventos<br/>src/domain"]
    APP -. "usa puertos" .-> PUERTOS["Puertos: UnidadDeTrabajo, Reloj, PasarelaPago,<br/>AlmacenEvidencia, BusEventos, CalendarioHabil"]
    INFRA["Infraestructura: SQLAlchemy, Repositorios, UoW,<br/>adaptadores<br/>src/infrastructure"] -. "implementa" .-> PUERTOS
    INFRA --> DOM
    COMP["Composition Root<br/>src/composicion.py"] --> API
    COMP --> INFRA
    COMP --> APP
```

| Capa | Carpeta | Responsabilidad | No debe |
| :--- | :--- | :--- | :--- |
| API | `src/api` | Traducir HTTP ⇄ comandos/DTO; mapear errores a códigos HTTP | Contener reglas de negocio |
| Aplicación | `src/application` | Orquestar casos de uso, transacciones, permisos por rol y publicación de eventos | Decidir reglas (las decide el dominio) |
| Dominio | `src/domain` | Reglas, invariantes, estados y eventos | Conocer HTTP, SQL o frameworks |
| Infraestructura | `src/infrastructure` | Persistencia, pasarela, evidencia, calendario, bus | Contener reglas de negocio |

## 2. Mapa del dominio (un Aggregate = una transacción)
```mermaid
classDiagram
    class Reservacion {
      +folio +estado +periodo +tarifa_diaria
      +cancelar() +liberar_por_no_show()
      +proponer_upgrade() +rechazar_upgrade() +otorgar_upgrade_cortesia()
    }
    class ContratoRenta {
      +id +estado +periodo +referencia_pago
      +solicitar_extension() +aprobar_extension()
      +registrar_devolucion() +cerrar()
    }
    class InspeccionVehiculo {
      +tipo ENTREGA/DEVOLUCION +fotos +danios +firma
      +firmar() +comparar_contra()
    }
    class Liquidacion {
      +cargos +deposito
      +calcular_cargos() +aprobar_cargo_danio()
      +disputar_cargo() +resolver_disputa() +liberar_deposito()
    }
    class Vehiculo { +estado +kilometraje +asignar_a_entrega() +marcar_rentado() }
    class TareaLimpieza { +estado +completar() }
    class Cliente { +licencia +metodo_pago +puede_rentar() }
    class CategoriaVehiculo { +nivel +tarifa_diaria +deposito }
    ContratoRenta "1" --> "1" Reservacion : convierte
    ContratoRenta "1" --> "1" Vehiculo : usa
    InspeccionVehiculo "2" --> "1" ContratoRenta : entrega y devolucion
    Liquidacion "1" --> "1" ContratoRenta : liquida
    TareaLimpieza "n" --> "1" Vehiculo : prepara
    Reservacion --> Cliente
    Reservacion --> CategoriaVehiculo
```
Los aggregates solo se referencian **por identificador**; las entidades internas (`Extension`, `ConductorAdicional`, `Cargo`, `Deposito`) no se tocan desde fuera de su raíz.

### Value Objects (inmutables, validados al construirse)
`Dinero` (Decimal), `PeriodoRenta`, `Kilometraje`, `NivelCombustible` (octavos), `Licencia`, `MetodoPagoRef` (token + últimos 4), `ReferenciaPago`, `EvidenciaFoto` (con sello de tiempo), `RegistroDanio`, `FirmaDigital`, `Disputa`, `CoberturaSeguro`, `DiferenciasInspeccion`, `CondicionesContrato`.

### Patrones aplicados
| Patrón | Dónde | Por qué |
| :--- | :--- | :--- |
| Specification | `domain/especificaciones.py` (11 especificaciones + combinadores `&`, `\|`, `~`) | Reglas booleanas reutilizables que explican cuál falló (`fallas()`) |
| State Machine | `domain/maquina_estados.py` + una tabla por aggregate | Los estados válidos se declaran una vez; ningún `if` de estado disperso |
| Domain Events | `domain/eventos.py` + `BusEventosEnMemoria` | Aggregates desacoplados; una transacción modifica un solo aggregate |
| Repository + Unit of Work | `infrastructure/repositorios.py`, `unidad_trabajo.py` | El dominio ignora la base de datos; commit/rollback atómico |
| Domain Service / Policy | `domain/politicas.py` | Reglas paramétricas (24 h, 29 min, 48 h…) que cambian por configuración |
| Ports & Adapters | `application/puertos.py` + `infrastructure/adaptadores.py` | Pasarela de pago, evidencia, calendario y reloj sustituibles |
| CQRS básico | `infrastructure/consultas.py` | Reportes con SQL directo, sin hidratar aggregates |

## 3. Máquinas de estados
```mermaid
stateDiagram-v2
    [*] --> CREADA
    CREADA --> UPGRADE_OFRECIDO: proponer_upgrade
    UPGRADE_OFRECIDO --> UPGRADE_ACEPTADO: aceptar_upgrade
    UPGRADE_OFRECIDO --> EN_LISTA_ESPERA: rechazar_a_lista_espera
    UPGRADE_OFRECIDO --> CANCELADA: rechazar_con_reembolso
    CREADA --> UPGRADE_ACEPTADO: upgrade de cortesia
    CREADA --> CONVERTIDA: contrato abierto
    UPGRADE_ACEPTADO --> CONVERTIDA: contrato abierto
    CREADA --> CANCELADA: cancelar
    CREADA --> LIBERADA_NO_SHOW: 2 h sin presentarse
    CONVERTIDA --> [*]
    CANCELADA --> [*]
    LIBERADA_NO_SHOW --> [*]
```
```mermaid
stateDiagram-v2
    direction LR
    state "Contrato" as C {
        [*] --> ABIERTO
        ABIERTO --> DEVUELTO: registrar_devolucion
        DEVUELTO --> CERRADO: deposito liberado
    }
    state "Vehiculo" as V {
        [*] --> DISPONIBLE
        DISPONIBLE --> ASIGNADO: asignar_a_entrega
        ASIGNADO --> RENTADO: contrato abierto
        RENTADO --> EN_LIMPIEZA: devolucion
        EN_LIMPIEZA --> DISPONIBLE: tarea completada
    }
```
```mermaid
stateDiagram-v2
    [*] --> PENDIENTE_APROBACION: dano nuevo
    [*] --> APLICADO: km, combustible o retraso
    PENDIENTE_APROBACION --> APLICADO: Administracion fija el monto
    APLICADO --> DISPUTADO: el cliente disputa
    DISPUTADO --> APLICADO: resolucion CONFIRMADO
    DISPUTADO --> ANULADO: resolucion ANULADO
```

## 4. Flujo de eventos (consistencia eventual entre aggregates)
```mermaid
flowchart LR
    CA["ContratoAbierto"] --> H1["Reservacion CONVERTIDA"]
    CA --> H2["Vehiculo RENTADO"]
    CA --> H3["Abre Liquidacion con deposito"]
    VD["VehiculoDevuelto"] --> H4["Calcula cargos"]
    VD --> H5["Vehiculo EN_LIMPIEZA"]
    VD --> H6["Crea TareaLimpieza"]
    TL["TareaLimpiezaCompletada"] --> H7["Vehiculo DISPONIBLE"]
    DL["DepositoLiberado"] --> H8["Contrato CERRADO"]
```
Cada handler abre **su propia transacción** y es **idempotente**: si el mismo evento llega dos veces el resultado es el mismo (probado en `TestIdempotenciaDeHandlers`).

## 5. Secuencia: entrega y apertura del contrato
```mermaid
sequenceDiagram
    actor Ag as Agente
    participant API as API REST
    participant EA as EntregaAppService
    participant IA as InspeccionAppService
    participant CA as ContratoAppService
    participant D as Dominio
    participant P as PasarelaPago
    participant B as BusEventos
    Ag->>API: POST /reservaciones/{folio}/entrega
    API->>EA: iniciar_entrega
    EA->>D: Cliente.puede_rentar (Specifications)
    EA->>D: Vehiculo.asignar_a_entrega
    Ag->>API: POST /inspecciones/entrega (fotos)
    API->>IA: registrar_inspeccion_entrega
    IA->>D: InspeccionVehiculo.registrar
    Ag->>API: POST /inspecciones/{id}/firma (cliente)
    Ag->>API: POST /contratos
    API->>CA: abrir_contrato
    CA->>P: retener_deposito
    CA->>D: ContratoRenta.abrir
    CA->>B: publicar ContratoAbierto (despues del commit)
    B-->>D: Reservacion CONVERTIDA, Vehiculo RENTADO, abre Liquidacion
```

## 6. Secuencia: devolución y cargos
```mermaid
sequenceDiagram
    actor Pa as Patio
    actor Ag as Agente
    participant CA as ContratoAppService
    participant B as BusEventos
    participant LA as LiquidacionAppService
    participant D as Dominio
    Pa->>CA: checklist de devolucion
    Ag->>CA: procesar_devolucion
    CA->>D: ContratoRenta.registrar_devolucion
    CA->>B: publicar VehiculoDevuelto
    B->>LA: calcular_cargos
    LA->>D: devolucion.comparar_contra(entrega)
    LA->>D: Liquidacion.calcular_cargos (PoliticaCargos)
    D-->>LA: cargos km, combustible, retraso y danios pendientes
    B->>CA: Vehiculo EN_LIMPIEZA y TareaLimpieza
```

## 7. Persistencia
Una tabla por aggregate con **columnas indexadas** para consultar y un **documento JSON** con el estado completo (ADR-005).

```mermaid
erDiagram
    clientes { string id PK }
    categorias { string id PK int nivel }
    vehiculos { string id PK string categoria_id string sucursal_id string estado }
    reservaciones { string id PK string cliente_id string categoria_id string estado datetime inicio datetime fin }
    contratos { string id PK string reservacion_folio string vehiculo_id string estado int monto_base }
    inspecciones { string id PK string contrato_id string tipo }
    liquidaciones { string id PK string contrato_id string deposito_estado int total_cargos }
    tareas_limpieza { string id PK string vehiculo_id string estado datetime creada_en }
    categorias ||--o{ vehiculos : agrupa
    clientes ||--o{ reservaciones : hace
    reservaciones ||--o| contratos : se_convierte_en
    contratos ||--o{ inspecciones : tiene
    contratos ||--|| liquidaciones : liquida
    vehiculos ||--o{ tareas_limpieza : requiere
```
Dinero se guarda en **centavos enteros**; las fechas siempre en UTC (`UTCDateTime`).

## 8. Despliegue
```mermaid
flowchart LR
    U["Cliente HTTP / Swagger"] --> A["Contenedor app<br/>uvicorn + FastAPI"]
    A --> DB[("PostgreSQL 16")]
    A --> EV[("Volumen de evidencias")]
    T["Contenedor tests<br/>pytest + cobertura"] --> DB2[("BD novarent_test")]
    GH["GitHub Actions"] -- "ruff, pytest en PostgreSQL, docker compose" --> A
```

## 9. Principios SOLID en el código
| Principio | Evidencia |
| :--- | :--- |
| S · Responsabilidad única | Cada aggregate protege sus invariantes; cada servicio de aplicación atiende un módulo del negocio |
| O · Abierto/cerrado | Nueva regla = nueva `Especificacion` o nuevo handler, sin modificar los existentes |
| L · Sustitución de Liskov | `RelojFijo`/`RelojSistema`, `PasarelaPagoSimulada`, `AlmacenEvidenciaMemoria`/`Disco` son intercambiables |
| I · Segregación de interfaces | Puertos pequeños (`CalendarioHabil`, `Reloj`, `PasarelaPago`…) en lugar de un "servicio de infraestructura" único |
| D · Inversión de dependencias | `application/puertos.py` define las interfaces; `composicion.py` es el único lugar que conoce las implementaciones |

## Decisiones de arquitectura (ADR)
| ADR | Decisión |
| :--- | :--- |
| [ADR-001](ADR-001-domain-model-service-layer.md) | Domain Model + Service Layer |
| [ADR-002](ADR-002-reportes-consultas-directas.md) | Reportes con consultas directas |
| [ADR-003](ADR-003-specification-y-maquina-de-estados.md) | Specification y máquina de estados declarativa |
| [ADR-004](ADR-004-persistencia-documento-por-aggregate.md) | Persistencia: un documento por aggregate con columnas indexadas |
| [ADR-005](ADR-005-eventos-en-proceso-e-idempotencia.md) | Eventos de dominio en proceso, post-commit e idempotentes |
| [ADR-006](ADR-006-api-rest-y-contrato-de-errores.md) | API REST y contrato de errores |
| [ADR-007](ADR-007-autenticacion-simulada-y-autorizacion-por-rol.md) | Autenticación simulada, autorización real por rol |
| [ADR-008](ADR-008-dinero-y-tiempo.md) | Dinero con Decimal y tiempo con zona horaria |
| [ADR-009](ADR-009-configuracion-docker-y-despliegue.md) | Configuración 12-Factor, Docker y CI |
| [ADR-010](ADR-010-adaptacion-del-paquete-de-datos.md) | Adaptación del paquete de datos del PIA |
