import os
import re
import requests
import pandas as pd
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin
# from selenium import webdriver
# from selenium.webdriver.common.by import By
# from selenium.webdriver.common.keys import Keys
# from selenium.webdriver.support.ui import WebDriverWait
# from selenium.webdriver.support import expected_conditions as EC
# import time

TIMEOUT = 10
EMAIL_REGEX = r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+'
SESSION = requests.Session()  # Improve performance by reusing the session
BLOCKED_EMAIL_KEYWORDS = ['example', 'noreply']
CONTACT = ['contact', 'kontakt', 'contat']
GENERIC_EMAIL_KEYWORDS = ['info', 'contact', 'office', 'hello', 'admin', 'mail']
CONFIRMATION_KEYWORDS = ["yes", "18", "accept", "agree", "continue", "i am", "ok", "si", "ja", "oui", "sì", "sì,", "welcome"]  # Add more if needed
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/137.0.0.0 Safari/537.36"
    )
}

# def initialize_driver():
#     """Function to initialize a headless Chrome WebDriver using Selenium."""
#     options = webdriver.ChromeOptions()
#     options.add_argument('--headless')
#     options.add_argument('--no-sandbox') # Bypass OS security model
#     options.add_argument('--disable-gpu') # Applicable to Windows OS only
#     options.add_argument('--disable-dev-shm-usage') # Overcome limited resource problems
#     options.add_argument(f"user-agent={HEADERS['User-Agent']}")
#     driver = webdriver.Chrome(options=options)
#     return driver

# Manually extracting the search_selector from the DOM of a website to use selenium is much less efficient than
# finding the search url AND using it with requests!
# def search_sector(driver, sector, search_selector):
#     """Function to search for a sector on the given URL."""
#     search_input = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, search_selector)))
#     search_input.send_keys(Keys.CONTROL + "a")
#     search_input.send_keys(Keys.DELETE)
#     time.sleep(0.2)
#     search_input.send_keys(sector)
#     search_input.send_keys(Keys.RETURN)
#     time.sleep(2)  # Wait for search results to load

def fetch_html(url):
    """Fetches HTML content from a given URL and parses it."""
    try:
        response = SESSION.get(url, timeout=TIMEOUT, stream=True, headers=HEADERS, allow_redirects=False)
        status_code = response.status_code

        if status_code == 200:
            response.encoding = response.apparent_encoding
            return BeautifulSoup(response.text, 'html.parser'), None
        
        elif 300 <= status_code < 400:
            redirect_url = response.headers.get("Location").replace("www.www.", "www.")
            if redirect_url:
                if not urlparse(redirect_url).scheme:  # If missing scheme, add from current URL
                    redirect_url = urljoin(url, redirect_url)
            # if redirect_url != url:  # Avoid infinite loop on same URL
                return fetch_html(redirect_url)
            
        # elif status_code == 403:
            # print(f"403 encountered, retrying with Selenium for {url}")
            # return fetch_html_selenium(url)
            # return 403  # Return 403 status code to handle it later

        error = f"HTTP Error {status_code}"

    except requests.exceptions.ConnectionError as e:
        if "NameResolutionError" in str(e) or "getaddrinfo failed" in str(e):
            error = "DNS" # DNS Failure (Domain cannot be resolved) 
        else:
            error = f"Connection Error: {e}"

    except requests.exceptions.Timeout:
        error = "Timeout"

    except requests.exceptions.RequestException as e:
        error = f"Request Exception: {e}"

    return "", error

# def fetch_html_selenium(url):
#     driver = initialize_driver()
#     driver.implicitly_wait(10)  # Wait for elements to load
#     try:
#         driver.get(url)
#         # WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.XPATH, "//a[starts-with(@href, 'mailto:')]")))
#         WebDriverWait(driver, 5).until(lambda d: d.execute_script("return document.readyState") == "complete")
#         time.sleep(2)
#         # Try to click cookie consent or age confirmation buttons
#         buttons = driver.find_elements(By.TAG_NAME, "a") + driver.find_elements(By.TAG_NAME, "button")
#         # for btn in buttons:
#         #     try:
#         #         text = btn.text.strip().lower()
#         #         if any(k in text for k in CONFIRMATION_KEYWORDS):
#         #             href = btn.get_attribute('href')
#         #             if href and href.startswith("http"):  # Follow redirect if needed
#         #                 driver.get(href)
#         #                 time.sleep(1)
#         #                 return
#         #             else:
#         #                 btn.click()
#         #                 time.sleep(1)
#         #                 return
#         #     except:
#         #         continue
#         for btn in buttons:
#             try:
#                 text = btn.text.strip().lower()
#                 if any(k in text for k in CONFIRMATION_KEYWORDS):
#                     btn.click()
#                     time.sleep(1)
#                     break
#             except:
#                 continue
#         html = driver.page_source
#         driver.quit()
#         return BeautifulSoup(html, 'html.parser')
#     except Exception as e:
#         print(f"[Selenium Error] {url}: {e}")
#         driver.quit()
#         return ""

def is_valid_url(url):
    """Checks if a URL is reachable."""
    try:
        response = SESSION.head(url, timeout=TIMEOUT, headers=HEADERS)
        return response.status_code == 200
    except requests.RequestException:
        return False

