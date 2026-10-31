from .base import ComingSoonScenario, Param, Scenario
from .buildings import (
    HotelScenario,
    KantorScenario,
    LainnyaScenario,
    MalScenario,
    PerumahanScenario,
    RukoScenario,
)

SCENARIOS = {
    s.key: s
    for s in [
        PerumahanScenario(),
        RukoScenario(),
        KantorScenario(),
        HotelScenario(),
        MalScenario(),
        LainnyaScenario(),
        ComingSoonScenario("industri"),
        ComingSoonScenario("reklamasi"),
    ]
}

__all__ = ["SCENARIOS", "Scenario", "Param"]
