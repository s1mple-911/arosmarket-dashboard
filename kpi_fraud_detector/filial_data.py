# -*- coding: utf-8 -*-
"""Filial ro'yxati + yarim plan/bajarildi.

Manbalar (ustuvorlik bo'yicha):
  1. PostgreSQL `cache_filial`  — PG_DSN berilgan bo'lsa
  2. n8n webhook'lar (auth talab qilmaydi):
       aros-filial-plan-list  -> filiallar ro'yxati + yarim planlar
       aros-cache-filial      -> plan / qoldi / foiz (bajarildi = plan - qoldi)
"""
import time
from dataclasses import dataclass

import requests

from config import (HTTP_TIMEOUT, MIN_HALF_PLAN, N8N_FILIAL_CACHE,
                    N8N_FILIAL_PLAN_LIST, PG_DSN, RATE_LIMIT_SEC,
                    SKIP_FILIAL_NAMES, bugun_uzb)


@dataclass
class Filial:
    warehouse_id: int
    nomi: str
    profil: str = ""
    plan: float = 0.0        # yarim plan
    bajarildi: float = 0.0   # yarim bajarildi (orders - returns)
    foiz: float = 0.0

    def foiz_hisobla(self, bajarildi: float = None) -> float:
        b = self.bajarildi if bajarildi is None else bajarildi
        if not self.plan:
            return 0.0
        return b / self.plan * 100.0


# ---------------------------------------------------------------- n8n manbai
def _get_json(url, params=None):
    r = requests.get(url, params=params, timeout=HTTP_TIMEOUT)
    r.raise_for_status()
    txt = (r.text or "").strip()
    if not txt:
        return {}
    try:
        return r.json()
    except ValueError:
        return {}


def filiallar_royxati(oy: int, yil: int, yarim: int, log=print):
    """Filiallar ro'yxati (ombor/xizmat nuqtalari chiqarib tashlanadi).

    `aros-filial-plan-list` faqat JORIY oy uchun to'liq to'ldirilgan bo'ladi —
    o'tgan oylar uchun bo'sh qaytsa, ro'yxatni joriy oydan olamiz (plan/bajarildi
    baribir `aros-cache-filial` dan kerakli davr uchun qayta yoziladi)."""
    data = _get_json(N8N_FILIAL_PLAN_LIST, {"oy": oy, "yil": yil})
    xom = data.get("filiallar") or []
    if len(xom) < 5:
        b = bugun_uzb()
        data = _get_json(N8N_FILIAL_PLAN_LIST, {"oy": b.month, "yil": b.year})
        xom = data.get("filiallar") or []
        log("  ! %02d.%d uchun plan ro'yxati bo'sh — ro'yxat %02d.%d dan olindi"
            % (oy, yil, b.month, b.year))
    korilgan, natija = set(), []
    for f in xom:
        wid = f.get("warehouse_id")
        if wid is None or wid in korilgan:
            continue
        korilgan.add(wid)
        nomi = (f.get("filial") or "").strip()
        if nomi.lower() in SKIP_FILIAL_NAMES:
            continue
        yarim_plan = 0.0
        try:
            yarim_plan = float(((f.get("yarim") or {}).get(str(yarim)) or {}).get("plan") or 0)
        except (TypeError, ValueError):
            yarim_plan = 0.0
        natija.append(Filial(warehouse_id=int(wid), nomi=nomi,
                             profil=f.get("profil") or "", plan=yarim_plan))
    natija.sort(key=lambda x: x.nomi)
    return natija


