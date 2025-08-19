from .utils import fetch_html, extract_href, extract_company_name, extract_location, extract_emails, select_primary_email, add_company_to_csv, extract_emails_from_contact_page, fetch_html_selenium, homepage_fallback, initialize_selenium_driver
import utils

def collect_company_info(url, config, company_info={}):
    """Recursively collects company info from the current page."""

    if not company_info:
        company_info["links"] = []
        company_info["names"] = []
        company_info["countries"] = []
        company_info["emails"] = []

    html, _ = fetch_html(url)
    hrefs = extract_href(html, config["company_tile_class"]) # if config["company_tile_class"] else extract_href(html, config["company_link_class"])
    
    for href in hrefs:
        try:
            href_url = config["start_url"] + href
            href_html, _ = fetch_html(href_url) # if config["company_tile_class"] else html
            company_link = extract_href(href_html, config["company_link_class"]) # if config["company_tile_class"] else href
            company_link = company_link[0] if company_link and isinstance(company_link, list) else company_link  # Ensure it's a string
            if not company_link or company_link in company_info["links"]:  # Avoid duplicates
                continue

            emails = extract_emails(href_html, href_url)
            if not emails:  # External link logic – if no email on Europages, go to the company’s actual website.
                company_html, error = fetch_html(company_link)

                if not company_html:
                    if not error == "DNS":  
                        add_company_to_csv(company_link, error)  # Troubleshooting: log the error
                    continue
                
                driver = None
                if error == 403:
                    if "Forbidden" in company_html.text:
                        continue  # Skip if the page is forbidden
                    driver = initialize_selenium_driver()
                    company_html, error, driver = fetch_html_selenium(driver, company_link)  # Try selenium for refused requests

                elif error == 404:
                    new_company_link = homepage_fallback(url)
                    if new_company_link == company_link or not new_company_link:
                        # You could also try to add an extra check to exclude unsolvable 404 errors
                        # (e.g., check for homepage button or "error" in the text...)
                        continue
                    company_link = new_company_link
                    company_html, error = fetch_html(company_link)
                
                emails = extract_emails(company_html, company_link)

                if not emails:  # CONTACT PAGE LOGIC (not computationally intensive)
                    emails, error = extract_emails_from_contact_page(company_html, company_link)

                if not emails and not driver:  # SELENIUM (computationally intensive)
                    driver = initialize_selenium_driver()
                    company_html, error, driver = fetch_html_selenium(driver, company_link)  # e.g.: https://vinosonline.es/es/ (could've extracted email from initial page w/ selenium)
                    emails = extract_emails(company_html, company_link)

                if not emails:
                    emails, error = utils.extract_emails_from_contact_page(html, url, driver=driver)

                if not emails:
                    company_html, error, driver = fetch_html_selenium(driver, url=None, bypass_gate=True)  # Try to bypass any gate that might be blocking the request
                    emails = extract_emails(company_html, company_link)

                if not emails:
                    emails, error = extract_emails_from_contact_page(company_html, company_link, driver=driver)  # e.g.: https://vignobleskandler.plugwine.com/

                if not emails:
                    if error != 503:  # No need to log 503 errors as they need no troubleshooting
                        add_company_to_csv(company_link, error)  # error == 200 ==> No email found
                    continue
            
            if driver:
                driver.quit()  # Close the driver if it was used

            email = emails[0] if len(emails) == 1 else select_primary_email(emails, company_link)
        
            company_info["links"].append(company_link)
            company_info["names"].append(extract_company_name(href_html, config["company_name_class"]))
            company_info["countries"].append(extract_location(href_html, config["country_selector"]))
            company_info["emails"].append(email)

        except Exception as e:
            print(f"Failed to extract company link from {config['start_url'] + href}: {e}")
            add_company_to_csv(company_link, str(e))  # Log the error for troubleshooting

    next_url = extract_href(html, config["next_button_class"])
    if next_url:
        return collect_company_info(config["start_url"] + next_url[0], config, company_info)
    return company_info