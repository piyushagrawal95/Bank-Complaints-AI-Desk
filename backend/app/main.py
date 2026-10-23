from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.db import pool
from app.routes import ai, auth, complaints, regulations, trends


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

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.frontend_origin,
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:5175",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "http://127.0.0.1:5175",
    ],
    allow_origin_regex=r"^https?://.*",
    allow_credentials=True,
    allow_methods=["*"],
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
