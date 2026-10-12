"""예매 전 운임 — 열차를 예약하기 전에 미리 보는 기준 운임."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pykorail.models.parsing import integer, text


@dataclass(frozen=True)
class Fare:
    """한 구간 · 한 객실의 운임.

    **결제 금액이 아닙니다.** 할인 전의 기준 운임이고, 실제로 낼 금액은 예약한 뒤
    :attr:`Reservation.price <pykorail.models.reservation.Reservation.price>` 에 있습니다.
    """

    train_no: str
    #: 여정 안의 구간 번호 (``jrnySqno``). 환승 여정은 구간마다 줄이 나뉩니다.
    journey_no: str
    seat_class_name: str
    #: 응답의 ``rcvdPrc``. ``Reservation.price``(결제 예정 금액)와 이름만 같고 다른 값입니다.
    price: int
    #: 응답의 ``rcvdFare``. ``price`` 에 더해지는 금액입니다 (특실 요금 등).
    charge: int
    #: 응답의 ``sumAmt``. 이 객실의 기준 운임 합계입니다.
    total: int

    @classmethod
    def from_response(cls, data: dict[str, Any]) -> Fare:
        return cls(
            train_no=text(data, "trnNo"),
            journey_no=text(data, "jrnySqno"),
            seat_class_name=text(data, "psrmClNm"),
            price=integer(data, "rcvdPrc"),
            charge=integer(data, "rcvdFare"),
            total=integer(data, "sumAmt"),
        )
