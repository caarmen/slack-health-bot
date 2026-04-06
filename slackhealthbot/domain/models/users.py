import dataclasses
from typing import TypeAlias


@dataclasses.dataclass(frozen=True)
class FitbitUserLookup:
    user_id: str


@dataclasses.dataclass(frozen=True)
class HealthUserLookup:
    user_id: str


UserLookup: TypeAlias = FitbitUserLookup | HealthUserLookup
