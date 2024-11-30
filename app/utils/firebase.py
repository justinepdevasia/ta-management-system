import pyrebase

firebase = None
auth = None
db = None
storage = None

def initialize_firebase(app):
    global firebase, auth, db, storage
    firebase = pyrebase.initialize_app(app.config['FIREBASE_CONFIG'])
    auth = firebase.auth()
    db = firebase.database()
    storage = firebase.storage()

def get_firebase():
    return firebase, auth, db, storage