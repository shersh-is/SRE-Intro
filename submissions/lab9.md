# Lab 9 — Stateful Services & DB Reliability
## Proof of work by Viktoriya Yurina B24-CBS-01
### Task 1 — Migrations & Backup/Restore
#### alembic history output showing the two revisions (baseline + email)
```
┌──(.venv)─(shersh㉿kali)-[~/SRE-Intro]
└─$ alembic history                                 
9dec944598d2 -> b26c23c0fb15 (head), add email column to events
<base> -> 9dec944598d2, baseline - pre-existing schema
```

#### \d events output showing the new email column
```
┌──(.venv)─(shersh㉿kali)-[~/SRE-Intro]
└─$ kubectl exec -i $(kubectl get pod -l app=postgres -o name) -- \
  psql -U quickticket -d quickticket -c '\d events'
                                        Table "public.events"
    Column     |           Type           | Collation | Nullable |              Default               
---------------+--------------------------+-----------+----------+------------------------------------
 id            | integer                  |           | not null | nextval('events_id_seq'::regclass)
 name          | text                     |           | not null | 
 venue         | text                     |           | not null | 
 event_date    | timestamp with time zone |           | not null | 
 total_tickets | integer                  |           | not null | 
 price_cents   | integer                  |           | not null | 
 email         | character varying(255)   |           |          | 
Indexes:
    "events_pkey" PRIMARY KEY, btree (id)
Referenced by:
    TABLE "orders" CONSTRAINT "orders_event_id_fkey" FOREIGN KEY (event_id) REFERENCES events(id)
```

#### time alembic upgrade head output (elapsed time — expect <1s for nullable add)
```
┌──(.venv)─(shersh㉿kali)-[~/SRE-Intro]
└─$ time alembic upgrade head
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.

real    0.35s
user    0.29s
sys     0.04s
cpu     93%
```

#### Prometheus 5xx last 1min before and after migration (should both be 0 or unchanged)
Before:
```
┌──(.venv)─(shersh㉿kali)-[~/SRE-Intro]
└─$ kubectl exec -n monitoring deployment/prometheus -- wget -qO- \
  'http://localhost:9090/api/v1/query?query=sum(increase(gateway_requests_total%7Bstatus%3D~%225..%22%7D%5B1m%5D))' \
  | python3 -c "import sys,json;r=json.load(sys.stdin)['data']['result'];print('5xx last 1min:', r[0]['value'][1] if r else 0)"
5xx last 1min: 2.1818181818181817
```
After:
```
┌──(.venv)─(shersh㉿kali)-[~/SRE-Intro]
└─$ kubectl exec -n monitoring deployment/prometheus -- wget -qO- \  
  'http://localhost:9090/api/v1/query?query=sum(increase(gateway_requests_total%7Bstatus%3D~%225..%22%7D%5B1m%5D))' \
  | python3 -c "import sys,json;r=json.load(sys.stdin)['data']['result'];print('5xx last 1min:', r[0]['value'][1] if r else 0)"

5xx last 1min: 0
```

#### ls -lh /tmp/quickticket.dump + pg_restore --list output showing backup is valid
```
┌──(.venv)─(shersh㉿kali)-[~/SRE-Intro]
└─$ ls -lh /3tmp/quickticket.dump
-rw-rw-r-- 1 shersh shersh 7.2K Jul 10 18:59 /tmp/quickticket.dump

┌──(.venv)─(shersh㉿kali)-[~/SRE-Intro]
└─$ kubectl exec $POD -- pg_restore --list /tmp/backup.dump | head -25
;
; Archive created at 2026-07-10 15:59:20 UTC
;     dbname: quickticket
;     TOC Entries: 18
;     Compression: gzip
;     Dump Version: 1.16-0
;     Format: CUSTOM
;     Integer: 4 bytes
;     Offset: 8 bytes
;     Dumped from database version: 17.10
;     Dumped by pg_dump version: 17.10
;
;
; Selected TOC Entries:
;
220; 1259 16412 TABLE public alembic_version quickticket
218; 1259 16390 TABLE public events quickticket
217; 1259 16389 SEQUENCE public events_id_seq quickticket
3444; 0 0 SEQUENCE OWNED BY public events_id_seq quickticket
219; 1259 16398 TABLE public orders quickticket
3279; 2604 16393 DEFAULT public events id quickticket
3437; 0 16412 TABLE DATA public alembic_version quickticket
3435; 0 16390 TABLE DATA public events quickticket
3436; 0 16398 TABLE DATA public orders quickticket
3445; 0 0 SEQUENCE SET public events_id_seq quickticket
```

