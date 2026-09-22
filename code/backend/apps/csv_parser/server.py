from fastapi import FastAPI, HTTPException
from fastapi.middleware import Middleware
from fastapi.middleware.cors import CORSMiddleware

from apps.csv_parser.csv_parse_handler import csv_parsing_flow
from core.config import config


env = config.env


def init_routers(app_: FastAPI) -> None:
    @app_.post(f"/{env}/parse/csv")
    async def parse_csv(payload: dict):
        file_id = payload.get("file_id")
        if not file_id:
            raise HTTPException(status_code=400, detail="file_id is required in the payload")
        result = csv_parsing_flow(file_id)
        return {"message": "File processed successfully", "data": result}

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
        title="CSV Parsing",
        description="Parse LATAM CSV PO templates",
        version="1.0.0",
        dependencies=[],
        middleware=make_middleware(),
    )
    init_routers(app_=app_)
    return app_


app = create_app()