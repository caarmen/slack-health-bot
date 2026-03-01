"""
Tests for the SQLAdmin integration.

The purpose isn't to test the SQLAdmin package, but rather to test that
we have correctly configured it.
"""

import re

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from slackhealthbot.admin.hash_password import main as hash_password_main
from slackhealthbot.main import app, lifespan
from slackhealthbot.settings import Settings


@pytest.mark.asyncio
async def test_admin_access_integration_test(
    capsys: pytest.CaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
    settings: Settings,
    client: TestClient,
):
    """
    Integration test for accessing admin pages.

    Given a configured admin password
    And an unauthenticated user
    When the user logs in with the correct username and password
    Then authentication succeeds

    ---

    When the user accesses the admin pages
    Then access to the admin pages is granted.

    ---

    When the user logs out
    And tries to access the admin pages
    Then they are redirected to the login page.
    """
    # Given a configured admin password
    monkeypatch.setattr(
        "slackhealthbot.admin.hash_password.getpass", lambda _: "azerty"
    )
    cmd_status = hash_password_main()
    assert cmd_status == 0
    captured = capsys.readouterr()
    password_hash = re.search("\$pbkdf2.*$", captured.out).group(0)
    settings.secret_settings.admin_password_hash = password_hash

    # And an unauthenticated user

    # When the user logs in with the correct username and password
    async with lifespan(app):
        response = client.post(
            "/admin/login",
            data={
                "username": "admin",
                "password": "azerty",
            },
        )
    assert response.status_code == status.HTTP_200_OK

    # When the user accesses the admin pages
    for list_page in (
        "user",
        "withings-user",
        "fitbit-user",
        "fitbit-activity",
        "fitbit-daily-activity",
    ):
        response = client.get(
            f"/admin/{list_page}/list",
            follow_redirects=False,
        )
        # Then access to the admin pages is granted.
        assert response.status_code == status.HTTP_200_OK

    # When the user logs out
    response = client.get("/admin/logout")
    # And tries to access the admin pages
    for list_page in (
        "user",
        "withings-user",
        "fitbit-user",
        "fitbit-activity",
        "fitbit-daily-activity",
    ):
        # Then they are redirected to the login page.
        response = client.get(
            f"/admin/{list_page}/list",
            follow_redirects=False,
        )
        assert response.status_code == status.HTTP_302_FOUND
        assert response.next_request.url.path == "/admin/login"


def test_generate_password_passwords_dont_match(
    capsys: pytest.CaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
):
    """
    Given a user
    When the user uses the hash password script, providing two different passwords
    Then the script fails.
    """
    # Given a user
    # When the user uses the hash password script, providing two different passwords
    getpass_input = iter(["azerty", "qsqfg"])
    monkeypatch.setattr(
        "slackhealthbot.admin.hash_password.getpass", lambda _: next(getpass_input)
    )

    # Then the script fails.
    cmd_status = hash_password_main()
    assert cmd_status == 1
    captured_err = capsys.readouterr().err
    assert captured_err.strip() == "Passwords do not match!"


@pytest.mark.asyncio
async def test_login_wrong_password(
    capsys: pytest.CaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
    settings: Settings,
    client: TestClient,
):
    """
    Given a configured admin password
    And a user
    When the user logs in with the wrong username and password
    And tries to access the admin pages
    Then they are redirected to the login page.
    """
    # Given a configured admin password
    monkeypatch.setattr(
        "slackhealthbot.admin.hash_password.getpass", lambda _: "azerty"
    )
    cmd_status = hash_password_main()
    assert cmd_status == 0
    captured = capsys.readouterr()
    password_hash = re.search("\$pbkdf2.*$", captured.out).group(0)
    settings.secret_settings.admin_password_hash = password_hash

    # And a user
    # When the user logs in with the wrong username and password
    async with lifespan(app):
        response = client.post(
            "/admin/login",
            data={
                "username": "admin",
                "password": "wrong password",
            },
        )
    assert response.status_code == status.HTTP_400_BAD_REQUEST

    # And tries to access the admin pages
    for list_page in (
        "user",
        "withings-user",
        "fitbit-user",
        "fitbit-activity",
        "fitbit-daily-activity",
    ):
        # Then they are redirected to the login page.
        response = client.get(
            f"/admin/{list_page}/list",
            follow_redirects=False,
        )
        assert response.status_code == status.HTTP_302_FOUND
        assert response.next_request.url.path == "/admin/login"
