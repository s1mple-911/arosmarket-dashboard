# -*- coding: utf-8 -*-
"""Aros API klienti — orders (pagination + rate limit + retry)."""
import time
from datetime import date, datetime, timedelta

import requests
from requests.auth import HTTPBasicAuth

from config import (AROS_API_BASE, AROS_LOGIN, AROS_PAGE_SIZE, AROS_PASSWORD,
                    DISPLAY_TO_AROS_WID, HTTP_RETRY, HTTP_TIMEOUT,
                    RATE_LIMIT_SEC, UZB_TZ)


class ArosAuthError(RuntimeError):
    pass


class ArosClient:
    def __init__(self, login: str = None, password: str = None, verbose: bool = True):
        self.login = login if login is not None else AROS_LOGIN
        self.password = password if password is not None else AROS_PASSWORD
        self.verbose = verbose
        self.s = requests.Session()
        self.s.auth = HTTPBasicAuth(self.login, self.password)
        self.s.headers["Accept"] = "application/json"
        self._last_call = 0.0

    # -- ichki ---------------------------------------------------------------
    def _wait(self):
        dt = time.time() - self._last_call
        if dt < RATE_LIMIT_SEC:
            time.sleep(RATE_LIMIT_SEC - dt)
        self._last_call = time.time()

    def _get(self, url: str, params: dict = None) -> dict:
        last_err = None
        for urinish in range(1, HTTP_RETRY + 1):
            self._wait()
            try:
                r = self.s.get(url, params=params, timeout=HTTP_TIMEOUT)
            except requests.RequestException as e:
                last_err = e
                time.sleep(1.5 * urinish)
                continue
            if r.status_code in (401, 403):
                raise ArosAuthError(
                    "Aros API auth xato (HTTP %d). .env dagi AROS_LOGIN/AROS_PASSWORD ni tekshiring. "
                    "Javob: %s" % (r.status_code, r.text[:200]))
            if r.status_code == 429 or r.status_code >= 500:
                last_err = RuntimeError("HTTP %d: %s" % (r.status_code, r.text[:200]))
                time.sleep(2.0 * urinish)
                continue
            if not r.ok:
                raise RuntimeError("HTTP %d: %s" % (r.status_code, r.text[:300]))
            return r.json()
        raise RuntimeError("So'rov bajarilmadi (%d urinish): %s" % (HTTP_RETRY, last_err))

    # -- ommaviy -------------------------------------------------------------
    def tekshir(self) -> bool:
        """Auth ishlayaptimi — 1 ta yengil so'rov."""
        self._get(AROS_API_BASE + "/api/admin/orders/", {"page": 1, "page_size": 1})
        return True

    def orders(self, warehouse_id: int, sana_dan: date, sana_gacha: date):
        """Bitta filialning [sana_dan .. sana_gacha] (ikkisi ham kiritiladi)
        oralig'idagi barcha orderlari. Pagination `next` bo'yicha yuriladi."""
        wid = DISPLAY_TO_AROS_WID.get(int(warehouse_id), int(warehouse_id))
        params = {
            "page": 1,
            "page_size": AROS_PAGE_SIZE,
            "warehouse": wid,
            "created_datetime_after": sana_dan.isoformat(),
            # `before` chegarasi qat'iy bo'lishi mumkin — 1 kun qo'shib olamiz,
            # keyin mahalliy sana bo'yicha filtrlaymiz
            "created_datetime_before": (sana_gacha + timedelta(days=1)).isoformat(),
        }
        url = AROS_API_BASE + "/api/admin/orders/"
        natija, sahifa = [], 1
        while True:
            # 1-sahifa: params bilan. Keyingilari: `next` URL'ida params bor.
            data = self._get(url, params) if sahifa == 1 else self._get(url)
            results = data.get("results") or []
            natija.extend(results)
            nxt = data.get("next")
            if not nxt:
                break
            url, sahifa = nxt, sahifa + 1
            if sahifa > 500:  # xavfsizlik cheklovi
                break
        # mahalliy sana bo'yicha aniq filtr
        return [o for o in natija
                if sana_dan <= order_sanasi(o) <= sana_gacha] if natija else []


# --- yordamchilar -----------------------------------------------------------
def order_vaqti(o: dict) -> datetime:
    """created_datetime -> Toshkent vaqtidagi datetime."""
    s = (o or {}).get("created_datetime") or ""
    if not s:
        return datetime(1970, 1, 1, tzinfo=UZB_TZ)
    s = s.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return datetime(1970, 1, 1, tzinfo=UZB_TZ)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UZB_TZ)
    return dt.astimezone(UZB_TZ)


def order_sanasi(o: dict) -> date:
    return order_vaqti(o).date()


def order_summasi(o: dict) -> float:
    for key in ("total_price", "total_amount"):
        v = (o or {}).get(key)
        if v not in (None, ""):
            try:
                return float(v)
            except (TypeError, ValueError):
                pass
    pay = (o or {}).get("payment") or {}
    try:
        return float(pay.get("total_amount") or 0)
    except (TypeError, ValueError):
        return 0.0


def order_mijozi(o: dict) -> dict:
    u = (o or {}).get("user") or {}
    ism = ((u.get("first_name") or "") + " " + (u.get("last_name") or "")).strip()
    return {
        "id": u.get("id"),
        "ism": ism or "Noma'lum",
        "telefon": u.get("username") or "",
        "rol": u.get("role") or "",
    }
