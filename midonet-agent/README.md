Copyright (c) 2015 Midokura SARL, All Rights Reserved.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

   http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.


Overview
========

This charm provides midonet-agent along with open jdk7.
Midonet-agent designed work with openvswitch kernal version 1.10.2 or later
Requires specify the zookeeper and casssandra IP addresses in the 
midolman configuration file 

Before deploying the midonet-cassandra make sure you already deployed
midonet-repository juju charm in order to all the neccessary repositories
for ubuntu.

Requires the zookeeper and cassandra relations

Usage
=====
    juju deploy midonet-agent
    juju add-relation midonet-agent midonet-zookeeper
    juju add-relation midonet-agent midonet-cassandra

   

Note:
=====
    Please makesure that you already installed the zookeeeper and
    cassandra using below 
    juju deploy midonet-zookeeper
    juju deploy midonet-cassandra

    if you didnt deploy midonet-repositoy please run the below
    juju deploy midonet-repository
 
