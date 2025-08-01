from src.utils import save_to_csv, initialize_driver#, search_sector
from src.scraper import collect_company_info

WEBSITES = {
    "europages": {
        "start_url": "https://www.europages.co.uk/",
        "search_url": "https://www.europages.co.uk/en/search?q=",
        "sectors": ["winery"],
        # "sectors": ["winery", "real estate", "construction", "software", "consulting"],
        "search_selector": "input[name='q']",
        "company_tile_class": "flex items-center justify-center overflow-hidden rounded-sm bg-white hover:no-underline border border-navy-10 ep:border-darkgreen-10 p-0.5",
        "company_link_class": "btn btn--subtle btn--md website-button",
        "company_name_class": "company-name mt-1.5 mb-0.5 font-display-500 text-neutral-100 hover:no-underline",
        "country_selector": "div.flex.gap-1.items-center.mt-0\\.5 > span:nth-of-type(2)",
        "next_button_class": "button next", 
        "page_limit": 2,  # Limit to 2 pages for efficient testing
    }
}

# driver = initialize_driver()
config = WEBSITES["europages"]

for sector in config["sectors"]:
    # driver.get(config["start_url"])
    # search_sector(driver, sector, config["search_selector"])
    # info = collect_company_info(driver.current_url, config)
    info = collect_company_info(config["search_url"] + sector, config)
    
    # Save links to CSV
    save_to_csv(info["links"], f"output/links_{sector}.csv", headers=["url"])

    # Save names, countries, and emails to CSV
    data = {"name": info["names"], "country": info["countries"], "email": info["emails"]}
    save_to_csv(data, f"output/emails_{sector}.csv", headers=["name", "country", "email"])

# driver.quit()