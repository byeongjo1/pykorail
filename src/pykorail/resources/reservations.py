"""예약 리소스."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pykorail.constants import API_ENDPOINTS
from pykorail.exceptions import KorailError, NoResultsError
from pykorail.models.car import CarSeat
from pykorail.models.card import Card
from pykorail.models.parsing import records, text
from pykorail.models.passenger import AdultPassenger, Passenger
from pykorail.models.reservation import Reservation
from pykorail.models.seat import Seat
from pykorail.options import ReserveOption
from pykorail.resources.base import Resource, without_blanks

if TYPE_CHECKING:
    from collections.abc import Sequence

    from pykorail.models.schedule import Train
    from pykorail.options import ReserveOptionCode

#: 좌석이 있는 열차를 예매할 때의 특실 선택 규칙. 값은 "특실을 고를지" 여부입니다.
_SEATED_PREFERS_SPECIAL = {
    ReserveOption.GENERAL_ONLY: lambda train: False,
    ReserveOption.SPECIAL_ONLY: lambda train: True,
    ReserveOption.GENERAL_FIRST: lambda train: not train.has_general_seat(),
    ReserveOption.SPECIAL_FIRST: lambda train: train.has_special_seat(),
}

#: 좌석을 지정한 예매의 작업 구분 (``txtJobId``). 앱의 좌석 선택 화면이
#: ``ReservationJobId.SEAT`` 를 싣고, 그 값이 1103 입니다.
_JOB_SEAT_DESIGNATED = "1103"

#: 좌석이 없어 예약대기를 걸 때의 규칙. 가용 좌석이 없으니 선호만 반영합니다.
_WAITING_PREFERS_SPECIAL = {
    ReserveOption.GENERAL_ONLY: False,
    ReserveOption.GENERAL_FIRST: False,
    ReserveOption.SPECIAL_ONLY: True,
    ReserveOption.SPECIAL_FIRST: True,
}


class ReservationResource(Resource):
    """``korail.reservations`` — 예매·조회·취소."""

    def all(self) -> list[Reservation]:
        """결제 전 예약 목록. 없으면 빈 리스트.

        각 예약의 좌석 상세까지 채워서 돌려주므로 예약 수만큼 추가 요청이 나갑니다.
        하나만 필요하면 :meth:`find` 를 쓰세요 — 그쪽은 2회로 끝납니다.
        """
        return [self._complete(entry) for entry in self._entries()]

    def find(self, rsv_id: str | None) -> Reservation | None:
        """``rsv_id`` 와 일치하는 예약 하나. 없으면 ``None``.

        목록을 전부 조립하지 않고 **일치하는 예약의 좌석만** 조회합니다. 예약이
        N건이어도 찾았을 때 요청은 2회(목록 + 그 예약의 좌석)이고, 목록에 없으면
        1회에서 멈춥니다 — 전에는 모든 예약의 좌석 상세를 긁은 뒤 하나만 골라
        버려서, 예매 한 번에 요청이 N+2회 나갔습니다.
        """
        if not rsv_id:
            return None
        matched = next((entry for entry in self._entries() if text(entry, "h_pnr_no") == rsv_id), None)
        return None if matched is None else self._complete(matched)

    def _entries(self) -> list[dict[str, Any]]:
        """예약 목록 응답에서 예약 항목들을 평평하게 꺼냅니다. 없으면 빈 리스트."""
        payload = self._api.get(API_ENDPOINTS["myreservationview"], params=self._api.base_payload())
        try:
            self._api.check(payload)
        except NoResultsError:
            return []

        return [
            train_info
            for journey in records(payload, "jrny_infos", "jrny_info")
            for train_info in records(journey, "train_infos", "train_info")
        ]

    def _complete(self, entry: dict[str, Any]) -> Reservation:
        """예약 항목 하나에 좌석 상세를 붙여 완성합니다 (요청 1회).

        좌석을 나중에 주입하지 않고 여기서 미리 조회해 생성자에 넘깁니다 —
        반쯤 채워진 예약이 돌아다니면 안 됩니다 (AGENTS.md §2-3).
        """
        seats, wct_no = self.seats(entry.get("h_pnr_no"))
        return Reservation.from_response(entry, seats=tuple(seats), wct_no=wct_no)

    def seats(self, rsv_id: str | None = None) -> tuple[list[Seat], str | None]:
        """예약의 좌석 상세와 발매창구 번호(``wct_no``).

        조회 결과가 없으면 ``([], None)`` 을 돌려줍니다 — 호출부가 항상 튜플로
        풀 수 있어야 하므로 실패해도 모양을 유지합니다.
        """
        payload = self._api.get(
            API_ENDPOINTS["myreservationlist"],
            params={**self._api.base_payload(), "hidPnrNo": rsv_id},
        )
        try:
            self._api.check(payload)
        except NoResultsError:
            return [], None

        wct_no = payload.get("h_wct_no")
        journeys = records(payload, "jrny_infos", "jrny_info")
        if not journeys:
            return [], wct_no

        return [Seat.from_response(seat) for seat in records(journeys[0], "seat_infos", "seat_info")], wct_no

    def create(
        self,
        train: Train,
        passengers: Sequence[Passenger] | None = None,
        option: ReserveOptionCode = ReserveOption.GENERAL_FIRST,
    ) -> Reservation:
        """열차를 예매합니다. 좌석이 없고 예약대기가 열려 있으면 대기를 겁니다.

        Raises:
            KorailError: 서버가 예매를 거부했거나(매진 등), 예매 후 예약을 다시
                조회하지 못했습니다.
        """
        if train.has_seat() or train.wait_reserve_flag < 0:
            reserving_seat = True
            is_special_seat = _SEATED_PREFERS_SPECIAL[option](train)
        else:
            # 좌석이 없고 예약대기가 열려 있는 열차 — 대기를 겁니다.
            reserving_seat = False
            is_special_seat = _WAITING_PREFERS_SPECIAL[option]

        reduced = Passenger.reduce(passengers or [AdultPassenger()])
        total_count = sum(p.count for p in reduced)

        url = API_ENDPOINTS["reserve"]
        headers, _ = self._api.sign(url)
        data = {
            **self._api.base_payload(),
            "txtMenuId": "11",
            "txtJobId": "1101" if reserving_seat else "1102",
            "txtGdNo": "",
            "hidFreeFlg": "N",
            "txtTotPsgCnt": total_count,
            "txtSeatAttCd1": "000",
            "txtSeatAttCd2": "000",
            "txtSeatAttCd3": "000",
            "txtSeatAttCd4": "015",
            "txtSeatAttCd5": "000",
            "txtStndFlg": "N",
            "txtSrcarCnt": "0",
            "txtJrnyCnt": "1",
            "txtJrnySqno1": "001",
            "txtJrnyTpCd1": "11",
            "txtDptDt1": train.dep_date,
            "txtDptRsStnCd1": train.dep_code,
            "txtDptTm1": train.dep_time,
            "txtArvRsStnCd1": train.arr_code,
            "txtTrnNo1": train.train_no,
            "txtRunDt1": train.run_date,
            "txtTrnClsfCd1": train.train_type,
            "txtTrnGpCd1": train.train_group,
            "txtPsrmClCd1": "2" if is_special_seat else "1",
            "txtChgFlg1": "",
            # 편도 예매라 2번째 여정 필드는 비워 보냅니다 (폼이 존재 자체를 요구합니다).
            "txtJrnySqno2": "",
            "txtJrnyTpCd2": "",
            "txtDptDt2": "",
            "txtDptRsStnCd2": "",
            "txtDptTm2": "",
            "txtArvRsStnCd2": "",
            "txtTrnNo2": "",
            "txtRunDt2": "",
            "txtTrnClsfCd2": "",
            "txtPsrmClCd2": "",
            "txtChgFlg2": "",
        }
        for index, passenger in enumerate(reduced, 1):
            data.update(passenger.get_dict(index))

        payload = self._api.get(url, params=data, headers=headers)
        self._api.check(payload)

        return self._reserved(payload)

    def create_with_seats(
        self,
        train: Train,
        seats: Sequence[CarSeat],
        passengers: Sequence[Passenger] | None = None,
    ) -> Reservation:
        """고른 좌석으로 열차를 예매합니다.

        좌석은 :meth:`TrainResource.seats <pykorail.resources.trains.TrainResource.seats>`
        가 돌려준 것을 넘깁니다. 객실(일반실 · 특실)은 좌석에 붙어 있어 따로 넘기지 않습니다.

        요청은 코레일+ 7.0.8 의 ``TicketReservationIn`` 을 폼으로 펼친 모양입니다 —
        :meth:`create` 의 폼과는 다릅니다. 앱의 좌석 선택 화면이 작업 구분을 좌석 지정으로
        두고 고른 좌석을 호차 번호 · 좌석 식별자 쌍으로 싣습니다.

        Args:
            train: :meth:`TrainResource.search <pykorail.resources.trains.TrainResource.search>`
                가 돌려준 열차.
            seats: 예매할 좌석. **승객 한 명에 하나씩**이어야 하고, 전부 같은 객실이어야 합니다.
                호차는 서로 달라도 됩니다.
            passengers: 생략하면 어른 1명.

        Raises:
            TypeError: 좌석이 아닌 것을 넘겼습니다.
            ValueError: 좌석 수가 승객 수와 다르거나, 같은 좌석을 두 번 넘겼거나, 객실이
                섞였거나, 열차에 예매에 필요한 값이 없습니다. 요청 전에 막습니다.
            KorailError: 서버가 예매를 거부했거나(이미 팔린 좌석 등), 예매 후 예약을 다시
                조회하지 못했습니다.
        """
        reduced = Passenger.reduce(passengers or [AdultPassenger()])
        total_count = sum(p.count for p in reduced)
        seat_class = self._seat_class_of(seats, total_count)

        # 값이 비면 without_blanks 가 그 칸을 통째로 빼서 다른 요청이 됩니다. 실제 좌석이
        # 걸린 요청이라 넘겨짚지 않고 여기서 멈춥니다. 이름은 사용자가 아는 Train 의 속성입니다.
        journey = {
            "train_no": train.train_no,
            "train_type": train.train_type,
            "train_group": train.train_group,
            "run_date": train.run_date,
            "dep_date": train.dep_date,
            "dep_time": train.dep_time,
            "dep_code": train.dep_code,
            "dep_cons_order": train.dep_cons_order,
            "dep_run_order": train.dep_run_order,
            "arr_code": train.arr_code,
            "arr_cons_order": train.arr_cons_order,
            "arr_run_order": train.arr_run_order,
        }
        missing = sorted(name for name, value in journey.items() if not value)
        if missing:
            raise ValueError(f"좌석 지정 예매에 필요한 값이 열차에 없습니다: {', '.join(missing)}")

        url = API_ENDPOINTS["reserve"]
        # 서명은 붙이되 Sid 는 싣지 않습니다 (앱의 요청 모델에 Sid 가 없습니다).
        headers, _ = self._api.sign(url, include_sid=False)
        # 필드의 순서는 앱이 요청 모델을 펼치는 순서입니다: 공통 → 예매 → 승객 → 여정 → 좌석.
        form: dict[str, Any] = {
            **self._api.common_payload(),
            "txtMenuId": "11",
            "txtJobId": _JOB_SEAT_DESIGNATED,
            "hidFreeFlg": "N",
            "txtStndFlg": "N",
            "txtTotPsgCnt": str(total_count),
            "txtSeatAttCd1": "000",
            "txtSeatAttCd2": "000",
            "txtSeatAttCd3": "000",
            "txtSeatAttCd4": "015",
            "txtSeatAttCd5": "000",
            "txtJrnyCnt": "1",
            # 호차 수가 아니라 고른 **좌석** 수입니다.
            "txtSrcarCnt": str(len(seats)),
        }
        for index, passenger in enumerate(reduced, 1):
            form[f"txtCompaCnt{index}"] = str(passenger.count)
            form[f"txtPsgTpCd{index}"] = passenger.typecode
            form[f"txtDiscKndCd{index}"] = passenger.discount_type
            form[f"txtCardNo_{index}"] = passenger.card_no
        form.update(
            {
                "txtJrnyTpCd1": "11",
                "txtJrnySqno1": "001",
                # 열차번호는 조회가 준 그대로입니다. 앱도 가공하지 않습니다.
                "txtTrnNo1": journey["train_no"],
                "txtTrnClsfCd1": journey["train_type"],
                "txtTrnGpCd1": journey["train_group"],
                "txtRunDt1": journey["run_date"],
                "txtDptDt1": journey["dep_date"],
                "txtDptTm1": journey["dep_time"],
                "txtDptRsStnCd1": journey["dep_code"],
                "txtDptStnConsOrdr1": journey["dep_cons_order"],
                "txtDptStnRunOrdr1": journey["dep_run_order"],
                "txtArvRsStnCd1": journey["arr_code"],
                "txtArvStnConsOrdr1": journey["arr_cons_order"],
                "txtArvStnRunOrdr1": journey["arr_run_order"],
                "txtChgFlg1": "N",
                "txtPsrmClCd1": seat_class,
            }
        )
        for index, seat in enumerate(seats, 1):
            # 서버가 준 호차 번호("0003")와 좌석 식별자("57")를 그대로 돌려보냅니다.
            form[f"txtSrcarNo{index}"] = seat.car_no
            form[f"txtSeatNo{index}"] = seat.seat_no

        payload = self._api.post(url, data=without_blanks(form), headers=headers)
        self._api.check(payload)

        return self._reserved(payload)

    @staticmethod
    def _seat_class_of(seats: Sequence[CarSeat], total_count: int) -> str:
        """고른 좌석들을 검사하고 그 객실 구분 코드를 돌려줍니다."""
        if not all(isinstance(seat, CarSeat) for seat in seats):
            # 배정 좌석(Seat)처럼 이름이 비슷한 것을 넘기면 속성 오류로는 원인을 알기 어렵습니다.
            raise TypeError("seats 에는 trains.seats() 가 돌려준 CarSeat 를 넘기세요")
        if total_count < 1:
            # 인원이 0 인 승객만 넘기면 합쳐지며 전부 버려집니다. 좌석 0개와 맞아떨어져
            # 아래 검사를 지나치지 않게 먼저 막습니다.
            raise ValueError("승객이 한 명 이상이어야 합니다")
        if len(seats) != total_count:
            raise ValueError(f"좌석은 승객 한 명에 하나씩 넘기세요: 좌석 {len(seats)}개, 승객 {total_count}명")
        if len({(seat.car_no, seat.seat_no) for seat in seats}) != len(seats):
            raise ValueError("같은 좌석을 두 번 넘겼습니다")
        if any(not seat.car_no or not seat.seat_no for seat in seats):
            raise ValueError("호차 번호나 좌석 식별자가 빈 좌석이 있습니다")
        classes = {seat.seat_class for seat in seats}
        if len(classes) != 1 or "" in classes:
            raise ValueError(f"좌석은 전부 같은 객실이어야 합니다: {sorted(classes)}")
        return classes.pop()

    def _reserved(self, payload: dict[str, Any]) -> Reservation:
        """예매 응답의 예약번호로 예약을 다시 조회해 돌려줍니다."""
        rsv_id = payload.get("h_pnr_no")
        reservation = self.find(rsv_id)
        if reservation is None:
            raise KorailError(f"예매는 성공했지만 예약({rsv_id})을 다시 조회하지 못했습니다")
        return reservation

    def pay(self, reservation: Reservation, card: Card) -> None:
        """신용카드로 결제해 예약을 승차권으로 확정합니다.

        Args:
            reservation: 결제할 예약. :attr:`~pykorail.models.reservation.Reservation.wct_no`
                가 채워져 있어야 합니다 (:meth:`all`/:meth:`find` 가 채워 줍니다).
            card: 결제 수단 (:class:`~pykorail.models.card.Card`).

        Raises:
            KorailError: 결제가 거부됐습니다.
        """
        if not isinstance(reservation, Reservation):
            raise TypeError("reservation must be a Reservation instance")
        if not isinstance(card, Card):
            raise TypeError("card must be a Card instance")

        payload = self._api.post(
            API_ENDPOINTS["pay"],
            data={
                **self._api.base_payload(),
                "hidPnrNo": reservation.rsv_id,
                "hidWctNo": reservation.wct_no,
                "hidTmpJobSqno1": "000000",
                "hidTmpJobSqno2": "000000",
                "hidRsvChgNo": "000",
                "hidInrecmnsGridcnt": "1",
                "hidStlMnsSqno1": "1",
                "hidStlMnsCd1": "02",
                "hidMnsStlAmt1": str(reservation.price),
                "hidCrdInpWayCd1": "@",
                "hidStlCrCrdNo1": card.number,
                "hidVanPwd1": card.password,
                "hidCrdVlidTrm1": card.expire,
                "hidIsmtMnthNum1": card.installment,
                "hidAthnDvCd1": card.auth_type,
                "hidAthnVal1": card.verify_number,
                "hiduserYn": "Y",
            },
        )
        self._api.check(payload)

    def cancel(self, reservation: Reservation) -> None:
        """예약을 취소합니다.

        Raises:
            KorailError: 서버가 취소를 거부했습니다.
        """
        if not isinstance(reservation, Reservation):
            raise TypeError("reservation must be a Reservation instance")

        payload = self._api.post(
            API_ENDPOINTS["cancel"],
            data={
                **self._api.base_payload(),
                "txtPnrNo": reservation.rsv_id,
                "txtJrnySqno": reservation.journey_no,
                "txtJrnyCnt": reservation.journey_cnt,
                "hidRsvChgNo": reservation.rsv_chg_no,
            },
        )
        self._api.check(payload)
