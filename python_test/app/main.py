"""Application entry point: FastAPI app factory, logging, routers, error handlers."""

import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.extract import router as extract_router

# Configure root logging for the service.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Document Text Extraction Service (OCR & Text Extraction)",
    description=(
        "Async microservice that accepts base64-encoded documents, detects their "
        "type via magic numbers and extracts text: locally for editable PDF/DOCX, "
        "via an external n8n OCR API for images and scanned PDFs. Protected by JWT."
    ),
    version="1.0.0",
)

app.include_router(extract_router)

# CORS: вызовы из браузерных клиентов (Elma365 web, swagger с другого хоста).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Return validation errors in the unified {"detail": "..."} format.

    By default FastAPI answers 422 with a nested `detail` array of objects;
    clients like Elma365 expect a plain string and often surface the raw 422
    without explanation. We log the full details and return a readable message.
    """
    logger.warning(
        "Request validation failed on %s %s: %s",
        request.method,
        request.url.path,
        exc.errors(),
    )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": "Invalid request body or parameters"},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all handler returning errors in the unified {"detail": ...} format."""
    logger.exception("Unhandled internal error on %s %s: %s", request.method, request.url.path, exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"},
    )


@app.get("/health", tags=["health"])
async def health_check() -> dict:
    """Liveness probe."""
    return {"status": "ok"}
