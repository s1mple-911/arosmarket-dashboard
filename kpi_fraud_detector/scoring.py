# -*- coding: utf-8 -*-
"""Shubha ballari — 5 ta signal (BRIEF bo'yicha)."""
from dataclasses import dataclass, field
from datetime import date

from aros_api import (order_mijozi, order_sanasi, order_summasi, order_vaqti)
from config import (BALL_ORTA, BALL_YUQORI, BAD_STATUS, GOOD_STATUS, MAX_BALL,
                    MIN_DELTA_FOIZ, NASIYA_BALL, NASIYA_BALL_BRIEF,
                    PROFIL_BRIEF, PROFIL_KALIBR, THRESHOLDS)


@dataclass
class Shubha:
    filial: str
    warehouse_id: int
    sana: date
    vaqt: str
    order_id: int
    mijoz: str
    telefon: str
    rol: str
    summa: float
    tolov: str
    foiz_oldin: float
    foiz_keyin: float
    chegara_otdi: bool
    otgan_chegara: str
    hal_qiluvchi: bool = False
    kun_order_soni: int = 0     # shu mijozning o'sha kundagi order soni
    kun_nasiya: float = 0.0     # shu mijozning o'sha kundagi jami nasiyasi
    # --- v3: retrospektiv vozvrat tasdiqlash (asosiy 100 lik ballga kirmaydi)
    vozvrat_holati: str = "hali ma'lum emas"
    vozvrat_foizi: float = None
    vozvrat_sanasi: str = ""
    vozvrat_balli: int = 0
    signallar: list = field(default_factory=list)
    ball: int = 0
    daraja: str = ""
    izoh: str = ""

    @property
    def signal_matni(self) -> str:
        return "; ".join(self.signallar)


# --------------------------------------------------------------- 1-signal
def signal_chegara(f_before: float, f_after: float, delta_foiz: float = None,
                   yakuniy_foiz: float = None, profil: str = PROFIL_KALIBR):
    """(ball, matn, otdi?, chegara) — chegaradan o'tkazish.

    `delta_foiz`   — orderning O'ZI qo'shgan foiz (summa / yarim_plan * 100)
    `yakuniy_foiz` — filialning yarim oxiridagi yakuniy foizi

    Kalibrlangan profilda chegara o'tishi **hal qiluvchi** (pivotal) bo'lishi
    kerak: shu ordersiz filial chegaradan o'ta olmasmidi?
        yakuniy_foiz - delta_foiz < C
    4000 ta orderdan chegara chizig'ini qaysi biri kesgani ko'pincha tasodif —
    yakunda zapas qolgan bo'lsa, o'tish firibgarlik belgisi emas.
    """
    kalibr = (profil == PROFIL_KALIBR and delta_foiz is not None)

    otgan = [c for c in THRESHOLDS if f_before < c <= f_after]
    if otgan:
        c = otgan[0]
        matn = "chegaradan o'tkazdi %d%% (%.1f%% -> %.1f%%)" % (c, f_before, f_after)
        if kalibr and yakuniy_foiz is not None:
            busiz = yakuniy_foiz - delta_foiz
            if busiz < c:
                return 25, matn + " — HAL QILUVCHI (busiz %.1f%%)" % busiz, True, c, True
            return 8, matn + " [yakunda zapas bor (%.1f%%) — tasodifiy o'tish]" % yakuniy_foiz, True, c, False
        return 25, matn, True, c, True

    yaqin = [c for c in THRESHOLDS if f_after < c <= f_after + 3 and f_before < c]
    if yaqin:
        if kalibr and delta_foiz < MIN_DELTA_FOIZ:
            return 0, "", False, None, False
        c = min(yaqin)
        return 13, "chegaraga yaqinlashtirdi %d%% (%.1f%% -> %.1f%%)" % (c, f_before, f_after), False, c, False
    return 0, "", False, None, False


# --------------------------------------------------------------- 2-signal
def signal_nasiya(order: dict, profil: str = PROFIL_KALIBR):
    if (order.get("payment_method") or "").lower() == "wallet":
        return (NASIYA_BALL_BRIEF if profil == PROFIL_BRIEF else NASIYA_BALL), "nasiya (wallet)"
    return 0, ""


