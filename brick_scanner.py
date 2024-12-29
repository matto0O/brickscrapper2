import time
from playwright.sync_api import sync_playwright
from dotenv import load_dotenv
from os import getenv
from threading import Thread
from collections import deque
import json
from utils import split_workload

load_dotenv()

class PartScanner(Thread):
    def __init__(
            self,
            index: int,
            data_source: deque,
            timeout: int = 3,
            **kwargs
        ):
        super().__init__()
        self.results = []
        self.site = "https://www.bricklink.com/"
        self.kwargs = kwargs
        self.data_source = data_source
        self.index = index
        self.timeout = timeout
        self.timeout_ms = timeout * 1000
    
    def launch(self):
        # accept cookies
        self.p = sync_playwright().start()
        self.browser = self.p.chromium.launch(**self.kwargs)
        self.context = self.browser.new_context()
        self.page = self.context.new_page()
        self.page.goto(self.site)
        tab = self.page.query_selector('xpath=.//div[contains(@id, "js-btn-section")]')
        just_necessary = tab.query_selector('xpath=.//button[contains(@class, "btn btn--white text--bold l-border cookie-notice__btn")]')
        just_necessary.click()

        # login
        try:
            login_button = self.page.query_selector('xpath=.//button[contains(@class, "blp-btn blp-icon-nav__item blp-icon-nav__item--sign-in")]')
            login_button.click()
            login = getenv('LOGIN')
            password = getenv('PASSWORD')
            
            input_username = self.page.query_selector('xpath=.//input[@id="usernameOrEmail"]')
            input_pwd = self.page.query_selector('xpath=.//input[@id="password"]')
            input_username.fill(login)
            input_pwd.fill(password)
            self.page.keyboard.press('Enter')
            self.page.expect_navigation(timeout=self.timeout_ms)
        except:
            print("Already logged in")

    # def join(self):
    #     self.browser.close()
    #     self.p.stop()



    def find_brick(self, id, max_qty=100):
        offer_results = []

        try:
            self.page.wait_for_selector('xpath=.//input[@class="blp-adv-search__input"]', timeout=self.timeout_ms)
        except:
            raise Exception("Timeout")
        input_field = self.page.query_selector('xpath=.//input[@class="blp-adv-search__input"]')
        input_field.fill(id)
        self.page.keyboard.press('Enter')
        try:
            self.page.expect_navigation(timeout=self.timeout_ms)
            self.page.wait_for_selector('xpath=.//td[contains(@id, "_idblWideTabTemplate")]', timeout=self.timeout_ms)
        except:
            raise Exception("Timeout")

        # are there any results?        
        tabs = self.page.query_selector_all('xpath=.//td[contains(@id, "_idblWideTabTemplate")]')
        if not tabs:
            raise Exception("No part tab found")
        
        clicked = False
        for tab in tabs:
            text = tab.text_content()
            if "Part" in text:
                tab.click()
                clicked = True
                break
        if not clicked:
            raise Exception("No part tab found")
        
        # find part number
        results = self.page.query_selector_all(
            'xpath=.//div[contains(@id, "_idContentsTabP")]//tr[contains(@class, "pspItemTypeContentsNew ")]'
        )

        to_check = []

        for result in results:
            part_number = result.query_selector('xpath=.//span[contains(@class, "pspItemCateAndNo")]')
            official_id = part_number.text_content().split(" : ")[1]
            if id in official_id:
                hyperlink = result.query_selector('xpath=.//a[contains(@class, "pspItemNameLink")]').get_attribute("href")
                to_check.append(hyperlink.split("&")[0])
        
        for link in to_check:
            self.page.goto("https://www.bricklink.com" + link + "#T=P")
            try:
                self.page.wait_for_selector('#_idSelectedColorText', timeout=self.timeout_ms)
            except:
                raise Exception("No color picker found / Timeout")
            
            color_picker = self.page.query_selector('xpath=.//span[contains(@id, "_idSelectPGColorContainer")]')
            color_picker.click()
            options = self.page.query_selector_all(
                'xpath=.//div[contains(@class, "pciPGTabColorDropdownList")]//div[contains(@class, "pciSelectColorColorItem")]'
            )

            if not options:
                raise Exception("No color options found")

            for option in options:
                color = option.text_content().replace('\xa0\xa0', '')
                option.click()
                try:
                    self.page.wait_for_selector('#_idPGContents > table > tbody > tr:nth-child(1) > td:nth-child(2)', timeout=self.timeout_ms)
                except:
                    raise Exception("Timeout")
                
                offer_table = self.page.query_selector_all('xpath=.//table[contains(@class, "pcipgInnerTable")]')[-1]
                offers = offer_table.query_selector_all('xpath=.//tr')
                if len(offers) > 9:
                    offers = offers[2:-7]
                    total_qty = 0
                    for offer in offers:
                        l = offer.query_selector_all('xpath=.//td')
                        seller, qty, price = l[0], l[1], l[2]
                        seller = seller.query_selector('xpath=.//a').get_attribute("href")
                        qty = int(qty.text_content())
                        total_qty += qty
                        price = float(price.text_content().split(" ")[1])
                        offer_results.append((official_id, color, seller, qty, price))
                        if total_qty >= max_qty:
                            break
                color_picker.click()
        return offer_results
    
    def run(self):
        self.launch()
        time.sleep(self.timeout)
        data = []
        unsuccessful = []
        while self.data_source:
            id = self.data_source.pop()
            try:
                res = self.find_brick(id)
                for item in res:
                    row = {
                        "Part": item[0],
                        "Color": item[1],
                        "Link": item[2],
                        "Quantity": item[3],
                        "Price": item[4]
                    }
                    data.append(row)
            except KeyboardInterrupt:
                unsuccessful.append(id)
                while self.data_source:
                    unsuccessful.append(self.data_source.pop())
                break
            except Exception as e:
                print(f"Thread {self.index}, Part {id}, Error: {e}")
                unsuccessful.append({"Part": id, "Error": str(e)})
                continue
        json.dump(data, open(f"results{self.index}.json", "w"))
        json.dump(unsuccessful, open(f"uns{self.index}.json", "w"))

if __name__ == "__main__":
    items = json.load(open("parts.json"))

    THREAD_COUNT = 4
    workloads = split_workload(list(items)[1000:], THREAD_COUNT)

    threads = []

    for i in range(THREAD_COUNT):
        q = deque(workloads[i])
        scanner = PartScanner(index=i, headless=True, data_source=q, timeout=5)
        scanner.start()
        threads.append(scanner)

    for scanner in threads:
        scanner.join()