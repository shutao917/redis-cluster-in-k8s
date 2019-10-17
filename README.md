# redis-cluster-in-k8s
k8s部署redis集群实例
# 起因
redis cluster集群中各redis实例的cluster.conf文件保存了集群所有节点的信息,只支持ip,不支持域名,而k8s集群中,各容器的ip是随机，并且随着Pod的重建变化,此时会存在以下两种情况
