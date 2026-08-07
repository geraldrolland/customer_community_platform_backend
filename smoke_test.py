"""End-to-end smoke test for the HappenHub API.

Requires a running backend (local uvicorn or the Docker container) on
``http://127.0.0.1:8000``. Registers fresh users with timestamped
emails, walks the full customer/venue-manager workflows, and asserts the
expected status code for every endpoint, including the middleware
negative cases (401/403/400).

Usage:
    python smoke_test.py
"""
import sys
import time
from datetime import datetime, timedelta, timezone

import requests

BASE = "http://127.0.0.1:8000"
TS = int(time.time())
PASSWORD = "SmokePass!123"
PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
    b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)

results = []


def check(name: str, ok: bool, extra: str = ""):
    """Record and print the result of a single check.

    Args:
        name: Human-readable check description.
        ok: Whether the check passed.
        extra: Optional detail appended to the output line.
    """
    results.append((name, ok))
    status = "PASS" if ok else "FAIL"
    print(f"[{status}] {name}{' - ' + extra if extra else ''}")


class Client:
    """HTTP client wrapper with automatic CSRF header injection.

    Maintains a cookie jar (so the rotated ``auth_token`` cookie stays in
    sync) and attaches the ``x-csrf-token`` header, read from the
    ``csrf_token`` cookie, to every state-changing request.
    """

    def __init__(self):
        """Initialize an empty session and CSRF token placeholder."""
        self.session = requests.Session()
        self.csrf_token = None

    def request(self, method: str, path: str, expected: int, **kwargs):
        """Send a request, inject CSRF header, and assert the status code.

        Args:
            method: HTTP method.
            path: API path (appended to ``BASE``).
            expected: Expected status code.
            **kwargs: Extra arguments forwarded to ``requests``.

        Returns:
            requests.Response: The server response.
        """
        headers = dict(kwargs.pop("headers", {}))
        if method in ("POST", "PATCH", "PUT", "DELETE"):
            headers["x-csrf-token"] = self.csrf_token or ""
        url = path if path.startswith("http") else BASE + path
        resp = self.session.request(
            method, url, headers=headers, timeout=15, **kwargs
        )
        if self.csrf_token is None:
            self.csrf_token = self.session.cookies.get("csrf_token")
        ok = resp.status_code == expected
        check(f"{method} {path}", ok, f"got {resp.status_code}, want {expected}")
        return resp

    def post(self, path, expected=200, **kw):
        """Send a POST request through :meth:`request`."""
        return self.request("POST", path, expected, **kw)

    def get(self, path, expected=200, **kw):
        """Send a GET request through :meth:`request`."""
        return self.request("GET", path, expected, **kw)

    def patch(self, path, expected=200, **kw):
        """Send a PATCH request through :meth:`request`."""
        return self.request("PATCH", path, expected, **kw)

    def delete(self, path, expected=200, **kw):
        """Send a DELETE request through :meth:`request`."""
        return self.request("DELETE", path, expected, **kw)


def future_iso(days: int = 30) -> str:
    """Return an ISO datetime ``days`` in the future.

    Args:
        days: Days ahead (default 30).

    Returns:
        str: ISO-8601 timestamp.
    """
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()


