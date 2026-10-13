#!/usr/bin/env bash
# =====================================================================
# N8N_BAJARILDI_QOSHISH.sh — 2026-10-13 — filial "bajarildi" summasiga qo'lda QO'SHISH (ayirish bilan yonma-yon)
#  Asilbek: Oktyabr 2026 1-yarim — Qarshi shourum (wid 104) +82 324 000, 43- Do'kon (wid 100) +2 127 000,
#           Izza shourum aksessuar (wid 103) +0, Qarshi Bahor aksessuar (wid 102) +69 681 000.
#  Avvalgi ayirish (103 −638 000 000, 100 −236 400 000) SAQLANADI — ikkalasi birga: bajarildi = max(0, savdo − ayirish + qoshish).
#
#  1) `filial_bajarildi_ayirish` jadvaliga `qoshish numeric default 0` ustuni (bitta jadval, ikki yo'nalish).
#  2) Cache Builder (xgfB2F52mXZ5tJJk):
#     - «Get Filial Plan Half PG»: `bajarildi_qoshish` ustuni ham qaytadi (SUM(qoshish)).
#     - «Prepare Filials» attachOverride: obj.ov_bajarildi_qoshish.
#     - «Build Cache»: bajarildi = max(0, bajarildi − ayirish + qoshish); cacheData'ga bajarildi_qoshish yoziladi.
#
# ISHLATISH (Asilbek, bitta buyruq):
#   ssh root@37.27.15.184 'bash -s' < /Users/s1mple/Projects/arosmarket-dashboard/N8N_BAJARILDI_QOSHISH.sh
# Keyin n8n UI da «Aros Market - Cache Builder» ni ochib «Publish» → Execute (yoki keyingi soat). Qayta ishga tushirish xavfsiz.
# Keyinchalik summa o'zgartirish — faqat jadvalda:
#   update filial_bajarildi_ayirish set qoshish=... where warehouse_id=104 and yil=2026 and oy=10 and oy_yarim=1;
# =====================================================================
set -euo pipefail
PG="docker exec n8n-postgres psql -U n8n -d n8n -v ON_ERROR_STOP=1"
WF=xgfB2F52mXZ5tJJk
mkdir -p /root/n8n-backups
$PG -Atc "select row_to_json(w) from workflow_entity w where id='$WF'" > /root/n8n-backups/${WF}_$(date +%Y%m%d_%H%M%S).json
$PG -Atc "select nodes::text from workflow_entity where id='$WF'" > /tmp/${WF}_nodes.json
echo "zaxira: $(ls -t /root/n8n-backups/${WF}_*.json | head -1)"

APPDB=""
for D in aros kundalik postgres; do
  R=$($PG -d "$D" -Atc "select to_regclass('public.cache_filial') is not null and to_regclass('public.filial_bajarildi_ayirish') is not null" 2>/dev/null || true)
  if [ "$R" = "t" ]; then APPDB="$D"; break; fi
done
[ -n "$APPDB" ] || { echo "XATO: cache_filial + filial_bajarildi_ayirish bor baza topilmadi (avval N8N_BAJARILDI_AYIRISH.sh)"; exit 1; }
echo "ilova bazasi: $APPDB"
APG="docker exec n8n-postgres psql -U n8n -d $APPDB -v ON_ERROR_STOP=1"
APGI="docker exec -i n8n-postgres psql -U n8n -d $APPDB -v ON_ERROR_STOP=1"

# --- filial nomlarini tekshirish ---
for W in 100 102 103 104; do
  N=$($APG -Atc "select data->>'filial' from cache_filial where warehouse_id::text='$W' and oy_yarim=1")
  echo "wid $W = $N"
  case $W in
    100) echo "$N" | grep -qi "43" || { echo "XATO: wid 100 — 43- Do'kon emas"; exit 1; } ;;
    102) echo "$N" | grep -qi "bahor" || { echo "XATO: wid 102 — Bahor emas"; exit 1; } ;;
    103) echo "$N" | grep -qi "izza" || { echo "XATO: wid 103 — Izza emas"; exit 1; } ;;
    104) echo "$N" | grep -qi "qarshi shou" || { echo "XATO: wid 104 — Qarshi shourum emas"; exit 1; } ;;
  esac
done

# --- 1) ustun + qiymatlar (summa = ayirish SAQLANADI, faqat qoshish yoziladi) ---
$APGI <<'SQLEOF'
alter table filial_bajarildi_ayirish add column if not exists qoshish numeric not null default 0;
insert into filial_bajarildi_ayirish (warehouse_id, yil, oy, oy_yarim, summa, qoshish, izoh) values
  (104, 2026, 10, 1, 0, 82324000, 'Qarshi shourum +82 324 000 — Asilbek 2026-10-13'),
  (100, 2026, 10, 1, 0, 2127000,  '43- Do''kon +2 127 000 — Asilbek 2026-10-13'),
  (103, 2026, 10, 1, 0, 0,        'Izza shourum aksessuar +0 — Asilbek 2026-10-13'),
  (102, 2026, 10, 1, 0, 69681000, 'Qarshi Bahor aksessuar +69 681 000 — Asilbek 2026-10-13')
