"""DynaPath v2 토큰의 서버-visible 속성 회귀 테스트.

서버는 토큰 본문을 보지 않고 ``201`` 프리픽스만 검사하므로(근거:
``docs/protocol-evidence-7.0.10.json``), 여기서는 프리픽스·문자셋·길이·요청별
변화만 검증합니다. 실제 네이티브 서명이나 서버 수용 증거가 아닙니다.
"""

from __future__ import annotations

import pytest

from pykorail.auth.dynapath import (
    _ALPHABET,
    _BOUND_TOKEN_LENGTH,
    _PLAIN_TOKEN_LENGTH,
    DynaPathMasterEngine,
)
from pykorail.constants import TOKEN_PREFIX

INIT_MS = 1_700_000_000_000


def test_token_has_version_prefix() -> None:
    # when
    token = DynaPathMasterEngine().generate_token()

    # then
    assert token.startswith(TOKEN_PREFIX)


def test_body_uses_alphanumeric_charset() -> None:
    # when
    token = DynaPathMasterEngine().generate_token()

    # then
    assert set(token) <= set(_ALPHABET)


@pytest.mark.parametrize(
    ("request_bound", "expected"),
    [(True, _BOUND_TOKEN_LENGTH), (False, _PLAIN_TOKEN_LENGTH)],
)
def test_length_is_chosen_by_request_binding(request_bound: bool, expected: int) -> None:
    # when
    token = DynaPathMasterEngine().generate_token(request_bound=request_bound)

    # then
    assert len(token) == expected


def test_tokens_differ_between_calls() -> None:
    # given
    engine = DynaPathMasterEngine()

    # when
    first = engine.generate_token()
    second = engine.generate_token()

    # then
    assert first != second


def test_generate_token_with_timestamp_returns_sampled_time(monkeypatch: pytest.MonkeyPatch) -> None:
    # given
    monkeypatch.setattr("pykorail.auth.dynapath.time.time", lambda: (INIT_MS + 1234) / 1000)

    # when
    token, timestamp = DynaPathMasterEngine().generate_token_with_timestamp()

    # then
    assert timestamp == INIT_MS + 1234
    assert token.startswith(TOKEN_PREFIX)
