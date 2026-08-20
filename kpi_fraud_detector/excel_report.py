# -*- coding: utf-8 -*-
"""Excel hisobot — 2 varaq (openpyxl)."""
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from config import (BALL_ORTA, BALL_YUQORI, MAX_BALL, OXIRGI_KUN_SONI,
                    THRESHOLDS, YIRIK_SUMMA)

# ranglar
CLR_HEADER = "FF1F3864"
CLR_TITLE = "FF2F5496"
CLR_YUQORI = "FFFFC7CE"   # qizil
CLR_ORTA = "FFFFEB9C"     # sariq
CLR_TASDIQ = "FFFF8A8A"   # to'q qizil — vozvrat bilan tasdiqlangan
CLR_ZEBRA = "FFF7F9FC"

F_HEADER = Font(bold=True, color="FFFFFFFF", size=11)
F_TITLE = Font(bold=True, color="FFFFFFFF", size=12)
THIN = Side(style="thin", color="FFD9D9D9")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)

SHEET1 = "Shubhali orderlar"
SHEET2 = "Filial jamlanma"
SHEET3 = "Oxirgi %d kun yirik" % OXIRGI_KUN_SONI
SHEET4 = "Ball qoidalari"
SHEET5 = "Vozvrat tasdiqlash"

USTUNLAR1 = [
    ("Filial", 22), ("Sana", 11), ("Vaqt", 8), ("Order ID", 11),
    ("Mijoz", 24), ("Telefon", 15), ("Rol", 17), ("Summa", 15),
    ("To'lov turi", 12), ("Foiz (oldin)", 12), ("Foiz (keyin)", 12),
    ("Chegara o'tkazdi", 15), ("Hal qiluvchi", 12), ("Signallar", 62),
    ("Ball", 7), ("Daraja", 12),
    ("Vozvrat bo'ldimi", 16), ("Vozvrat foizi", 11), ("Vozvrat sanasi", 13),
    ("Vozvrat balli", 10), ("Izoh", 30),
]

USTUNLAR2 = [
    ("Filial", 24), ("Filial foizi", 11), ("Chegara ustida to'xtadi", 20),
    ("Shubhali order soni", 12),
    ("Yuqori", 9), ("O'rta", 9), ("Jami shubhali summa", 18),
    ("Nasiya summa", 16), ("Eng katta shubhali order", 20),
    ("Eng katta order ID", 14),
    ("Yarimdan keyin qaytgan summa", 17),
    ("Chegarani ushlab turdimi", 24),
]

USTUNLAR3 = [
    ("Filial", 22), ("Sana", 11), ("Vaqt", 8), ("Order ID", 11),
    ("Mijoz", 26), ("Telefon", 15), ("Rol", 17), ("Summa", 15),
    ("To'lov turi", 12), ("Shu mijozning o'sha kundagi order soni", 15),
    ("Shu mijozga o'sha kuni berilgan jami nasiya", 18),
]


def _sarlavha(ws, ustunlar, sarlavha_matni):
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(ustunlar))
    c = ws.cell(row=1, column=1, value=sarlavha_matni)
    c.font = F_TITLE
    c.fill = PatternFill("solid", fgColor=CLR_TITLE)
    c.alignment = Alignment(horizontal="left", vertical="center")
    ws.row_dimensions[1].height = 22

    for i, (nom, kengl) in enumerate(ustunlar, 1):
        cell = ws.cell(row=2, column=i, value=nom)
        cell.font = F_HEADER
        cell.fill = PatternFill("solid", fgColor=CLR_HEADER)
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = BORDER
        ws.column_dimensions[get_column_letter(i)].width = kengl
    ws.row_dimensions[2].height = 30
    ws.freeze_panes = "A3"


