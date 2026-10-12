"""조회·예매 옵션 코드.

``Enum`` 이 아니라 문자열 상수인 것은 의도적입니다 — 이 값들은 폼 필드에 그대로
실려 나가는데, ``str`` 을 섞은 ``Enum`` 은 파이썬 버전에 따라 ``str()`` 결과가
``"TrainType.KTX"`` 로 나와 전송 값이 조용히 깨집니다.

대신 :data:`TrainTypeCode` · :data:`ReserveOptionCode` 같은 리터럴 별칭으로 오타를
정적으로 잡습니다 — ``train_type="999"`` 는 타입 검사에서 걸립니다.
"""

from __future__ import annotations

from typing import Final, Literal

#: 유효한 열차 종별 코드. :class:`TrainType` 의 상수들이 이 집합을 이룹니다.
TrainTypeCode = Literal["100", "101", "102", "103", "104", "105", "109"]

#: 유효한 특실/일반실 선택 전략.
ReserveOptionCode = Literal["GENERAL_FIRST", "GENERAL_ONLY", "SPECIAL_FIRST", "SPECIAL_ONLY"]

#: 유효한 객실 구분 코드.
SeatClassCode = Literal["1", "2"]

#: 유효한 마일리지 종류 코드.
MileageTypeCode = Literal["1", "2"]

#: 유효한 마일리지 내역 구분 코드.
MileageInquiryCode = Literal["0", "1", "2"]


class TrainType:
    """``selGoTrain``/``txtTrnGpCd`` 열차 종별 코드.

    KTX 와 KTX-산천은 같은 코드(``100``)를 씁니다 — 별칭이지 오타가 아닙니다.
    """

    KTX: Final = "100"
    KTX_SANCHEON: Final = "100"
    SAEMAEUL: Final = "101"
    ITX_SAEMAEUL: Final = "101"
    MUGUNGHWA: Final = "102"
    NURIRO: Final = "102"
    TONGGUEN: Final = "103"
    ITX_CHEONGCHUN: Final = "104"
    AIRPORT: Final = "105"
    ALL: Final = "109"


class ReserveOption:
    """특실/일반실 선택 전략."""

    GENERAL_FIRST: Final = "GENERAL_FIRST"
    GENERAL_ONLY: Final = "GENERAL_ONLY"
    SPECIAL_FIRST: Final = "SPECIAL_FIRST"
    SPECIAL_ONLY: Final = "SPECIAL_ONLY"


class SeatClass:
    """객실 구분 코드 (``psrmClCd``). 호차·좌석 조회에 그대로 실립니다."""

    GENERAL: Final = "1"
    SPECIAL: Final = "2"


class MileageType:
    """마일리지 종류 코드 (``pontTpVal``). 내역을 볼 장부를 고릅니다.

    코레일+ 7.0.8 의 ``MileageType`` 이 서버로 보내는 값입니다.
    """

    KTX: Final = "1"
    RAIL_POINT: Final = "2"


class MileageInquiry:
    """마일리지 내역 구분 코드 (``qryDvVal``). 앱의 "조회 유형"입니다.

    코레일+ 7.0.8 의 ``MileageInquiryType`` 이 서버로 보내는 값입니다.
    """

    ALL: Final = "0"
    SAVE: Final = "1"
    USE: Final = "2"