# --------------------------------------------------------------- 3-signal
def signal_mijoz_anomaliya(summa: float, mijoz_ortacha: float, mijoz_soni: int):
    if mijoz_soni <= 0:
        if summa >= 5_000_000:
            return 7, "yangi mijoz + katta order"
        return 0, ""
    if mijoz_ortacha <= 0:
        return 0, ""
    nisbat = summa / mijoz_ortacha
    if nisbat >= 3:
        return 13, "mijoz o'rtachasidan %.1f× katta (o'rt. %s)" % (nisbat, _fmt(mijoz_ortacha))
    if nisbat >= 2:
        return 7, "mijoz o'rtachasidan %.1f× katta (o'rt. %s)" % (nisbat, _fmt(mijoz_ortacha))
    return 0, ""


# --------------------------------------------------------------- 4-signal
def signal_oxirgi_kun(sana: date, oyna_oxiri: date):
    farq = (oyna_oxiri - sana).days
    ballar = {0: 10, 1: 8, 2: 6, 3: 4, 4: 2}
    b = ballar.get(farq, 0)
    if not b:
        return 0, ""
    matn = "oxirgi kun" if farq == 0 else "oxirgi kundan %d kun oldin" % farq
    return b, matn


# --------------------------------------------------------------- 6-signal
def signal_kunlik_order_soni(soni: int, odat: float = 0.0,
                             profil: str = PROFIL_KALIBR):
    """Bir mijozga bir kunda ko'p order — katta summa bo'laklangan belgisi.
    Signal shu mijozning o'sha kundagi BARCHA orderlariga tarqaladi.

    `odat` — shu mijozning tarix davridagi o'rtacha kunlik order soni.

    Kalibrlangan profilda mutlaq son yetarli emas: Aros'da bitta savat bir
    necha orderga bo'linadi va yirik B2B mijozlar HAR KUNI 20+ order uradi
    (oyna orderlarining 53% i >=4 order/kun guruhida). Shuning uchun order
    soni mijozning O'Z ODATIDAN sezilarli oshgan bo'lishi kerak.
    """
    if profil == PROFIL_BRIEF:
        nisbat = 99.0
    else:
        nisbat = (soni / odat) if odat > 0 else 99.0

    def matn(b):
        if odat > 0:
            return "shu mijozga bir kunda %d ta order (odatda ~%.0f)" % (soni, odat)
        return "shu mijozga bir kunda %d ta order" % soni

    if soni >= 8 and nisbat >= 3:
        return 13, matn(13)
    if soni >= 5 and nisbat >= 2:
        return 9, matn(9)
    if soni >= 4 and nisbat >= 2:
        return 5, matn(5)
    return 0, ""


# --------------------------------------------------------------- 7-signal
def signal_kech_vaqt(dt):
    """Ish vaqtidan tashqari — kunni "yopishdan" oldin urilgan order."""
    soat = dt.hour
    if soat >= 21:
        b = 8
    elif soat >= 20:
        b = 5
    elif soat >= 19:
        b = 3
    else:
        return 0, ""
    return b, "kech vaqt (%02d:%02d)" % (soat, dt.minute)


# --------------------------------------------------------------- 8-signal
def signal_yumaloq_summa(summa: float):
    """Sun'iy orderlar ko'pincha yumaloq. Zaif signal — faqat qo'shimcha."""
    s = int(round(summa))
    if s <= 0:
        return 0, ""
    if s % 5_000_000 == 0:
        return 5, "yumaloq summa (%s)" % _fmt(summa)
    if s % 1_000_000 == 0:
        return 3, "yumaloq summa (%s)" % _fmt(summa)
    return 0, ""


# --------------------------------------------------------------- 9-signal
def signal_kunlik_nasiya(kun_nasiya: float):
    """Bir order kichik ko'rinsa ham, mijozga o'sha kun JAMI nasiya katta.
    Signal o'sha kundagi barcha orderlariga tarqaladi."""
    if kun_nasiya >= 20_000_000:
        return 10, "kunlik jami nasiya %s" % _fmt(kun_nasiya)
    if kun_nasiya >= 10_000_000:
        return 6, "kunlik jami nasiya %s" % _fmt(kun_nasiya)
    if kun_nasiya >= 5_000_000:
        return 3, "kunlik jami nasiya %s" % _fmt(kun_nasiya)
    return 0, ""


# --------------------------------------------------------------- 5-signal
def signal_yirik_summa(summa: float):
    if summa >= 20_000_000:
        return 6, "yirik summa (%s)" % _fmt(summa)
    if summa >= 10_000_000:
        return 5, "katta summa (%s)" % _fmt(summa)
    if summa >= 5_000_000:
        return 3, "summa %s" % _fmt(summa)
    return 0, ""


def _fmt(n: float) -> str:
    return "{:,.0f}".format(n or 0).replace(",", " ")


