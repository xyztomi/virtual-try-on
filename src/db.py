from appwrite.client import Client

from src.config import logger
from src.config import APPWRITE_ENDPOINT, APPWRITE_ID, APPWRITE_KEY


def appwrite_create_client():
    endpoint = APPWRITE_ENDPOINT
    project_id = APPWRITE_ID
    api_key = APPWRITE_KEY
    try:
        client = Client()
        client.set_endpoint(endpoint)
        client.set_project(project_id)
        client.set_key(api_key)
        logger.info("Appwrite client connected successfully!")
        print(client)
        return client
    except Exception as e:
        logger.error(f"Failed to create Appwrite client: {e}")
        return None
