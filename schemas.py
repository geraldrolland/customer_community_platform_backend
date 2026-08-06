from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, HttpUrl, model_validator

from models import EventStatus, VenuePurpose, VenueStatus, VenueType, VoteStatus


Amenities = [
    "Wi-Fi",
    "Audio/Visual Equipment",
    "Stage",
    "Lighting",
    "Heating/Cooling",
    "Restrooms",
    "Catering Services",
    "Bar Services",
    "Kitchen Facilities",
    "Outdoor Space",
    "Parking",
]

VenuePurposeMapping = {
    "Corporate and Business": [
        "Conference Center",
        "Convention Center",
        "Meeting Room",
        "Boardroom",
        "Training Room",
        "Seminar Hall",
        "Business Center",
        "Coworking Space",
    ],
    "Weddings and Celebration": [
        "Banquet Hall",
        "Ballroom",
        "Wedding Hall",
        "Reception Hall",
        "Garden",
        "Chapel",
        "Event Center",
    ],
    "Entertainment": [
        "Theater",
        "Cinema",
        "Concert Hall",
        "Opera House",
        "Comedy Club",
        "Nightclub",
        "Casino",
    ],
    "Sport": [
        "Stadium", 
        "Arena", 
        "Sports Complex",
        "Gymnasium",
        "Indoor Sports Hall",
        "Tennis Court",
        "Golf Club",
        "Swimming Pool",
        ],
    "Outdoor": [
        "Park",
        "Beach",
        "Rooftop",
        "Botanical Garden",
        "Farm",
        "Ranch",
        "Campground",
        "Open Field",
        "Amphitheater",
        ],
    "Hospitality": [
        "Hotel",
        "Resort",
        "Restaurant",
        "Cafe",
        "Bar",
        "Lounge",
        "Winery",
        "Brewery",
    ],
    "Educational": [
        "University Auditorium",
        "School Hall",
        "Lecture Hall",
        "Library",
        "Classroom",
    ],
    "Religion": [
        "Church",
        "Mosque",
        "Temple",
        "Synagogue",
        "Community Worship Hall",
    ],
    "Community and Government": [
        "Community Center",
        "Civic Center",
        "Town Hall",
        "Cultural Center",
        "Exhibition Center",
    ],
    "Exhibition and Trade": [
        "Exhibition Hall",
        "Trade Fair Center",
        "Gallery",
        "Museum",
    ],
    "Creative and Media": [
        "Studio",
        "Recording Studio",
        "Photography Studio",
        "Art Gallery",
        "Makerspace",
    ],
    "Private": [
        "Private Residence",
        "Villa",
        "Mansion",
        "Apartment",
        "Vacation Home",
    ],
    "Health and Wellness": [
        "Spa",
        "Wellness Center",
        "Yoga Studio",
        "Fitness Center",
    ],
    "Unique Venues": [
        "Aquarium",
        "Zoo",
        "Historic Building",
        "Castle",
        "Lighthouse",
        "Ship or Yacht",
        "Cruise Boat",
        "Hangar",
        "Warehouse",
        "Vineyard",
    ]
}

_venue_purpose_values = {purpose.value for purpose in VenuePurpose}
_venue_type_values = {venue_type.value for venue_type in VenueType}

for _purpose, _venue_types in VenuePurposeMapping.items():
    assert (
        _purpose in _venue_purpose_values
    ), f"Unknown purpose in mapping: {_purpose}"
    for _venue_type in _venue_types:
        assert (
            _venue_type in _venue_type_values
        ), f"Unknown venue type '{_venue_type}' under purpose '{_purpose}'"


class CustomerBase(BaseModel):
    first_name: str
    middle_name: str | None = None
    last_name: str
    email: EmailStr


class CustomerCreate(CustomerBase):
    password: str
    confirm_password: str

    @model_validator(mode="after")
    def check_passwords_match(self):
        if self.password != self.confirm_password:
            raise ValueError("Passwords do not match")
        return self


