FROM registry.com:8500/library/redis:5.0.3-alpine

RUN apk update
RUN apk add python3
RUN pip3 install kubernetes
COPY redis-k8s.py /root/
COPY redis.conf /root/redis.conf
COPY entrypoint.sh /root/entrypoint.sh
RUN  chmod 777 /root/entrypoint.sh
ENV  PASSWORD=123456789
ENV POD_NAMESPACE redis
ENV REDIS_SERVICE_NAME redis-cluster
ENV REDIS_CONFIG_FILE /data/redis.conf
ENV STATEFUL_SET_NAME redis-app

ENTRYPOINT ["/root/entrypoint.sh"]
