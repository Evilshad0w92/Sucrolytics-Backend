from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.routes.auth    import router as auth_router
from app.routes.users   import router as users_router
from app.routes.ingreso import router as ingreso_router
from app.routes.calculo import router as calculo_router
from app.routes.cordia import router as cordia_router

app = FastAPI(title="Sucrolytics API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL, "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router,    prefix="/api/auth",    tags=["auth"])
app.include_router(users_router,   prefix="/api/users",   tags=["users"])
app.include_router(ingreso_router, prefix="/api/ingreso", tags=["ingreso"])
app.include_router(calculo_router, prefix="/api/calculo", tags=["calculo"])
app.include_router(cordia_router,  prefix="/api/cordia",  tags=["cordia"])

@app.get("/api/health")
def health():
    return {"status": "ok"}
