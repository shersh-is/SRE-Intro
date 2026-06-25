# Lab 7 — Progressive Delivery: Canary Deployments
## Proof of work by Viktoriya Yurina B24-CBS-01
### Task 1 — Manual Canary Deployment
#### Output of kubectl argo rollouts version
```
┌──(shersh㉿kali)-[~/SRE-Intro]
└─$ kubectl argo rollouts version
kubectl-argo-rollouts: v1.9.0+838d4e7
  BuildDate: 2026-03-20T21:08:11Z
  GitCommit: 838d4e792be666ec11bd0c80331e0c5511b5010e
  GitTreeState: clean
  GoVersion: go1.24.13
  Compiler: gc
  Platform: linux/amd64
```

#### Output of kubectl argo rollouts get rollout gateway showing Paused at 20% (during canary)
```
Name:            gateway
Namespace:       default
Status:          ॥ Paused
Message:         CanaryPauseStep
Strategy:        Canary
  Step:          1/5
  SetWeight:     20
  ActualWeight:  20
Images:          ghcr.io/shersh-is/quickticket-gateway:19bf938567b44de1dfb4bf45b29ef1430579c944 (canary, stable)
Replicas:
  Desired:       5
  Current:       5
  Updated:       1
  Ready:         5
  Available:     5

NAME                                 KIND        STATUS     AGE    INFO
⟳ gateway                            Rollout     ॥ Paused   3m38s  
├──# revision:2                                                    
│  └──⧉ gateway-7474f66f7d           ReplicaSet  ✔ Healthy  40s    canary
│     └──□ gateway-7474f66f7d-5zns9  Pod         ✔ Running  39s    ready:1/1
└──# revision:1                                                    
   └──⧉ gateway-5588cbccc4           ReplicaSet  ✔ Healthy  3m38s  stable
      ├──□ gateway-5588cbccc4-4dplx  Pod         ✔ Running  3m37s  ready:1/1
      ├──□ gateway-5588cbccc4-5rsb5  Pod         ✔ Running  3m37s  ready:1/1
      ├──□ gateway-5588cbccc4-qjpx4  Pod         ✔ Running  3m37s  ready:1/1
      └──□ gateway-5588cbccc4-xzp7r  Pod         ✔ Running  3m37s  ready:1/1
```

#### Output after promote — showing progression to 100%
```
Name:            gateway
Namespace:       default
Status:          ✔ Healthy
Strategy:        Canary
  Step:          5/5
  SetWeight:     100
  ActualWeight:  100
Images:          ghcr.io/shersh-is/quickticket-gateway:19bf938567b44de1dfb4bf45b29ef1430579c944 (stable)
Replicas:
  Desired:       5
  Current:       5
  Updated:       5
  Ready:         5
  Available:     5

NAME                                 KIND        STATUS        AGE    INFO
⟳ gateway                            Rollout     ✔ Healthy     9m43s  
├──# revision:2                                                       
│  └──⧉ gateway-7474f66f7d           ReplicaSet  ✔ Healthy     6m45s  stable
│     ├──□ gateway-7474f66f7d-5zns9  Pod         ✔ Running     6m44s  ready:1/1
│     ├──□ gateway-7474f66f7d-mlgv8  Pod         ✔ Running     112s   ready:1/1
│     ├──□ gateway-7474f66f7d-zmqhp  Pod         ✔ Running     112s   ready:1/1
│     ├──□ gateway-7474f66f7d-9fp78  Pod         ✔ Running     71s    ready:1/1
│     └──□ gateway-7474f66f7d-skcnq  Pod         ✔ Running     71s    ready:1/1
└──# revision:1                                                       
   └──⧉ gateway-5588cbccc4           ReplicaSet  • ScaledDown  9m43s  
```

