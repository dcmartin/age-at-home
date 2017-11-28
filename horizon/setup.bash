wget -qO - http://pkg.bluehorizon.network/bluehorizon.network-public.key | apt-key add -

cat <<EOF > /etc/apt/sources.list.d/bluehorizon.list
deb [arch=amd64] http://pkg.bluehorizon.network/linux/ubuntu xenial-testing main
deb-src [arch=amd64] http://pkg.bluehorizon.network/linux/ubuntu xenial-testing main
EOF

apt-get update

apt-get install -y horizon bluehorizon bluehorizon-ui

cat <<'EOF' > /etc/rsyslog.d/10-horizon-docker.conf
$template DynamicWorkloadFile,"/var/log/workload/%syslogtag:R,ERE,1,DFLT:.*workload-([^\[]+)--end%.log"

:syslogtag, startswith, "workload-" -?DynamicWorkloadFile
& stop
:syslogtag, startswith, "docker/" -/var/log/docker_containers.log
& stop
:syslogtag, startswith, "docker" -/var/log/docker.log
& stop
EOF
service rsyslog restart

mkdir -p /var/horizon/reg/microservice;
mkdir -p /var/horizon/reg/workload;
mkdir -p /var/horizon/reg/examples;
cd /var/horizon/reg;
find . ! -name env_vars -type f -exec rm -f {} +;
wget -i https://raw.githubusercontent.com/linggao/horizon-utils/master/reg/filelist.txt;
wget -i https://raw.githubusercontent.com/linggao/horizon-utils/master/reg/microservice/filelist.txt -P microservice/
wget -i https://raw.githubusercontent.com/linggao/horizon-utils/master/reg/workload/filelist.txt -P workload/
wget -i https://raw.githubusercontent.com/linggao/horizon-utils/master/reg/examples/filelist.txt -P examples/
wget https://raw.githubusercontent.com/linggao/horizon-utils/master/update_horizon;
chmod +x reg_all rereg update_horizon;
ln -sf /var/horizon/reg/reg_all /usr/local/sbin;
ln -sf /var/horizon/reg/rereg /usr/local/sbin;
ln -sf /var/horizon/reg/update_horizon /usr/local/sbin
