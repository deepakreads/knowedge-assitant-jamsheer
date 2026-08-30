"""
SOP Monitoring API - Browse and monitor SOPs with real-time compliance tracking.

GET  /api/sops/                       -> List all SOPs
GET  /api/sops/{sop_id}              -> Get specific SOP details
GET  /api/sops/search?q=query        -> Search SOPs
WS   /ws/monitor/{sop_id}            -> WebSocket for real-time monitoring
"""
import base64
import json
import logging
import io
from typing import Optional

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, Query
from fastapi.responses import JSONResponse

from app.services.sop_retrieval_service import SOPRetrievalService
from app.services.monitoring_service import SOPMonitoringService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["sop-monitoring"])

# Store active monitoring sessions
_active_sessions = {}


@router.get("/sops/")
async def list_sops():
    """
    List all SOPs available for monitoring.

    Returns:
        {
            "sops": [
                {
                    "id": "sop_id",
                    "title": "Assembly Process",
                    "purpose": "To assemble product X",
                    "estimated_duration": "15 minutes",
                    "steps": [...],
                    "required_tools": [...]
                },
                ...
            ]
        }
    """
    try:
        sops = SOPRetrievalService.get_all_sops()
        return JSONResponse(
            content={
                "total": len(sops),
                "sops": sops
            }
        )
    except Exception as e:
        logger.error(f"Failed to list SOPs: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve SOPs")


