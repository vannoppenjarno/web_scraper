from .utils import fetch_html, extract_href, extract_company_name, extract_location, extract_emails, is_valid_url, select_primary_email, follow_contact_page, fetch_html_selenium

def collect_company_info(url, config, company_info={}, count=0):
    """Recursively collects company info from the current page."""

    if count == 0:
        company_info["links"] = []
        company_info["names"] = []
        company_info["countries"] = []
        company_info["emails"] = []

    html = fetch_html(url)
    hrefs = extract_href(html, config["company_tile_class"]) # if config["company_tile_class"] else extract_href(html, config["company_link_class"])
    
    for href in hrefs:
        try:
            href_html = fetch_html(config["start_url"] + href) # if config["company_tile_class"] else html
            company_link = extract_href(href_html, config["company_link_class"]) # if config["company_tile_class"] else href
            company_link = company_link[0] if company_link and isinstance(company_link, list) else company_link  # Ensure it's a string
            
            if not company_link and company_link in company_info["links"]:  # Avoid duplicates
                continue

            email = extract_emails(href_html)
            if not email:  # External link logic – if no email on Europages, go to the company’s actual website.
                company_html = fetch_html(company_link)
                if not company_html:
                    continue
                # if company_html: #and company_html != 403:
                email = extract_emails(company_html)
                    # email = email if email else follow_contact_page(company_html, company_link)
                # if company_html == 403 or not email:  # If the request fails (403) or not able to extract emails, try Selenium
                    # company_html = fetch_html_selenium(company_link)
                    # email = extract_emails(company_html)
            elif not is_valid_url(company_link):  
                # Check if the extracted company link is valid when the email is found on Europages (which never seems to be the case on Europages)
                continue
            if email:
                email = email[0] if len(email) == 1 else select_primary_email(email, company_link)
            else:
                email = None  # or skip this company with continue
            company_info["links"].append(company_link)
            company_info["names"].append(extract_company_name(href_html, config["company_name_class"]))
            company_info["countries"].append(extract_location(href_html, config["country_selector"]))
            company_info["emails"].append(email)

        except Exception as e:
            print(f"Failed to extract company link from {config['start_url'] + href}: {e}")

    next_url = extract_href(html, config["next_button_class"])
    if next_url and count < config["page_limit"]:  
        return collect_company_info(config["start_url"] + next_url[0], config, company_info, count + 1)
    else:
        # company_links = list(set(company_links))  # Alternative way to remove duplicates 
        return company_info