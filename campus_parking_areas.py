"""NSYSU area names and capacities transcribed from user's 115-02-23 campus map.

The geographical inventory is reference data; all generated stays are fictional.
Hourly rates are intentionally simplified Miniworld values, NOT official fees.
"""
from __future__ import annotations

# (map number, location label on 115-02-23 map, parking spaces)
CAR_AREAS = [
    (1, '西子灣停車場(來賓)', 48),
    (2, '國研大樓地下停車場', 20),
    (3, '國研大樓停車場(來賓)', 18),
    (4, '海堤停車場(來賓)', 65),
    (5, '行政大樓前(理學院側)', 32),
    (6, '行政大樓前(社科院側)', 44),
    (7, '理工大樓旁', 50),
    (8, '實習工廠旁', 4),
    (9, '理工二道', 67),
    (10, '電資大樓前(理工三道)', 39),
    (11, '電資大樓後(含斜坡)', 32),
    (12, '社科院及幼稚園間', 10),
    (13, '社科院旁', 24),
    (14, '舊管院旁', 38),
    (15, '新管院旁', 27),
    (16, '國資大樓後方', 23),
    (17, '活動中心前', 27),
    (18, '海工大隧道停車場', 30),
    (19, '海工館後方', 18),
    (20, '海資館前方', 13),
    (21, '海資館後方', 10),
    (22, '海科院前方', 28),
    (23, '海科院旁及後方', 56),
    (24, '文學院地下停車場', 33),
    (25, '文學院前方', 14),
    (26, '文藝大樓坡道', 19),
    (27, '文藝大樓停車場', 30),
    (28, '教職員宿舍', 51),
]

MOTORCYCLE_AREAS = [
    (1, '翠亨道兩側機車停放區', 1378),
    (2, '武嶺宿舍米羅廣場', 519),
    (3, '翠亨道西側入口區', 48),
    (4, '翠亭宿舍後方', 160),
    (5, 'L棟機車停車場', 996),
    (6, '生態步道區(來賓)', 222),
    (7, '活動中心前路橋下', 431),
    (8, '360藝文空間後方路橋下', 544),
    (9, '海工機車停車場', 236),
    (10, '海科院機車停車場', 297),
    (11, '海科院機車停車場(來賓)', 28),
    (12, '海科院造波池旁', 69),
    (13, '文學院機車停車場(大)', 423),
    (14, '文學院機車停車場(小)', 55),
    (15, '文藝大樓東側管道', 123),
    (16, '國研機車停車場(來賓)', 268),
    (17, '海堤機車停車場(來賓)', 266),
    (18, '室外籃球場旁(來賓)', 68),
    (19, '單槓場旁(來賓)', 52),
    (20, '網球場旁(來賓)', 113),
    (21, '司令台後方游泳池前(來賓)', 10),
]

# The school's visitor parking page specifically lists these four motorcycle
# areas as public guest lots; other red-labelled sites may have conditions.
CAR_VISITOR_NUMBERS = frozenset((1, 3, 4))
MOTORCYCLE_VISITOR_NUMBERS = frozenset((6, 11, 16, 17))
CAR_STUDENT_PERMIT_NUMBERS = frozenset((4,))  # university rule: student cars -> seaside area

assert len(CAR_AREAS) == 28 and sum(x[2] for x in CAR_AREAS) == 870
assert len(MOTORCYCLE_AREAS) == 21 and sum(x[2] for x in MOTORCYCLE_AREAS) == 6306
