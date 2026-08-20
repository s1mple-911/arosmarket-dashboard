# -*- coding: utf-8 -*-
"""Sun'iy KPI ko'tarish detektori — asosiy skript.

Ishlatish:
    python main.py                         # joriy oy/yarim
    python main.py --oy 7 --yil 2026 --yarim 2
    python main.py --wid 37,1 --min-ball 45
    python main.py --demo                  # API'siz sinov (sun'iy ma'lumot)
"""
import argparse
import json
import sys
from datetime import timedelta
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from aros_api import ArosAuthError, ArosClient, order_sanasi  # noqa: E402
from config import (BALL_ORTA, HISTORY_DAYS, PROFIL, PROFIL_BRIEF,  # noqa: E402
                    PROFIL_KALIBR, WINDOW_DAYS, YAKUN_BUFFER_KUN,
                    YIRIK_SUMMA, bugun_uzb, joriy_davr)
from davr import davr_yasa  # noqa: E402
from excel_report import SHEET3, SHEET5, hisobot_yasa  # noqa: E402
from filial_data import filiallar_yukla  # noqa: E402
from scoring import (filial_tahlil, qaytarilgan_orderlar,  # noqa: E402
                     statuslar_hisoboti, vozvrat_tasdiqlash, yirik_orderlar)
from detal import DetalKesh  # noqa: E402


def _konsol_utf8():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass


def fmt(n):
    return "{:,.0f}".format(n or 0).replace(",", " ")


def argumentlar():
    oy0, yil0, yarim0 = joriy_davr()
    p = argparse.ArgumentParser(
        description="Aros Market — sun'iy KPI ko'tarish (window-dressing) detektori")
    p.add_argument("--oy", type=int, default=oy0, help="oy (1-12), default: joriy")
    p.add_argument("--yil", type=int, default=yil0, help="yil, default: joriy")
    p.add_argument("--yarim", type=int, choices=[1, 2], default=yarim0,
                   help="yarim oy: 1 = 1-15, 2 = 16-oxiri")
    p.add_argument("--wid", default="", help="faqat shu filiallar (vergul bilan): 37,1,35")
    p.add_argument("--min-ball", type=int, default=BALL_ORTA,
                   help="hisobotga tushish uchun minimal ball (default: %d)" % BALL_ORTA)
    p.add_argument("--oyna-kun", type=int, default=WINDOW_DAYS,
                   help="yarim oxiridagi necha kun tekshirilsin (default: %d)" % WINDOW_DAYS)
    p.add_argument("--tarix-kun", type=int, default=HISTORY_DAYS,
                   help="mijoz o'rtachasi uchun tarix (kun). 0 = oy boshidan")
    p.add_argument("--yirik-summa", type=float, default=YIRIK_SUMMA,
                   help="3-varaq uchun minimal summa (default: %d)" % YIRIK_SUMMA)
    p.add_argument("--profil", choices=[PROFIL_KALIBR, PROFIL_BRIEF], default=PROFIL,
                   help="ball profili: kalibr (default, shovqini kam) yoki brief (BRIEF ballari aynan)")
    p.add_argument("--out", default="", help="chiqish fayli (.xlsx)")
    p.add_argument("--vozvratsiz", action="store_true",
                   help="vozvrat tekshiruvini o'tkazib yuborish (tezroq)")
    p.add_argument("--kesh", action="store_true",
                   help="orderlarni diskka saqlab qayta ishlatish (ball sozlash uchun tez)")
    p.add_argument("--tekshir", action="store_true", help="faqat auth/ulanishni tekshirish")
    p.add_argument("--demo", action="store_true",
                   help="Aros API'siz sun'iy ma'lumot bilan sinov")
    return p.parse_args()


def _orderlar_ol(client, fil, davr, kesh_dir):
    """Orderlar — keshdan yoki API'dan (kesh yoqilgan bo'lsa saqlab qo'yiladi)."""
    if kesh_dir is not None:
        fayl = kesh_dir / ("%d.json" % fil.warehouse_id)
        if fayl.exists():
            return json.loads(fayl.read_text(encoding="utf-8"))
    orderlar = client.orders(fil.warehouse_id, davr.tarix_boshi, davr.oyna_oxiri)
    if kesh_dir is not None:
        (kesh_dir / ("%d.json" % fil.warehouse_id)).write_text(
            json.dumps(orderlar, ensure_ascii=False), encoding="utf-8")
    return orderlar


