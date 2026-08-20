# QO'SHIMCHA BRIEF v2: KPI Fraud Detector — yangi signallar + yangi varaq

Birinchi versiya zo'r ishladi (iyul/avgust Y1 da haqiqiy shubhali holatlar tutildi:
Yunus chiroqchi 7 order/kun 84M nasiya, Fayoz Nazarov 6× anomaliya, Omon Aripov
19.5× — hammasi to'g'ri). Endi ikki narsa qo'shamiz.

═══════════════════════════════════════════════════════════════════
## A QISM — YANGI SIGNALLAR (scoring.py ga qo'shiladi)
═══════════════════════════════════════════════════════════════════

### Signal 6 — Bir mijoz, bir kunda ko'p order (KUCHLI) — MAX +20
Firibgar katta summani bo'laklab, bir mijozga bir kunda ko'p order uradi.
Real ma'lumotda aniq ko'rindi: "Yunus chiroqchi 7 order", "Abror 12 order".

Hisoblash: har (mijoz_id + sana) uchun o'sha filialdagi order sonini sanang.
- >= 8 order/kun  -> +20
- >= 5 order/kun  -> +14
- >= 4 order/kun  -> +8
- < 4            -> 0

Izohga qo'shilsin: "shu mijoz bir kunda N ta order" (allaqachon bor).
MUHIM: bu signal shu mijozning O'SHA KUNDAGI barcha orderlariga tarqalsin
(hammasi shubha to'plasin), chunki bo'laklangan.

### Signal 7 — Kech vaqt / ish vaqtidan tashqari — MAX +12
Firibgar kunni "yopishdan" oldin kech soatda uradi. Real ma'lumotda:
18:45, 22:09, 21:11, 19:52 kabi.

created_datetime dagi soatga qarab:
- soat >= 21:00  -> +12
- soat >= 20:00  -> +8
- soat >= 19:00  -> +4
- < 19:00       -> 0

Izohga: "kech vaqt (HH:MM)"

### Signal 8 — Yumaloq (round) summa — MAX +8
Sun'iy orderlar ko'pincha yumaloq. Haqiqiy savdo tasodifiy.
- Summa 5M ga bo'linadi (5M, 10M, 15M, 20M...) -> +8
- Summa 1M ga bo'linadi (aniq million) -> +4
- Aks holda -> 0
Izohga: "yumaloq summa"
ESLATMA: bu zaif signal, faqat qo'shimcha. Yolg'iz o'zi shubha yaratmasin.

### Signal 9 — Kun bo'yicha jami nasiya anomaliyasi — MAX +15
Bir order kichik ko'rinsa ham, mijozga o'sha kun JAMI katta nasiya bo'lsa.
Har (mijoz + sana) uchun jami wallet summasini hisobla:
- kun jami nasiya >= 20M -> +15
- >= 10M -> +10
- >= 5M  -> +5
Bu signal ham o'sha kundagi barcha orderlarga tarqaladi.

### Yangilangan daraja chegaralari (kalibr profili)
Yangi signallar bilan maksimal ball oshdi. Chegaralarni moslashtiring:
- YUQORI: 75+ (avval 70)
- O'RTA: 50-74 (avval 45)
Yoki .env orqali sozlansin (BALL_YUQORI, BALL_ORTA).
Real run'dan keyin birga kalibrlaymiz.

═══════════════════════════════════════════════════════════════════
## B QISM — YANGI EXCEL VARAQ: "Oxirgi 2 kun — yirik orderlar"
═══════════════════════════════════════════════════════════════════

Uchinchi varaq qo'shiladi (excel_report.py):

### Varaq nomi: "Oxirgi 2 kun yirik"

### Mazmuni
- FAQAT oxirgi 2 kun (yarim oxiridan): masalan Y1 -> 14-15, Y2 -> (oxiri-1)—oxiri
- FAQAT summa >= 2,000,000 orderlar
- BARCHA bunday orderlar tushsin (shubha ballidan QAT'I NAZAR — hammasi)
- status = completed (canceled/returned chiqariladi)
- Barcha filiallar (nafaqat shubhali topilganlar)

### Ustunlar
Filial | Sana | Vaqt | Order ID | Mijoz | Telefon | Rol | Summa |
To'lov turi | Order/kun (shu mijoz) | Ball | Daraja

### Sortlash
Filial bo'yicha guruhlab, keyin summa kamayish tartibida.
(yoki: summa kamayish tartibida global — qaysi qulay)

### Maqsad
ROP tez ko'z yugurtirishi uchun: "oxirgi 2 kunda katta orderlar kim, qancha,
nasiyami" — shubha balli bo'lmasa ham qo'lda tekshirish uchun.

### Chegara .env da
YIRIK_SUMMA=2000000    # oxirgi 2 kun varaqi uchun minimal summa
OXIRGI_KUN_SONI=2      # necha kun (default 2)

═══════════════════════════════════════════════════════════════════
## Qisqa xulosa
═══════════════════════════════════════════════════════════════════
1. scoring.py: signal 6,7,8,9 qo'shilsin (bir kunda ko'p order eng muhim)
2. Signal 6 va 9 shu mijozning o'sha kundagi HAMMA orderiga tarqalsin
3. excel_report.py: 3-varaq "Oxirgi 2 kun yirik" (2M+, hamma, shubhadan qat'i nazar)
4. .env: YIRIK_SUMMA, OXIRGI_KUN_SONI, yangilangan BALL_YUQORI/ORTA
5. Real run -> birga kalibrlash
