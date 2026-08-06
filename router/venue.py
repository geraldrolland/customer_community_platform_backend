"""Venue endpoints: create, list, update, delete, and view venues.

Venue managers manage their own venues; customers browse the venue
catalog. Shared read endpoints (all venues, venue details) are served
from the in-memory cache and invalidated on any venue write.
"""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from cache import cache_get, cache_set, invalidate
from database import get_db
from dependencies import RequirePermission
from models import Venue, Roles
from router.static import MEDIA_DIR
from schemas import VenueCreate, VenueOut, VenueUpdate

router = APIRouter(prefix="/api/venue", tags=["venue"])


@router.post(
    "/create",
    status_code=status.HTTP_201_CREATED,
    response_model=VenueOut,
    dependencies=[Depends(RequirePermission(roles=[Roles.VENUE_MANAGER]))],
)
def create_venue(
    payload: VenueCreate,
    request: Request,
    db: Session = Depends(get_db),
):
    """Create a venue owned by the authenticated venue manager.

    Args:
        payload: Validated venue data.
        request: Incoming request with the authenticated venue manager.
        db: Database session.

    Returns:
        VenueOut: The created venue.
    """
    venue = Venue(
        name=payload.name,
        description=payload.description,
        address=payload.address,
        city=payload.city,
        state=payload.state,
        country=payload.country,
        capacity=payload.capacity,
        purpose=payload.purpose,
        venue_type=payload.venue_type,
        amenities=payload.amenities,
        accessibility=payload.accessibility.model_dump(),
        contact=payload.contact.model_dump(),
        website=str(payload.website) if payload.website else None,
        rental_price=payload.rental_price,
        status=payload.status,
        images=[str(img) for img in payload.images],
        parking_availability=payload.parking_availability.model_dump(),
        operating_hours=payload.operating_hours.model_dump(),
        venue_manager_id=request.state.auth_user.id,
    )
    db.add(venue)
    db.commit()
    db.refresh(venue)
    invalidate("venue")
    return venue


@router.get(
    "/me/all",
    response_model=list[VenueOut],
    dependencies=[Depends(RequirePermission(roles=[Roles.VENUE_MANAGER]))],
)
def get_my_venues(
    request: Request,
    limit: Annotated[int, Query(ge=1, le=25)] = 25,
    page_num: Annotated[int, Query(ge=1)] = 1,
    db: Session = Depends(get_db),
):
    """List the authenticated venue manager's venues, newest first.

    Args:
        request: Incoming request with the authenticated venue manager.
        limit: Maximum items per page (1-25).
        page_num: Page number (1-based).
        db: Database session.

    Returns:
        list[VenueOut]: The manager's venues for the requested page.
    """
    return (
        db.query(Venue)
        .filter(Venue.venue_manager_id == request.state.auth_user.id)
        .order_by(Venue.created_at.desc(), Venue.id.desc())
        .offset((page_num - 1) * limit)
        .limit(limit)
        .all()
    )


@router.get(
    "/all",
    response_model=list[VenueOut],
    dependencies=[Depends(RequirePermission(roles=[Roles.CUSTOMER]))],
)
def get_all_venues(
    limit: Annotated[int, Query(ge=1, le=30)] = 30,
    page_num: Annotated[int, Query(ge=1)] = 1,
    db: Session = Depends(get_db),
):
    """List the venue catalog for customers (cached 60s).

    Args:
        limit: Maximum items per page (1-30).
        page_num: Page number (1-based).
        db: Database session.

    Returns:
        list[VenueOut]: Venues, newest first.
    """
    key = f"venue:all:{limit}:{page_num}"
    cached = cache_get(key)
    if cached is not None:
        return cached

    venues = (
        db.query(Venue)
        .order_by(Venue.created_at.desc(), Venue.id.desc())
        .offset((page_num - 1) * limit)
        .limit(limit)
        .all()
    )
    payload = [VenueOut.model_validate(venue).model_dump(mode="json") for venue in venues]
    cache_set(key, payload)
    return payload


