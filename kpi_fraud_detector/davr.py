# -*- coding: utf-8 -*-
"""Yarim oy (bi-monthly) davr hisoblari."""
import calendar
from dataclasses import dataclass
from datetime import date, timedelta

from config import HISTORY_DAYS, OXIRGI_KUN_SONI, OY_NOMLARI, WINDOW_DAYS


@dataclass
class Davr:
    oy: int
    yil: int
    yarim: int          # 1 yoki 2
    boshi: date         # yarim boshlanishi
    oxiri: date         # yarim tugashi
    oyna_boshi: date    # oxirgi N kun oynasi boshi
    oyna_oxiri: date    # = oxiri
    tarix_boshi: date   # mijoz o'rtachasi uchun tarix boshi
    yirik_boshi: date   # 3-varaq ("Oxirgi N kun yirik") boshi

    @property
    def nomi(self) -> str:
        return "%s %d · Y%d" % (OY_NOMLARI[self.oy - 1], self.yil, self.yarim)

    @property
    def oyna_kunlari(self):
        n = (self.oyna_oxiri - self.oyna_boshi).days + 1
        return [self.oyna_boshi + timedelta(days=i) for i in range(n)]

    def oyna_ichidami(self, d: date) -> bool:
        return self.oyna_boshi <= d <= self.oyna_oxiri

    def yarim_ichidami(self, d: date) -> bool:
        return self.boshi <= d <= self.oxiri


def davr_yasa(oy: int, yil: int, yarim: int,
              oyna_kun: int = None, tarix_kun: int = None) -> Davr:
    if yarim not in (1, 2):
        raise ValueError("yarim 1 yoki 2 bo'lishi kerak")
    oyna_kun = oyna_kun or WINDOW_DAYS
    if tarix_kun is None:
        tarix_kun = HISTORY_DAYS

    oy_oxiri = calendar.monthrange(yil, oy)[1]
    if yarim == 1:
        boshi, oxiri = date(yil, oy, 1), date(yil, oy, 15)
    else:
        boshi, oxiri = date(yil, oy, 16), date(yil, oy, oy_oxiri)

    oyna_boshi = max(boshi, oxiri - timedelta(days=oyna_kun - 1))
    # Mijoz o'rtachasi uchun tarix: 0 bo'lsa — oy boshidan
    tarix_boshi = (oxiri - timedelta(days=tarix_kun - 1)) if tarix_kun else date(yil, oy, 1)
    tarix_boshi = min(tarix_boshi, oyna_boshi)

    yirik_boshi = max(oyna_boshi, oxiri - timedelta(days=OXIRGI_KUN_SONI - 1))

    return Davr(oy=oy, yil=yil, yarim=yarim, boshi=boshi, oxiri=oxiri,
                oyna_boshi=oyna_boshi, oyna_oxiri=oxiri, tarix_boshi=tarix_boshi,
                yirik_boshi=yirik_boshi)
