# Lab 12 — Bonus: Advanced Kubernetes Resilience
## Proof of work by Viktoriya Yurina
### Task 1 — Multi-Replica Failover + PDBs
#### kubectl get deploy,rollout showing all services at their target replica counts
```
┌──(shersh㉿kali)-[~/SRE-Intro]
└─$ kubectl get deployments --show-labels              
NAME            READY   UP-TO-DATE   AVAILABLE   AGE   LABELS
events          2/2     2            2           31d   <none>
mixedload       2/2     2            2           10h   <none>
notifications   2/2     2            2           11h   <none>
payments        2/2     2            2           31d   <none>
postgres        1/1     1            1           31d   <none>
redis           1/1     1            1           31d   <none>
```

#### The before/after 5xx count from Prometheus around the pod-kill test (should both be 0)
Before:
```
┌──(shersh㉿kali)-[~/SRE-Intro]
└─$ # before
kubectl exec -n monitoring deployment/prometheus -- wget -qO- \
  'http://localhost:9090/api/v1/query?query=sum(increase(gateway_requests_total%7Bstatus%3D~%225..%22%7D%5B3m%5D))'

{"status":"success","data":{"resultType":"vector","result":[{"metric":{},"value":[1784303270.273,"4.180693702754518"]}]}}
```

#### kubectl get pdb output
```
┌──(shersh㉿kali)-[~/SRE-Intro]
└─$ kubectl get pdb                      
NAME                MIN AVAILABLE   MAX UNAVAILABLE   ALLOWED DISRUPTIONS   AGE
events-pdb          1               N/A               1                     19m
gateway-pdb         2               N/A               3                     19m
notifications-pdb   N/A             1                 1                     19m
payments-pdb        1               N/A               1                     19m
```

#### kubectl get rollout gateway -o jsonpath='{.spec.template.spec.topologySpreadConstraints}' output showing the constraint is in the live spec, plus kubectl get pod -l app=gateway -o wide showing the actual placement
```
┌──(shersh㉿kali)-[~/SRE-Intro]
└─$ kubectl get rollout gateway -o jsonpath='{.spec.template.spec.topologySpreadConstraints}'
[{"labelSelector":{"matchLabels":{"app":"gateway"}},"maxSkew":1,"topologyKey":"kubernetes.io/hostname","whenUnsatisfiable":"ScheduleAnyway"}]     

┌──(shersh㉿kali)-[~/SRE-Intro]
└─$ kubectl get pod -l app=gateway -o wide
NAME                      READY   STATUS    RESTARTS   AGE     IP            NODE                       NOMINATED NODE   READINESS GATES
gateway-ccd78d88c-f2wf9   1/1     Running   0          4m25s   10.42.0.220   k3d-quickticket-server-0   <none>           <none>
gateway-ccd78d88c-f6gzt   1/1     Running   0          16m     10.42.0.219   k3d-quickticket-server-0   <none>           <none>
gateway-ccd78d88c-pj2vc   1/1     Running   0          3m14s   10.42.0.221   k3d-quickticket-server-0   <none>           <none>
gateway-ccd78d88c-qqm9n   1/1     Running   0          18m     10.42.0.218   k3d-quickticket-server-0   <none>           <none>
gateway-ccd78d88c-vjmls   1/1     Running   0          2m33s   10.42.0.222   k3d-quickticket-server-0   <none>           <none>
```

#### The HTTP 429 JSON body from the tightened-PDB eviction test (proves PDB enforcement)
```
┌──(shersh㉿kali)-[~/SRE-Intro]
└─$ POD=$(kubectl get pod -l app=events -o jsonpath='{.items[0].metadata.name}')
                                                                                                                                              
┌──(shersh㉿kali)-[~/SRE-Intro]
└─$ echo $POD       
events-ffdf69bc8-b5vkc
                                                                                                                                              
┌──(shersh㉿kali)-[~/SRE-Intro]
└─$ curl -s -X POST -H 'Content-Type: application/json' \                       
  -d "{\"apiVersion\":\"policy/v1\",\"kind\":\"Eviction\",\"metadata\":{\"name\":\"$POD\",\"namespace\":\"default\"}}" \
  -w "\nHTTP_STATUS:%{http_code}\n" \
  http://127.0.0.1:18901/api/v1/namespaces/default/pods/$POD/eviction
{
  "kind": "Status",
  "apiVersion": "v1",
  "metadata": {},
  "status": "Failure",
  "message": "Cannot evict pod as it would violate the pod's disruption budget.",
  "reason": "TooManyRequests",
  "details": {
    "causes": [
      {
        "reason": "DisruptionBudget",
        "message": "The disruption budget events-pdb needs 2 healthy pods and has 2 currently"
      }
    ]
  },
  "code": 429
}
HTTP_STATUS:429
```

