# ADR-005 · Eventos de dominio en proceso, post-commit e idempotentes

**Estado:** Aceptada

## Contexto
ACT-F03 fija que una transacción modifica **un solo aggregate**; los demás reaccionan por eventos.

## Decisión
- La Unit of Work recoge los eventos de los aggregates **solo si el commit tuvo éxito**; el servicio los publica en `BusEventosEnMemoria` después de cerrar la transacción.
- Cada handler abre su propia transacción y es **idempotente por estado** (si el aggregate ya avanzó, no hace nada).
- Un handler que falla se registra (`bus.errores`) pero no revierte al emisor.

## Consecuencias
- (+) Aggregates desacoplados y fáciles de probar; reproducible repitiendo eventos (`TestIdempotenciaDeHandlers`).
- (−) Entre el commit y el handler hay una ventana de consistencia eventual. En producción se resolvería con el patrón **Outbox** y un *worker*; queda como mejora futura documentada.
- Hallazgo durante el desarrollo: un handler idempotente solo contra "ya está en el estado destino" falla si el evento se repite cuando el aggregate ya siguió avanzando; por eso los handlers de flota comparan contra el estado *origen* esperado.
