"""SQLAlchemy ORM models and enumerations for the HappenHub platform.

Defines the two user types (customers and venue managers), venues, events,
votes, and the shared mixins/enums used across the schema.
"""
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class Roles(str, PyEnum):
    """User roles supported by the platform."""

    CUSTOMER = "customer"
    VENUE_MANAGER = "venue_manager"

class TimestampMixin:
    """Mixin adding ``created_at`` and ``updated_at`` timestamp columns."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class UserMixin:
    """Mixin with the shared identity and credential columns for both user types."""

    first_name: Mapped[str] = mapped_column(String(50), nullable=False)
    middle_name: Mapped[str | None] = mapped_column(String(50), nullable=True)
    last_name: Mapped[str] = mapped_column(String(50), nullable=False)
    email: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False
    )
    is_email_verified: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="0", nullable=False
    )
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    session_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True, default=None
    )


class Customer(TimestampMixin, UserMixin, Base):
    """A registered customer who proposes events and casts votes."""

    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    role: Mapped[str] = mapped_column(
        String(50), nullable=False, default="customer", server_default="customer"
    )

    events: Mapped[list["Event"]] = relationship(back_populates="customer")
    votes: Mapped[list["Vote"]] = relationship(back_populates="customer")


class VenueManager(TimestampMixin, UserMixin, Base):
    """A venue manager who manages venues and approves or rejects events."""

    __tablename__ = "venue_managers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    role: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="venue_manager",
        server_default="venue_manager",
    )

    venues: Mapped[list["Venue"]] = relationship(
        back_populates="venue_manager", cascade="all, delete-orphan"
    )


class VenuePurpose(str, PyEnum):
    """Catalog of venue purposes used to constrain the valid venue types."""

    corporate_and_business = "Corporate and Business"
    weddings_and_celebration = "Weddings and Celebration"
    entertainment = "Entertainment"
    sport = "Sport"
    outdoor = "Outdoor"
    hospitality = "Hospitality"
    educational = "Educational"
    religion = "Religion"
    community_and_government = "Community and Government"
    exhibition_and_trade = "Exhibition and Trade"
    creative_and_media = "Creative and Media"
    private = "Private"
    health_and_wellness = "Health and Wellness"
    unique_venues = "Unique Venues"


class VenueType(str, PyEnum):
    """Catalog of venue types, each grouped under a venue purpose."""

    conference_center = "Conference Center"
    convention_center = "Convention Center"
    meeting_room = "Meeting Room"
    boardroom = "Boardroom"
    training_room = "Training Room"
    seminar_hall = "Seminar Hall"
    business_center = "Business Center"
    coworking_space = "Coworking Space"
    banquet_hall = "Banquet Hall"
    wedding_hall = "Wedding Hall"
    reception_hall = "Reception Hall"
    ballroom = "Ballroom"
    garden = "Garden"
    chapel = "Chapel"
    event_center = "Event Center"
    theater = "Theater"
    cinema = "Cinema"
    concert_hall = "Concert Hall"
    opera_house = "Opera House"
    comedy_club = "Comedy Club"
    nightclub = "Nightclub"
    casino = "Casino"
    hotel = "Hotel"
    resort = "Resort"
    restaurant = "Restaurant"
    cafe = "Cafe"
    bar = "Bar"
    lounge = "Lounge"
    winery = "Winery"
    brewery = "Brewery"
    stadium = "Stadium"
    arena = "Arena"
    sports_complex = "Sports Complex"
    gymnasium = "Gymnasium"
    indoor_sports_hall = "Indoor Sports Hall"
    tennis_court = "Tennis Court"
    golf_club = "Golf Club"
    swimming_pool = "Swimming Pool"
    park = "Park"
    beach = "Beach"
    rooftop = "Rooftop"
    botanical_garden = "Botanical Garden"
    farm = "Farm"
    ranch = "Ranch"
    campground = "Campground"
    open_field = "Open Field"
    amphitheater = "Amphitheater"
    university_auditorium = "University Auditorium"
    school_hall = "School Hall"
    lecture_hall = "Lecture Hall"
    library = "Library"
    classroom = "Classroom"
    church = "Church"
    mosque = "Mosque"
    temple = "Temple"
    synagogue = "Synagogue"
    community_worship_hall = "Community Worship Hall"
    community_center = "Community Center"
    civic_center = "Civic Center"
    town_hall = "Town Hall"
    cultural_center = "Cultural Center"
    exhibition_center = "Exhibition Center"
    exhibition_hall = "Exhibition Hall"
    trade_fair_center = "Trade Fair Center"
    gallery = "Gallery"
    museum = "Museum"
    studio = "Studio"
    recording_studio = "Recording Studio"
    photography_studio = "Photography Studio"
    art_gallery = "Art Gallery"
    makerspace = "Makerspace"
    private_residence = "Private Residence"
    villa = "Villa"
    mansion = "Mansion"
    apartment = "Apartment"
    vacation_home = "Vacation Home"
    spa = "Spa"
    wellness_center = "Wellness Center"
    yoga_studio = "Yoga Studio"
    fitness_center = "Fitness Center"
    aquarium = "Aquarium"
    zoo = "Zoo"
    historic_building = "Historic Building"
    castle = "Castle"
    lighthouse = "Lighthouse"
    ship_or_yacht = "Ship or Yacht"
    cruise_boat = "Cruise Boat"
    hangar = "Hangar"
    warehouse = "Warehouse"
    vineyard = "Vineyard"


class VenueStatus(str, PyEnum):
    """Operational status of a venue."""

    available = "available"
    reserved = "reserved"
    booked = "booked"
    under_maintenance = "under_maintenance"
    closed = "closed"


def _enum_values(enum_class):
    """Return the member values of an enum for SQLAlchemy ``Enum`` storage.

    Args:
        enum_class: A ``str``-based enum class.

    Returns:
        list[str]: The raw string values of the enum members.
    """
    return [member.value for member in enum_class]


class Venue(TimestampMixin, Base):
    """A bookable venue owned by a venue manager."""

    __tablename__ = "venues"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    address: Mapped[str] = mapped_column(String(255), nullable=False)
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    state: Mapped[str] = mapped_column(String(100), nullable=False)
    country: Mapped[str] = mapped_column(String(100), nullable=False)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    purpose: Mapped[VenuePurpose] = mapped_column(
        Enum(VenuePurpose, values_callable=_enum_values), nullable=False
    )
    venue_type: Mapped[VenueType] = mapped_column(
        Enum(VenueType, values_callable=_enum_values), nullable=False
    )
    amenities: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    accessibility: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    contact: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    website: Mapped[str | None] = mapped_column(String(255), nullable=True, default=None)
    rental_price: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[VenueStatus] = mapped_column(
        Enum(VenueStatus, values_callable=_enum_values),
        nullable=False,
        default=VenueStatus.available,
        server_default="available",
    )
    images: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    parking_availability: Mapped[dict] = mapped_column(
        JSON, nullable=False, default=dict
    )
    operating_hours: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    venue_manager_id: Mapped[int] = mapped_column(
        ForeignKey("venue_managers.id"), nullable=False, index=True
    )

    venue_manager: Mapped[VenueManager] = relationship(back_populates="venues")

    events: Mapped[list["Event"]] = relationship(
        back_populates="venue", passive_deletes=True
    )


class EventStatus(str, PyEnum):
    """Lifecycle status of a proposed event."""

    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class Event(TimestampMixin, Base):
    """An event proposed by a customer for a target venue."""

    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    proposed_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    target_venue_id: Mapped[int] = mapped_column(
        ForeignKey("venues.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[EventStatus] = mapped_column(
        Enum(EventStatus, values_callable=_enum_values),
        nullable=False,
        default=EventStatus.pending,
        server_default="pending",
    )
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id"), nullable=False, index=True
    )
    vote_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )

    venue: Mapped[Venue] = relationship(back_populates="events")
    customer: Mapped[Customer] = relationship(back_populates="events")
    votes: Mapped[list["Vote"]] = relationship(
        back_populates="event", cascade="all, delete-orphan"
    )


class VoteStatus(str, PyEnum):
    """Ballot status of a vote."""

    ballot_open = "ballot_open"
    ballot_close = "ballot_close"


class Vote(Base):
    """A single vote cast by a customer on a pending event."""

    __tablename__ = "votes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[int] = mapped_column(
        ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True
    )
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id"), nullable=False, index=True
    )
    status: Mapped[VoteStatus] = mapped_column(
        Enum(VoteStatus, values_callable=_enum_values),
        nullable=False,
        default=VoteStatus.ballot_open,
        server_default="ballot_open",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    event: Mapped[Event] = relationship(back_populates="votes")
    customer: Mapped[Customer] = relationship(back_populates="votes")
