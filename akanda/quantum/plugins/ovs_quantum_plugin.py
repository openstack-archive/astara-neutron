from quantum.plugins.openvswitch import ovs_quantum_plugin

from akanda.quantum.db import models_v2

class OVSQuantumPluginV2(ovs_quantum_plugin.OVSQuantumPluginV2):
    supported_extension_aliases = (
        ovs_quantum_plugin.OVSQuantumPluginV2.supported_extension_aliases +
        ["dhportforward", "dhaddressgroup", "dhaddressentry",
         "dhfilterrule", "dhportalias"])
