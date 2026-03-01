from sqladmin import ModelView
from sqladmin.filters import OperationColumnFilter as BaseOperationColumnFilter
from sqlalchemy.inspection import inspect
from sqlalchemy.sql.sqltypes import Date, DateTime

from slackhealthbot.data.database.models import (
    FitbitActivity,
    FitbitDailyActivity,
    FitbitUser,
    User,
    WithingsUser,
)


class OperationColumnFilter(BaseOperationColumnFilter):
    """
    Override SQLAdmin's OperationColumnFilter, to make it possible
    to filter with greater_than and less_than on date type fields.
    """

    def get_operation_options(self, column_obj):
        if isinstance(column_obj.type, (Date, DateTime)):
            return [
                ("equals", "Equals"),
                ("greater_than", "Greater than"),
                ("less_than", "Less than"),
            ]
        return super().get_operation_options(column_obj)


def user_formatter(obj: User) -> str:
    return f"{obj.id} - {obj.slack_alias}"


def fitbit_user_formatter(obj: FitbitUser) -> str:
    return obj.oauth_userid


def withings_user_formatter(obj: WithingsUser) -> str:
    return obj.oauth_userid


def auto_admin(cls):
    """
    Class decorator for admin classes, configuring all model fields
    to appear in the list, sortable and filterable.
    """
    cls.column_list = "__all__"
    mapper = inspect(cls.model).mapper
    columns = [c.key for c in mapper.column_attrs]
    cls.column_sortable_list = columns
    cls.column_filters = [OperationColumnFilter(c) for c in columns]
    cls.column_type_formatters = {
        User: user_formatter,
        FitbitUser: fitbit_user_formatter,
        WithingsUser: withings_user_formatter,
    }
    return cls


@auto_admin
class UserAdmin(ModelView, model=User): ...


@auto_admin
class WithingsUserAdmin(ModelView, model=WithingsUser):
    form_include_pk = True


@auto_admin
class FitbitUserAdmin(ModelView, model=FitbitUser):
    form_include_pk = True


@auto_admin
class FitbitActivityAdmin(ModelView, model=FitbitActivity):
    form_include_pk = True
    column_default_sort = [
        (FitbitActivity.created_at, True),
    ]


@auto_admin
class FitbitDailyActivityAdmin(ModelView, model=FitbitDailyActivity):
    column_default_sort = [
        (FitbitDailyActivity.date, True),
        (FitbitDailyActivity.type_id, False),
    ]
    form_include_pk = True
    can_create = False
    can_edit = False
    can_delete = False
