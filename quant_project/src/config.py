from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class PipelineConfig:
    start_date: str = "2019-01-01"
    end_date: str = "2026-11-01"
    in_sample_end: str = "2024-12-31"
    universe_index: str = "hs300"
    min_list_days: int = 60
    mad_multiplier: float = 5.0
    valuation_max_age_days: int = 90
    industry_max_age_days: int = 45
    base_dir: Path = field(default_factory=lambda: Path(__file__).resolve().parents[1] / "quant_project_data")

    def __post_init__(self):
        if self.universe_index not in {"hs300", "zz500"}:
            raise ValueError("universe_index must be hs300 or zz500")
        if not self.start_date <= self.in_sample_end < self.end_date:
            raise ValueError("Invalid sample split")

    @property
    def raw_dir(self):
        return self.base_dir / "raw"

    @property
    def processed_dir(self):
        return self.base_dir / "processed"

    @property
    def figure_dir(self):
        return self.base_dir / "figures"
