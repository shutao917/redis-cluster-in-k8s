#! /bin/sh

sed -i  -e '23c masterauth '"$PASSWORD"'' -e '35c requirepass '"$PASSWORD"''  /root/redis.conf

if [ ! -f "/data/redis.conf" ];then
cp /root/redis.conf /data/redis.conf
fi
python3 /root/redis-k8s.py
redis-server /data/redis.conf