def main():
    _konsol_utf8()
    a = argumentlar()

    if a.tekshir:
        return tekshiruv()

    davr = davr_yasa(a.oy, a.yil, a.yarim, oyna_kun=a.oyna_kun, tarix_kun=a.tarix_kun)
    print("=" * 74)
    print("Sun'iy KPI ko'tarish detektori — %s" % davr.nomi)
    print("Yarim: %s — %s | Tekshiruv oynasi: %s — %s | Tarix: %s dan"
          % (davr.boshi, davr.oxiri, davr.oyna_boshi, davr.oyna_oxiri, davr.tarix_boshi))
    print("Profil: %s | min ball: %d" % (a.profil, a.min_ball))
    print("=" * 74)

    if a.demo:
        from demo_data import demo_filiallar_va_orderlar
        filiallar, orderlar_map = demo_filiallar_va_orderlar(davr)
        client = None
    else:
        faqat = [w.strip() for w in a.wid.split(",") if w.strip()] if a.wid else None
        print("\n[1/3] Filial plan/bajarildi yuklanmoqda...")
        filiallar = filiallar_yukla(a.oy, a.yil, a.yarim, faqat_wid=faqat)
        if not filiallar:
            print("Filial topilmadi. --wid ni yoki manbani tekshiring.")
            return 1
        client = ArosClient()
        orderlar_map = None

    kesh_dir = (Path(__file__).resolve().parent / ".kesh"
                / ("%d-%02d-Y%d" % (a.yil, a.oy, a.yarim)))
    kesh_dir.mkdir(parents=True, exist_ok=True)

    # Order detali: yakunlanish sanasi (completed_at) + vozvrat ma'lumoti
    dkesh = None if a.demo else DetalKesh(kesh_dir.parent / "detal.json")
    # v3: vozvrat tekshiruvi faqat TUGAGAN davr uchun ma'noli
    davr_tugagan = davr.oxiri < bugun_uzb()
    vozvrat_yoq = a.demo or a.vozvratsiz or not davr_tugagan

    shubhalar, yiriklar, qaytganlar, xatolar = [], [], [], []
    print("\n[2/3] Orderlar tekshirilmoqda (%d filial)..." % len(filiallar))
    for i, f in enumerate(filiallar, 1):
        try:
            if orderlar_map is not None:
                orderlar = orderlar_map.get(f.warehouse_id, [])
            else:
                orderlar = _orderlar_ol(client, f, davr, kesh_dir if a.kesh else None)
        except ArosAuthError:
            raise
        except Exception as e:
            xatolar.append((f.nomi, str(e)[:160]))
            print("  %2d/%d  %-24s XATO: %s" % (i, len(filiallar), f.nomi, str(e)[:80]))
            continue

        # Oyna atrofidagi orderlarning detali — YAKUNLANISH sanasi uchun
        if dkesh is not None:
            nomzodlar = [o.get("id") for o in orderlar
                         if (o.get("status") or "").lower() in ("completed", "returned")
                         and order_sanasi(o) >= davr.oyna_boshi - timedelta(days=YAKUN_BUFFER_KUN)]
            dkesh.toldir(nomzodlar, log=print,
                         xabar="%s: " % f.nomi[:18])

        hammasi = filial_tahlil(f, orderlar, davr, profil=a.profil,
                                detal_kesh=dkesh)
        topildi = [s for s in hammasi if s.ball >= a.min_ball]
        shubhalar.extend(topildi)
        # 3-varaq MUSTAQIL hisoblanadi — 1-varaq mantiqi bilan aralashmaydi
        yiriklar.extend(yirik_orderlar(f, orderlar, davr, a.yirik_summa,
                                       detal_kesh=dkesh))

        # v3: retrospektiv vozvrat tasdiqlash
        if not vozvrat_yoq and dkesh is not None:
            vozvrat_tasdiqlash(topildi, dkesh)
            qaytganlar.extend(qaytarilgan_orderlar(f, orderlar, davr, dkesh))
        st = statuslar_hisoboti(orderlar)
        print("  %2d/%d  %-24s foiz=%3.0f%%  order=%4d (%s)  shubhali=%d%s"
              % (i, len(filiallar), f.nomi[:24], f.foiz or f.foiz_hisobla(),
                 len(orderlar), ", ".join("%s:%d" % kv for kv in sorted(st.items())[:3]),
                 len(topildi),
                 "  << %d YUQORI" % sum(1 for s in topildi if s.daraja == "YUQORI")
                 if any(s.daraja == "YUQORI" for s in topildi) else ""))

    # hal qiluvchi orderlar tepada, keyin ball bo'yicha kamayish tartibida
    shubhalar.sort(key=lambda s: (0 if s.hal_qiluvchi else 1, -s.ball))
    # 3-varaq: filial bo'yicha guruhlab, ichida summa kamayish tartibida
    yiriklar.sort(key=lambda y: (y["filial"], -y["summa"]))

    out = a.out or ("shubhali_orderlar_%02d_%d_Y%d.xlsx" % (a.oy, a.yil, a.yarim))
    out_path = Path(out)
    if not out_path.is_absolute():
        out_path = Path(__file__).resolve().parent / "hisobotlar" / out_path
    out_path.parent.mkdir(parents=True, exist_ok=True)

    print("\n[3/3] Excel yasalmoqda: %s" % out_path)
    # fayl Excel'da ochiq bo'lsa — bo'sh nom topilguncha urinamiz
    asosiy = out_path
    for urinish in range(10):
        try:
            hisobot_yasa(shubhalar, filiallar, davr, str(out_path),
                         yiriklar=yiriklar, yirik_summa=a.yirik_summa,
                         qaytganlar=qaytganlar)
            break
        except PermissionError:
            qoshimcha = "_yangi" if urinish == 0 else "_yangi%d" % (urinish + 1)
            out_path = asosiy.with_name(asosiy.stem + qoshimcha + asosiy.suffix)
            print("  ! %s yozib bo'lmadi (Excel'da ochiq?) — %s ga urinaman"
                  % (asosiy.name if urinish == 0 else "oldingi nom", out_path.name))
    else:
        print("  ! Hisobot saqlanmadi — ochiq Excel fayllarni yoping.")
        return 1

    yuqori = sum(1 for s in shubhalar if s.daraja == "YUQORI")
    orta = sum(1 for s in shubhalar if s.daraja == "O'RTA")
    jami = sum(s.summa for s in shubhalar)
    nasiya = sum(s.summa for s in shubhalar if (s.tolov or "").lower() == "wallet")
    print("\n" + "-" * 74)
    print("NATIJA: %d shubhali order  (YUQORI: %d, O'RTA: %d)" % (len(shubhalar), yuqori, orta))
    print("Jami shubhali summa: %s so'm   |   shundan nasiya: %s so'm" % (fmt(jami), fmt(nasiya)))
    print("3-varaq «%s»: %d ta order, jami %s so'm (%s — %s, >= %s)"
          % (SHEET3, len(yiriklar), fmt(sum(y["summa"] for y in yiriklar)),
             davr.yirik_boshi, davr.oyna_oxiri, fmt(a.yirik_summa)))
    if vozvrat_yoq:
        sabab = ("davr hali tugamagan" if not davr_tugagan
                 else ("--vozvratsiz" if a.vozvratsiz else "demo"))
        print("Vozvrat tekshiruvi: o'tkazilmadi (%s)" % sabab)
    else:
        tasdiq = sum(1 for s in shubhalar if s.daraja == "TASDIQLANDI")
        qisman = sum(1 for s in shubhalar
                     if s.vozvrat_balli and s.daraja != "TASDIQLANDI")
        print("Vozvrat tasdiqlash: shubhali orderlardan %d ta TO'LIQ qaytarilgan, "
              "%d ta qisman" % (tasdiq, qisman))
        print("5-varaq «%s»: yarim yopilgandan keyin qaytarilgan %d ta order, "
              "%s so'm" % (SHEET5, len(qaytganlar),
                           fmt(sum(q["vozvrat_summa"] for q in qaytganlar))))
    if xatolar:
        print("Xatolar (%d filial): %s" % (len(xatolar), "; ".join(n for n, _ in xatolar)))
    print("Fayl: %s" % out_path)
    print("-" * 74)

    for s in shubhalar[:10]:
        print("  %3d  %-8s %-20s #%-8s %14s  %s"
              % (s.ball, s.daraja, s.filial[:20], s.order_id, fmt(s.summa),
                 s.signal_matni[:60]))
    return 0


