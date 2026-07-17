# Lab 11 — Bonus: Advanced Microservice Patterns
## Proof of work by Viktoriya Yurina
### Task 1 — Notifications Service + Retries
#### app/notifications/main.py (the key bits) and requirements.txt
Key bits of app/notifications/main.py
```
# --- Prometheus metrics ---
REQUEST_COUNT = Counter(
    "notifications_requests_total",
    "Total requests",
    ["method", "path", "status"],
)

REQUEST_DURATION = Histogram(
    "notifications_request_duration_seconds",
    "Request duration",
    ["method", "path"],
)

NOTIFY_TOTAL = Counter(
    "notifications_notify_total",
    "Total notification attempts",
    ["result"],
)


@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    start = time.time()

    response = await call_next(request)

    duration = time.time() - start
    path = request.url.path

    if not path.startswith("/metrics"):
        REQUEST_COUNT.labels(
            request.method,
            path,
            response.status_code,
        ).inc()

        REQUEST_DURATION.labels(
            request.method,
            path,
        ).observe(duration)

    return response


@app.post("/notify")
def notify(payload: dict):
    # Simulate latency
    if NOTIFY_LATENCY_MS > 0:
        time.sleep(NOTIFY_LATENCY_MS / 1000)

    event = payload.get("event")
    order_id = payload.get("order_id")

    if not event or not order_id:
        raise HTTPException(
            status_code=400,
            detail="event and order_id are required",
        )

    # Simulate failure
    if random.random() < NOTIFY_FAILURE_RATE:
        NOTIFY_TOTAL.labels(result="failed").inc()

        log.error(
            f'Notification failed: event="{event}", order_id="{order_id}"'
        )

        raise HTTPException(
            status_code=500,
            detail="Notification service failure",
        )

    notification_id = str(uuid.uuid4())

    NOTIFY_TOTAL.labels(result="success").inc()

    log.info(
        f'Notification sent: id="{notification_id}", event="{event}", order_id="{order_id}"'
    )

    return {
        "status": "sent",
        "notification_id": notification_id,
        "event": event,
        "order_id": order_id,
    }


@app.get("/health")
def health():
    return {
        "status": "healthy",
        "failure_rate": NOTIFY_FAILURE_RATE,
        "latency_ms": NOTIFY_LATENCY_MS,
    }


@app.get("/metrics")
def metrics():
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )
```

#### k8s/notifications.yml
```
apiVersion: apps/v1
kind: Deployment
metadata:
  name: notifications
spec:
  replicas: 1
  selector:
    matchLabels:
      app: notifications
  template:
    metadata:
      labels:
        app: notifications
    spec:
      containers:
        - name: notifications
          image: quickticket-notifications:v1
          imagePullPolicy: Never
          ports:
            - containerPort: 8083
          env:
            - name: NOTIFY_FAILURE_RATE
              value: "0.0"
            - name: NOTIFY_LATENCY_MS
              value: "0"

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
              port: 8083
            initialDelaySeconds: 10
            periodSeconds: 10
            failureThreshold: 3

          readinessProbe:
            httpGet:
              path: /health
              port: 8083
            periodSeconds: 5
            failureThreshold: 2

---
apiVersion: v1
kind: Service
metadata:
  name: notifications
spec:
  selector:
    app: notifications
  ports:
    - port: 8083
      targetPort: 8083
  type: ClusterIP
```

#### call_with_retry() implementation
```
async def call_with_retry(func, target: str, max_retries: int = RETRY_MAX):
    last_exception = None
    base_delay = RETRY_BASE_DELAY_MS / 1000.0

    for attempt in range(max_retries):
        try:
            result = await func()

            if attempt > 0:
                RETRY_TOTAL.labels(
                    target=target,
                    result="succeeded_after_retry",
                ).inc()

            return result

        except Exception as exc:
            last_exception = exc

            retryable = False

            if isinstance(exc, (httpx.TimeoutException, httpx.ConnectError)):
                retryable = True

            elif isinstance(exc, httpx.HTTPStatusError):
                status = exc.response.status_code

                if status >= 500 or status in (408, 429):
                    retryable = True
                elif 400 <= status < 500:
                    RETRY_TOTAL.labels(
                        target=target,
                        result="non_retryable",
                    ).inc()
                    raise

            if attempt == max_retries - 1:
                RETRY_TOTAL.labels(
                    target=target,
                    result="exhausted",
                ).inc()
                raise last_exception

            RETRY_TOTAL.labels(
                target=target,
                result="retried",
            ).inc()

            delay = base_delay * (2 ** attempt) + random.uniform(0, base_delay)
            await asyncio.sleep(delay)

    raise last_exception
```

