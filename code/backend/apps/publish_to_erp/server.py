from fastapi import FastAPI, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware import Middleware
from fastapi import UploadFile, File, HTTPException
from apps.publish_to_erp.publish_to_erp_handler import publish_to_erp
from typing import List
import logging
from core.config import config

env = config.env


def init_routers(app_: FastAPI) -> None:
    @app_.post(f"/{env}/ocr/erp-push")
    async def erp_push(data: dict):
        result = publish_to_erp(data)
        return {"message": "File pushed", "data": result}
    
    @app_.get("/")
    async def health_check():
        return {"message": "Application is healthy and running", "data": "None"}
    
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
        title="Publish to ERP",
        description="Publish OCR output to ERP",
        version="1.0.0",
        dependencies=[],
        middleware=make_middleware(),
    )
    
    init_routers(app_=app_)
    return app_


app = create_app()  
        