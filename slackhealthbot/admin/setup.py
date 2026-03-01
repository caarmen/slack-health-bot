from dependency_injector.wiring import Provide, inject
from sqladmin import Admin
from sqlalchemy import create_engine

from slackhealthbot.admin.auth import AdminAuth
from slackhealthbot.admin.models import (
    FitbitActivityAdmin,
    FitbitDailyActivityAdmin,
    FitbitUserAdmin,
    UserAdmin,
    WithingsUserAdmin,
)
from slackhealthbot.containers import Container
from slackhealthbot.settings import Settings


@inject
def init_admin(
    app,
    settings: Settings = Provide[Container.settings],
):
    """
    Configure the SQLAdmin interface.
    https://aminalaee.github.io/sqladmin/configurations/
    """
    sync_engine = create_engine(
        f"sqlite:///{settings.app_settings.database_path}",
        connect_args={"check_same_thread": False},
    )
    admin = Admin(
        app,
        engine=sync_engine,
        authentication_backend=AdminAuth(settings.secret_settings.session_secret_key),
    )
    admin.add_view(UserAdmin)
    admin.add_view(WithingsUserAdmin)
    admin.add_view(FitbitUserAdmin)
    admin.add_view(FitbitActivityAdmin)
    admin.add_view(FitbitDailyActivityAdmin)
    return admin
