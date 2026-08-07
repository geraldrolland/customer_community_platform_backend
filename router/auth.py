"""Authentication endpoints: registration, login, profile management, and
logout.

Login sets the signed ``auth_token`` cookie and the readable ``csrf_token``
cookie used by the CSRF middleware. All session handling is cookie-based.
"""
import secrets
from typing import Union

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    Response,
    status,
)
from sqlalchemy.orm import Session

from core.settings import settings
from database import get_db
from models import Customer, VenueManager
from schemas import (
    CustomerCreate,
    CustomerOut,
    LoginRequest,
    UpdateProfileRequest,
    VenueManagerCreate,
    VenueManagerOut,
)
from security import (
    create_access_token,
    create_auth_token,
    create_csrf_token,
    create_refresh_token,
    hash_password,
    verify_password,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _register_user(
    db: Session,
    model,
    first_name: str,
    middle_name: str | None,
    last_name: str,
    email: str,
    password: str,
):
    """Create a new user account.

    Args:
        db: Database session.
        model: Either ``Customer`` or ``VenueManager``.
        first_name: User's first name.
        middle_name: User's middle name, if any.
        last_name: User's last name.
        email: User's email (normalized to lowercase).
        password: Plaintext password to hash.

    Returns:
        The newly created user row.

    Raises:
        HTTPException: 400 if the email is already registered.
    """
    email = email.lower()
    if db.query(model).filter(model.email == email).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    user = model(
        first_name=first_name,
        middle_name=middle_name,
        last_name=last_name,
        email=email,
        hashed_password=hash_password(password),
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return user


def _set_auth_cookies(response: Response, session_id: str, user):
    """Set the signed auth cookie and the readable CSRF cookie.

    Args:
        response: Response to attach the cookies to.
        session_id: Current server-side session id.
        user: The authenticated user (customer or venue manager).
    """
    access_token = create_access_token(session_id, user.role)
    refresh_token = create_refresh_token(session_id, user.role)
    auth_token = create_auth_token(access_token, refresh_token)
    csrf_token = create_csrf_token()

    response.set_cookie(
        key=settings.AUTH_TOKEN_COOKIE,
        value=auth_token,
        httponly=True,
        samesite="lax",
        secure=False,
        path="/",
    )
    response.set_cookie(
        key=settings.CSRF_TOKEN_COOKIE,
        value=csrf_token,
        httponly=False,
        samesite="lax",
        secure=False,
        path="/",
    )


def _login_user(
    db: Session,
    response: Response,
    model,
    email: str,
    password: str,
):
    """Authenticate a user and set the session cookies.

    Args:
        db: Database session.
        response: Response to attach the auth cookies to.
        model: Either ``Customer`` or ``VenueManager``.
        email: User's email.
        password: Plaintext password.

    Returns:
        The authenticated user row.

    Raises:
        HTTPException: 400 on unknown email or wrong password.
    """
    email = email.lower()
    user = db.query(model).filter(model.email == email).first()
    if not user:
        other_model = VenueManager if model is Customer else Customer
        requested_role = "customer" if model is Customer else "venue manager"
        other_role = "venue manager" if model is Customer else "customer"
        if db.query(other_model).filter(other_model.email == email).first():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"No {requested_role} account exists for this email — it "
                    f"belongs to a {other_role} account; use the {other_role} "
                    "login instead"
                ),
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email not found",
        )

    if not verify_password(password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect password",
        )

    user.session_id = secrets.token_urlsafe(32)
    db.commit()

    _set_auth_cookies(response, user.session_id, user)

    return user


@router.post(
    "/register/customer",
    status_code=status.HTTP_201_CREATED,
    response_model=CustomerOut,
)
def register_customer(
    payload: CustomerCreate,
    db: Session = Depends(get_db),
):
    """Register a new customer account.

    Args:
        payload: Customer registration data.
        db: Database session.

    Returns:
        CustomerOut: The created customer.

    Raises:
        HTTPException: 400 if the email is already registered.
    """
    return _register_user(
        db,
        Customer,
        payload.first_name,
        payload.middle_name,
        payload.last_name,
        payload.email,
        payload.password,
    )


