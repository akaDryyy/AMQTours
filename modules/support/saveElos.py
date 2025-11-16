from modules.support.readCredentials import readCredentials

def saveElos(directory, sheetID, sheetName, cell, elos_path):
    gc = readCredentials(directory)
    sheet = gc.open(sheetName)
    wks = sheet.get_worksheet_by_id(sheetID)

    with open(elos_path) as f:
        data = f.read()
        wks.update_acell(cell, data)