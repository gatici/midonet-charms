#!/usr/bin/env python
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

import sys
import mock
import unittest
from pkg_resources import resource_filename

# allow importing actions from the hooks directory
sys.path.append(resource_filename(__name__, '../hooks'))
import actions


class TestActions(unittest.TestCase):
    @mock.patch('charmhelpers.core.hookenv.log')
    def test_log_start(self, log):
        actions.log_start('test-service')
        log.assert_called_once_with('midonet-cassandra starting')


if __name__ == '__main__':
    unittest.main()