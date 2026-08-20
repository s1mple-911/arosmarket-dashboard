# Sun'iy KPI Ko'tarish Detektori (AROS Market)

Yarim oy oxirida filial KPI foizini sun'iy ravishda keyingi chegaradan
o'tkazish (window-dressing) uchun urilgan shubhali orderlarni **vozvratni
kutmasdan** aniqlaydi va ROP'lar uchun Excel hisobot yasaydi.

## O'rnatish

```bash
cd kpi_fraud_detector
python -m pip install -r requirements.txt
cp .env.example .env      # Windows: copy .env.example .env
```

`.env` da **AROS_LOGIN / AROS_PASSWORD** ni to'ldiring (n8n'dagi
`ArosBasicAuth2` kredit ichidagi login-parol).

Tekshirish:

```bash
python main.py --tekshir
```

## Ishlatish

```bash
python main.py                              # joriy oy + joriy yarim
python main.py --oy 7 --yil 2026 --yarim 2  # aniq davr
python main.py --wid 37,1,35                # faqat tanlangan filiallar
python main.py --min-ball 60                # faqat kuchliroq signallar
python main.py --oyna-kun 7                 # oxirgi 7 kun (default 5)
python main.py --out C:\hisobot.xlsx
python main.py --profil brief               # BRIEF ballari aynan (shovqinli)
python main.py --kesh                       # orderlarni saqlab, qayta ishlatish
python main.py --demo                       # API'siz sinov (sun'iy ma'lumot)
```

