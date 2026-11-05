from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler

from app.core.config import settings
from app.core.limiter import limiter
from app.db import pool
from app.routes import ai, auth,billing, complaints, regulations, trends


@asynccontextmanager
async def lifespan(app: FastAPI):
    pool.open()
    yield
    pool.close()


app = FastAPI(
    title=settings.app_name,
    description="AI-powered Complaint Intelligence & Regulatory Compliance System for Banks",
    lifespan=lifespan,
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Configure strict CORS origins - wildcard regex removed to prevent cross-origin credentials exploit
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = []
    for err in exc.errors():
        loc = err.get("loc", [])
        field = loc[-1] if loc and loc[-1] != "body" else ""
        raw_msg = err.get("msg", "Invalid value")
        clean_msg = raw_msg.replace("Value error, ", "").replace("Assertion error, ", "").strip()
        if field:
            clean_field = str(field).replace("_", " ").title()
            if clean_field.lower() in clean_msg.lower():
                errors.append(clean_msg)
            else:
                errors.append(f"{clean_field}: {clean_msg}")
        else:
            errors.append(clean_msg)

    formatted_message = ". ".join(errors) if errors else "Invalid form values submitted."
    return JSONResponse(
        status_code=422,
        content={"detail": formatted_message},
    )

app.include_router(auth.router)
app.include_router(complaints.router)
app.include_router(regulations.router)
app.include_router(trends.router)
app.include_router(ai.router)
app.include_router(billing.router)
app.include_router(billing.webhook_router)


@app.get("/health")
def health():
    return {"status": "ok", "app": settings.app_name, "model": settings.llm_model}


@app.get("/health/db")
def health_db():
    try:
        with pool.connection() as conn:
            conn.execute("SELECT 1")
    except Exception:
        raise HTTPException(status_code=503, detail="Database is not available")
    return {"status": "ok"}
