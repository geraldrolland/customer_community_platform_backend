"""Vote endpoints: cast, list, fetch, and delete votes on pending events.

Customers may cast at most one vote per pending event while the proposed
date is still in the future. Casting or deleting a vote changes the
event's vote count, so event cache entries are invalidated accordingly.
"""
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import and_, case, func
from sqlalchemy.orm import Session

from cache import invalidate
from database import get_db
from dependencies import RequirePermission
from models import Event, EventStatus, Roles, Vote, VoteStatus
from schemas import VoteOut

router = APIRouter(prefix="/api/vote", tags=["vote"])


@router.post(
    "/cast",
    status_code=status.HTTP_201_CREATED,
    response_model=VoteOut,
    dependencies=[Depends(RequirePermission(roles=[Roles.CUSTOMER]))],
)
def cast_vote(event_id: int, request: Request, db: Session = Depends(get_db)):
    """Cast a vote on a pending event as a customer.

    Args:
        event_id: Target event id.
        request: Incoming request with the authenticated customer.
        db: Database session.

    Returns:
        VoteOut: The created vote.

    Raises:
        HTTPException: 404 when the event is missing; 400 when the event
            is not pending, its date has passed, or the customer already
            voted on it.
    """
    event_obj = db.query(Event).filter(Event.id == event_id).first()
    if not event_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found",
        )

    if event_obj.status != EventStatus.pending:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vote can only be cast on a pending event",
        )

    if event_obj.proposed_date <= datetime.now(timezone.utc).replace(tzinfo=None):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vote can only be cast on an event whose proposed date has not passed",
        )

    existing = (
        db.query(Vote)
        .filter(
            Vote.event_id == event_id,
            Vote.customer_id == request.state.auth_user.id,
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vote already cast for this event",
        )

    vote = Vote(
        event_id=event_id,
        customer_id=request.state.auth_user.id,
    )
    event_obj.vote_count += 1
    db.add(vote)
    db.commit()
    db.refresh(vote)
    invalidate("event")
    return VoteOut(
        id=vote.id,
        event_title=event_obj.title,
        status=vote.status,
        event_id=vote.event_id,
        created_at=vote.created_at,
    )


@router.get(
    "/me/all",
    response_model=list[VoteOut],
    dependencies=[Depends(RequirePermission(roles=[Roles.CUSTOMER]))],
)
def get_my_votes(
    request: Request,
    limit: Annotated[int, Query(ge=1, le=20)] = 20,
    page_num: Annotated[int, Query(ge=1)] = 1,
    db: Session = Depends(get_db),
):
    """List the authenticated customer's votes, newest first.

    Ballots for events whose proposed date has passed are reported as
    closed.

    Args:
        request: Incoming request with the authenticated customer.
        limit: Maximum items per page (1-20).
        page_num: Page number (1-based).
        db: Database session.

    Returns:
        list[VoteOut]: The customer's votes for the requested page.
    """
    effective_status = case(
        (
            and_(
                Event.proposed_date < func.now(),
                Vote.status == VoteStatus.ballot_open,
            ),
            VoteStatus.ballot_close,
        ),
        else_=Vote.status,
    ).label("effective_status")
    rows = (
        db.query(Vote, Event.title, effective_status)
        .join(Event, Event.id == Vote.event_id)
        .filter(Vote.customer_id == request.state.auth_user.id)
        .order_by(Vote.created_at.desc(), Vote.id.desc())
        .offset((page_num - 1) * limit)
        .limit(limit)
        .all()
    )
    return [
        VoteOut(
            id=vote.id,
            event_title=title,
            status=status,
            event_id=vote.event_id,
            created_at=vote.created_at,
        )
        for vote, title, status in rows
    ]


@router.get(
    "/{vote_id}",
    response_model=VoteOut,
    dependencies=[Depends(RequirePermission(roles=[Roles.CUSTOMER]))],
)
def get_vote(vote_id: int, request: Request, db: Session = Depends(get_db)):
    """Fetch one of the customer's votes by id.

    Args:
        vote_id: Vote to fetch.
        request: Incoming request with the authenticated customer.
        db: Database session.

    Returns:
        VoteOut: The requested vote.

    Raises:
        HTTPException: 404 when the vote is missing; 403 when it belongs
            to another customer.
    """
    vote = db.query(Vote).filter(Vote.id == vote_id).first()
    if not vote:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vote not found",
        )

    if vote.customer_id != request.state.auth_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied",
        )

    return VoteOut(
        id=vote.id,
        event_title=vote.event.title,
        status=vote.status,
        event_id=vote.event_id,
        created_at=vote.created_at,
    )


@router.delete(
    "/{vote_id}",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(RequirePermission(roles=[Roles.CUSTOMER]))],
)
def delete_vote(vote_id: int, request: Request, db: Session = Depends(get_db)):
    """Delete one of the customer's votes while its ballot is open.

    Args:
        vote_id: Vote to delete.
        request: Incoming request with the authenticated customer.
        db: Database session.

    Returns:
        dict: Success message.

    Raises:
        HTTPException: 404 when the vote is missing; 403 when it belongs
            to another customer; 400 when the ballot is closed or the
            event's proposed date has passed.
    """
    vote = db.query(Vote).filter(Vote.id == vote_id).first()
    if not vote:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vote not found",
        )

    if vote.customer_id != request.state.auth_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied",
        )

    if vote.status != VoteStatus.ballot_open:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vote can only be deleted while the ballot is open",
        )

    if vote.event.proposed_date <= datetime.now(timezone.utc).replace(tzinfo=None):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vote can only be deleted before the event's proposed date",
        )

    event = vote.event
    db.delete(vote)
    event.vote_count -= 1
    db.commit()
    invalidate("event")
    return {"message": "Vote deleted successfully"}