def daraja_aniqla(ball: int, vozvrat_foizi: float = None) -> str:
    # v3: to'liq qaytarilgan order — "tutildi", ballardan qat'i nazar
    if vozvrat_foizi is not None and vozvrat_foizi >= 95:
        return "TASDIQLANDI"
    if ball >= BALL_YUQORI:
        return "YUQORI"
    if ball >= BALL_ORTA:
        return "O'RTA"
    return ""


# ------------------------------------------------------------------ asosiy
def kpi_sanasi(o, detal_kesh=None):
    """Order KPI'ga qaysi kun hisoblanadi — YAKUNLANGAN kun.

    `completed_at` faqat order-detailda bor. Kesh bo'lmasa yoki maydon bo'sh
    bo'lsa — tushgan kunga qaytamiz (orderlarning 94% i shu kuni yakunlanadi).
    """
    if detal_kesh is not None:
        d = detal_kesh.ol(o.get("id"))
        if d and d.get("yakun"):
            from detal import sana_ol
            s = sana_ol(d["yakun"])
            if s:
                return s
    return order_sanasi(o)


def filial_tahlil(fil, orderlar, davr, profil: str = PROFIL_KALIBR,
                  detal_kesh=None):
    """Bitta filialning oyna orderlarini baholaydi.

    fil      — filial_data.Filial (plan, bajarildi to'ldirilgan)
    orderlar — [tarix_boshi .. oyna_oxiri] oralig'idagi XOM orderlar
    davr     — davr.Davr

    BARCHA baholangan orderlar qaytariladi (ball bo'yicha filtrsiz) — 3-varaq
    ("Oxirgi N kun yirik") uchun past balli orderlar ham kerak.
    """

    # 1) faqat completed
    completed = [o for o in orderlar
                 if (o.get("status") or "").lower() in GOOD_STATUS]
    # 2) oyna (oxirgi N kun) va tarix qismlariga ajratamiz.
    #    Oyna — YAKUNLANGAN kun bo'yicha (KPI shunday hisoblaydi).
    #    Tarix (mijoz o'rtachasi uchun) — tushgan kun yetarli.
    oyna, tarix, sana_map = [], [], {}
    for o in completed:
        d = kpi_sanasi(o, detal_kesh)
        if davr.oyna_ichidami(d):
            oyna.append(o)
            sana_map[o.get("id")] = d
        elif order_sanasi(o) < davr.oyna_boshi:
            tarix.append(o)
    oyna.sort(key=lambda o: (sana_map.get(o.get("id")), order_vaqti(o)))

    # 3) mijoz bo'yicha tarix o'rtachasi (oyna ORDERLARISIZ — sun'iy order
    #    o'rtachani ko'tarib yubormasligi uchun)
    mijoz_stat = {}
    for o in tarix:
        uid = (o.get("user") or {}).get("id")
        if uid is None:
            continue
        s = mijoz_stat.setdefault(uid, {"soni": 0, "jami": 0.0, "kunlar": set()})
        s["soni"] += 1
        s["jami"] += order_summasi(o)
        s["kunlar"].add(order_sanasi(o))

    # 4) kumulyativ bajarildi: yarim yakuniy bajarildi'dan orqaga qarab
    #    oyna orderlari ayriladi (vozvratlar hisobga olingan holda qoladi)
    plan = fil.plan or 0.0
    yakuniy = fil.bajarildi or 0.0
    chegara_ishlaydi = plan > 0 and yakuniy > 0
    yakuniy_foiz = (yakuniy / plan * 100.0) if plan > 0 else 0.0
    summalar = [order_summasi(o) for o in oyna]
    suffix = [0.0] * (len(summalar) + 1)
    for i in range(len(summalar) - 1, -1, -1):
        suffix[i] = suffix[i + 1] + summalar[i]

    # 5) (mijoz + kun) kesimi: order soni va jami nasiya.
    #    Katta summa bo'laklab urilganda signal HAMMA orderga tarqalishi uchun
    #    filialning shu kundagi barcha completed orderlari sanaladi.
    kun_mijoz, kun_nasiya = {}, {}
    for o in completed:
        kalit = ((o.get("user") or {}).get("id"), kpi_sanasi(o, detal_kesh))
        kun_mijoz[kalit] = kun_mijoz.get(kalit, 0) + 1
        if (o.get("payment_method") or "").lower() == "wallet":
            kun_nasiya[kalit] = kun_nasiya.get(kalit, 0.0) + order_summasi(o)

    natija = []
    for i, o in enumerate(oyna):
        summa = summalar[i]
        if summa <= 0:
            continue
        m = order_mijozi(o)
        sana = sana_map.get(o.get("id")) or order_sanasi(o)
        vaqt = order_vaqti(o).strftime("%H:%M")

        if chegara_ishlaydi:
            oldin_summa = max(0.0, yakuniy - suffix[i])
            f_before = oldin_summa / plan * 100.0
            delta_foiz = summa / plan * 100.0
            f_after = f_before + delta_foiz
            ch_ball, ch_matn, ch_otdi, ch_chegara, ch_hal = signal_chegara(
                f_before, f_after, delta_foiz, yakuniy_foiz, profil)
            # 130%+ da KPI allaqachon maksimal — motiv kuchsiz
            if f_before >= 130:
                ch_ball = int(round(ch_ball * 0.5))
                if ch_matn:
                    ch_matn += " [130%+ — kuchsizlantirildi]"
        else:
            f_before = f_after = fil.foiz
            ch_ball, ch_matn, ch_otdi, ch_chegara, ch_hal = 0, "", False, None, False

        st = mijoz_stat.get(m["id"], {"soni": 0, "jami": 0.0, "kunlar": set()})
        ortacha = (st["jami"] / st["soni"]) if st["soni"] else 0.0
        # mijozning odatdagi kunlik order soni (savdo qilgan kunlar bo'yicha)
        odat = (st["soni"] / len(st["kunlar"])) if st["kunlar"] else 0.0
        kun_soni = kun_mijoz.get((m["id"], sana), 0)
        kun_nasiya_summa = kun_nasiya.get((m["id"], sana), 0.0)

        signallar, ball = [], 0
        for b, t in ((ch_ball, ch_matn),
                     signal_nasiya(o, profil),
                     signal_mijoz_anomaliya(summa, ortacha, st["soni"]),
                     signal_oxirgi_kun(sana, davr.oyna_oxiri),
                     signal_yirik_summa(summa),
                     signal_kunlik_order_soni(kun_soni, odat, profil),
                     signal_kech_vaqt(order_vaqti(o)),
                     signal_yumaloq_summa(summa),
                     signal_kunlik_nasiya(kun_nasiya_summa)):
            if b:
                ball += b
                if t:
                    signallar.append(t)
        ball = min(ball, MAX_BALL)   # shkala 0..100

        izoh = ""
        if kun_soni >= 3:
            izoh = "shu mijoz bir kunda %d ta order" % kun_soni

        natija.append(Shubha(
            filial=fil.nomi, warehouse_id=fil.warehouse_id,
            sana=sana, vaqt=vaqt, order_id=o.get("id"),
            mijoz=m["ism"], telefon=m["telefon"], rol=m["rol"],
            summa=summa, tolov=(o.get("payment_method") or ""),
            foiz_oldin=round(f_before, 1), foiz_keyin=round(f_after, 1),
            chegara_otdi=ch_otdi, hal_qiluvchi=ch_hal,
            otgan_chegara=("%d%%" % ch_chegara) if (ch_otdi and ch_chegara) else "",
            kun_order_soni=kun_soni, kun_nasiya=kun_nasiya_summa,
            signallar=signallar, ball=ball, daraja=daraja_aniqla(ball),
            izoh=izoh,
        ))

    natija.sort(key=lambda x: -x.ball)
    return natija


