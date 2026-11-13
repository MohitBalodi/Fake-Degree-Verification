from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.errors import AppError

app = FastAPI(
    title="Authenticity Validator for Academia",
    description="Prototype credential verification API. All data is synthetic.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(AppError)
def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.code, "message": exc.message, **exc.extra}},
    )


@app.exception_handler(StarletteHTTPException)
def http_exception_handler(_: Request, exc: StarletteHTTPException) -> JSONResponse:
    detail = exc.detail
    code = detail.get("code") if isinstance(detail, dict) else f"http_{exc.status_code}"
    message = detail.get("message") if isinstance(detail, dict) else str(detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": code, "message": message}},
        headers=getattr(exc, "headers", None),
    )


@app.exception_handler(RequestValidationError)
def validation_exception_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "validation_error",
                "message": "Request body or parameters are invalid.",
                "fields": [{"loc": list(e["loc"]), "msg": e["msg"]} for e in exc.errors()],
            }
        },
    )


@app.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    return {"status": "ok", "env": settings.env}


app.include_router(api_router, prefix=settings.api_v1_prefix)
