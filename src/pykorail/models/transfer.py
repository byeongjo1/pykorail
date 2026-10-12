"""환승 — 갈아탈 수 있는 역과, 두 열차를 이어 붙인 환승 여정."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from pykorail.models.parsing import integer, text
from pykorail.models.schedule import Train

if TYPE_CHECKING:
    from collections.abc import Sequence


@dataclass(frozen=True)
class TransferStation:
    """두 역 사이에서 갈아탈 수 있는 역."""

    code: str
    name: str
    english_name: str

    @classmethod
    def from_response(cls, data: dict[str, Any]) -> TransferStation:
        return cls(
            code=text(data, "chtnRsStnCd"),
            name=text(data, "chtnRsStnNm"),
            english_name=text(data, "chtnRsStnEngNm"),
        )


@dataclass(frozen=True)
class Transfer:
    """두 열차를 갈아타는 여정 하나.

    열차를 상속하지 않고 **참조**합니다 — 여정은 열차가 아니라 열차 둘의 묶음입니다.
    """

    first: Train
    second: Train

    @classmethod
    def from_response(cls, first: dict[str, Any], second: dict[str, Any]) -> Transfer:
        """한 여정으로 묶인 두 행에서 만듭니다. 묶는 일은 :func:`parse_transfers` 가 합니다."""
        return cls(first=Train.from_response(first), second=Train.from_response(second))

    @property
    def legs(self) -> tuple[Train, Train]:
        """타는 순서대로 두 구간."""
        return (self.first, self.second)

    @property
    def station_name(self) -> str | None:
        """갈아타는 역 이름. 첫 열차의 도착역과 둘째 열차의 출발역이 다르면 ``None``.

        두 역이 다르다는 것은 역 사이를 따로 이동해야 한다는 뜻이라, 한쪽 이름을
        환승역이라고 넘겨짚지 않습니다. ``first.arr_name`` 과 ``second.dep_name`` 을 보세요.
        """
        return self.first.arr_name if self.first.arr_name == self.second.dep_name else None

    def has_seat(self) -> bool:
        """두 구간 모두 좌석이 있는지. 한쪽만 있어서는 여정을 탈 수 없습니다."""
        return self.first.has_seat() and self.second.has_seat()


def parse_transfers(rows: Sequence[dict[str, Any]]) -> list[Transfer]:
    """환승 조회의 열차 행들을 여정 단위로 묶습니다.

    서버는 여정을 중첩하지 않고 열차 행을 한 줄로 늘어놓은 채, 같은 여정의 행에 같은
    ``h_trn_seq`` 를(``"000"``, ``"001"`` …), 여정 안의 타는 순서에 ``h_chg_trn_seq``
    를(``"1"``, ``"2"``) 붙여 줍니다. 여정 번호가 같은 행을 묶고 타는 순서대로 놓습니다.

    **둘로 묶이지 않는 것은 여정으로 만들지 않습니다** — 번호가 비어 있는 행, 한 줄만
    있는 번호, 셋 이상인 번호. 무엇과 짝인지 알 수 없는 행을 넘겨짚어 이으면 실제로는
    갈아탈 수 없는 여정이 만들어집니다.
    """
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        sequence = text(row, "h_trn_seq")
        if sequence:
            groups.setdefault(sequence, []).append(row)
    # 타는 순서는 응답의 줄 순서가 아니라 서버가 붙인 번호를 따릅니다. 번호가 없으면 0 으로
    # 읽혀 줄 순서가 그대로 남습니다 (sorted 는 안정 정렬입니다).
    pairs = [sorted(group, key=_leg_order) for group in groups.values() if len(group) == 2]
    return [Transfer.from_response(first, second) for first, second in pairs]


def _leg_order(row: dict[str, Any]) -> int:
    return integer(row, "h_chg_trn_seq")