def _varaq1(wb, shubhalar, davr):
    ws = wb.active
    ws.title = SHEET1
    _sarlavha(ws, USTUNLAR1,
              "Sun'iy KPI ko'tarish — shubhali orderlar · %s · oyna: %s — %s"
              % (davr.nomi, davr.oyna_boshi.strftime("%d.%m.%Y"),
                 davr.oyna_oxiri.strftime("%d.%m.%Y")))

    qator = 3
    for s in shubhalar:
        qiymatlar = [
            s.filial, s.sana, s.vaqt, s.order_id, s.mijoz, s.telefon, s.rol,
            s.summa, s.tolov, s.foiz_oldin, s.foiz_keyin,
            ("HA" + (" (" + s.otgan_chegara + ")" if s.otgan_chegara else "")) if s.chegara_otdi else "yo'q",
            "HAL QILUVCHI" if s.hal_qiluvchi else "",
            s.signal_matni, s.ball, s.daraja,
            s.vozvrat_holati,
            (round(s.vozvrat_foizi, 1) if s.vozvrat_foizi is not None else None),
            s.vozvrat_sanasi, (s.vozvrat_balli or None), s.izoh,
        ]
        fill = None
        if s.daraja == "TASDIQLANDI":
            fill = PatternFill("solid", fgColor=CLR_TASDIQ)
        elif s.daraja == "YUQORI":
            fill = PatternFill("solid", fgColor=CLR_YUQORI)
        elif s.daraja == "O'RTA":
            fill = PatternFill("solid", fgColor=CLR_ORTA)

        for i, v in enumerate(qiymatlar, 1):
            cell = ws.cell(row=qator, column=i, value=v)
            cell.border = BORDER
            if fill:
                cell.fill = fill
            if i == 2:
                cell.number_format = "DD.MM.YYYY"
                cell.alignment = Alignment(horizontal="center")
            elif i == 8:
                cell.number_format = "#,##0"
            elif i in (10, 11, 18):
                cell.number_format = "0.0"
                cell.alignment = Alignment(horizontal="center")
            elif i in (3, 4, 12, 13, 15, 16, 17, 19, 20):
                cell.alignment = Alignment(horizontal="center")
            elif i == 14:
                cell.alignment = Alignment(wrap_text=True, vertical="top")
            if i == 13 and v:
                cell.font = Font(bold=True, color="FF9C0006")
            if i == 15:
                cell.font = Font(bold=True)
            if i in (16, 17) and s.daraja == "TASDIQLANDI":
                cell.font = Font(bold=True, color="FF9C0006")
        qator += 1

    oxirgi = max(qator - 1, 2)
    ws.auto_filter.ref = "A2:%s%d" % (get_column_letter(len(USTUNLAR1)), oxirgi)
    if not shubhalar:
        ws.cell(row=3, column=1, value="Shubhali order topilmadi").font = Font(italic=True)
    return ws


def _varaq2(wb, jamlanma, davr):
    ws = wb.create_sheet(SHEET2)
    _sarlavha(ws, USTUNLAR2, "Filial kesimida jamlanma · %s" % davr.nomi)

    qator = 3
    for j in jamlanma:
        qiymatlar = [
            j["filial"], j["foiz"], j["chegara_ustida"], j["soni"],
            j["yuqori"], j["orta"],
            j["jami_summa"], j["nasiya_summa"], j["eng_katta"], j["eng_katta_id"],
            j["keyingi_vozvrat"] or None, j["chegara_ushlab"],
        ]
        for i, v in enumerate(qiymatlar, 1):
            cell = ws.cell(row=qator, column=i, value=v)
            cell.border = BORDER
            if i in (7, 8, 9, 11):
                cell.number_format = "#,##0"
            elif i == 2:
                cell.number_format = "0.0"
                cell.alignment = Alignment(horizontal="center")
            elif i in (3, 4, 5, 6, 10):
                cell.alignment = Alignment(horizontal="center")
            if i == 3 and v:
                cell.fill = PatternFill("solid", fgColor=CLR_YUQORI)
                cell.font = Font(bold=True)
            if i == 5 and v:
                cell.fill = PatternFill("solid", fgColor=CLR_YUQORI)
            if i == 6 and v:
                cell.fill = PatternFill("solid", fgColor=CLR_ORTA)
            if i == 12 and v:
                cell.fill = PatternFill("solid", fgColor=CLR_TASDIQ)
                cell.font = Font(bold=True)
                cell.alignment = Alignment(wrap_text=True)
        qator += 1

    oxirgi = max(qator - 1, 2)
    ws.auto_filter.ref = "A2:%s%d" % (get_column_letter(len(USTUNLAR2)), oxirgi)
    if not jamlanma:
        ws.cell(row=3, column=1, value="Ma'lumot yo'q").font = Font(italic=True)
    return ws


