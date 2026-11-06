# Procesos de negocio (BPMN) · NovaRent

El diagrama BPMN de U2 se entregó como imagen. Aquí se reexpresa en **Mermaid** (versionable en Git y visible en GitHub), un diagrama por proceso, con los carriles agrupados por actor. Las correspondencias con historias de usuario están en cada título.

## 1. Reservación (US01 · US02 · US03 · US04)
```mermaid
flowchart TD
    subgraph Cliente
        A([Inicio]) --> B["Busca disponibilidad por sucursal, fechas y categoria"]
        B --> C{"Hay unidad?"}
        C -- No --> Z1([Fin: sin disponibilidad 409])
        C -- Si --> D["Genera la reservacion"]
        D --> E{"Cancela?"}
    end
    subgraph Sistema
        D --> D1["Reservacion CREADA: garantiza categoria, no unidad"]
        E -- Si --> F{"Faltan 24 h o mas?"}
        F -- Si --> G["Cancelacion sin penalizacion"]
        F -- No --> H["Cancelacion con penalizacion"]
        E -- No --> I{"Se presenta en 2 h?"}
        I -- No --> J["Job no-show: libera la reservacion"]
        I -- Si --> K([Pasa al proceso de Entrega])
    end
```

## 2. Entrega y excepciones (US05 · US06 · US07 · US08 · US09 · US10)
```mermaid
flowchart TD
    subgraph Agente
        A([Cliente llega]) --> B["Valida licencia y metodo de pago"]
        B --> C{"Cliente apto?"}
        C -- No --> Z1([Fin: rechazado 422])
        C -- Si --> D{"Hay unidad en la categoria reservada?"}
    end
    subgraph Excepcion
        D -- No --> E{"Hay categoria superior con unidad?"}
        E -- No --> Z2([Fin: sin disponibilidad 409])
        E -- Si --> F["Ofrece upgrade sin costo"]
        F --> G{"Cliente acepta?"}
        G -- No --> H["Lista de espera o reembolso"]
        G -- Si --> D2["Asigna unidad de la categoria superior"]
        Admin["Administracion: upgrade de cortesia"] -.-> D2
    end
    subgraph Patio
        D -- Si --> I["Asigna la unidad con menos km"]
        D2 --> J
        I --> J["Captura checklist: combustible, km, danios y fotos con sello de tiempo"]
    end
    subgraph Cliente
        J --> K["Firma digital del checklist"]
        K --> L["Checklist inmutable"]
    end
    subgraph Sistema
        L --> M["Retiene el deposito de garantia"]
        M --> N["Abre el contrato; reservacion CONVERTIDA; vehiculo RENTADO"]
    end
```

## 3. Extensión de renta (US11 · US12)
```mermaid
flowchart TD
    A([Cliente pide mas tiempo]) --> B{"Faltan 2 h o mas para vencer?"}
    B -- No --> Z1([Rechazada 422])
    B -- Si --> C{"Hay disponibilidad en el nuevo lapso?"}
    C -- No --> Z2([Rechazada 409])
    C -- Si --> D{"Horas solicitadas"}
    D -- "48 h o menos" --> E["Agente aprueba: renta extendida"]
    D -- "Mas de 48 h" --> F["Queda PENDIENTE de autorizacion"]
    F --> G{"Administracion aprueba antes del vencimiento?"}
    G -- Si --> E
    G -- No --> Z3([Sin extension])
```

## 4. Devolución, cargos y disputa (US13 · US14 · US15 · US16 · US17)
```mermaid
flowchart TD
    subgraph Patio
        A([Cliente devuelve la unidad]) --> B["Captura checklist de devolucion con fotos"]
    end
    subgraph Agente
        B --> C["Procesa la devolucion: contrato DEVUELTO"]
    end
    subgraph Sistema
        C --> D["Compara devolucion contra entrega"]
        D --> E["Cargo por kilometraje: sobre 200 km por dia a 3 MXN por km"]
        D --> F["Cargo por combustible: mas de 1/8 de tanque"]
        D --> G["Cargo por retraso: despues de 29 min, por hora, tope de 1 dia"]
        D --> H["Danios nuevos: cargo PENDIENTE de monto"]
        E & F & G & H --> I["Liquidacion con cargos"]
    end
    subgraph Administracion
        H --> J["Fija el monto del danio"]
    end
    subgraph Cliente
        I --> K{"Disputa un cargo?"}
        J --> K
        K -- Si --> L["Disputa con motivo"]
    end
    subgraph Disputa
        L --> M["Se compara la evidencia de entrega y devolucion"]
        M --> N["Administracion resuelve: CONFIRMADO o ANULADO"]
    end
```

## 5. Cierre: limpieza, disponibilidad y depósito (US18 · US19 · US20)
```mermaid
flowchart TD
    subgraph Sistema
        A([Vehiculo devuelto]) --> B["Vehiculo EN_LIMPIEZA y se crea la tarea de limpieza"]
        L["Job diario"] --> M{"5 dias habiles cumplidos y sin incidencias?"}
        M -- Si --> N["Libera el deposito en la pasarela"]
        N --> O["Contrato CERRADO"]
        M -- No --> P["Retiene el deposito"]
    end
    subgraph Limpieza
        B --> C["Prepara la unidad"]
        C --> D["Marca la tarea como completada"]
    end
    subgraph Flota
        D --> E["Vehiculo DISPONIBLE y evento VehiculoListoParaRenta"]
    end
    subgraph Administracion
        R["Consulta reporte: ocupacion, ingresos y rotacion"]
    end
```
