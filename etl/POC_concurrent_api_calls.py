import collections
import pandas as pd
import asyncio
import httpx
import trio

Request = collections.namedtuple("Request", ["url", "params"])


def format_date(date: pd.Timestamp):
    date_str = date.strftime("%Y-%m-%dT%H:%M%z")
    return date_str[:-2] + ":" + date_str[-2:]


def extract_generation_by_source(start, end):
    url = "https://api.energy-charts.info/total_power"
    params = {"country": "de", "start": format_date(start), "end": format_date(end)}

    response = httpx.get(url=url, params=params)

    if response.status_code != 200:
        raise httpx.HTTPError

    print(response)
    # data = json.loads(response.text)
    # df_generation = pd.DataFrame(
    #     {item['name']:item['data'] for item in data['production_types']},
    #     index=[datetime.fromtimestamp(date) for date in data['unix_seconds']]
    # )

    # return df_generation


def extract_capacity_by_source():
    req = Request(
        "https://api.energy-charts.info/installed_power",
        {"country": "de", "time_step": "yearly", "installation_commission": False},
    )

    response = httpx.get(url=req.url, params=req.params)

    if response.status_code != 200:
        raise httpx.HTTPError

    print(response)


# print(response.text)
# df_generation = pd.read_json(response.text)
# print(df_generation)
# for item in data:
#    print(item)

# breakpoint()


# async def extract_generation_by_source():

#     url = 'https://api.energy-charts.info/total_power'
#     params = {"country":"de" ,"start": format_date(start), "end":format_date(end)}


async def handle_api_request(client, url, params, results):
    # results[url] = await client.get(url=url, params=params)
    print(await client.get(url=url, params=params))


async def extract_data(start, end):
    """collect data by asyncronous API calls"""

    requests = [
        Request(
            "https://api.energy-charts.info/total_power",
            {"country": "de", "start": format_date(start), "end": format_date(end)},
        ),
        Request(
            "https://api.energy-charts.info/installed_power",
            {"country": "de", "time_step": "yearly", "installation_commission": False},
        ),
    ]

    async with httpx.AsyncClient() as httpx_client:
        async with trio.open_nursery() as nursery:
            # with trio slightly faster
            results = {}
            tasks = [
                (handle_api_request, httpx_client, request.url, request.params)
                for request in requests
            ]
            for task in tasks:
                nursery.start_soon(*task, results)


async def extract_data_asyncio(start, end):
    """collect data by asyncronous API calls"""

    requests = [
        Request(
            "https://api.energy-charts.info/total_power",
            {"country": "de", "start": format_date(start), "end": format_date(end)},
        ),
        Request(
            "https://api.energy-charts.info/installed_power",
            {"country": "de", "time_step": "yearly", "installation_commission": False},
        ),
    ]

    async with httpx.AsyncClient() as httpx_client:
        tasks = [
            httpx_client.get(url=request.url, params=request.params)
            for request in requests
        ]
        #  await asyncio.gather(*tasks)
        print(await asyncio.gather(*tasks))


if __name__ == "__main__":
    # try:

    import time

    end = pd.Timestamp.today(tz="Europe/Brussels")  # now
    start = end - pd.Timedelta(hours=24)

    start_time = time.perf_counter()
    trio.run(extract_data, start, end)

    async_time = time.perf_counter()
    asyncio.run(extract_data_asyncio(start, end))

    async_io_time = time.perf_counter()
    extract_generation_by_source(start, end)
    extract_capacity_by_source()

    end_time = time.perf_counter()
    print(
        f"async: {async_time - start_time:.2f} sec\n async_io: {async_io_time - async_time:.2f} sec"
    )
    print(f"sync: {end_time - async_io_time:.2f} sec")
