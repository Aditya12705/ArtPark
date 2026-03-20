"""
main.py – PathForge FastAPI application entry-point.

Startup/shutdown lifecycle:
    - skills_graph.json  loaded once → app.state.skills_graph
    - course_catalog.yaml loaded once → app.state.course_catalog
    All routers read from app.state; no per-request file I/O.
"""

from __future__ import annotations

import json
import logging
import os
from contextlib import asynccontextmanager
from typing import Any, Dict, List

import yaml
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from routers import gap, parse, pathway

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s – %(message)s",
)
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Data paths (relative to this file)
# ─────────────────────────────────────────────────────────────────────────────
_BASE = os.path.dirname(__file__)
_SKILLS_GRAPH_PATH   = os.path.join(_BASE, "data", "skills_graph.json")
_COURSE_CATALOG_PATH = os.path.join(_BASE, "data", "course_catalog.yaml")


# ─────────────────────────────────────────────────────────────────────────────
# Lifespan – load heavy data once at startup
# ─────────────────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load static data files into app.state at startup."""

    # skills_graph.json
    try:
        with open(_SKILLS_GRAPH_PATH, "r", encoding="utf-8") as f:
            app.state.skills_graph: Dict[str, Any] = json.load(f)
        logger.info("Loaded skills_graph.json – %d skills.", len(app.state.skills_graph))
    except FileNotFoundError:
        logger.warning("skills_graph.json not found at %s – using empty graph.", _SKILLS_GRAPH_PATH)
        app.state.skills_graph = {}

    # course_catalog.yaml
    try:
        with open(_COURSE_CATALOG_PATH, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)
        app.state.course_catalog: List[Dict[str, Any]] = (
            raw.get("courses", []) if isinstance(raw, dict) else (raw or [])
        )
        logger.info("Loaded course_catalog.yaml – %d courses.", len(app.state.course_catalog))
    except FileNotFoundError:
        logger.warning("course_catalog.yaml not found at %s – using empty catalog.", _COURSE_CATALOG_PATH)
        app.state.course_catalog = []

    yield  # ← application runs here

    logger.info("PathForge shutting down.")


# ─────────────────────────────────────────────────────────────────────────────
# App
# ─────────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="PathForge API",
    description=(
        "AI-powered skill-gap analyser and personalised learning pathway generator "
        "for corporate onboarding and career development."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ─────────────────────────────────────────────────────────────────────────────
# CORS
# ─────────────────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────────────────────────────────────────────────────────────────────
# Global exception handler – clean 500s, never leak stack traces to clients
# ─────────────────────────────────────────────────────────────────────────────

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": f"Internal server error: {type(exc).__name__}: {exc}"},
    )

# ─────────────────────────────────────────────────────────────────────────────
# Routers
# ─────────────────────────────────────────────────────────────────────────────

app.include_router(parse.router,   prefix="/parse",   tags=["Parse"])
app.include_router(gap.router,     prefix="/gap",     tags=["Gap Analysis"])
app.include_router(pathway.router, prefix="/pathway", tags=["Pathway"])

# ─────────────────────────────────────────────────────────────────────────────
# Health
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/health", tags=["Health"], summary="Service liveness check")
async def health(request: Request):
    """
    Returns 200 {"status": "ok"} when the service is running.
    Also reports how many skills and courses are loaded.
    """
    return {
        "status": "ok",
        "skills_loaded":  len(getattr(request.app.state, "skills_graph",  {})),
        "courses_loaded": len(getattr(request.app.state, "course_catalog", [])),
    }


@app.get("/", tags=["Health"], summary="Root redirect to docs")
async def root():
    return {"message": "Welcome to PathForge API. Visit /docs for the interactive UI."}
