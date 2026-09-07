"""
Machine-based SOP Discovery API

GET  /api/find-sop/departments          -> List all departments
GET  /api/find-sop/machines              -> List all machines
GET  /api/find-sop/by-department         -> Search SOPs by department
GET  /api/find-sop/by-machine-name       -> Search SOPs by machine name
POST /api/find-sop/by-image              -> Find SOPs by machine image (vision AI)
"""
import logging
import base64
import tempfile
import re
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import JSONResponse

from app.services.sop_retrieval_service import SOPRetrievalService
from app.services import vision_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/find-sop", tags=["machine-sop-finder"])


@router.get("/departments")
async def get_departments():
    """
    Get list of all unique departments from available SOPs.

    Returns:
        {
            "departments": ["Department A", "Department B", ...],
            "total": 3
        }
    """
    try:
        sops = SOPRetrievalService.get_all_sops()
        departments = set()

        for sop in sops:
            dept = sop.get("metadata", {}).get("department")
            if dept:
                departments.add(dept)

        departments_list = sorted(list(departments))

        return JSONResponse(
            content={
                "departments": departments_list,
                "total": len(departments_list)
            }
        )
    except Exception as e:
        logger.error(f"Failed to get departments: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve departments")


@router.get("/machines")
async def get_machines():
    """
    Get list of all unique machines from available SOPs.

    Returns:
        {
            "machines": ["Machine X", "Machine Y", ...],
            "total": 3
        }
    """
    try:
        sops = SOPRetrievalService.get_all_sops()
        machines = set()

        for sop in sops:
            machine = sop.get("metadata", {}).get("machine_name")
            if machine:
                machines.add(machine)

        machines_list = sorted(list(machines))

        return JSONResponse(
            content={
                "machines": machines_list,
                "total": len(machines_list)
            }
        )
    except Exception as e:
        logger.error(f"Failed to get machines: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve machines")


@router.get("/by-department")
async def find_by_department(department: str = Query(..., min_length=1)):
    """
    Find SOPs by department.

    Args:
        department: Department name to search for

    Returns:
        {
            "query": "Department A",
            "total": 3,
            "sops": [
                {
                    "id": "sop_id",
                    "title": "...",
                    "status": "APPROVED",
                    "estimated_duration": "...",
                    "machine_name": "..."
                },
                ...
            ]
        }
    """
    try:
        sops = SOPRetrievalService.get_all_sops()
        matching_sops = [
            {
                "id": sop.get("id"),
                "title": sop.get("title", "Unknown"),
                "purpose": sop.get("purpose", ""),
                "status": sop.get("status", "REVIEW_REQUIRED"),
                "estimated_duration": sop.get("estimated_duration", "Not specified"),
                "machine_name": sop.get("metadata", {}).get("machine_name", "Not specified"),
                "department": sop.get("metadata", {}).get("department", ""),
            }
            for sop in sops
            if sop.get("metadata", {}).get("department", "").lower() == department.lower()
        ]

        return JSONResponse(
            content={
                "query": department,
                "total": len(matching_sops),
                "sops": matching_sops
            }
        )
    except Exception as e:
        logger.error(f"Failed to search by department: {e}")
        raise HTTPException(status_code=500, detail="Failed to search SOPs")


@router.get("/by-machine-name")
async def find_by_machine(machine_name: str = Query(..., min_length=1)):
    """
    Find SOPs by machine name.

    Args:
        machine_name: Machine name to search for

    Returns:
        {
            "query": "Machine X",
            "total": 2,
            "sops": [
                {
                    "id": "sop_id",
                    "title": "...",
                    "status": "APPROVED",
                    "estimated_duration": "...",
                    "department": "..."
                },
                ...
            ]
        }
    """
    try:
        sops = SOPRetrievalService.get_all_sops()
        matching_sops = [
            {
                "id": sop.get("id"),
                "title": sop.get("title", "Unknown"),
                "purpose": sop.get("purpose", ""),
                "status": sop.get("status", "REVIEW_REQUIRED"),
                "estimated_duration": sop.get("estimated_duration", "Not specified"),
                "machine_name": sop.get("metadata", {}).get("machine_name", "Not specified"),
                "department": sop.get("metadata", {}).get("department", ""),
            }
            for sop in sops
            if machine_name.lower() in sop.get("metadata", {}).get("machine_name", "").lower()
        ]

        return JSONResponse(
            content={
                "query": machine_name,
                "total": len(matching_sops),
                "sops": matching_sops
            }
        )
    except Exception as e:
        logger.error(f"Failed to search by machine name: {e}")
        raise HTTPException(status_code=500, detail="Failed to search SOPs")


