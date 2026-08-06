import secrets
from typing import Union

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Request,
    Response,
    status,
)
from sqlalchemy.orm import Session

from config import settings
from database import get_db
from email_service import send_verification_email
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
    create_verification_token,
    decode_token,
    hash_password,
    verify_password,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _register_user(
    db: Session,
    background_tasks: BackgroundTasks,
    model,
    first_name: str,
    middle_name: str | None,
    last_name: str,
    email: str,
    password: str,
):
    email = email.lower()
    if db.query(Customer).filter(Customer.email == email).first() or db.query(
        VenueManager
    ).filter(VenueManager.email == email).first():
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

    token = create_verification_token(user.id, user.role)
    verification_url = f"{settings.EMAIL_VERIFICATION_BASE_URL}?token={token}"
    background_tasks.add_task(
        send_verification_email, email, first_name, verification_url
    )

    return user


def _set_auth_cookies(response: Response, session_id: str, user):
    access_token = create_access_token(session_id, user.id, user.role)
    refresh_token = create_refresh_token(session_id, user.id, user.role)
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
        httponly=True,
        samesite="lax",
        secure=False,
        path="/",
    )


def _login_user(
    db: Session,
    response: Response,
    background_tasks: BackgroundTasks,
    model,
    email: str,
    password: str,
):
    email = email.lower()
    user = db.query(model).filter(model.email == email).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email not found",
        )

    if not verify_password(password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect password",
        )

    if not user.is_email_verified:
        token = create_verification_token(user.id, user.role)
        verification_url = f"{settings.EMAIL_VERIFICATION_BASE_URL}?token={token}"
        background_tasks.add_task(
            send_verification_email, email, user.first_name, verification_url
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email not verified - verification link sent",
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
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    return _register_user(
        db,
        background_tasks,
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
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    return _register_user(
        db,
        background_tasks,
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
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    return _login_user(
        db, response, background_tasks, Customer, payload.email, payload.password
    )


@router.post(
    "/login/venue-manager",
    status_code=status.HTTP_200_OK,
    response_model=VenueManagerOut,
)
def login_venue_manager(
    payload: LoginRequest,
    response: Response,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    return _login_user(
        db,
        response,
        background_tasks,
        VenueManager,
        payload.email,
        payload.password,
    )


@router.get("/verify-email", status_code=status.HTTP_200_OK)
def verify_email(token: str, db: Session = Depends(get_db)):
    try:
        payload = decode_token(token)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid token",
        )

    user_id = int(payload.get("sub"))
    role = payload.get("role")

    if role == "venue_manager":
        user = db.query(VenueManager).filter(VenueManager.id == user_id).first()
    elif role == "customer":
        user = db.query(Customer).filter(Customer.id == user_id).first()
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid token",
        )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    user.is_email_verified = True
    db.commit()

    return {"message": "Email verified successfully"}


@router.get("/me", response_model=Union[CustomerOut, VenueManagerOut])
def me(request: Request):
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
