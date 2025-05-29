from fastapi import FastAPI, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware import Middleware
from fastapi import HTTPException
from apps.ingest_documents.ocr_ingest_doc import upload_invoice_file
from typing import List
from core.config import config

env = config.env

def init_routers(app_: FastAPI) -> None:
    @app_.post(f"/{env}/ocr/ingest")
    async def upload_pdf(data: dict):
        if data.get('data',{}).get('file_type') not in ['application/pdf', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 'text/csv', 'application/octet-stream']:
            raise HTTPException(status_code=400, detail="Invalid file type.")
        result = upload_invoice_file(data)
        return {"message": "File ingested successfully", "data": result}
    
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
        title="Ingest Documents",
        description="Ingest PO templates",
        version="1.0.0",
        dependencies=[],
        middleware=make_middleware(),
    )
    
    init_routers(app_=app_)
    return app_


app = create_app()  
        