@router.get(
    "/me/{venue_id}",
    response_model=VenueOut,
    dependencies=[Depends(RequirePermission(roles=[Roles.VENUE_MANAGER]))],
)
def get_my_venue(venue_id: int, request: Request, db: Session = Depends(get_db)):
    """Fetch one of the venue manager's own venues.

    Args:
        venue_id: Venue to fetch.
        request: Incoming request with the authenticated venue manager.
        db: Database session.

    Returns:
        VenueOut: The requested venue.

    Raises:
        HTTPException: 404 when the venue is missing; 403 when the caller
            does not manage it.
    """
    venue = db.query(Venue).filter(Venue.id == venue_id).first()
    if not venue:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Venue not found",
        )

    if venue.venue_manager_id != request.state.auth_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied",
        )

    return venue


@router.get(
    "/{venue_id}",
    response_model=VenueOut,
    dependencies=[Depends(RequirePermission(roles=[Roles.CUSTOMER]))],
)
def get_venue(venue_id: int, db: Session = Depends(get_db)):
    """Fetch a single venue for customers (cached 60s).

    Args:
        venue_id: Venue to fetch.
        db: Database session.

    Returns:
        VenueOut: The requested venue.

    Raises:
        HTTPException: 404 when the venue does not exist.
    """
    key = f"venue:detail:{venue_id}"
    cached = cache_get(key)
    if cached is not None:
        return cached

    venue = db.query(Venue).filter(Venue.id == venue_id).first()
    if not venue:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Venue not found",
        )
    payload = VenueOut.model_validate(venue).model_dump(mode="json")
    cache_set(key, payload)
    return payload


@router.patch(
    "/{venue_id}",
    response_model=VenueOut,
    dependencies=[Depends(RequirePermission(roles=[Roles.VENUE_MANAGER]))],
)
def update_venue(
    venue_id: int,
    payload: VenueUpdate,
    request: Request,
    db: Session = Depends(get_db),
):
    """Update a venue owned by the venue manager.

    Replacing the image list deletes the previously uploaded media files.

    Args:
        venue_id: Venue to update.
        payload: Fields to change (all optional).
        request: Incoming request with the authenticated venue manager.
        db: Database session.

    Returns:
        VenueOut: The updated venue.

    Raises:
        HTTPException: 404 when the venue is missing; 403 when the caller
            does not manage it.
    """
    venue = db.query(Venue).filter(Venue.id == venue_id).first()
    if not venue:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Venue not found",
        )

    if venue.venue_manager_id != request.state.auth_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied",
        )

    if payload.images is not None:
        for image_url in venue.images:
            file_name = image_url.rsplit("/", 1)[-1]
            (MEDIA_DIR / file_name).unlink(missing_ok=True)
        venue.images = [str(img) for img in payload.images]

    for field, value in payload.model_dump(exclude={"images"}).items():
        if value is not None:
            setattr(venue, field, value)

    db.commit()
    db.refresh(venue)
    invalidate("venue")
    return venue


@router.delete(
    "/{venue_id}",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(RequirePermission(roles=[Roles.VENUE_MANAGER]))],
)
def delete_venue(venue_id: int, request: Request, db: Session = Depends(get_db)):
    """Delete a venue owned by the venue manager.

    Also removes the venue's uploaded media files from disk.

    Args:
        venue_id: Venue to delete.
        request: Incoming request with the authenticated venue manager.
        db: Database session.

    Returns:
        dict: Success message.

    Raises:
        HTTPException: 404 when the venue is missing; 403 when the caller
            does not manage it.
    """
    venue = db.query(Venue).filter(Venue.id == venue_id).first()
    if not venue:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Venue not found",
        )

    if venue.venue_manager_id != request.state.auth_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied",
        )

    for image_url in venue.images:
        file_name = image_url.rsplit("/", 1)[-1]
        (MEDIA_DIR / file_name).unlink(missing_ok=True)

    db.delete(venue)
    db.commit()
    invalidate("venue")
    return {"message": "Venue deleted successfully"}
