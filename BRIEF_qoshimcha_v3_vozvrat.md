# QO'SHIMCHA BRIEF v3: Vozvrat tasdiqlash ustuni

## MAQSAD
Asosiy algoritm PROAKTIV (vozvratni kutmasdan shubhani aniqlaydi). Endi
RETROSPEKTIV tasdiqlash qo'shamiz: o'tgan davr (masalan iyul Y2) uchun,
shubhali orderlar keyin (keyingi yarimda) VOZVRAT bo'lganmi tekshirish.

**Mantiq:** shubhali order (yarim oxirida, chegaradan o'tkazgan, nasiya) keyin
100% yoki katta foizda vozvrat bo'lgan bo'lsa — bu firibgarlik DEYARLI ANIQ.
Bu eng kuchli TASDIQLOVCHI signal.

**MUHIM:** bu ustun faqat o'tgan (tugagan) davrlar uchun ma'noli. Joriy yarim
uchun vozvrat hali bo'lmagan bo'lishi mumkin — ustun "hali ma'lum emas" bo'ladi.
Bu asosiy ballga TA'SIR QILMAYDI (oylik o'z vaqtida beriladi), faqat
tasdiqlash uchun ko'rsatiladi.

═══════════════════════════════════════════════════════════════════
## VOZVRAT MA'LUMOTINI OLISH (Aros API)
═══════════════════════════════════════════════════════════════════

### Order itemlari + vozvrat holati
Order ichidagi mahsulotlar (items) va ularning vozvrat bo'lgan-bo'lmaganini
aniqlash kerak. Aros API'da order detali endpoint tekshirilsin:

```
GET https://api.aros.uz/api/admin/orders/{order_id}/
```
yoki order listda `items` / `order_products` maydoni bo'lishi mumkin.

Har item uchun kerak:
- item summasi (yoki miqdor × narx)
- shu item VOZVRAT bo'lganmi (returned_quantity yoki return holati)
- vozvrat sanasi (qaysi kun/yarimda qaytdi)

**Agar order-detail'da vozvrat ko'rinmasa**, ProductReturn / ProductReturnItem
endpoint ishlatilsin (backend hujjatidan):
- `product_return.created_datetime` = vozvrat sanasi
- `working_return_quantity + broken_return_quantity` = qaytgan miqdor
- `order_product.selling_price` = narx
- return summasi = qaytgan_miqdor × selling_price

CC: avval order-detail (order_id bilan) sinab ko'rsin — items va vozvrat
bormi. Bo'lmasa returns endpointini qidirsin. Bitta shubhali order_id bilan
(masalan iyul Y2 dagi) test qilib, javob strukturasini ko'rsin.

═══════════════════════════════════════════════════════════════════
## YANGI USTUNLAR (1-varaq "Shubhali orderlar")
═══════════════════════════════════════════════════════════════════

Mavjud ustunlarga qo'shiladi:

| Ustun | Mazmuni |
|-------|---------|
| Vozvrat bo'ldimi | HA / YO'Q / QISMAN / hali ma'lum emas |
| Vozvrat foizi | order summasining necha % vozvrat bo'lgan (0-100%) |
| Vozvrat sanasi | eng oxirgi vozvrat sanasi (yoki bo'sh) |

### Vozvrat foizi hisoblash
```
vozvrat_foiz = (jami_vozvrat_summa / order_total_price) * 100
```
- 100% (yoki >=95%) -> "HA (to'liq)" — ENG KUCHLI SIGNAL
- 50-95% -> "QISMAN (N%)"
- 1-50% -> "QISMAN (N%)" (kuchsizroq)
- 0% -> "YO'Q"
- order o'tgan davrda emas / ma'lumot yo'q -> "hali ma'lum emas"

═══════════════════════════════════════════════════════════════════
## BALLGA TA'SIR (yangi signal)
═══════════════════════════════════════════════════════════════════

### Signal 10 — Vozvrat tasdiqlash (RETROSPEKTIV) — MAX +50
FAQAT o'tgan davrlar uchun (vozvrat ma'lum bo'lsa):
- Vozvrat >= 95% (to'liq) -> +50  (firibgarlik deyarli aniq!)
- Vozvrat 50-95% -> +30
- Vozvrat 20-50% -> +15
- Vozvrat < 20% yoki yo'q -> 0
- Ma'lum emas (joriy davr) -> 0 (ta'sir yo'q)

**MUHIM:** bu signal joriy (tugamagan) yarim uchun ISHLAMAYDI — chunki vozvrat
hali bo'lmagan. Faqat o'tgan davr tahlilida (--oy 7 --yarim 2 kabi) qo'shiladi.

Izohga: "VOZVRAT TASDIQLANDI: order 100% qaytarilgan (18.08 sanasida)"

### Daraja
Vozvrat 100% bo'lgan order avtomat YUQORI (qizil) bo'ladi, boshqa ballardan
qat'i nazar. Bu "tutildi" degani.

═══════════════════════════════════════════════════════════════════
## VOZVRAT QIDIRISH DAVRI
═══════════════════════════════════════════════════════════════════
Shubhali order yarim oxirida (masalan iyul 27-31). Vozvrat KEYIN bo'ladi:
- Keyingi yarimda (avgust 1-15) yoki
- O'sha yarimning oxirida

Qidirish oynasi: order sanasidan +30 kun ichida vozvrat bo'lganmi.
(vozvrat sanasi order sanasidan keyin va 30 kun ichida)

═══════════════════════════════════════════════════════════════════
## EXCEL YANGILANISHI
═══════════════════════════════════════════════════════════════════
1-varaq ("Shubhali orderlar")ga 3 yangi ustun:
  ... | Vozvrat bo'ldimi | Vozvrat foizi | Vozvrat sanasi

- "HA (to'liq)" / 100% qatorlar QIZIL rang (eng muhim)
- Vozvrat foizi ustuni: 0-100% format
- Ball ustuni yangilanadi (signal 10 qo'shilgan)

═══════════════════════════════════════════════════════════════════
## TEST (CC uchun)
═══════════════════════════════════════════════════════════════════
1. Iyul Y2 (--oy 7 --yil 2026 --yarim 2) da ishga tushirilsin
2. Shubhali orderlar topilgach, har biri uchun vozvrat tekshirilsin
3. Vozvrat 100% bo'lganlar QIZIL, "VOZVRAT TASDIQLANDI" izohi bilan
4. Natijani birga ko'ramiz — nechta shubhali order haqiqatan qaytarilgan

MUHIM: order-detail yoki returns endpoint javob strukturasini avval bitta
order bilan sinab ko'rsin (item + vozvrat bormi). Struktura noaniq bo'lsa,
menga (Asilbek) namuna javobni ko'rsatsin — birga aniqlaymiz.