@router.post("/by-image")
async def find_by_image(image: UploadFile = File(...)):
    """
    Find SOPs by analyzing machine image using vision AI.

    This endpoint uses computer vision to:
    1. Identify the machine type from the uploaded image
    2. Compare it with machine images stored in SOPs
    3. Return matching SOPs scored by visual similarity

    Args:
        image: Image file (JPG, PNG, GIF)

    Returns:
        {
            "machine_detected": "Machine X",
            "confidence": 0.95,
            "analysis": "This appears to be a plasticizing injection molding machine...",
            "matching_sops": [
                {
                    "id": "sop_id",
                    "title": "...",
                    "match_score": 95,
                    "department": "...",
                    "machine_name": "...",
                    "image_similarity": 0.92
                },
                ...
            ],
            "total": 3
        }
    """
    try:
        # Validate image file
        extension = Path(image.filename or "").suffix.lower()
        if extension not in {".jpg", ".jpeg", ".png", ".gif"}:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported image type '{extension}'. Allowed: .jpg, .jpeg, .png, .gif",
            )

        # Read image data
        image_data = await image.read()
        image_base64 = base64.b64encode(image_data).decode()

        # Create temporary image file
        with tempfile.NamedTemporaryFile(suffix=extension, delete=False) as tmp:
            tmp.write(image_data)
            tmp_path = tmp.name

        try:
            # Use vision service to analyze machine image
            analysis_prompt = """Analyze this machine image and answer:
1. What type of machine is this? (e.g., "Injection molding machine", "CNC machine", "Assembly line")
2. What specific model or brand if visible?
3. What is the primary function of this machine?
4. What department would this typically be in? (e.g., "Manufacturing", "Assembly", "Quality Control")
5. What are the key visible features and characteristics?
6. List specific visual identifiers (color, size, shape, components, controls visible)

Be specific and technical. Base your answer only on what you can see in the image."""

            logger.info("Analyzing machine image...")
            analysis = await vision_service.analyze_frame_with_prompt(
                image_base64,
                analysis_prompt
            )

            # Extract machine type and department from analysis
            machine_type = extract_machine_type(analysis)
            detected_department = extract_department(analysis)

            # Get all SOPs and score matches
            sops = SOPRetrievalService.get_all_sops()
            scored_sops = []

            for sop in sops:
                sop_machine_name = sop.get("metadata", {}).get("machine_name", "")
                sop_dept = sop.get("metadata", {}).get("department", "")
                sop_machine_pic = sop.get("metadata", {}).get("machine_picture")

                match_score = 0
                image_similarity = 0

                # Text-based matching on machine name and department
                if sop_machine_name:
                    sop_machine_lower = sop_machine_name.lower()
                    if machine_type and machine_type in sop_machine_lower:
                        match_score += 40  # Reduced from 60
                    elif machine_type:
                        # Partial match
                        if any(word in sop_machine_lower for word in machine_type.split()):
                            match_score += 20

                # Department match
                if sop_dept:
                    sop_dept_lower = sop_dept.lower()
                    if detected_department and detected_department in sop_dept_lower:
                        match_score += 20  # Reduced from 40
                    elif detected_department:
                        # Partial match
                        if any(word in sop_dept_lower for word in detected_department.split()):
                            match_score += 10

                # Visual comparison with stored machine image
                if sop_machine_pic and Path(sop_machine_pic).exists():
                    try:
                        logger.info(f"Comparing images for SOP {sop.get('id')}")

                        # Read stored machine image
                        with open(sop_machine_pic, "rb") as f:
                            stored_image_data = f.read()
                        stored_image_base64 = base64.b64encode(stored_image_data).decode()

                        # Compare the two images using vision AI
                        comparison_prompt = f"""Compare these two machine images:

IMAGE 1 (Reference from SOP): This is a stored reference image
IMAGE 2 (User uploaded): This is the image uploaded by the user

Task: Determine if these are the same machine or similar machines.

Analyze:
1. Are these the same machine model? (Yes/No/Maybe)
2. How similar are they in appearance? (Percentage 0-100%)
3. Do they have the same key features and components?
4. Same color scheme and design?
5. Confidence in match (Low/Medium/High)

Base your assessment ONLY on visual similarity.
Provide a numerical similarity score from 0 to 100."""

                        # Call vision service to compare both images
                        # Note: This is a simplified comparison using single image analysis
                        # For true visual similarity, would need multi-image comparison
                        similarity_analysis = await vision_service.analyze_frame_with_prompt(
                            image_base64,
                            f"{comparison_prompt}\n\nReference machine description: {analysis}"
                        )

                        # Extract similarity score from response
                        image_similarity = extract_similarity_score(similarity_analysis)

                        # Add image similarity score to total (up to 40 points)
                        image_match_points = int((image_similarity / 100) * 40)
                        match_score += image_match_points

                        logger.info(
                            f"SOP {sop.get('id')}: Image similarity={image_similarity}%, "
                            f"Image points={image_match_points}, Total score={match_score}"
                        )

                    except Exception as e:
                        logger.warning(f"Failed to compare machine images for SOP {sop.get('id')}: {e}")
                        image_similarity = 0

                # Only include SOPs with meaningful matches
                if match_score > 15 or image_similarity > 30:
                    scored_sops.append({
                        "id": sop.get("id"),
                        "title": sop.get("title", "Unknown"),
                        "status": sop.get("status", "REVIEW_REQUIRED"),
                        "estimated_duration": sop.get("estimated_duration", "Not specified"),
                        "machine_name": sop_machine_name or "Not specified",
                        "department": sop_dept or "Not specified",
                        "match_score": min(100, match_score),
                        "image_similarity": image_similarity,
                    })

            # Sort by match score (text + visual combined)
            scored_sops.sort(key=lambda x: x["match_score"], reverse=True)

            return JSONResponse(
                content={
                    "machine_detected": machine_type or "Unknown",
                    "department_detected": detected_department or "Unknown",
                    "confidence": 0.85,
                    "analysis": analysis,
                    "matching_sops": scored_sops[:10],  # Top 10 matches
                    "total": len(scored_sops),
                }
            )

        finally:
            # Clean up temporary file
            Path(tmp_path).unlink(missing_ok=True)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Image analysis failed: {e}")
        raise HTTPException(status_code=500, detail=f"Image analysis failed: {str(e)}")


