#!/usr/bin/env bash
# =====================================================================
# N8N_BAJARILDI_AYIRISH.sh — 2026-10-09 — filial "bajarildi" summasidan qo'lda ayirish (DB darajasida)
#  Asilbek: Oktyabr 2026 1-yarim — Izza shourum aksessuar (wid 103) −638 000 000,
#           43- Do'kon (wid 100) −236 400 000. Frontendda emas — kesh/oylik hisob ham shu summani olishi kerak.
#
#  1) Yangi jadval `filial_bajarildi_ayirish` (warehouse_id, yil, oy, oy_yarim, summa, izoh) — filial_plan_half'dan
#     ALOHIDA: admin.html'dagi plan «reset» (DELETE) ayirishni o'chirib yubormasin, Plan Override Apply plan'ga tegmasin.
#  2) Cache Builder (xgfB2F52mXZ5tJJk):
#     - «Get Filial Plan Half PG»: FULL JOIN bilan `bajarildi_ayirish` ustuni qo'shiladi (override yo'q filial ham oladi;
#       plan NULL bo'lsa attachOverride avvalgidek has_plan_override=false qiladi).
#     - «Prepare Filials» attachOverride: obj.ov_bajarildi_ayirish.
#     - «Build Cache»: bajarildi = max(0, bajarildi − ayirish); foiz/qoldi/prognoz shu yangi bajarildi'dan hisoblanadi.
#       orders_summa (tushum) / returns_summa o'zgarmaydi. cacheData'ga bajarildi_ayirish yoziladi (iz qolsin).
#
# ISHLATISH (Asilbek, bitta buyruq):
#   ssh root@37.27.15.184 'bash -s' < /Users/s1mple/Projects/arosmarket-dashboard/N8N_BAJARILDI_AYIRISH.sh
# Keyin n8n UI da «Aros Market - Cache Builder» ni ochib «Publish» → keyingi soatlik yugurishda (yoki qo'lda Execute)
# kesh yangilanadi. Zaxira: /root/n8n-backups/<id>_<vaqt>.json. Qayta ishga tushirish xavfsiz.
# Keyinchalik summa o'zgartirish/olib tashlash — faqat jadvalda (workflow'ga tegmasdan):
#   update filial_bajarildi_ayirish set summa=... where warehouse_id=103 and yil=2026 and oy=10 and oy_yarim=1;
# =====================================================================
set -euo pipefail
PG="docker exec n8n-postgres psql -U n8n -d n8n -v ON_ERROR_STOP=1"
WF=xgfB2F52mXZ5tJJk
mkdir -p /root/n8n-backups
$PG -Atc "select row_to_json(w) from workflow_entity w where id='$WF'" > /root/n8n-backups/${WF}_$(date +%Y%m%d_%H%M%S).json
$PG -Atc "select nodes::text from workflow_entity where id='$WF'" > /tmp/${WF}_nodes.json
echo "zaxira: $(ls -t /root/n8n-backups/${WF}_*.json | head -1)"

# --- ilova bazasini topish (cache_filial + filial_plan_half n8n bazasida EMAS — workflow'ning Postgres credential bazasi) ---
APPDB=""
for D in aros kundalik postgres; do
  R=$($PG -d "$D" -Atc "select to_regclass('public.cache_filial') is not null and to_regclass('public.filial_plan_half') is not null" 2>/dev/null || true)
  if [ "$R" = "t" ]; then APPDB="$D"; break; fi
done
[ -n "$APPDB" ] || { echo "XATO: cache_filial + filial_plan_half bor baza topilmadi"; exit 1; }
echo "ilova bazasi: $APPDB"
APG="docker exec n8n-postgres psql -U n8n -d $APPDB -v ON_ERROR_STOP=1"
APGI="docker exec -i n8n-postgres psql -U n8n -d $APPDB -v ON_ERROR_STOP=1"

