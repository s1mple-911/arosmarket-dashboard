# -*- coding: utf-8 -*-
"""Order detali — yakunlanish sanasi (`completed_at`) va vozvrat ma'lumoti.

Nega kerak:
  * Orders LIST javobida `completed_at` YO'Q va API uni filtrlay olmaydi —
    faqat `/api/admin/orders/{id}/` da bor. KPI esa order YAKUNLANGAN kun
    bo'yicha hisoblanadi (31-da tushib 1-da yakunlangan order iyulga kirmaydi).
  * Vozvrat ma'lumoti ham shu javobda: `return_amount`, `returned_at`,
    `products[].working_return_quantity / broken_return_quantity`.

Bitta so'rov ikkala ehtiyojni ham qoplaydi. Natijalar diskda keshlanadi.
"""
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from pathlib import Path

import requests
from requests.auth import HTTPBasicAuth

from config import (AROS_API_BASE, AROS_LOGIN, AROS_PASSWORD, DETAL_THREADS,
                    HTTP_TIMEOUT)

# Vozvrat order sanasidan keyingi necha kun ichida qidiriladi
VOZVRAT_OYNA_KUN = 30

_yerli = threading.local()


def _sessiya():
    s = getattr(_yerli, "s", None)
    if s is None:
        s = requests.Session()
        s.auth = HTTPBasicAuth(AROS_LOGIN, AROS_PASSWORD)
        s.headers["Accept"] = "application/json"
        _yerli.s = s
    return s


def sana_ol(s):
    if not s:
        return None
    try:
        return date.fromisoformat(str(s)[:10])
    except ValueError:
        return None


def order_detali(order_id: int) -> dict:
    """Bitta order uchun kerakli maydonlar (3 marta urinadi)."""
    url = AROS_API_BASE + "/api/admin/orders/%d/" % int(order_id)
    oxirgi = None
    for urinish in range(3):
        try:
            r = _sessiya().get(url, timeout=HTTP_TIMEOUT)
            if r.status_code >= 500 or r.status_code == 429:
                oxirgi = "HTTP %d" % r.status_code
                continue
            r.raise_for_status()
            d = r.json()
            break
        except Exception as e:
            oxirgi = str(e)[:120]
    else:
        raise RuntimeError("order #%s detali olinmadi: %s" % (order_id, oxirgi))

    prods = d.get("products") or []

    def son(v):
        try:
            return float(v or 0)
        except (TypeError, ValueError):
            return 0.0

    vozvrat = son(d.get("return_amount"))
    if vozvrat <= 0:
        for p in prods:
            qty = (p.get("working_return_quantity") or 0) + \
                  (p.get("broken_return_quantity") or 0)
            if qty:
                vozvrat += qty * son(p.get("selling_price"))

    # asl (vozvratdan oldingi) summa — mahsulotlar yig'indisi eng ishonchli
    asl = sum(son(p.get("total_price")) for p in prods)
    if asl <= 0:
        pay = d.get("payment") or {}
        asl = son(pay.get("original_amount")) or son(pay.get("total_amount"))

    return {
        "status": d.get("status") or "",
        "yakun": (d.get("completed_at") or "")[:10],
        "vozvrat_summa": vozvrat,
        "vozvrat_sana": (d.get("returned_at") or "")[:10],
        "asl_summa": asl,
    }


class DetalKesh:
    """order_id -> detal ma'lumoti, diskda saqlanadi."""

    def __init__(self, fayl: Path):
        self.fayl = Path(fayl)
        self.data = {}
        self._lock = threading.Lock()
        if self.fayl.exists():
            try:
                self.data = json.loads(self.fayl.read_text(encoding="utf-8"))
            except (ValueError, OSError):
                self.data = {}

    def saqla(self):
        self.fayl.parent.mkdir(parents=True, exist_ok=True)
        self.fayl.write_text(json.dumps(self.data, ensure_ascii=False),
                             encoding="utf-8")

    def bor(self, order_id):
        return str(order_id) in self.data

    def ol(self, order_id):
        return self.data.get(str(order_id))

    def toldir(self, order_idlar, log=None, xabar=""):
        """Keshda yo'qlarini parallel yuklab oladi. Nechta yangi olingani."""
        kerak = [oid for oid in order_idlar if not self.bor(oid)]
        if not kerak:
            return 0
        if log:
            log("      %s%d ta order detali olinmoqda..." % (xabar, len(kerak)))

        xatolar = [0]

        def ish(oid):
            try:
                return oid, order_detali(oid)
            except Exception:
                xatolar[0] += 1
                return oid, None

        with ThreadPoolExecutor(max_workers=DETAL_THREADS) as ex:
            for oid, natija in ex.map(ish, kerak):
                if natija is not None:
                    with self._lock:
                        self.data[str(oid)] = natija
        self.saqla()
        if log and xatolar[0]:
            log("      ! %d ta order detali olinmadi" % xatolar[0])
        return len(kerak) - xatolar[0]


# --------------------------------------------------------------- vozvrat
def vozvrat_holati(detal: dict, order_sanasi_: date, asl_zaxira: float = 0.0):
    """(matn, foiz, sana, ball) — BRIEF v3 qoidalari.

    `returned_at` ba'zan bo'sh bo'ladi (qisman vozvratlarda) — bunday holatda
    vozvrat baribir hisobga olinadi, faqat sana ko'rsatilmaydi.
    """
    if not detal:
        return "hali ma'lum emas", None, "", 0

    summa = float(detal.get("vozvrat_summa") or 0)
    if summa <= 0:
        return "YO'Q", 0.0, "", 0

    vsana = sana_ol(detal.get("vozvrat_sana"))
    if vsana is not None:
        # 30 kunlik oyna faqat sana ma'lum bo'lganda tekshiriladi
        if vsana < order_sanasi_ or vsana > order_sanasi_ + timedelta(days=VOZVRAT_OYNA_KUN):
            return "YO'Q", 0.0, "", 0

    asl = float(detal.get("asl_summa") or 0) or asl_zaxira
    if asl <= 0:
        return "hali ma'lum emas", None, (vsana.isoformat() if vsana else ""), 0

    foiz = min(100.0, summa / asl * 100.0)
    sana_matn = vsana.isoformat() if vsana else ""
    if foiz >= 95:
        return "HA (to'liq)", foiz, sana_matn, 50
    if foiz >= 50:
        return "QISMAN (%.0f%%)" % foiz, foiz, sana_matn, 30
    if foiz >= 20:
        return "QISMAN (%.0f%%)" % foiz, foiz, sana_matn, 15
    if foiz > 0:
        return "QISMAN (%.0f%%)" % foiz, foiz, sana_matn, 0
    return "YO'Q", 0.0, "", 0
