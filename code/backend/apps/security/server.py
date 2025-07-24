from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware import Middleware
from fastapi import UploadFile, File, HTTPException, Request, FastAPI, APIRouter
from fastapi.responses import JSONResponse
from apps.security.authorizer import validate_token
from typing import List
import os

from core.config import config

env = config.env

def init_routers(app: FastAPI) -> None:
    @app.get(f"/{env}/ocr/auth")
    async def authenticate(request: Request):
        token = request.headers.get("Authorization")
        if validate_token(token=token):
            content = {
                "message": "Token is valid",
                "hostname": os.getenv("HOSTNAME")
            }
            headers = {
                "userid": "admin",
                "role": "admin",
            }
            return JSONResponse(content=content, status_code=200, headers=headers)
        else:
            raise HTTPException(status_code=401, detail="Unauthorized Access")
     
    @app.get("/")
    async def health_check():
        return {"message": "Application is healthy and running"}
    
def make_middleware() -> List[Middleware]:
    return [
        Middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        ),
    ]

def create_app() -> FastAPI:
    app = FastAPI(
        title="Authorizer",
        description="API Authorizer",
        version="1.0.0",
        middleware=make_middleware(),
    )
    init_routers(app)
    return app

app = create_app()
