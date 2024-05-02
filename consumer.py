from playwright.async_api import async_playwright
import asyncio
from threading import Thread
import re

class Consumer(Thread):
    def __init__(
            self,
            login: str,
            password: str,
            products: list,
            usd_exchange_rate: float = 4.1,
            profit_threshold: int = 150,
            **kwargs
        ):

        super().__init__()

        self.login = login
        self.password = password
        self.products = products
        self.exchange = usd_exchange_rate
        self.threshold = profit_threshold

        self.kwargs = kwargs

        self.results = []

    def __str__(self) -> str:
        return f"Consumer"
    
    # def __del__(self):
    #     asyncio.run(self.driver.close())
    
    async def _bricklink_login(self):
        await self.driver.goto("https://www.bricklink.com/v2/main.page")
        buttons = await self.driver.query_selector_all('button')    
        await buttons[-1].click()               # cookies
        await self.driver.click('button#nav-login-button')
        
        await self.driver.fill('input[id="usernameOrEmail"]', self.login)
        await self.driver.fill('input[id="password"]', self.password)
        login_button = self.driver.get_by_role("button", name="Log in", exact=True)
        await login_button.click()
        await asyncio.sleep(2)

    async def _olx_cookies(self):
        await self.driver.goto("https://www.olx.pl/")
        await self.driver.click('button[id="onetrust-accept-btn-handler"]')
        await asyncio.sleep(2)


    def dump_results(self) -> list:
        dump = self.results
        self.results = []
        return dump
    
    async def _check_olx(self, catalog_no, promoklocki_price):
        await self.driver.goto(f"https://www.olx.pl/oferty/q-LEGO-{catalog_no}/?search%5Border%5D=filter_float_price:asc&search[filter_enum_state][0]=new")
        total_count = await self.driver.query_selector('span[data-testid="total-count"]')
        if total_count is None:
            return "Brak ogłoszeń"
        
        tc_text = await total_count.text_content()
        tc_number = int(re.findall(r'\d+', tc_text)[0])

        if not tc_number:
            return "Brak ogłoszeń"
        
        price_elements = await self.driver.query_selector_all('p[data-testid="ad-price"]')
        price = 0
        i = 0
        while price < 0.4 * promoklocki_price and i < len(price_elements):
            best = price_elements[i]
            price_text = await best.text_content()
            price = float(price_text.split(" ")[0].replace(",", "."))
            if price > promoklocki_price:
                return "Drozsze niż promoklocki"
            i += 1
        return price
    
    async def magic(self):
        async with async_playwright() as playwright:
            client = await playwright.chromium.launch(**self.kwargs)
            self.driver = await client.new_page()
            await self._bricklink_login()
            await self._olx_cookies()

            while self.products:
                product = self.products.pop()
                name = product["name"]
                price = float(product["price"])
                year = product["year"]
                catalog_no = name.split(" - ")[0].split(" ")[-1]

                bricklink = f"https://www.bricklink.com/catalogPOV.asp?itemType=S&itemNo={catalog_no}&itemSeq=1&itemQty=1&breakType=M&itemCondition=N&incInstr=Y&incParts=Y"
                await self.driver.goto(bricklink)
                
                try:
                    bold = await self.driver.query_selector_all('(//tr[last()]//td)[1]//p//b')
                    boldText = await bold[0].text_content()
                    avg = float(boldText.split(" ")[1][1:]) * self.exchange
                except:
                    continue

                roi = round(100 * (avg - price) / price, 2)
                    
                olx = await self._check_olx(catalog_no)

                # if roi >= self.threshold:
                # total_bricks = int(await bold[1].text_content())
                # unique_bricks = int(await bold[2].text_content())
                # price_per_unique = round(price / float(unique_bricks), 2)

                columns = {"Numer zestawu": catalog_no, "Nazwa": name,
                    # "Łączna liczba klocków": total_bricks, "Liczba unikalnych klocków": unique_bricks, "Cena/unikatowy klocek":price_per_unique, 
                    "Part Out Value": round(avg, 2), "Zysk %": roi,
                    "Minimalna promoklocki": price, "Minimalna olx": olx, #"Minimalna Allegro": min_allegro,
                    }
                
                self.results.append(columns)

    def run(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self.magic())
        loop.close()
