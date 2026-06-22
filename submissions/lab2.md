# Lab 2 — Containerization: Inspect, Understand, Optimize
## Proof of work by Viktoriya Yurina

### Task 1 — Docker Inspection & Operations
#### Output of docker images | grep app with image sizes
```
┌──(shersh㉿kali)-[~/SRE-Intro/app]
└─$ sudo docker images | grep app
app-gateway          latest         53d972da0029   22 hours ago    142MB
app-events           latest         46d5cfa0edd1   23 hours ago    156MB
app-payments         latest         c03f349ec632   23 hours ago    141MB
```
#### Output of docker history for one image — annotate which layer is pip install
app-events is the largest layer, thus:
```
┌──(shersh㉿kali)-[~/SRE-Intro/app]
└─$ sudo docker history app-events --no-trunc --format "table {{.CreatedBy}}\n{{.Size}}"
CREATED BY
SIZE
CMD ["uvicorn" "main:app" "--host" "0.0.0.0" "--port" "8081"]
0B
EXPOSE map[8081/tcp:{}]
0B
COPY main.py . # buildkit
10.6kB
RUN /bin/sh -c pip install --no-cache-dir -r requirements.txt # buildkit
38.5MB
COPY requirements.txt . # buildkit
96B
WORKDIR /app
0B
CMD ["python3"]
0B
RUN /bin/sh -c set -eux;  for src in idle3 pip3 pydoc3 python3 python3-config; do   dst="$(echo "$src" | tr -d 3)";   [ -s "/usr/local/bin/$src" ];   [ ! -e "/usr/local/bin/$dst" ];   ln -svT "$src" "/usr/local/bin/$dst";  done # buildkit
36B
RUN /bin/sh -c set -eux;   savedAptMark="$(apt-mark showmanual)";  apt-get update;  apt-get install -y --no-install-recommends   dpkg-dev   gcc   gnupg   libbluetooth-dev   libbz2-dev   libc6-dev   libdb-dev   libffi-dev   libgdbm-dev   liblzma-dev   libncursesw5-dev   libreadline-dev   libsqlite3-dev   libssl-dev   make   tk-dev   uuid-dev   wget   xz-utils   zlib1g-dev  ;   wget -O python.tar.xz "https://www.python.org/ftp/python/${PYTHON_VERSION%%[a-z]*}/Python-$PYTHON_VERSION.tar.xz";  echo "$PYTHON_SHA256 *python.tar.xz" | sha256sum -c -;  wget -O python.tar.xz.asc "https://www.python.org/ftp/python/${PYTHON_VERSION%%[a-z]*}/Python-$PYTHON_VERSION.tar.xz.asc";  GNUPGHOME="$(mktemp -d)"; export GNUPGHOME;  gpg --batch --keyserver hkps://keys.openpgp.org --recv-keys "$GPG_KEY";  gpg --batch --verify python.tar.xz.asc python.tar.xz;  gpgconf --kill all;  rm -rf "$GNUPGHOME" python.tar.xz.asc;  mkdir -p /usr/src/python;  tar --extract --directory /usr/src/python --strip-components=1 --file python.tar.xz;  rm python.tar.xz;   cd /usr/src/python;  gnuArch="$(dpkg-architecture --query DEB_BUILD_GNU_TYPE)";  ./configure   --build="$gnuArch"   --enable-loadable-sqlite-extensions   --enable-optimizations   --enable-option-checking=fatal   --enable-shared   $(test "${gnuArch%%-*}" != 'riscv64' && echo '--with-lto')   --with-ensurepip  ;  nproc="$(nproc)";  EXTRA_CFLAGS="$(dpkg-buildflags --get CFLAGS)";  LDFLAGS="$(dpkg-buildflags --get LDFLAGS)";  LDFLAGS="${LDFLAGS:-} -Wl,--strip-all";  arch="$(dpkg --print-architecture)"; arch="${arch##*-}";  case "$arch" in   amd64|arm64)    EXTRA_CFLAGS="${EXTRA_CFLAGS:-} -fno-omit-frame-pointer -mno-omit-leaf-frame-pointer";    ;;   i386)    ;;   *)    EXTRA_CFLAGS="${EXTRA_CFLAGS:-} -fno-omit-frame-pointer";    ;;  esac;  make -j "$nproc"   "EXTRA_CFLAGS=${EXTRA_CFLAGS:-}"   "LDFLAGS=${LDFLAGS:-}"  ;  rm python;  make -j "$nproc"   "EXTRA_CFLAGS=${EXTRA_CFLAGS:-}"   "LDFLAGS=${LDFLAGS:-} -Wl,-rpath='\$\$ORIGIN/../lib'"   python  ;  make install;   cd /;  rm -rf /usr/src/python;   find /usr/local -depth   \(    \( -type d -a \( -name test -o -name tests -o -name idle_test \) \)    -o \( -type f -a \( -name '*.pyc' -o -name '*.pyo' -o -name 'libpython*.a' \) \)   \) -exec rm -rf '{}' +  ;   ldconfig;   apt-mark auto '.*' > /dev/null;  apt-mark manual $savedAptMark;  find /usr/local -type f -executable -not \( -name '*tkinter*' \) -exec ldd '{}' ';'   | awk '/=>/ { so = $(NF-1); if (index(so, "/usr/local/") == 1) { next }; gsub("^/(usr/)?", "", so); printf "*%s\n", so }'   | sort -u   | xargs -rt dpkg-query --search   | awk 'sub(":$", "", $1) { print $1 }'   | sort -u   | xargs -r apt-mark manual  ;  apt-get purge -y --auto-remove -o APT::AutoRemove::RecommendsImportant=false;  apt-get dist-clean;   export PYTHONDONTWRITEBYTECODE=1;  python3 --version;  pip3 --version # buildkit
35.3MB
ENV PYTHON_SHA256=2ab91ff401783ccca64f75d10c882e957bdfd60e2bf5a72f8421793729b78a71
0B
ENV PYTHON_VERSION=3.13.13
0B
ENV GPG_KEY=7169605F62C751356D054A26A821E680E5FA6305
0B
RUN /bin/sh -c set -eux;  apt-get update;  apt-get install -y --no-install-recommends   ca-certificates   netbase   tzdata  ;  apt-get dist-clean # buildkit
3.81MB
ENV PATH=/usr/local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
0B
# debian.sh --arch 'amd64' out/ 'trixie' '@1779062400'
78.6MB
```
The 4th layer
```
RUN /bin/sh -c pip install --no-cache-dir -r requirements.txt # buildkit
38.5MB
```
is a pip install

