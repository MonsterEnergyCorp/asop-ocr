from fastapi import FastAPI, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware import Middleware
from fastapi import UploadFile, File, HTTPException
from apps.excel_parser.excel_parse_handler import excel_parsing_flow
from typing import List
import logging
from core.config import config

env = config.env
logging.info(f'ENV: {env}')

def init_routers(app_: FastAPI) -> None:
    # @app_.post("/parse/excel")
    # async def upload_excel(file: UploadFile = File(...)):
    #     if file.content_type != 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet':
    #         raise HTTPException(status_code=400, detail="Invalid file type. Please upload an Excel file.")

    #     content = await file.read()
    #     result = excel_parsing_flow(content)
    #     return {"message": "File processed successfully", "data": result}
    
    @app_.post(f"/{env}/parse/excel")
    async def parse_val(payload: dict):
        file_id = payload.get("file_id")
        if not file_id:
            raise HTTPException(status_code=400, detail="file_id is required in the payload")
        
        result = excel_parsing_flow(file_id)
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
        title="Excel Parsing",
        description="Parse Excel PO templates",
        version="1.0.0",
        dependencies=[],
        middleware=make_middleware(),
    )
    
    init_routers(app_=app_)
    return app_


app = create_app()  
        
