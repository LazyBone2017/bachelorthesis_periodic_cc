#!/bin/bash

set -e

CMD=$1
RTT=$2
JITTER=$3
LOSS=$4
RATE=$5
LIMIT0=$6
LIMIT1=$7

NS1=ns1
NS2=ns2
VETH1=veth1
VETH2=veth2
IP1=10.0.0.1
IP2=10.0.0.2


function setup() {
    
    RTT_VAL=${RTT%ms}
    HALF=$(($RTT_VAL / 2))
    ONE_WAY_DELAY="${HALF}ms"

    ip netns add $NS1
    ip netns add $NS2

    ip link add $VETH1 type veth peer name $VETH2

    ip link set $VETH1 netns $NS1
    ip link set $VETH2 netns $NS2

    ip netns exec $NS1 ip addr add $IP1/24 dev $VETH1
    ip netns exec $NS2 ip addr add $IP2/24 dev $VETH2
    ip netns exec $NS1 ip link set lo up
    ip netns exec $NS2 ip link set lo up
    ip netns exec $NS1 ip link set $VETH1 up
    ip netns exec $NS2 ip link set $VETH2 up

    echo "Set Traffic Control: RTT=$RTT, jitter=$JITTER, loss=$LOSS, rate=$RATE"

    ip netns exec $NS1 tc qdisc add dev $VETH1 root netem delay $ONE_WAY_DELAY $JITTER loss $LOSS rate $RATE limit $LIMIT0
    ip netns exec $NS2 tc qdisc add dev $VETH2 root netem delay $ONE_WAY_DELAY $JITTER loss $LOSS rate $RATE limit $LIMIT1

    echo "Setup successful"
    echo "Run your server: server_start.sh"
    echo "Run your client: ui_start.sh <CONFIG>"
}

function cleanup() {
    echo "Cleaning up namespaces and veths"
    ip netns del $NS1 2>/dev/null || true
    ip netns del $NS2 2>/dev/null || true

    ip link del $VETH1 2>/dev/null || true
    ip link del $VETH2 2>/dev/null || true

    echo "Cleaned up"
}

case "$CMD" in
    setup)
        setup
        ;;
    cleanup)
        cleanup
        ;;
    *)
        echo "Unknown command; Usage: sudo ./network_setup.sh [setup|cleanup] [RTT] [jitter] [loss] [rate] [lim_data] [lim_ack]"
        echo "Example:"
        echo "  sudo ./netns_sim.sh setup 100ms 0ms 1% 10mbit 100 100"
        echo "  sudo ./netns_sim.sh cleanup"
        exit 1
        ;;
esac