def tekshiruv():
    """Auth va ma'lumot manbalarini tekshirish."""
    print("Ulanish tekshiruvi")
    print("-" * 40)
    ok = True
    try:
        ArosClient().tekshir()
        print("  Aros API basic auth : OK")
    except ArosAuthError as e:
        ok = False
        print("  Aros API basic auth : XATO\n    %s" % e)
    except Exception as e:
        ok = False
        print("  Aros API            : XATO — %s" % str(e)[:200])

    oy, yil, yarim = joriy_davr()
    try:
        fl = filiallar_yukla(oy, yil, yarim, log=lambda *_: None)
        print("  Filial manbai       : OK (%d filial)" % len(fl))
        for f in fl[:5]:
            print("      #%-4d %-24s plan=%15s bajarildi=%15s foiz=%5.1f%%"
                  % (f.warehouse_id, f.nomi[:24], fmt(f.plan), fmt(f.bajarildi), f.foiz))
    except Exception as e:
        ok = False
        print("  Filial manbai       : XATO — %s" % str(e)[:200])
    return 0 if ok else 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except ArosAuthError as e:
        _konsol_utf8()
        print("\nAUTH XATO: %s" % e)
        print("`.env` faylida AROS_LOGIN va AROS_PASSWORD to'g'ri ekanini tekshiring.")
        sys.exit(2)
    except KeyboardInterrupt:
        print("\nTo'xtatildi.")
        sys.exit(130)
    except Exception:
        traceback.print_exc()
        sys.exit(1)
