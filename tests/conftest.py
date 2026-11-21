import pandas as pd
import pytest


@pytest.fixture
def clients_df() -> pd.DataFrame:
    return pd.DataFrame({
        "cliente_id": [1, 2, 3],
        "fecha_alta": ["2024-01-10", "2025-02-01", "2025-11-15"],
        "segmento": ["Personal", "Pyme", "Personal"],
        "ciudad": ["BOGOTA", "medellin", "B/quilla"],
        "edad": [30, 999, 0],
        "canal_adquisicion": ["web", "app", "referido"],
        "plataforma_principal": ["android", "ios", "web"],
        "estado_actual": ["activo", "inactivo", "activo"],
        "contactado_por_retencion": [0, 1, 0],
        "fecha_contacto_retencion": [None, "2025-10-10", None],
    })


@pytest.fixture
def subs_df() -> pd.DataFrame:
    return pd.DataFrame({
        "suscripcion_id": [100, 101, 102, 103],
        "cliente_id": [1, 1, 2, 3],
        "plan": ["Basico", "Premium", "Estandar", "Familiar"],
        "fecha_inicio": ["2024-01-10", "2025-02-10", "2025-02-01", "2025-11-15"],
        "fecha_fin": ["2025-02-10", None, "2025-03-15", None],
        "motivo_cancelacion": ["cambio_plan", None, "precio", None],
    })


@pytest.fixture
def invoices_df() -> pd.DataFrame:
    return pd.DataFrame({
        "factura_id": [1, 1, 2, 3],
        "cliente_id": [1, 1, 1, 1],
        "suscripcion_id": [101, 101, 101, 101],
        "periodo": ["2025-09", "2025-09", "2025-09", "2025-10"],
        "monto": [49900, 49900, 49900, 49900],
        "fecha_vencimiento": ["2025-09-15", "2025-09-15", "2025-09-15", "2025-10-15"],
        "fecha_pago": ["2025-09-10", "2025-09-10", "2025-09-12", None],
        "metodo_pago": ["tarjeta"] * 4,
        "fecha_carga": ["2025-09-02 02:00:00", "2025-09-05 07:00:00", "2025-09-02 02:00:00", "2025-10-02 02:00:00"],
    })


@pytest.fixture
def events_df() -> pd.DataFrame:
    return pd.DataFrame({
        "event_id": ["e1", "e1", "e2"],
        "cliente_id": [1, 1, 1],
        "ts": ["2025-09-20T10:00:00Z", "2025-09-20T10:00:00Z", "2025-10-01T04:30:00Z"],
        "tipo": ["login", "login", "error_app"],
        "plataforma": ["android"] * 3,
        "version_app": ["5.2.0"] * 3,
        "duracion_seg": [None, None, None],
        "funcionalidad": [None, None, None],
        "codigo_error": [None, None, "CRASH_ON_START"],
    })


@pytest.fixture
def tickets_raw() -> list[dict]:
    return [
        {"ticket_id": "TK-0000001", "customer": "CL-012375", "created_at": "2025-10-01T04:30:00Z",
         "channel": "chat", "category": "cobro_doble", "text": "Veo un cobro duplicado en mi tarjeta, quisiera que me devuelvan uno.",
         "status": "closed", "resolved_at": "2025-10-02T10:00:00Z", "csat": 4},
        {"id": "TK-0000002", "cliente": {"id": "12386", "segmento": "Personal"}, "fecha": "2025-09-30T23:30:00-05:00",
         "canal": "telefono", "tipo": {"principal": "facturacion", "sub": "cobro_doble"},
         "mensajes": [{"autor": "cliente", "texto": "Me encanta pagar dos veces por lo mismo, muy buena estrategia la de ustedes jaja."},
                      {"autor": "agente", "texto": "Lamentamos el inconveniente, estamos revisando su solicitud."}],
         "estado": {"valor": "abierto", "fecha": None}},
    ]
