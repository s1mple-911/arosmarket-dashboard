#!/usr/bin/env bash
# =====================================================================
# N8N_CEO_HODIM_FILIAL_BAJARILDI.sh — 2026-11-02 — «Aros Market - CEO Hodimlar API» (N3FUObspigFbIEiC)
#
# SABAB: ceo-hodimlar Excel'ida filial faqat FOIZ bilan chiqadi — Asilbek filialning qancha BAJARILGANINI (summa) ham so'radi.
#   * realtime yo'li: hodimda `filial_bajarildi` allaqachon bor, `filial_plan` yo'q edi;
#   * history yo'li (yopilgan yarimlar, hodim_kpi_history): ikkalasi ham yo'q edi.
#
# NIMA O'ZGARADI (javobga yangi maydonlar qo'shiladi, eski maydonlar tegilmaydi):
#   1) Get History (SQL): hodim_kpi_history ga cache_filial_history (shu yil/oy/yarim) LATERAL JOIN →
#      filial_bajarildi, filial_plan. Arxivda bajarildi 0/yo'q bo'lsa (RESYNC yozmagan filiallar) cache_filial'ning
#      o'sha davrdagi qatori (data.yil/oy_raqami mos) ishlatiladi.
#   2) Build History Response: filial va hodim obyektlariga filial_bajarildi / filial_plan.
#   3) Get All Filial Foiz PG: + (data->>'plan') AS filial_plan; Prepare Worker Jobs, Calc Worker KPI,
#      Build Realtime Response: filial_plan (va filialda filial_bajarildi) uzatiladi.
#
#   ssh root@37.27.15.184 'bash -s' < /Users/s1mple/Projects/arosmarket-dashboard/N8N_CEO_HODIM_FILIAL_BAJARILDI.sh
#   ssh root@37.27.15.184 'bash -s -- --rollback' < ...            (oxirgi zaxiradan qaytarish)
#   ssh root@37.27.15.184 'bash -s -- --rollback /root/n8n-backups/<fayl>.json' < ...
# Keyin n8n UI: «Aros Market - CEO Hodimlar API» → Publish. Qayta ishga tushirish xavfsiz (o'zgarish yo'q bo'lsa yozilmaydi).
# =====================================================================
set -euo pipefail
WF=N3FUObspigFbIEiC
PG="docker exec n8n-postgres psql -U n8n -d n8n"
MODE=apply
RB_FILE=""
while [ $# -gt 0 ]; do
  case "$1" in
    --rollback) MODE=rollback; shift; RB_FILE="${1:-}"; [ -n "$RB_FILE" ] && shift; continue ;;
    *) echo "noma'lum argument: $1"; exit 2 ;;
  esac
done

RUNNING=$($PG -Atc "select count(*) from execution_entity where \"workflowId\"='$WF' and status in ('running','new','waiting')")
if [ "$RUNNING" != "0" ]; then echo "XATO: workflow hozir ishlayapti ($RUNNING execution) — tugashini kuting."; exit 1; fi

mkdir -p /root/n8n-backups
if [ "$MODE" = "rollback" ]; then
  [ -n "$RB_FILE" ] || RB_FILE=$(ls -t /root/n8n-backups/${WF}_*.json | head -1)
  [ -f "$RB_FILE" ] || { echo "zaxira topilmadi: $RB_FILE"; exit 1; }
  echo "qaytarish: $RB_FILE"
  python3 - "$RB_FILE" <<'PYEOF'
import json, sys
w = json.load(open(sys.argv[1]))
json.dump(w["nodes"], open("/tmp/ceoh_nodes_new.json", "w"), ensure_ascii=False)
json.dump(w["connections"], open("/tmp/ceoh_conn_new.json", "w"), ensure_ascii=False)
print("zaxira o'qildi: node", len(w["nodes"]))
PYEOF
else
  $PG -Atc "select row_to_json(w) from workflow_entity w where id='$WF'" > /root/n8n-backups/${WF}_$(date +%Y%m%d_%H%M%S).json
  echo "zaxira: $(ls -t /root/n8n-backups/${WF}_*.json | head -1)"
  $PG -Atc "select nodes::text from workflow_entity where id='$WF'" > /tmp/ceoh_nodes.json
  $PG -Atc "select connections::text from workflow_entity where id='$WF'" > /tmp/ceoh_conn.json
  set +e
  CEOH_NODES=/tmp/ceoh_nodes.json CEOH_CONN=/tmp/ceoh_conn.json \
  CEOH_NODES_OUT=/tmp/ceoh_nodes_new.json CEOH_CONN_OUT=/tmp/ceoh_conn_new.json python3 - <<'PYEOF'
import json, os, sys

