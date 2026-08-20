# BRIEF: Sun'iy KPI Ko'tarish Detektori (AROS Market)

## KONTEKST

Aros Market — 24 filialli chakana savdo tarmog'i. Hodimlarga **KPI bonus** tizimi
bor: filial bajarilgan foiziga qarab oylik hisoblanadi. KPI **chegaralar** bilan
pog'onali: 50/60/70/80/90/100 — har chegaradan o'tsa bonus foizi sakraydi.

**Firibgarlik (window-dressing):** ba'zi hodimlar yarim oxirida (oxirgi kunlarda)
tanish mijoz nomiga yoki o'z profiliga **katta/nasiya order** urib, filial KPI foizini
sun'iy ravishda keyingi chegaradan o'tkazadilar (masalan 79% → 80%), keyin order
vozvrat qilinadi. Maqsad — kattaroq KPI bonus olish.

**Vazifa:** vozvratni KUTMASDAN, order o'zidanoq shubhalini aniqlaydigan avtomatik
algoritm. Natija — ROP'lar (rahbarlar) tekshirishi uchun Excel hisobot.

---

## BIZNES QOIDALARI (o'zgarmas)

### Bi-monthly (yarim oy) tizimi
- Har oy 2 yarimga bo'linadi: **Y1 = 1-15**, **Y2 = 16-oy_oxiri**
- KPI har yarim uchun alohida hisoblanadi

### KPI chegaralari va bonus foizlari (filial foiziga qarab)
```
filial_foiz >= 130 -> kpi 1.15%, boshqaruv 0.31%
filial_foiz >= 125 -> kpi 1.10%, boshqaruv 0.31%
filial_foiz >= 120 -> kpi 1.00%, boshqaruv 0.31%
filial_foiz >= 115 -> kpi 0.95%, boshqaruv 0.31%
filial_foiz >= 110 -> kpi 0.90%, boshqaruv 0.31%
filial_foiz >= 105 -> kpi 0.85%, boshqaruv 0.31%
filial_foiz >= 100 -> kpi 0.80%, boshqaruv 0.31%
filial_foiz >= 90  -> kpi 0.70%, boshqaruv 0.21%
filial_foiz >= 80  -> kpi 0.60%, boshqaruv 0.11%
filial_foiz >= 70  -> kpi 0.50%, boshqaruv 0.05%
filial_foiz >= 60  -> kpi 0.40%, boshqaruv 0.03%
< 60               -> kpi 0%,    boshqaruv 0%
```
**Muhim chegaralar (bonus sakraydigan nuqtalar): 60, 70, 80, 90, 100, 105, 110, 115, 120, 125, 130**

### Filial "bajarildi" formulasi
```
bajarildi = max(0, orders_summa - returns_summa)
filial_foiz = round(bajarildi / plan * 100)   # yarim plan = oylik_plan / 2
```

---

## MA'LUMOT MANBALARI

### 1. Aros API — Orders (asosiy)
```
GET https://api.aros.uz/api/admin/orders/
  ?page=1&page_size=200
  &warehouse={warehouse_id}
  &created_datetime_after=YYYY-MM-DD
  &created_datetime_before=YYYY-MM-DD
Auth: HTTP Basic (ArosBasicAuth2 credential — summary/date ruxsati bor)
```
Javob: `{count, next, previous, results: [...]}`  (pagination bor!)

**Order maydonlari:**
```json
{
  "id": 382067,
  "user": {"id": 9122, "first_name": "...", "last_name": "...",
           "username": "+998...", "role": "business_partner|master|customer"},
  "status": "completed|canceled|returned|...",
  "payment_method": "cash|wallet|cashback",   // wallet = NASIYA (kuchli signal)
  "delivery_method": "aros_office|bts_office|...",
  "total_price": "100000.00",
  "warehouse": {"id": 37, "name": "O'rikzor C8"},
  "created_datetime": "2026-07-16T19:27:38+05:00",
  "comment": null
}
```
- Sana filtri `created_datetime` bo'yicha ISHLAYDI
- `payment_method: "wallet"` = nasiya (to'lanmagan) = kuchli firibgarlik signali
- Order'da HODIM (worker) maydoni YO'Q — shuning uchun FILIAL bo'yicha bog'lanadi (hodim shart emas)

### 2. Filial plan + bajarildi (KPI konteksti)
PostgreSQL `cache_filial` jadvali (n8n-postgres):
```sql
SELECT warehouse_id::text, oy_yarim,
       (data->>'plan')::numeric AS plan,
       (data->>'bajarildi')::numeric AS bajarildi,
       (data->>'foiz')::int AS foiz,
       (data->>'filial')::text AS filial_nomi
FROM cache_filial WHERE oy_yarim IN (1,2);
```
Yoki Aros cachier-report'dan real-time (agar cache eski bo'lsa).

