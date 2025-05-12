import os
import uvicorn
import logging
from core.config import config

logging.config.fileConfig("logging.conf")

def main(app_path: str) -> None:
    if not app_path:
        raise ValueError("FAST_API_APP_PATH is not set in environment variables")
    logging.info(f"Starting app : {app_path}")
    uvicorn.run(
        app=app_path,
        host="0.0.0.0",
        port=config.port
    )


if __name__ == "__main__":
    main(os.getenv("FAST_API_APP_PATH") or 'apps.ingest_documents.server:app') 