def yirik_orderlar(fil, orderlar, davr, min_summa, detal_kesh=None):
    """3-varaq uchun MUSTAQIL ro'yxat — shubha mantiqiga umuman bog'liq emas.

    Yarim oxiridagi oxirgi N kun (davr.yirik_boshi..oyna_oxiri) ichidagi
    barcha `completed` orderlar, summasi >= min_summa. Ball hisoblanmaydi,
    filtrlanmaydi — ROP qo'lda ko'z yugurtirishi uchun xom ro'yxat.
    """
    completed = [o for o in orderlar
                 if (o.get("status") or "").lower() in GOOD_STATUS]

    # (mijoz + kun) kesimi filialning shu kundagi BARCHA orderlaridan
    kun_soni, kun_nasiya = {}, {}
    for o in completed:
        kalit = ((o.get("user") or {}).get("id"), kpi_sanasi(o, detal_kesh))
        kun_soni[kalit] = kun_soni.get(kalit, 0) + 1
        if (o.get("payment_method") or "").lower() == "wallet":
            kun_nasiya[kalit] = kun_nasiya.get(kalit, 0.0) + order_summasi(o)

    natija = []
    for o in completed:
        sana = kpi_sanasi(o, detal_kesh)
        summa = order_summasi(o)
        if sana < davr.yirik_boshi or sana > davr.oyna_oxiri or summa < min_summa:
            continue
        m = order_mijozi(o)
        kalit = (m["id"], sana)
        natija.append({
            "filial": fil.nomi, "warehouse_id": fil.warehouse_id,
            "sana": sana, "vaqt": order_vaqti(o).strftime("%H:%M"),
            "order_id": o.get("id"), "mijoz": m["ism"], "telefon": m["telefon"],
            "rol": m["rol"], "summa": summa,
            "tolov": (o.get("payment_method") or ""),
            "kun_order_soni": kun_soni.get(kalit, 0),
            "kun_nasiya": kun_nasiya.get(kalit, 0.0),
        })
    return natija