#### IP addresses of all 3 services from docker inspect
```
┌──(shersh㉿kali)-[~/SRE-Intro/app]
└─$ sudo docker inspect app-events-1 --format '{{.Name}} {{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}'
/app-events-1 172.18.0.5
                                                                                                                      
┌──(shersh㉿kali)-[~/SRE-Intro/app]
└─$ sudo docker inspect app-gateway-1 --format '{{.Name}} {{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}'
/app-gateway-1 172.18.0.6
                                                                                                                      
┌──(shersh㉿kali)-[~/SRE-Intro/app]
└─$ sudo docker inspect app-payments-1 --format '{{.Name}} {{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}'
/app-payments-1 172.18.0.3
```
#### Environment variables of payments service
```
┌──(shersh㉿kali)-[~/SRE-Intro/app]
└─$ sudo docker inspect app-payments-1 --format '{{range .Config.Env}}{{println .}}{{end}}'                         
PAYMENT_FAILURE_RATE=0.0
PAYMENT_LATENCY_MS=0
PATH=/usr/local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
GPG_KEY=7169605F62C751356D054A26A821E680E5FA6305
PYTHON_VERSION=3.13.13
PYTHON_SHA256=2ab91ff401783ccca64f75d10c882e957bdfd60e2bf5a72f8421793729b78a71
```
#### Output of whoami and python3 urllib call to events:8081/health from inside the gateway container
```
┌──(shersh㉿kali)-[~/SRE-Intro/app]
└─$ sudo docker exec app-gateway-1 whoami                                                  
root

┌──(shersh㉿kali)-[~/SRE-Intro/app]
└─$ sudo docker exec app-gateway-1 python3 -c "        
import urllib.request
print(urllib.request.urlopen('http://events:8081/health').read().decode())
"
{"status":"healthy","checks":{"postgres":"ok","redis":"ok"}}
```
#### Log snippet showing the same request flowing through gateway → events
```
┌──(shersh㉿kali)-[~/SRE-Intro/app]
└─$ sudo docker-compose logs gateway --tail 5
gateway-1  | INFO:     Finished server process [1]
gateway-1  | INFO:     Started server process [1]
gateway-1  | INFO:     Waiting for application startup.
gateway-1  | INFO:     Application startup complete.
gateway-1  | INFO:     Uvicorn running on http://0.0.0.0:8080 (Press CTRL+C to quit)
                                                                                                                      
┌──(shersh㉿kali)-[~/SRE-Intro/app]
└─$ sudo docker-compose logs events --tail 5
events-1  | {"time":"2026-06-10 07:28:22,448","level":"INFO","service":"events","msg":"DB pool created (max=10)"}
events-1  | {"time":"2026-06-10 07:28:22,456","level":"INFO","service":"events","msg":"Redis connected"}
events-1  | INFO:     Application startup complete.
events-1  | INFO:     Uvicorn running on http://0.0.0.0:8081 (Press CTRL+C to quit)
events-1  | INFO:     172.18.0.6:46722 - "GET /health HTTP/1.1" 200 OK
```
#### Network inspect output showing all containers and their IPs
```
┌──(shersh㉿kali)-[~/SRE-Intro/app]
└─$ sudo docker network inspect app_default --format '{{range .Containers}}{{.Name}}: {{.IPv4Address}}{{"\n"}}{{end}}' 
app-gateway-1: 172.18.0.6/16
app-redis-1: 172.18.0.2/16
app-events-1: 172.18.0.5/16
app-postgres-1: 172.18.0.4/16
app-payments-1: 172.18.0.3/16
```
#### Answer: "How does the gateway find the events service? What IP does events resolve to?"
The gateway is not finding the events service by IP address directly.\
Both gateway and events are attached to the same network: app_default.\
Docker automatically creates DNS records for service names defined in docker-compose.yml.\
Therefore, the gateway can connect to the events service using the hostname events.\