#### Test #1 — ok=30 fail=0 result + /pay p99 < 100ms during the notify-failure injection (proves fire-and-forget)
```
┌──(shersh㉿kali)-[~/SRE-Intro]
└─$ kubectl run checkout-burst \                                                                                  
  --image=curlimages/curl:latest \
  --image-pull-policy=IfNotPresent \
  --rm -i --restart=Never --quiet \
  --command -- sh -c 'ok=0; fail=0
for i in $(seq 1 30); do
  RES=$(curl -s -X POST http://gateway:8080/events/3/reserve -H "Content-Type: application/json" -d "{\"quantity\":1}")
  RID=$(echo "$RES" | sed -n "s/.*reservation_id\":\"\\([^\"]*\\).*/\\1/p")
  if [ -z "$RID" ]; then echo "[$i] reserve failed"; fail=$((fail+1)); continue; fi
  CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST http://gateway:8080/reserve/$RID/pay)
  if [ "$CODE" = "200" ]; then ok=$((ok+1)); else echo "[$i] pay failed: $CODE"; fail=$((fail+1)); fi
  sleep 0.1
done
echo "result: ok=$ok fail=$fail"
'
result: ok=30 fail=0
```

```
┌──(shersh㉿kali)-[~/SRE-Intro]
└─$ kubectl exec -n monitoring deployment/prometheus -- wget -qO- \
  'http://localhost:9090/api/v1/query?query=histogram_quantile(0.99,+sum+by+(le,path)+(rate(gateway_request_duration_seconds_bucket%5B2m%5D)))'
{"status":"success","data":{"resultType":"vector","result":[{"metric":{"path":"/health"},"value":[1784284745.104,"0.09099999999999986"]},{"metric":{"path":"/events"},"value":[1784284745.104,"0.021627999999999967"]},{"metric":{"path":"/events/{id}/reserve"},"value":[1784284745.104,"0.03768749999999979"]},{"metric":{"path":"/reserve/{id}/pay"},"value":[1784284745.104,"0.09624999999999999"]}]}}
```
#### Test #2 — ok≈30 fail<2 result + gateway_retry_total{result="retried"} and result="succeeded_after_retry" both non-zero (proves retries actually fire)
```
┌──(shersh㉿kali)-[~/SRE-Intro]
└─$ kubectl run retry-test --image=curlimages/curl:latest --rm -i --restart=Never --quiet --command -- sh -c '
ok=0; fail=0
for i in $(seq 1 30); do
  RES=$(curl -s -X POST http://gateway:8080/events/3/reserve -H "Content-Type: application/json" -d "{\"quantity\":1}")
  RID=$(echo "$RES" | sed -n "s/.*reservation_id\":\"\\([^\"]*\\).*/\\1/p")
  [ -z "$RID" ] && { fail=$((fail+1)); continue; }
  CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST http://gateway:8080/reserve/$RID/pay)
  [ "$CODE" = "200" ] && ok=$((ok+1)) || fail=$((fail+1))
  sleep 0.1
done
echo "result: ok=$ok fail=$fail"
'
result: ok=29 fail=1

┌──(shersh㉿kali)-[~/SRE-Intro]
└─$ kubectl exec -n monitoring deployment/prometheus -- wget -qO- \
  'http://localhost:9090/api/v1/query?query=sum+by+(target,result)+(gateway_retry_total)'
{

  "status": "success",
  "data": {"resultType": "vector", "result": [
    {"metric": {"result": "retried", "target": "payments"}, "value": [..., "4"]},
    {"metric": {"result": "succeeded_after_retry", "target": "payments"}, "value": [..., "4"]}
  ]}
}
```