#### Output after abort — showing instant rollback
```
┌──(shersh㉿kali)-[~/SRE-Intro]
└─$ kubectl argo rollouts get rollout gateway        
Name:            gateway
Namespace:       default
Status:          ✖ Degraded
Message:         RolloutAborted: Rollout aborted update to revision 3
Strategy:        Canary
  Step:          0/5
  SetWeight:     0
  ActualWeight:  0
Images:          ghcr.io/shersh-is/quickticket-gateway:19bf938567b44de1dfb4bf45b29ef1430579c944 (stable)
Replicas:
  Desired:       5
  Current:       5
  Updated:       0
  Ready:         5
  Available:     5

NAME                                 KIND        STATUS        AGE    INFO
⟳ gateway                            Rollout     ✖ Degraded    11m    
├──# revision:3                                                       
│  └──⧉ gateway-ffcc46fc6            ReplicaSet  • ScaledDown  51s    canary
├──# revision:2                                                       
│  └──⧉ gateway-7474f66f7d           ReplicaSet  ✔ Healthy     8m27s  stable
│     ├──□ gateway-7474f66f7d-5zns9  Pod         ✔ Running     8m26s  ready:1/1
│     ├──□ gateway-7474f66f7d-mlgv8  Pod         ✔ Running     3m34s  ready:1/1
│     ├──□ gateway-7474f66f7d-zmqhp  Pod         ✔ Running     3m34s  ready:1/1
│     ├──□ gateway-7474f66f7d-9fp78  Pod         ✔ Running     2m53s  ready:1/1
│     └──□ gateway-7474f66f7d-j2pwr  Pod         ✔ Running     23s    ready:1/1
└──# revision:1                                                       
   └──⧉ gateway-5588cbccc4           ReplicaSet  • ScaledDown  11m    
```

#### Answer: "How long from abort to all traffic serving the stable version? Compare with git revert rollback from Lab 5."
After aborting the rollout, all traffic was redirected back to the stable version in approximately 15–20 seconds. This was significantly faster than the git revert rollback from Lab 5, which took about 7 minutes because it involved creating a Git commit, pushing changes, running the CI pipeline, ArgoCD synchronization, and a full Kubernetes rollout. In contrast, aborting an Argo Rollouts canary immediately switched traffic back to the stable ReplicaSet without rebuilding or redeploying the application.

### Task 2 — Multi-Step Canary with Observation
#### Multi-step canary strategy YAML
```
┌──(shersh㉿kali)-[~/SRE-Intro]
└─$ cat k8s/gateway.yml    
apiVersion: apps/v1
kind: Deployment
metadata:
  name: gateway
spec:
  replicas: 1
  selector:
    matchLabels:
      app: gateway
  template:
    metadata:
      labels:
        version: "v2"
        app: gateway
    spec:
      imagePullSecrets:
        - name: ghcr-secret
      containers:
        - name: gateway
          image: ghcr.io/shersh-is/quickticket-gateway:19bf938567b44de1dfb4bf45b29ef1430579c944
          imagePullPolicy: Always
          ports:
            - containerPort: 8080
          env:
            - name: EVENTS_URL
              value: "http://events:8081"
            - name: PAYMENTS_URL
              value: "http://payments:8082"
            - name: GATEWAY_TIMEOUT_MS
              value: "5000"

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

          readinessProbe:
            httpGet:
              path: /health
              port: 8080
            periodSeconds: 5
            failureThreshold: 2
---
apiVersion: v1
kind: Service
metadata:
  name: gateway
spec:
  selector:
    app: gateway
  ports:
    - port: 8080
      targetPort: 8080
  type: ClusterIP
```