def vozvrat_tasdiqlash(shubhalar, detal_kesh, log=print):
    """v3 — har bir shubhali orderni vozvrat bo'yicha tekshiradi.

    Asosiy ball (0..100) o'zgarmaydi — vozvrat ALOHIDA tasdiq balli sifatida
    ko'rsatiladi (oylik vozvratni kutmasdan beriladi). To'liq qaytarilgan
    order darajasi "TASDIQLANDI" bo'ladi.
    """
    from detal import vozvrat_holati

    tekshirildi = 0
    for s in shubhalar:
        v = detal_kesh.ol(s.order_id) if s.order_id else None
        if v is None:
            continue
        tekshirildi += 1
        matn, foiz, sana, ball = vozvrat_holati(v, s.sana, s.summa)
        s.vozvrat_holati = matn
        s.vozvrat_foizi = foiz
        s.vozvrat_sanasi = sana
        s.vozvrat_balli = ball
        if ball:
            s.izoh = ((s.izoh + "; ") if s.izoh else "") + \
                "VOZVRAT TASDIQLANDI: order %.0f%% qaytarilgan (%s)" % (foiz, sana)
        s.daraja = daraja_aniqla(s.ball, foiz)
    return tekshirildi


def qaytarilgan_orderlar(fil, orderlar, davr, detal_kesh, log=print):
    """v3 — oynadagi orderlardan YARIM YOPILGANDAN KEYIN qaytarilganlari.

    Bular eng kuchli dalil: KPI allaqachon hisoblangan, keyin order qaytgan.
    1-varaqda ko'rinmaydi (status `returned` bo'lgani uchun completed filtri
    ularni chiqarib tashlaydi), shuning uchun alohida ro'yxat.
    """
    from detal import VOZVRAT_OYNA_KUN, sana_ol

    natija = []
    for o in orderlar:
        if (o.get("status") or "").lower() != "returned":
            continue
        v = detal_kesh.ol(o.get("id"))
        if v is None:
            continue
        # qaytarilgan order ham YAKUNLANGAN kun bo'yicha KPI'ga kirgan
        sana = sana_ol(v.get("yakun")) or order_sanasi(o)
        if not davr.oyna_ichidami(sana):
            continue
        vsana = sana_ol(v.get("vozvrat_sana"))
        if vsana is None or vsana <= davr.oxiri:
            continue    # yarim ichida qaytgan — KPI'ga ta'sir qilmagan
        if (vsana - sana).days > VOZVRAT_OYNA_KUN:
            continue
        summa = float(v.get("asl_summa") or 0) or order_summasi(o)
        vsumma = float(v.get("vozvrat_summa") or 0)
        m = order_mijozi(o)
        natija.append({
            "filial": fil.nomi, "warehouse_id": fil.warehouse_id,
            "sana": sana, "vaqt": order_vaqti(o).strftime("%H:%M"),
            "order_id": o.get("id"), "mijoz": m["ism"], "telefon": m["telefon"],
            "rol": m["rol"], "summa": summa,
            "tolov": (o.get("payment_method") or ""),
            "vozvrat_sanasi": vsana,
            "kun_farqi": (vsana - sana).days,
            "vozvrat_summa": vsumma,
            "vozvrat_foizi": min(100.0, vsumma / summa * 100.0) if summa else None,
        })
    return natija


def statuslar_hisoboti(orderlar):
    """Diagnostika uchun status kesimi."""
    stat = {}
    for o in orderlar:
        s = (o.get("status") or "?").lower()
        stat[s] = stat.get(s, 0) + 1
    return stat


__all__ = ["Shubha", "filial_tahlil", "yirik_orderlar", "daraja_aniqla",
           "vozvrat_tasdiqlash", "qaytarilgan_orderlar", "statuslar_hisoboti",
           "BAD_STATUS"]