def extract_href(parsed_request, class_name):
    """Extracts hrefs from parsed HTML based on the provided class name."""
    link_tags = parsed_request.find_all("a", class_=class_name)
    return [tag["href"] for tag in link_tags] if link_tags else []

def extract_company_name(parsed_request, class_name):
    """Extracts company names from parsed HTML based on the provided class name."""
    company_name = parsed_request.find('a', class_=class_name)
    company_name = company_name.get_text(strip=True) if company_name else None
    return company_name

def extract_location(parsed_request, selector):
    """Extracts company location from parsed HTML based on the provided selector."""
    country = parsed_request.select_one(selector)
    return country.get_text(strip=True) if country else None

def extract_emails(soup):
    """Extracts unique emails from visible text and mailto links in parsed HTML."""
    if not soup:
        return []
    
    # Visible text from all elements
    text = soup.get_text(separator=' ')

    # Fallback: scan individual divs/spans too
    # for tag in soup.find_all(['div', 'span', 'p']):
    #     text += ' ' + tag.get_text(separator=' ')

    emails_from_text = [clean_email(e) for e in re.findall(EMAIL_REGEX, text)]
    # mailto_links = [clean_email(a['href'][7:]) for a in soup.find_all('a', href=True) if a['href'].startswith('mailto:')]
    mailto_links = []
    for a in soup.find_all('a'):
        href = a.get('href', '')
        if isinstance(href, str) and href.lower().startswith('mailto:'):
            mailto_links.append(clean_email(href[7:]))  # Remove 'mailto:' prefix
    
    all_emails = set(emails_from_text + mailto_links)
    return list(filter(is_valid_email, all_emails))

def clean_email(email):
    """Cleans up the email by removing any query parameters or fragments."""
    return email.split('?')[0].strip()

def is_valid_email(email):
    """Checks if an email is a valid business email based on common fake/broken email formats."""
    return all(x not in email.lower() for x in BLOCKED_EMAIL_KEYWORDS)

def select_primary_email(email_list, company_url):
    """Heuristically selects the most relevant email."""
    if not email_list:
        return None

    domain = extract_domain(company_url)

    # Filter by domain match
    domain_matched = [e for e in email_list if domain in e]

    # From domain-matched, prefer generic names
    for email in domain_matched:
        prefix = email.split('@')[0].lower()
        if any(keyword in prefix for keyword in GENERIC_EMAIL_KEYWORDS):
            return email

    # Fallback: first domain-matched email
    if domain_matched:
        return domain_matched[0]

    # Else: pick first short-looking email
    return sorted(email_list, key=len)[0]

def extract_domain(url):
    """Extracts domain name from a URL like https://www.company.com -> company.com"""
    from urllib.parse import urlparse
    netloc = urlparse(url).netloc
    return netloc.replace("www.", "") if netloc else ""
    
def save_to_csv(data, filename, headers=None):
    """Saves data to a CSV."""
    if headers is not None:
        df = pd.DataFrame(data, columns=headers)
    else:
        df = pd.DataFrame(data)
    df.drop_duplicates(inplace=True)
    df.to_csv(filename, index=False)

def follow_contact_page(soup, base_url):
    """Follows the contact page link and extracts emails."""
    links = soup.find_all("a", href=True)
    for a in links:
        href = a['href'].lower()
        for keyword in CONTACT:
            if keyword in href:  # Check if the link contains 'contact' or similar
                contact_url = href
                if contact_url.startswith("/"):
                    contact_url = base_url.rstrip("/") + contact_url
                elif contact_url.startswith("http"):
                    pass
                else:
                    contact_url = base_url.rstrip("/") + "/" + contact_url
            contact_html = fetch_html(contact_url)
            if contact_html:
                return extract_emails(contact_html)
    return []

# def check_for_validation_page(soup):
    # Check the length of the soup, if it is small, it is a validation page and should be handled accordingly
    # if not soup or len(soup.get_text()) < 100:  # Arbitrary length threshold
    #     return True
    # text = soup.get_text(separator=' ').lower()
    # return any(keyword in text for keyword in CONFIRMATION_KEYWORDS)
    # # print(len(response.text))

def add_company_to_csv(url, error, csv_filename="output/errors.csv", headers=None):
    """Adds a company's information to an existing CSV file.
    
    Args:
        company_name (str): Name of the company
        country (str): Country where the company is located
        link (str): Website URL of the company
        csv_filename (str): Path to the CSV file
        headers (list, optional): Column headers if creating a new file. 
                                 Defaults to ['company_name', 'country', 'link']
    """
    
    # Default headers if not provided
    if headers is None:
        headers = ['error', 'url']

    # Check if file exists
    file_exists = os.path.exists(csv_filename)
    
    # Create new row data
    new_row = [error, url]
    
    if file_exists:
        # Read existing data
        try:
            df = pd.read_csv(csv_filename)
            # Add new row
            new_data = pd.DataFrame([new_row], columns=headers)
            df = pd.concat([df, new_data], ignore_index=True)
        except pd.errors.EmptyDataError:
            # File exists but is empty
            df = pd.DataFrame([new_row], columns=headers)
    else:
        # Create new DataFrame
        df = pd.DataFrame([new_row], columns=headers)

    # Remove duplicates based on company name and URL
    df.drop_duplicates(subset=['url'], inplace=True)

    # Save to CSV
    df.to_csv(csv_filename, index=False)
