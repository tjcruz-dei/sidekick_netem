#!/bin/bash

# Copyright original version (c) 2015, Excentis nv
# All rights reserved.
#
# Original Author: Tim De Backer <tim.debacker@excentis.com>
#
# This script will configure the impairment node.
#
# It applies impairment configurations between two interfaces of a specified 'bypassX', by doing the following:
#   * Create a VLAN tagged interface on both interfaces (or work with the native interface if no VLAN is specified).
#   * Bridge the virtual interfaces with equal VLAN IDs on the two interfaces (or the interfaces themselves) together.
#   * Apply the specified configuration to the incoming traffic.
#
# If no configuration is specified, all impairment configurations are parsed from 'tc.conf'.
# If a configuration is specified, only that impairment is applied.
#
#Adapted for sideckick - this script initialized the interfaces + root QDISC
#

# Set the management interface of this impairment node
manif="eth2"

########################
### Input validation ###
########################

SCRIPTDIR=$(dirname $0)

# Test argument count
if test $# -lt 2; then
    echo "Error: Wrong number of arguments (2 to apply tc.conf or clear, 3 to apply explicit conf)"
    echo "  syntax: tc.sh apply <bridge0|1> [<impconf>]"
    echo "  syntax: tc.sh clear <bridge0|1>"
    exit 1
fi

# Saving argument values to variables
action=$1
shift
bypass=$1
shift

# Test if known action
if test "$action" != "apply" -a "$action" != "clear" ; then
    echo "Error: Invalid arguments, action '$action' unknown"
    echo "  syntax: tc.sh apply <bridge|1> [<impconf>]"
    echo "  syntax: tc.sh clear <bridge|1>"
    exit 1
fi

# Test if known bypass
if test "$bypass" = "bridge0"; then
    ifds="eth0"
    ifus="eth1"
elif test "$bypass" = "bridge1"; then
    ifds="eth2"
    ifus="eth3"
else
    echo "Error: Invalid arguments, bypass '$bypass' unknown"
    echo "  syntax: tc.sh apply <bridge0|1> [<impconf>]"
    echo "  syntax: tc.sh clear <bridge0|1>"
    exit 1
fi

# Test if running as root
if test $UID -ne 0 ; then
    echo "Error: This script should be executed as a superuser"
    exit 1
fi

#######################################
### Clear impairment configuration  ###
#######################################

echo "Clearing previous configuration"

echo -n " - Removing all $bypass bridges..."
bridges=`ifconfig -a | grep -E "^bridge" | cut --delimiter=':'  -f1`
for bridge in $bridges
do
    echo $bridge
    ifconfig $bridge down
    brctl delbr $bridge >/dev/null 2>&1
done
echo "done"

echo -n " - Removing all existing impairment configurations on the (virtual) $bypass interfaces..."
interfaces=`ifconfig -a | grep -E "^(${ifds}|${ifus})" | cut --delimiter=' ' -f1`
for interface in $interfaces
do
    tc qdisc del dev $interface root >/dev/null 2>&1
done
echo "done"

echo -n " - Removing all virtual interfaces on the $bypass interfaces..."
vinterfaces=`ifconfig -a | grep -E "^({ifds}|{ifus})\." | cut --delimiter=':' -f1`
for vinterface in $vinterfaces
do
    ifconfig $vinterface down
    vconfig rem $vinterface >/dev/null >/dev/null 2>&1
done
echo "done"

echo -n " - Removing default (non-virtual) $bypass bridge..."
ifconfig $bypass down >/dev/null 2>&1
brctl delbr bypass0 >/dev/null 2>&1
echo "done"

echo -n " - Bringing $bypass interfaces down..."
ifconfig $ifds down >/dev/null 2>&1
ifconfig $ifus down >/dev/null 2>&1
echo "done"

if test "$action" = "clear" ; then
    echo -n "Restarting network..."
    /etc/init.d/networking restart >/dev/null
    echo "done"
    exit 0
fi

########################################
### Create impairment configuration  ###
########################################

