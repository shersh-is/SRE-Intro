# Lab 1 — SRE Philosophy: Deploy, Break, Understand
## Proof of Work by Victoria Yurina B24-CBS-01

### Task 1 — Deploy & Break QuickTicket
#### Output of docker compose ps showing all 5 services running
```
┌──(shersh㉿kali)-[~/SRE-Intro/app]
└─$ sudo docker-compose ps
NAME             IMAGE                COMMAND                  SERVICE    CREATED          STATUS                    PORTS
app-events-1     app-events           "uvicorn main:app --…"   events     23 seconds ago   Up 16 seconds             0.0.0.0:8081->8081/tcp, :::8081->8081/tcp
app-gateway-1    app-gateway          "uvicorn main:app --…"   gateway    23 seconds ago   Up 15 seconds             0.0.0.0:3080->8080/tcp, [::]:3080->8080/tcp
app-payments-1   app-payments         "uvicorn main:app --…"   payments   23 seconds ago   Up 22 seconds             0.0.0.0:8082->8082/tcp, :::8082->8082/tcp
app-postgres-1   postgres:17-alpine   "docker-entrypoint.s…"   postgres   23 seconds ago   Up 22 seconds (healthy)   0.0.0.0:5432->5432/tcp, :::5432->5432/tcp
app-redis-1      redis:7-alpine       "docker-entrypoint.s…"   redis      23 seconds ago   Up 22 seconds (healthy)   0.0.0.0:6379->6379/tcp, :::6379->6379/tcp
```

#### Output of the full critical path (list → reserve → pay) with real data
```
┌──(shersh㉿kali)-[~/SRE-Intro/app]
└─$ curl -s http://localhost:3080/events | python3 -m json.tool 
[
    {
        "id": 1,
        "name": "Go Conference 2026",
        "venue": "Main Hall A",
        "date": "2026-09-15T09:00:00+00:00",
        "total_tickets": 100,
        "price_cents": 5000,
        "available": 100
    },
    {
        "id": 4,
        "name": "Python Workshop",
        "venue": "Lab 301",
        "date": "2026-09-22T14:00:00+00:00",
        "total_tickets": 25,
        "price_cents": 2000,
        "available": 25
    },
    {
        "id": 2,
        "name": "SRE Meetup",
        "venue": "Room 204",
        "date": "2026-10-01T18:00:00+00:00",
        "total_tickets": 30,
        "price_cents": 0,
        "available": 30
    },
    {
        "id": 5,
        "name": "Kubernetes Deep Dive",
        "venue": "Auditorium B",
        "date": "2026-10-10T10:00:00+00:00",
        "total_tickets": 80,
        "price_cents": 8000,
        "available": 80
    },
    {
        "id": 3,
        "name": "Cloud Native Summit",
        "venue": "Expo Center",
        "date": "2026-11-20T10:00:00+00:00",
        "total_tickets": 500,
        "price_cents": 15000,
        "available": 500
    }
]
                                                                                                                                              
┌──(shersh㉿kali)-[~/SRE-Intro/app]
└─$ curl -s -X POST http://localhost:3080/events/1/reserve \
  -H "Content-Type: application/json" \
  -d '{"quantity": 1}' | python3 -m json.tool
{
    "reservation_id": "a15fa6b7-efb6-4e60-9d87-c50d3e8adaa6",
    "event_id": 1,
    "quantity": 1,
    "total_cents": 5000,
    "expires_in_seconds": 300
}
                                                                                                                
┌──(shersh㉿kali)-[~/SRE-Intro/app]
└─$ curl -s -X POST http://localhost:3080/reserve/a15fa6b7-efb6-4e60-9d87-c50d3e8adaa6/pay | python3 -m json.tool
{
    "order_id": "a15fa6b7-efb6-4e60-9d87-c50d3e8adaa6",
    "event_id": 1,
    "quantity": 1,
    "total_cents": 5000,
    "status": "confirmed"
}
```

#### Output of curl -s http://localhost:3080/health when everything is healthy
```
┌──(shersh㉿kali)-[~/SRE-Intro/app]
└─$ curl -s http://localhost:3080/health | python3 -m json.tool
{
    "status": "healthy",
    "checks": {
        "events": "ok",
        "payments": "ok",
        "circuit_payments": "CLOSED"
    }
}
```

#### A dependency map
```
                 +------------------+
                 |     Gateway      |
                 |   (API Router)   |
                 +--------+---------+
                          |
          +---------------+---------------+
          |                               |
          v                               v
+------------------+          +------------------+
|      Events      |          |    Payments      |
| Ticket Service   |          | Payment Service  |
+--------+---------+          +------------------+
         |
         |
         +----------------+
         |                |
         v                v
+----------------+  +----------------+
|   PostgreSQL   |  |     Redis      |
| Event & Orders |  | Reservations   |
+----------------+  +----------------+
```

#### A failure table:
```
| Component Killed | Events List | Reserve | Pay | Health Check | User Impact |
|-----------------|----------- --|---------|-----|--------------|-------------|
| payments        |              |         |     |              |             |
| events          |              |         |     |              |             |
| redis           |              |         |     |              |             |
| postgres        |              |         |     |              |             |
```

#### Load generator output showing the error rate spike when payments is killed

### Task 2 — Graceful Degradation
#### The diff of your gateway change (git diff app/gateway/main.py)

#### Output of reserve (works) and pay (clear 503) when payments is down

### Task 3 — GitHub Community Engagement
#### GitHub Community
Starring repositories helps open-source projects by showing community interest and appreciation. A higher number of stars increases a project's visibility and can attract more contributors and users.\
Following developers helps you stay updated on their work, learn from their contributions, and discover useful projects. In team environments, it also makes collaboration easier by helping you track teammates' activity and professional growth.
