from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.routers import auth, companies, health, users, admin, employees, access, procurement, suppliers, warehouse, finance, finance_obligations, counterparties, documents, etp, transport, tenders

app = FastAPI(
    title=settings.app_name,
    version="0.25.0-pilot",
    docs_url="/docs" if settings.environment == "development" else None,
    redoc_url="/redoc" if settings.environment == "development" else None,
    openapi_url="/openapi.json" if settings.environment == "development" else None,
)
if settings.environment == "development":
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-CSRF-Token"],
    )
app.include_router(health.router)
app.include_router(auth.router)
app.include_router(companies.router)
app.include_router(users.router)
app.include_router(admin.router)
app.include_router(employees.router)
app.include_router(access.router)
app.include_router(procurement.router)
app.include_router(suppliers.router)
app.include_router(suppliers.rfq_router)
app.include_router(warehouse.router)
app.include_router(finance.router)
app.include_router(finance_obligations.router)
app.include_router(counterparties.router)
app.include_router(counterparties.contracts_router)
app.include_router(documents.router)
app.include_router(documents.contract_router)
app.include_router(etp.router)
app.include_router(transport.router)
app.include_router(tenders.router)

@app.get("/")
def root():
    return {"name": settings.app_name, "version": app.version, "status": settings.environment}
