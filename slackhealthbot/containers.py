from dependency_injector import containers, providers
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from slackhealthbot.data.database.connection import (
    create_async_session_maker,
    session_context_manager,
)
from slackhealthbot.data.repositories.sqlalchemyfitbitrepository import (
    SQLAlchemyFitbitRepository,
)
from slackhealthbot.data.repositories.sqlalchemywithingsrepository import (
    SQLAlchemyWithingsRepository,
)
from slackhealthbot.domain.localrepository.localfitbitrepository import (
    LocalFitbitRepository,
)
from slackhealthbot.domain.localrepository.localwithingsrepository import (
    LocalWithingsRepository,
)
from slackhealthbot.domain.remoterepository.remotefitbitrepository import (
    RemoteFitbitRepository,
)
from slackhealthbot.domain.remoterepository.remoteopenairepository import (
    RemoteOpenAiRepository,
)
from slackhealthbot.domain.remoterepository.remoteslackrepository import (
    RemoteSlackRepository,
)
from slackhealthbot.domain.remoterepository.remotewithingsrepository import (
    RemoteWithingsRepository,
)
from slackhealthbot.remoteservices.repositories.webapifitbitrepository import (
    WebApiFitbitRepository,
)
from slackhealthbot.remoteservices.repositories.webapiwithingsrepository import (
    WebApiWithingsRepository,
)
from slackhealthbot.remoteservices.repositories.webhookslackrepository import (
    WebhookSlackRepository,
)
from slackhealthbot.remoteservices.repositories.webopenairepository import (
    WebOpenAiRepository,
)
from slackhealthbot.settings import AppSettings, SecretSettings, Settings


class Container(containers.DeclarativeContainer):
    config = providers.Configuration()

    wiring_config = containers.WiringConfiguration(
        modules=[
            "slackhealthbot.data.database.connection",
            "slackhealthbot.domain.usecases.fitbit.usecase_calculate_streak",
            "slackhealthbot.domain.usecases.fitbit.usecase_get_last_activity",
            "slackhealthbot.domain.usecases.fitbit.usecase_get_last_sleep",
            "slackhealthbot.domain.usecases.fitbit.usecase_login_user",
            "slackhealthbot.domain.usecases.fitbit.usecase_post_user_logged_out",
            "slackhealthbot.domain.usecases.fitbit.usecase_process_daily_activities",
            "slackhealthbot.domain.usecases.fitbit.usecase_process_daily_activity",
            "slackhealthbot.domain.usecases.fitbit.usecase_process_new_activity",
            "slackhealthbot.domain.usecases.fitbit.usecase_process_new_sleep",
            "slackhealthbot.domain.usecases.fitbit.usecase_update_user_oauth",
            "slackhealthbot.domain.usecases.fitbit.usecase_update_user_oauth",
            "slackhealthbot.domain.usecases.slack.usecase_post_activity",
            "slackhealthbot.domain.usecases.slack.usecase_post_daily_activity",
            "slackhealthbot.domain.usecases.slack.usecase_post_sleep",
            "slackhealthbot.domain.usecases.slack.usecase_post_user_logged_out",
            "slackhealthbot.domain.usecases.slack.usecase_post_weight",
            "slackhealthbot.domain.usecases.withings.usecase_get_last_weight",
            "slackhealthbot.domain.usecases.withings.usecase_login_user",
            "slackhealthbot.domain.usecases.withings.usecase_post_user_logged_out",
            "slackhealthbot.domain.usecases.withings.usecase_process_new_weight",
            "slackhealthbot.domain.usecases.withings.usecase_update_user_oauth",
            "slackhealthbot.oauth.fitbitconfig",
            "slackhealthbot.oauth.withingsconfig",
            "slackhealthbot.routers.dependencies",
            "slackhealthbot.routers.fitbit",
            "slackhealthbot.routers.withings",
            "slackhealthbot.tasks.fitbitpoll",
        ],
    )

    app_settings: AppSettings = providers.Factory(AppSettings)
    secret_settings: SecretSettings = providers.Factory(SecretSettings)
    settings: Settings = providers.Singleton(
        Settings,
        app_settings,
        secret_settings,
    )
    slack_repository: RemoteSlackRepository = providers.Factory(
        WebhookSlackRepository,
        settings,
    )
    remote_fitbit_repository: RemoteFitbitRepository = providers.Factory(
        WebApiFitbitRepository,
        settings,
    )
    remote_withings_repository: RemoteWithingsRepository = providers.Factory(
        WebApiWithingsRepository,
        settings,
    )
    openai_repository: RemoteOpenAiRepository = providers.Factory(
        WebOpenAiRepository,
        settings,
    )
    session_factory: async_sessionmaker = providers.Singleton(
        create_async_session_maker,
        settings,
    )

    db: AsyncSession = providers.Resource(
        session_context_manager,
        session_factory,
    )

    local_withings_repository: LocalWithingsRepository = providers.Factory(
        SQLAlchemyWithingsRepository,
        db,
    )

    local_fitbit_repository: LocalFitbitRepository = providers.Factory(
        SQLAlchemyFitbitRepository,
        db,
    )
