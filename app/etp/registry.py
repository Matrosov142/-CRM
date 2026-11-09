"""Verified capability registry for ETP connectors.

No connector is marked live until its official API, contract permissions,
credentials flow, and integration tests have been verified.
"""
from dataclasses import asdict, dataclass

@dataclass(frozen=True)
class Platform:
    code: str
    name: str
    priority: int
    connection_status: str
    official_api_verified: bool
    automatic_tender_sync: bool
    document_sync: bool
    status_sync: bool
    manual_import: bool
    notes: str

PLATFORMS = (
    Platform("b2b_center", "B2B-Center", 1, "planned", False, False, False, False, True,
             "Первая интеграция. Требуется проверить доступность официального API, договорные условия и права доступа аккаунта."),
    Platform("rts_tender", "РТС-тендер", 2, "planned", False, False, False, False, True,
             "Подключение после B2B-Center; API и условия использования не проверены."),
    Platform("fabrikant", "Фабрикант", 3, "planned", False, False, False, False, True,
             "API и условия использования не проверены."),
    Platform("sber_a", "Сбер А", 4, "planned", False, False, False, False, True,
             "API и условия использования не проверены."),
    Platform("tek_torg", "ТЭК-Торг", 5, "planned", False, False, False, False, True,
             "API и условия использования не проверены."),
)

def list_platforms() -> list[dict]:
    return [asdict(item) for item in PLATFORMS]

def get_platform(code: str) -> Platform | None:
    return next((item for item in PLATFORMS if item.code == code), None)
