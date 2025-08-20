import os
import re
import base64
import requests
import pandas as pd
from bs4 import BeautifulSoup
from bs4 import NavigableString
from urllib.parse import urlparse, urljoin
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

TIMEOUT = 10
RETRIES = 3
SESSION = requests.Session()  # Improve performance by reusing the session
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/137.0.0.0 Safari/537.36"
    )
}

COOKIE = "cookie"
EMAIL_REGEX = r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+'
BLOCKED_EMAIL_KEYWORDS = ['example', 'noreply']
CONTACT = ['contact', 'kontakt', 'contat', 'kapcsolat', 'quem-somos', 'impressum']  # 'eπικοινωνια' 
GENERIC_EMAIL_KEYWORDS = ['info', 'contact', 'office', 'hello', 'admin', 'mail']
GATE_KEYWORDS = ["yes", "si", "ja", "oui", "sim", "accept", "agree", "continue", "older", "i am", "enter",
                 "english", "ok", "got it"]

def fetch_html(url, timeout=TIMEOUT, retries=0):
    """Fetches HTML content from a given URL and parses it."""
    soup = ""
    if not is_valid_url(url):
        return soup, "Invalid URL"
    try:
        response = SESSION.get(url, timeout=timeout, stream=True, headers=HEADERS, allow_redirects=False)
        response.encoding = response.apparent_encoding  # Analyzes the actual byte content and guesses the most likely encoding
        status_code = response.status_code
        
        if 300 <= status_code < 400:
            redirect_url = response.headers.get("Location").replace("www.www.", "www.")
            if redirect_url:
                if not urlparse(redirect_url).scheme:  # If missing scheme, add from current URL
                    redirect_url = urljoin(url, redirect_url)
            # if redirect_url != url:  # Avoid infinite loop on same URL
                return fetch_html(redirect_url)

        soup = BeautifulSoup(response.text, 'html.parser')
        error = status_code

    except requests.exceptions.ConnectionError as e:
        if "NameResolutionError" in str(e) or "getaddrinfo failed" in str(e):
            error = "DNS" # DNS Failure (Domain cannot be resolved) 
        else:
            error = f"Connection Error" #: {e}"

    except requests.exceptions.Timeout:
        error = "Timeout"
        if retries < RETRIES:
            return fetch_html(url, 2*timeout, retries + 1)  # Retry fetching HTML

    except requests.exceptions.RequestException as e:
        error = f"Request Exception: {e}"

    return soup, error

def initialize_selenium_driver():
    """Initializes a Selenium WebDriver with Chrome options."""
    options = Options()
    options.add_argument("--headless")  # Run in headless mode
    options.add_argument("--no-sandbox")  # Bypass OS security model
    options.add_argument("--disable-dev-shm-usage")  # Overcome limited resource problems
    options.add_argument('--disable-gpu') # Applicable to Windows OS only
    options.add_argument(f"user-agent={HEADERS['User-Agent']}")
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    return driver

def fetch_html_selenium(driver, url=None, bypass_gate=False, timeout=TIMEOUT):
    try:
        if url:
            driver.get(url)
        if bypass_gate and driver:
            try_click_gate_buttons(driver)

        # Wait for some visible content 
        try:
            WebDriverWait(driver, timeout).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
        except:
            pass

        html = driver.page_source
        return BeautifulSoup(html, "html.parser"), 200, driver
    except Exception as e:
        return "", f"Selenium error: {e}", driver

def try_click_gate_buttons(driver):
    """
    Try to bypass first-visit gates (age, language, cookies) by clicking
    links or buttons containing relevant keywords.
    """
    # Collect candidate elements
    candidates = driver.find_elements(By.TAG_NAME, "a") + driver.find_elements(By.TAG_NAME, "button")
    for el in candidates:
        try:
            text = el.get_attribute("textContent").strip().lower()

            if COOKIE in text:
                el.click()  # Click cookie consent buttons directly
                continue
                
            if any(keyword in text for keyword in GATE_KEYWORDS):
                href = el.get_attribute("href")

                if href:  # If it's a link
                    absolute_href = urljoin(driver.current_url, href)
                    driver.get(absolute_href)

                else:  # Otherwise click button
                    driver.execute_script("arguments[0].click();", el)

                return True
        except Exception:
            continue

    return False

def is_valid_url(url: str) -> bool:
    # Basic conditions
    if "http" not in url.lower():
        return False
    if "@gmail.com" in url.lower():
        return False
    if "@" in url:  # No @ symbol allowed at all
        return False
    
    # Extract domain part (between // and first / after that)
    try:
        domain = re.search(r"https?://([^/]+)", url).group(1)
    except AttributeError:
        return False  # couldn't parse domain
    
    # Valid domain characters: letters, numbers, hyphens, dots
    if not re.match(r"^[a-zA-Z0-9.-]+$", domain):
        return False
    
    # Domain shouldn't start or end with a hyphen or dot
    if domain.startswith(("-", ".")) or domain.endswith(("-", ".")):
        return False
    
    return True

def extract_href(parsed_request, class_name):
    """Extracts hrefs from parsed HTML based on the provided class name."""
    if not parsed_request:
        return ""
    link_tags = parsed_request.find_all("a", class_=class_name)
    return [tag["href"] for tag in link_tags] if link_tags else ""

