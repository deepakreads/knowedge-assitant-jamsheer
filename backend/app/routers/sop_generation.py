import logging
from fastapi import APIRouter, HTTPException, Response

from app.services import pdf_service, sop_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sop-generation", tags=["SOP Generation"])


@router.get("/sops/{sop_id}")
async def get_sop(sop_id: str):
    sop = sop_service.load_sop(sop_id)
    if sop is None:
        raise HTTPException(status_code=404, detail="SOP not found.")
    return sop


@router.get("/sops/{sop_id}/pdf")
async def download_sop_pdf(sop_id: str):
    sop = sop_service.load_sop(sop_id)
    if sop is None:
        raise HTTPException(status_code=404, detail="SOP not found.")

    try:
        pdf_bytes = pdf_service.generate_sop_pdf(sop)
        filename = f"SOP_{sop.title.replace(' ', '_')}_{sop_id[:8]}.pdf"
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )
    except Exception as exc:
        logger.exception("Failed to generate PDF for SOP %s: %s", sop_id, exc)
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {exc}")