#### Real notify failure rate from the notifications pod's /metrics (notifications_notify_total{result})
```
┌──(shersh㉿kali)-[~/SRE-Intro]
└─$ kubectl exec -i $(kubectl get pod -l app=notifications -o name) -- python3 -c "
import urllib.request
print(urllib.request.urlopen('http://localhost:8083/metrics').read().decode())
" | grep notifications_notify_total
# HELP notifications_notify_total Total notification attempts
# TYPE notifications_notify_total counter
notifications_notify_total{result="success"} 76.0
```

#### Answer: "Why should notifications be non-blocking (fire-and-forget)?"
Notifications should be non-blocking (fire-and-forget) because sending emails or messages is not part of the critical request path. The user should receive a successful response as soon as the reservation or payment is completed, without waiting for the notification service. This reduces latency, improves throughput, and ensures that temporary notification failures do not cause reservation or payment requests to fail. Notifications can be processed asynchronously or retried later if necessary.

#### Answer (Design Prompt from 11.4): "Why is cb.call(retry(...)) the correct composition for Task 2, not retry(lambda: cb.call(...))?"
cb.call(retry(...)) is the correct composition because the circuit breaker should observe the final outcome of the entire retry operation, not each individual attempt. The retry logic handles transient failures internally and only returns a failure if all retry attempts are exhausted. This prevents the circuit breaker from counting every temporary failure as a separate failure and opening unnecessarily.

If we use retry(lambda: cb.call(...)), each retry passes through the circuit breaker independently. Every failed attempt increments the circuit breaker's failure count, making it much more likely to open even when a later retry would have succeeded. This defeats the purpose of retries and reduces system resilience.


### Task 2 — Circuit Breaker + Rate Limiter
#### Your CircuitBreaker and RateLimiter class code
CircuitBreaker:
```
class CircuitBreaker:
    """Stateful circuit breaker. Lab 11 task 11.7.

    No-op default: state is always CLOSED, .call just calls func. Replace the
    body of .call with a real CLOSED → OPEN → HALF_OPEN state machine that
    fast-fails with CircuitOpenError once `failures >= threshold`, recovers
    after `cooldown_s`, and emits `gateway_circuit_breaker_transitions_total`.
    """

    OPEN = "OPEN"
    CLOSED = "CLOSED"
    HALF_OPEN = "HALF_OPEN"

    def __init__(self, threshold: int, cooldown_s: float, name: str = "cb"):
        self.threshold = threshold
        self.cooldown = cooldown_s
        self.name = name
        self.failures = 0
        self.state = self.CLOSED
        self.opened_at = 0.0

    def _transition(self, new_state: str):
        """Record a state change. Use this from your .call implementation
        so transitions show up in Prometheus."""
        if self.state != new_state:
            log.warning(f"circuit[{self.name}] {self.state} -> {new_state}")
            CB_STATE_TRANSITIONS.labels(new_state).inc()
        self.state = new_state

    async def call(self, func):
        """Run func with circuit-breaker protection.
	No-op default: just calls func. Lab 11 task 11.7 replaces this with
        the state machine. Raise `CircuitOpenError` when the circuit is open.
        """

        # Fast-fail if the circuit is OPEN
        if self.state == "OPEN":
                if time.time() - self.opened_at >= self.cooldown:
                self._transition("HALF_OPEN")
                else:
                raise CircuitOpenError(f"circuit[{self.name}] OPEN")

        try:
                result = await func()

                # Success: close the circuit and reset failures
                self.failures = 0
                self._transition("CLOSED")
                return result

        except Exception:
                self.failures += 1
                self.opened_at = time.time()

                # Open immediately if HALF_OPEN fails,
                # or if failure threshold is reached in CLOSED
                if self.state == "HALF_OPEN" or self.failures >= self.threshold:
                self._transition("OPEN")

                raise

        return await func()

```

RateLimiter:
```
class RateLimiter:
    """Per-key sliding-window rate limiter. Lab 11 task 11.8.

    No-op default: .allow always returns True. Replace it with a sliding
    1-second window that tracks request timestamps per key and rejects
    once `len(window) >= self.rps`.
    """

    def __init__(self, rps: int):
        self.rps = rps
        self.window_s = 1.0
        self.hits: dict[str, deque] = defaultdict(deque)

    def allow(self, key: str) -> bool:
        """Return True if the request should be allowed.

        No-op default: always True. Lab 11 task 11.8 replaces this body.
        """
        now = time.time()
        q = self.hits[key]
        cutoff = now - self.window_s

        # Remove timestamps outside the sliding window
        while q and q[0] < cutoff:
                q.popleft()

        # Reject if the request rate exceeds the limit
        if len(q) >= self.rps:
                return False

        # Record the current request
        q.append(now)
        return True
```

