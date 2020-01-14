from kubernetes import client, config
import os,re,time
import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

def update_cluster_config():
    #获取环境变量
    namespace=os.environ['POD_NAMESPACE']
    service_name=os.environ['REDIS_SERVICE_NAME']
    conf_file=os.environ['REDIS_CONFIG_FILE']
    apiserver = 'https://'+os.environ['KUBERNETES_SERVICE_HOST']+ ":" + os.environ['KUBERNETES_SERVICE_PORT']
    pod_name=os.environ['POD_NAME']
    st_name=pod_name[0:pod_name.rfind('-')]

    redis_conf=get_redis_conf(conf_file)
    #调用API获取service所有endpoint
    with open('/var/run/secrets/kubernetes.io/serviceaccount/token', 'r') as file:
        Token = file.read().strip('\n')

    configuration = client.Configuration()
    configuration.host = apiserver
    configuration.verify_ssl = False
    configuration.api_key = {"authorization": "Bearer " + Token}
    client.Configuration.set_default(configuration)
    v1 = client.CoreV1Api()
    endpoints=v1.list_namespaced_endpoints(namespace,field_selector='metadata.name='+service_name)
    redis_port=0
    pods=[]
    if endpoints.items[0].subsets and endpoints.items[0].subsets!='None':
        redis_port=endpoints.items[0].subsets[0].ports[0].port
        pods=endpoints.items[0].subsets[0].addresses

    myip=get_myself_ip()
    myport=redis_conf['port']
    if 'requirepass' in redis_conf:
        redis_passwd=redis_conf['requirepass']
    else:
        redis_passwd=''
    #读取cluter.conf文件
    cluster_file=redis_conf['cluster-config-file']
    lines=''
    line_new=''
    if os.path.exists(cluster_file):
        conf=open(cluster_file, 'r+')
        lines=conf.read()
        line_new=lines

    #本脚本先于redis-server启动,判断本节点是否已加入集群
    if not os.path.exists(cluster_file) or (lines and len(lines.split('\n'))<4):
        print("%s [%s] %s" % (time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time())),'info','this node is not a part of cluster yet!'))
        #判断是否已存在集群
        clusters=[]
        cluster_exists=0
        if pods:
          for pod in pods:
            cluster_info=get_redis_cluster_info(pod.ip,redis_port,redis_passwd)
            if cluster_info['in_cluster']==1:cluster_exists=1
            clusters.append(cluster_info)
        print(clusters)
        if cluster_exists==1:
            print("%s [%s] %s" % (time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time())),'info','there is a redis cluster exists,do nothing'))
            return
        #判断当前是否最后一个启动的Pod
        v1b2=client.AppsV1beta2Api()
        st=v1b2.list_namespaced_stateful_set(namespace,field_selector='metadata.name='+st_name)
        if not st.items:
            print("%s [%s] %s" % (time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time())),'error',st_name+' not exists'))
            return
        replicas=st.items[0].spec.replicas
        current_replicas=st.items[0].status.current_replicas
        if current_replicas==replicas:
            print("%s [%s] %s" % (time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time())),'info','this pod is the last replica,begin create cluster!'))
            cluster_instances=[myip+':'+str(myport)]
            for pod in pods:
                if pod.ip+':'+str(redis_port) not in cluster_instances:cluster_instances.append(pod.ip+':'+str(redis_port))
            start_redis=os.system("echo 'daemonize yes' >> "+conf_file)
            start_redis=os.system('redis-server '+conf_file)
            rs=os.popen("echo 'yes'|redis-cli --cluster create --cluster-replicas 1 -a %s --no-auth-warning %s"%(redis_passwd,(' ').join(cluster_instances)))
            res=rs.read()
            print("%s [%s] %s" % (time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time())),'info',res))
            os.system('pkill redis-server')
            start_redis=os.system("echo 'daemonize no' >> "+conf_file)
        else:
            print("%s [%s] %s" % (time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time())),'info','this pod is not the last replica,do nothing!'))

        return


    redis_nodes=[]
    if myip:
      for line in lines.split('\n'):
        row=line.split(' ')
        if len(row)>7 and row[2].split(',')[0]=='myself':
            line_new=re.sub(row[0]+' '+row[1], row[0]+' '+myip+':'+str(myport)+'@'+row[1].split('@')[1], line_new)

    try:
      #把IP和Node_id对应起来
      print("%s [%s] %s" % (time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time())),'info',pods))

      if pods:
        for pod in pods:
          cluster_info=get_redis_cluster_info(pod.ip,redis_port,redis_passwd)
          if cluster_info:redis_nodes.append({'host':pod.ip,'port':redis_port,'node_id':cluster_info['node_id']})
        print("%s [%s] %s" % (time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time())),'info',redis_nodes))
        #根据node_id替换cluster.conf文件中的ip
        for line in lines.split('\n'):
          row=line.split(' ')
        
          for node in redis_nodes:
            if len(row)>7 and node['node_id']==row[0]:
                line_new=re.sub(row[0]+' '+row[1], row[0]+' '+node['host']+':'+str(node['port'])+'@'+row[1].split('@')[1], line_new)
    except Exception as e:
      print("%s [%s] %s" % (time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time())),'error',str(e)))


    #重写cluster.conf文件
    conf.seek(0)
    conf.truncate()
    conf.write(line_new)
    conf.close()

def get_myself_ip():
  try:
    rs=os.popen("ifconfig|grep 'inet addr'|grep -v '127.0.0.1'")
    res=rs.read()
    myip=res.strip().split(' ')[1].split(':')[1]
    return myip
  except Exception as e:
    print("%s [%s] %s" % (time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time())),'error','get myself ip error:'+str(e)))
    return None


def get_redis_conf(conf_path):
    conf=open(conf_path,'r')
    lines=conf.read()
    conf.close()
    redis_conf={}
    for line in lines.split('\n'):
        row=line.split(' ')
        if row[0].lower() in ['port','cluster-config-file','requirepass']:
            redis_conf[row[0]]=row[1]
    return redis_conf

def get_redis_cluster_info(host,port,password):
  try:
    rs=os.popen('redis-cli -h '+host+' -p '+str(port)+' -a '+str(password)+' --no-auth-warning cluster nodes|grep myself')
    res=rs.read()
    in_cluster=0
    role=''
    node_id=res.split(' ')[0]
    if 'slave' in res.split(' ')[2].split(','):role='slave'
    if 'master' in res.split(' ')[2].split(','):role='master'
    if 'slave' in res.split(' ')[2].split(',')  or len(res.split(' '))==9:in_cluster=1
    cluster_info={'ip':host,'port':port,'node_id':node_id,'in_cluster':in_cluster,'role':role}

    return cluster_info
  except Exception as e:
    print("%s [%s] %s" % (time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time())),'error','get redis node_id error:'+str(e)))
    return None

if __name__ == '__main__':
    update_cluster_config()
