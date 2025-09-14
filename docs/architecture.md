# Architecture

The arrows in the architecture indicate dependencies. For example, the Data layer depends on the Domain layer.

## Level 1 - overview
```mermaid
graph TD

    subgraph EntryPoints[Entry points]
        Routes
        Tasks
    end
    subgraph Domain
        UseCases
        Models
        LocalRepositoryInterfaces
        RemoteRepositoryInterfaces
    end
    subgraph Data
        LocalRepositories
        Database
    end
    subgraph RemoteServices[Remote services]
        RemoteRepositories
        Apis
    end

    EntryPoints-->Domain
    Data-->Domain
    RemoteServices-->Domain
```
## Level 2 - some more details
```mermaid
graph TD

    subgraph EntryPoints[Entry points]
        Routes
        Tasks
    end
    subgraph Domain
        UseCases
        LocalRepositoryInterfaces:::interface
        RemoteRepositoryInterfaces:::interface
    end
    subgraph Data
        LocalRepositories
        ORM
    end
    subgraph RemoteServices[Remote services]
        RemoteRepositories
        Apis
    end
    DI
    ExternalWebServers:::external
    Sqlite3Database[(Sqlite3Database)]:::external


    Routes-->Domain
    Tasks-->Domain
    RemoteRepositories--implements-->RemoteRepositoryInterfaces
    LocalRepositories--implements-->LocalRepositoryInterfaces
    RemoteRepositories-->Apis
    LocalRepositories-->ORM
    UseCases-->RemoteRepositoryInterfaces
    UseCases-->LocalRepositoryInterfaces
    DI--creates-->RemoteRepositories
    DI--creates-->LocalRepositories
    Routes-->DI 
    Tasks-->DI
    ORM-->Sqlite3Database
    Apis-->ExternalWebServers
    classDef interface fill:#FFF, stroke:#333,stroke-dasharray: 5 5;
    classDef external fill:#FEE
```
## Level 3 - even more details
```mermaid
graph
    subgraph Main
    end

    subgraph Tasks
        FitbitPolling
    end
    subgraph Routes
        FitbitRoutes
        WithingsRoutes
    end
    subgraph Data
        subgraph LocalRepositories
            SQLAlchemyFitbitRepository
            SQLAlchemyWithingsRepository
        end
        ORM
    end
    subgraph Domain
        subgraph UseCases
            FitbitUseCases
            WithingsUseCases
            SlackUseCases
        end
        subgraph LocalRepositoryInterfaces
            LocalFitbitRepository("`*LocalFitbitRepository*`"):::interface
            LocalWithingsRepository("`*LocalWithingsRepository*`"):::interface
        end
        subgraph RemoteRepositoryInterfaces
            RemoteFitbitRepository("`*RemoteFitbitRepository*`"):::interface
            RemoteWithingsRepository("`*RemoteWithingsRepository*`"):::interface
            RemoteSlackRepository("`*RemoteSlackRepository*`"):::interface
            RemoteOpenAiRepository("`*RemoteOpenAiRepository*`"):::interface
        end
    end
    subgraph RemoteServices[Remote services]
        subgraph RemoteRepositories
            WebApiFitbitRepository
            WebApiWithingsRepository
            WebhookSlackRepository
            WebOpenAiRepository
        end
        subgraph Apis
            FitbitApis
            WithingsApis
            SlackApis
        end
    end
    subgraph DI
    end
    ExternalWebServers:::external
    Sqlite3Database[(SQlite3Database)]:::external


    Main-->Routes
    Main-->Tasks
    Routes-->DI
    Tasks-->DI
    DI--creates-->LocalRepositories
    DI--creates-->RemoteRepositories
    Tasks-->Domain
    Routes-->Domain
    LocalRepositories-->ORM

    UseCases-->LocalRepositoryInterfaces
    UseCases-->RemoteRepositoryInterfaces

    LocalRepositories--implements-->LocalRepositoryInterfaces
    RemoteRepositories--implements-->RemoteRepositoryInterfaces
    RemoteRepositories-->Apis
    Apis--http--->ExternalWebServers


    ORM--sql--->Sqlite3Database
    classDef interface fill:#FFF, stroke:#333,stroke-dasharray: 5 5;
    classDef external fill:#FEE
```
## Level 4 - TLDR arrows everywhere
```mermaid
graph  
    subgraph Main
    end

    subgraph Tasks
        FitbitPolling
    end
    subgraph Routes
        FitbitRoutes
        WithingsRoutes
    end
    subgraph Data
        subgraph LocalRepositories
            SQLAlchemyFitbitRepository
            SQLAlchemyWithingsRepository
        end
        ORM
    end
    subgraph Domain
        subgraph UseCases
            FitbitUseCases
            WithingsUseCases
            SlackUseCases
        end
        subgraph LocalRepositoryInterfaces
            LocalFitbitRepository("`*LocalFitbitRepository*`"):::interface
            LocalWithingsRepository("`*LocalWithingsRepository*`"):::interface
        end
        subgraph RemoteRepositoryInterfaces
            RemoteFitbitRepository("`*RemoteFitbitRepository*`"):::interface
            RemoteWithingsRepository("`*RemoteWithingsRepository*`"):::interface
            RemoteSlackRepository("`*RemoteSlackRepository*`"):::interface
            RemoteOpenAiRepository("`*RemoteOpenAiRepository*`"):::interface
        end
    end
    subgraph RemoteServices[Remote services]
        subgraph RemoteRepositories
            WebApiFitbitRepository
            WebApiWithingsRepository
            WebhookSlackRepository
            WebOpenAiRepository
        end
        subgraph Apis
            FitbitApis
            WithingsApis
            SlackApis
        end
    end
    subgraph Core
        CoreModels[Models]
        Exceptions
    end
    subgraph OAuth
        FitbitOAuth
        WithingsOAuth
    end
    subgraph DI
    end
    Sqlite3Database[(SQlite3Database)]:::external
    WithingsWebServer:::external
    FitbitWebServer:::external
    SlackWebServer:::external
    OpenAiWebServer:::external

    Main-->Routes
    Main-->Tasks
    Routes-->DI
    Tasks-->DI
    DI--creates-->SQLAlchemyFitbitRepository
    DI--creates-->SQLAlchemyWithingsRepository
    DI--creates-->WebApiFitbitRepository
    DI--creates-->WebApiWithingsRepository
    DI--creates-->WebhookSlackRepository
    DI--creates-->WebOpenAiRepository
    Tasks-->Domain
    Routes-->Domain
    LocalRepositories-->ORM

    UseCases-->LocalRepositoryInterfaces
    UseCases-->RemoteRepositoryInterfaces


    SQLAlchemyFitbitRepository--implements-->LocalFitbitRepository
    SQLAlchemyWithingsRepository--implements-->LocalWithingsRepository

    WebApiFitbitRepository--implements-->RemoteFitbitRepository
    WebApiWithingsRepository--implements-->RemoteWithingsRepository
    WebhookSlackRepository--implements-->RemoteSlackRepository
    WebOpenAiRepository --implements-->RemoteOpenAiRepository
    OpenAiSdk{{OpenAISdk}}
    WebApiFitbitRepository-->FitbitApis
    WebApiWithingsRepository-->WithingsApis
    WebhookSlackRepository-->SlackApis
    WebOpenAiRepository-->OpenAiSdk
    FitbitApis--http--->FitbitWebServer
    WithingsApis--http--->WithingsWebServer
    SlackApis--http--->SlackWebServer
    FitbitOAuth--http--->FitbitWebServer
    WithingsOAuth--http--->WithingsWebServer
    OpenAiSdk--http--->OpenAiWebServer

    Domain-->Core
    RemoteServices-->Core
    RemoteServices-->OAuth
    Routes-->OAuth
    OAuth-->Core

    ORM--sql--->Sqlite3Database
    classDef interface fill:#FFF, stroke:#333,stroke-dasharray: 5 5;
    classDef external fill:#FEE
```
