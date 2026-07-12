from datetime import timedelta

import pytest

from investsim.config import FinnhubConfig, MissingApiKey, load_finnhub_config


def test_load_from_explicit_env():
    cfg = load_finnhub_config({"FINNHUB_API_KEY": "abc123"})
    assert cfg.api_key == "abc123"
    assert cfg.base_url == "https://finnhub.io/api/v1"
    assert cfg.ttl == timedelta(seconds=60)
    assert cfg.max_retries == 3


def test_missing_api_key_raises():
    with pytest.raises(MissingApiKey):
        load_finnhub_config({})


def test_empty_api_key_raises():
    with pytest.raises(MissingApiKey):
        load_finnhub_config({"FINNHUB_API_KEY": ""})


def test_defaults_are_sensible():
    cfg = FinnhubConfig(api_key="x")
    assert cfg.timeout == 10.0
    assert cfg.max_retries == 3
    assert cfg.ttl == timedelta(seconds=60)
