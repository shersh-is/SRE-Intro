# Lab 6 — Alerting & Incident Response
## Proof of work by Viktoriya Yurina B24-CBS-01
### Task 1 — Create Alerts & Respond to an Incident
#### Your alert rule PromQL queries (both rules)
```
sum(rate(gateway_requests_total{status=~"5.."}[5m])) / sum(rate(gateway_requests_total[5m])) * 100
(1 - (sum(rate(gateway_requests_total{status!~"5.."}[30m])) / sum(rate(gateway_requests_total[30m])))) / (1 - 0.995)
```
#### Contact point type and evidence of notification received (webhook URL output or screenshot)
Contact-point type: Grafana-managed \
Evidence of notification received: \

#### Your runbook (full text)
# Runbook: QuickTicket High Error Rate
## Alert

**Alert Name:** High Error Rate

**Trigger Condition:** Gateway 5xx error rate > 5% for 2 consecutive minutes.

**Impact:** Users may be unable to browse events or complete ticket purchases.

**Severity:** Warning

---

## Dashboards

Review the following dashboards:

* Grafana → QuickTicket Golden Signals
* Grafana → Service Health Dashboard
* Prometheus Alerts

Key metrics:

* Error Rate
* Request Rate
* Response Latency
* Service Availability

---

## Diagnose

### 1. Check gateway health

```bash
curl -s http://localhost:3000/health | python3 -m json.tool
```

### 2. Check payments service

```bash
curl -s http://localhost:8082/health
```

### 3. Check events service

```bash
curl -s http://localhost:8081/health
```

### 4. Check container status

```bash
docker-compose ps
```

Look for unhealthy or restarting containers.

### 5. Check logs

Gateway:

```bash
docker-compose logs gateway --tail=50
```

Payments:

```bash
docker-compose logs payments --tail=50
```

Events:

```bash
docker-compose logs events --tail=50
```

Look for:

* HTTP 5xx errors
* Connection refused messages
* Database errors
* Timeout errors
* Payment processing failures

---

## Common Causes

| Cause                       | How to Identify                     | Resolution                           |
| --------------------------- | ----------------------------------- | ------------------------------------ |
| Payments service down       | Health endpoint unavailable         | Restart payments service             |
| Events service unavailable  | Gateway logs show connection errors | Restart events service               |
| Database connectivity issue | Database errors in logs             | Verify database connectivity         |
| High payment failure rate   | Payment errors increase             | Adjust payment failure configuration |
| Faulty deployment           | Errors started after deployment     | Roll back deployment                 |

---

## Mitigation

### Restart failing service

Payments:

```bash
docker-compose restart payments
```

Events:

```bash
docker-compose restart events
```

Gateway:

```bash
docker-compose restart gateway
```

### Roll back deployment

If the issue started after a recent deployment:

```bash
git revert <commit>
git push
```

Wait for CI/CD and deployment synchronization.

### Verify recovery

```bash
docker-compose ps
```

Confirm that:

* All services are healthy.
* Error rate drops below 5%.
* Dashboard metrics return to normal.

---

## Escalation

Escalate if:

* The issue remains unresolved after 15 minutes.
* Multiple services are affected.
* Database corruption is suspected.
* User impact continues.

Notify:

* Instructor
* Teaching Assistant

Include:

* Alert screenshots
* Relevant logs
* Timeline of actions taken

---

## Related Information

Recent deployment history:

```bash
git log --oneline -5
```

Related services:

* Gateway
* Events
* Payments
* PostgreSQL
* Prometheus
* Grafana

#### Alert firing evidence: Grafana alert rule status showing "Firing"


#### Timeline: when you injected → when alert fired → when you diagnosed → when you fixed → when alert resolved
| Event                          | Time     |
| ------------------------------ | -------- |
| Failure injected               | 13:25    |
| Alert entered Pending state    | 13:26    |
| Alert fired                    | 13:28    |
| Alert received in Webhook.site | 13:28:51 |
| Diagnosed root cause           | 13:31    |
| Fix applied                    | 13:33    |
| Alert resolved                 | 13:35    |


#### Answer: "How long from failure injection to alert firing? Why the delay?"
It took approximately 3 minutes from failure injection to alert firing. \

The failure was injected at approximately 13:25 and the alert fired at approximately 13:28, resulting in a delay of about 3 minutes. This delay is caused by the alert evaluation window and the alert rule configuration (for: 2m), which requires the condition to remain true continuously before transitioning to the firing state. Additional seconds may be introduced by Prometheus scrape intervals and Grafana evaluation intervals.

### Task 2 — Blameless Postmortem
#### Full postmortem document
# Postmortem: QuickTicket High Error Rate

**Date:** 23/06/2026
**Duration:** 13:25-13:35
**Severity:** SEV-2
**Author:** Viktoriya Yurina

## Summary

A simulated incident was introduced by increasing the payments service failure rate to 50%. This caused a significant increase in failed payment requests and elevated the gateway error rate above the alert threshold. The issue was detected by Grafana alerts, investigated, and resolved by restoring normal service behavior.

## Timeline

| Time  | Event                                                      |
| ----- | ---------------------------------------------------------- |
| 13:25 | Failure injected by increasing payment failure rate to 50% |
| 13:26 | First failed payment requests observed                     |
| 13:28 | High Error Rate alert entered firing state                 |
| 13:29 | Investigation started                                      |
| 13:31 | Root cause identified in payments service configuration    |
| 13:33 | Fix applied and payments service restarted                 |
| 13:35 | Alert resolved and service recovered                       |

## Root Cause

The payments service failure rate was intentionally increased to 50%, causing a large percentage of payment requests to fail. These failures propagated to the gateway, which returned 5xx responses to users. The elevated error rate exceeded the configured alert threshold and consumed part of the service error budget.

## What Went Well

* Alert fired within approximately 3 minutes of failure injection.
* Grafana notification was successfully delivered through the configured webhook.
* The runbook provided clear investigation and mitigation steps.
* Root cause was identified quickly using service health checks and logs.

## What Went Wrong

* The alert notification did not immediately indicate which downstream service was responsible.
* Investigation required checking multiple services before isolating the payments service.
* The runbook did not explicitly mention validating the PAYMENT_FAILURE_RATE configuration.

## Action Items

| Action                                                          | Owner  | Priority |
| --------------------------------------------------------------- | ------ | -------- |
| Add a dedicated alert for abnormal payment failure rate         | shersh | High     |
| Add payment success rate panel to Grafana dashboard             | shersh | High     |
| Update runbook with PAYMENT_FAILURE_RATE validation step        | shersh | Medium   |
| Add deployment annotations to dashboards for easier correlation | shersh | Medium   |
| Create a payment transaction health check                       | shersh | Low      |

## Lessons Learned

The monitoring and alerting pipeline successfully detected the failure and guided the recovery process. While the incident was intentionally injected, it demonstrated that alerts, dashboards, webhooks, and runbooks work together effectively to reduce detection and recovery time.

#### Answer: "What is the most important action item from your postmortem? Why?"
The most important action item is to add a dedicated alert for abnormal payment failure rates.

During the incident, the first alert indicated an elevated gateway error rate, but it did not immediately identify the payments service as the source of the problem. A dedicated payment failure alert would provide earlier and more precise detection, reducing investigation time and helping engineers identify the root cause faster. This would improve both mean time to detect (MTTD) and mean time to resolve (MTTR).
