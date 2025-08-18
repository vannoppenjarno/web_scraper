import os
import re
import requests
import pandas as pd
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

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

EMAIL_REGEX = r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+'
BLOCKED_EMAIL_KEYWORDS = ['example', 'noreply']
CONTACT = ['contact', 'kontakt', 'contat']  # 'kapcsolat', 'Επικοινωνια', 'ΕΠΙΚΟΙΝΩΝΙΑ'
GENERIC_EMAIL_KEYWORDS = ['info', 'contact', 'office', 'hello', 'admin', 'mail']

# Age verification keywords (in multiple languages)
AGE_KEYWORDS = ["eres mayor de edad", "are you of legal", "legal drinking age", "вам исполнилось 18", 
                "vous avez plus de 18", "over 18"]

# Cookie wall keywords
COOKIE_KEYWORDS = ["usamos cookies", "acepto", "manage consent", "guardar y aceptar", "cookie policy"]

# Yes/No response indicators
YN_KEYWORDS = ["sí", "si", "yes", "no", "да", "нет"]

# Login wall indicators
# LOGIN_KEYWORDS = ["inicia sesión", "login", "sign in"]



def fetch_html(url, timeout=TIMEOUT,retries=0):
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
            error = f"Connection Error: {e}"

    except requests.exceptions.Timeout:
        error = "Timeout"
        if retries < RETRIES:
            return fetch_html(url, 2*timeout, retries + 1)  # Retry fetching HTML

    except requests.exceptions.RequestException as e:
        error = f"Request Exception: {e}"

    return soup, error

def fetch_html_selenium(url, wait_seconds=2):
    options = Options()
    options.add_argument("--headless")   
    options.add_argument("--no-sandbox")  # Bypass OS security model
    options.add_argument("--disable-dev-shm-usage")  # Overcome limited resource problems
    # options.add_argument('--disable-gpu') # Applicable to Windows OS only
    options.add_argument(f"user-agent={HEADERS['User-Agent']}")
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

    try:
        driver.get(url)
        time.sleep(wait_seconds)                    # simple wait; use WebDriverWait for precision
        html = driver.page_source
        return BeautifulSoup(html, "html.parser"), 200
    except Exception as e:
        return "", f"Selenium error: {e}"
    finally:
        driver.quit()

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

def extract_emails(soup, url):
    """Extracts unique emails from visible text and mailto links in parsed HTML."""
    if not soup:
        return []
    
    # Visible text from all elements
    text = soup.get_text(separator=' ')
    emails = set(clean_email(e) for e in re.findall(EMAIL_REGEX, text))
    
    if not emails:
        for iframe in soup.find_all("iframe"):
            src = iframe.get("src")
            if src:
                iframe_url = urljoin(url, src)
                iframe_soup, _ = fetch_html(iframe_url)
                emails.update(extract_emails(iframe_soup, iframe_url))

    for a in soup.find_all('a'):
        href = a.get('href', '')
        if isinstance(href, str) and href.lower().startswith('mailto:'):
            emails.add(clean_email(href[7:]))  # Remove 'mailto:' prefix

        # anchor visible text can contain emails too
        link_text = a.get_text(strip=True)
        if re.search(EMAIL_REGEX, link_text):
            emails.add(clean_email(link_text))

    return list(filter(is_valid_email, emails))

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

def homepage_fallback(url):
    """Fallback function to get the homepage URL (assuming its the base URL)."""
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}/"

def is_first_visit_page(parsed_text: str) -> bool:
    """
    Check whether the parsed text likely represents a 'first visit' verification page.
    parsed_text: text extracted from HTML (soup.get_text()).
    """
    text = parsed_text.lower()

    # Length check: If the page is extremely short, it’s suspicious
    if len(text) < 50:
        return True

    # Vocabulary size check: If it contains very few distinct words, also suspicious
    words = set(text.split())
    if len(words) < 5:
        return True
    
    # Alternatively, integrate DOM element counting (e.g., if <script> and <iframe> tags dominate, mark as suspicious) = more robust

    # Check for any match
    if any(k in text for k in AGE_KEYWORDS):
        return True
    if any(k in text for k in COOKIE_KEYWORDS):
        return True
    # if any(k in text for k in LOGIN_KEYWORDS):
        # return True
    # Optional: detect high density of yes/no buttons in small page
    if sum(text.count(k) for k in YN_KEYWORDS) >= 2 and len(text) < 3000:
        return True

    return False

def extract_contact_page(soup, base_url):
    """Extracts the contact page URL from the company page."""
    links = soup.find_all("a", href=True)
    contact_url = None
    for a in links:
        text = a.get_text(strip=True).lower()  # visible button text
        if "cookie" in text:
            continue
        href = a['href'].lower()
        for keyword in CONTACT:
            if keyword not in href:
                continue
            contact_url = href
            if contact_url.startswith("/"):
                contact_url = base_url.rstrip("/") + contact_url
            elif not contact_url.startswith("http"):
                contact_url = base_url.rstrip("/") + "/" + contact_url
            break
    return contact_url              

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
