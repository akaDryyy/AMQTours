from flask import Flask, render_template, redirect, url_for, request, session, jsonify, make_response
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
from tools.usual import NGMsolverusual, eloscrape
import json 
import threading

app = Flask(__name__, template_folder="templates")

def get_elos():
    with open("./tools/usual/elos.json") as f:
     content = f.read()
     return json.loads(content)

def get_tourlist():
    with open("./tools/usual/tourlist.txt") as f:
     return f.read()
    
def get_ranks():
   with open("./tools/usual/ranks.txt") as f:
      return f.read()
   
def get_aliases():
   with open("./tools/aliases.txt") as f:
      return f.read()
   
def get_codes():
   with open("./tools/usual/codes.txt") as f:
      return f.read()
   
def add_to_tourlist(tour):
   with open("./tools/usual/tourlist.txt", "a") as f:
    f.write(tour)

def add_players(players):
   with open("./tools/usual/players.txt", "w") as f:
          f.write(players)

def run_solver(players):
    add_players(players)
    NGMsolverusual.main()

@app.get("/")
def main():
    elos = get_elos()
    tourlist = get_tourlist()
    ranks = get_ranks()
    return render_template("menu.html", elos=elos, tourlist=tourlist, ranks=ranks)

@app.route("/codes", methods = ["GET", "POST"])
def codes():
    action = request.form.get('action')
    codes = ""
    if action == "start_tour":
       players = request.form.get('players')
       print(players)
       threading.Thread(target=run_solver, args=(players,)).start()
       return "Solver started! Check back later for codes."
    else:
       return render_template("codes.html", codes=codes)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3000, debug=True)

# 'flask --app main run' to run app.