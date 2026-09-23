from pathlib import Path
import yaml
from .models import Scenario


def load_scenarios(path: str | Path) -> list[Scenario]:
    raw = yaml.safe_load(Path(path).read_text())
    return [Scenario.model_validate(item) for item in raw["scenarios"]]

