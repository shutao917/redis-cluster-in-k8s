# redis-cluster-in-k8s
k8s部署redis集群实例
# 起因
redis cluster集群中各redis实例的cluster.conf文件保存了集群所有节点的信息,只支持ip,不支持域名,而k8s集群中,各容器的ip是随机，并且随着Pod的重建而变化
假如有这样一个6节点的集群:  
172.31.100.11:7000@17000 master  
172.31.100.12:7000@17000 master  
172.31.100.13:7000@17000 slave  
172.31.100.14:7000@17000 slave  
172.31.100.10:7000@17000 myself,slave  
172.31.100.15:7000@17000 master  

此时会存在以下两种情况  
1.如果172.31.100.10节点挂掉,pod重建后,ip变更为172.31.100.16,redis启动后会按照cluster.conf中的配置，把本节点的信息(包括ip)传播给其他节点,其他节点根据新ip更新自己的cluster.conf文件.但因为Redis不会更新cluster.conf中自己那一条的ip,所以新的172.31.100.16节点上cluster.conf中自己的ip还是172.18.10.10. 些时各节点之间的通信恢复正常，但很多程序的驱动会获取cluster.conf缓存起来，用于后续的key路由,连接到新的172.31.100.16节点的程序，获取到的cluster.conf文件中，ip还是172.31.100.10,最后会因为无法连接而报错

2.如果所有节点都挂掉(像上次深圳机房维护),重启后所有节点的IP都已发生变化,些时每个节点根据cluster.conf中的配置，都找不到任何其他节点，整个集群崩溃

# 原理
使用redis-k8s.py脚本，在redis-server启动前，调用k8s api获取其他实例的ip，更新cluster.conf文件，并在第一次启动时自动创建redis集群,流程如下  
![image](https://github.com/shutao917/redis-cluster-in-k8s/blob/master/images/Redis-Cluster-In-K8S.jpg)

其中的判断逻辑如下:  
1.本节点是否已加入Redis集群  
    如果本地cluster.conf文件不存在，或cluster.conf中只有本节点的记录,则认为本节点还没有加入Redis集群  
2.是否已存在集群  
    连接其他已启动节点的redis server,执行cluster nodes命令,如果有一个节点是slave或slot已经分配，则认为集群已经存在  
3.是否是最后一个启动的Pod  
    使用K8S Api Server，读取StatefulSet的当前状态，StatefulSet中Pod是按顺序启动，把Pod的readinessProbe设置为tcpSocket:port:7000,只有当前一个Pod处于Ready状态(Redis 7000端口启动)，才会启动下一个Pod，因此当current_replicas==replicas时,认为当前为最后一个启动的Pod,并且前面所有Redis已经启动

# 使用
1、创建镜像并上传到镜像仓库  
docker build -t registry.yingzi.com:8500/library/redis:5.0.3-cluster ./  
docker push registry.yingzi.com:8500/library/redis:5.0.3-cluster  
2、部署StatefulSet  
kubectl create -f rediscluster.yaml  
一个6节点，3主3从的节点创建完毕,redis-cli -h redis-cluster -p 7000 -a abcdef cluster nodes查看集群节点

# 联系方式
QQ:276522206
