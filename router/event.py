from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from database import get_db
from dependencies import RequirePermission
from models import Event, EventStatus, Roles, Venue, VoteStatus
from schemas import EventCreate, EventOut

router = APIRouter(prefix="/api/event", tags=["event"])


@router.post(
    "/create",
    status_code=status.HTTP_201_CREATED,
    response_model=EventOut,
    dependencies=[Depends(RequirePermission(roles=[Roles.CUSTOMER]))],
)
def create_event(payload: EventCreate, request: Request, db: Session = Depends(get_db)):
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
    return (
        db.query(Event)
        .filter(Event.status == EventStatus.approved, Event.proposed_date >= func.now())
        .order_by(Event.proposed_date.asc(), Event.id.asc())
        .offset((page_num - 1) * limit)
        .limit(limit)
        .all()
    )


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
    return (
        db.query(Event)
        .filter(Event.status == EventStatus.pending, Event.proposed_date > func.now())
        .order_by(Event.proposed_date.asc(), Event.id.asc())
        .offset((page_num - 1) * limit)
        .limit(limit)
        .all()
    )


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

    if event.proposed_date <= func.now():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot update status of an event whose proposed date has passed",
        )

    event.status = new_status
    for vote in event.votes:
        vote.status = VoteStatus.ballot_close
    db.commit()
    db.refresh(event)
    return event


@router.get(
    "/{event_id}",
    response_model=EventOut,
    dependencies=[Depends(RequirePermission(roles=[Roles.CUSTOMER]))],  
)
def get_event(event_id: int, request: Request, db: Session = Depends(get_db)):
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found",
        )

    return event