#### Answer: "With 3 gateway replicas and minAvailable: 1, what's the maximum number of pods that can be evicted simultaneously? Why is your gateway-pdb set to minAvailable: 2 with 5 replicas?
A PodDisruptionBudget with `minAvailable: 1` and a total of 3 replicas guarantees that at least one pod remains available during voluntary disruptions. This means Kubernetes can evict up to two pods at once, but any additional eviction request is rejected if it would leave no healthy replicas running.

For the `gateway` service, which has 5 replicas, the budget is set to `minAvailable: 2`. This configuration permits up to three concurrent evictions while still ensuring that two instances continue serving traffic. Setting the threshold to `minAvailable: 4` would be much more restrictive, allowing only one pod to be evicted at a time. As a result, maintenance operations such as draining a node would take longer because Kubernetes would have to wait for each replacement pod to become Ready before proceeding with the next eviction. Using `minAvailable: 2` provides a better balance between service availability and maintenance efficiency.

#### Answer: "Your topology-spread constraint has no observable effect on single-node k3d. In a 3-node cluster, what placement would maxSkew: 1 produce for 5 gateway pods? What about for 7?"
When `maxSkew` is set to `1`, Kubernetes tries to distribute replicas so that no node hosts more than one additional pod compared with any other node. As a result, 5 replicas spread across 3 nodes are arranged as `2/2/1`, while more uneven layouts such as `3/1/1` or `4/1/0` are not allowed because the difference between the most and least populated nodes exceeds one.

The same rule applies with 7 replicas. The valid placement is `3/2/2`, since the largest and smallest pod counts differ by only one. Although `3/3/1` also totals seven replicas, it violates the constraint because the busiest node has two more pods than the least populated one.

### Task 2 — Graceful Shutdown + Zero-Downtime Migration
#### The preStop / readinessProbe block as it appears in your k8s/gateway.yaml
```
lifecycle:
  preStop:
    exec:
      command: ["sh", "-c", "sleep 10"]

readinessProbe:
  httpGet:
    path: /health
    port: 8080
  periodSeconds: 2
  failureThreshold: 1

resources:
  requests:
    cpu: 50m
    memory: 64Mi
  limits:
    cpu: 200m
    memory: 256Mi

livenessProbe:
  httpGet:
    path: /health
    port: 8080
  initialDelaySeconds: 10
  periodSeconds: 10
  failureThreshold: 3
```

#### 5xx count before / after the rolling restart (both should be 0)
Before and after outputs are the same
```
┌──(shersh㉿kali)-[~/SRE-Intro]
└─$ kubectl exec -n monitoring deployment/prometheus -- wget -qO- \
  'http://localhost:9090/api/v1/query?query=sum(increase(gateway_requests_total%7Bstatus%3D~%225..%22%7D%5B3m%5D))'
{"status":"success","data":{"resultType":"vector","result":[{"metric":{},"value":[1784328986.491,"0"]}]}}
```

#### Your migration code (the autocommit_block wrapper is the key detail)
```
┌──(shersh㉿kali)-[~/SRE-Intro]
└─$ cat migrations/versions/4739477fc4d6_index_events_event_date_concurrently.py 
"""index events.event_date concurrently

Revision ID: 4739477fc4d6
Revises: b26c23c0fb15
Create Date: 2026-07-18 02:05:15.509536

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4739477fc4d6'
down_revision: Union[str, Sequence[str], None] = 'b26c23c0fb15'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.get_context().autocommit_block():
        op.create_index(
            "ix_events_event_date",
            "events",
            ["event_date"],
            unique=False,
            postgresql_concurrently=True,
            if_not_exists=True,
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.get_context().autocommit_block():
        op.drop_index(
            "ix_events_event_date",
            table_name="events",
            postgresql_concurrently=True,
            if_exists=True,
        )
```

#### 5xx count before / after the migration (both should be 0)
Before:
```
┌──(shersh㉿kali)-[~/SRE-Intro]
└─$ cat /tmp/5xx.before
{"status":"success","data":{"resultType":"vector","result":[{"metric":{},"value":[1784330330.268,"0"]}]}}
```
After:
```
┌──(shersh㉿kali)-[~/SRE-Intro]
└─$ cat /tmp/5xx.after                        
{"status":"success","data":{"resultType":"vector","result":[{"metric":{},"value":[1784329649.579,"0"]}]}}
```