`--kesh` bilan bir marta yuklab olingan orderlar `.kesh/{yil}-{oy}-Y{yarim}/`
da saqlanadi — ball/profil sozlashda qayta yuklash shart emas (25 filial uchun
to'liq yuklash ~8-10 daqiqa, keshdan ~5 soniya).

Natija: `hisobotlar/shubhali_orderlar_{oy}_{yil}_Y{yarim}.xlsx` — **4 varaq**:

1. **Shubhali orderlar** — ball bilan baholangan orderlar. Hal qiluvchi
   orderlar tepada, so'ng ball bo'yicha kamayish tartibida, daraja rangi bilan
   (🔴 YUQORI, 🟡 O'RTA)
2. **Filial jamlanma** — filial kesimi + «chegara ustida to'xtadi» belgisi
3. **Oxirgi N kun yirik** — yarimning oxirgi `OXIRGI_KUN_SONI` kunidagi
   **barcha** completed orderlar (summa ≥ `YIRIK_SUMMA`). **1-varaq mantiqidan
   butunlay mustaqil** — bu yerda ball ham, daraja ham hisoblanmaydi, shunchaki
   xom ro'yxat: kim, qancha, nasiyami, o'sha kuni nechta order.
   Filial bo'yicha guruhlangan, ichida summa kamayish tartibida.
4. **Vozvrat tasdiqlash** — yarim **yopilgandan keyin** qaytarilgan orderlar
   (retrospektiv dalil, faqat tugagan davrlar uchun)
5. **Ball qoidalari** — har bir signal uchun «qachon ishlaydi / nega shubhali /
   necha ball» jadvali + barcha ustunlar nimani anglatishi. Oddiy til bilan,
   ROP uchun.

## Algoritm

Qamrov: yarim oxiridagi **oxirgi 5 kun** `completed` orderlari
(Y1 → 11–15, Y2 → oy_oxiri-4 … oy_oxiri). `canceled` / `returned` chiqariladi.

### Sana — YAKUNLANGAN kun bo'yicha

KPI order **yakunlangan** (`completed_at`) kun bo'yicha hisoblanadi, tushgan
(`created_datetime`) kun bo'yicha emas: 31-da tushib 1-da yakunlangan order
iyulga kirmaydi, 29-da tushib 31-da yakunlangani esa kiradi.

Muammo: `completed_at` orders LIST javobida **yo'q** va API uni filtrlay
olmaydi — u faqat `/api/admin/orders/{id}/` da bor. Shuning uchun oyna
atrofidagi (oyna boshidan `YAKUN_BUFFER_KUN` = 4 kun oldin boshlab) barcha
`completed`/`returned` orderlarning detali olinadi (6 parallel oqim,
`.kesh/detal.json` da keshlanadi) va oyna a'zoligi shu sana bo'yicha
aniqlanadi. O'lchov: orderlarning **94%** i tushgan kuni yakunlanadi, 6% i
1–2 kun keyin.

Mijoz o'rtachasi (3-signal) uchun tarix orderlarida tushgan sana ishlatiladi —
o'rtachaga 1-2 kunlik siljish ta'sir qilmaydi, detal esa 40 000 order uchun
juda qimmat bo'lardi.

**Maksimal ball — 100** (barcha signallar to'liq ishlaganda). Shkala hisobotning
4-varag'ida ("Ball qoidalari") oddiy til bilan ham yozilgan.

| Signal | Shart | Ball |
|---|---|---|
| 1. Chegara o'tkazuvchi | hal qiluvchi o'tish (`F_before < C <= F_after` va shu ordersiz o'tmasdi) | **25** |
| | chegaradan o'tgan, lekin yakunda zapas bor | 8 |
| | o'tmadi, 3% ichida yaqinlashtirdi | 13 |
| 2. Nasiya | `payment_method == "wallet"` | 10 |
| 3. Mijoz anomaliyasi | ≥3× o'rtacha / ≥2× / yangi mijoz + >5M | 13 / 7 / 7 |
| 4. Oxirgi kunlarga yaqinlik | oxirgi kun → 10, −1 → 8, −2 → 6, −3 → 4, −4 → 2 | ≤ 10 |
| 5. Yirik summa | ≥20M → 6, ≥10M → 5, ≥5M → 3 | ≤ 6 |
| 6. Bir kunda ko'p order (odatdan oshgan) | ≥8 va ≥3× odat → 13, ≥5 va ≥2× → 9, ≥4 va ≥2× → 5 | ≤ 13 |
| 7. Kech vaqt | ≥21:00 → 8, ≥20:00 → 5, ≥19:00 → 3 | ≤ 8 |
| 8. Yumaloq summa | 5M ga karrali → 5, 1M ga karrali → 3 | ≤ 5 |
| 9. Kunlik jami nasiya (shu mijoz) | ≥20M → 10, ≥10M → 6, ≥5M → 3 | ≤ 10 |
| **Jami** | | **100** |

**6 va 9-signal** shu mijozning o'sha kundagi *barcha* orderlariga tarqaladi —
katta summa bo'laklab urilganda har bo'lak shubha to'plashi kerak.

**6-signal — odat darvozasi (`kalibr` profili):** mutlaq son o'zi yetarli emas.
Aros'da bitta savat bir necha orderga bo'linadi (oyna orderlarining 16% i bir
xil daqiqada urilgan) va yirik B2B mijozlar HAR KUNI 20+ order uradi — natijada
«≥4 order/kun» qoidasi orderlarning **53%** iga tegadi. Shuning uchun order
soni mijozning o'z odatidan oshgan bo'lishi kerak: ≥8 va ≥3× odat → +20,
≥5 va ≥2× → +14, ≥4 va ≥2× → +8. Tarixi yo'q (yangi) mijozda darvoza ochiq.
`--profil brief` da mutlaq qoida (odatsiz) ishlaydi.

Daraja: **≥50 = 🔴 YUQORI** (maksimalning yarmi), **33–49 = 🟡 O'RTA**
(uchdan biri), `<33` hisobotga tushmaydi.
Filial foizi order oldidan allaqachon 130%+ bo'lsa, chegara signali ×0.5
(maksimal KPI'da ko'tarish motivi yo'q).

### Ball profillari (`--profil`)

BRIEF ballari real ma'lumotda juda shovqinli chiqdi (iyul Y2 → 1042 ta natija,
shundan faqat 44 tasi haqiqatan chegaradan o'tkazgan). Ikki sabab:

1. **Nasiya kamdan-kam holat emas** — C8 da iyulda 3363 ta completed orderning
   2284 tasi (68%) `wallet`. +25 ball deyarli har bir orderga tushadi.
2. **«Chegaraga yaqinlashtirdi»** — yarim oxirida filial foizi chegaraga yaqin
   tursa, o'sha zonadagi *har bir* order +20 oladi, hatto 200 ming so'mlik ham.

Shuning uchun ikkita profil bor:

| | `--profil brief` | `--profil kalibr` (default) |
|---|---|---|
| Chegaradan o'tkazdi, **hal qiluvchi** | +40 | +40 |
| Chegaradan o'tkazdi, yakunda zapas bor | +40 | +12 (tasodifiy o'tish) |
| Chegaraga yaqinlashtirdi | +20 | +20, lekin order hissasi ≥ `MIN_DELTA_FOIZ` (1%) bo'lsa |
| Nasiya (wallet) | +25 | `NASIYA_BALL` (default +15) |

**Hal qiluvchi (pivotal)** = shu ordersiz filial chegaradan o'ta olmasdi:

```
yakuniy_foiz - order_hissasi < C
```

Mantiq: 4000 ta orderdan chegara chizig'ini qaysi biri kesib o'tgani ko'pincha
tasodif — filial 126% bilan tugagan bo'lsa, 110% dan o'tgan order hech narsani
hal qilmagan. Firibgarlik belgisi — order **ayni chegarani ushlab qolgan**
bo'lishi. Hal qiluvchi orderlar hisobotda alohida ustunda va eng tepada
chiqadi. Barcha qiymatlar `.env` orqali sozlanadi.

### Vozvrat tasdiqlash (retrospektiv)

Asosiy algoritm **proaktiv** — vozvratni kutmaydi. Tugagan davr tahlil qilinsa,
skript qo'shimcha ravishda har bir shubhali orderni **keyin qaytarilganmi**
deb tekshiradi (`/api/admin/orders/{id}/` → `return_amount`, `returned_at`,
`products[].working_return_quantity`). Qidirish oynasi — order sanasidan
keyingi 30 kun.

| Vozvrat foizi | Vozvrat balli | Daraja |
|---|---|---|
| ≥95% | 50 | **TASDIQLANDI** |
| 50–95% | 30 | o'zgarmaydi |
| 20–50% | 15 | o'zgarmaydi |
| <20% yoki yo'q | 0 | o'zgarmaydi |

**Vozvrat balli asosiy 100 ballik shkalaga qo'shilmaydi** — oylik vozvratni
kutmasdan beriladi, shuning uchun asosiy ball faqat proaktiv signallardan
iborat. Vozvrat esa keyin ma'lum bo'ladigan alohida tasdiq.

**Muhim 1:** qisman vozvratlarda `returned_at` **bo'sh** bo'lishi mumkin
(`return_amount > 0` bo'lsa ham). Bunday holatda vozvrat baribir hisobga
olinadi — faqat sanasi ko'rsatilmaydi va 30 kunlik oyna tekshirilmaydi.

**Muhim 2:** Aros'da to'liq qaytarilgan orderning statusi `returned` bo'lib
qoladi va `payment.total_amount` 0 ga tushadi. Shu sababli u 1-varaqqa (faqat
`completed`) umuman tushmaydi — eng kuchli dalil yo'qolmasligi uchun bunday
orderlar alohida **«Vozvrat tasdiqlash»** varag'ida ko'rsatiladi: yarim
yopilgandan **keyin** qaytarilganlar, ya'ni KPI allaqachon hisoblangan holatlar.

Tekshiruv faqat tugagan davr uchun avtomat yoqiladi. O'chirish: `--vozvratsiz`.
Natijalar `.kesh/vozvrat.json` da saqlanadi — qayta ishga tushirishda API
qayta so'ralmaydi.

### Varaq 2 dagi «Chegara ustida to'xtadi»

Filialning yakuniy foizi chegaradan 0–2% ustida to'xtagan bo'lsa (masalan
100.3%, 100.4%, 100.6%) — bu order darajasidan qat'i nazar mustaqil belgi.
Bunday filiallar jamlanmada tepada va qizil bilan chiqadi.

### F_before / F_after qanday hisoblanadi

Yarim uchun yakuniy `bajarildi` (vozvratlar ayrilgan) ma'lum. Oyna orderlari
vaqt bo'yicha tartiblanadi va yakuniy bajarildi'dan **orqaga qarab** ayriladi:

```
F_before(i) = (bajarildi_yakuniy - Σ summa[i..oxir]) / yarim_plan * 100
F_after(i)  = F_before(i) + summa[i] / yarim_plan * 100
```

Shu sababli hisobot yarim tugagandan keyin (yoki oxirgi kunlar davomida)
ishga tushirilsa eng aniq bo'ladi — `bajarildi` cache qanchalik yangi bo'lsa,
foizlar shunchalik to'g'ri.

## Ma'lumot manbalari

| Nima | Manba | Auth |
|---|---|---|
| Orderlar | `GET api.aros.uz/api/admin/orders/` (`warehouse`, `created_datetime_after/before`, pagination `next`) | HTTP Basic |
| Filiallar ro'yxati | n8n `aros-filial-plan-list` | yo'q |
| Filial plan / bajarildi / foiz | n8n `aros-cache-filial` (`bajarildi = prognoz`) | yo'q |
| (muqobil) plan / bajarildi | PostgreSQL `cache_filial` — `.env` da `PG_DSN` bo'lsa | PG |

- Ombor/xizmat nuqtalari (1C chiqim, Asosiy ombor, Xitoy, Distribyutsiya
  markazi, Aksessuar ombor) va yarim plani `MIN_HALF_PLAN` dan kichik
  filiallar tekshirilmaydi.
- `aros-filial-plan-list` faqat **joriy oy** uchun to'liq to'ldirilgan.
  O'tgan oy so'ralsa, filial ro'yxati avtomatik joriy oydan olinadi —
  plan/bajarildi esa baribir `aros-cache-filial` dan kerakli davr uchun keladi.
- `bajarildi` uchun `prognoz` maydoni ishlatiladi: plan oshib bajarilganda
  `qoldi = 0` bo'lib qoladi va `plan - qoldi` noto'g'ri (kam) chiqadi.
- Aksessuar filiallar: dashboard ID → Aros warehouse ID mapping
  `100→71, 103→73, 104→75` (`config.DISPLAY_TO_AROS_WID`).
- API chaqiruvlari orasida `AROS_RATE_LIMIT` (default 0.3s) kutish,
  5xx/429 da 3 marta qayta urinish bor.

## Cron (avtomatik ishlash)

Har yarim oxirida, Toshkent vaqti bilan 23:40 — Windows Task Scheduler:

```powershell
schtasks /create /tn "AROS KPI Fraud Y1" /tr "python C:\Users\laziz\arosmarket-dashboard\kpi_fraud_detector\main.py" /sc monthly /d 15 /st 23:40
schtasks /create /tn "AROS KPI Fraud Y2" /tr "python C:\Users\laziz\arosmarket-dashboard\kpi_fraud_detector\main.py" /sc monthly /mo lastday /st 23:40
```

Linux cron:

```
40 23 15 * *  cd /opt/kpi_fraud_detector && python main.py
40 23 28-31 * * [ "$(date -d tomorrow +\%d)" = "01" ] && cd /opt/kpi_fraud_detector && python main.py
```

## Fayllar

| Fayl | Vazifasi |
|---|---|
| `config.py` | `.env`, KPI jadvali, chegaralar, filial filtri |
| `davr.py` | yarim oy / oyna / tarix sanalari |
| `aros_api.py` | Aros orders klienti (pagination, rate-limit, retry) |
| `filial_data.py` | filial ro'yxati + plan/bajarildi (n8n yoki PG) |
| `scoring.py` | 5 signal, ball, daraja |
| `excel_report.py` | 2 varaqli Excel |
| `detal.py` | order detali: yakunlanish sanasi + vozvrat, parallel + kesh |
| `demo_data.py` | `--demo` uchun sun'iy ma'lumot |
| `main.py` | CLI |

## Kelajak kengaytma

Shubhali orderlarni bazaga yozib borish → vozvrat kelganda tasdiqlash
(order haqiqatan qaytdimi) → algoritm ishonchini o'lchash.
