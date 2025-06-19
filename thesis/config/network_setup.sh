#!/bin/bash

set -e

CMD=$1
DELAY=${2:-100ms}
LOSS=${3:-1%}
RATE=${4:-5mbit}

NS1=ns1
NS2=ns2
VETH1=veth1
VETH2=veth2
IP1=10.0.0.1
IP2=10.0.0.2

function setup() {
    echo "[+] Creating namespaces $NS1 and $NS2..."
    ip netns add $NS1
    ip netns add $NS2

    echo "[+] Creating veth pair $VETH1 <-> $VETH2..."
    ip link add $VETH1 type veth peer name $VETH2

    echo "[+] Moving veth interfaces to namespaces..."
    ip link set $VETH1 netns $NS1
    ip link set $VETH2 netns $NS2

    echo "[+] Configuring interfaces and routes..."
    ip netns exec $NS1 ip addr add $IP1/24 dev $VETH1
    ip netns exec $NS2 ip addr add $IP2/24 dev $VETH2
    ip netns exec $NS1 ip link set lo up
    ip netns exec $NS2 ip link set lo up
    ip netns exec $NS1 ip link set $VETH1 up
    ip netns exec $NS2 ip link set $VETH2 up
    ip netns exec $NS1 ip route add default via $IP2 dev $VETH1
    ip netns exec $NS2 ip route add default via $IP1 dev $VETH2

    echo "[+] Applying traffic control: delay=$DELAY, loss=$LOSS, rate=$RATE"
    ip netns exec $NS1 tc qdisc add dev $VETH1 root netem delay $DELAY loss $LOSS rate $RATE
    ip netns exec $NS2 tc qdisc add dev $VETH2 root netem delay $DELAY loss $LOSS rate $RATE


    echo ""
    echo "[✓] Setup complete"
    echo "Run your server in ns2:"
    echo "  sudo ip netns exec $NS2 python3 server.py"
    echo "Run your client in ns1:"
    echo "  sudo ip netns exec $NS1 python3 client.py"
}

function cleanup() {
    echo "[+] Cleaning up namespaces and veths..."
    ip netns del $NS1 2>/dev/null || true
    ip netns del $NS2 2>/dev/null || true
    ip link del $VETH1 2>/dev/null || true
    echo "[✓] Cleaned up"
}

case "$CMD" in
    setup)
        setup
        ;;
    cleanup)
        cleanup
        ;;
    *)
        echo "Usage: sudo ./netns_sim.sh [setup|cleanup] [delay] [loss] [rate]"
        echo "Example:"
        echo "  sudo ./netns_sim.sh setup 100ms 1% 5mbit"
        echo "  sudo ./netns_sim.sh cleanup"
        exit 1
        ;;
esac
