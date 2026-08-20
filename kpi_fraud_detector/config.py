# -*- coding: utf-8 -*-
"""Konfiguratsiya — .env dan o'qiladi."""
import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# --- .env yuklash (python-dotenv bo'lmasa ham ishlaydi) ---------------------
def _load_env():
    env_path = BASE_DIR / ".env"
    if not env_path.exists():
        return
    try:
        from dotenv import load_dotenv  # type: ignore
        load_dotenv(env_path, override=False)
        return
    except ImportError:
        pass
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_env()

# --- Aros API ---------------------------------------------------------------
AROS_API_BASE = os.getenv("AROS_API_BASE", "https://api.aros.uz").rstrip("/")
AROS_LOGIN = os.getenv("AROS_LOGIN", "")
AROS_PASSWORD = os.getenv("AROS_PASSWORD", "")
AROS_PAGE_SIZE = int(os.getenv("AROS_PAGE_SIZE", "200"))
RATE_LIMIT_SEC = float(os.getenv("AROS_RATE_LIMIT", "0.3"))
HTTP_TIMEOUT = int(os.getenv("HTTP_TIMEOUT", "60"))
HTTP_RETRY = int(os.getenv("HTTP_RETRY", "3"))

# --- n8n webhook'lar (filial plan/bajarildi manbai, auth talab qilmaydi) ----
N8N_BASE = os.getenv("N8N_BASE", "https://n8n.arosmarket.com/webhook").rstrip("/")
N8N_FILIAL_CACHE = N8N_BASE + "/aros-cache-filial"      # ?wid&oy&yil&yarim
N8N_FILIAL_PLAN_LIST = N8N_BASE + "/aros-filial-plan-list"  # ?oy&yil

# --- PostgreSQL (ixtiyoriy — cache_filial to'g'ridan-to'g'ri o'qish) --------
PG_DSN = os.getenv("PG_DSN", "").strip()

# --- Vaqt zonasi ------------------------------------------------------------
UZB_TZ = timezone(timedelta(hours=5))

# --- KPI biznes qoidalari ---------------------------------------------------
# Bonus sakraydigan chegaralar
THRESHOLDS = [60, 70, 80, 90, 100, 105, 110, 115, 120, 125, 130]

# filial_foiz -> (kpi %, boshqaruv %)  — hisobotda ma'lumot uchun
KPI_TABLE = [
    (130, 1.15, 0.31),
    (125, 1.10, 0.31),
    (120, 1.00, 0.31),
    (115, 0.95, 0.31),
    (110, 0.90, 0.31),
    (105, 0.85, 0.31),
    (100, 0.80, 0.31),
    (90, 0.70, 0.21),
    (80, 0.60, 0.11),
    (70, 0.50, 0.05),
    (60, 0.40, 0.03),
]

# --- Ball / daraja chegaralari ---------------------------------------------
# Maksimal ball = 100 (barcha 9 signal to'liq ishlaganda)
MAX_BALL = 100
BALL_YUQORI = int(os.getenv("BALL_YUQORI", "50"))   # maksimalning yarmi
BALL_ORTA = int(os.getenv("BALL_ORTA", "33"))       # maksimalning uchdan biri

# --- Ball profili -----------------------------------------------------------
# "brief"  — BRIEF'dagi ballar aynan (nasiya +25, har qanday order chegara
#            zonasida bo'lsa +20). Real ma'lumotda juda shovqinli.
# "kalibr" — real ma'lumotga moslangan (default):
#            * chegara signali orderning O'Z hissasiga bog'lanadi
#            * nasiya balli pasaytirilgan (orderlarning ~2/3 qismi nasiya)
PROFIL_BRIEF = "brief"
PROFIL_KALIBR = "kalibr"
PROFIL = os.getenv("PROFIL", PROFIL_KALIBR).strip().lower()

# Chegara signali uchun orderning minimal o'z hissasi (yarim planning %)
MIN_DELTA_FOIZ = float(os.getenv("MIN_DELTA_FOIZ", "1.0"))
# Nasiya (wallet) balli — kalibrlangan profilda
NASIYA_BALL = int(os.getenv("NASIYA_BALL", "10"))
# BRIEF profilida nasiya balli (nisbatan og'irroq)
NASIYA_BALL_BRIEF = 16

# Qamrov: yarim oxiridagi necha kun
WINDOW_DAYS = int(os.getenv("WINDOW_DAYS", "5"))

# --- Order YAKUNLANISH sanasi (completed_at) -------------------------------
# KPI order yakunlangan kun bo'yicha hisoblanadi, tushgan kun bo'yicha emas.
# `completed_at` faqat order-detailda bor, shuning uchun oyna atrofidagi
# orderlarning detali olinadi. Buffer — necha kun oldin tushganlari ham
# tekshirilsin (kuzatilgan maksimal farq: 2 kun).
YAKUN_BUFFER_KUN = int(os.getenv("YAKUN_BUFFER_KUN", "4"))
# Detal so'rovlari uchun parallel oqimlar soni
DETAL_THREADS = int(os.getenv("DETAL_THREADS", "6"))
# Mijoz o'rtachasini hisoblash uchun tarix (kun). 0 = oy boshidan
HISTORY_DAYS = int(os.getenv("HISTORY_DAYS", "0"))

# --- 3-varaq: "Oxirgi N kun yirik" -----------------------------------------
YIRIK_SUMMA = float(os.getenv("YIRIK_SUMMA", "2000000"))
OXIRGI_KUN_SONI = int(os.getenv("OXIRGI_KUN_SONI", "2"))

# --- Filial filtri ----------------------------------------------------------
# Ombor/xizmat "filial"lari — KPI filiallari emas, chiqarib tashlanadi
SKIP_FILIAL_NAMES = {
    "1c chiqim",
    "asosiy ombor",
    "asosiy zapchast",
    "aksessuar ombor",
    "distribyutsiya markazi",
    "xitoy",
}
# Yarim plani shundan kichik bo'lsa — KPI filiali emas
MIN_HALF_PLAN = float(os.getenv("MIN_HALF_PLAN", "1000000"))

# Dashboard'dagi ko'rsatish ID -> Aros warehouse ID (aksessuar filiallar)
DISPLAY_TO_AROS_WID = {100: 71, 103: 73, 104: 75}

# --- Statuslar --------------------------------------------------------------
GOOD_STATUS = {"completed"}
BAD_STATUS = {"canceled", "cancelled", "returned", "rejected"}

OY_NOMLARI = [
    "Yanvar", "Fevral", "Mart", "Aprel", "May", "Iyun",
    "Iyul", "Avgust", "Sentabr", "Oktabr", "Noyabr", "Dekabr",
]


def bugun_uzb() -> date:
    """Toshkent vaqti bo'yicha bugungi sana."""
    return datetime.now(UZB_TZ).date()


def joriy_davr():
    """Joriy (oy, yil, yarim) — Toshkent vaqti bo'yicha."""
    d = bugun_uzb()
    return d.month, d.year, (1 if d.day <= 15 else 2)


def kpi_foizi(filial_foiz: float):
    """filial foizidan (kpi%, boshqaruv%) qaytaradi."""
    for chegara, kpi, boshqaruv in KPI_TABLE:
        if filial_foiz >= chegara:
            return kpi, boshqaruv
    return 0.0, 0.0
