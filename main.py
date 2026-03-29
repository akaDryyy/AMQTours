from flask import Flask, render_template, redirect, url_for, request, session, jsonify, make_response
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
import json 

app = Flask(__name__, template_folder="templates")

def get_elos(folder):
    with open(f"./{folder}/elos.json") as f:
     content = f.read()
     return json.loads(content)

def get_mvps(folder):
    with open(f"./{folder}/mvps.txt", encoding="utf-8") as f:
     content = f.read()
     return content

def get_changelog(folder):
    with open(f"./{folder}/changelog.txt", encoding="utf-8") as f:
     content = f.read()
     return content

def get_tourlist(folder):
    with open(f"./{folder}/tourlist.txt", encoding="utf-8") as f:
     return f.read()

@app.get("/usual")
def usual():
    elos = get_elos("usual")
    tourlist = get_tourlist("usual")
    return render_template("tour.html", elos=elos, tourType="random", tourlist=tourlist)

@app.get("/quagsual")
def quagsual():
    elos = get_elos("usual")
    tourlist = get_tourlist("usual")
    return render_template("tour.html", elos=elos, tourType="random 15s", tourlist=tourlist)

@app.get("/watched")
def watched():
    folder = "watched_autoelo"
    elos = get_elos(folder)
    mvps = get_mvps(folder)
    changelog = get_changelog(folder)
    return render_template("tour.html", elos=elos, tourType="watched", mvps=mvps, changelog=changelog)

@app.get("/random_op")
def random_op():
    folder = "op_autoelo"
    elos = get_elos(folder)
    mvps = get_mvps(folder)
    changelog = get_changelog(folder)
    return render_template("tour.html", elos=elos, tourType="random op", mvps=mvps, changelog=changelog)

@app.get("/random_ed")
def random_ed():
    folder = "ed_autoelo"
    elos = get_elos(folder)
    mvps = get_mvps(folder)
    changelog = get_changelog(folder)
    return render_template("tour.html", elos=elos, tourType="random ed", mvps=mvps, changelog=changelog)

@app.get("/random_in")
def random_in():
    folder = "in_autoelo"
    elos = get_elos(folder)
    mvps = get_mvps(folder)
    changelog = get_changelog(folder)
    return render_template("tour.html", elos=elos, tourType="random ins", mvps=mvps, changelog=changelog)

@app.get("/random_cl")
def random_cl():
    folder = "cl-usual"
    elos = get_elos(folder)
    mvps = get_mvps(folder)
    changelog = get_changelog(folder)
    return render_template("tour.html", elos=elos, tourType="random cl", mvps=mvps, changelog=changelog)

@app.get("/watched_in")
def watched_in():
    folder = "in_watched"
    elos = get_elos(folder)
    mvps = get_mvps(folder)
    changelog = get_changelog(folder)
    return render_template("tour.html", elos=elos, tourType="watched ins", mvps=mvps, changelog=changelog)

@app.get("/watched_5s")
def watched_5s():
    elos = get_elos("5s")
    tourlist = get_tourlist("5s")
    return render_template("tour.html", elos=elos, tourType="watched 5s", tourlist=tourlist)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3000, debug=True)

# 'flask --app main run' to run app.