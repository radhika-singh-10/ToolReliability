from pathlib import Path
import yaml
from .models import Scenario


def load_scenarios(path: str | Path) -> list[Scenario]:
    raw = yaml.safe_load(Path(path).read_text())
    return [Scenario.model_validate(item) for item in raw["scenarios"]]


def load_domain(domain: str, directory: str | Path = "scenarios") -> list[Scenario]:
    path = Path(directory) / f"{domain}.yaml"
    if not path.exists():
        raise ValueError(f"unknown evaluation domain: {domain}")
    return load_scenarios(path)


def available_domains(directory: str | Path = "scenarios") -> list[str]:
    return sorted(path.stem for path in Path(directory).glob("*.yaml") if path.stem != "commerce")