# --- filial nomlarini tekshirish (wid xato bo'lsa to'xtaydi) ---
N100=$($APG -Atc "select data->>'filial' from cache_filial where warehouse_id::text='100' and oy_yarim=1")
N103=$($APG -Atc "select data->>'filial' from cache_filial where warehouse_id::text='103' and oy_yarim=1")
echo "wid 100 = $N100 | wid 103 = $N103"
echo "$N100" | grep -qi "43" || { echo "XATO: wid 100 — 43- Do'kon emas"; exit 1; }
echo "$N103" | grep -qi "izza" || { echo "XATO: wid 103 — Izza emas"; exit 1; }
echo "$N103" | grep -qi "aksessuar" || { echo "XATO: wid 103 — aksessuar emas"; exit 1; }

# --- 1) jadval + qiymatlar ---
$APGI <<'SQLEOF'
create table if not exists filial_bajarildi_ayirish (
  warehouse_id int not null,
  yil int not null,
  oy int not null,
  oy_yarim int not null,
  summa numeric not null default 0,
  izoh text,
  updated_at timestamptz not null default now(),
  primary key (warehouse_id, yil, oy, oy_yarim)
);
insert into filial_bajarildi_ayirish (warehouse_id, yil, oy, oy_yarim, summa, izoh) values
  (103, 2026, 10, 1, 638000000, 'Izza shourum aksessuar — Asilbek 2026-10-09'),
  (100, 2026, 10, 1, 236400000, '43- Do''kon — Asilbek 2026-10-09')
on conflict (warehouse_id, yil, oy, oy_yarim) do update set summa=excluded.summa, izoh=excluded.izoh, updated_at=now();
-- n8n credential qaysi rol bilan ulansa ham o'qiy olsin: filial_plan_half egasiga ham huquq
do $$ declare o text; begin
  select tableowner into o from pg_tables where schemaname='public' and tablename='filial_plan_half';
  if o is not null and o <> current_user then execute format('grant all on filial_bajarildi_ayirish to %I', o); end if;
end $$;
select * from filial_bajarildi_ayirish order by yil, oy, oy_yarim, warehouse_id;
SQLEOF

# --- 2) Cache Builder patch ---
python3 - <<'PYEOF'
import json
p="/tmp/xgfB2F52mXZ5tJJk_nodes.json"; nodes=json.load(open(p)); N={n["name"]:n for n in nodes}

# 2a) Get Filial Plan Half PG
q=N["Get Filial Plan Half PG"]["parameters"]["query"]
if "bajarildi_ayirish" in q: print("Get Filial Plan Half PG: allaqachon bor")
else:
    N["Get Filial Plan Half PG"]["parameters"]["query"]=(
"""-- 2026-10-09: filial_bajarildi_ayirish FULL JOIN (override yo'q filial uchun ham ayirish keladi)
WITH f AS (
  SELECT warehouse_id::text AS warehouse_id, oy_yarim::int AS oy_yarim, plan, qarz_limit, hodim_plan, fiksa
  FROM filial_plan_half
  WHERE yil = EXTRACT(YEAR FROM (NOW() + INTERVAL '5 hours'))::int
    AND oy = EXTRACT(MONTH FROM (NOW() + INTERVAL '5 hours'))::int
), a AS (
  SELECT warehouse_id::text AS warehouse_id, oy_yarim::int AS oy_yarim, SUM(summa) AS summa
  FROM filial_bajarildi_ayirish
  WHERE yil = EXTRACT(YEAR FROM (NOW() + INTERVAL '5 hours'))::int
    AND oy = EXTRACT(MONTH FROM (NOW() + INTERVAL '5 hours'))::int
  GROUP BY warehouse_id, oy_yarim
)
SELECT COALESCE(f.warehouse_id, a.warehouse_id) AS warehouse_id,
       COALESCE(f.oy_yarim, a.oy_yarim) AS oy_yarim,
       f.plan, f.qarz_limit, f.hodim_plan, f.fiksa,
       COALESCE(a.summa, 0) AS bajarildi_ayirish
FROM f FULL OUTER JOIN a ON a.warehouse_id = f.warehouse_id AND a.oy_yarim = f.oy_yarim""")
    print("Get Filial Plan Half PG: bajarildi_ayirish qo'shildi")

