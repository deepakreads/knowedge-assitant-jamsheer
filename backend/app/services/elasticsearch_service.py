import logging

from elasticsearch import Elasticsearch

from app.config import ELASTICSEARCH_API_KEY, ELASTICSEARCH_SOP_INDEX, ELASTICSEARCH_URL
from app.schemas.models import Sop

logger = logging.getLogger(__name__)

_es_client = None


def get_es_client() -> Elasticsearch:
    global _es_client
    if _es_client is None:
        kwargs = {"hosts": [ELASTICSEARCH_URL]}
        if ELASTICSEARCH_API_KEY:
            kwargs["api_key"] = ELASTICSEARCH_API_KEY
        _es_client = Elasticsearch(**kwargs)
    return _es_client


def ensure_index_exists():
    """Ensure the target index with nested mappings exists before writing documents."""
    client = get_es_client()
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


def index_sop(sop: Sop):
    """Index an SOP Pydantic model into Elasticsearch."""
    try:
        ensure_index_exists()
        client = get_es_client()

        # Convert Pydantic model to dict/JSON payload
        doc = sop.model_dump()

        response = client.index(
            index=ELASTICSEARCH_SOP_INDEX,
            id=sop.id,
            document=doc,
            refresh=True,  # Makes document immediately searchable
        )
        logger.info("Successfully indexed SOP %s into Elasticsearch index '%s'. Result: %s", sop.id, ELASTICSEARCH_SOP_INDEX, response.get("result"))
        return response
    except Exception as exc:
        logger.error("Failed to index SOP %s in Elasticsearch: %s", sop.id, exc, exc_info=True)
        # Non-fatal so local storage remains functional if Elasticsearch is down
        return None