@router.get("/sops/{sop_id}")
async def get_sop(sop_id: str):
    """
    Get detailed SOP information by ID.

    Args:
        sop_id: Unique SOP identifier

    Returns:
        {
            "id": "sop_id",
            "title": "...",
            "purpose": "...",
            "scope": "...",
            "required_tools": [...],
            "required_materials": [...],
            "safety": "...",
            "estimated_duration": "...",
            "steps": [
                {
                    "step_number": 1,
                    "title": "Position Part",
                    "description": "...",
                    "duration": 30,
                    "tools": ["wrench"],
                    "materials": ["..."],
                    "safety_notes": "...",
                    "quality_check": "..."
                },
                ...
            ]
        }
    """
    try:
        sop = SOPRetrievalService.get_sop_by_id(sop_id)
        if not sop:
            raise HTTPException(status_code=404, detail="SOP not found")

        return JSONResponse(content=sop)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get SOP {sop_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve SOP")


@router.patch("/sops/{sop_id}/approve")
async def approve_sop(sop_id: str):
    """Approve an SOP (change status to APPROVED)."""
    try:
        from app.config import SOPS_DIR, ELASTICSEARCH_SOP_INDEX
        from app.services.elasticsearch_service import get_es_client

        sop = SOPRetrievalService.get_sop_by_id(sop_id)
        if not sop:
            raise HTTPException(status_code=404, detail="SOP not found")

        # Update status to APPROVED
        sop["status"] = "APPROVED"

        # Save to local storage
        sop_file = SOPS_DIR / f"{sop_id}.json"
        with open(sop_file, 'w') as f:
            json.dump(sop, f, indent=2)

        # Update in Elasticsearch if available
        es_client = get_es_client()
        if es_client:
            try:
                es_client.update(
                    index=ELASTICSEARCH_SOP_INDEX,
                    id=sop_id,
                    doc={"status": "APPROVED"},
                    retry_on_conflict=3
                )
            except Exception as e:
                logger.warning(f"Failed to update SOP status in Elasticsearch: {e}")

        logger.info(f"SOP {sop_id} approved")
        return JSONResponse(
            status_code=200,
            content={"message": "SOP approved successfully", "sop_id": sop_id, "status": "APPROVED"}
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to approve SOP {sop_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to approve SOP: {str(e)}")


@router.delete("/sops/{sop_id}")
async def delete_sop(sop_id: str):
    """Delete an SOP."""
    try:
        from app.config import SOPS_DIR, ELASTICSEARCH_SOP_INDEX
        from app.services.elasticsearch_service import get_es_client

        # Delete from local storage
        sop_file = SOPS_DIR / f"{sop_id}.json"
        if sop_file.exists():
            sop_file.unlink()
            logger.info(f"Deleted SOP file: {sop_file}")

        # Delete from Elasticsearch if available
        es_client = get_es_client()
        if es_client:
            try:
                es_client.delete(
                    index=ELASTICSEARCH_SOP_INDEX,
                    id=sop_id,
                    ignore=[404]
                )
                logger.info(f"Deleted SOP from Elasticsearch: {sop_id}")
            except Exception as e:
                logger.warning(f"Failed to delete SOP from Elasticsearch: {e}")

        logger.info(f"SOP {sop_id} deleted")
        return JSONResponse(
            status_code=200,
            content={"message": "SOP deleted successfully", "sop_id": sop_id}
        )
    except Exception as e:
        logger.error(f"Failed to delete SOP {sop_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete SOP: {str(e)}")


@router.get("/sops/search")
async def search_sops(q: str = Query(..., min_length=2)):
    """
    Search SOPs by title, purpose, or scope.

    Args:
        q: Search query (minimum 2 characters)

    Returns:
        {
            "query": "assembly",
            "results": [
                {
                    "id": "sop_id",
                    "title": "Assembly Process",
                    "purpose": "...",
                    "estimated_duration": "..."
                },
                ...
            ]
        }
    """
    try:
        results = SOPRetrievalService.search_sops(q)
        return JSONResponse(
            content={
                "query": q,
                "total": len(results),
                "results": results
            }
        )
    except Exception as e:
        logger.error(f"Search failed for query '{q}': {e}")
        raise HTTPException(status_code=500, detail="Search failed")


@router.websocket("/ws/monitor/{sop_id}")
async def websocket_monitor(websocket: WebSocket, sop_id: str):
    """
    WebSocket endpoint for real-time SOP monitoring with live camera feed.

    Protocol:
        Client → Server:
            {
                "frame": "base64_encoded_image_data"
            }

        Server → Client:
            {
                "current_step": 1,
                "total_steps": 5,
                "step_title": "Position Part",
                "compliance": 75.5,
                "overall_compliance": 72.3,
                "feedback": "Great work! Continue...",
                "next_step_ready": false,
                "warnings": [],
                "time_remaining": 15,
                "progress_percent": 20,
                "tools_required": ["wrench"],
                "step_number": 1
            }
    """
    await websocket.accept()
    monitoring_service = None

    try:
        # Get SOP
        sop = SOPRetrievalService.get_sop_by_id(sop_id)
        if not sop:
            await websocket.send_json({
                "error": "SOP not found",
                "sop_id": sop_id
            })
            await websocket.close(code=4004)
            return

        # Initialize monitoring service
        monitoring_service = SOPMonitoringService(sop)
        session_id = f"{sop_id}_{id(websocket)}"
        _active_sessions[session_id] = monitoring_service

        logger.info(f"Started monitoring session {session_id} for SOP {sop_id}")

        # Send initial SOP info
        await websocket.send_json({
            "type": "sop_loaded",
            "sop_id": sop_id,
            "sop_title": sop.get("title", "Unknown"),
            "total_steps": len(sop.get("steps", [])),
            "message": "SOP loaded. Camera feed ready. Send frames to begin monitoring."
        })

        # Main monitoring loop
        frame_count = 0
        while True:
            # Receive frame from client
            data = await websocket.receive_json()

            if "frame" not in data:
                await websocket.send_json({
                    "error": "Invalid message format. Expected 'frame' field."
                })
                continue

            frame_base64 = data["frame"]

            # Analyze frame
            try:
                result = await monitoring_service.analyze_frame(frame_base64)

                # Add metadata
                result["sop_id"] = sop_id
                result["frame_number"] = frame_count

                # Send back analysis
                await websocket.send_json(result)

                frame_count += 1

                # Log every 30 frames
                if frame_count % 30 == 0:
                    logger.info(
                        f"Session {session_id}: {frame_count} frames analyzed, "
                        f"Step {result.get('current_step', 0)}/{result.get('total_steps', 0)}, "
                        f"Compliance: {result.get('overall_compliance', 0)}%"
                    )

            except Exception as e:
                logger.error(f"Frame analysis error: {e}")
                await websocket.send_json({
                    "error": "Analysis failed",
                    "details": str(e),
                    "frame_number": frame_count
                })

    except WebSocketDisconnect:
        logger.info(f"Client disconnected from monitoring session")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        try:
            await websocket.send_json({"error": f"Server error: {str(e)}"})
        except:
            pass
    finally:
        # Cleanup
        if monitoring_service:
            session_id = f"{sop_id}_{id(websocket)}"
            summary = monitoring_service.get_session_summary()
            logger.info(
                f"Closed monitoring session {session_id}: "
                f"{summary['frames_analyzed']} frames analyzed, "
                f"Overall compliance: {summary['overall_compliance']}%"
            )
            _active_sessions.pop(session_id, None)

        try:
            await websocket.close()
        except:
            pass


@router.get("/monitoring/sessions")
async def get_active_sessions():
    """
    Get list of active monitoring sessions (for debugging/admin purposes).

    Returns:
        {
            "active_sessions": 3,
            "sessions": [
                {
                    "session_id": "...",
                    "sop_id": "...",
                    "current_step": 2,
                    "overall_compliance": 85.5
                },
                ...
            ]
        }
    """
    sessions_info = []
    for session_id, service in _active_sessions.items():
        summary = service.get_session_summary()
        sessions_info.append({
            "session_id": session_id,
            "sop_id": service.sop.get("id", "unknown"),
            "sop_title": service.sop.get("title", "unknown"),
            "current_step": summary["current_step"],
            "total_steps": summary["total_steps"],
            "overall_compliance": summary["overall_compliance"],
            "frames_analyzed": summary["frames_analyzed"],
            "completed": summary["completed"]
        })

    return JSONResponse(
        content={
            "active_sessions": len(sessions_info),
            "sessions": sessions_info
        }
    )


@router.get("/sops/debug/status")
async def debug_sop_status():
    """
    Debug endpoint to check SOP storage status.

    Returns:
        {
            "elasticsearch_status": "connected|failed|not_configured",
            "elasticsearch_url": "...",
            "elasticsearch_index": "...",
            "local_sops_count": 0,
            "elasticsearch_sops_count": 0,
            "sample_local_sops": [...]
        }
    """
    from app.services.elasticsearch_service import get_es_client
    from app.config import ELASTICSEARCH_URL, ELASTICSEARCH_SOP_INDEX, SOPS_DIR

    status_data = {
        "elasticsearch_url": ELASTICSEARCH_URL,
        "elasticsearch_index": ELASTICSEARCH_SOP_INDEX,
        "elasticsearch_status": "not_configured"
    }

    # Check Elasticsearch
    try:
        client = get_es_client()
        if client:
            info = client.info()
            status_data["elasticsearch_status"] = "connected"
            status_data["elasticsearch_version"] = info.get("version", {}).get("number", "unknown")

            # Try to count SOPs in index
            try:
                count_response = client.count(index=ELASTICSEARCH_SOP_INDEX)
                status_data["elasticsearch_sops_count"] = count_response.get("count", 0)
            except Exception as e:
                status_data["elasticsearch_sops_count"] = 0
                status_data["elasticsearch_error"] = str(e)
        else:
            status_data["elasticsearch_status"] = "disconnected"
    except Exception as e:
        status_data["elasticsearch_status"] = "failed"
        status_data["elasticsearch_error"] = str(e)

    # Check local SOPs
    local_sops = []
    try:
        if SOPS_DIR.exists():
            for sop_file in SOPS_DIR.glob("*.json"):
                try:
                    with open(sop_file, 'r') as f:
                        sop = json.load(f)
                        local_sops.append({
                            "id": sop.get("id", "unknown"),
                            "title": sop.get("title", "Unknown"),
                            "file": sop_file.name
                        })
                except Exception as e:
                    logger.error(f"Error reading {sop_file}: {e}")
    except Exception as e:
        logger.error(f"Error reading SOPS_DIR: {e}")

    status_data["local_sops_count"] = len(local_sops)
    status_data["sample_local_sops"] = local_sops[:5]

    return JSONResponse(content=status_data)
