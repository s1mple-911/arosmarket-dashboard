#!/usr/bin/env bash
# =====================================================================
# N8N_ORDERS_PAYMENT_FIX.sh — 2026-10-06 — ikki tuzatish (Postgres orqali, MCP update_workflow ISHLATILMAYDI)
#  1) Cache Builder (xgfB2F52mXZ5tJJk) «Build Cache»: confirmedOrders[] ga `payment_method` (cash/wallet/click…) va
#     `delivery_method` qo'shiladi — mini app ochiq buyurtmalarda to'lov turini ko'rsatadi (Asilbek).
#  2) Debtors V2 API (zQXwQmoheSiUj6qm) «Prep Orders»: filial filtri `wid` BILAN BIRGA `api_wid` ni ham qabul qiladi.
#  3) 🔴 Orders API (ZNt6IqsCtRSX1Xl7, webhook aros-orders) «Code orders»: AKSESSUAR_MAP qattiq xarita {100:71,103:73,104:75}
#     — Qarshi Bahor aksessuar (102→91) TUSHIB QOLGAN → mijoz 16008 bosilganda «Order topilmadi» (buyurtmalar warehouse 91,
#     filtr 102). Xaritaga 102:91 qo'shiladi VA klient yuboradigan `api_warehouse_id` ham qabul qilinadi (kelajakda yangi
#     aksessuar filial qo'shilsa xaritani kutmaydi).
#  4) Cache Builder trigger «Every 1 Hour»: har soat → cron `0 0,7-23 * * *` (n8n TZ=Asia/Tashkent): 07:00–23:00 har soat,
#     oxirgi 00:00, kechasi 01:00–06:00 ISHLAMAYDI (Asilbek 2026-10-06). Node nomi saqlanadi (ichki havolalar buzilmasin).
#
# ISHLATISH (Asilbek, bitta buyruq):
#   ssh root@37.27.15.184 'bash -s' < /Users/s1mple/Projects/arosmarket-dashboard/N8N_ORDERS_PAYMENT_FIX.sh
# Keyin n8n UI da IKKALA workflow'ni ochib «Publish». Zaxira: /root/n8n-backups/<id>_<vaqt>.json. Qayta ishga tushirish xavfsiz.
# =====================================================================
set -euo pipefail
PG="docker exec n8n-postgres psql -U n8n -d n8n"
mkdir -p /root/n8n-backups
for WF in xgfB2F52mXZ5tJJk zQXwQmoheSiUj6qm ZNt6IqsCtRSX1Xl7; do
  $PG -Atc "select row_to_json(w) from workflow_entity w where id='$WF'" > /root/n8n-backups/${WF}_$(date +%Y%m%d_%H%M%S).json
  $PG -Atc "select nodes::text from workflow_entity where id='$WF'" > /tmp/${WF}_nodes.json
done
echo "zaxiralar: $(ls -t /root/n8n-backups/*.json | head -2 | tr '\n' ' ')"

python3 - <<'PYEOF'
import json
# 1) Cache Builder — Build Cache
p="/tmp/xgfB2F52mXZ5tJJk_nodes.json"; nodes=json.load(open(p)); hit=False
for n in nodes:
    if n["name"]=="Build Cache":
        c=n["parameters"]["jsCode"]
        if "payment_method" in c: print("Build Cache: payment_method allaqachon bor"); hit=True; break
        old="    status: o.status || '', is_transfer: isTransfer,\n    from_warehouse_name: fromWarehouseName\n  };"
        assert c.count(old)==1, "Build Cache: confirmedOrders bloki topilmadi"
        new=("    status: o.status || '', is_transfer: isTransfer,\n"
             "    from_warehouse_name: fromWarehouseName,\n"
             "    // 2026-10-06 (Asilbek): to'lov turi va yetkazish usuli — mini app ochiq buyurtmalarda ko'rsatiladi\n"
             "    payment_method: o.payment_method || null,\n"
             "    delivery_method: o.delivery_method || null\n  };")
        n["parameters"]["jsCode"]=c.replace(old,new); hit=True; print("Build Cache: payment_method qo'shildi")
assert hit, "Build Cache node topilmadi"
# 4) Cache Builder trigger — kechasi 01:00–06:00 ishlamasin
trg=[n for n in nodes if n.get("type")=="n8n-nodes-base.scheduleTrigger"]
assert len(trg)==1, "scheduleTrigger node 1 ta bo'lishi kerak: %d" % len(trg)
rule=trg[0]["parameters"].get("rule",{}); iv=rule.get("interval",[{}])
if iv and iv[0].get("field")=="cronExpression" and iv[0].get("expression")=="0 0,7-23 * * *":
    print("Trigger: cron allaqachon 0 0,7-23")
else:
    trg[0]["parameters"]["rule"]={"interval":[{"field":"cronExpression","expression":"0 0,7-23 * * *"}]}
    print("Trigger: har soat → cron 0 0,7-23 * * * (Toshkent; 01:00–06:00 ishlamaydi)")
