from scanner import Scanner, Predicate
from consumer import Consumer
from utils import *

import asyncio

# Description: Configuration file for the program

STOP_CONDITION = Predicate.MAX_YEAR
STOP_VALUE = 2019
CONSUMER_THREADS = 1
SCANNING_THREADS = 1
PROFIT_THRESHOLD = 50 #irrelevant

LOGIN, PASSWORD = get_credentials()
FILENAME = generate_filename(val=STOP_VALUE) 
CURRENCY_RATE = get_currency_rate("usd")

def start_scanners(scanners: list):
    for i in range(SCANNING_THREADS):
        scanner = Scanner(
            exit_pred=STOP_CONDITION,
            exit_val=STOP_VALUE,
            step=SCANNING_THREADS,
            index=i+1,
            headless=False,
        )
        scanner.start()
        scanners.append(scanner)

def join_scanners(scanners: list, consumables: list):
    for scanner in scanners:
        scanner.join()
        consumables += scanner.dump_results()

def start_consumers(consumers: list, consumables: list):
    for i in range(CONSUMER_THREADS):
        consumer = Consumer(
            login=LOGIN,
            password=PASSWORD,
            products=consumables[i],
            usd_exchange_rate=CURRENCY_RATE,
            profit_threshold=PROFIT_THRESHOLD,
            headless=False,
        )
        consumer.start()
        consumers.append(consumer)

def join_consumers(consumers: list, results: list):
    for consumer in consumers:
        consumer.join()
        results += consumer.dump_results()

async def main():
    scanners = []
    consumers = []
    results = []
    to_consume = []

    start_scanners(scanners)
    join_scanners(scanners, to_consume)

    batches = split_workload(to_consume, CONSUMER_THREADS)

    start_consumers(consumers, batches)
    join_consumers(consumers, results)

    results_to_excel(results, FILENAME)

if __name__=="__main__":
    asyncio.run(main())