def _varaq3(wb, yiriklar, davr, min_summa=None):
    """Oxirgi N kundagi yirik orderlar — MUSTAQIL ro'yxat.

    1-varaq (shubha ballari) mantiqi bilan aralashmaydi: bu yerda ball ham,
    daraja ham yo'q — oddiy xom ro'yxat.
    """
    min_summa = YIRIK_SUMMA if min_summa is None else min_summa
    ws = wb.create_sheet(SHEET3)
    _sarlavha(ws, USTUNLAR3,
              "Oxirgi %d kun (%s — %s) · summa >= %s so'm · barcha completed "
              "orderlar (shubha ballari bu yerda hisoblanmaydi)"
              % (OXIRGI_KUN_SONI, davr.yirik_boshi.strftime("%d.%m.%Y"),
                 davr.oyna_oxiri.strftime("%d.%m.%Y"),
                 "{:,.0f}".format(min_summa).replace(",", " ")))

    qator = 3
    for y in yiriklar:
        qiymatlar = [
            y["filial"], y["sana"], y["vaqt"], y["order_id"], y["mijoz"],
            y["telefon"], y["rol"], y["summa"], y["tolov"],
            y["kun_order_soni"], y["kun_nasiya"],
        ]
        for i, v in enumerate(qiymatlar, 1):
            cell = ws.cell(row=qator, column=i, value=v)
            cell.border = BORDER
            if i == 2:
                cell.number_format = "DD.MM.YYYY"
                cell.alignment = Alignment(horizontal="center")
            elif i in (8, 11):
                cell.number_format = "#,##0"
            elif i in (3, 4, 10):
                cell.alignment = Alignment(horizontal="center")
            if i == 9 and str(v).lower() == "wallet":
                cell.font = Font(bold=True, color="FF9C0006")
        qator += 1

    oxirgi = max(qator - 1, 2)
    ws.auto_filter.ref = "A2:%s%d" % (get_column_letter(len(USTUNLAR3)), oxirgi)
    if not yiriklar:
        ws.cell(row=3, column=1, value="Yirik order topilmadi").font = Font(italic=True)
    return ws


# --------------------------------------------------------------------------
# 4-varaq: ball qoidalari (oddiy til bilan)
# --------------------------------------------------------------------------
QOIDALAR = [
    ("1", "Chegaradan o'tkazdi — HAL QILUVCHI",
     "Filial KPI foizi shu order tufayli navbatdagi chegaradan (60/70/80/90/"
     "100/105/110/115/120/125/130) o'tgan VA shu ordersiz o'ta olmasdi.",
     "Bonus foizi aynan shu orderga bog'liq bo'lib qolgan — eng kuchli belgi.",
     25),
    ("1", "Chegaradan o'tkazdi — lekin zapas bor",
     "Chegaradan o'tgan, lekin yarim oxirida filial baribir undan ancha "
     "yuqorida tugagan.",
     "O'tish tasodifiy — bu order bo'lmasa ham chegaradan o'tar edi.", 8),
    ("1", "Chegaraga yaqinlashtirdi",
     "Order filialni chegaraga 3% ichida olib kelgan, lekin o'tkazmagan.",
     "Chegaraga «yetkazish» urinishi bo'lishi mumkin.", 13),
    ("2", "Nasiya (wallet)",
     "Order pul bilan emas, nasiyaga (wallet) rasmiylashtirilgan.",
     "Pul kelmagan — orderni keyin qaytarish oson.", 10),
    ("3", "Mijoz odatidan 3 barobar katta",
     "Order summasi shu mijozning shu oydagi o'rtacha orderidan >= 3× katta.",
     "Mijoz to'satdan odatdan tashqari katta xarid qilgan.", 13),
    ("3", "Mijoz odatidan 2 barobar katta",
     "Order summasi o'rtachadan >= 2× katta.", "", 7),
    ("3", "Yangi mijoz + katta order",
     "Mijozda oldingi xarid tarixi yo'q va order 5 mln so'mdan katta.",
     "Yangi ism ostida katta order urilgan bo'lishi mumkin.", 7),
    ("4", "Yarimning oxirgi kuni",
     "Order yarimning eng oxirgi kunida urilgan.",
     "KPI yopilishidan oldingi oxirgi imkoniyat.", 10),
    ("4", "Oxirgi kundan 1 / 2 / 3 / 4 kun oldin",
     "Order oxirgi kunga qanchalik yaqin bo'lsa, ball shuncha yuqori.",
     "", "8 / 6 / 4 / 2"),
    ("5", "Yirik summa: 20 mln+ / 10 mln+ / 5 mln+",
     "Orderning mutlaq summasi.", "Katta summa KPI foiziga sezilarli ta'sir qiladi.",
     "6 / 5 / 3"),
    ("6", "Bir kunda ko'p order (odatdan oshgan)",
     "Shu mijozga bir kunda 8+ order (odatdagidan 3× ko'p) → 13 ball; "
     "5+ order (2× ko'p) → 9; 4+ order (2× ko'p) → 5.",
     "Katta summa mayda orderlarga bo'lingan bo'lishi mumkin. Mijozning "
     "O'Z odatiga solishtiriladi — har kuni ko'p order uradigan ulgurji "
     "mijozlar bejiz tushmasligi uchun.", "13 / 9 / 5"),
    ("7", "Kech vaqt: 21:00+ / 20:00+ / 19:00+",
     "Order ish vaqtidan keyin urilgan.",
     "Kunni «yopishdan» oldin oshirib qo'yish belgisi.", "8 / 5 / 3"),
    ("8", "Yumaloq summa: 5 mln ga karrali / 1 mln ga karrali",
     "Summa aynan yumaloq (masalan 10 000 000).",
     "Haqiqiy savdo summasi kamdan-kam yumaloq bo'ladi. Zaif belgi — "
     "yolg'iz o'zi shubha yaratmaydi.", "5 / 3"),
    ("9", "Shu mijozga o'sha kuni jami nasiya: 20 mln+ / 10 mln+ / 5 mln+",
     "Bitta order kichik ko'rinsa ham, mijozga o'sha kuni berilgan jami "
     "nasiya katta bo'lsa.",
     "Bo'laklab urilgan nasiyani ushlaydi.", "10 / 6 / 3"),
]

