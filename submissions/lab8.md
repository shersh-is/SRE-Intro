# Lab 8 — Chaos Engineering: Break Things on Purpose
## Proof of work by Viktoriya Yurina B24-CBS-01
### Task 1 Experiment 1 — Pod Kill Under Load
#### Hypothesis
If I delete one gateway pod while traffic is flowing,
the load would be redistributed among 4 pods
because the Kubernetes balances incoming requests across all healthy pods.

#### The command(s) I ran
```
┌──(shersh㉿kali)-[~/SRE-Intro]
└─$ VICTIM=$(kubectl get pods -l app=gateway -o name | head -1)
                                                                                                                                                                                 
┌──(shersh㉿kali)-[~/SRE-Intro]
└─$ echo "Killing $VICTIM at $(date +%H:%M:%S)"
Killing pod/gateway-6fd487bcf7-68f4s at 11:12:54
                                                                                                                                                                                 
┌──(shersh㉿kali)-[~/SRE-Intro]
└─$ kubectl delete "$VICTIM"
pod "gateway-6fd487bcf7-68f4s" deleted
                                                                                                                                                                                 
┌──(shersh㉿kali)-[~/SRE-Intro]
└─$ kubectl get pods -l app=gateway -w
NAME                       READY   STATUS    RESTARTS   AGE
gateway-6fd487bcf7-cqfrp   1/1     Running   0          12s
gateway-6fd487bcf7-gwg45   1/1     Running   0          18m
gateway-6fd487bcf7-jxj69   1/1     Running   0          17m
gateway-6fd487bcf7-pq6sh   1/1     Running   0          21m
gateway-6fd487bcf7-xxmns   1/1     Running   0          20m
^C
                                                                                                                                                                                 
┌──(shersh㉿kali)-[~/SRE-Intro]
└─$ kubectl exec -n monitoring deployment/prometheus -- wget -qO- \
  'http://localhost:9090/api/v1/query?query=sum(increase(gateway_requests_total%7Bstatus%3D~%225..%22%7D%5B3m%5D))'
{"status":"success","data":{"resultType":"vector","result":[{"metric":{},"value":[1782461621.400,"1041.009464973545"]}]}}
                                                                                                                                                                                 
┌──(shersh㉿kali)-[~/SRE-Intro]
└─$ kubectl exec -n monitoring deployment/prometheus -- wget -qO- \
  'http://localhost:9090/api/v1/query?query=sum+by+(pod)+(rate(gateway_requests_total%5B1m%5D))'
{"status":"success","data":{"resultType":"vector","result":[{"metric":{"pod":"gateway-6fd487bcf7-xxmns"},"value":[1782461638.400,"1.1454545454545455"]},{"metric":{"pod":"gateway-6fd487bcf7-gwg45"},"value":[1782461638.400,"1.3454545454545452"]},{"metric":{"pod":"gateway-6fd487bcf7-jxj69"},"value":[1782461638.400,"1.1636363636363636"]},{"metric":{"pod":"gateway-6fd487bcf7-pq6sh"},"value":[1782461638.400,"1.4545454545454546"]},{"metric":{"pod":"gateway-6fd487bcf7-cqfrp"},"value":[1782461638.400,"1.0353062499999999"]}]}}
```

#### What I observed
From the commands' output, I observed that after deleting a pod, kubectl created the new pod immediately, so the load were redistributed among 5 pods in a seconds (4 old and 1 new).
I deleted pod at 10:15, after a few seconds ran kubectl get pods ..., and new pod was already there. \
But still there was enough time to receive for around 1040 5xx responses from the service.
I re-ran this command after the experiment to see the "usual" number of 5xx responses:
```
┌──(shersh㉿kali)-[~/SRE-Intro]
└─$ kubectl exec -n monitoring deployment/prometheus -- wget -qO- \
  'http://localhost:9090/api/v1/query?query=sum(increase(gateway_requests_total%7Bstatus%3D~%225..%22%7D%5B3m%5D))'
{"status":"success","data":{"resultType":"vector","result":[{"metric":{},"value":[1782462325.521,"1032.6857142857143"]}]}}
```
So the difference is not very much, just ~10 responses. Based on these observations, deleting a single pod did not cause a significant increase in service errors.
Kubernetes replaced the failed pod quickly, and the service continued handling requests with minimal observable impact.

