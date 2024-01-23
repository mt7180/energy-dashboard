import requests
from prefect.blocks.system import String


def trigger_webhook(payload: dict) -> None:
    """triggers a prefect webhooks' url endpoint with some payload"""
    url = String.load("email-webhook-url").value

    if not url:
        raise ValueError("Webhook URL not found")

    response = requests.post(url, json=payload)

    if response.status_code != 204:
        raise Exception(
            f"Failed to call the webhook. Status code: {response.status_code}"
        )

    print("Successfully called the webhook.")


def send_report(email_address: str, email_txt: str) -> None:
    """send report via email to given email_address by triggering
    a webhook, which triggers an automated flow run on Prefect Cloud
    """
    payload = {"message_address": email_address, "message_text": email_txt}
    trigger_webhook(payload)


if __name__ == "__main__":
    email_address = String.load("test-email").value
    payload = {
        "message_address": email_address,
        "message_text": "Hi from Energy Dashboard",
    }
    trigger_webhook(payload)
