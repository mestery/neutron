# Copyright (c) 2013-2014 OpenStack Foundation
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

from oslo.config import cfg

from neutron.common import constants as n_const
from neutron.extensions import portbindings
from neutron.openstack.common import log
from neutron.plugins.common import constants
from neutron.plugins.ml2 import driver_api as api
from odldrivers.ml2.mech_driver import OpenDaylightDriver

LOG = log.getLogger(__name__)

ODL_NETWORKS = 'networks'
ODL_SUBNETS = 'subnets'
ODL_PORTS = 'ports'

odl_opts = [
    cfg.StrOpt('url',
               help=_("HTTP URL of OpenDaylight REST interface.")),
    cfg.StrOpt('username',
               help=_("HTTP username for authentication")),
    cfg.StrOpt('password', secret=True,
               help=_("HTTP password for authentication")),
    cfg.IntOpt('timeout', default=10,
               help=_("HTTP timeout in seconds.")),
    cfg.IntOpt('session_timeout', default=30,
               help=_("Tomcat session timeout in minutes.")),
]

cfg.CONF.register_opts(odl_opts, "odl_rest")


class OpenDaylightMechanismDriver(api.MechanismDriver):

    """Mechanism Driver for OpenDaylight.

    This driver was a port from the Tail-F NCS MechanismDriver.  The API
    exposed by ODL is slightly different from the API exposed by NCS,
    but the general concepts are the same.
    """

    def initialize(self):
        self.url = cfg.CONF.odl_rest.url
        self.timeout = cfg.CONF.odl_rest.timeout
        self.username = cfg.CONF.odl_rest.username
        self.password = cfg.CONF.odl_rest.password
        required_opts = ('url', 'username', 'password')
        for opt in required_opts:
            if not getattr(self, opt):
                raise cfg.RequiredOptError(opt, 'odl_rest')
        self.vif_type = portbindings.VIF_TYPE_OVS
        self.vif_details = {portbindings.CAP_PORT_FILTER: True}
        self.odl_drv = OpenDaylightDriver.OpenDaylightDriver()

    # Postcommit hooks are used to trigger synchronization.

    def create_network_postcommit(self, context):
        self.odl_drv.synchronize('create', ODL_NETWORKS, context)

    def update_network_postcommit(self, context):
        self.odl_drv.synchronize('update', ODL_NETWORKS, context)

    def delete_network_postcommit(self, context):
        self.odl_drv.synchronize('delete', ODL_NETWORKS, context)

    def create_subnet_postcommit(self, context):
        self.odl_drv.synchronize('create', ODL_SUBNETS, context)

    def update_subnet_postcommit(self, context):
        self.odl_drv.synchronize('update', ODL_SUBNETS, context)

    def delete_subnet_postcommit(self, context):
        self.odl_drv.synchronize('delete', ODL_SUBNETS, context)

    def create_port_postcommit(self, context):
        self.odl_drv.synchronize('create', ODL_PORTS, context)

    def update_port_postcommit(self, context):
        self.odl_drv.synchronize('update', ODL_PORTS, context)

    def delete_port_postcommit(self, context):
        self.odl_drv.synchronize('delete', ODL_PORTS, context)

    def bind_port(self, context):
        LOG.debug("Attempting to bind port %(port)s on "
                  "network %(network)s",
                  {'port': context.current['id'],
                   'network': context.network.current['id']})
        for segment in context.network.network_segments:
            if self.check_segment(segment):
                context.set_binding(segment[api.ID],
                                    self.vif_type,
                                    self.vif_details,
                                    status=n_const.PORT_STATUS_ACTIVE)
                LOG.debug("Bound using segment: %s", segment)
                return
            else:
                LOG.debug("Refusing to bind port for segment ID %(id)s, "
                          "segment %(seg)s, phys net %(physnet)s, and "
                          "network type %(nettype)s",
                          {'id': segment[api.ID],
                           'seg': segment[api.SEGMENTATION_ID],
                           'physnet': segment[api.PHYSICAL_NETWORK],
                           'nettype': segment[api.NETWORK_TYPE]})

    def check_segment(self, segment):
        """Verify a segment is valid for the OpenDaylight MechanismDriver.

        Verify the requested segment is supported by ODL and return True or
        False to indicate this to callers.
        """
        network_type = segment[api.NETWORK_TYPE]
        return network_type in [constants.TYPE_LOCAL, constants.TYPE_GRE,
                                constants.TYPE_VXLAN, constants.TYPE_VLAN]