QOIDALAR_VOZVRAT = [
    ("10", "Vozvrat tasdiqlash — order keyin qaytarilgan",
     "Order sanasidan keyin 30 kun ichida qaytarilgan bo'lsa: 95%+ qaytgan "
     "→ 50, 50–95% → 30, 20–50% → 15.",
     "Bu TASDIQLOVCHI dalil: KPI hisoblangandan keyin order qaytarilgan "
     "bo'lsa — firibgarlik deyarli aniq.", "50 / 30 / 15"),
]

USTUNLAR4 = [
    ("Signal", 8), ("Nima uchun ball beriladi", 34), ("Qachon ishlaydi", 56),
    ("Nega bu shubhali", 46), ("Ball", 10),
]

IZOHLAR = [
    ("Ball", "Barcha signallar ballari qo'shiladi. Eng yuqori ball — 100."),
    ("Daraja", "%d ball va undan yuqori = YUQORI (qizil, ROP darhol tekshirsin). "
               "%d–%d ball = O'RTA (sariq, ko'rib chiqilsin). "
               "%d balldan past orderlar hisobotga umuman tushmaydi."
               % (BALL_YUQORI, BALL_ORTA, BALL_YUQORI - 1, BALL_ORTA)),
    ("Foiz (oldin) / Foiz (keyin)",
     "Filialning KPI foizi shu order urilishidan OLDIN va KEYIN qanday "
     "bo'lgani. Orderlar vaqt bo'yicha tartiblanib, filialning yarimdagi "
     "yakuniy bajarilgan summasidan orqaga qarab hisoblanadi."),
    ("Chegara o'tkazdi",
     "Shu order filialni KPI chegarasidan (masalan 100%) o'tkazganmi."),
    ("Hal qiluvchi",
     "Shu ordersiz filial o'sha chegaradan o'ta olmasmidi. «HAL QILUVCHI» "
     "bo'lsa — bonus aynan shu orderga bog'liq."),
    ("Shu mijozning o'sha kundagi order soni",
     "Shu mijoz o'sha filialda o'sha kuni jami nechta order qilgan "
     "(faqat completed). Masalan 9 bo'lsa — bir kunda 9 marta xarid."),
    ("Shu mijozga o'sha kuni berilgan jami nasiya",
     "Shu mijozga o'sha filialda o'sha kuni nasiyaga (wallet) berilgan "
     "orderlarning JAMI summasi — bitta order emas, kun bo'yicha yig'indi."),
    ("Chegara ustida to'xtadi (2-varaq)",
     "Filialning yarimdagi yakuniy foizi chegaradan atigi 0–2% yuqorida "
     "tugagan (masalan 100.1%). Buning o'zi mustaqil ogohlantirish."),
    ("Chegarani ushlab turdimi (2-varaq)",
     "Yarim yopilgandan keyin qaytarilgan orderlar o'sha yarim ichida "
     "qaytarilganida filial foizi chegaradan PASTGA tushib ketarmidi. "
     "«HA» bo'lsa — KPI bonusi aynan keyin qaytarilgan orderlar hisobiga "
     "olingan. Bu eng kuchli filial darajasidagi dalil."),
    ("3-varaq",
     "«Oxirgi %d kun yirik» varaqi 1-varaqdan MUSTAQIL: u yerda shubha "
     "ballari umuman hisoblanmaydi. Bu shunchaki yarim oxiridagi barcha "
     "yirik orderlar ro'yxati — ROP qo'lda ko'z yugurtirishi uchun."
     % OXIRGI_KUN_SONI),
    ("Vozvrat bo'ldimi / foizi / sanasi",
     "Order keyinchalik qaytarilganmi (order sanasidan keyin 30 kun ichida). "
     "«HA (to'liq)» = 95%+ qaytgan, «QISMAN (N%)» = qisman, «YO'Q» = "
     "qaytarilmagan, «hali ma'lum emas» = davr hali tugamagan yoki tekshiruv "
     "o'chirilgan (--vozvratsiz)."),
    ("TASDIQLANDI (daraja)",
     "Order 95%+ qaytarilgan — shubha vozvrat bilan tasdiqlangan. Bu "
     "daraja YUQORI dan ham muhimroq."),
    ("«Vozvrat tasdiqlash» varaqi",
     "Yarim YOPILGANDAN KEYIN qaytarilgan orderlar. Bular 1-varaqda "
     "ko'rinmaydi, chunki qaytarilgan order statusi «returned» bo'lib qoladi "
     "va shubha hisobiga (faqat «completed») kirmaydi. KPI esa o'sha order "
     "hisobga olingan holda hisoblangan edi — shuning uchun bu eng kuchli dalil."),
]


