# Metabase o'rniga backend API — talablar ro'yxati

Sana: 2026-10-13. Muallif: Asilbek (Dashboard / Provodka / n8n).

Hozir `metabase.aros.uz` (Aros DB ustida) **5 ta public card** orqali ishlatiladi. Iste'molchilar: n8n (3 faol workflow + 1 o'chiq), Provodka «Aylanma» (Supabase), Dashboard CEO sahifasi, MML Google Sheet. Metabase uzilsa shu 5 ta so'rov o'rniga API kerak. Frontend va SQL o'zgarmaydi — faqat n8n'dagi HTTP so'rovlar almashtiriladi.

## Ustuvorlik

| # | Card | Kim ishlatadi | Chastota | Holat | Ustuvorlik |
|---|------|---------------|----------|-------|-----------|
| 1 | materialreport total (62) | Cache Builder, Aylanma Snapshot | har soat / har kun | ishlayapti | 🔴 1 |
| 2 | Profit report filiallar (134) | Aylanma Snapshot | har kun | ishlayapti (ba'zi kun bo'sh) | 🔴 1 |
| 5 | ai agent uchun — katalog (69) | IG Katalog sinxroni | 1 soat (hozir o'chiq) | 2026-09-05 dan to'xtatilgan | 🟡 2 |
| 3 | MML Classified A (64) | MML Stock Sync | har kun 06:00 | 🔴 2026-07-01 dan buzilgan | 🟢 3 (qaror kerak) |
| 4 | Material Report (47) | MML Stock Sync | har kun 06:00 | 🔴 2026-07-01 dan buzilgan | 🟢 3 |
| 6 | (ochilmagan) transfer tannarx | Aylanma Snapshot | — | reja | ⚪ ixtiyoriy |

---

## 1. Ombor qoldig'i TANNARXDA — «materialreport total» (card 62, `4f729857-…`)

**Kim ishlatadi**
- n8n **Aros Market - Cache Builder** (`xgfB2F52mXZ5tJJk`, har soat 07:00–00:00): har plan-filial uchun alohida so'rov (≈33 ta) → `cache_filial.ombor_summa_usd`, `ombor_mahsulot_soni` → **CEO sahifa** «Balansi» badge va ombor modali (`ceo.html showOmborModal`). Metabase yiqilsa `cache_filial_history` dan oxirgi qiymat (`ombor_source='fallback_cache'`).
- n8n **Aros Provodka - Aylanma Snapshot** (`o3BZP8uYatGkRu8b`, har kuni 03:00 Toshkent): **hamma 68 ombor bitta so'rovda** (≈12 s) → `aylanma_snapshot` bo'limlari **T1** (tovar omborlarda) va **T5** (brak omborlar) → Provodka «Aylanma» sahifasi (sof aylanma kapital, jami). Juftlash **ombor NOMI** bo'yicha (`name_uz`) — id yo'q, nom o'zgarsa buziladi.

**Parametrlar (hozir)**: `warehouse_filter` (id massivi), `start_date`, `end_date` (oxirgi 30 kun; faqat «Oxirgi…» ustunlari kerak, davr ahamiyatsiz).

**Ustunlar (hozir qaytadi)**: Ombor, Boshlangich miqdori/summa, Postupleniya miqdori/summa, Zakaz miqdori/summa ($), Qaytgan miqdori/summa ($), Inv kirim/chiqim miqdori/summa, Transfer kirim miqdori/summa, Transfer yolda miqdori/summa (so'm), Transfer chiqim miqdori/summa, Manual tuzatish, Sales window, **Oxirgi miqdori**, **Oxirgi summa**.

**Ishlatiladigani**: `Ombor`, `Oxirgi miqdori`, `Oxirgi summa` (USD = ending qty × `back_office_productincomeitem.average_price` — kirim/tannarx narxi, sotuv emas), `Transfer yolda summa` (faqat ma'lumot, jamiga qo'shilmaydi).

**API talab**
```
GET /api/admin/reports/stock-value?warehouse_ids=1,2,3&date=2026-10-13
→ [{ warehouse_id, warehouse_name, qty, cost_usd, transfer_on_way_sum_uzs }]
```
- `warehouse_id` majburiy (nom bilan juftlashdan qutulamiz). Brak omborlar ham kiradi (`is_broken`).
- `warehouse_ids` bo'sh bo'lsa — hammasi. 68 ombor ≤ 15 s.
- `date` bo'lmasa — hozirgi qoldiq.

---

## 2. Kunlik FOYDA filial bo'yicha — «Profit report — filiallar bo'yicha (Totals)» (card 134, `c89e54d0-…`)

**Kim ishlatadi**: Aylanma Snapshot («Foyda URL» → «Get Metabase Foyda»): kecha va undan oldingi kun, har kun alohida so'rov (`dan` = `gacha` = kun) → `sync_aylanma_foyda` → `aylanma_foyda` (Supabase) → Aylanma **hisobot** (Reja = boshlang'ich jami + Σ foyda − Σ xarajat) va filial breakdown. `JAMI` qatori ham yoziladi.

**Parametrlar**: `dan`, `gacha` (date, Toshkent), `filial` (ixtiyoriy).

**Ustunlar**: Filial, Sotilgan soni, Qaytarilgan soni, Kirim narx ($), Sotuv narx ($), Keshbek orqali to'lov ($), Foyda ($), Sanadan, Sanagacha. Oxirida `JAMI` qatori.

**Mantiq (card tavsifi)**: admin paneldagi Profit report (Excel «Barcha Tugallangan») — buyurtma **tugallangan sanasi** (Toshkent) oralig'ida, faol buyurtma/qator, summalar USD.

**Ma'lum muammo**: 2026-10-03 dan boshlab ayrim kunlar bo'sh keladi (12.10 uchun `JAMI` = null). API da bo'sh kun 0 emas, bo'sh massiv bo'lsin.

**API talab**
```
GET /api/admin/reports/profit?date_from=2026-10-12&date_to=2026-10-12&group_by=warehouse
→ { total: {...}, rows: [{ warehouse_id, warehouse_name, sold_qty, returned_qty, cost_usd, sale_usd, cashback_usd, profit_usd }] }
```

---

## 3. MML A-sinf ro'yxat — «MML report Classified - ModifiedA» (card 64, `66a68b75-…`)

**Kim ishlatadi**: n8n **Aros Market - MML Stock Sync** (`QBWpVZNXMGfHblci`, har kuni 06:00, har filial): A sinf tovarlar ro'yxatini Material Report (4-band) bilan solishtirib filialda **yetishmayotgan A tovarlar** → `mml_stock_check` + Google Sheet (`1lXV4eAdm1TK84RmhiGaplkQDieRC_PHVIqWuYWXCSYk`).

**Parametrlar**: `warehouse_filter` (id massivi), `start_date`, `end_date` (30 kun), `reason_filter` (null), `class_filter` = `['A']`.

**Ustunlar (n8n o'qiydi)**: Maxsulot IDsi, Class, Mahsulot nomi, Kategoriya, Sifat, Rang.

**🔴 Holat**: 2026-07-01 dan beri card «invalid-query» qaytaradi, `mml_stock_check` har kuni 0 bilan yoziladi (34 filial). Modul kerak bo'lsa API, kerak bo'lmasa workflow o'chiriladi.

**API talab**
```
GET /api/admin/reports/mml?warehouse_id=75&date_from&date_to&class=A
→ [{ product_variant_id, class, name, category, quality, color }]
```

---

## 4. Filial qoldig'i MAHSULOT kesimida — «Material Report» (card 47, `b4de6f16-…`)

**Kim ishlatadi**: MML Stock Sync (3-band bilan juft).

**Parametrlar**: `warehouse_filter`, `start_date`, `end_date`.

**Ustunlar (n8n o'qiydi)**: ID, Mahsulot nomi, Kategoriya, Brend, Sifat, Rang, Oxirgi miqdori.

**Holat**: 3-band bilan birga buzilgan.

**API talab**
```
GET /api/admin/warehouses/{id}/stock?date=
→ [{ product_variant_id, name, category, brand, quality, color, qty, avg_cost_usd }]
```
Eslatma: shu endpoint bo'lsa 1-band (ombor qiymati) uning yig'indisi — ikkalasini bitta endpoint + `summary=true` bilan berish mumkin.

---

## 5. Katalog + narxlar — «ai agent uchun» (card 69, `06ca79fd-…`, `/query/json`, parametrsiz, ≈17 900 qator)

**Kim ishlatadi**: n8n **Aros IG — 2. Katalog va narx sinxroni** (`Fo1RsUjCWdYJc7hX`, har soat, **hozir o'chiq**, oxirgi sync 2026-09-05) → `ig_products` (4 666 variant) → Instagram AI agent (narx va mavjudlik). Yo'qolgan variantlar `aktiv=false`, narx null kelsa eski narx saqlanadi.

**Ustunlar**: Mahsulot Parent ID, ID, Mahsulot nomi, Kategoriya, Brend, Model, Rang, Sifat, Sklad, Quantity, average price, b2c, b2m, b2b. (Bir variant har ombor uchun alohida qator.)

**API talab**
```
GET /api/admin/catalog/variants?page=1&page_size=1000&active=true
→ [{ variant_id, parent_id, name, category, brand, model, color, quality, price_b2c, price_b2m, price_b2b, stock: [{ warehouse_id, warehouse_name, qty }] }]
```
Faqat IG bot qayta yoqilsa kerak.

---

## 6. Rejada (Metabase'da ochilmagan) — ochiq transferlar TANNARXDA

`pravodka/METABASE_AYLANMA_TRANSFER.sql` — `on_way`/`created` transferlar uchun `qty × oxirgi average_price`. Hozir Aylanma `v2/transfers.document_price` (hujjat/sotuv narxi) ishlatadi, bu tannarx emas.

**API talab**: `v2/transfers` javobiga har transfer uchun `cost_usd` (tannarx) maydoni qo'shilsa yetadi.

---

## Umumiy talablar (hammasi uchun)

- **Auth**: Basic (n8n'da `httpBasicAuth` bor) yoki token header.
- **warehouse_id** — Aros API id (`api_warehouse_id`), nom emas.
- **Sana** — Toshkent vaqti, `YYYY-MM-DD`.
- **Hajm**: 68 ombor / 18 000 variant — pagination yoki ≤ 20 s javob.
- **Bo'sh natija** — bo'sh massiv (0 qiymat emas), xato — HTTP 4xx/5xx + `{error}`.
- **Kim o'zgartiradi**: n8n'dagi 3 workflow (Cache Builder, Aylanma Snapshot, MML Stock Sync) — frontend va Supabase SQL o'zgarmaydi, kesh/payload tuzilmasi saqlanadi.

## Metabase'ga bog'liq joylar (xarita)

| Joy | Node / fayl | Card |
|-----|-------------|------|
| n8n Cache Builder | «Get Metabase Stock» (HTTP), «Build Cache» (cols: Oxirgi summa/miqdori), «Get Last Ombor PG» (zaxira) | 62 |
| n8n Aylanma Snapshot | «MB Prep» → «Get Metabase» → «Build Payload» (Ombor/Oxirgi summa/miqdori/Transfer yolda summa) | 62 |
| n8n Aylanma Snapshot | «Foyda URL» → «Get Metabase Foyda» → «Foyda Payload» (7 ustun MAP) | 134 |
| n8n MML Stock Sync | «Prepare Jobs» → «Fetch MML» / «Fetch Material» → «Compare A vs Material» | 64, 47 |
| n8n IG Katalog (o'chiq) | «Metabase public cardni tortish» → «Variantlarni tayyorlash» | 69 |
| Supabase (pravodka) | `aylanma_snapshot.manba_holati.metabase`, `aylanma_foyda.manba='metabase'`, `PROVODKA_AYLANMA*.sql` | — |
| Dashboard | `ceo.html` (ombor_summa_usd, ombor_mahsulot_soni — cache orqali) | — |
