import matplotlib.pyplot as plt

months = ['September 2026', 'October 2026']
turnover = [41589.04, 21823.10]
gst = [2079.45, 1091.16]

fig, ax1 = plt.subplots(figsize=(8, 5))

color = 'tab:blue'
ax1.set_xlabel('Month', fontweight='bold', fontsize=12)
ax1.set_ylabel('Taxable Turnover (₹)', color=color, fontweight='bold', fontsize=12)
bars = ax1.bar(months, turnover, color=['#3b82f6', '#60a5fa'], width=0.4, alpha=0.85, label='Turnover')
ax1.tick_params(axis='y', labelcolor=color)
ax1.grid(axis='y', linestyle='--', alpha=0.5)

for bar in bars:
    yval = bar.get_height()
    ax1.text(bar.get_x() + bar.get_width()/2.0, yval + 1000, f'₹{yval:,.2f}', ha='center', va='bottom', fontweight='bold', color='#1e3a8a')

ax2 = ax1.twinx()  
color = 'tab:orange'
ax2.set_ylabel('Total GST 5% (₹)', color=color, fontweight='bold', fontsize=12)
ax2.plot(months, gst, color='#f97316', marker='o', linewidth=3, markersize=8, label='GST 5%')
ax2.tick_params(axis='y', labelcolor=color)

for i, txt in enumerate(gst):
    ax2.annotate(f'₹{txt:,.2f}', (months[i], gst[i]), textcoords="offset points", xytext=(0,10), ha='center', fontweight='bold', color='#c2410c')

plt.title('Sri Ganapathi Colours — Monthly Turnover & 5% GST Audit Radar', fontsize=14, fontweight='bold', pad=20)
fig.tight_layout()

output_path = r'C:\Users\mukil\Desktop\SGC_GST_Audit_Infographic.png'
plt.savefig(output_path, dpi=300)
print(f"Infographic successfully saved to {output_path}")