echo -n "Creating ethernet bridge..."
brctl addbr $bypass
brctl addif $bypass $ifds
brctl addif $bypass $ifus
brctl setfd $bypass 0
brctl sethello $bypass 2
brctl setmaxage $bypass 12
brctl stp $bypass off
echo "done"

ethtool -K eth0 gso off
ethtool -K eth0 tso off
ethtool -K eth0 gro off
ethtool -K eth1 gso off
ethtool -K eth1 tso off
ethtool -K eth1 gro off

echo -n "Bringing default (non-virtual) $bypass bridge online..."
ifconfig $ifds up
ifconfig $ifus up
ifconfig $bypass up
echo "done"

#EXPERIMENTAL - TJC
ethtool -G eth0 rx 512
ethtool -G eth0 rx-mini 1024
ethtool -G eth0 tx 512
ethtool -G eth1 rx 512
ethtool -G eth1 rx-mini 1024
ethtool -G eth1 tx 512
ethtool -C eth0 rx-frames 0
ethtool -C eth1 rx-frames 0
ifconfig eth0 txqueuelen 1
ifconfig eth1 txqueuelen 1
ifconfig bridge0 txqueuelen 100

echo -n "    * Constructing root handler..."
    tc qdisc add dev eth0 root handle 1: htb
    tc qdisc add dev eth1 root handle 1: htb 

    #NAO MEXER AQUI !!!! QDISC RAIZ
    echo "A"
    tc class add dev eth0 parent 1: classid 1:1 htb rate 500Mbit ceil 500Mbit burst 0 cburst 1500 quantum 1500
    tc class add dev eth1 parent 1: classid 1:1 htb rate 500Mbit ceil 500Mbit burst 0 cburst 1500 quantum 1500

    #AJUSTAR LARGURA DE BANDA AQUI
    #colocar o mesmo valor em rate e burst, para os dois casos
    #echo "B"
    #tc class add dev eth0 parent 1:1 classid 1:10 htb rate 5000kbit ceil 5000kbit burst 0 prio 0
    #tc class add dev eth1 parent 1:1 classid 1:10 htb rate 5000kbit ceil 5000kbit burst 0 prio 0

    #para valores pequenos reduzir limit - NOTA: BxL product rules
    #como ajustar o limit:
    #para testes com 100kbit/s, multiplicar  8,3 por latencia e por 1.5
    #para testes com 500kbit/s, multiplicar  41,6 por latencia e por 1.5
    #para testes com bw 1Mbit/s, multiplicar 83,3 por latencia e por 1.5
    #
    #limit  calculado pela formula (bw/MTU) * latencia * 1.5
    #
    #ex: 1Gbit/s, 100ms latencia
    #1 Gbps / 1500 bytes MTU * 100 ms * 1.5

    #echo "D"
    #tc qdisc add dev eth0 parent 1:10 handle 21: netem delay 0ms loss 0.0% limit 32
    #tc qdisc add dev eth1 parent 1:10 handle 21: netem delay 0ms loss 0.0% limit 32

    #NAO ESQUECER DE MUDAR O IP!!!
    #echo "F - Client to S 40M"
    #antes estava o 1.13 na primeira linha
    #tc filter add dev eth0 protocol ip parent 1:0 prio 0 u32 match ip dst 192.168.2.10/32 flowid 1:10
    #tc filter add dev eth0 protocol ip parent 1:0 prio 0 u32 match ip dst 192.168.1.10/32 flowid 1:10

    #echo "S to Client 1G"
    #antes estava o 1.13 na primeira linha
    #tc filter add dev eth1 protocol ip parent 1:0 prio 0 u32 match ip src 192.168.2.10/32 flowid 1:10
    #tc filter add dev eth1 protocol ip parent 1:0 prio 0 u32 match ip src 192.168.1.10/32 flowid 1:10
    #echo "done-G"


echo -n "Restarting network..."
/etc/init.d/networking restart >/dev/null
ifconfig eth2 up
dhclient eth2
echo "done"

exit 0
