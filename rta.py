import argparse
import logging
from calendar import day_name
from datetime import datetime, timedelta
from os import environ
from textwrap import dedent

from selenium.webdriver import Firefox
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.support.ui import WebDriverWait

logging.basicConfig(format='%(asctime)s - %(message)s', level=logging.INFO)
env_variables = ['RTA_PASSWORD', 'RTA_LOGIN']

lang_dict = {
    'en': {
        'My account': 'My account',
        'Search': 'Search',
        'Search connection': 'Search your connection',
        'Monthly ticket': 'Season Ticket - seat reservation ',
        'Choose': 'Choose',
        'Confirm': 'confirm',
        'Logout': 'Log out',
        'Car types': ['Indifferent', 'Compartment coach', 'Noncompartment coach'],
        'Position': ['Indifferent', 'window', 'middle', 'corridor'],
    },
    'pl': {
        'My account': 'Moje konto',
        'Search': 'Wyszukaj',
        'Search connection': 'Wyszukaj połączenie',
        'Monthly ticket': 'Bilet Okresowy - miejscówka ',
        'Choose': 'Wybierz',
        'Confirm': 'potwierdź',
        'Logout': 'Wyloguj',
        'Car types': ['dowolny', 'Wagon z przedziałami', 'Wagon bez przedziałów'],
        'Position': ['dowolny', 'okno', 'środek', 'korytarz'],
    }
}


class FirefoxBrowser(object):
    def __init__(self, headless: bool, page: str):
        browser_options = Options()
        browser_options.headless = headless
        self.browser = Firefox(options=browser_options)
        self.browser.get(page)

    def __del__(self):
        self.browser.close()
        self.browser.quit()


class PageActions(object):
    def __init__(self, browser: FirefoxBrowser):
        self.fb = browser
        self.monthly_ticket_id = None

    def _wait_until_element_is_visible(self, by: By, name: str):
        element_present = expected_conditions.presence_of_element_located((by, name))
        WebDriverWait(self.fb.browser, 20).until(element_present)

    def _close_current_tab(self):
        self.fb.browser.close()
        self.fb.browser.switch_to.window(self.fb.browser.window_handles[-1])

    def _wait_and_act(self, by: By, argument: str, text_input: str = ''):
        method = {
            By.XPATH: self.fb.browser.find_element_by_xpath,
            By.NAME: self.fb.browser.find_element_by_name,
            By.ID: self.fb.browser.find_element_by_id,
        }

        self._wait_until_element_is_visible(by, argument)
        element = method[by](argument)
        element.send_keys(text_input) if text_input else element.click()

    def _log_ticket_data(self):
        self._wait_until_element_is_visible(By.CLASS_NAME, 'label_std_sub')
        ticket_details = self.fb.browser.find_elements_by_xpath(
            xpath="//*[@class='data_box_section']//*[@class='label_shadow' or @class='label_std_sub']"
        )

        logging.info('Booked ticket data:')
        for x, y in zip([y.text for y in ticket_details][5::2], [y.text for y in ticket_details][6::2]):
            logging.info('+  {}: {}'.format(x.replace('\n', ' '), y))

    def login(self):
        self._wait_and_act(By.XPATH, "//*[contains(text(), '{}')]".format(lang_dict['My account']))
        self._close_current_tab()

        # transition to another page
        self._wait_and_act(By.NAME, 'login', environ['RTA_LOGIN'])
        self._wait_and_act(By.NAME, 'password', environ['RTA_PASSWORD'])
        self._wait_and_act(By.NAME, 'actlogin')

    def get_monthly_ticket_id(self):
        self._wait_until_element_is_visible(By.XPATH, "//*[@class='first table_div_cell']")
        for ticket in self.fb.browser.find_elements_by_xpath("//*[@class='first table_div_cell']"):
            if 'City Bilet' in ticket.text:
                self.monthly_ticket_id = ''.join([x for x in ticket.text.split()[0] if not x.isalpha()])
                logging.info('Monthly ticket ID: {}'.format(self.monthly_ticket_id))

        logging.info('Monthly ticket validity: {}'.format(
            ' - '.join([x.text for x in self.fb.browser.find_elements_by_xpath(
                "//*[@class='table_div_cell table_div_cell_wyjazd_od_do']/div/div[@class='display-inline']"
            ) if any(y.isdigit() for y in list(x.text))
                        ])))

    @staticmethod
    def get_next_day(name: str) -> datetime:
        delta = 0
        while (datetime.today() + timedelta(days=delta)).strftime('%A') != name:
            delta += 1
        return datetime.today() + timedelta(days=delta)

    def find_connections(self, start_city: str, destination_city: str, dep_time: datetime):
        self._wait_and_act(By.XPATH, "//*[contains(text(), '{}')]".format(lang_dict['Search connection']))

        self._wait_and_act(By.ID, 'ic-seek-z', start_city)
        self._wait_and_act(By.XPATH, "//*[@title='{}']".format(start_city))

        self._wait_and_act(By.ID, 'ic-seek-do', destination_city)
        self._wait_and_act(By.XPATH, "//*[@title='{}']".format(destination_city))

        while self.fb.browser.find_element_by_id('InputID3').get_attribute('value') < dep_time.strftime('%Y-%m-%d'):
            self._wait_and_act(
                by=By.XPATH,
                argument="//*[@class='input-controls jsInputDatepickerControls']/span[@class='prev icon-angle-top']"
            )

        while self.fb.browser.find_element_by_id('ic-seek-time').get_attribute('value') <= dep_time.strftime('%H:%M'):
            self._wait_and_act(
                by=By.XPATH,
                argument="//*[@class='input-controls jsInputTimepickerControls']/span[@class='prev icon-angle-top']"
            )

        while self.fb.browser.find_element_by_id('ic-seek-time').get_attribute('value') > dep_time.strftime('%H:%M'):
            self._wait_and_act(
                by=By.XPATH,
                argument="//*[@class='input-controls jsInputTimepickerControls']/span[@class='next icon-angle-bottom']"
            )

        self._wait_and_act(By.XPATH, "//*[@for='ic-seek-direct']/span")
        self._wait_and_act(By.XPATH, "//*[contains(text(), '{}')]".format(lang_dict['Search']))

    def fill_ticket_details(self, car_type: str, position: str):
        self._wait_and_act(By.ID, 'liczba_n')
        self._wait_and_act(By.XPATH, "//*[@id='liczba_n']/option[text()='0']")

        self._wait_and_act(By.ID, 'liczba_u')
        self._wait_and_act(By.XPATH, "//*[@id='liczba_u']/option[text()='1']")

        self._wait_and_act(By.ID, 'kod_znizki')
        self._wait_and_act(By.XPATH, "//*[@id='kod_znizki']/option[text()='{}']".format(lang_dict['Monthly ticket']))

        self._wait_and_act(By.ID, 'rodzaj_wagonu')
        self._wait_and_act(By.XPATH, "//*[@id='rodzaj_wagonu']/option[text()='{}']".format(car_type))

        self._wait_and_act(By.ID, 'usytuowanie')
        self._wait_and_act(By.XPATH, "//*[@id='usytuowanie']/option[text()='{}']".format(position))

        self._wait_and_act(By.ID, 'strefa_modal')

        # transition to another page
        self._wait_and_act(By.ID, 'nr_biletu_do_doplaty', self.monthly_ticket_id)
        self._wait_and_act(By.XPATH, "//*[contains(text(), '{}')]".format(lang_dict['Choose']))

        # transition to another page
        self._log_ticket_data()
        self._wait_and_act(By.XPATH, "//*[@value='{}']".format(lang_dict['Confirm']))

    def logout(self):
        self._wait_and_act(By.XPATH, "//*[contains(text(), '{}')]".format(lang_dict['Logout']))

    def book_ticket(self, start_city: str, destination_city: str, dep_time: datetime, car_type: str, position: str):
        self.find_connections(
            start_city=start_city,
            destination_city=destination_city,
            dep_time=dep_time,
        )
        self.fill_ticket_details(
            car_type=car_type,
            position=position,
        )


