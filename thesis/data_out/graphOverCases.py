import matplotlib.pyplot as plt
from matplotlib.rcsetup import cycler
import numpy as np

okabe_ito = [
    "#E69F00",  # orange
    "#56B4E9",  # sky blue
    "#009E73",  # bluish green
    "#F0E442",  # yellow
    "#0072B2",  # blue
    "#D55E00",  # vermillion
    "#CC79A7",  # reddish purple
    "#000000",  # black (optional)
]

# Set as global default
plt.rcParams["axes.prop_cycle"] = cycler(color=okabe_ito)

# HIGH RTT, RTTMEAN
data = {
    100: np.array(
        [
            110.6796946278419,
            110.98786869512804,
            110.70071662044327,
            110.62488500286493,
            110.33179634561316,
        ]
    )
    - 100,
    200: np.array(
        [
            221.98322038606017,
            219.21380792773965,
            220.68313867408062,
            220.41306100842237,
            220.74744417267254,
        ]
    )
    - 200,
    400: np.array(
        [
            434.69726386354006,
            438.0308251817372,
            437.42703145452293,
            437.3618546427072,
            436.88838337315246,
        ]
    )
    - 400,
}


# High RTT, goodput
"""data = {
    100: np.array(
        [
            7.305524710061268,
            7.3247542931803284,
            7.283063366091212,
            7.283320610885442,
            7.288377542033207,
        ]
    )
    * 10,
    200: np.array(
        [
            7.141139393434757,
            7.143108443765285,
            7.162704524049044,
            7.15380072359244,
            7.163409550537075,
        ]
    )
    * 10,
    400: np.array(
        [
            6.874013443607648,
            6.870357067501481,
            6.873187256861119,
            6.855425116913643,
            6.854632670488486,
        ]
    )
    * 10,
}"""
# data = {0: [11.46], 1: [5.82], 3: [4.83], 5: [4.35]}

jitter = np.array(sorted(data.keys()))
mean_util = np.array([np.mean(data[j]) for j in jitter])
std_util = np.array([np.std(data[j]) for j in jitter])
fig, ax = plt.subplots(figsize=(6.4, 3.2))
ax.plot(jitter, mean_util, marker="o", lw=2.2)
ax.fill_between(jitter, mean_util - std_util, mean_util + std_util, alpha=0.2)

ax.set_ylim(7, 40)
plt.tick_params(axis="both", which="major", labelsize=12)
plt.xlabel("Prop. RTT [ms]", fontsize=12)
plt.ylabel("Excess RTT$_{mean}$ [ms]", fontsize=12)
ax.grid(True, alpha=0.2)
# ax.legend(frameon=False)
plt.tight_layout()
plt.savefig("pulse_only_prop_rtt", dpi=300, bbox_inches="tight")
plt.show()