def extract_company_name(parsed_request, class_name):
    """Extracts company names from parsed HTML based on the provided class name."""
    company_name = parsed_request.find('a', class_=class_name)
    company_name = company_name.get_text(strip=True) if company_name else None
    return company_name

def extract_location(parsed_request, selector):
    """Extracts company location from parsed HTML based on the provided selector."""
    country = parsed_request.select_one(selector)
    return country.get_text(strip=True) if country else None

def flatten_text(element):
    """Recursively join all text in nested tags without adding extra spaces."""
    texts = []
    for node in element.descendants:
        if isinstance(node, NavigableString):
            texts.append(str(node))
    return ''.join(texts)

def extract_email(soup, url):
    """Extracts unique emails from visible text and mailto links in parsed HTML."""
    if not soup:
        return None
    
    emails = set()
    # --- 1. Visible text from all elements ---
    text = normalize_text(soup.get_text(separator=' '))
    if text:
        emails = set(clean_email(e) for e in re.findall(EMAIL_REGEX, text))
    
    # --- 2. Handle iframes recursively ---
    if not emails:
        for iframe in soup.find_all("iframe"):
            src = iframe.get("src")
            if src:
                iframe_url = urljoin(url, src)
                iframe_soup, _ = fetch_html(iframe_url)
                email = extract_email(iframe_soup, iframe_url)
                if email:
                    emails.update(email)

    # --- 3. Scan anchor tags ---
    for a in soup.find_all('a'):
        href = a.get('href', '')
        if isinstance(href, str) and href.lower().startswith('mailto:'):
            emails.add(clean_email(href[7:]))  # Remove 'mailto:' prefix

        # anchor visible text can contain (obfuscated) emails too
        link_text = a.get_text(strip=True)
        if re.search(EMAIL_REGEX, link_text):
            emails.add(clean_email(normalize_text(link_text)))

    # --- 4. Scan all attributes for base64 encoded or hidden emails ---
    for tag in soup.find_all(True):
        for attr_val in tag.attrs.values():
            if isinstance(attr_val, str):
                attr_val = attr_val.strip()
                decoded = try_base64_decode(attr_val)
                if decoded:
                    emails.add(decoded)

    emails = list(filter(is_valid_email, emails))
    if not emails:
        return None
    email = emails[0] if len(emails) == 1 else select_primary_email(emails, url)
    return email

def normalize_text(text: str) -> str:
    """Clean common email obfuscations in text."""
    if not text:
        return ""
    text = text.replace("(at)", "@").replace("[at]", "@").replace("{at}", "@")
    text = re.sub(r'\s+@\s+', '@', text)        # remove spaces around @
    text = re.sub(r'\s+', ' ', text)            # normalize whitespace
    text = text.replace("\u200b", "")           # zero width space
    text = text.replace("\xa0", " ")            # non-breaking space
    return text

def clean_email(email):
    """Cleans up the email by removing any query parameters or fragments."""
    return email.split('?')[0].strip()

def is_valid_email(email):
    """Checks if an email is a valid business email based on common fake/broken email formats."""
    return all(x not in email.lower() for x in BLOCKED_EMAIL_KEYWORDS)

def try_base64_decode(value: str):
    """Try to decode a base64 string and return email if found."""
    try:
        decoded = base64.b64decode(value).decode(errors="ignore")
        if decoded.startswith("mailto:"):
            return decoded[7:]
        elif re.fullmatch(EMAIL_REGEX, decoded):
            return decoded
    except Exception:
        pass
    return None

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
    netloc = urlparse(url).netloc
    return netloc.replace("www.", "") if netloc else ""

def homepage_fallback(url):
    """Fallback function to get the homepage URL (assuming its the base URL)."""
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}/"

def extract_email_from_contact_page(soup, base_url, driver=None):
    """Extracts emails from the contact page."""
    if not soup:
        return None, "No contact page found"
    
    if driver:
        WebDriverWait(driver, TIMEOUT).until(EC.presence_of_all_elements_located((By.TAG_NAME, "a")))

    links = soup.find_all("a", href=True)
    strong_candidates = []
    weak_candidates = []

    for a in links:
        text = a.get_text(strip=True).lower()  # visible button text
        href = a['href'].lower()

        if COOKIE in text:
            continue

        # Check contact keywords
        href_match = any(keyword in href for keyword in CONTACT)
        text_match = any(keyword in text for keyword in CONTACT)

        if href_match and text_match:
            strong_candidates.append(a)
        elif href_match or text_match:
            weak_candidates.append(a)

    # Prefer strong match
    candidates = strong_candidates if strong_candidates else weak_candidates

    if not candidates:
        return None, "No contact page found"

    contact_url = candidates[0]['href']
    if contact_url.startswith("/"):
        contact_url = base_url.rstrip("/") + contact_url
    elif not contact_url.startswith("http"):
        contact_url = base_url.rstrip("/") + "/" + contact_url
    
    if not driver:
        contact_html, error = fetch_html(contact_url) 
        
    else: 
        contact_html, error, _ = fetch_html_selenium(driver, contact_url, bypass_gate=False) 
    return extract_email(contact_html, contact_url), error

def save_to_csv(data, filename, headers=None):
    """Saves data to a CSV."""
    if headers is not None:
        df = pd.DataFrame(data, columns=headers)
    else:
        df = pd.DataFrame(data)
    df.drop_duplicates(inplace=True)
    df.to_csv(filename, index=False)

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
