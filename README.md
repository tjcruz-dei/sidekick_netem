# sidekick_netem
Sidekick tool for experiment control using netem and transparent bridge VMs

##Capabilities
The sidekick tool was written for the purpose of introducing communications-related disturbances in a controlled way, to test/evaluate the performance and robustness of communications protocols, APIs or services.  The fundamental operation model for this tool is presented on the next figure.

A Network Emulator bridge based on a Linux virtual appliance provides the means to constrain/disturb the traffic between communicating peers on different network segments, in a transparent way. This appliance is configured with three network interfaces: two for the transparent bridge and one for out-of-band experiment control. Network traffic shaping capabilities are provided by the native Linux TC and Netem subsystems, to constrain bandwidth or inject disturbances such as packet losses, jitter, or latency. 
To deal with the integration of these capabilities within a fault injection framework, the sidekick agent provides remote control of the traffic shaper, for integrated experiment management purposes. This tool provides the following capabilities:

The tool provides the following capabilities:
* Remote scheduling for time-triggered network shaper profile activation
* Integration with standard MQTT brokers
* Easy-to-use JSON profile configuration file
* Can operate in foreground or in daemonized/background mode
* Trigger precision around 0.02s, on average (for overall system load <20%)

## Important remarks

The tools is provided 'as-is', with no guarantees of any sort. Tested with a kali linux 2021.1 distro (kernel Debian 5.10.13-1kali1".
