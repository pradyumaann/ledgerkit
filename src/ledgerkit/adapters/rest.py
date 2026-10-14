"""REST adapter: one POST endpoint per tool, generated from the registry, plus the web interface."""

import hmac
from pathlib import Path

from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session, sessionmaker

from ledgerkit import __version__
from ledgerkit.adapters.schema_export import export_tool_schemas
from ledgerkit.config import Settings, get_settings
from ledgerkit.db import make_engine, make_session_factory
from ledgerkit.tools import Actor, registry
from ledgerkit.tools.registry import Tool

STATUS_CODES = {"ok": 200, "pending_approval": 202}
ERROR_CODES = {"unknown_tool": 404, "not_found": 404, "forbidden": 403}

WEB_DIST = Path(__file__).parent.parent / "web_dist"

WEB_NOT_BUILT = """<!doctype html>
<title>ledgerkit</title>
<body style="font: 1rem/1.5 system-ui, sans-serif; max-width: 40rem; margin: 4rem auto; padding: 0 1rem">
<h1>ledgerkit is running</h1>
<p>The API is available at <a href="/api/docs">/api/docs</a>.</p>
<p>The web interface has not been built yet. From the project folder run:</p>
<pre>cd web
npm install
npm run build</pre>
<p>then reload this page.</p>
</body>
"""


def _http_status(result: dict) -> int:
    if result["status"] == "error":
        return ERROR_CODES.get(result["error"]["code"], 400)
    return STATUS_CODES[result["status"]]


def create_app(
    session_factory: sessionmaker[Session] | None = None,
    settings: Settings | None = None,
    web_dist: Path = WEB_DIST,
) -> FastAPI:
    settings = settings or get_settings()
    session_factory = session_factory or make_session_factory(make_engine(settings.database_url))
    auth_required = bool(settings.user_token or settings.agent_token)
    app = FastAPI(
        title="ledgerkit",
        version=__version__,
        description="Every operation is a tool. POST a tool's input as JSON to /api/tools/{name}.",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        redoc_url=None,
    )
    api = APIRouter(prefix="/api")

    def get_actor(authorization: str | None = Header(None), x_ledgerkit_actor: str | None = Header(None)) -> Actor:
        """The bearer token decides whether the caller is a human user or an agent.

        A caller with user rights may ask to be treated as an agent (X-Ledgerkit-Actor: agent),
        which only ever reduces what it can do. The web interface uses this to demonstrate the
        approval gate.
        """
        if not auth_required:
            actor = Actor("user", "local")
        else:
            token = (authorization or "").removeprefix("Bearer ").strip()
            if settings.user_token and hmac.compare_digest(token.encode(), settings.user_token.encode()):
                actor = Actor("user", "api")
            elif settings.agent_token and hmac.compare_digest(token.encode(), settings.agent_token.encode()):
                actor = Actor("agent", "api")
            else:
                raise HTTPException(status_code=401, detail="Missing or invalid bearer token.")
        if actor.type == "user" and x_ledgerkit_actor == "agent":
            return Actor("agent", actor.id)
        return actor

    @api.get("/health")
    def health():
        return {"status": "ok", "version": __version__, "auth_required": auth_required}

    @api.get("/me")
    def me(actor: Actor = Depends(get_actor)):
        return {"actor": actor.type, "auth_required": auth_required}

    @api.get("/tools")
    def list_tools(_actor: Actor = Depends(get_actor)):
        return export_tool_schemas(registry, include_meta=True)

    def add_tool_route(tool: Tool) -> None:
        input_model = tool.input_model

        def endpoint(body: input_model, actor: Actor = Depends(get_actor)):
            result = registry.call(session_factory, tool.name, body.model_dump(mode="json", exclude_unset=True), actor)
            return JSONResponse(result, status_code=_http_status(result))

        notes = []
        if tool.requires_approval:
            notes.append("When called by an agent this is held for human approval (HTTP 202).")
        api.post(
            f"/tools/{tool.name}",
            name=tool.name,
            summary=tool.name,
            description=" ".join([tool.description, *notes]),
            tags=["changes data" if tool.mutating else "read only"],
        )(endpoint)

    for tool in registry.list():
        add_tool_route(tool)

    @api.api_route("/{path:path}", methods=["GET", "POST"], include_in_schema=False)
    def api_not_found(path: str):
        raise HTTPException(status_code=404, detail=f"There is no API endpoint at /api/{path}.")

    app.include_router(api)
    _serve_web(app, web_dist)
    return app


def _serve_web(app: FastAPI, web_dist: Path) -> None:
    """Serve the built single-page app, sending unknown paths to it for client-side routing."""
    index = web_dist / "index.html"
    if not index.is_file():

        @app.get("/", include_in_schema=False)
        def not_built():
            return HTMLResponse(WEB_NOT_BUILT)

        return

    if (web_dist / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=web_dist / "assets"), name="assets")
    root = web_dist.resolve()

    @app.get("/{path:path}", include_in_schema=False)
    def web(path: str):
        candidate = (root / path).resolve()
        if path and candidate.is_file() and candidate.is_relative_to(root):
            return FileResponse(candidate)
        # The app shell must not be cached, or a new build would not be picked up.
        return FileResponse(index, headers={"Cache-Control": "no-cache"})
