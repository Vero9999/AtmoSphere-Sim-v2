from .base import ComingSoonScenario, Param, Scenario
from .perumahan import PerumahanScenario

SCENARIOS = {
    s.key: s
    for s in [
        PerumahanScenario(),
        ComingSoonScenario(
            "industri",
            "Pabrik / industri",
            "Emisi cerobong (Gaussian plume), kebisingan, limbah cair.",
        ),
        ComingSoonScenario(
            "reklamasi",
            "Pembukaan lahan / reklamasi pesisir",
            "Hilangnya mangrove, emisi karbon, abrasi, sedimen.",
        ),
    ]
}

__all__ = ["SCENARIOS", "Scenario", "Param"]
