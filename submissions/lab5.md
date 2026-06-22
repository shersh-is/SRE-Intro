# Lab 5 — CI/CD & GitOps
## Proof of work by Viktoriya Yurina

### Task 1 — CI Pipeline + ArgoCD Setup
#### Link to your GitHub Actions run (green check)
https://github.com/shersh-is/SRE-Intro/actions/runs/27945247999

#### Output of gh api user/packages?package_type=container showing pushed images
```
┌──(shersh㉿kali)-[~]
└─$ gh api user/packages?package_type=container --jq '.[].name'
quickticket-gateway
quickticket-events
quickticket-payments
```

#### Output of argocd app get quickticket showing Synced + Healthy

#### Output proving a Git change was synced (label, annotation, or image tag change visible in cluster)

#### Answer: "What happens if someone manually runs kubectl edit on a resource managed by ArgoCD?"

