# -*- coding: utf-8 -*-
"""Sun'iy (demo) ma'lumot — Aros API'siz mantiqni sinash uchun.

`python main.py --demo` shu ma'lumot ustida to'liq quvurni ishlatadi.
"""
from datetime import timedelta

from filial_data import Filial

_ORDER_ID = [900000]


def _order(oid_sana, soat, summa, user, tolov="cash", status="completed"):
    _ORDER_ID[0] += 1
    return {
        "id": _ORDER_ID[0],
        "user": user,
        "status": status,
        "payment_method": tolov,
        "delivery_method": "aros_office",
        "total_price": "%.2f" % summa,
        "created_datetime": "%sT%02d:%02d:00+05:00" % (oid_sana.isoformat(), soat, 15),
        "comment": None,
    }


def _mijoz(uid, ism, tel, rol="business_partner"):
    ismlar = ism.split(" ", 1)
    return {"id": uid, "first_name": ismlar[0],
            "last_name": ismlar[1] if len(ismlar) > 1 else "",
            "username": tel, "role": rol}


def demo_filiallar_va_orderlar(davr):
    oxiri = davr.oyna_oxiri
    kun = lambda n: oxiri - timedelta(days=n)  # noqa: E731
    tarix_kun = davr.oyna_boshi - timedelta(days=3)

    tanish = _mijoz(9122, "Tanish Mijoz", "+998901112233")
    oddiy1 = _mijoz(4745, "Farhod Islamov", "+998955703939")
    oddiy2 = _mijoz(8360, "Muzaffar Nazirov", "+998905888845")
    yangi = _mijoz(12777, "Yangi Mijoz", "+998900000001", "customer")

    filiallar = [
        # 80% chegarasi ostida turgan filial — oxirgi kuni "itarib" yuborilgan
        Filial(37, "C8-Do'kon", "Zapchast", plan=1_000_000_000,
               bajarildi=805_000_000, foiz=81),
        # sog'lom filial
        Filial(1, "Malika zapchast", "Zapchast", plan=500_000_000,
               bajarildi=310_000_000, foiz=62),
        # allaqachon 130%+ — chegara signali kuchsizlanadi
        Filial(35, "Samarqand zapchast", "Zapchast", plan=200_000_000,
               bajarildi=272_000_000, foiz=136),
    ]

    orderlar = {
        37: [
            # tarix (oyna tashqarisi) — mijoz o'rtachasi shu yerdan
            _order(tarix_kun, 11, 2_000_000, tanish),
            _order(tarix_kun, 15, 1_800_000, tanish),
            _order(tarix_kun, 17, 2_200_000, tanish),
            _order(tarix_kun, 12, 9_000_000, oddiy1),
            # oyna
            _order(kun(4), 10, 5_000_000, oddiy1),
            _order(kun(3), 12, 3_000_000, oddiy2),
            _order(kun(2), 14, 2_000_000, oddiy1),
            _order(kun(1), 16, 5_000_000, oddiy2),
            _order(kun(0), 19, 40_000_000, tanish, tolov="wallet"),   # <-- firibgarlik
            _order(kun(0), 20, 12_000_000, yangi, tolov="wallet"),    # yangi mijoz, nasiya
            _order(kun(0), 21, 30_000_000, tanish, status="canceled"),  # hisobga olinmaydi
        ],
        1: [
            _order(tarix_kun, 11, 4_000_000, oddiy1),
            _order(kun(4), 10, 3_500_000, oddiy1),
            _order(kun(2), 13, 2_800_000, oddiy2),
            _order(kun(0), 15, 4_100_000, oddiy1),
        ],
        35: [
            _order(tarix_kun, 11, 3_000_000, oddiy2),
            _order(kun(1), 12, 6_000_000, oddiy2),
            _order(kun(0), 18, 22_000_000, tanish, tolov="wallet"),
        ],
    }
    return filiallar, orderlar
