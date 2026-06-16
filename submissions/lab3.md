# Lab 3 — Monitoring, Observability & SLOs
## Proof of work by Viktoriya Yurina B24-CBS-01

### Task 1 — Configure Monitoring & Build Dashboard 
#### Output of compose ps showing all 7 services


#### Prometheus targets output (all 3 up)


#### Custom metrics list


#### PromQL query output (request rate)


#### PromQL queries you used for Latency and Saturation panels


#### Dashboard observations: normal traffic vs payments failure


#### Answer: "Which golden signal showed the failure first? How long after killing payments?"

### Task 2 — Define SLOs & Recording Rules
#### SLI/SLO definitions with error budget math


#### Rules loaded output


#### SLO gauge observation during failure

### Bonus Task — Correlate Failure Across Metrics & Logs
#### Timeline with timestamps: injection → first error in logs → spike on dashboard → recovery


#### Log excerpts from gateway and payments at the failure moment


#### Root cause explanation connecting metrics to logs