# 2b) Prepare Filials — attachOverride
c=N["Prepare Filials"]["parameters"]["jsCode"]
if "ov_bajarildi_ayirish" in c: print("Prepare Filials: allaqachon bor")
else:
    o1="    obj.has_plan_override = obj.ov_plan > 0;\n"
    o2="    obj.ov_plan = 0; obj.ov_qarz_limit = 0; obj.ov_hodim_plan = 0; obj.ov_fiksa = 0;\n"
    assert c.count(o1)==1 and c.count(o2)==1, "Prepare Filials: attachOverride topilmadi"
    c=c.replace(o1,o1+"    obj.ov_bajarildi_ayirish = parseNum(ov.bajarildi_ayirish);\n")
    c=c.replace(o2,o2+"    obj.ov_bajarildi_ayirish = 0;\n")
    N["Prepare Filials"]["parameters"]["jsCode"]=c; print("Prepare Filials: ov_bajarildi_ayirish qo'shildi")

# 2c) Build Cache
c=N["Build Cache"]["parameters"]["jsCode"]
if "bajarildiAyirish" in c: print("Build Cache: allaqachon bor")
else:
    o1=("    bajarildi = sheetsBajarildi;\n    bajarildi_source = 'sheets_fallback';\n  }\n}\n")
    assert c.count(o1)==1, "Build Cache: bajarildi bloki topilmadi"
    c=c.replace(o1,o1+
        "// 2026-10-09 (Asilbek): qo'lda ayirish — filial_bajarildi_ayirish jadvalidan (foiz/qoldi/prognoz shundan)\n"
        "const bajarildiAyirish = parseFloat(filial.ov_bajarildi_ayirish) || 0;\n"
        "if (bajarildiAyirish > 0) bajarildi = Math.max(0, bajarildi - bajarildiAyirish);\n")
    o2="  bajarildi, foiz, qoldi, prognoz, prognoz_foiz: prognozFoiz,\n"
    assert c.count(o2)==1, "Build Cache: cacheData bajarildi satri topilmadi"
    c=c.replace(o2,"  bajarildi_ayirish: bajarildiAyirish,\n"+o2)
    N["Build Cache"]["parameters"]["jsCode"]=c; print("Build Cache: ayirish qo'shildi")

json.dump(nodes, open(p+".new","w"), ensure_ascii=False)
PYEOF

docker cp /tmp/${WF}_nodes.json.new n8n-postgres:/tmp/${WF}_nodes.json.new
cat > /tmp/${WF}_upd.sql <<SQLEOF
\set nodes \`cat /tmp/${WF}_nodes.json.new\`
begin;
update workflow_entity set nodes = :'nodes'::json, "versionId" = gen_random_uuid(), "updatedAt" = now() where id = '${WF}';
insert into workflow_history ("versionId","workflowId",authors,"createdAt","updatedAt",nodes,connections)
select "versionId", id, 'Asilbek (bajarildi ayirish 2026-10-09)', now(), now(), nodes, connections from workflow_entity where id = '${WF}';
commit;
select name, "versionId" as yangi_versiya, "activeVersionId" as faol_versiya from workflow_entity where id = '${WF}';
SQLEOF
docker cp /tmp/${WF}_upd.sql n8n-postgres:/tmp/${WF}_upd.sql
$PG -f /tmp/${WF}_upd.sql
echo "TAYYOR — n8n UI da «Aros Market - Cache Builder» ni ochib Publish bosing, so'ng Execute (yoki keyingi soatni kuting)."