def initialize():
    description = """
    Automated ticket booking script. Requires {} environment variables to be set with login data.
    
    Selenium library and gecko driver are required:
     - https://github.com/mozilla/geckodriver/releases
     - https://pypi.org/project/selenium/
    
    """.format(', '.join(env_variables))

    car_help = '\n'.join(['{}: {}'.format(x, y) for x, y in list(enumerate(lang_dict['en']['Car types']))])

    parser = argparse.ArgumentParser(description=dedent(description), formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument('weekday', type=str, choices=day_name, help='Weekday for which booking should be made')
    parser.add_argument('url', type=str, help='Url for ticket website')
    parser.add_argument('--start_station', type=str, default='Poznań Główny', help='start station')
    parser.add_argument('--dest_station', type=str, default='Bydgoszcz Główna', help='destination station')
    parser.add_argument('--start_time', type=str, default='05:30', help='train departure in HH:MM format')
    parser.add_argument('--start_car', type=int, default=2, help=car_help, choices=range(0, 3))

    parser.add_argument('--book_return', default=False, action='store_true', help='book return ticket')
    parser.add_argument('--return_time', type=str, default='15:30', help='return train departure in HH:MM format')
    parser.add_argument('--return_car', type=int, default=0, help=car_help, choices=range(0, 3))

    parser.add_argument('--lang', type=str, default='pl', help='language', choices=['pl', 'en'])

    args = parser.parse_args()

    if not all([x in environ for x in env_variables]):
        [logging.error('Please provide {} environmental variable'.format(x)) for x in env_variables if x not in environ]
        exit(1)

    return args


if __name__ == "__main__":

    args = initialize()
    lang_dict = lang_dict[args.lang]

    ica = PageActions(FirefoxBrowser(headless=False, page='{}/{}/'.format(args.url, args.lang)))
    ica.login()
    ica.get_monthly_ticket_id()
    ica.book_ticket(
        start_city=args.start_station,
        destination_city=args.dest_station,
        dep_time=ica.get_next_day(args.weekday).replace(
            hour=int(args.start_time.split(':')[0]),
            minute=int(args.start_time.split(':')[1]),
        ),
        car_type=lang_dict['Car types'][args.start_car],
        position=lang_dict['Position'][1],
    )
    if args.book_return:
        ica.book_ticket(
            start_city=args.dest_station,
            destination_city=args.start_station,
            dep_time=ica.get_next_day(args.weekday).replace(
                hour=int(args.return_time.split(':')[0]),
                minute=int(args.return_time.split(':')[1]),
            ),
            car_type=lang_dict['Car types'][args.return_car],
            position=lang_dict['Position'][1],
        )
    ica.logout()