json.dump(nodes, open(p+".new","w"), ensure_ascii=False)
# 2) Debtors V2 API — Prep Orders
p="/tmp/zQXwQmoheSiUj6qm_nodes.json"; nodes=json.load(open(p)); hit=False
for n in nodes:
    if n["name"]=="Prep Orders":
        c=n["parameters"]["jsCode"]
        if "api_wid" in c: print("Prep Orders: api_wid allaqachon bor"); hit=True; break
        old1="const wid = q.wid ? parseInt(q.wid) : null;"
        old2="  if (wid && w && w !== wid) return false;"
        assert c.count(old1)==1 and c.count(old2)==1, "Prep Orders: kutilgan satrlar topilmadi"
        new1=("const wid = q.wid ? parseInt(q.wid) : null;\n"
              "// 2026-10-06: filialning IKKI id si (dashboard warehouse_id va Aros api_warehouse_id) — ikkalasi ham qabul qilinadi.\n"
              "// Aros buyurtmalarida warehouse.id = API id (masalan Qarshi Bahor aksessuar 102 → 91); faqat 102 bilan hammasi filtrlanib «order yo'q» bo'lardi.\n"
              "const wids = [q.wid, q.api_wid].map(function (x) { return x ? parseInt(x) : null; }).filter(function (x) { return x && !isNaN(x); });")
        new2="  if (wids.length && w && wids.indexOf(w) < 0) return false;"
        n["parameters"]["jsCode"]=c.replace(old1,new1).replace(old2,new2); hit=True; print("Prep Orders: api_wid qo'shildi")
assert hit, "Prep Orders node topilmadi"
json.dump(nodes, open(p+".new","w"), ensure_ascii=False)
# 3) Orders API — Code orders (AKSESSUAR_MAP + api_warehouse_id)
p="/tmp/ZNt6IqsCtRSX1Xl7_nodes.json"; nodes=json.load(open(p)); hit=False
for n in nodes:
    if n["name"]=="Code orders":
        c=n["parameters"]["jsCode"]
        if "api_warehouse_id" in c: print("Code orders: allaqachon patch qilingan"); hit=True; break
        old_map="const AKSESSUAR_MAP = { '100': 71, '103': 73, '104': 75 };"
        old_w="let warehouseId = query.warehouse_id ? parseInt(query.warehouse_id) : null;\nif (warehouseId && AKSESSUAR_MAP[String(warehouseId)]) {\n  warehouseId = AKSESSUAR_MAP[String(warehouseId)];\n}"
        assert c.count(old_map)==1 and c.count(old_w)==1, "Code orders: kutilgan satrlar topilmadi"
        new_map=("// 2026-10-06: 102 (Qarshi Bahor aksessuar) → 91 QO'SHILDI (tushib qolgan edi → «Order topilmadi»).\n"
                 "// Xarita zaxira — asosiy manba klient yuboradigan api_warehouse_id (cache_filial.data.api_warehouse_id).\n"
                 "const AKSESSUAR_MAP = { '100': 71, '102': 91, '103': 73, '104': 75 };")
        new_w=("const rawWid = query.warehouse_id ? parseInt(query.warehouse_id) : null;\n"
               "const apiWid = query.api_warehouse_id ? parseInt(query.api_warehouse_id) : null;\n"
               "// Ruxsat etilgan warehouse id lar: dashboard id, xaritadagi api id, klient bergan api id — bittasi mos kelsa yetadi\n"
               "const allowedWids = [rawWid, rawWid && AKSESSUAR_MAP[String(rawWid)], apiWid].filter(function (x) { return x && !isNaN(x); });\n"
               "let warehouseId = allowedWids.length ? allowedWids[0] : null;")
        c=c.replace(old_map,new_map).replace(old_w,new_w)
        old_f="    if (warehouseId && w && w !== warehouseId) return false;"
        assert c.count(old_f)==2, "Code orders: filtr satri 2 ta bo'lishi kerak"
        c=c.replace(old_f,"    if (allowedWids.length && w && allowedWids.indexOf(w) < 0) return false;")
        n["parameters"]["jsCode"]=c; hit=True; print("Code orders: 102:91 + api_warehouse_id qo'shildi")
assert hit, "Code orders node topilmadi"
json.dump(nodes, open(p+".new","w"), ensure_ascii=False)
PYEOF

for WF in xgfB2F52mXZ5tJJk zQXwQmoheSiUj6qm ZNt6IqsCtRSX1Xl7; do
  docker cp /tmp/${WF}_nodes.json.new n8n-postgres:/tmp/${WF}_nodes.json.new
  cat > /tmp/${WF}_upd.sql <<SQLEOF
\set nodes \`cat /tmp/${WF}_nodes.json.new\`
begin;
update workflow_entity set nodes = :'nodes'::json, "versionId" = gen_random_uuid(), "updatedAt" = now() where id = '${WF}';
insert into workflow_history ("versionId","workflowId",authors,"createdAt","updatedAt",nodes,connections)
select "versionId", id, 'Asilbek (orders/payment fix 2026-10-06)', now(), now(), nodes, connections from workflow_entity where id = '${WF}';
commit;
select name, "versionId" as yangi_versiya, "activeVersionId" as faol_versiya from workflow_entity where id = '${WF}';
SQLEOF
  docker cp /tmp/${WF}_upd.sql n8n-postgres:/tmp/${WF}_upd.sql
  $PG -f /tmp/${WF}_upd.sql
done
echo "TAYYOR — n8n UI da «Aros Market - Cache Builder», «Aros Market - Debtors V2 API» va «Aros Market - Orders API» ni ochib Publish bosing."
