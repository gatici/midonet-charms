ミドネット
==========

This repository contains Ubuntu Juju Charms to install MidoNet, the distributed virtual network controller for building a network overlay solution (NVO) with OpenStack.

For help with these charms you can visit our community slack channel, as a customer of MEM you can also open a support request.

The community channel is available here: http://slack.midonet.org/ .

Contributing
============

You can contribute to these charms by opening a pull request.

Please note that your charm should be tested by you with a full OpenStack installation performed by you, testing the following:

- installing OpenStack Juno on Ubuntu 14.04 with the latest MidoNet OSS version
- testing creation of at least one VM
- ping the internet without associating a floating IP to the VM
- create a L4 load balancer using at least 3 VMs with a http server as backends
- test the load balancer from outside
- associate a floating IP and ping from outside, log into the VM, do a wget to www.midokura.com and any other website
- use iperf to test connectivity to the VM and from the VM to an outside host

As soon as your PR gets through we will then QA the changed code on all supported MEM releases that can be installed with the MidoNet Juju Charm.

Neutron
=======

MidoNet contains a neutron plugin for OpenStack.

The network controller agent is using the kernel flow datapath from openvswitch-datapath.

No user-space components of OVS are used.

Background
==========

Please watch the following slide for an introduction to MidoNet:

http://www.slideshare.net/takufukushima79/introduction-to-mido-net