@router.post(
    "/register/venue-manager",
    status_code=status.HTTP_201_CREATED,
    response_model=VenueManagerOut,
)
def register_venue_manager(
    payload: VenueManagerCreate,
    db: Session = Depends(get_db),
):
    """Register a new venue-manager account.

    Args:
        payload: Venue-manager registration data.
        db: Database session.

    Returns:
        VenueManagerOut: The created venue manager.

    Raises:
        HTTPException: 400 if the email is already registered.
    """
    return _register_user(
        db,
        VenueManager,
        payload.first_name,
        payload.middle_name,
        payload.last_name,
        payload.email,
        payload.password,
    )


@router.post(
    "/login/customer",
    status_code=status.HTTP_200_OK,
    response_model=CustomerOut,
)
def login_customer(
    payload: LoginRequest,
    response: Response,
    db: Session = Depends(get_db),
):
    """Log in a customer and set the auth + CSRF cookies.

    Args:
        payload: Login credentials.
        response: Response receiving the session cookies.
        db: Database session.

    Returns:
        CustomerOut: The authenticated customer.
    """
    return _login_user(
        db, response, Customer, payload.email, payload.password
    )


@router.post(
    "/login/venue-manager",
    status_code=status.HTTP_200_OK,
    response_model=VenueManagerOut,
)
def login_venue_manager(
    payload: LoginRequest,
    response: Response,
    db: Session = Depends(get_db),
):
    """Log in a venue manager and set the auth + CSRF cookies.

    Args:
        payload: Login credentials.
        response: Response receiving the session cookies.
        db: Database session.

    Returns:
        VenueManagerOut: The authenticated venue manager.
    """
    return _login_user(
        db,
        response,
        VenueManager,
        payload.email,
        payload.password,
    )


@router.get("/me", response_model=Union[CustomerOut, VenueManagerOut])
def me(request: Request):
    """Return the currently authenticated user's profile.

    Args:
        request: Incoming request with ``auth_user`` set by the middleware.

    Returns:
        CustomerOut | VenueManagerOut: The authenticated user.

    Raises:
        HTTPException: 401 when not authenticated.
    """
    auth_user = getattr(request.state, "auth_user", None)
    if auth_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    return auth_user


@router.patch("/me/update", response_model=Union[CustomerOut, VenueManagerOut])
def update_me(
    payload: UpdateProfileRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Update the authenticated user's profile fields.

    Args:
        payload: Fields to update (all optional).
        request: Incoming request with the authenticated user.
        db: Database session.

    Returns:
        CustomerOut | VenueManagerOut: The updated user.

    Raises:
        HTTPException: 401 when not authenticated; 404 if the user no
            longer exists.
    """
    auth_user = getattr(request.state, "auth_user", None)
    if auth_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    if auth_user.role == "customer":
        user = db.query(Customer).filter(Customer.id == auth_user.id).first()
    else:
        user = db.query(VenueManager).filter(VenueManager.id == auth_user.id).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    if payload.first_name is not None:
        user.first_name = payload.first_name
    if payload.middle_name is not None:
        user.middle_name = payload.middle_name
    if payload.last_name is not None:
        user.last_name = payload.last_name
    if payload.password is not None:
        user.hashed_password = hash_password(payload.password)

    db.commit()
    db.refresh(user)

    return user


@router.post("/logout", status_code=status.HTTP_200_OK)
def logout(request: Request, db: Session = Depends(get_db)):
    """Log out the authenticated user and clear the session cookies.

    Invalidates the server-side session id and expires both the auth and
    CSRF cookies.

    Args:
        request: Incoming request with the authenticated user.
        db: Database session.

    Returns:
        Response: Empty response with cleared cookies.

    Raises:
        HTTPException: 401 when not authenticated.
    """
    auth_user = getattr(request.state, "auth_user", None)
    if auth_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    if auth_user.role == "customer":
        user = db.query(Customer).filter(Customer.id == auth_user.id).first()
    else:
        user = db.query(VenueManager).filter(VenueManager.id == auth_user.id).first()

    if user:
        user.session_id = None
        db.commit()

    response = Response()
    response.set_cookie(
        settings.AUTH_TOKEN_COOKIE,
        "",
        httponly=True,
        samesite="lax",
        secure=False,
        path="/",
    )
    response.set_cookie(
        settings.CSRF_TOKEN_COOKIE,
        "",
        httponly=True,
        samesite="lax",
        secure=False,
        path="/",
    )

    return response
