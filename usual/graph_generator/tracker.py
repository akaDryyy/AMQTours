import os, json, re
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator
from datetime import datetime

elo_history_path = os.path.abspath(os.path.join(os.pardir, "elo_history.json"))
player_name = input("Enter player name: ")

with open(elo_history_path, "r") as f:
    elo_history = json.load(f)

dates = []
elos = []
first_flag = True
for tour in elo_history:
    date = tour["time"]
    for player, elo in tour["player"].items():
        if player.lower() == player_name.lower():
            numbers = re.findall(r'-?\d+\.\d+', elo)
            if first_flag:
                elos.append(numbers[0])
                dates.append(date)
                first_flag = False
            elos.append(numbers[1])
            dates.append(date)

dates = [datetime.fromisoformat(d).replace(tzinfo=None).date() for d in dates]

plt.figure(figsize=(10, 5))
plt.plot(dates, elos, marker='o')

plt.gca().yaxis.set_major_locator(MaxNLocator(nbins=25,  prune=None))


plt.title(f"{player_name}'s ELO Over Time")
plt.xlabel("Date")
plt.ylabel("Elo")
plt.gcf().autofmt_xdate()
plt.tight_layout()
plt.show()