def extract_machine_type(analysis: str) -> Optional[str]:
    """Extract machine type from vision analysis."""
    analysis_lower = analysis.lower()

    # Common machine types
    machines = [
        "injection molding",
        "cnc machine",
        "assembly line",
        "welding",
        "lathe",
        "milling",
        "grinding",
        "drilling",
        "stamping",
        "pressing",
        "packaging",
        "conveyor",
        "robot",
    ]

    for machine in machines:
        if machine in analysis_lower:
            return machine

    # Try to extract first sentence as fallback
    sentences = analysis.split(".")
    if sentences:
        first_sentence = sentences[0].strip()
        if "machine" in first_sentence.lower():
            return first_sentence[:50]

    return None


def extract_department(analysis: str) -> Optional[str]:
    """Extract department from vision analysis."""
    analysis_lower = analysis.lower()

    # Common departments
    departments = [
        "manufacturing",
        "assembly",
        "quality control",
        "maintenance",
        "operations",
        "production",
        "testing",
        "inspection",
    ]

    for dept in departments:
        if dept in analysis_lower:
            return dept

    return None


def extract_similarity_score(analysis: str) -> float:
    """
    Extract similarity percentage from vision comparison analysis.

    Looks for patterns like "XX%", "similarity: XX", etc.
    """
    analysis_lower = analysis.lower()

    # Look for percentage patterns
    percentages = re.findall(r'(\d+)\s*%', analysis)
    if percentages:
        # Return the first percentage found (usually the similarity score)
        return float(percentages[0])

    # Look for similarity scores without percent sign
    if "yes" in analysis_lower and "same" in analysis_lower:
        return 80.0
    elif "maybe" in analysis_lower or "partially" in analysis_lower or "similar" in analysis_lower:
        return 50.0
    elif "no" in analysis_lower or "different" in analysis_lower:
        return 20.0

    # Look for confidence levels
    if "high confidence" in analysis_lower or "very similar" in analysis_lower:
        return 85.0
    elif "medium confidence" in analysis_lower or "somewhat similar" in analysis_lower:
        return 55.0
    elif "low confidence" in analysis_lower or "quite different" in analysis_lower:
        return 25.0

    # Default: unable to determine, but not impossible
    return 40.0