USTUNLAR5 = [
    ("Filial", 22), ("Order sanasi", 12), ("Vaqt", 8), ("Order ID", 11),
    ("Mijoz", 26), ("Telefon", 15), ("Rol", 17), ("Order summasi", 15),
    ("To'lov turi", 12), ("Vozvrat sanasi", 13),
    ("Necha kundan keyin qaytdi", 13), ("Vozvrat summasi", 15),
    ("Vozvrat foizi", 11),
]


def _varaq5(wb, qaytganlar, davr):
    """Yarim YOPILGANDAN KEYIN qaytarilgan orderlar — retrospektiv dalil."""
    ws = wb.create_sheet(SHEET5)
    _sarlavha(ws, USTUNLAR5,
              "Yarim (%s) yopilgandan KEYIN qaytarilgan orderlar — KPI allaqachon "
              "hisoblangan edi" % davr.oxiri.strftime("%d.%m.%Y"))

    qator = 3
    for q in qaytganlar:
        qiymatlar = [
            q["filial"], q["sana"], q["vaqt"], q["order_id"], q["mijoz"],
            q["telefon"], q["rol"], q["summa"], q["tolov"],
            q["vozvrat_sanasi"], q["kun_farqi"], q["vozvrat_summa"],
            (round(q["vozvrat_foizi"], 1) if q["vozvrat_foizi"] is not None else None),
        ]
        fill = PatternFill("solid", fgColor=CLR_TASDIQ) \
            if (q["vozvrat_foizi"] or 0) >= 95 else None
        for i, v in enumerate(qiymatlar, 1):
            cell = ws.cell(row=qator, column=i, value=v)
            cell.border = BORDER
            if fill:
                cell.fill = fill
            if i in (2, 10):
                cell.number_format = "DD.MM.YYYY"
                cell.alignment = Alignment(horizontal="center")
            elif i in (8, 12):
                cell.number_format = "#,##0"
            elif i == 13:
                cell.number_format = "0.0"
                cell.alignment = Alignment(horizontal="center")
            elif i in (3, 4, 11):
                cell.alignment = Alignment(horizontal="center")
            if i == 9 and str(v).lower() == "wallet":
                cell.font = Font(bold=True, color="FF9C0006")
        qator += 1

    oxirgi = max(qator - 1, 2)
    ws.auto_filter.ref = "A2:%s%d" % (get_column_letter(len(USTUNLAR5)), oxirgi)
    if not qaytganlar:
        ws.cell(row=3, column=1,
                value="Yarim yopilgandan keyin qaytarilgan order topilmadi "
                      "(yoki davr hali tugamagan)").font = Font(italic=True)
    return ws


