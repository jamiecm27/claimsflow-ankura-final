"""Local-only account recovery; no remote reset endpoints."""
import html, os, secrets, sqlite3, time, threading, shlex
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs
from accounts import set_password, add_user, initialize
DB=Path(os.environ['CLAIMSFLOW_ACCOUNTS_DB'])
TOKEN=secrets.token_urlsafe(32)
DEADLINE=time.monotonic()+600

def admins():
    initialize(DB)
    with sqlite3.connect(DB) as db:
        return [r[0] for r in db.execute("SELECT username FROM users WHERE role='admin' AND active=1 ORDER BY username")]

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path!='/'+TOKEN or time.monotonic()>DEADLINE:
            self.send_error(404);return
        users=admins()
        if users:
            options=''.join('<option value="'+html.escape(u,quote=True)+'">'+html.escape(u)+'</option>' for u in users)
            user_input='<label>Administrator account<select name="username" required>'+options+'</select></label>'
            title='Reset administrator password'
        else:
            user_input='<label>New administrator username<input name="username" required pattern="[A-Za-z0-9_-]+" maxlength="80" autocomplete="username"></label>'
            title='Create administrator account'
        self.reply('<!doctype html><html><meta charset="utf-8"><title>ClaimsFlow account recovery</title><style>body{font:16px system-ui;max-width:500px;margin:8vh auto;padding:20px}input,button,select{display:block;width:100%;padding:12px;margin:12px 0;box-sizing:border-box}label{display:block}</style><h1>'+title+'</h1><p>This page works only on the Mac mini. Existing claims are not deleted.</p><form method="post">'+user_input+'<label>New password (at least 12 characters)<input name="password" type="password" minlength="12" required autocomplete="new-password"></label><label>Confirm password<input name="confirm" type="password" minlength="12" required autocomplete="new-password"></label><button>Save new login</button></form></html>')
    def do_POST(self):
        if self.path!='/'+TOKEN or time.monotonic()>DEADLINE:
            self.send_error(404);return
        try: length=int(self.headers.get('Content-Length','0'))
        except ValueError: self.send_error(400);return
        if length>4096 or length<0: self.send_error(413);return
        data=parse_qs(self.rfile.read(length).decode('utf-8',errors='replace'))
        username=data.get('username',[''])[0].strip(); password=data.get('password',[''])[0]; confirm=data.get('confirm',[''])[0]
        if password!=confirm:
            self.reply('<h1>Passwords do not match</h1><p>Go back and try again.</p>');return
        try:
            users=admins()
            if users:
                if username not in users: raise ValueError('Select an existing administrator')
                set_password(DB,username,password)
            else:
                add_user(DB,username,password,'admin')
        except (ValueError,sqlite3.Error) as e:
            self.reply('<h1>Could not save login</h1><p>'+html.escape(str(e))+'</p><p>Go back and try again.</p>');return
        self.reply('<h1>Login updated successfully</h1><p>Username: <strong>'+html.escape(username)+'</strong></p><p>You can now sign in to ClaimsFlow. This recovery page is closed.</p>')
        threading.Thread(target=self.server.shutdown,daemon=True).start()
    def reply(self,body):
        b=body.encode();self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)
    def log_message(self,*args):pass
if __name__=='__main__':
    initialize(DB)
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    url=f'http://127.0.0.1:{server.server_port}/{TOKEN}'
    print('Opening local administrator recovery in Safari...')
    os.system('open -a Safari '+shlex.quote(url))
    timer=threading.Timer(600,server.shutdown);timer.daemon=True;timer.start()
    server.serve_forever()
