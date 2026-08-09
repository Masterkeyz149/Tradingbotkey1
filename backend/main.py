from fastapi import FastAPI, WebSocket
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from backend.logging_config import setup_logging
from backend.db.session import Base, engine
from backend.webhook.router import router as webhook_router
from backend.dashboard.router import router as dashboard_router
from backend.dashboard.overrides import router as overrides_router
from backend.dashboard.ws import websocket_endpoint
from backend.auth.router import router as auth_router

setup_logging()

# Creates tables on first run if they don't exist. For anything beyond local
# dev, prefer real migrations (Alembic) over this -- noted in README.
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Trading Setup Confirmation Dashboard")

app.include_router(webhook_router)
app.include_router(dashboard_router)
app.include_router(overrides_router)
app.include_router(auth_router)


@app.websocket("/ws/signals")
async def ws_signals(websocket: WebSocket):
    await websocket_endpoint(websocket)


@app.get("/health")
def health():
    return {"status": "ok"}


# Serve the single-page dashboard frontend (see frontend/index.html).
app.mount("/static", StaticFiles(directory="frontend"), name="static")


@app.get("/")
def serve_dashboard():
    return FileResponse("frontend/index.html")


@app.get("/login")
def serve_login():
    return FileResponse("frontend/login.html")