#### \d events output showing the new idx_events_event_date index
```
┌──(.venv)─(shersh㉿kali)-[~/SRE-Intro]
└─$ kubectl exec -i $(kubectl get pod -l app=postgres -o name) -- \
  psql -U quickticket -d quickticket -c '\d events' | grep ix_events
    "ix_events_event_date" btree (event_date)
```

#### The 3-migration + 2-deploy expand-and-contract sketch from 12.8 (write it as a numbered list, no code required)
1. **Migration 1:** Add a new nullable column `scheduled_at` while keeping the existing `event_date` column. At this stage, both columns exist, so the current application continues to work without modification.

2. **Code Deploy A:** Update the application to write values to both `event_date` and `scheduled_at`. When reading, use `scheduled_at` if it contains a value; otherwise, fall back to `event_date`. This ensures compatibility with both old and new records.

3. **Migration 2:** Backfill existing data by copying values from `event_date` into `scheduled_at` for rows where `scheduled_at` is still `NULL`. This is safe because the application is already dual-writing, so new and updated rows remain synchronized during the migration.

4. **Code Deploy B:** Change the application to read exclusively from `scheduled_at` and write only to `scheduled_at`. The old column is no longer used by the application, but it remains available as a safety net until the deployment is fully rolled out.

5. **Migration 3:** Remove the obsolete `event_date` column. This step must only be performed after Deploy B has been successfully deployed everywhere, ensuring that no running application instance still depends on the old column.

#### (Optional, if you did 12.9) HPA YAML and a screenshot of kubectl get hpa showing CPU utilization climbing under load
k8s/gateway-hpa.yml
```
┌──(shersh㉿kali)-[~/SRE-Intro]
└─$ cat k8s/gateway-hpa.yml 
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: gateway
spec:
  scaleTargetRef:
    apiVersion: argoproj.io/v1alpha1
    kind: Rollout
    name: gateway
  minReplicas: 5
  maxReplicas: 12
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70

┌──(shersh㉿kali)-[~/SRE-Intro]
└─$ kubectl apply -f k8s/gateway-hpa.yml 
horizontalpodautoscaler.autoscaling/gateway created
                                                                                                                                                                    
┌──(shersh㉿kali)-[~/SRE-Intro]
└─$ kubectl get hpa gateway             
NAME      REFERENCE         TARGETS              MINPODS   MAXPODS   REPLICAS   AGE
gateway   Rollout/gateway   cpu: <unknown>/70%   5         12        0          0s

┌──(shersh㉿kali)-[~/SRE-Intro]
└─$ kubectl get hpa gateway             
NAME      REFERENCE         TARGETS        MINPODS   MAXPODS   REPLICAS   AGE
gateway   Rollout/gateway   cpu: 54%/70%   5         12        5          78s

┌──(shersh㉿kali)-[~/SRE-Intro]
└─$ kubectl get hpa gateway             
NAME      REFERENCE         TARGETS        MINPODS   MAXPODS   REPLICAS   AGE
gateway   Rollout/gateway   cpu: 86%/70%   5         12        12         108s
```
#### Answer: "Why does CREATE INDEX CONCURRENTLY matter? What happens if you omit it on a table with 10M rows?"
CREATE INDEX CONCURRENTLY allows PostgreSQL to build an index without taking an exclusive lock that blocks normal application activity. As a result, the table can continue handling reads and writes while the index is being created.

If CONCURRENTLY is omitted on a table with around 10 million rows, PostgreSQL acquires a lock that prevents writes for the duration of the index build. Since creating the index can take a significant amount of time on a large table, inserts, updates, and deletes may be blocked, causing slow requests, timeouts, or even temporary application downtime.

#### Answer (from 12.8): "In your expand-and-contract sketch, why MUST migration 3 (drop old column) come after deploy B has fully rolled out? What goes wrong if it runs before?"
Migration 3 must be performed only after Deploy B has been fully rolled out because every running instance of the application must have stopped using the old column. Until then, some instances may still read from or write to event_date.

If the old column is dropped too early, those older application instances will try to access a column that no longer exists. This will result in database errors, failed requests, and potentially application outages. Waiting until Deploy B is fully deployed ensures that all instances rely exclusively on scheduled_at, making it safe to remove the old column without disrupting service.
