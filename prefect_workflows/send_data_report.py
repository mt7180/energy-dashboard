from prefect import flow
from prefect_email import EmailServerCredentials, email_send_message
from typing import NamedTuple


class User(NamedTuple):
    name: str
    email: str
    country_code: str


@flow
def send_data_report(email_address: str, email_text) -> None:
    """sends an energy data report to a specified email address"""

    # use the prefect Email Credentials Block here:
    email_server_credentials = EmailServerCredentials.load("my-email-credentials")
    user = User(name="test_user", email=email_address, country_code="DE")

    line1 = f"Hello {user.name}, <br>"
    line2 = "Please find our lastest update on: <br><br>"
    # line3 = f"<h1>Generation (Forecasts) for {data['title']} - {region}</h1>"
    # this is a pre-defined prefect task:
    email_send_message.with_options(name="send-user-newsletter").submit(
        email_server_credentials=email_server_credentials,
        subject="Newsletter:",
        msg=line1 + line2 + email_text,
        email_to=user.email,
    )


if __name__ == "__main__":
    from dotenv import load_dotenv
    from prefect.flows import DeploymentTrigger

    deploy_flow = True
    load_dotenv("../.env", override=True)

    if deploy_flow:
        send_data_report.from_source(
            source="https://github.com/mt7180/energy-dashboard.git",
            entrypoint="./prefect_workflows/send_data_report.py:send_data_report",
        ).deploy(
            name="my-first-deployment",
            work_pool_name="my_prefect_managed_infra",
            triggers=[
                DeploymentTrigger(
                    match={"prefect.resource.id": "email-webhook-id"},
                    parameters={
                        "email_address": "{{ event.resource.message_address }}",
                        "email_text": "{{ event.resource.message_txt }}",
                    },
                )
            ],
        )
    else:
        send_data_report()