nodes = json.load(open(os.environ["CEOH_NODES"]))
conn = json.load(open(os.environ["CEOH_CONN"]))
by = {n["name"]: n for n in nodes}
for need in ("Get History", "Build History Response", "Get All Filial Foiz PG", "Prepare Worker Jobs", "Calc Worker KPI", "Build Realtime Response"):
    assert need in by, "node yo'q: " + need

changed = False
def rep(node, old, new, what):
    """old -> new, faqat bitta joyda; new allaqachon bo'lsa o'tkazib yuboriladi"""
    global changed
    p = by[node]["parameters"]
    key = "query" if node in ("Get History", "Get All Filial Foiz PG") else "jsCode"
    code = p[key]
    if new in code:
        return
    assert code.count(old) == 1, "%s: %s topilmadi (%d)" % (node, what, code.count(old))
    p[key] = code.replace(old, new)
    changed = True

# ---- 1. Get History: filial_bajarildi / filial_plan (cache_filial_history, bo'lmasa cache_filial) ----
OLD_Q = ("SELECT telegram_id, worker_id, warehouse_id, ism, lavozim, oy, yil, oy_yarim, hodim_plan, fiksa, jami_savdo, jami_qaytarilgan, "
         "jami_sof, jami_buyurtma, clients_jami, clients_aktiv, filial_foiz, kpi_foiz, kpi_bonus, boshqaruv_foiz, boshqaruv_bonus, oylik, fidoyilik "
         "FROM hodim_kpi_history WHERE oy = $1::int AND yil = $2::int AND (oy_yarim = $3::int OR oy_yarim = 0) ORDER BY warehouse_id, lavozim DESC")
NEW_Q = ("-- 2026-11-02: filial_bajarildi / filial_plan (Excel) — cache_filial_history, 0/yo'q bo'lsa cache_filial'ning o'sha davr qatori\n"
         "SELECT h.telegram_id, h.worker_id, h.warehouse_id, h.ism, h.lavozim, h.oy, h.yil, h.oy_yarim, h.hodim_plan, h.fiksa, h.jami_savdo, h.jami_qaytarilgan, "
         "h.jami_sof, h.jami_buyurtma, h.clients_jami, h.clients_aktiv, h.filial_foiz, h.kpi_foiz, h.kpi_bonus, h.boshqaruv_foiz, h.boshqaruv_bonus, h.oylik, h.fidoyilik, "
         "coalesce(nullif(cfh.baj, 0), cf.baj) AS filial_bajarildi, coalesce(cfh.plan, cf.plan) AS filial_plan "
         "FROM hodim_kpi_history h "
         "LEFT JOIN LATERAL (SELECT (x.data->>'bajarildi')::numeric AS baj, (x.data->>'plan')::numeric AS plan FROM cache_filial_history x "
         "WHERE x.warehouse_id = h.warehouse_id::text AND x.yil = h.yil AND x.oy = h.oy AND x.oy_yarim = h.oy_yarim LIMIT 1) cfh ON true "
         "LEFT JOIN LATERAL (SELECT (y.data->>'bajarildi')::numeric AS baj, (y.data->>'plan')::numeric AS plan FROM cache_filial y "
         "WHERE y.warehouse_id = h.warehouse_id::text AND y.oy_yarim = h.oy_yarim AND (y.data->>'yil')::int = h.yil AND (y.data->>'oy_raqami')::int = h.oy LIMIT 1) cf ON true "
         "WHERE h.oy = $1::int AND h.yil = $2::int AND (h.oy_yarim = $3::int OR h.oy_yarim = 0) ORDER BY h.warehouse_id, h.lavozim DESC")
rep("Get History", OLD_Q, NEW_Q, "SQL")

# ---- 2. Build History Response ----
rep("Build History Response",
    "      filial_prognoz_foiz: parseInt(r.filial_foiz || 0),\n      boshliq_ism: null, hodimlar_soni: 0,\n",
    "      filial_prognoz_foiz: parseInt(r.filial_foiz || 0),\n"
    "      filial_bajarildi: (r.filial_bajarildi == null ? null : parseFloat(r.filial_bajarildi)), // 2026-11-02 Excel\n"
    "      filial_plan: (r.filial_plan == null ? null : parseFloat(r.filial_plan)),\n"
    "      boshliq_ism: null, hodimlar_soni: 0,\n", "filMap filial_foiz")
rep("Build History Response",
    "    filial_foiz: parseInt(r.filial_foiz || 0), filial_prognoz_foiz: parseInt(r.filial_foiz || 0),\n",
    "    filial_foiz: parseInt(r.filial_foiz || 0), filial_prognoz_foiz: parseInt(r.filial_foiz || 0),\n"
    "    filial_bajarildi: (r.filial_bajarildi == null ? null : parseFloat(r.filial_bajarildi)),\n"
    "    filial_plan: (r.filial_plan == null ? null : parseFloat(r.filial_plan)),\n", "hodim filial_foiz")

