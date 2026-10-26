"""예외 계층과 응답 코드 매핑."""

from __future__ import annotations

import pytest

from pykorail.exceptions import (
    AccessRestrictedError,
    HttpStatusError,
    KorailError,
    LoginFailedError,
    NeedToLoginError,
    NetFunnelError,
    NoResultsError,
    PasswordChangeRequiredError,
    PykorailError,
    SoldOutError,
    TransportError,
    error_for_code,
)


class TestHierarchy:
    @pytest.mark.parametrize(
        "error_type",
        [
            KorailError,
            NeedToLoginError,
            NoResultsError,
            SoldOutError,
            NetFunnelError,
            TransportError,
            HttpStatusError,
            AccessRestrictedError,
            LoginFailedError,
            PasswordChangeRequiredError,
        ],
    )
    def test_everything_is_a_pykorail_error(self, error_type: type[Exception]) -> None:
        """호출부가 except PykorailError 하나로 라이브러리 실패를 다 잡을 수 있어야 합니다."""
        # when
        is_library_error = issubclass(error_type, PykorailError)

        # then
        assert is_library_error

    def test_netfunnel_is_not_a_korail_error(self) -> None:
        """대기열 게이트는 코레일 응답이 아니므로 형제 타입이어야 합니다."""
        # when
        is_korail_error = issubclass(NetFunnelError, KorailError)

        # then
        assert not is_korail_error

    def test_password_change_notice_is_still_a_login_failure(self) -> None:
        """``login()`` 의 계약은 "실패는 전부 LoginFailedError" 입니다. 새 타입이 그 밖으로 나가면 깨집니다."""
        # when
        is_login_failure = issubclass(PasswordChangeRequiredError, LoginFailedError)

        # then
        assert is_login_failure

    def test_access_restriction_is_still_an_http_status_error(self) -> None:
        """기존 ``except HttpStatusError`` 호출부가 이용제한도 계속 잡아야 합니다."""
        # when
        is_http_status_error = issubclass(AccessRestrictedError, HttpStatusError)

        # then
        assert is_http_status_error


class TestCodeMapping:
    @pytest.mark.parametrize(
        ("code", "expected"),
        [
            ("P058", NeedToLoginError),
            ("P100", NoResultsError),
            ("WRG000000", NoResultsError),
            ("WRD000061", NoResultsError),
            ("WRT300005", NoResultsError),
            ("IRT010110", SoldOutError),
            ("ERR211161", SoldOutError),
            ("WRC000420", PasswordChangeRequiredError),
        ],
    )
    def test_known_codes_promote_to_specific_types(self, code: str, expected: type[KorailError]) -> None:
        # when
        error = error_for_code(code, "서버 메시지")

        # then
        assert type(error) is expected
        assert error.code == code

    @pytest.mark.parametrize(
        ("code", "said"),
        [
            ("P058", "로그아웃되었습니다. 다시 로그인하여 주십시오."),
            ("P058", "회원로그인 후 사용하시기 바랍니다."),
            ("WRG000000", "조회 결과가 없습니다."),
            ("IRT010110", "잔여석 없음"),
            ("WRC000420", "6개월 이상 동일한 비밀번호를 사용하고 있습니다."),
        ],
        ids=["logged-out", "login-first", "no-results", "sold-out", "password-change"],
    )
    def test_known_code_keeps_what_the_server_said(self, code: str, said: str) -> None:
        """타입으로 승격돼도 서버의 말은 남아야 합니다. 같은 코드에 다른 문구가 옵니다."""
        # when
        error = error_for_code(code, said)

        # then
        assert error.msg == said

    @pytest.mark.parametrize("said", [None, ""], ids=["absent", "blank"])
    def test_known_code_without_a_message_falls_back_to_the_default(self, said: str | None) -> None:
        # when
        error = error_for_code("P100", said)

        # then
        assert error.msg == "No Results"

    def test_known_code_renders_the_server_message_with_its_code(self) -> None:
        # when
        rendered = str(error_for_code("P058", "로그아웃되었습니다."))

        # then
        assert rendered == "로그아웃되었습니다. (P058)"

    def test_unknown_code_keeps_server_message(self) -> None:
        # when
        error = error_for_code("ZZZ999", "알 수 없는 오류")

        # then
        assert type(error) is KorailError
        assert error.msg == "알 수 없는 오류"
        assert error.code == "ZZZ999"

    def test_missing_code(self) -> None:
        # when
        error = error_for_code(None, "메시지만 있음")

        # then
        assert type(error) is KorailError
        assert error.code is None

    def test_new_subclass_is_picked_up_without_registration(self) -> None:
        """codes 만 채우면 등록 테이블을 손대지 않아도 매핑돼야 합니다."""

        # given
        class TemporarilyUnavailableError(KorailError):
            codes = frozenset({"TEST9999"})
            default_msg = "잠시 후 다시"

        # when
        error = error_for_code("TEST9999")

        # then
        assert type(error) is TemporarilyUnavailableError
        assert error.msg == "잠시 후 다시"


class TestMessages:
    def test_default_message_applies(self) -> None:
        # when
        error = NoResultsError()

        # then
        assert error.msg == "No Results"

    def test_str_includes_code(self) -> None:
        # given
        error = SoldOutError(code="IRT010110")

        # when
        rendered = str(error)

        # then
        assert rendered == "Sold out (IRT010110)"

    def test_explicit_message_wins(self) -> None:
        # when
        error = NoResultsError("직접 지정")

        # then
        assert error.msg == "직접 지정"


class TestRenderingWithoutCode:
    @pytest.mark.parametrize(
        ("error", "expected"),
        [
            (KorailError("서버 메시지", code="P999"), "서버 메시지 (P999)"),
            (KorailError("서버 메시지"), "서버 메시지"),
            (KorailError(), ""),
            (HttpStatusError(403, "차단", "-2000"), "HTTP 403: 차단 (-2000)"),
            (HttpStatusError(500), "HTTP 500: 응답 본문 없음"),
            (AccessRestrictedError(403, "막힘", "-2000"), "이용제한: 막힘 (HTTP 403, -2000)"),
            (AccessRestrictedError(403, "막힘"), "이용제한: 막힘 (HTTP 403)"),
        ],
        ids=[
            "korail-with-code",
            "korail-without-code",
            "korail-without-message",
            "http-with-code",
            "http-without-code",
            "restricted-with-code",
            "restricted-without-code",
        ],
    )
    def test_str_omits_the_missing_code(self, error: Exception, expected: str) -> None:
        # when
        rendered = str(error)

        # then
        assert rendered == expected
        assert "None" not in rendered
