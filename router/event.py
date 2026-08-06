"""Event endpoints: propose, list, update, delete, and moderate events.

Customers propose events for a target venue; venue managers review
pending proposals and can approve or reject them. Read endpoints shared
across users (upcoming/pending lists, event details) are served from the
in-memory cache and invalidated on any event write.
"""
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from cache import cache_get, cache_set, invalidate
from database import get_db
from dependencies import RequirePermission
from models import Event, EventStatus, Roles, Venue, VoteStatus
from schemas import EventCreate, EventOut, EventUpdate

router = APIRouter(prefix="/api/event", tags=["event"])


@router.post(
    "/create",
    status_code=status.HTTP_201_CREATED,
    response_model=EventOut,
    dependencies=[Depends(RequirePermission(roles=[Roles.CUSTOMER]))],
)
def create_event(payload: EventCreate, request: Request, db: Session = Depends(get_db)):
    """Propose a new event as a customer.

    Args:
        payload: Event proposal (title, date, target venue).
        request: Incoming request with the authenticated customer.
        db: Database session.

    Returns:
        EventOut: The created event (status ``pending``).

    Raises:
        HTTPException: 404 when the target venue does not exist.
    """
    if not db.query(Venue).filter(Venue.id == payload.target_venue_id).first():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Venue not found",
        )

    event = Event(
        title=payload.title,
        description=payload.description,
        proposed_date=payload.proposed_date,
        target_venue_id=payload.target_venue_id,
        status=payload.status,
        customer_id=request.state.auth_user.id,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    invalidate("event")
    return event


@router.get(
    "/me/all",
    response_model=list[EventOut],
    dependencies=[Depends(RequirePermission(roles=[Roles.CUSTOMER]))],
)
def get_my_events(
    request: Request,
    limit: Annotated[int, Query(ge=1, le=25)] = 25,
    page_num: Annotated[int, Query(ge=1)] = 1,
    db: Session = Depends(get_db),
):
    """List the authenticated customer's own events, newest first.

    Args:
        request: Incoming request with the authenticated customer.
        limit: Maximum items per page (1-25).
        page_num: Page number (1-based).
        db: Database session.

    Returns:
        list[EventOut]: The customer's events for the requested page.
    """
    return (
        db.query(Event)
        .filter(Event.customer_id == request.state.auth_user.id)
        .order_by(Event.created_at.desc(), Event.id.desc())
        .offset((page_num - 1) * limit)
        .limit(limit)
        .all()
    )


@router.get(
    "/status",
    response_model=list[EventOut],
    dependencies=[Depends(RequirePermission(roles=[Roles.VENUE_MANAGER]))],
)
def get_venue_events_by_status(
    venue_id: int,
    status: Annotated[EventStatus, Query(alias="status")],
    request: Request,
    limit: Annotated[int, Query(ge=1, le=50)] = 50,
    page_num: Annotated[int, Query(ge=1)] = 1,
    db: Session = Depends(get_db),
):
    """List events of a venue filtered by status (venue-manager only).

    Args:
        venue_id: Target venue id.
        status: Event status filter (pending/approved/rejected).
        request: Incoming request with the authenticated venue manager.
        limit: Maximum items per page (1-50).
        page_num: Page number (1-based).
        db: Database session.

    Returns:
        list[EventOut]: Matching events, ordered by vote count.

    Raises:
        HTTPException: 404 when the venue does not exist; 403 when the
            caller does not manage the venue.
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

    return (
        db.query(Event)
        .filter(Event.target_venue_id == venue_id, Event.status == status)
        .order_by(Event.vote_count.desc(), Event.created_at.desc(), Event.id.desc())
        .offset((page_num - 1) * limit)
        .limit(limit)
        .all()
    )


@router.get(
    "/all/upcoming",
    response_model=list[EventOut],
    dependencies=[Depends(RequirePermission(roles=[Roles.CUSTOMER]))],
)
def get_upcoming_events(
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
    page_num: Annotated[int, Query(ge=1)] = 1,
    db: Session = Depends(get_db),
):
    """List approved events scheduled from now onward (cached 60s).

    Args:
        limit: Maximum items per page (1-100).
        page_num: Page number (1-based).
        db: Database session.

    Returns:
        list[EventOut]: Upcoming approved events, soonest first.
    """
    key = f"event:upcoming:{limit}:{page_num}"
    cached = cache_get(key)
    if cached is not None:
        return cached

    events = (
        db.query(Event)
        .filter(Event.status == EventStatus.approved, Event.proposed_date >= func.now())
        .order_by(Event.proposed_date.asc(), Event.id.asc())
        .offset((page_num - 1) * limit)
        .limit(limit)
        .all()
    )
    payload = [
        EventOut.model_validate(event).model_dump(mode="json") for event in events
    ]
    cache_set(key, payload)
    return payload


@router.get(
    "/all/pending",
    response_model=list[EventOut],
    dependencies=[Depends(RequirePermission(roles=[Roles.CUSTOMER]))],
)
def get_pending_events(
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
    page_num: Annotated[int, Query(ge=1)] = 1,
    db: Session = Depends(get_db),
):
    """List pending events scheduled in the future (cached 60s).

    Args:
        limit: Maximum items per page (1-100).
        page_num: Page number (1-based).
        db: Database session.

    Returns:
        list[EventOut]: Pending future events, soonest first.
    """
    key = f"event:pending:{limit}:{page_num}"
    cached = cache_get(key)
    if cached is not None:
        return cached

    events = (
        db.query(Event)
        .filter(Event.status == EventStatus.pending, Event.proposed_date > func.now())
        .order_by(Event.proposed_date.asc(), Event.id.asc())
        .offset((page_num - 1) * limit)
        .limit(limit)
        .all()
    )
    payload = [
        EventOut.model_validate(event).model_dump(mode="json") for event in events
    ]
    cache_set(key, payload)
    return payload


@router.patch(
    "/{event_id}/status",
    response_model=EventOut,
    dependencies=[Depends(RequirePermission(roles=[Roles.VENUE_MANAGER]))],
)
def update_event_status(
    event_id: int,
    new_status: Annotated[EventStatus, Query(alias="status")],
    request: Request,
    db: Session = Depends(get_db),
):
    """Approve or reject a pending event (venue-manager only).

    Also closes the ballot on every vote cast for the event.

    Args:
        event_id: Event to moderate.
        new_status: Target status (approved or rejected).
        request: Incoming request with the authenticated venue manager.
        db: Database session.

    Returns:
        EventOut: The updated event.

    Raises:
        HTTPException: 404 when the event is missing; 403 when the caller
            does not manage the target venue; 400 when the transition or
            the event date is invalid.
    """
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found",
        )

    venue = db.query(Venue).filter(Venue.id == event.target_venue_id).first()
    if not venue or venue.venue_manager_id != request.state.auth_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied",
        )

    if event.status != EventStatus.pending or new_status not in (
        EventStatus.approved,
        EventStatus.rejected,
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Event status can only be updated from pending to approved or rejected",
        )

    if event.proposed_date <= datetime.now(timezone.utc).replace(tzinfo=None):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot update status of an event whose proposed date has passed",
        )

    event.status = new_status
    for vote in event.votes:
        vote.status = VoteStatus.ballot_close
    db.commit()
    db.refresh(event)
    invalidate("event")
    return event


@router.patch(
    "/{event_id}",
    response_model=EventOut,
    dependencies=[Depends(RequirePermission(roles=[Roles.CUSTOMER]))],
)
def update_event(
    event_id: int,
    payload: EventUpdate,
    request: Request,
    db: Session = Depends(get_db),
):
    """Update a pending event owned by the customer.

    Args:
        event_id: Event to update.
        payload: Fields to change (all optional).
        request: Incoming request with the authenticated customer.
        db: Database session.

    Returns:
        EventOut: The updated event.

    Raises:
        HTTPException: 404 when the event or target venue is missing; 403
            when the event belongs to another customer; 400 when the event
            is not pending or the new date is in the past.
    """
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found",
        )

    if event.customer_id != request.state.auth_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied",
        )

    if event.status != EventStatus.pending:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Event can only be updated while pending",
        )

    if payload.proposed_date is not None and payload.proposed_date <= datetime.now(
        timezone.utc
    ).replace(tzinfo=None):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Proposed date must be in the future",
        )

    if payload.target_venue_id is not None and not db.query(Venue).filter(
        Venue.id == payload.target_venue_id
    ).first():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Venue not found",
        )

    for field, value in payload.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(event, field, value)

    db.commit()
    db.refresh(event)
    invalidate("event")
    return event


@router.delete(
    "/{event_id}",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(RequirePermission(roles=[Roles.CUSTOMER]))],
)
def delete_event(event_id: int, request: Request, db: Session = Depends(get_db)):
    """Delete a pending event owned by the customer.

    Args:
        event_id: Event to delete.
        request: Incoming request with the authenticated customer.
        db: Database session.

    Returns:
        dict: Success message.

    Raises:
        HTTPException: 404 when the event is missing; 403 when it belongs
            to another customer; 400 when it is no longer pending.
    """
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found",
        )

    if event.customer_id != request.state.auth_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied",
        )

    if event.status != EventStatus.pending:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Event can only be deleted while pending",
        )

    db.delete(event)
    db.commit()
    invalidate("event")
    return {"message": "Event deleted successfully"}


@router.get(
    "/{event_id}",
    response_model=EventOut,
    dependencies=[Depends(RequirePermission(roles=[Roles.CUSTOMER]))],
)
def get_event(event_id: int, request: Request, db: Session = Depends(get_db)):
    """Fetch a single event by id (cached 60s).

    Args:
        event_id: Event to fetch.
        request: Incoming request with the authenticated user.
        db: Database session.

    Returns:
        EventOut: The requested event.

    Raises:
        HTTPException: 404 when the event does not exist.
    """
    key = f"event:detail:{event_id}"
    cached = cache_get(key)
    if cached is not None:
        return cached

    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found",
        )

    payload = EventOut.model_validate(event).model_dump(mode="json")
    cache_set(key, payload)
    return payload