on conflict (warehouse_id, yil, oy, oy_yarim) do update
  set qoshish = excluded.qoshish,
      izoh = coalesce(filial_bajarildi_ayirish.izoh, '') || ' | ' || excluded.izoh,
      updated_at = now();
select warehouse_id, oy_yarim, summa as ayirish, qoshish, izoh from filial_bajarildi_ayirish order by yil, oy, oy_yarim, warehouse_id;
SQLEOF

# --- 2) Cache Builder patch ---
python3 - <<'PYEOF'
import json
p="/tmp/xgfB2F52mXZ5tJJk_nodes.json"; nodes=json.load(open(p)); N={n["name"]:n for n in nodes}

# 2a) Get Filial Plan Half PG — qoshish ham qaytsin
q=N["Get Filial Plan Half PG"]["parameters"]["query"]
if "bajarildi_qoshish" in q: print("Get Filial Plan Half PG: allaqachon bor")
else:
    o1="SUM(summa) AS summa\n"
    o2="       COALESCE(a.summa, 0) AS bajarildi_ayirish\n"
    assert q.count(o1)==1 and q.count(o2)==1, "Get Filial Plan Half PG: kutilgan satrlar topilmadi"
    q=q.replace(o1,"SUM(summa) AS summa, SUM(COALESCE(qoshish, 0)) AS qoshish\n")
    q=q.replace(o2,"       COALESCE(a.summa, 0) AS bajarildi_ayirish,\n       COALESCE(a.qoshish, 0) AS bajarildi_qoshish\n")
    N["Get Filial Plan Half PG"]["parameters"]["query"]=q; print("Get Filial Plan Half PG: bajarildi_qoshish qo'shildi")

# 2b) Prepare Filials
c=N["Prepare Filials"]["parameters"]["jsCode"]
if "ov_bajarildi_qoshish" in c: print("Prepare Filials: allaqachon bor")
else:
    o1="    obj.ov_bajarildi_ayirish = parseNum(ov.bajarildi_ayirish);\n"
    o2="    obj.ov_bajarildi_ayirish = 0;\n"
    assert c.count(o1)==1 and c.count(o2)==1, "Prepare Filials: ayirish satrlari topilmadi"
    c=c.replace(o1,o1+"    obj.ov_bajarildi_qoshish = parseNum(ov.bajarildi_qoshish);\n")
    c=c.replace(o2,o2+"    obj.ov_bajarildi_qoshish = 0;\n")
    N["Prepare Filials"]["parameters"]["jsCode"]=c; print("Prepare Filials: ov_bajarildi_qoshish qo'shildi")

# 2c) Build Cache
c=N["Build Cache"]["parameters"]["jsCode"]
if "bajarildiQoshish" in c: print("Build Cache: allaqachon bor")
else:
    o1="if (bajarildiAyirish > 0) bajarildi = Math.max(0, bajarildi - bajarildiAyirish);\n"
    assert c.count(o1)==1, "Build Cache: ayirish satri topilmadi"
    c=c.replace(o1,
        "// 2026-10-13 (Asilbek): qo'lda qo'shish ham — ayirish bilan birga: bajarildi = max(0, savdo − ayirish + qoshish)\n"
        "const bajarildiQoshish = parseFloat(filial.ov_bajarildi_qoshish) || 0;\n"
        "if (bajarildiAyirish !== 0 || bajarildiQoshish !== 0) bajarildi = Math.max(0, bajarildi - bajarildiAyirish + bajarildiQoshish);\n")
    o2="  bajarildi_ayirish: bajarildiAyirish,\n"
    assert c.count(o2)==1, "Build Cache: cacheData ayirish satri topilmadi"
    c=c.replace(o2,o2+"  bajarildi_qoshish: bajarildiQoshish,\n")
    N["Build Cache"]["parameters"]["jsCode"]=c; print("Build Cache: qoshish qo'shildi")

json.dump(nodes, open(p+".new","w"), ensure_ascii=False)
PYEOF

docker cp /tmp/${WF}_nodes.json.new n8n-postgres:/tmp/${WF}_nodes.json.new
cat > /tmp/${WF}_upd.sql <<SQLEOF
\set nodes \`cat /tmp/${WF}_nodes.json.new\`
begin;
update workflow_entity set nodes = :'nodes'::json, "versionId" = gen_random_uuid(), "updatedAt" = now() where id = '${WF}';
insert into workflow_history ("versionId","workflowId",authors,"createdAt","updatedAt",nodes,connections)
select "versionId", id, 'Asilbek (bajarildi qoshish 2026-10-13)', now(), now(), nodes, connections from workflow_entity where id = '${WF}';
commit;
select name, "versionId" as yangi_versiya, "activeVersionId" as faol_versiya from workflow_entity where id = '${WF}';
SQLEOF
docker cp /tmp/${WF}_upd.sql n8n-postgres:/tmp/${WF}_upd.sql
$PG -f /tmp/${WF}_upd.sql
echo "TAYYOR — n8n UI da «Aros Market - Cache Builder» ni ochib Publish bosing, so'ng Execute (yoki keyingi soatni kuting)."
