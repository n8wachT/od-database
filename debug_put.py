import requests
import json


payload = json.dumps({
    "website_id": 123,
    "url": "ftp://132.249.213.137",
    # "url": "http://localhost:8000/",
    # "url": "http://ubuntu.mirrorservice.org/",
    "priority": 2,
    "callback_type": "",
    "callback_args": "{}"
})

r = requests.post("http://localhost:5001/task/put",
                  headers={"Content-Type": "application/json",
                           "Authorization": "Token abc"},
                  data=payload)
