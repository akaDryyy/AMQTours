from modules.support.readCredentials import readCredentials
import os
from modules.support.readElos import (
    load_composite_dict_from_json,
    save_composite_dict_to_json,
    sheet_safe_json_text,
)

def saveElos(directory, sheetID, sheetName, cell, elos_path, tourlist_path=None, tourlist_cell=None, backlog_path=None, backlog_cell=None):
    gc = readCredentials(directory)
    sheet = gc.open(sheetName)
    wks = sheet.get_worksheet_by_id(sheetID)

    ids_path = os.path.join(directory, "ids.csv")
    try:
        data = sheet_safe_json_text(elos_path, ids_path)
    except Exception:
        with open(elos_path, encoding="utf-8") as f:
            data = f.read()
    if cell:
        wks.update_acell(cell, data)

    if backlog_path and backlog_cell:
        with open(backlog_path) as f:
            backlog_data = f.read()
            wks.update_acell(backlog_cell, backlog_data)

    if tourlist_path and tourlist_cell:
        with open(os.path.join(directory, "tourlist.txt")) as t:
            tourlist_data = t.read()
            wks.update_acell(tourlist_cell, tourlist_data)