# ---- 3. Realtime: filial_plan ----
rep("Get All Filial Foiz PG",
    "(data->>'prognoz')::numeric AS filial_prognoz, ",
    "(data->>'prognoz')::numeric AS filial_prognoz, (data->>'plan')::numeric AS filial_plan, ", "filial_prognoz ustuni")
rep("Prepare Worker Jobs",
    "    filial_prognoz: parseFloat(fil.filial_prognoz || 0),\n",
    "    filial_prognoz: parseFloat(fil.filial_prognoz || 0),\n    filial_plan: parseFloat(fil.filial_plan || 0),\n", "filial_prognoz")
rep("Calc Worker KPI",
    "  filial_bajarildi: loopItem.filial_bajarildi, filial_prognoz: loopItem.filial_prognoz,\n",
    "  filial_bajarildi: loopItem.filial_bajarildi, filial_prognoz: loopItem.filial_prognoz,\n  filial_plan: loopItem.filial_plan,\n", "filial_bajarildi")
rep("Build Realtime Response",
    "      filial_prognoz_foiz: h.filial_prognoz_foiz || 0,\n",
    "      filial_prognoz_foiz: h.filial_prognoz_foiz || 0,\n      filial_bajarildi: h.filial_bajarildi || 0, filial_plan: h.filial_plan || 0,\n", "filial_prognoz_foiz")

if not changed:
    print("allaqachon qo'llangan (o'zgarish yo'q)")
    sys.exit(3)

# ---- verify ----
names = [n["name"] for n in nodes]
assert len(names) == len(set(names)), "node nomlari takrorlanadi"
for src, v in conn.items():
    assert src in names, "connections: manba node yo'q: " + src
    for outs in v.get("main", []):
        for t in outs:
            assert t["node"] in names, "connections: nishon node yo'q: " + t["node"]
for nm in ("Build History Response", "Prepare Worker Jobs", "Calc Worker KPI", "Build Realtime Response"):
    code = by[nm]["parameters"]["jsCode"]
    assert code.count("{") == code.count("}"), nm + ": qavslar balansi buzildi"
    assert code.count("(") == code.count(")"), nm + ": () balansi buzildi"
q = by["Get History"]["parameters"]["query"]
assert q.count("(") == q.count(")") and "filial_bajarildi" in q and "$3::int" in q
json.dump(nodes, open(os.environ["CEOH_NODES_OUT"], "w"), ensure_ascii=False)
json.dump(conn, open(os.environ["CEOH_CONN_OUT"], "w"), ensure_ascii=False)
print("patch tayyor: history + realtime javobida filial_bajarildi / filial_plan")
PYEOF
  RC=$?
  set -e
  if [ "$RC" = "3" ]; then echo "O'zgarish yo'q — workflow'ga tegilmadi."; exit 0
  elif [ "$RC" != "0" ]; then echo "XATO: patch bajarilmadi (kod $RC) — workflow'ga tegilmadi."; exit "$RC"; fi
fi

docker cp /tmp/ceoh_nodes_new.json n8n-postgres:/tmp/ceoh_nodes_new.json
docker cp /tmp/ceoh_conn_new.json n8n-postgres:/tmp/ceoh_conn_new.json
cat > /tmp/ceoh_upd.sql <<'SQLEOF'
\set nodes `cat /tmp/ceoh_nodes_new.json`
\set conn `cat /tmp/ceoh_conn_new.json`
begin;
update workflow_entity
   set nodes = :'nodes'::json, connections = :'conn'::json, "versionId" = gen_random_uuid(), "updatedAt" = now()
 where id = 'N3FUObspigFbIEiC';
insert into workflow_history ("versionId","workflowId",authors,"createdAt","updatedAt",nodes,connections)
select "versionId", id, 'Asilbek (filial_bajarildi/filial_plan Excel 2026-11-02)', now(), now(), nodes, connections
  from workflow_entity where id = 'N3FUObspigFbIEiC';
commit;
select "versionId" as yangi_versiya, "activeVersionId" as faol_versiya from workflow_entity where id = 'N3FUObspigFbIEiC';
SQLEOF
docker cp /tmp/ceoh_upd.sql n8n-postgres:/tmp/ceoh_upd.sql
$PG -f /tmp/ceoh_upd.sql
echo "TAYYOR — n8n UI da «Aros Market - CEO Hodimlar API» ni ochib Publish bosing. Tekshirish: ceo-hodimlar-dev → Excel → «Filial plan», «Filial bajarildi» ustunlari."
