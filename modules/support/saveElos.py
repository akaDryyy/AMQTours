from modules.support.readCredentials import readCredentials
import os
import json

def saveElos(directory, sheetID, sheetName, cell, elos_path, tourlist_path=None, tourlist_cell=None, backlog_path=None, backlog_cell=None):
    gc = readCredentials(directory)
    sheet = gc.open(sheetName)
    wks = sheet.get_worksheet_by_id(sheetID)

    with open(elos_path) as f:
        data = f.read()
        wks.update_acell(cell, data)

    if backlog_path and backlog_cell:
        with open(backlog_path) as f:
            backlog_data = f.read()
            wks.update_acell(backlog_cell, backlog_data)

    if tourlist_path and tourlist_cell:
        with open(os.path.join(directory, "tourlist.txt")) as t:
            tourlist_data = t.read()
            wks.update_acell(tourlist_cell, tourlist_data)

def save_composite_dict_to_json(data_dict, file_path):
    json_safe_dict = {f"{pid}|{name}": value for (pid, name), value in data_dict.items()}

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(json_safe_dict, f, indent=4)

def load_composite_dict_from_json(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        raw_data = json.load(f)

    reconstructed_dict = {}
    for key_str, value in raw_data.items():
        parts = key_str.split("|")
        reconstructed_dict[(float(parts[0]), parts[1])] = value

    return reconstructed_dict