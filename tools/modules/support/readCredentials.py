import gspread, os

def readCredentials(directory):
    DIRECTORY = os.path.abspath(os.path.join(directory, os.pardir))
    gc = gspread.oauth(
        credentials_filename=DIRECTORY + '/credentials/credentials.json',
        authorized_user_filename=DIRECTORY + '/credentials/authorized_user.json'
    )
    return gc