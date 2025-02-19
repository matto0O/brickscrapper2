from playwright.async_api import async_playwright
from time import time, sleep
from enum import Enum
from threading import Thread
import asyncio


class Predicate(Enum):
    MAX_YEAR = 1,
    PAGE_AMOUNT = 2,
    TIME_ELAPSED = 3


class Scanner(Thread):
    def __init__(
            self,
            site="https://promoklocki.pl/",
            index=1,
            step=1,
            exit_pred: Predicate=Predicate.MAX_YEAR,
            exit_val: int=2024,
            **kwargs
        ):

        super().__init__()

        self.step = step
        self.site = site
        self.index = index
        self.results = []

        self.exit_pred = exit_pred
        self.exit_val = exit_val

        self.sites_visited = 0

        self.kwargs = kwargs

        self.birth = time()

    # def __del__(self):
    #     asyncio.run(self.driver.close())

    def __str__(self) -> str:
        return f"Scanner(site={self.site}, index={self.index}, step={self.step})"

    def dump_results(self) -> list:
        dump = self.results
        self.results = []
        return dump

    async def move_to_next(self):
        self.sites_visited += 1
        self.index += self.step
        await self.driver.close()
        sleep(1)

    async def scrape(self):
        products = await self.driver.query_selector_all('xpath=.//div[contains(@class, "product")]')
        for product in products:
            data = await product.query_selector("a")
            link = await data.get_attribute("href")
            name = await data.get_attribute("title")

            year = await product.query_selector('xpath=.//span[contains(@class, "small")]')
            year = await year.text_content()
            year = year.split(",")[0].split(":")[1].strip()

            price = await product.query_selector('xpath=.//span[contains(@class, "price-browse")]')
            price_edit = await price.text_content()
            price = float(price_edit.replace(",", "."))

            self.results.append({"name": name, "link": link, "year": year, "price": price})
    
    def _has_time_elapsed(self) -> bool:
        return time() - self.birth > self.exit_val
    
    def _passed_max_year(self) -> bool:
        if not self.results:
            return False
        return int(self.results[-1]["year"]) < self.exit_val
    
    def _hit_page_limit(self) -> bool:
        return self.sites_visited >= self.exit_val

    async def magic(self):
        if self.exit_pred == Predicate.MAX_YEAR:
            predicate = self._passed_max_year
        elif self.exit_pred == Predicate.PAGE_AMOUNT:
            predicate = self._hit_page_limit
        elif self.exit_pred == Predicate.TIME_ELAPSED:
            predicate = self._has_time_elapsed
        else:
            raise ValueError("Invalid predicate")
        
        while not predicate():
        
            async with async_playwright() as playwright:
                client = await playwright.chromium.launch(**self.kwargs)
                self.driver = await client.new_page()
                await self.driver.goto(self.site + "?p=" + str(self.index))

                await self.scrape()
                await asyncio.sleep(1)
                await self.move_to_next()

    def run(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self.magic())
        loop.close()

    