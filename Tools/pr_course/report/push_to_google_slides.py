"""Replace the contents of an existing Google Slides deck with a local .pptx, keeping its link, sharing and history.

    python push_to_google_slides.py CLIENT_SECRET.json DECK.pptx [PRESENTATION_ID]

CLIENT_SECRET.json = an OAuth client of type "Desktop app" from Google Cloud Console (APIs & Services > Credentials),
in a project with the Google Drive API enabled. The first run opens a browser to sign in; the token is cached next to the
client secret (token_slides.json).

Safety: before writing, the current version of the deck is exported to DECK.backup-<time>.pptx, and Google keeps it in
File > Version history as well. Anything a teammate changed in the Google deck after you exported it is replaced, so
re-export and rebuild right before pushing if others are editing."""
import os, sys, time
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

SCOPES = ["https://www.googleapis.com/auth/drive"]
PPTX = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
secret, deck = sys.argv[1], sys.argv[2]
pid = sys.argv[3] if len(sys.argv) > 3 else "19nnqxH83eiz63YVwi7fEl4d009OODXVtZNgmVck8HT0"

tok = os.path.join(os.path.dirname(os.path.abspath(secret)), "token_slides.json")
creds = Credentials.from_authorized_user_file(tok, SCOPES) if os.path.exists(tok) else None
if not creds or not creds.valid:
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    else:
        creds = InstalledAppFlow.from_client_secrets_file(secret, SCOPES).run_local_server(port=0)
    open(tok, "w").write(creds.to_json())
drive = build("drive", "v3", credentials=creds)

meta = drive.files().get(fileId=pid, fields="name,mimeType,modifiedTime", supportsAllDrives=True).execute()
print(f"target: {meta['name']}  ({meta['mimeType']}, last modified {meta['modifiedTime']})")
if meta["mimeType"] != "application/vnd.google-apps.presentation":
    sys.exit("not a Google Slides file - stopping")
backup = f"{os.path.splitext(deck)[0]}.backup-{time.strftime('%Y%m%d-%H%M%S')}.pptx"
open(backup, "wb").write(drive.files().export(fileId=pid, mimeType=PPTX).execute())
print("backup of the current deck:", backup)

try:
    res = drive.files().update(fileId=pid, media_body=MediaFileUpload(deck, mimetype=PPTX, resumable=True),
                               fields="id,name,modifiedTime", supportsAllDrives=True).execute()
except HttpError as e:
    sys.exit(f"Google refused the in-place replace ({e.status_code}): {e.reason}\n"
             "Nothing was changed. Use File > Import slides in Google Slides instead.")
print(f"updated: https://docs.google.com/presentation/d/{res['id']}/edit  (modified {res['modifiedTime']})")