def main():
    """Run the full smoke-test flow and return the process exit code.

    Returns:
        int: 0 when every check passes, otherwise 1.
    """
    anon = Client()
    customer = Client()
    manager = Client()

    customer_email = f"smoke_customer_{TS}@test.com"
    manager_email = f"smoke_manager_{TS}@test.com"

    anon.get("/", 200)

    reg_cust = anon.post(
        "/api/auth/register/customer",
        201,
        json={
            "first_name": "Smoke",
            "last_name": "Customer",
            "email": customer_email,
            "password": PASSWORD,
            "confirm_password": PASSWORD,
        },
    )

    reg_mgr = anon.post(
        "/api/auth/register/venue-manager",
        201,
        json={
            "first_name": "Smoke",
            "last_name": "Manager",
            "email": manager_email,
            "password": PASSWORD,
            "confirm_password": PASSWORD,
        },
    )

    anon.post(
        "/api/auth/login/customer",
        200,
        json={"email": customer_email, "password": PASSWORD},
    )
    anon.post(
        "/api/auth/login/venue-manager",
        200,
        json={"email": manager_email, "password": PASSWORD},
    )
    customer.post(
        "/api/auth/login/customer",
        200,
        json={"email": customer_email, "password": PASSWORD},
    )
    manager.post(
        "/api/auth/login/venue-manager",
        200,
        json={"email": manager_email, "password": PASSWORD},
    )

    customer.get("/api/auth/me", 200)
    customer.patch("/api/auth/me/update", 200, json={"first_name": "Smokey"})

    upload = manager.post(
        "/api/media/upload",
        200,
        files=[("images", ("smoke.png", PNG_BYTES, "image/png"))],
    )
    media_url = upload.json()[0]
    anon.get(media_url, 200)

    venue_payload = {
        "name": "Smoke Theater",
        "description": "Smoke test venue",
        "address": "1 Main St",
        "city": "Test City",
        "state": "Test State",
        "country": "Test Country",
        "capacity": 200,
        "purpose": "Entertainment",
        "venue_type": "Theater",
        "amenities": ["Wi-Fi", "Parking"],
        "accessibility": {"wheel_chair_accessible": True, "elevator": False},
        "contact": {"name": "Jane", "phone": "1234567890", "email": "jane@test.com"},
        "website": "https://example.com",
        "rental_price": 5000,
        "status": "available",
        "images": [
            "https://example.com/1.png",
            "https://example.com/2.png",
            "https://example.com/3.png",
        ],
        "parking_availability": {"available": False},
        "operating_hours": {
            "days": ["Monday"],
            "opening_time": "09:00",
            "closing_time": "17:00",
        },
    }
    venue_a = manager.post("/api/venue/create", 201, json=venue_payload)
    venue_a_id = venue_a.json()["id"]

    manager.get("/api/venue/me/all", 200)
    manager.get(f"/api/venue/me/{venue_a_id}", 200)
    manager.patch(
        f"/api/venue/{venue_a_id}", 200, json={"description": "Updated venue"}
    )

    venue_b = manager.post(
        "/api/venue/create", 201, json={**venue_payload, "name": "Smoke Venue B"}
    )
    venue_b_id = venue_b.json()["id"]
    manager.patch(f"/api/venue/{venue_b_id}", 200, json={"status": "closed"})
    manager.delete(f"/api/venue/{venue_b_id}", 200)

    customer.get("/api/venue/all", 200)
    customer.get(f"/api/venue/{venue_a_id}", 200)

    event_payload = {
        "title": "Smoke Festival",
        "description": "Smoke test event",
        "proposed_date": future_iso(30),
        "target_venue_id": venue_a_id,
    }
    event_1 = customer.post("/api/event/create", 201, json=event_payload)
    event_1_id = event_1.json()["id"]

    customer.get("/api/event/me/all", 200)
    customer.get(f"/api/event/{event_1_id}", 200)
    customer.patch(
        f"/api/event/{event_1_id}", 200, json={"title": "Smoke Festival v2"}
    )

    vote_1 = customer.post(f"/api/vote/cast?event_id={event_1_id}", 201)
    vote_1_id = vote_1.json()["id"]
    customer.get("/api/vote/me/all", 200)
    customer.get(f"/api/vote/{vote_1_id}", 200)
    customer.delete(f"/api/vote/{vote_1_id}", 200)
    customer.post(f"/api/vote/cast?event_id={event_1_id}", 201)

    event_2 = customer.post(
        "/api/event/create", 201, json={**event_payload, "title": "Smoke Event B"}
    )
    event_2_id = event_2.json()["id"]
    customer.delete(f"/api/event/{event_2_id}", 200)

    manager.get(f"/api/event/status?venue_id={venue_a_id}&status=pending", 200)
    manager.patch(f"/api/event/{event_1_id}/status?status=approved", 200)

    pending_resp = customer.get("/api/event/all/pending", 200)
    upcoming_resp = customer.get("/api/event/all/upcoming", 200)
    pending_ids = [e["id"] for e in pending_resp.json()]
    upcoming_ids = [e["id"] for e in upcoming_resp.json()]
    check(
        "event moved out of pending list",
        event_1_id not in pending_ids,
        f"event {event_1_id} in pending: {event_1_id in pending_ids}",
    )
    check(
        "event present in upcoming list",
        event_1_id in upcoming_ids,
        f"event {event_1_id} in upcoming: {event_1_id in upcoming_ids}",
    )

    anon.get("/api/auth/me", 401)

    customer.request("POST", "/api/venue/create", 403, json=venue_payload)
    customer.request(
        "POST",
        "/api/venue/create",
        403,
        json=venue_payload,
        headers={"x-csrf-token": "wrong-token"},
    )

    evil = requests.get(
        BASE + "/", headers={"Host": "evil.com"}, timeout=15
    )
    check("GET / with evil Host", evil.status_code == 400, f"got {evil.status_code}")

    customer.post("/api/auth/logout", 200)

    passed = sum(1 for _, ok in results if ok)
    total = len(results)
    print(f"\n{passed}/{total} checks passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
