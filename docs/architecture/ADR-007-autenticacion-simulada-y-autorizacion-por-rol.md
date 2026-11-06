# ADR-007 · Autenticación simulada, autorización real por rol

**Estado:** Aceptada

## Contexto
El BRD no incluye autenticación, pero N5 exige "autorización controlada por rol" y el PIA pide pruebas de seguridad.

## Decisión
El actor se simula con `X-Actor-Id` y `X-Rol` (esquemas `ActorId` y `Rol` en Swagger → botón *Authorize*). Cada caso de uso verifica el rol contra la matriz `application/permisos.py`; además los aggregates **vuelven a exigir** el rol en las reglas críticas (extensión > 48 h, upgrade de cortesía, monto de daño, resolución de disputas) y un cliente solo opera sobre sus propios recursos (`exigir_propietario`).

## Consecuencias
- (+) Defensa en profundidad: aunque se llame al dominio directamente, el rol se vuelve a validar.
- (−) Los encabezados no son seguridad real; en producción se sustituyen por JWT/OAuth sin tocar casos de uso (solo `api/dependencias.py`).