TLDR: The gateway finds the events service through Docker Compose's internal DNS using the hostname events, which currently resolves to 172.18.0.5.

#### Image sizes before and after .dockerignore (any difference?)
Before:
```
┌──(shersh㉿kali)-[~/SRE-Intro/app]
└─$ sudo docker images | grep app
[sudo] password for shersh: 
app-gateway          latest         53d972da0029   22 hours ago    142MB
app-events           latest         46d5cfa0edd1   23 hours ago    156MB
app-payments         latest         c03f349ec632   23 hours ago    141MB
```
After:
```
┌──(shersh㉿kali)-[~/SRE-Intro/app]
└─$ sudo docker images | grep app       
app-gateway          latest         f01aa105bb79   25 seconds ago   142MB
app-events           latest         607342a5cc10   36 seconds ago   156MB
app-payments         latest         9bcecb9e677f   37 seconds ago   141MB
```
There are no differences. This is because .dockerignore reduces the build context rather than significantly affecting the final image layers. The ignored files were relatively small and therefore did not noticeably change the reported image sizes, although they help reduce build context size, improve build efficiency, and prevent unnecessary or sensitive files from being copied into images.

#### The .dockerignore content
```
┌──(shersh㉿kali)-[~/SRE-Intro/app]
└─$ cat events/.dockerignore
__pycache__
*.pyc
.git
.env
*.md
.vscode
```
#### Output of whoami inside the container after adding non-root user
```
┌──(shersh㉿kali)-[~/SRE-Intro/app]
└─$ sudo docker exec app-gateway-1 whoami      
app
```

#### The git diff of your Dockerfile changes
```
┌──(shersh㉿kali)-[~/SRE-Intro/app]
└─$ git diff gateway/Dockerfile
diff --git a/app/gateway/Dockerfile b/app/gateway/Dockerfile
index 68ef075..71c6891 100644
--- a/app/gateway/Dockerfile
+++ b/app/gateway/Dockerfile
@@ -6,4 +6,6 @@ RUN pip install --no-cache-dir -r requirements.txt
 COPY main.py .
 
 EXPOSE 8080
+RUN addgroup --system app && adduser --system --ingroup app app
+USER app
 CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
```
```
┌──(shersh㉿kali)-[~/SRE-Intro/app]
└─$ git diff events/Dockerfile
diff --git a/app/events/Dockerfile b/app/events/Dockerfile
index c45a68c..b6cb18d 100644
--- a/app/events/Dockerfile
+++ b/app/events/Dockerfile
@@ -6,4 +6,6 @@ RUN pip install --no-cache-dir -r requirements.txt
 COPY main.py .
 
 EXPOSE 8081
+RUN addgroup --system app && adduser --system --ingroup app app
+USER app
 CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8081"]
```
```
┌──(shersh㉿kali)-[~/SRE-Intro/app]
└─$ git diff payments/Dockerfile
diff --git a/app/payments/Dockerfile b/app/payments/Dockerfile
index 7f9e7c1..8cf997d 100644
--- a/app/payments/Dockerfile
+++ b/app/payments/Dockerfile
@@ -6,4 +6,6 @@ RUN pip install --no-cache-dir -r requirements.txt
 COPY main.py .
 
 EXPOSE 8082
+RUN addgroup --system app && adduser --system --ingroup app app
+USER app
 CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8082"]
```
   
