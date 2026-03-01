from sqladmin import ModelView
from sqladmin.filters import OperationColumnFilter
from sqlalchemy.inspection import inspect

from slackhealthbot.data.database.models import (
    FitbitActivity,
    FitbitDailyActivity,
    FitbitUser,
    User,
    WithingsUser,
)


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
