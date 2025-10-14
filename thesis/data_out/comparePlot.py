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

# Data
algos = ["Reno", "CUBIC", "PULSE"]
loss_base = np.array([9.08, 9.44, 7.92]) * 10
loss_dbw = np.array([8.82, 9.33, 7.78]) * 10
ratios = loss_dbw / loss_base

x = np.arange(len(algos))
w = 0.35

fig, ax = plt.subplots(figsize=(6.4, 3.2))

bars1 = ax.bar(x - w / 2, loss_base, w, label="Baseline")
bars2 = ax.bar(x + w / 2, loss_dbw, w, label="Jitter")

ax.set_xticks(x)
ax.set_xticklabels(algos)
# ax.set_ylabel("RTT$_{mean}$ [ms]")
ax.set_ylabel("Utilization [%]")
ax.set_ylim(0, 100)
plt.tick_params(axis="both", which="major", labelsize=12)
plt.xlabel("t [s]", fontsize=12)
plt.ylabel("Utilization [%]", fontsize=12)
plt.tight_layout()
ax.grid(axis="y", alpha=0.2)
ax.legend(frameon=False)

# --- Annotate inside bars ---
for i, (bar, r) in enumerate(zip(bars2, ratios)):
    height = bar.get_height()
    ax.text(
        bar.get_x() + bar.get_width() / 2,
        height * 0.6,  # position at ~60% of bar height
        f"{r:.2f}×",
        ha="center",
        va="center",
        fontsize=9,
        color="white",
        fontweight="bold",
    )

plt.tight_layout()
plt.savefig("case_jitter_util.png", dpi=300, bbox_inches="tight")
plt.show()
