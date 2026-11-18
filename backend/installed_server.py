"""Single-worker private-network runtime for installed releases."""
import json
import os
from pathlib import Path
import sys
import time
import socket
import uvicorn

if __name__ == '__main__':
    base = Path(sys.argv[1]).resolve(strict=True)
    config = json.loads((base/'install.json').read_text())
    os.environ.update(CLAIMSFLOW_DATA_DIR=str(base/'data'),
                      CLAIMSFLOW_ACCOUNTS_DB=str(base/'accounts.sqlite3'),
                      CLAIMSFLOW_AUTH_MODE='sessions',
                      CLAIMSFLOW_INSTANCE=config['instance'])
    # On login, wait for the private network interface. Bind only to that IP.
    while True:
        try:
            with socket.socket() as probe:
                probe.bind((config['host'], 0))
            break
        except OSError:
            time.sleep(5)
    uvicorn.run('app:app', host=config['host'], port=config['port'], workers=1, proxy_headers=False)
