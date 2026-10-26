"""로그인 세션 상태의 repr 이 개인정보를 싣지 않는지."""

from __future__ import annotations

from pykorail._shared import Account

PERSONAL = ("1234567890", "홍길동", "hong@example.com", "01012345678")


class TestRepr:
    def test_hides_personal_fields(self) -> None:
        # given
        account = Account(
            logined=True,
            membership_number=PERSONAL[0],
            name=PERSONAL[1],
            email=PERSONAL[2],
            phone_number=PERSONAL[3],
        )

        # when
        rendered = repr(account)

        # then
        assert [value for value in PERSONAL if value in rendered] == []

    def test_keeps_login_state(self) -> None:
        # when
        rendered = repr(Account(logined=True))

        # then
        assert "logined=True" in rendered
