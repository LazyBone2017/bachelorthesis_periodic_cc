import matplotlib.pyplot as plt

algos = ["Reno", "CUBIC", "PULSE"]
ratios = [0.34/0.13, 0.52/0.19, 0.83/0.35]  # ≈ [2.6, 2.7, 2.4]

plt.bar(algos, ratios, color="#F79646")
plt.ylabel("Relative Loss Increase (×)")
plt.ylim(0, 3)
plt.title("Loss Increase with Doubled Bandwidth")
plt.grid(axis="y", alpha=0.3)

# annotate each bar
for i, v in enumerate(ratios):
    plt.text(i, v + 0.05, f"{v:.1f}×", ha="center", fontweight="bold")

plt.tight_layout()
plt.show()
