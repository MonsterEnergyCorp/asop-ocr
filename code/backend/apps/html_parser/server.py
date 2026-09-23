from fastapi import FastAPI, HTTPException
from fastapi.middleware import Middleware
from fastapi.middleware.cors import CORSMiddleware

from apps.html_parser.html_parse_handler import html_parsing_flow
from core.config import config


env = config.env


def init_routers(app_: FastAPI) -> None:
    # Ingest calls this endpoint with a file_id after storing the file in Blob Storage.
    @app_.post(f"/{env}/parse/html")
    async def parse_html(payload: dict):
        file_id = payload.get("file_id")
        if not file_id:
            raise HTTPException(status_code=400, detail="file_id is required in the payload")
        result = html_parsing_flow(file_id)
        return {"message": "File processed successfully", "data": result}

    # Kubernetes probes and Helm smoke tests use this health endpoint.
    @app_.get("/")
    async def health_check():
        return {"message": "Application is healthy and running", "data": "None"}


def make_middleware() -> list[Middleware]:
    return [
        Middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    ]


def create_app() -> FastAPI:
    app_ = FastAPI(
        title="HTML Parsing",
        description="Parse LATAM HTML PO templates",
        version="1.0.0",
        dependencies=[],
        middleware=make_middleware(),
    )
    init_routers(app_=app_)
    return app_


app = create_app()