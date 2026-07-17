# Lab 10 — SRE Portfolio & Reliability Review
## Proof of work by Viktoriya Yurina
### Task 1 — Load Testing & Reliability Review

# QuickTicket Reliability Review

## 1. SLO Compliance

| SLO | Target | Observed | Status |
|------|--------|----------|--------|
| Availability (non-5xx) | ≥ 99.5% | 100% at 10 users; 76.42% at 50 users; 62.61% at 100 users | ✅ at 10 users / ❌ above 50 users |
| Latency (requests < 500 ms) | ≥ 95% | p95 17 ms at 10 users; p95 1200 ms at 50 users; p95 2700 ms at 100 users | ✅ at 10 users / ❌ above 50 users |
| Migration safety | 0 downtime | Database migrations completed without downtime | ✅ |
| DB recovery (RTO) | < 5 min | PostgreSQL pod recovered successfully using PVC in ~20 seconds | ✅ |

## 2. Load Test Results

| Users | Ramp | RPS | p50 | p95 | p99 | 5xx error rate | 409 (inventory) |
|------:|-----:|----:|----:|----:|----:|---------------:|----------------:|
| 10 | 2/s | 7.68 | 12 ms | 17 ms | 36 ms | 0.00% | 0 |
| 50 | 5/s | 23.93 | 400 ms | 1200 ms | 1600 ms | 23.58% | 0 |
| 100 | 10/s | 27.82 | 420 ms | 2700 ms | 4400 ms | 37.39% | 0 |

Breaking point: approximately 50 users (~24 RPS), where both the latency and availability SLOs were exceeded.

## 3. DORA Metrics

| Metric | Value | Source | DORA Tier |
|--------|-------|--------|-----------|
| Deployment Frequency | 6 rollout revisions during the project (~1/week) | `kubectl get rs`, Git history (63 commits) | Medium |
| Lead Time for Changes | ~10 minutes | CI build + ArgoCD synchronization | Elite (<1 day) |
| Change Failure Rate | N/A (no AnalysisRun history available) | `kubectl get analysisrun` | Not measured |
| MTTR | ~3–5 minutes | Git revert + ArgoCD synchronization | Elite (<1 hour) |

## 4. Top 3 Reliability Risks

1. Gateway overload under high traffic.
   - At 50 users the gateway starts returning 5xx responses and response time increases significantly.
   - Fix: increase CPU limits and configure Horizontal Pod Autoscaler.

2. Single PostgreSQL instance.
   - The database remains a single point of failure despite persistent storage.
   - Fix: deploy a PostgreSQL replica or HA solution.

3. Single replica of the Events service.
   - Most requests are handled by this service, making it the primary bottleneck.
   - Fix: increase the number of replicas and add a PodDisruptionBudget.

---

## 5. Toil Identification

| Toil | Frequency | Automation | Benefit |
|------|-----------|------------|---------|
| Recreating `kubectl port-forward` after pod restarts | Many times | Use Ingress or NodePort | Saves ~30 seconds every session |
| Manually monitoring Argo Rollouts | Every deployment | Configure automatic notifications | Saves 5–10 minutes per deployment |
| Running Prometheus queries manually | Every load test | Build Grafana dashboards | Faster troubleshooting and monitoring |

## 6. Monitoring Gaps

- No latency-based SLO alert. Only 5xx responses were monitored.
- No alert for pod restarts caused by failed liveness probes.
- No CPU saturation or database connection pool monitoring.
- No fast-burn alert for sudden increases in 5xx responses.
- A latency alert and pod restart alert would have detected the gateway failures much earlier during the load tests.

## 7. Capacity Plan

Current ceiling: approximately 24 RPS before SLO violations.

To support roughly 2× traffic (~45–50 RPS):

| Service | Current | Proposed |
|---------|---------|----------|
| gateway | 5 replicas | HPA 5–10 replicas |
| events | 1 replica | 3 replicas |
| payments | 1 replica | 2 replicas |
| redis | 1 replica | Keep a single instance |
| postgres | 1 instance | Increase CPU and memory, consider adding a replica |

### Resource limits

| Service | CPU Request | CPU Limit |
|---------|------------:|----------:|
| gateway | 100m | 500m |
| events | 250m | 1000m |
| payments | 100m | 300m |
| postgres | 250m | 1000m |

Estimated monthly cost:

- Current deployment: approximately 9 pods (~$45/month).
- 2× capacity: 12–13 pods (~$60/month).

### Task 2 — Capacity Plan with Numbers
#### Per-pod CPU at breaking point

| Service | Replicas | CPU | Memory | Observation |
|---------|---------:|----:|-------:|-------------|
| gateway | 5 | 6–7m | 39 Mi | Low CPU utilization |
| events | 1 | 8m | 43 Mi | Highest CPU usage, but still low |
| payments | 1 | 7m | 36 Mi | Low utilization |

The CPU metrics indicate that none of the services are CPU-bound. Even at the breaking point (~24 RPS), CPU utilization remained below 10m per pod. This suggests that the bottleneck is likely caused by request handling, gateway configuration, database access, or probe timeouts rather than lack of compute resources.

#### Detailed capacity plan with replica counts, resource limits, cost

| Service | Current | Proposed for 2× traffic |
|---------|---------|-------------------------|
| gateway | 5 replicas | HPA with 5–8 replicas |
| events | 1 replica | 2 replicas |
| payments | 1 replica | 1 replica |
| redis | 1 replica | Keep a single instance |
| postgres | 1 instance | Increase resources, add replica only if higher availability is required |

### Resource requests / limits

| Service | CPU Request | CPU Limit | Memory |
|---------|------------:|----------:|-------:|
| gateway | 100m | 500m | 128Mi |
| events | 100m | 500m | 256Mi |
| payments | 50m | 200m | 128Mi |
| redis | 50m | 200m | 128Mi |
| postgres | 250m | 1000m | 512Mi |

### Database

The current single PostgreSQL instance is sufficient for approximately 2× traffic, but it remains a single point of failure. For production environments, a replica should be added for high availability.

### Redis

Redis remains lightly utilized, so a single instance is sufficient for the expected traffic increase.

### Estimated cost

Current deployment:
- 9 pods (~$45/month)

2× traffic:
- 10–11 pods (~$50–55/month)

Most of the additional cost comes from running an extra Events replica and allowing the Gateway to scale automatically using HPA.
