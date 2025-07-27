import os
import asyncio
from dotenv import load_dotenv

from msal import SerializableTokenCache
from azure.cosmos.aio import CosmosClient as AsyncCosmosClient


load_dotenv(override=True)

COSMOS_URL = os.environ["COSMOS_URL"]
COSMOS_PORT = os.environ["COSMOS_PORT"]
COSMOS_KEY = os.environ["COSMOS_KEY"]
COSMOS_DB = os.environ["COSMOS_DB"]
COSMOS_CONTAINER = os.environ["COSMOS_CONTAINER"]
COSMOS_PARTITION_KEY = os.environ["COSMOS_PARTITION_KEY"]

# Global client instance to reuse connections
_cosmos_client = None
_cosmos_db = None
_cosmos_container = None


async def get_cosmos_client():
    global _cosmos_client
    if _cosmos_client is None:
        url = f"{COSMOS_URL}:{COSMOS_PORT}/"
        _cosmos_client = AsyncCosmosClient(url, credential=COSMOS_KEY)
    return _cosmos_client

async def get_cosmos_db():
    global _cosmos_db
    if _cosmos_db is None:
        client = await get_cosmos_client()
        _cosmos_db = client.get_database_client(COSMOS_DB)
    return _cosmos_db

async def get_cosmos_container():
    global _cosmos_container
    if _cosmos_container is None:
        db = await get_cosmos_db()
        _cosmos_container = db.get_container_client(COSMOS_CONTAINER)
    return _cosmos_container


async def close_cosmos_connections():
    """Close all Cosmos DB connections"""
    global _cosmos_client, _cosmos_db, _cosmos_container
    if _cosmos_client:
        await _cosmos_client.close()
        _cosmos_client = None
        _cosmos_db = None
        _cosmos_container = None


async def save_token_cache_to_cosmos(token_cache: SerializableTokenCache, cosmos_container, user_id: str):
    """
    Async version: Serialize and store the MSAL token cache in Cosmos DB for the given user_id.
    """
    if token_cache.has_state_changed:
        cache_blob = token_cache.serialize()
        item_to_save = {
            "id": user_id,
            COSMOS_PARTITION_KEY: user_id,  # Required for partition key
            "cache": cache_blob
        }
        result = await cosmos_container.upsert_item(item_to_save)
        print(f"🔍 Save to Cosmos: Successfully saved with id = '{result.get('id')}'")
    else:
        print(f"🔍 Save to Cosmos: No state changes, skipping save")


async def load_token_cache_from_cosmos(token_cache: SerializableTokenCache, cosmos_container, user_id: str):
    """
    Async version: Load and deserialize the MSAL token cache from Cosmos DB for the given user_id.
    """
    # Try to read the item, with retry for eventual consistency
    for attempt in range(3):
        try:
            item = await cosmos_container.read_item(item=user_id, partition_key=user_id)
            cache_blob = item.get("cache")
            if cache_blob:
                token_cache.deserialize(cache_blob)
                print(f"🔍 Load from Cosmos: Successfully deserialized cache")
                return
            else:
                print(f"🔍 Load from Cosmos: No cache blob found in item")
                return
        except Exception as e:
            # Handle missing items gracefully - just return empty cache
            if "does not exist" in str(e) or "NotFound" in str(e):
                if attempt < 2:  # Not the last attempt
                    await asyncio.sleep(1)
                    continue
                else:
                    print(f"🔍 Load from Cosmos: No cache found for user '{user_id}' after 3 attempts, starting with empty cache")
                    return
            else:
                # Re-raise other exceptions
                raise Exception(f"❌ Load from Cosmos: Error loading cache: {str(e)}")