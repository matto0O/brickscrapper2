from os import system, getenv

def get_currency_rate(currencyAcronym: str = "usd") -> float:
    import requests
    import json

    url = f"http://api.nbp.pl/api/exchangerates/rates/a/{currencyAcronym}/"

    response = requests.get(url)
    data = json.loads(response.text)
    return float(data['rates'][0]['mid'])

def get_credentials() -> tuple:
    from dotenv import load_dotenv

    load_dotenv()
    LOGIN = getenv("LOGIN")
    PASSWORD = getenv("PASSWORD")

    return LOGIN, PASSWORD

def split_workload(workload: list, threads_no: int) -> list:
    workload_size = len(workload)
    step = workload_size // threads_no
    remainder = workload_size % threads_no

    res = [workload[:step+remainder]]
    workload = workload[step+remainder:]
    for _ in range(1, threads_no):
        res.append(workload[:step])
        workload = workload[step:]

    return res

def results_to_excel(results: list, filename: str = "results.xlsx"):
    import pandas as pd

    df = pd.DataFrame(results)
    try:
        df.sort_values(by=["Zysk %", "Cena zakupu"], inplace=True, ascending=False)
    except KeyError:
        pass
    finally:
        df.to_excel(filename, index=False)
        system(filename)
        
def generate_filename(**kwargs) -> str:
    from datetime import datetime

    try:
        val = kwargs['val']
        now = datetime.now()
        return f"results_{val}_{now.strftime('%Y-%m-%d_%H-%M-%S')}.xlsx"
    except KeyError:
        now = datetime.now()
        return f"results_{now.strftime('%Y-%m-%d_%H-%M-%S')}.xlsx"
