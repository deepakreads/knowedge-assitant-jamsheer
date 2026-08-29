import logging
from typing import Optional

from elasticsearch import Elasticsearch

from app.config import ELASTICSEARCH_API_KEY, ELASTICSEARCH_SOP_INDEX, ELASTICSEARCH_URL
from app.schemas.models import Sop

logger = logging.getLogger(__name__)

_es_client = None
_es_checked = False


def get_es_client() -> Optional[Elasticsearch]:
    """
    Get Elasticsearch client - simple and robust.
    Returns None if Elasticsearch is not available or URL is empty.
    """
    global _es_client, _es_checked

    # If URL is empty, skip Elasticsearch entirely
    if not ELASTICSEARCH_URL or ELASTICSEARCH_URL.strip() == "":
        if not _es_checked:
            logger.info("Elasticsearch URL not configured, skipping indexing")
            _es_checked = True
        return None

    # If we already checked and failed, don't try again
    if _es_client is False:
        return None

    # If we have a client, return it
    if _es_client is not None and _es_client is not False:
        return _es_client

    # Try to create client once
    try:
        logger.info("Connecting to Elasticsearch at: %s", ELASTICSEARCH_URL)

        # Simple client creation with minimal parameters
        try:
            # Try with API key if provided
            if ELASTICSEARCH_API_KEY:
                _es_client = Elasticsearch([ELASTICSEARCH_URL], api_key=ELASTICSEARCH_API_KEY)
            else:
                _es_client = Elasticsearch([ELASTICSEARCH_URL])
        except TypeError:
            # Fallback if api_key parameter not supported
            _es_client = Elasticsearch([ELASTICSEARCH_URL])

        # Try a simple info call to verify connection
        try:
            info = _es_client.info()
            logger.info("✅ Connected to Elasticsearch version: %s", info.get("version", {}).get("number", "unknown"))
            return _es_client
        except Exception as e:
            logger.warning("Could not verify Elasticsearch connection: %s", e)
            # Still return the client - it might work for indexing
            return _es_client

    except Exception as exc:
        logger.warning(
            "⚠️  Cannot connect to Elasticsearch at %s: %s. "
            "SOP indexing will be skipped, but app will continue working with local storage.",
            ELASTICSEARCH_URL,
            exc
        )
        _es_client = False
        return None


def ensure_index_exists():
    """Ensure the target index with nested mappings exists before writing documents."""
    client = get_es_client()
    if client is None:
        return

    try:
        if not client.indices.exists(index=ELASTICSEARCH_SOP_INDEX):
            mapping = {
                "mappings": {
                    "properties": {
                        "id": {"type": "keyword"},
                        "job_id": {"type": "keyword"},
                        "status": {"type": "keyword"},
                        "title": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
                        "purpose": {"type": "text"},
                        "scope": {"type": "text"},
                        "required_tools": {"type": "keyword"},
                        "required_materials": {"type": "keyword"},
                        "safety": {"type": "text"},
                        "quality_checks": {"type": "text"},
                        "estimated_duration": {"type": "keyword"},
                        "source_video": {"type": "keyword"},
                        "steps": {
                            "type": "nested",
                            "properties": {
                                "step_number": {"type": "integer"},
                                "title": {"type": "text"},
                                "description": {"type": "text"},
                                "start_time": {"type": "float"},
                                "end_time": {"type": "float"},
                                "tools": {"type": "keyword"},
                                "materials": {"type": "keyword"},
                                "safety_notes": {"type": "text"},
                                "quality_check": {"type": "text"},
                                "confidence": {"type": "float"},
                            },
                        },
                    }
                }
            }
            client.indices.create(index=ELASTICSEARCH_SOP_INDEX, body=mapping)
            logger.info("Created Elasticsearch index: %s", ELASTICSEARCH_SOP_INDEX)
    except Exception as exc:
        logger.warning("Failed to create index: %s", exc)


def index_sop(sop: Sop) -> Optional[dict]:
    """Index an SOP Pydantic model into Elasticsearch. Non-fatal if fails."""
    client = get_es_client()
    if client is None:
        return None

    try:
        ensure_index_exists()
        doc = sop.model_dump()
        response = client.index(
            index=ELASTICSEARCH_SOP_INDEX,
            id=sop.id,
            document=doc,
            refresh=True,
        )
        logger.info("Successfully indexed SOP %s", sop.id)
        return response
    except Exception as exc:
        logger.warning("Failed to index SOP %s: %s", sop.id, exc)
        return None