### 3. Aktiv filiallar ro'yxati
PostgreSQL `users` jadvalidan distinct warehouse_id (worker_id bor bo'lganlar),
yoki `cache_filial` dagi barcha warehouse_id.

---

## ALGORITM (ballar tizimi)

Qamrov: har yarim oxiridagi **OXIRGI 5 KUN** completed orderlari.
- Y1 uchun: 11-15 kun
- Y2 uchun: (oy_oxiri-4) — oy_oxiri (masalan avgust: 27-31)
- canceled/returned CHIQARILADI

Har `completed` order uchun shubha balli:

### Signal 1 — Chegara o'tkazuvchi (ENG OG'IR) — MAX +40
- Filial foizi order OLDIN (F_before) va KEYIN (F_after) hisoblanadi
  - F_before = (bajarildi_shu_ordergacha) / yarim_plan * 100
  - F_after  = (bajarildi_shu_order_bilan) / yarim_plan * 100
- Chegaralar: [60,70,80,90,100,105,110,115,120,125,130]
- Agar biror chegara C: `F_before < C <= F_after` (order chegaradan O'TKAZGAN)
  → **+40**
- Agar o'tkazmadi lekin chegaraga 3% ichida yaqinlashtirdi → **+20**

### Signal 2 — Nasiya (to'lanmagan) — +25
- `payment_method == "wallet"` → **+25**

### Signal 3 — Mijoz summa anomaliyasi — MAX +20
- Mijozning shu oydagi (yoki 60 kun) o'rtacha order summasini hisobla
- order_summa >= 3× o'rtacha → **+20**
- order_summa >= 2× o'rtacha → **+10**
- mijoz tarixi yo'q (yangi) + order katta (>5M) → **+10**

### Signal 4 — Oxirgi kunlarga yaqinlik — MAX +15
- Oxirgi kun → +15;  -1 kun → +12;  -2 → +9;  -3 → +6;  -4 → +3

### Signal 5 — Yirik mutlaq summa — MAX +10
- >=20M → +10;  >=10M → +7;  >=5M → +4

### Shubha darajasi (ballar yig'indisi)
- **70+** = 🔴 YUQORI (ROP darhol tekshirsin)
- **45-69** = 🟡 O'RTA (ko'rib chiqilsin)
- **< 45** = chiqarilmaydi (shovqin kam)

### Nozik tuzatishlar
- Bir order bir necha signal to'plashi mumkin (ballar qo'shiladi)
- Filial foizi allaqachon 130%+ bo'lsa, chegara signali kuchsizlanadi (×0.5)
  — max KPI'da ko'tarish motivi kam
- Bir mijozga ketma-ket ko'p order (bir kunda) bitta "guruh" sifatida ham
  baholanishi mumkin (ixtiyoriy kengaytma)

---

## NATIJA (Excel, 2 varaq)

### Varaq 1: "Shubhali orderlar"
Ustunlar: Filial | Sana | Vaqt | Order ID | Mijoz | Telefon | Rol |
Summa | To'lov turi | Foiz (oldin) | Foiz (keyin) | Chegara o'tkazdi (ha/yo'q) |
Signallar (matn) | Ball | Daraja
- Ball bo'yicha kamayish tartibida sortlanган
- Daraja rangi bilan (qizil/sariq)

### Varaq 2: "Filial jamlanma"
Ustunlar: Filial | Shubhali order soni | Yuqori (soni) | O'rta (soni) |
Jami shubhali summa | Nasiya summa | Eng katta shubhali order

---

## TEXNIK TALABLAR

1. **Til:** Python (pandas + openpyxl). Requests bilan Aros API.
2. **Auth:** Aros Basic Auth — `.env` da saqlansin (ArosBasicAuth2 login/parol).
   Login: +998916160505 (yoki ArosBasicAuth2 ning aniq useri — Asilbek beradi)
3. **Pagination:** orders API `next` bo'yicha barcha sahifalar olinsin.
4. **Rate limit:** filiallar ketma-ket, har API call orasida kichik kutish (0.3s).
5. **Konfiguratsiya:** oy, yil, yarim — parametr sifatida (default: joriy).
6. **Avtomatik ishlash:** cron yoki qo'lda ishga tushiriladigan skript.
   Har yarim oxirida (yoki har kuni oxirgi 5 kun oynasida) ishlashi mumkin.
7. **PostgreSQL:** filial plan/bajarildi uchun `cache_filial` o'qilsin
   (yoki Aros cachier-report real-time). Ulanish `.env` da.
8. **Chiqish:** `shubhali_orderlar_{oy}_{yil}_Y{yarim}.xlsx`

---

## MUHIM ESLATMALAR

- **Vozvrat KUTILMAYDI** — order o'zidan shubhali aniqlanadi (proaktiv).
  Chunki oylik o'z vaqtida berilishi kerak, vozvratni kutib bo'lmaydi.
- **Hodim bog'lash SHART EMAS** — filial darajasida yetarli. Order'da worker
  maydoni yo'q, shuning uchun buni majburlamang.
- **Aksessuar filiallar** (warehouse 71/73/75 — display 100/103/104) Aros
  hisobini ishlatmasligi mumkin — ular uchun order manbai boshqacha. Agar order
  API ular uchun bo'sh qaytarsa, e'tiborsiz qoldiring.
- **False positive'ni kamaytirish:** past ball (<45) chiqarilmaydi. ROP faqat
  YUQORI va O'RTA ko'radi.
- **Kelajak kengaytma:** shubhali orderlarni bazaga yozib borish (tarix), keyin
  vozvrat bo'lganda tasdiqlash (order haqiqatan qaytdimi) — ishonchni oshirish.

---

## BOSQICHMA-BOSQICH REJA (Claude Code uchun)

1. `.env` sozlash (Aros auth, PG ulanish)
2. Aros API client (orders, pagination, rate-limit)
3. `cache_filial` dan filial plan/bajarildi o'qish
4. Har filial oxirgi 5 kun orderlarини olish
5. Ball hisoblash mantiqi (5 signal)
6. Chegara o'tkazish hisobi (F_before/F_after — orderlarni vaqt bo'yicha
   tartiblab, kumulyativ bajarildi ustiga qo'shib borish)
7. Excel yasash (2 varaq, formatlash, rang)
8. CLI parametrlar (oy/yil/yarim)
9. (Ixtiyoriy) cron sozlash

