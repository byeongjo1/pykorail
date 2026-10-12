"""리소스 공통 기반."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pykorail.api import ApiClient


def without_blanks(form: dict[str, Any]) -> dict[str, Any]:
    """빈 문자열 필드를 뺀 폼.

    앱은 요청 모델을 폼으로 펼칠 때 값이 빈 필드를 싣지 않습니다(코레일+ 7.0.8
    ``NetworkService`` 의 평탄화: 길이가 0 보다 클 때만 넣습니다). 7.0.8 에서 새로
    확인한 엔드포인트는 이 규칙을 따릅니다.

    **기존 엔드포인트에는 쓰지 마세요.** 조회의 빈 ``Sid`` 처럼 빈 값을 그대로 보내야
    하는 폼이 있고(AGENTS.md §3), 그것들은 실제 동작으로 검증된 모양입니다.
    """
    return {key: value for key, value in form.items() if value != ""}


class Resource:
    """엔드포인트 묶음 하나.

    리소스는 상태를 거의 갖지 않고 :class:`~pykorail.api.ApiClient` 를 통해서만
    통신합니다. 클라이언트 하나가 만든 리소스들은 세션·서명·로그인 상태를 공유합니다.
    """

    def __init__(self, api: ApiClient) -> None:
        self._api = api