#### Comparison
Matched: Kubernetes really balances incoming load between healthy pods, and this process is really fast. \
Surprised: Kubernetes recreated new pod immediately, so I even was not able to see the "drop-down" of the load. Load was redistributed among 5 pods, not 4.

#### To improve resilience against this failure, I would configure readiness and liveness probes, use a PodDisruptionBudget, enable graceful shutdown so in-flight requests can complete before a pod is terminated, and ensure that multiple replicas are distributed across different nodes. These measures would further reduce the impact of pod failures on service availability.


### Task 1 Experiment 2 — Payment Latency Injection
#### Hypothesis                        
If payments takes 2 seconds per request,
the gateway should not return additional 5xx responses because the latency is below the configured 5 s timeout. Read endpoints should remain unaffected.

#### The command(s) I ran 
```
┌──(shersh㉿kali)-[~/SRE-Intro]
└─$ kubectl set env deployment/payments PAYMENT_LATENCY_MS=2000
deployment.apps/payments env updated
                                                                                                                                                                                 
┌──(shersh㉿kali)-[~/SRE-Intro]
└─$ kubectl rollout status deployment/payments --timeout=30s
Waiting for deployment "payments" rollout to finish: 1 old replicas are pending termination...
Waiting for deployment "payments" rollout to finish: 1 old replicas are pending termination...
deployment "payments" successfully rolled out
                                                                                                                                                                                 
┌──(shersh㉿kali)-[~/SRE-Intro]
└─$ kubectl exec -n monitoring deployment/prometheus -- wget -qO- \
  'http://localhost:9090/api/v1/query?query=sum(rate(gateway_requests_total%7Bstatus%3D~%225..%22%7D%5B1m%5D))/sum(rate(gateway_requests_total%5B1m%5D))'
{"status":"success","data":{"resultType":"vector","result":[{"metric":{},"value":[1782466445.626,"0.7708830548926013"]}]}}                                                                                                                                                                                 

┌──(shersh㉿kali)-[~/SRE-Intro]
└─$ kubectl exec -n monitoring deployment/prometheus -- wget -qO- \
  'http://localhost:9090/api/v1/query?query=histogram_quantile(0.99,+sum+by+(le,path)+(rate(gateway_request_duration_seconds_bucket%5B1m%5D)))'
{"status":"success","data":{"resultType":"vector","result":[{"metric":{"path":"/events"},"value":[1782466460.486,"0.02419545454545453"]},{"metric":{"path":"/events/{id}/reserve"},"value":[1782466460.486,"NaN"]},{"metric":{"path":"/health"},"value":[1782466460.486,"0.24850000000000103"]}]}}                                                                                                                                                                                 

┌──(shersh㉿kali)-[~/SRE-Intro]
└─$ kubectl set env deployment/payments PAYMENT_LATENCY_MS=6000
deployment.apps/payments env updated
                                                                                                                                                                                 
┌──(shersh㉿kali)-[~/SRE-Intro]
└─$ kubectl exec -n monitoring deployment/prometheus -- wget -qO- \
  'http://localhost:9090/api/v1/query?query=sum(rate(gateway_requests_total%7Bstatus%3D~%225..%22%7D%5B1m%5D))/sum(rate(gateway_requests_total%5B1m%5D))'
{"status":"success","data":{"resultType":"vector","result":[{"metric":{},"value":[1782466512.309,"0.7673860911270984"]}]}}                                                                                                                                                                                 

┌──(shersh㉿kali)-[~/SRE-Intro]
└─$ kubectl exec -n monitoring deployment/prometheus -- wget -qO- \
  'http://localhost:9090/api/v1/query?query=histogram_quantile(0.99,+sum+by+(le,path)+(rate(gateway_request_duration_seconds_bucket%5B1m%5D)))'
{"status":"success","data":{"resultType":"vector","result":[{"metric":{"path":"/health"},"value":[1782466516.216,"0.050499999999999975"]},{"metric":{"path":"/events"},"value":[1782466516.216,"0.02389310344827588"]},{"metric":{"path":"/events/{id}/reserve"},"value":[1782466516.216,"0.02485"]}]}}
```

