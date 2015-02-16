#
# Copyright (c) 2015 Midokura SARL, All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
#!/usr/bin/python
import re
import os
import sys
import setup
import shutil
import socket
import subprocess
import time

from charmhelpers.core import hookenv
from charmhelpers.core import host

def create_puppet_node(zks, cass, os_ver, max_h, new_h):
    host_name = subprocess.check_output(["hostname"])
    host_name = host_name.strip()
    fd = open("node.pp","w")
    node_def = """
node %s {\n
    midolman::install {"%s":\n
        openstack_version => "%s"\n
    }\n
    ->\n
    midolman::configure {"%s":\n
        zookeepers => "%s",\n
        cassandras => "%s",\n
        max_heap_size => "%d",\n
        heap_newsize => "%d"\n
    }\n
    ->\n
    midolman::start {"%s":\n
    }\n
}\n
""" %(host_name,
      host_name,
      os_ver,
      host_name,
      zks,
      cass,
      max_h,
      new_h,
      host_name)
    fd.write("%s" % node_def)
    fd.close()

def install_midonet_agent():
    config = hookenv.config()
    zookeepers = []
    cassandras = []
    # create temparoty directory midonet
    os.makedirs("/tmp/midonet", 0755)
    os.chdir("/tmp/midonet")
    host_name =  subprocess.check_output("hostname", shell=True)
    host_ip = socket.gethostbyname(host_name.strip())
    # make list of zookeeeper server ips
    hostips = config['zookeeper_hosts']
    ips = list(hostips.split(' '))
    for ip in sorted(ips):
        zookeepers.append("%s" %str(ip))
    hostips = config['cassandra_hosts']
    ips = list(hostips.split(' '))
    # make a list of cassandra servers ips
    for ip in sorted(ips):
        cassandras.append("%s" %str(ip))
    openstack_version = config['openstack_release']
    max_heap_size = config['max_heap_size']
    heap_newsize = config['heap_newsize']
    # create node.pp for midonet-agent  
    node_path = create_puppet_node(zookeepers,
                                   cassandras,
                                   openstack_version,
                                   max_heap_size,
                                   heap_newsize)
   
    repo = config['midonet_puppet_modules']
    branch = config['midonet_puppet_modules_branch']
    git_cmd = "sudo git clone %s --branch %s" %(repo, branch)
    subprocess.check_output(git_cmd, shell=True)
    MODULEPATH = os.getcwd()+'/orizuru/puppet/modules'
    PUPPET_NODE_DEFINITION = os.getcwd()+'/node.pp'
    # execute the puppet apply command
    command = "sudo puppet apply --verbose --show_diff --modulepath=%s %s" %(MODULEPATH, PUPPET_NODE_DEFINITION)
    output = subprocess.call(command, shell=True)
    time.sleep(10) 
    os.chdir("/tmp")
    # deletetemparoty directory midonet
    shutil.rmtree("midonet")
    cmd = """"
for i in $(seq 1 12); do\n
    ps axufwwwwwwwwwwwww | grep -v grep | grep 'openjdk' | \
    grep '/etc/midolman/midolman.conf' && break || true\n
    sleep 1\n
done\n
"""
    output = subprocess.check_output(cmd, shell=True)
    cmd = """
ps axufwwwwwwwwwwwww | grep -v grep | grep 'openjdk' | "\
    grep '/etc/midolman/midolman.conf'"""
    output = subprocess.check_output(cmd, shell=True)

    cmd = "chmod 0777 /var/run/screen"
    output = subprocess.check_output(cmd, shell=True)
    cmd_dir = "mkdir -pv /etc/rc.local.d"
    output = subprocess.check_output(cmd_dir, shell=True)

    f = open("/etc/rc.local.d/midolman","w")
    str_file = "while(true); do"
    f.write("str_file\n")
    str_file = "    ps axufwwwwwwwwwwwww | grep -v grep | grep 'openjdk' \
| grep '/etc/midolman/midolman.conf' || /usr/share/midolman/midolman-start"
    f.write("str_file\n")
    str_file = "    sleep 10\n"
    f.write("str_file")
    str_file = "done\n"
    f.write("str_file")
    f.close()

    cmd_chmod = "chmod 0755 /etc/rc.local.d/midolman"
    output = subprocess.check_output(cmd_chmod, shell=True) 
    
    cmd = "screen -S midolman -d -m -- /etc/rc.local.d/midolman"
    output = subprocess.check_output(cmd, shell=True) 
   
    cmd = """"
for i in $(seq 1 24); do\n
    ps axufwwwwwwwwwwwww | grep -v grep | grep 'openjdk' | "\
    grep '/etc/midolman/midolman.conf' && break || true\n
    sleep 1\n
done\n
"""
    output = subprocess.check_output(cmd, shell=True)

    cmd = "ps axufwwwwwwwwwwwww | grep -v grep | grep 'openjdk' | "
    cmd = cmd + "grep '/etc/midolman/midolman.conf'"
    output = subprocess.check_output(cmd, shell=True)
 