def filial_kpi_n8n(fil: Filial, oy: int, yil: int, yarim: int) -> Filial:
    """aros-cache-filial dan plan/bajarildi/foiz to'ldiriladi."""
    try:
        d = _get_json(N8N_FILIAL_CACHE, {"wid": fil.warehouse_id, "oy": oy,
                                         "yil": yil, "yarim": yarim})
    except requests.RequestException:
        return fil
    if not isinstance(d, dict) or d.get("plan") in (None, ""):
        return fil

    def num(v):
        try:
            return float(v)
        except (TypeError, ValueError):
            return 0.0

    plan = num(d.get("plan"))
    qoldi = num(d.get("qoldi"))
    foiz = num(d.get("foiz"))
    prognoz = num(d.get("prognoz"))
    if plan > 0:
        fil.plan = plan
    # bajarildi: `prognoz` = yig'ilgan summa (plan - qoldi bilan bir xil, lekin
    # plan oshib bajarilganda qoldi=0 bo'lib qoladi — shuning uchun prognoz asosiy)
    if prognoz > 0:
        fil.bajarildi = prognoz
    elif d.get("qoldi") not in (None, "") and plan > 0:
        fil.bajarildi = max(0.0, plan - qoldi)
    else:
        fil.bajarildi = max(0.0, fil.plan * foiz / 100.0)
    fil.foiz = foiz if foiz else round(fil.foiz_hisobla(), 1)
    if d.get("filial"):
        fil.nomi = d["filial"]
    return fil


# ----------------------------------------------------------- PostgreSQL manbai
def _pg_rows(oy: int, yil: int, yarim: int):
    import psycopg2  # type: ignore
    import psycopg2.extras  # type: ignore

    sql = """
        SELECT warehouse_id::text AS wid,
               oy_yarim,
               (data->>'plan')::numeric      AS plan,
               (data->>'bajarildi')::numeric AS bajarildi,
               (data->>'foiz')::int          AS foiz,
               (data->>'filial')::text       AS filial_nomi
          FROM cache_filial
         WHERE oy_yarim = %s
    """
    with psycopg2.connect(PG_DSN) as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (yarim,))
            return cur.fetchall()


def filiallar_pg(oy: int, yil: int, yarim: int):
    natija = []
    for r in _pg_rows(oy, yil, yarim):
        try:
            wid = int(r["wid"])
        except (TypeError, ValueError):
            continue
        nomi = (r.get("filial_nomi") or "").strip()
        if nomi.lower() in SKIP_FILIAL_NAMES:
            continue
        plan = float(r.get("plan") or 0)
        if plan < MIN_HALF_PLAN:
            continue
        bajarildi = float(r.get("bajarildi") or 0)
        f = Filial(warehouse_id=wid, nomi=nomi or ("Filial %d" % wid),
                   plan=plan, bajarildi=bajarildi,
                   foiz=float(r.get("foiz") or 0))
        if not f.foiz:
            f.foiz = f.foiz_hisobla()
        natija.append(f)
    natija.sort(key=lambda x: x.nomi)
    return natija


# ----------------------------------------------------------------- umumiy API
def filiallar_yukla(oy: int, yil: int, yarim: int, faqat_wid=None, log=print):
    """Filiallar + plan/bajarildi. faqat_wid — warehouse_id ro'yxati (ixtiyoriy)."""
    manba = "n8n"
    filiallar = []
    if PG_DSN:
        try:
            filiallar = filiallar_pg(oy, yil, yarim)
            manba = "postgres (cache_filial)"
        except Exception as e:  # psycopg2 yo'q / ulanmadi -> n8n ga qaytamiz
            log("  ! PostgreSQL o'qilmadi (%s) — n8n webhook'ga o'tildi" % str(e)[:120])
            filiallar = []
    if not filiallar:
        filiallar = filiallar_royxati(oy, yil, yarim, log=log)
        manba = "n8n webhook"
        if faqat_wid:
            wanted = {int(w) for w in faqat_wid}
            filiallar = [f for f in filiallar if f.warehouse_id in wanted]
        for f in filiallar:
            filial_kpi_n8n(f, oy, yil, yarim)
            time.sleep(RATE_LIMIT_SEC)
        # KPI filiali emaslarni (ombor, yopilgan nuqta) shu davr plani bo'yicha chiqaramiz
        filiallar = [f for f in filiallar if f.plan >= MIN_HALF_PLAN]
    elif faqat_wid:
        wanted = {int(w) for w in faqat_wid}
        filiallar = [f for f in filiallar if f.warehouse_id in wanted]
    log("  Filial manbai: %s · %d ta filial" % (manba, len(filiallar)))
    return filiallar
