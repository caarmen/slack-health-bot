from factory import Faker, RelatedFactoryList, SelfAttribute, Sequence, SubFactory
from factory.alchemy import SQLAlchemyModelFactory

from slackhealthbot.database.models import (
    FitbitLatestActivity,
    FitbitUser,
    User,
    WithingsUser,
)


class WithingsUserFactory(SQLAlchemyModelFactory):
    class Meta:
        model = WithingsUser

    user_id = Faker("pyint")
    oauth_access_token = Faker("pystr")
    oauth_refresh_token = Faker("pystr")
    oauth_userid = Faker("pystr")
    oauth_expiration_date = Faker("date_time")
    last_weight = Faker("pyfloat")


class FitbitLatestActivityFactory(SQLAlchemyModelFactory):
    class Meta:
        model = FitbitLatestActivity

    log_id = Faker("pyint")
    type_id = Faker("pyint")
    total_minutes = Faker("pyint")
    calories = Faker("pyint")
    cardio_minutes = Faker("pyint")
    fat_burn_minutes = Faker("pyint")
    peak_minutes = Faker("pyint")
    out_of_range_minutes = Faker("pyint")
    fitbit_user_id = Faker("pyint")


class FitbitUserFactory(SQLAlchemyModelFactory):
    class Meta:
        model = FitbitUser

    id = Sequence(lambda n: n)
    user_id = Faker("pyint")
    oauth_access_token = Faker("pystr")
    oauth_refresh_token = Faker("pystr")
    oauth_userid = Faker("pystr")
    oauth_expiration_date = Faker("date_time")
    latest_activities = RelatedFactoryList(
        FitbitLatestActivityFactory, "fitbit_user", size=0
    )


class UserFactory(SQLAlchemyModelFactory):
    class Meta:
        model = User

    id = Faker("pyint")
    slack_alias = Faker("pystr")
    withings = SubFactory(WithingsUserFactory, user_id=SelfAttribute("..id"))
    fitbit = SubFactory(FitbitUserFactory, user_id=SelfAttribute("..id"))
