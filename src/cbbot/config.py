import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
STATE_DIR = ROOT / "state"
BRIEFINGS_DIR = ROOT / "briefings"

load_dotenv(ROOT / ".env")


@dataclass
class Limits:
    max_order_usd: float
    daily_cap_usd: float
    allowed_products: list[str]


@dataclass
class Config:
    mode: str
    watchlist: list[str]
    limits: Limits
    paper_starting_usd: float
    paper_fee_pct: float
    strategies: dict = field(default_factory=dict)


def load_config(path: Path = ROOT / "config.yaml") -> Config:
    raw = yaml.safe_load(path.read_text())
    mode = os.getenv("TRADING_MODE", "paper").strip().lower()
    if mode not in ("paper", "live"):
        mode = "paper"
    lim = raw["limits"]
    return Config(
        mode=mode,
        watchlist=raw.get("watchlist", []),
        limits=Limits(
            max_order_usd=float(lim["max_order_usd"]),
            daily_cap_usd=float(lim["daily_cap_usd"]),
            allowed_products=[p.upper() for p in lim["allowed_products"]],
        ),
        paper_starting_usd=float(raw.get("paper", {}).get("starting_usd", 1000)),
        paper_fee_pct=float(raw.get("paper", {}).get("fee_pct", 1.2)),
        strategies=raw.get("strategies", {}),
    )