#### Output of kubectl argo rollouts get rollout gateway --watch showing at least 3 steps
```
Name:            gateway
Namespace:       default
Status:          ◌ Progressing
Message:         more replicas need to be updated
Strategy:        Canary
  Step:          0/9
  SetWeight:     20
  ActualWeight:  0
Images:          ghcr.io/shersh-is/quickticket-gateway:19bf938567b44de1dfb4bf45b29ef1430579c944 (canary, stable)
Replicas:
  Desired:       5
  Current:       5
  Updated:       1
  Ready:         4
  Available:     4

NAME                                 KIND        STATUS         AGE  INFO
⟳ gateway                            Rollout     ◌ Progressing  89m  
├──# revision:7                                                      
│  └──⧉ gateway-5588cbccc4           ReplicaSet  ◌ Progressing  89m  canary
│     └──□ gateway-5588cbccc4-lbx44  Pod         ✔ Running      9s   ready:1/1
├──# revision:6                                                      
│  └──⧉ gateway-fdbf4c955            ReplicaSet  • ScaledDown   11m  
├──# revision:5                                                      
│  └──⧉ gateway-55c5fb7994           ReplicaSet  • ScaledDown   17m  
├──# revision:3                                                      
│  └──⧉ gateway-ffcc46fc6            ReplicaSet  • ScaledDown   78m  
└──# revision:2                                                      
   └──⧉ gateway-7474f66f7d           ReplicaSet  ✔ Healthy      86m  stable
      ├──□ gateway-7474f66f7d-mlgv8  Pod         ✔ Running      81m  ready:1/1
      ├──□ gateway-7474f66f7d-zmqhp  Pod         ✔ Running      81m  ready:1/1
      ├──□ gateway-7474f66f7d-j2pwr  Pod         ✔ Running      78m  ready:1/1
      └──□ gateway-7474f66f7d-ntx6q  Pod         ✔ Running      17m  ready:1/1






Name:            gateway
Namespace:       default
Status:          ◌ Progressing
Message:         more replicas need to be updated
Strategy:        Canary
  Step:          0/9
  SetWeight:     20
  ActualWeight:  25
Images:          ghcr.io/shersh-is/quickticket-gateway:19bf938567b44de1dfb4bf45b29ef1430579c944 (canary, stable)
Replicas:
  Desired:       5
  Current:       5
  Updated:       1
  Ready:         4
  Available:     4

NAME                                 KIND        STATUS         AGE  INFO
⟳ gateway                            Rollout     ◌ Progressing  89m  
├──# revision:7                                                      
│  └──⧉ gateway-5588cbccc4           ReplicaSet  ✔ Healthy      89m  canary
│     └──□ gateway-5588cbccc4-lbx44  Pod         ✔ Running      10s  ready:1/1
├──# revision:6                                                      
│  └──⧉ gateway-fdbf4c955            ReplicaSet  • ScaledDown   11m  
├──# revision:5                                                      
│  └──⧉ gateway-55c5fb7994           ReplicaSet  • ScaledDown   17m  
├──# revision:3                                                      
│  └──⧉ gateway-ffcc46fc6            ReplicaSet  • ScaledDown   78m  
└──# revision:2                                                      
   └──⧉ gateway-7474f66f7d           ReplicaSet  ✔ Healthy      86m  stable
      ├──□ gateway-7474f66f7d-mlgv8  Pod         ✔ Running      81m  ready:1/1
      ├──□ gateway-7474f66f7d-zmqhp  Pod         ✔ Running      81m  ready:1/1
      ├──□ gateway-7474f66f7d-j2pwr  Pod         ✔ Running      78m  ready:1/1
      └──□ gateway-7474f66f7d-ntx6q  Pod         ✔ Running      17m  ready:1/1






Name:            gateway
Namespace:       default
Status:          ◌ Progressing
Message:         more replicas need to be updated
Strategy:        Canary
  Step:          1/9
  SetWeight:     20
  ActualWeight:  20
Images:          ghcr.io/shersh-is/quickticket-gateway:19bf938567b44de1dfb4bf45b29ef1430579c944 (canary, stable)
Replicas:
  Desired:       5
  Current:       5
  Updated:       1
  Ready:         5
  Available:     5

NAME                                 KIND        STATUS         AGE  INFO
⟳ gateway                            Rollout     ◌ Progressing  89m  
├──# revision:7                                                      
│  └──⧉ gateway-5588cbccc4           ReplicaSet  ✔ Healthy      89m  canary
│     └──□ gateway-5588cbccc4-lbx44  Pod         ✔ Running      11s  ready:1/1
├──# revision:6                                                      
│  └──⧉ gateway-fdbf4c955            ReplicaSet  • ScaledDown   11m  
├──# revision:5                                                      
│  └──⧉ gateway-55c5fb7994           ReplicaSet  • ScaledDown   17m  
├──# revision:3                                                      
│  └──⧉ gateway-ffcc46fc6            ReplicaSet  • ScaledDown   78m  
└──# revision:2                                                      
   └──⧉ gateway-7474f66f7d           ReplicaSet  ✔ Healthy      86m  stable
      ├──□ gateway-7474f66f7d-mlgv8  Pod         ✔ Running      81m  ready:1/1
      ├──□ gateway-7474f66f7d-zmqhp  Pod         ✔ Running      81m  ready:1/1
      ├──□ gateway-7474f66f7d-j2pwr  Pod         ✔ Running      78m  ready:1/1
      └──□ gateway-7474f66f7d-ntx6q  Pod         ✔ Running      17m  ready:1/1






Name:            gateway
Namespace:       default
Status:          ॥ Paused
Message:         CanaryPauseStep
Strategy:        Canary
  Step:          1/9
  SetWeight:     20
  ActualWeight:  20
Images:          ghcr.io/shersh-is/quickticket-gateway:19bf938567b44de1dfb4bf45b29ef1430579c944 (canary, stable)
Replicas:
  Desired:       5
  Current:       5
  Updated:       1
  Ready:         5
  Available:     5

NAME                                 KIND        STATUS        AGE  INFO
⟳ gateway                            Rollout     ॥ Paused      89m  
├──# revision:7                                                     
│  └──⧉ gateway-5588cbccc4           ReplicaSet  ✔ Healthy     89m  canary
│     └──□ gateway-5588cbccc4-lbx44  Pod         ✔ Running     12s  ready:1/1
├──# revision:6                                                     
│  └──⧉ gateway-fdbf4c955            ReplicaSet  • ScaledDown  11m  
├──# revision:5                                                     
│  └──⧉ gateway-55c5fb7994           ReplicaSet  • ScaledDown  17m  
├──# revision:3                                                     
│  └──⧉ gateway-ffcc46fc6            ReplicaSet  • ScaledDown  78m  
└──# revision:2                                                     
   └──⧉ gateway-7474f66f7d           ReplicaSet  ✔ Healthy     86m  stable
      ├──□ gateway-7474f66f7d-mlgv8  Pod         ✔ Running     81m  ready:1/1
      ├──□ gateway-7474f66f7d-zmqhp  Pod         ✔ Running     81m  ready:1/1
      ├──□ gateway-7474f66f7d-j2pwr  Pod         ✔ Running     78m  ready:1/1
      └──□ gateway-7474f66f7d-ntx6q  Pod         ✔ Running     17m  ready:1/1
```

#### Dashboard observation during the rollout
The request rate remained stable at approximately 50 req/s throughout the rollout. Average response latency increased slightly from 35 ms to 45 ms during intermediate canary steps and returned to ~38 ms after reaching 100% traffic. CPU utilization increased from ~80 mCPU to ~140 mCPU per pod, while memory usage stayed around 60–70 MiB. No HTTP 5xx errors or abnormal metric spikes were observed, indicating a successful rollout.


#### Answer: "At what canary percentage would you want an automated abort? Why?"
I would configure an automated abort at 40% canary traffic. At this stage, enough real user traffic reaches the new version to detect issues reliably, while the impact remains limited. Aborting later (e.g., at 80%) would expose too many users to a potentially faulty release, whereas aborting at 20% may not provide enough traffic to reveal less frequent problems.
