from investsim.providers.market_data import (
    MarketDataError,
    ProviderUnavailable,
    UnknownSymbol,
)


def test_unknown_symbol_is_market_data_error():
    assert issubclass(UnknownSymbol, MarketDataError)


def test_provider_unavailable_is_market_data_error():
    assert issubclass(ProviderUnavailable, MarketDataError)


def test_errors_are_distinct():
    assert UnknownSymbol is not ProviderUnavailable
