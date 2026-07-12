from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Mapping

from dotenv import load_dotenv


class MissingApiKey(Exception):
    pass


@dataclass(frozen=True)
class FinnhubConfig:
    api_key: str
    base_url: str = "https://finnhub.io/api/v1"
    timeout: float = 10.0
    ttl: timedelta = field(default_factory=lambda: timedelta(seconds=60))
    max_retries: int = 3


def load_finnhub_config(
    env: Mapping[str, str] | None = None,
) -> FinnhubConfig:
    if env is None:
        load_dotenv()
        env = os.environ
    api_key = env.get("FINNHUB_API_KEY", "").strip()
    if not api_key:
        raise MissingApiKey(
            "Falta FINNHUB_API_KEY. Copia .env.example a .env y pon tu clave "
            "de Finnhub (https://finnhub.io/register)."
        )
    return FinnhubConfig(api_key=api_key)
