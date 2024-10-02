import logging
import os
from pathlib import Path

import requests
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from app import CONFIG

logger = logging.getLogger(__name__)

CERT_URL = (
    "https://cockroachlabs.cloud/clusters/3ae41880-2d4c-4fd7-bc3d-28330c1a4cd5/cert"
)

app_data = os.getenv("APPDATA")
if app_data:
    app_data = Path(app_data)
    cert_path = Path(app_data) / "postgresql"
else:
    # linux machine
    cert_path = Path("/root/.postgresql/")

if not cert_path.exists():
    os.mkdir(cert_path)
    cert_path = cert_path / "root.crt"
    response = requests.get(CERT_URL)

    if response.status_code == 200:
        with open(cert_path, "wb") as file:
            file.write(response.content)
            logger.info("Cert file downloaded")
    else:
        logger.error("Failed to download cert file")
else:
    logger.info("Cert file found at %s", cert_path)

engine = create_engine(
    CONFIG.SQLALCHEMY_DATABASE_URL,
    echo=True,
    echo_pool=True,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()