#### What I observed
Observations:
- After injecting 2 s payment latency, the deployment rolled out successfully.
- The 5xx error rate remained high (~0.77) and did not change significantly after increasing latency to 6 s.
- Endpoint latency metrics showed no noticeable increase for read endpoints (/events, /health), suggesting they were unaffected.
- The increase in /pay p99 latency was not visible in the collected metrics (possibly due to insufficient traffic or missing samples).

#### Comparison
Matched: Read endpoints were not affected by the injected payment latency.

Surprised:
- The /pay p99 latency spik wwas not visible in the metrics. The expected result was that no additional 5xx responses would be returned because the injected 2 s latency is below the 5 s gateway timeout. However, the Prometheus query still reported an approximately 77% 5xx rate.
This likely reflects pre-existing errors or failures from other requests included in the 1-minute rate window rather than errors caused by the injected payment latency.
- The /events/{id}/reserve endpoint was not affected. In previous labs, payment issues also impacted reservations, but that behavior was not observed in this experiment.
- Contrary to expectations, increasing the payment latency from 2 s to 6 s did not noticeably increase the observed 5xx rate.

#### To improve resilience against this failure, I would add retries with exponential backoff and a circuit breaker for the payment service, improve monitoring of payment latency, and review timeout settings to ensure they are appropriate.

### Task 1 Experiment 3 — Redis Failure
#### Hypothesis          
If Redis goes down, users should still be able to list events, but they should not be able to reserve tickets because the reservation workflow depends on Redis.

#### The command(s) I ran 
```
┌──(shersh㉿kali)-[~/SRE-Intro]
└─$ kubectl scale deployment/redis --replicas=0
deployment.apps/redis scaled

┌──(shersh㉿kali)-[~/SRE-Intro]
└─$ kubectl get pods -l app=redis -w
^C

┌──(shersh㉿kali)-[~/SRE-Intro]
└─$ kubectl run chaos-probe --image=curlimages/curl:latest --rm -i --restart=Never --quiet --command -- \
  sh -c 'echo "GET /events:"; curl -s -o /dev/null -w "%{http_code} %{time_total}s\n" http://gateway:8080/events;
         echo "POST /reserve:"; curl -s -X POST -w "%{http_code} %{time_total}s\n" \
              -H "Content-Type: application/json" -d "{\"quantity\":1}" \
              http://gateway:8080/events/1/reserve;
         echo "GET /health:"; curl -s http://gateway:8080/health'
GET /events:
200 0.021429s
POST /reserve:
500 0.011138s
GET /health:
{"status":"degraded","checks":{"events":"down","payments":"ok","circuit_payments":"CLOSED"}}

┌──(shersh㉿kali)-[~/SRE-Intro]
└─$ kubectl scale deployment/redis --replicas=1 && kubectl wait --for=condition=Available deployment/redis --timeout=60s
deployment.apps/redis scaled
deployment.apps/redis condition met
```

#### What I observed
- The Redis deployment was successfully scaled down, and no Redis pods remained running.
- GET /events returned 200 OK, showing that event listing continued to work without Redis.
- POST /events/1/reserve returned 503 Service Unavailable, confirming that ticket reservations depend on Redis.
- The /health endpoint reported a degraded system state. The response indicated that the events service was unavailable (events: "down"), while the payments service remained healthy.
- After scaling Redis back to one replica, the deployment became available again, confirming successful recovery.

#### Comparison
Matched:
- Users were still able to list events after Redis was disabled.
- Ticket reservations failed because the reservation workflow depends on Redis.
- The health endpoint reported a degraded system state while the payments service remained healthy.

Surprised: The /health endpoint marked the events service as down rather than reporting Redis separately as unavailable. This suggests that the health status of the events service depends on Redis availability.

#### To improve resilience against this failure, I would deploy Redis in a highly available configuration (for example, using Redis Sentinel or Redis Cluster), add graceful degradation for Redis-dependent features, and ensure that read-only operations remain available during Redis outages.


### Task 2 — Combined Failure Scenario
#### Scenario design (what + why)
I simulated degraded dependencies by combining two failures:
- Set the payments service to 30% failure rate with 500 ms artificial latency.
- Limited the events service database connection pool to 3 connections.
- Increased workload by scaling the mixedload deployment from 2 to 3 replicas.