class CustomerOut(CustomerBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    is_email_verified: bool
    role: str
    created_at: datetime
    updated_at: datetime


class VenueManagerBase(BaseModel):
    first_name: str
    middle_name: str | None = None
    last_name: str
    email: EmailStr


class VenueManagerCreate(VenueManagerBase):
    password: str
    confirm_password: str

    @model_validator(mode="after")
    def check_passwords_match(self):
        if self.password != self.confirm_password:
            raise ValueError("Passwords do not match")
        return self


class VenueManagerOut(VenueManagerBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    is_email_verified: bool
    role: str
    created_at: datetime
    updated_at: datetime


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: str


class UpdateProfileRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    first_name: str | None = None
    middle_name: str | None = None
    last_name: str | None = None
    password: str | None = None
    confirm_password: str | None = None

    @model_validator(mode="after")
    def check_password_fields(self):
        if self.password is not None and self.confirm_password is None:
            raise ValueError(
                "confirm_password must be provided when password is provided"
            )
        if self.confirm_password is not None and self.password is None:
            raise ValueError(
                "password must be provided when confirm_password is provided"
            )
        if self.password is not None and self.password != self.confirm_password:
            raise ValueError("Passwords do not match")
        return self




class Accessibilty(BaseModel):
    model_config = ConfigDict(extra="forbid")
    wheel_chair_accessible: bool
    elevator: bool

class Contact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    phone: str
    email: EmailStr

class ParkingAvailability(BaseModel):
    model_config = ConfigDict(extra="forbid")
    available: bool
    capacity: int | None = None
    price: int | None = None
    hours: str | None = None

    @model_validator(mode="after")
    def check_parking_fields(self):
        if self.available is False and  any([self.capacity, self.price, self.hours]):
            raise ValueError(
                "capacity, price, and hours must be None when available is False"
            )

        if self.available is True and not all([self.capacity, self.price, self.hours]):
            raise ValueError(
                "capacity, price, and hours must be provided when available is True"
            )
        return self


class OperatingHours(BaseModel):
    model_config = ConfigDict(extra="forbid")
    days: list[str]
    opening_time: str
    closing_time: str
    
class VenueCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    description: str | None = None
    address: str
    city: str
    state: str
    country: str
    capacity: int
    purpose: VenuePurpose
    venue_type: VenueType
    amenities: list[str]
    accessibility: Accessibilty
    contact: Contact
    website: HttpUrl | None = None
    rental_price: int = Field(gt=0)
    status: VenueStatus = VenueStatus.available
    images: list[HttpUrl]
    parking_availability: ParkingAvailability = ParkingAvailability(available=False)
    operating_hours: OperatingHours

    @model_validator(mode="after")
    def check_amenities(self):
        for amenity in self.amenities:
            if amenity not in Amenities:
                raise ValueError(f"Invalid amenity: {amenity}")
        return self

    @model_validator(mode="after")
    def check_image_urls(self):
        if len(self.images) < 3:
            raise ValueError("At least 3 images are required")
        if len(self.images) > 5:
            raise ValueError("No more than 5 images are allowed")
        return self

    @model_validator(mode="after")
    def check_purpose_and_venue_type(self):
        purpose = self.purpose
        venue_type = self.venue_type

        if purpose and venue_type:
            valid_venue_types = VenuePurposeMapping.get(purpose.value, [])
            if venue_type.value not in valid_venue_types:
                raise ValueError(
                    f"Invalid venue type '{venue_type.value}' for purpose '{purpose.value}'. "
                    f"Valid types are: {valid_venue_types}"
                )
        return self


class VenueUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    
    name: str | None = None
    description: str | None = None
    address: str | None = None
    city: str | None = None
    state: str | None = None
    country: str | None = None
    capacity: int | None = None
    purpose: VenuePurpose | None = None
    venue_type: VenueType | None = None
    amenities: list[str] | None = None
    accessibility: Accessibilty | None = None
    contact: Contact | None = None
    website: HttpUrl | None = None
    rental_price: int | None = None
    status: VenueStatus | None = None
    images: list[HttpUrl] | None = None
    parking_availability: ParkingAvailability | None = None
    operating_hours: OperatingHours | None = None

    @model_validator(mode="after")
    def check_amenities(self):
        if self.amenities is not None:
            for amenity in self.amenities:
                if amenity not in Amenities:
                    raise ValueError(f"Invalid amenity: {amenity}")
        return self

    @model_validator(mode="after")
    def check_image_urls(self):
        if self.images is not None:
            if len(self.images) < 3:
                raise ValueError("At least 3 images are required")
            if len(self.images) > 5:
                raise ValueError("No more than 5 images are allowed")
        return self

    @model_validator(mode="after")
    def check_purpose_and_venue_type(self):
        purpose = self.purpose
        venue_type = self.venue_type

        if purpose is not None and venue_type is None:
            raise ValueError("venue_type must be provided when purpose is provided")
        if venue_type is not None and purpose is None:
            raise ValueError("purpose must be provided when venue_type is provided")
        
        if purpose and venue_type:
            valid_venue_types = VenuePurposeMapping.get(purpose.value, [])
            if venue_type.value not in valid_venue_types:
                raise ValueError(
                    f"Invalid venue type '{venue_type.value}' for purpose '{purpose.value}'. "
                    f"Valid types are: {valid_venue_types}"
                )
        return self


class VenueOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None
    address: str
    city: str
    state: str
    country: str
    capacity: int
    purpose: VenuePurpose
    venue_type: VenueType
    amenities: list[str]
    accessibility: Accessibilty
    contact: Contact
    website: HttpUrl | None
    rental_price: int
    status: VenueStatus
    images: list[HttpUrl]
    parking_availability: ParkingAvailability
    operating_hours: OperatingHours
    venue_manager_id: int
    created_at: datetime
    updated_at: datetime


class EventCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    description: str | None = None
    proposed_date: datetime
    target_venue_id: int
    status: EventStatus = EventStatus.pending


class EventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str | None
    proposed_date: datetime
    target_venue_id: int
    status: EventStatus
    customer_id: int
    vote_count: int
    created_at: datetime
    updated_at: datetime


class VoteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    event_title: str
    status: VoteStatus
    event_id: int
    created_at: datetime
