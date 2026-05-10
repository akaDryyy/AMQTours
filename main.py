from flask import Flask, render_template, redirect, url_for, request, session, jsonify, make_response
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
import json 
from utils import get_elos, get_tourlist, get_mvps, get_changelog
app = Flask(__name__, template_folder="templates")

@app.get("/usual")
def usual():
    elos = get_elos("usual")
    tourlist = get_tourlist("usual")
    return render_template("tour.html", elos=elos, tourType="random", tourlist=tourlist, dryelo=False)

@app.get("/quagsual")
def quagsual():
    elos = get_elos("usual")
    tourlist = get_tourlist("usual")
    return render_template("tour.html", elos=elos, tourType="random 15s", tourlist=tourlist, dryelo=False)

@app.get("/watched")
def watched():
    folder = "watched_autoelo"
    elos = get_elos(folder)
    mvps = get_mvps(folder)
    changelog = get_changelog(folder)
    return render_template("tour.html", elos=elos, tourType="watched", mvps=mvps, changelog=changelog, dryelo=True)

@app.get("/random_op")
def random_op():
    folder = "op_autoelo"
    elos = get_elos(folder)
    mvps = get_mvps(folder)
    changelog = get_changelog(folder)
    return render_template("tour.html", elos=elos, tourType="random op", mvps=mvps, changelog=changelog, dryelo=True)

@app.get("/random_ed")
def random_ed():
    folder = "ed_autoelo"
    elos = get_elos(folder)
    mvps = get_mvps(folder)
    changelog = get_changelog(folder)
    return render_template("tour.html", elos=elos, tourType="random ed", mvps=mvps, changelog=changelog, dryelo=True)

@app.get("/random_in")
def random_in():
    folder = "in_autoelo"
    elos = get_elos(folder)
    mvps = get_mvps(folder)
    changelog = get_changelog(folder)
    return render_template("tour.html", elos=elos, tourType="random ins", mvps=mvps, changelog=changelog, dryelo=True)

@app.get("/random_cl")
def random_cl():
    folder = "cl-usual"
    elos = get_elos(folder)
    mvps = get_mvps(folder)
    changelog = get_changelog(folder)
    return render_template("tour.html", elos=elos, tourType="random cl", mvps=mvps, changelog=changelog, dryelo=True)

@app.get("/watched_in")
def watched_in():
    folder = "in_watched"
    elos = get_elos(folder)
    mvps = get_mvps(folder)
    changelog = get_changelog(folder)
    return render_template("tour.html", elos=elos, tourType="watched ins", mvps=mvps, changelog=changelog, dryelo=True)

@app.get("/watched_ed")
def watched_ed():
    folder = "ed_watched"
    elos = get_elos(folder)
    mvps = get_mvps(folder)
    changelog = get_changelog(folder)
    return render_template("tour.html", elos=elos, tourType="watched ed", mvps=mvps, changelog=changelog, dryelo=True)

@app.get("/watched_op")
def watched_op():
    folder = "op_watched"
    elos = get_elos(folder)
    mvps = get_mvps(folder)
    changelog = get_changelog(folder)
    return render_template("tour.html", elos=elos, tourType="watched op", mvps=mvps, changelog=changelog, dryelo=True)

@app.get("/watched_5s")
def watched_5s():
    folder = "5s"
    elos = get_elos(folder)
    tourlist = get_tourlist(folder)
    return render_template("tour.html", elos=elos, tourType="watched 5s", tourlist=tourlist, dryelo=False)

@app.get("/watched_2_8")
def watched_2_8():
    folder = "2+8"
    elos = get_elos(folder)
    tourlist = get_tourlist(folder)
    return render_template("tour.html", elos=elos, tourType="watched 2 8", tourlist=tourlist, dryelo=False)

@app.get("/watched_2009")
def watched_2009():
    folder = "x-2009"
    elos = get_elos(folder)
    tourlist = get_tourlist(folder)
    return render_template("tour.html", elos=elos, tourType="watched x-2009", tourlist=tourlist, dryelo=False)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3000, debug=True)

# 'flask --app main run' to run app.