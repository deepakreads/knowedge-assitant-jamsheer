import json
import logging
from pathlib import Path
from typing import List, Dict, Optional

from app.config import SOPS_DIR, ELASTICSEARCH_SOP_INDEX
from app.services.elasticsearch_service import get_es_client

logger = logging.getLogger(__name__)


class SOPRetrievalService:
    """Service to retrieve SOPs from Elasticsearch or fallback to local storage"""

    @staticmethod
    def get_all_sops() -> List[Dict]:
        """Get all SOPs from Elasticsearch or fallback to local storage"""
        client = get_es_client()

        if client:
            try:
                logger.info(f"Searching Elasticsearch index: {ELASTICSEARCH_SOP_INDEX}")
                response = client.search(
                    index=ELASTICSEARCH_SOP_INDEX,
                    size=100,
                    query={"match_all": {}}
                )
                sops = [hit["_source"] for hit in response["hits"]["hits"]]
                logger.info(f"Retrieved {len(sops)} SOPs from Elasticsearch")
                if sops:
                    return sops
            except Exception as e:
                logger.warning(f"Failed to get SOPs from Elasticsearch: {e}")

        # Fallback to local JSON files
        logger.info("Falling back to local storage")
        return SOPRetrievalService._get_sops_from_local()

    @staticmethod
    def _get_sops_from_local() -> List[Dict]:
        """Get SOPs from local JSON files"""
        sops = []
        if not SOPS_DIR.exists():
            logger.info(f"SOPS_DIR does not exist: {SOPS_DIR}")
            return sops

        try:
            for sop_file in SOPS_DIR.glob("*.json"):
                try:
                    with open(sop_file, 'r', encoding='utf-8') as f:
                        sop = json.load(f)
                        sops.append(sop)
                except Exception as e:
                    logger.error(f"Failed to load SOP {sop_file}: {e}")

            logger.info(f"Retrieved {len(sops)} SOPs from local storage")
        except Exception as e:
            logger.error(f"Error reading SOPS_DIR: {e}")

        return sops

    @staticmethod
    def get_sop_by_id(sop_id: str) -> Optional[Dict]:
        """Get specific SOP by ID from Elasticsearch or local storage"""
        client = get_es_client()

        if client:
            try:
                logger.info(f"Fetching SOP {sop_id} from Elasticsearch index: {ELASTICSEARCH_SOP_INDEX}")
                response = client.get(index=ELASTICSEARCH_SOP_INDEX, id=sop_id)
                logger.info(f"Retrieved SOP {sop_id} from Elasticsearch")
                return response["_source"]
            except Exception as e:
                logger.debug(f"Failed to get SOP {sop_id} from Elasticsearch: {e}")

        # Fallback to local
        logger.info(f"Falling back to local storage for SOP {sop_id}")
        sop_file = SOPS_DIR / f"{sop_id}.json"
        if sop_file.exists():
            try:
                with open(sop_file, 'r', encoding='utf-8') as f:
                    sop = json.load(f)
                    logger.info(f"Retrieved SOP {sop_id} from local storage")
                    return sop
            except Exception as e:
                logger.error(f"Failed to load SOP from local storage: {e}")

        logger.warning(f"SOP {sop_id} not found in Elasticsearch or local storage")
        return None

    @staticmethod
    def search_sops(query: str) -> List[Dict]:
        """Search SOPs by title, purpose, or scope"""
        if not query or len(query.strip()) < 2:
            logger.debug(f"Search query too short: '{query}'")
            return []

        client = get_es_client()

        if client:
            try:
                logger.info(f"Searching Elasticsearch index '{ELASTICSEARCH_SOP_INDEX}' for: '{query}'")
                response = client.search(
                    index=ELASTICSEARCH_SOP_INDEX,
                    query={
                        "multi_match": {
                            "query": query,
                            "fields": ["title", "purpose", "scope"]
                        }
                    }
                )
                sops = [hit["_source"] for hit in response["hits"]["hits"]]
                logger.info(f"Found {len(sops)} SOPs matching '{query}' in Elasticsearch")
                if sops:
                    return sops
            except Exception as e:
                logger.warning(f"Search failed in Elasticsearch: {e}")

        # Fallback to local search
        logger.info("Falling back to local storage search")
        all_sops = SOPRetrievalService.get_all_sops()
        query_lower = query.lower()
        results = [
            sop for sop in all_sops
            if query_lower in sop.get("title", "").lower()
               or query_lower in sop.get("purpose", "").lower()
               or query_lower in sop.get("scope", "").lower()
        ]
        logger.info(f"Found {len(results)} SOPs matching '{query}' in local storage")
        return results
