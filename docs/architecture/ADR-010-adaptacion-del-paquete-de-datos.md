# ADR-010 · Adaptación del paquete de datos del PIA

**Estado:** Aceptada

## Contexto
El paquete modela "renta de equipos" con operaciones SOLICITADA → APROBADA → ENTREGADA → DEVUELTA y reglas `puede_procesarse` y `beneficio_referencia`. NovaRent renta **automóviles** con reservación → contrato → liquidación. El propio LEEME aclara que es un "modelo de pruebas propuesto" y que no debe reemplazar los requerimientos del equipo.

## Decisión
1. El dominio de NovaRent se deriva del BRD, las historias y ACT-F03, **no** del paquete.
2. Los CSV alimentan los datos de demostración (`infrastructure/datos_demo.py`): actores → clientes, catálogo → categorías y flota, ciudad → sucursal.
3. Los 120 casos y las 20 transiciones se ejecutan con los componentes genéricos del dominio (Specification, máquina de estados, `Dinero`) en `src/validacion_paquete`, contra un oráculo independiente en las pruebas.
4. Las diferencias y los oráculos adaptados están en [adaptacion_paquete_datos.md](../adaptacion_paquete_datos.md).

## Consecuencias
- (+) Se cumple la indicación del paquete y se aprovechan sus 160 casos como pruebas adicionales.
- (−) Los nombres originales de los recursos (proyectores, laptops…) no se usan porque no corresponden al giro.
