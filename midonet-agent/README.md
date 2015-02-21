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

This charm will install the midonet java agent.
All installed agents work as the distributed flow simulator.
Each agent requires access to the zookeeper and cassandra servers.
Topology information and host NIC bindings are stored in zookeeper.
Cassandra can be used as a secondary storage for L4 and NAT state.

Usage
=====
    juju deploy midonet-zookeeper
    juju deploy midnet-cassandra
    juju deploy midonet-agent
    juju add-relation midonet-agent midonet-zookeeper
    juju add-relation midonet-agent midonet-cassandra

