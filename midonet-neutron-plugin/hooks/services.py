#!/usr/bin/python
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
from charmhelpers.core.services.base import ServiceManager
from charmhelpers.core.services import helpers

import actions


def manage():
    manager = ServiceManager([
        {
            'service': 'midonet-neutron-plugin',
            'ports': [],  # ports to after start
            'provided_data': [
                # context managers for provided relations
                # e.g.: helpers.HttpRelation()
            ],
            'required_data': [
                # data (contexts) required to start the service
                # e.g.: helpers.RequiredConfig('domain', 'auth_key'),
                #       helpers.MysqlRelation(),
            ],
            'data_ready': [
                helpers.render_template(
                    source='upstart.conf',
                    target='/etc/init/midonet-neutron-plugin'),
                actions.log_start,
            ],
        },
    ])
    manager.manage()
