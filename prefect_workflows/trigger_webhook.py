import requests
from prefect.blocks.system import String

def trigger_webhook(msg: str) -> None:
    

    url = 'https://api.prefect.cloud/hooks/bSHnwyVlSn1WfbuRVZH35g'
    myobj = {'message_text': msg}

    x = requests.post(url, json = myobj)

    print(x)

if __name__ == "__main__":
    email = String.load("test-email").value,
    trigger_webhook("trigger my webhook")