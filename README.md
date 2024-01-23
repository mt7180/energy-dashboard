# energy-dashboard

This is a project to visualize real time electricity generation data  for the pan-European market obtained from 
[ENTSOE](https://transparency.entsoe.eu/content/static_content/Static%20content/web%20api/Guide.html)



> Note:
A Prefect Webhook with the follofing template needs to be created to support the energy report email functionality of the app. The url endpoint needs to be saved in a Prefect String block to not be exposed publicly.
```
{
    "event": "email_webhook.called",
    "resource": {
        "prefect.resource.id": "email-webhook-id",
        "message_txt": "{{ body.message_text }}",
        "message_address": "{{ body.message_address }}"
    }
}
``````


### Future Improvements: 
- include transportation and consumption information
- include EPEX Spot Dayahead 
- include current wind speed (on x m height for given geo-loc -> find geo loc of ip address?!)
- include sun radiation ^