def _varaq4(wb, davr):
    ws = wb.create_sheet(SHEET4)
    _sarlavha(ws, USTUNLAR4,
              "Ball qanday hisoblanadi — maksimal ball 100 · %s" % davr.nomi)

    qator = 3
    oxirgi_signal = None
    for sig, nom, qachon, nega, ball in QOIDALAR:
        for i, v in enumerate([sig, nom, qachon, nega, ball], 1):
            cell = ws.cell(row=qator, column=i, value=v)
            cell.border = BORDER
            cell.alignment = Alignment(wrap_text=True, vertical="top",
                                       horizontal="center" if i in (1, 5) else "left")
            if i == 1:
                cell.font = Font(bold=True)
            if i == 5:
                cell.font = Font(bold=True)
            if sig != oxirgi_signal:
                cell.fill = PatternFill("solid", fgColor=CLR_ZEBRA)
        oxirgi_signal = sig
        qator += 1

    # jami
    ws.cell(row=qator, column=2, value="JAMI (barcha signal to'liq ishlasa)").font = Font(bold=True)
    c = ws.cell(row=qator, column=5, value=MAX_BALL)
    c.font = Font(bold=True, color="FFFFFFFF")
    c.fill = PatternFill("solid", fgColor=CLR_HEADER)
    c.alignment = Alignment(horizontal="center")
    for i in range(1, 6):
        ws.cell(row=qator, column=i).border = BORDER
    qator += 2

    # 10-signal — alohida (asosiy 100 lik shkalaga kirmaydi)
    ws.cell(row=qator, column=1,
            value="ALOHIDA: VOZVRAT BALLI (yuqoridagi 100 ballga QO'SHILMAYDI)"
            ).font = Font(bold=True, size=12)
    qator += 1
    for sig, nom, qachon, nega, ball in QOIDALAR_VOZVRAT:
        for i, v in enumerate([sig, nom, qachon, nega, ball], 1):
            cell = ws.cell(row=qator, column=i, value=v)
            cell.border = BORDER
            cell.fill = PatternFill("solid", fgColor=CLR_TASDIQ)
            cell.alignment = Alignment(wrap_text=True, vertical="top",
                                       horizontal="center" if i in (1, 5) else "left")
            if i in (1, 5):
                cell.font = Font(bold=True)
        qator += 1
    ws.merge_cells(start_row=qator, start_column=1, end_row=qator, end_column=5)
    izoh = ws.cell(row=qator, column=1,
                   value="Nega alohida: oylik vozvratni kutmasdan beriladi, "
                         "shuning uchun asosiy ball (0–100) faqat PROAKTIV "
                         "signallardan iborat. Vozvrat esa KEYIN ma'lum "
                         "bo'ladigan TASDIQ. Vozvrat 95%+ bo'lsa order darajasi "
                         "ballardan qat'i nazar «TASDIQLANDI» bo'ladi.")
    izoh.alignment = Alignment(wrap_text=True, vertical="top")
    ws.row_dimensions[qator].height = 44
    qator += 2

    # izohlar
    ws.cell(row=qator, column=1, value="USTUNLAR NIMANI ANGLATADI").font = Font(bold=True, size=12)
    qator += 1
    for nom, izoh in IZOHLAR:
        a = ws.cell(row=qator, column=1, value=nom)
        a.font = Font(bold=True)
        a.alignment = Alignment(wrap_text=True, vertical="top")
        ws.merge_cells(start_row=qator, start_column=2, end_row=qator, end_column=5)
        b = ws.cell(row=qator, column=2, value=izoh)
        b.alignment = Alignment(wrap_text=True, vertical="top")
        ws.row_dimensions[qator].height = 30
        qator += 1
    return ws


