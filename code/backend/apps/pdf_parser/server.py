from fastapi import FastAPI, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware import Middleware
from fastapi import UploadFile, File, HTTPException
from apps.pdf_parser.pdf_parse_handler import pdf_parsing_flow
from typing import List
import logging
from core.config import config

env = config.env

def init_routers(app_: FastAPI) -> None:
    @app_.post(f"/{env}/parse/pdf")
    async def upload_pdf(data: dict):
        result = pdf_parsing_flow(data)
        return {"message": "File processed successfully", "data": result}
    
    
def make_middleware() -> list[Middleware]:
    middleware = [
        Middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        ),
    ]
    return middleware  

def create_app() -> FastAPI:
    app_ = FastAPI(
        title="PDF Parsing",
        description="Parse PDF PO templates",
        version="1.0.0",
        dependencies=[],
        middleware=make_middleware(),
    )
    
    init_routers(app_=app_)
    return app_


app = create_app()  
        