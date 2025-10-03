from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.config import logger
from src.db import appwrite_create_client

# Initialize FastAPI application
app = FastAPI(
    title="Drop the Drip API",
    description="AI-powered virtual clothing try-on service",
    version="1.0.0",
)

appwrite_create_client()


# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # ⚠️ !prod remindme - configure for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


logger.info("Drop the Drip API initialized successfully")