#### 500s/503s breakdown from the CB test under 100% payment failure
```
┌──(shersh㉿kali)-[~/SRE-Intro]
└─$ kubectl run cb-probe --image=curlimages/curl:latest --rm -i --restart=Never --quiet --command -- sh -c '
STATS_500=0; STATS_503=0
for i in $(seq 1 80); do
  RES=$(curl -s -X POST http://gateway:8080/events/3/reserve -H "Content-Type: application/json" -d "{\"quantity\":1}")
  RID=$(echo "$RES" | sed -n "s/.*reservation_id\":\"\\([^\"]*\\).*/\\1/p")
  [ -z "$RID" ] && continue
  CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST http://gateway:8080/reserve/$RID/pay)
  case "$CODE" in
    500) STATS_500=$((STATS_500+1));;
    503) STATS_503=$((STATS_503+1));;
  esac
done
echo "500s=$STATS_500 503s=$STATS_503"
'
500s=22 503s=56
```

#### 200s after recovery showing the circuit closed
```
┌──(shersh㉿kali)-[~/SRE-Intro]
└─$ kubectl run cb-probe2 --image=curlimages/curl:latest --rm -i --restart=Never --quiet --command -- sh -c '
for i in $(seq 1 15); do
  RES=$(curl -s -X POST http://gateway:8080/events/3/reserve -H "Content-Type: application/json" -d "{\"quantity\":1}")
  RID=$(echo "$RES" | sed -n "s/.*reservation_id\":\"\\([^\"]*\\).*/\\1/p")
  [ -z "$RID" ] && continue
  CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST http://gateway:8080/reserve/$RID/pay)
  echo "[$i] $CODE"
done
'
[1] 200
[2] 200
[3] 200
[4] 200
[5] 200
[6] 200
[7] 200
[8] 200
[9] 200
[10] 200
[11] 200
[12] 200
[13] 200
[14] 200
[15] 200
```

#### 200/429 split from the rate-limit burst test
```
┌──(shersh㉿kali)-[~/SRE-Intro]
└─$ kubectl run rl-burst --image=curlimages/curl:latest --rm -i --restart=Never --quiet --command -- sh -c '
OK=0; LIMITED=0
for i in $(seq 1 100); do
  CODE=$(curl -s -o /dev/null -w "%{http_code}" http://gateway:8080/events)
  case "$CODE" in
    200) OK=$((OK+1));;
    429) LIMITED=$((LIMITED+1));;
  esac
done
echo "200=$OK 429=$LIMITED"
'
200=45 429=55
```

#### The Retry-After: 1 header observed on a 429 response
```
┌──(shersh㉿kali)-[~/SRE-Intro]
└─$ kubectl run rl-headers --image=curlimages/curl:latest --rm -i --restart=Never --quiet --command -- sh -c '
# warm up the limiter with rapid hits
for i in $(seq 1 50); do curl -s -o /dev/null http://gateway:8080/events; done
# next request should 429 — capture headers
curl -s -D - -o /dev/null http://gateway:8080/events | grep -iE "^(HTTP|retry-after)"
'
HTTP/1.1 429 Too Many Requests
retry-after: 1
```

#### gateway_circuit_breaker_transitions_total{to} and gateway_rate_limit_rejections_total{path} from Prometheus
```
┌──(shersh㉿kali)-[~/SRE-Intro]
└─$ kubectl exec -n monitoring deployment/prometheus -- wget -qO- \
  'http://localhost:9090/api/v1/query?query=sum+by+(path)+(gateway_rate_limit_rejections_total)'
{
  "status": "success",
  "data": {"resultType": "vector", "result": [
    {"metric": {"path": "/reserve/{id}/pay"}, "value": [..., "2"]},
    {"metric": {"path": "/events"}, "value": [..., "68"]}
  ]}
}
```