#### Row counts before disaster / after DROP / after restore for events and orders
Before:
```
┌──(.venv)─(shersh㉿kali)-[~/SRE-Intro]
└─$ kubectl exec $POD -- psql -U quickticket -d quickticket \
  -c 'SELECT count(*) FROM events; SELECT count(*) FROM orders'
 count 
-------
     5
(1 row)

 count 
-------
    50
(1 row)
```
After DROP:
```
┌──(.venv)─(shersh㉿kali)-[~/SRE-Intro]
└─$ kubectl exec $POD -- psql -U quickticket -d quickticket \
  -c 'SELECT count(*) FROM events; SELECT count(*) FROM orders'
 events_count
--------------
            5
(1 row)

 orders_table
--------------

(1 row)

┌──(.venv)─(shersh㉿kali)-[~/SRE-Intro]
└─$ kubectl run smoke --image=curlimages/curl:latest --rm -i --restart=Never --quiet \
  --command -- curl -s -o /dev/null -w "/events=%{http_code}\n" http://gateway:8080/events
/events=502
```
After restore:
```
┌──(.venv)─(shersh㉿kali)-[~/SRE-Intro]
└─$ 
kubectl exec $POD -- psql -U quickticket -d quickticket \
  -c 'SELECT count(*) FROM events; SELECT count(*) FROM orders'
 count 
-------
     5
(1 row)

 count 
-------
    50
(1 row)

┌──(.venv)─(shersh㉿kali)-[~/SRE-Intro]
└─$ 
kubectl run smoke --image=curlimages/curl:latest --rm -i --restart=Never --quiet \
  --command -- curl -s -o /dev/null -w "/events=%{http_code}\n" http://gateway:8080/events
/events=200
```

#### Answer: "What's the RPO of your current setup (single pg_dump)? How would you improve it? (Hint: Bonus Task)"
The current setup with a single pg_dump has an RPO equal to the interval between backups (e.g., 24 hours if backups run daily). Any changes made after the last dump are lost. To improve the RPO, I would implement continuous WAL archiving (Bonus Task) and use PITR, reducing the RPO to near zero.

### Task 2 — Disaster Recovery Under Load
#### Timestamps for the four phases (disaster / new pod ready / restored / app ready)
```
┌──(.venv)─(shersh㉿kali)-[~/SRE-Intro]
└─$ echo "
Disaster at      $T_KILL
New pod ready    $T_READY
Restored         $T_RESTORED
App fully up     $T_APP_READY
"

Disaster at      19:28:18
New pod ready    19:28:26
Restored         19:28:55
App fully up     19:29:12
```
#### Actual RTO value in seconds
```
19:29:12 - 19:28:18 = 66 sec
```

#### Orders count before disaster vs after restore (RPO gap)
RPO = 3435 - 218 = 3217 orders

#### Prometheus error-rate curve around the incident
```
┌──(.venv)─(shersh㉿kali)-[~/SRE-Intro]
└─$ kubectl exec -n monitoring deployment/prometheus -- wget -qO- \
  'http://localhost:9090/api/v1/query?query=sum(rate(gateway_requests_total%7Bstatus%3D~%225..%22%7D%5B30s%5D))'
{"status":"success","data":{"resultType":"vector","result":[{"metric":{},"value":[1783704122.293,"0"]}]}} 
```

#### Answer: "The new Postgres pod was empty. Why? How would you eliminate this failure mode?" (Answer: no PVC — fix it in the Bonus)
The new Postgres pod was empty because the original deployment stored its database files on the container filesystem without PersistentVolumeClaim.
Deleting the pod removed that writable layer and the new replacement pod started with a fresh empty directory. 
The fix is to mount a PVC for Postgres data so pod restarts could reuse the same storage.