The goal was to observe how simultaneous dependency failures affect the system under higher load and determine which component becomes the bottleneck first.

#### Observations over the 3-5 minute window — which golden signal reacted first?
```
┌──(shersh㉿kali)-[~/SRE-Intro]
└─$ kubectl exec -n monitoring deployment/prometheus -- wget -qO- \
  'http://localhost:9090/api/v1/query?query=sum(rate(gateway_requests_total%7Bstatus%3D~%225..%22%7D%5B1m%5D))/sum(rate(gateway_requests_total%5B1m%5D))'

{"status":"success","data":{"resultType":"vector","result":[{"metric":{},"value":[1782471963.986,"0.839430894308943"]}]}}                                                                                                                                                        
┌──(shersh㉿kali)-[~/SRE-Intro]
└─$ kubectl exec -n monitoring deployment/prometheus -- wget -qO- \
  'http://localhost:9090/api/v1/query?query=sum(rate(gateway_requests_total%7Bstatus%3D~%225..%22%7D%5B1m%5D))/sum(rate(gateway_requests_total%5B1m%5D))'

{"status":"success","data":{"resultType":"vector","result":[{"metric":{},"value":[1782472103.448,"0.8648180242634316"]}]}}                                                                                                                                                        
┌──(shersh㉿kali)-[~/SRE-Intro]
└─$ kubectl exec -n monitoring deployment/prometheus -- wget -qO- \
  'http://localhost:9090/api/v1/query?query=histogram_quantile(0.99,+sum+by+(le,path)+(rate(gateway_request_duration_seconds_bucket%5B1m%5D)))'

{"status":"success","data":{"resultType":"vector","result":[{"metric":{"path":"/health"},"value":[1782472132.624,"0.12849999999999953"]},{"metric":{"path":"/events"},"value":[1782472132.624,"0.009946328293736501"]},{"metric":{"path":"/events/{id}/reserve"},"value":[1782472132.624,"NaN"]}]}}                                                                                                                                                        
┌──(shersh㉿kali)-[~/SRE-Intro]
└─$ kubectl exec -n monitoring deployment/prometheus -- wget -qO- \
  'http://localhost:9090/api/v1/query?query=histogram_quantile(0.99,+sum+by+(le,path)+(rate(gateway_request_duration_seconds_bucket%5B1m%5D)))'

{"status":"success","data":{"resultType":"vector","result":[{"metric":{"path":"/health"},"value":[1782472155.377,"0.043250000000000025"]},{"metric":{"path":"/events"},"value":[1782472155.377,"0.009956387665198237"]},{"metric":{"path":"/events/{id}/reserve"},"value":[1782472155.377,"0.00495"]}]}}
```
The error rate reacted first and showed the most significant degradation. \
Prometheus queries reported:
- Initial 5xx error ratio: 0.839 (83.9%)
- Later 5xx error ratio: 0.865 (86.5%)

This indicates that most gateway requests were failing during the experiment, showing that the combined failures severely impacted service availability. \
The first measurement for /events/{id}/reserve returned NaN, suggesting insufficient successful requests during the observation period because many requests failed. Once some successful requests were recorded, the latency stabilized around 5 ms. \
Overall, latency did not increase dramatically, while the error rate increased sharply, indicating that requests were failing before spending significant time waiting. \

The error rate was the first and strongest golden signal to react. It rapidly increased above 80%, while latency remained relatively stable for successful requests.

#### Which path shows the worst latency amplification? (/events vs /events/{id}/reserve vs /pay)
Among the application endpoints, /events showed the highest measurable p99 latency (~10 ms). The /events/{id}/reserve endpoint initially produced NaN, indicating that too few successful requests completed to calculate latency, which suggests it was more heavily affected by failures even though its eventual measured latency was lower.

#### Answer: "Which component was the weakest link? How would you make it more resilient?"
The weakest link was the payments service, as its failures caused the gateway error rate to exceed 80%. To improve resilience, I would add retries with exponential backoff, circuit breakers, request timeouts, and better database connection management to reduce cascading failures.
