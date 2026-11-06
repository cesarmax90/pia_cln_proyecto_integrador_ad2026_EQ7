"""Exporta el contrato OpenAPI a docs/api/openapi.json (python scripts/exportar_openapi.py)."""
import json
from pathlib import Path

from src.api.main import crear_app
from src.config import Settings

app = crear_app(Settings(database_url="sqlite://", cargar_datos_demo=False))
destino = Path("docs/api/openapi.json")
destino.parent.mkdir(parents=True, exist_ok=True)
destino.write_text(json.dumps(app.openapi(), ensure_ascii=False, indent=2), encoding="utf-8")
print(f"OpenAPI exportado: {len(app.openapi()['paths'])} rutas -> {destino}")
