import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from dependencies import RequirePermission
from models import Roles
router = APIRouter(prefix="/api/media", tags=["media"])

MEDIA_DIR = Path(__file__).resolve().parent.parent / "media"
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}
MAX_IMAGES = 5


@router.post(
    "/upload",
    dependencies=[Depends(RequirePermission(roles=[Roles.VENUE_MANAGER]))],
)
async def upload_images(images: list[UploadFile] = File(...)):
    if len(images) > MAX_IMAGES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Maximum of {MAX_IMAGES} images allowed",
        )

    MEDIA_DIR.mkdir(parents=True, exist_ok=True)

    image_urls = []
    for image in images:
        extension = Path(image.filename or "").suffix.lower()
        if extension not in ALLOWED_IMAGE_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported image format: {extension or 'unknown'}",
            )

        file_name = uuid.uuid4().hex + extension
        content = await image.read()
        if not content:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Empty image file: {image.filename}",
            )

        (MEDIA_DIR / file_name).write_bytes(content)
        image_urls.append(f"/static/media/{file_name}")

    return image_urls