def chegara_ustida(foiz: float) -> str:
    """Filial aynan chegara ustida to'xtaganmi (0..2% ichida) — o'zi belgi."""
    for c in THRESHOLDS:
        if c <= foiz <= c + 2:
            return "HA (%d%% +%.1f)" % (c, foiz - c)
    return ""


def _chegara_ushlab(foiz, plan, keyingi_vozvrat):
    """Yarimdan keyingi vozvratlar chegarani ushlab turganmi.

    Agar o'sha vozvratlar yarim ichida bo'lganida filial foizi chegaradan
    PASTGA tushib ketardi — demak chegara aynan shu orderlar hisobiga
    ushlab turilgan.
    """
    if not plan or keyingi_vozvrat <= 0:
        return ""
    past = [c for c in THRESHOLDS if c <= foiz]
    if not past:
        return ""
    c = max(past)
    busiz = foiz - (keyingi_vozvrat / plan * 100.0)
    if busiz < c:
        return "HA — busiz %.1f%% (chegara %d%%)" % (busiz, c)
    return ""


def jamlanma_yasa(shubhalar, filiallar, qaytganlar=None):
    """Varaq 2 uchun filial kesimi."""
    vozvrat_map = {}
    for q in (qaytganlar or []):
        vozvrat_map[q["warehouse_id"]] = vozvrat_map.get(q["warehouse_id"], 0.0) \
            + (q["vozvrat_summa"] or 0)

    map_ = {}
    for f in filiallar:
        aniq_foiz = round(f.foiz_hisobla(), 1) if f.plan else float(f.foiz or 0)
        kv = vozvrat_map.get(f.warehouse_id, 0.0)
        map_[f.warehouse_id] = {
            "filial": f.nomi, "foiz": aniq_foiz,
            "chegara_ustida": chegara_ustida(aniq_foiz),
            "soni": 0, "yuqori": 0, "orta": 0, "jami_summa": 0.0,
            "nasiya_summa": 0.0, "eng_katta": 0.0, "eng_katta_id": "",
            "keyingi_vozvrat": kv,
            "chegara_ushlab": _chegara_ushlab(aniq_foiz, f.plan, kv),
        }
    for s in shubhalar:
        j = map_.get(s.warehouse_id)
        if j is None:
            j = map_.setdefault(s.warehouse_id, {
                "filial": s.filial, "foiz": 0.0, "chegara_ustida": "",
                "soni": 0, "yuqori": 0, "orta": 0,
                "jami_summa": 0.0, "nasiya_summa": 0.0, "eng_katta": 0.0,
                "eng_katta_id": "", "keyingi_vozvrat": 0.0, "chegara_ushlab": "",
            })
        j["soni"] += 1
        j["jami_summa"] += s.summa
        if s.daraja == "YUQORI":
            j["yuqori"] += 1
        elif s.daraja == "O'RTA":
            j["orta"] += 1
        if (s.tolov or "").lower() == "wallet":
            j["nasiya_summa"] += s.summa
        if s.summa > j["eng_katta"]:
            j["eng_katta"] = s.summa
            j["eng_katta_id"] = s.order_id

    # shubhali orderi bo'lgan YOKI chegara ustida to'xtagan / vozvratli filiallar
    jamlanma = [j for j in map_.values()
                if j["soni"] > 0 or j["chegara_ustida"] or j["keyingi_vozvrat"]]
    jamlanma.sort(key=lambda j: (0 if j["chegara_ushlab"] else 1,
                                 0 if j["chegara_ustida"] else 1,
                                 -j["yuqori"], -j["soni"], -j["jami_summa"]))
    return jamlanma


def hisobot_yasa(shubhalar, filiallar, davr, fayl_yoli, yiriklar=None,
                 yirik_summa=None, qaytganlar=None):
    wb = Workbook()
    _varaq1(wb, shubhalar, davr)
    _varaq2(wb, jamlanma_yasa(shubhalar, filiallar, qaytganlar), davr)
    _varaq3(wb, yiriklar or [], davr, yirik_summa)
    _varaq5(wb, qaytganlar or [], davr)
    _varaq4(wb, davr)
    wb.save(fayl_yoli)
    return fayl_yoli
