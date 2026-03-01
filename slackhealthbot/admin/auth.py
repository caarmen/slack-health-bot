from dependency_injector.wiring import Provide, inject
from fastapi import Request
from passlib.hash import pbkdf2_sha256
from sqladmin.authentication import AuthenticationBackend

from slackhealthbot.containers import Container
from slackhealthbot.settings import Settings


class AdminAuth(AuthenticationBackend):
    """
    Basic authentication backend for the sqladmin interface.
    See: https://aminalaee.github.io/sqladmin/authentication/
    """

    @inject
    async def login(
        self,
        request: Request,
        settings: Settings = Provide[Container.settings],
    ) -> bool:
        """
        If the username and hash of the password match the admin username
        and password hash in the settings, then set the 'admin' attribute to true
        in the session and return True.

        Otherwise, return False without setting anything in the session.
        """
        form = await request.form()
        username = form["username"]
        password = form["password"]

        if (
            username == settings.secret_settings.admin_username
            and password
            and pbkdf2_sha256.verify(
                password, settings.secret_settings.admin_password_hash
            )
        ):
            request.session["admin"] = True
            return True

        return False

    async def logout(self, request: Request) -> bool:
        request.session.clear()
        return True

    async def authenticate(self, request: Request):
        """
        return True if we previously authenticated the user in the login() function,
        by checking the 'admin' attriute of the session.
        """
        return request.session.get("admin", False)
