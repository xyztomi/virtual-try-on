from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import logger
from app.api import router

# Initialize FastAPI application
app = FastAPI(
    title="Virtual Try-On API",
    description="AI-powered virtual clothing try-on service",
    version="1.0.0",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # ⚠️ !prod remindme - configure for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(router)

logger.info("Virtual Try-On API initialized successfully")
