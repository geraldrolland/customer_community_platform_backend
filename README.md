# HappenHub Backend API

REST API for **HappenHub**, a community event platform where customers
propose events at local venues, venue managers approve or reject them, and
the community votes on pending proposals.

Built with **FastAPI**, **SQLAlchemy**, and **SQLite**, with cookie-based
session authentication, CSRF protection, and an in-memory response cache.

---

## Table of Contents

- [Features](#features)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Prerequisites](#prerequisites)
- [Running Locally with Docker](#running-locally-with-docker)
- [Running Locally Without Docker](#running-locally-without-docker)
- [Environment Variables](#environment-variables)
- [API Overview](#api-overview)
- [Security Model](#security-model)
- [Caching](#caching)
- [Testing](#testing)
- [Docker Production Notes](#docker-production-notes)

---

## Features

- **Role-based accounts** — customers and venue managers
- **Venue management** — venue managers create, update, and delete venues
- **Venue lifecycle** — setting a venue's status to `closed` rejects every
  event assigned to it and closes their ballots
- **Event proposals** — customers propose events at venues (title, date, target venue)
- **Moderation flow** — venue managers approve or reject pending proposals
- **Community voting** — customers vote on pending events; ballots close when an
  event is approved or its date passes
- **Media uploads** — venue managers upload up to 5 images per request
- **Security** — signed HttpOnly session cookies, per-request session rotation,
  double-submit CSRF protection, trusted-host validation, CORS allow-list
- **Performance** — in-memory TTL cache on hot shared read endpoints
- **Observability** — structured per-request logging middleware

---

## Tech Stack

| Layer       | Technology                                  |
|-------------|---------------------------------------------|
| Framework   | FastAPI (Starlette)                         |
| ORM         | SQLAlchemy 2.0 (Mapped-style models)        |
| Database    | SQLite (file-backed, FK enforcement on)     |
| Validation  | Pydantic v2 + pydantic-settings             |
| Auth        | PyJWT (signed cookies via itsdangerous)     |
| Password    | bcrypt                                      |
| Caching     | cachetools (TTLCache)                       |
| Server      | Uvicorn                                     |
| Container   | Docker (python:3.12-slim)                   |

---

## Project Structure

```
backend/
├── core/
│   └── settings.py          # pydantic-settings configuration
├── middleware/
│   ├── auth_middleware.py   # cookie session auth + rotation
│   ├── csrf_middleware.py   # double-submit CSRF check
│   └── request_logger_middleware.py  # per-request logging
├── router/
│   ├── auth.py              # register / login / me / logout
│   ├── venue.py             # venue CRUD + catalog
│   ├── event.py             # event proposals + moderation
│   ├── vote.py              # voting endpoints
│   └── static.py            # image uploads
├── models.py                # SQLAlchemy models + enums
├── schemas.py               # Pydantic request/response schemas
├── security.py              # JWT, cookies, hashing helpers
├── cache.py                 # thread-safe TTL cache helpers
├── database.py              # engine, session factory, Base
├── dependencies.py          # role/permission dependency
├── main.py                  # application entrypoint
├── smoke_test.py            # end-to-end smoke test
├── Dockerfile
├── .env.example             # environment template
└── requirements.txt
```

---

## Prerequisites

- **Docker Desktop** (Docker Engine 24+ recommended) — [download](https://www.docker.com/products/docker-desktop/)
- Docker Desktop must be **running** before building or running the container
- Optional: [Python 3.12](https://www.python.org/downloads/) only needed for the
  non-Docker workflow or the smoke test

---

## Running Locally with Docker

### 1. Configure environment variables

Copy the template and adjust values (safe for local development as-is):

```bash
# PowerShell / cmd
copy .env.example .env

# macOS / Linux
cp .env.example .env
```

> **Windows tip:** if `copy` is not available, run `cp` via PowerShell or edit
> the file in any editor. The `.env` file is gitignored and never committed.

### 2. Build the image

From the `backend/` directory:

```bash
docker build -t happenhub-backend .
```

This installs the Python dependencies and copies the application into the
image. Rebuild anytime you change code:

```bash
docker build -t happenhub-backend .
```

### 3. Run the container

Start the container on port `8000`, passing the environment file and mounting
the SQLite database and media folder so data persists on your machine:

```bash
docker run -d \
  --name happenhub-backend \
  -p 8000:8000 \
  --env-file .env \
  -v "$(pwd)/event_platform.db:/app/event_platform.db" \
  -v "$(pwd)/media:/app/media" \
  happenhub-backend
```

> **Windows PowerShell:** `$(pwd)` works. If you prefer, replace it with the
> absolute path, e.g. `C:\Users\you\project\backend`.

**What each flag does:**

| Flag               | Purpose                                                    |
|--------------------|------------------------------------------------------------|
| `-d`               | Run detached (in the background)                           |
| `--name`           | Container name for easy management                         |
| `-p 8000:8000`     | Expose the API on `http://localhost:8000`                  |
| `--env-file .env`  | Inject environment variables (secrets stay out of the image) |
| `-v ...db`         | Persist the SQLite database on the host                    |
| `-v ...media`      | Persist uploaded images on the host                        |

### 4. Verify it is running

```bash
docker ps                              # STATUS should be "Up"
curl http://localhost:8000/            # -> {"message":"Community Event Platform API"}
```

Open the interactive API docs at **http://localhost:8000/docs**.

### 5. View logs

```bash
docker logs -f happenhub-backend
```

You should see the request-logger lines, e.g.:

```
INFO:middleware.request_logger_middleware:method=GET url_path=/ status=200
```

### 6. Stop / remove the container

```bash
docker stop happenhub-backend      # stop
docker start happenhub-backend     # start it again later
docker rm -f happenhub-backend     # remove (volumes keep your data)
```

### 7. Rebuild after code changes

```bash
docker build -t happenhub-backend .
docker rm -f happenhub-backend
docker run -d --name happenhub-backend -p 8000:8000 --env-file .env \
  -v "$(pwd)/event_platform.db:/app/event_platform.db" \
  -v "$(pwd)/media:/app/media" \
  happenhub-backend
```

---

## Running Locally Without Docker

```bash
cd backend
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env        # optional, defaults are fine for dev

uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

The API is then available at `http://localhost:8000` with live reload.

---

## Environment Variables

All variables are optional — defaults are safe for local development. Settings
are loaded from the environment and an optional `.env` file (see
`core/settings.py`).

> **Note:** list-typed variables use **JSON array syntax** in the environment
> or `.env` file, e.g. `CORS_ORIGINS=["http://localhost:3000"]`.

| Variable                             | Type        | Default                                       | Description                                  |
|--------------------------------------|-------------|-----------------------------------------------|----------------------------------------------|
| `APP_NAME`                           | string      | `HappenHub`                                   | FastAPI application title (shown in `/docs`) |
| `COOKIE_SIGNING_SECRET`              | string      | defaults to `JWT_SECRET`                      | Signs the auth cookie value                  |
| `ACCESS_TOKEN_EXPIRE_MINUTES`        | int         | `7`                                           | Access-token lifetime (minutes)              |
| `REFRESH_TOKEN_EXPIRE_DAYS`          | int         | `7`                                           | Refresh-token lifetime (days)                |
| `AUTH_TOKEN_COOKIE`                  | string      | `auth_token`                                  | Name of the signed session cookie            |
| `CSRF_TOKEN_COOKIE`                  | string      | `csrf_token`                                  | Name of the CSRF cookie                      |
| `CORS_ORIGINS`                       | JSON array  | `["http://localhost:3000"]`                   | Allowed browser origins (credentials mode)   |
| `TRUSTED_HOSTS`                      | JSON array  | `["localhost","127.0.0.1","testserver"]`      | Allowed `Host` headers (`testserver` needed for FastAPI TestClient) |

---

## API Overview

Base URL: `http://localhost:8000` — interactive docs at `/docs`.

### Authentication flow

1. `POST /api/auth/register/customer` or `POST /api/auth/register/venue-manager` → 201
2. `POST /api/auth/login/customer` or `POST /api/auth/login/venue-manager` → 200
   (sets the `auth_token` and `csrf_token` cookies)
3. Use the session cookie automatically; send `x-csrf-token` header on writes

### Endpoints

| Method | Path                        | Role         | Description                          |
|--------|-----------------------------|--------------|--------------------------------------|
| POST   | `/api/auth/register/customer` | public       | Register a customer                 |
| POST   | `/api/auth/register/venue-manager` | public | Register a venue manager           |
| POST   | `/api/auth/login/customer`  | public       | Customer login (sets cookies)        |
| POST   | `/api/auth/login/venue-manager` | public    | Venue-manager login (sets cookies)   |
| GET    | `/api/auth/me`              | authenticated| Current user profile                 |
| PATCH  | `/api/auth/me/update`       | authenticated| Update own profile                   |
| POST   | `/api/auth/logout`          | authenticated| Log out and clear cookies            |
| POST   | `/api/media/upload`         | venue_manager | Upload up to 5 images                |
| POST   | `/api/venue/create`         | venue_manager | Create a venue                       |
| GET    | `/api/venue/me/all`         | venue_manager | List own venues                      |
| GET    | `/api/venue/me/{id}`        | venue_manager | Fetch own venue                      |
| PATCH  | `/api/venue/{id}`           | venue_manager | Update own venue; setting status to `closed` rejects all its events |
| DELETE | `/api/venue/{id}`           | venue_manager | Delete own venue                     |
| GET    | `/api/venue/all`            | customer      | Browse venue catalog                 |
| GET    | `/api/venue/{id}`           | customer      | Fetch a venue                        |
| POST   | `/api/event/create`         | customer      | Propose an event                     |
| GET    | `/api/event/me/all`         | customer      | List own events                      |
| PATCH  | `/api/event/{id}`           | customer      | Update pending event                 |
| DELETE | `/api/event/{id}`           | customer      | Delete pending event                 |
| GET    | `/api/event/{id}`           | customer      | Fetch an event                       |
| GET    | `/api/event/all/upcoming`   | customer      | Approved events from today onward    |
| GET    | `/api/event/all/pending`    | customer      | Pending future events                |
| GET    | `/api/event/status`         | venue_manager | List venue events by status          |
| PATCH  | `/api/event/{id}/status`    | venue_manager | Approve/reject pending event         |
| POST   | `/api/vote/cast`            | customer      | Vote on a pending event              |
| GET    | `/api/vote/me/all`          | customer      | List own votes                       |
| GET    | `/api/vote/{id}`            | customer      | Fetch own vote                       |
| DELETE | `/api/vote/{id}`            | customer      | Delete open vote                     |

All state-changing endpoints under `/api/venue`, `/api/event`, `/api/vote`,
`/api/auth/me` and `/api/media` require the `x-csrf-token` header matching the
`csrf_token` cookie.

---

## Security Model

Middleware chain (outermost first):

```
TrustedHostMiddleware  ->  CORSMiddleware  ->  AuthMiddleware  ->  CsrfMiddleware  ->  app
```

1. **TrustedHost** — rejects requests with a `Host` header outside
   `TRUSTED_HOSTS` (400).
2. **CORS** — allows only `CORS_ORIGINS` with credentials (cookies are used).
3. **Auth** — validates the signed `auth_token` cookie on protected routes,
   binds `request.state.auth_user`, verifies the server-side `session_id`, and
   **rotates the session + cookie on every request** (stolen cookies expire
   quickly). Invalid sessions are cleared and rejected (401).
4. **CSRF** — on protected write requests, the `x-csrf-token` header must equal
   the `csrf_token` cookie (constant-time comparison, 403 otherwise). The CSRF
   cookie is readable by JavaScript (`httponly=False`) so the client can echo
   it into the header.
5. **RequestLogger** — logs `method`, `url_path`, and `status` for every request.

Passwords are hashed with bcrypt; JWTs are signed with `JWT_SECRET`; the auth
cookie payload is additionally signed with `COOKIE_SIGNING_SECRET`.

---

## Caching

Hot shared read endpoints are cached in-process with a **60-second TTL**
(`cache.py`, backed by `cachetools`):

- `GET /api/event/all/upcoming`, `GET /api/event/all/pending`, `GET /api/event/{id}`
- `GET /api/venue/all`, `GET /api/venue/{id}`

Every event/venue/vote **write** invalidates the matching cache prefix, so
data is never stale after a mutation. Cached values are serialized Pydantic
payloads, never ORM objects.

> **Note:** the cache is per-process. With multiple uvicorn workers or
> replicas, each instance holds its own cache — fine for local development;
> use a shared store (e.g. Redis) at larger scale.

---

## Testing

An end-to-end smoke test walks the full user journey (register →
login → venue → event → vote → approve → negative cases).

Requires the backend to be running (Docker container or local uvicorn) and the
`requests` package in your Python environment:

```bash
# from the backend/ directory, with the container running:
pip install requests
python smoke_test.py
```

Expected output ends with `42/42 checks passed` (exit code 0).

---

## Docker Production Notes

- **Secrets**: never bake `.env` into the image (it is in `.dockerignore`).
  Inject at runtime with `--env-file` or your orchestrator's secrets store.
- **JWT_SECRET**: always override the dev default outside local development.
- **Persistent data**: SQLite and media are bind-mounted in the instructions
  above; in production prefer named volumes or a managed database.
- **Cookies over HTTPS**: set `secure=True` on cookies behind a TLS reverse
  proxy (currently `secure=False` for local HTTP).
- **Workers**: the in-memory cache and per-request session rotation assume a
  single process; scale the app with a shared cache/session store.
- **Health check**: `GET /` is the simplest readiness probe.
