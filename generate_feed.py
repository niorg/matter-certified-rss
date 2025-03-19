#!/usr/bin/env python3
import time
from datetime import datetime, timezone
import xml.etree.ElementTree as ET

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

# Base URL for the products (without #fragment)
BASE_URL = "https://csa-iot.org/csa-iot_products/"
# Query parameters (do not include the hash fragment here)
QUERY_PARAMS = "p_keywords&p_type%5B0%5D=17&p_type%5B1%5D=14&p_type%5B2%5D=1053&p_program_type%5B0%5D=1049&p_certificate&p_family&p_firmware_ver"
# Number of pages to scrape
NUM_PAGES = 3

def construct_url(page_number):
    """
    Construct the URL for the given page.
    For page 1, we use:
      BASE_URL?{QUERY_PARAMS}
    For page 2+, we assume the format:
      BASE_URL/page/{page_number}/?{QUERY_PARAMS}
    """
    if page_number == 1:
        return f"{BASE_URL}?{QUERY_PARAMS}"
    else:
        return f"{BASE_URL}page/{page_number}/?{QUERY_PARAMS}"

def fetch_page_selenium(url, driver):
    """Fetch page source using Selenium and wait for JavaScript to load."""
    driver.get(url)
    # Wait for the page's JavaScript to load content.
    # Adjust this if needed (or use WebDriverWait for a more robust solution)
    time.sleep(3)
    return driver.page_source

def parse_products(html):
    """
    Parse product items from the HTML.
    This function first tries to use <article> tags.
    If not found, it looks for parent containers of any "Learn More" links.
    """
    soup = BeautifulSoup(html, "html.parser")
    products = []

    # Try finding articles first
    product_tiles = soup.find_all("article")
    if not product_tiles:
        # Fallback: select elements that contain a "Learn More" link
        product_tiles = []
        for link in soup.find_all("a", string=lambda t: t and "Learn More" in t):
            parent = link.find_parent()
            if parent and parent not in product_tiles:
                product_tiles.append(parent)

    for tile in product_tiles:
        # Extract title: look for a header tag (h2, h3, h4) or fallback to tile text.
        title_tag = tile.find(["h2", "h3", "h4"])
        title = title_tag.get_text(strip=True) if title_tag else tile.get_text(strip=True)
        
        # Extract the "Learn More" link as the product URL.
        learn_more_link = tile.find("a", string=lambda t: t and "Learn More" in t)
        url = learn_more_link["href"] if learn_more_link and learn_more_link.has_attr("href") else None
        
        # Try to extract an image URL from any <img> tag.
        image_tag = tile.find("img")
        image_url = image_tag["src"] if image_tag and image_tag.has_attr("src") else None

        # Build a simple description via the tile's text.
        description = tile.get_text(" ", strip=True)

        products.append({
            "title": title,
            "link": url or "N/A",
            "image": image_url,
            "description": description,
            "pubDate": datetime.now(timezone.utc).strftime('%a, %d %b %Y %H:%M:%S GMT')
        })
    return products

def build_rss(products):
    """
    Build an RSS XML string from the list of product dictionaries.
    """
    rss = ET.Element("rss", version="2.0")
    channel = ET.SubElement(rss, "channel")

    ch_title = ET.SubElement(channel, "title")
    ch_title.text = "CSA-IoT Certified Products Feed"

    ch_link = ET.SubElement(channel, "link")
    ch_link.text = f"{BASE_URL}?{QUERY_PARAMS}"

    ch_description = ET.SubElement(channel, "description")
    ch_description.text = "An RSS feed of CSA-IoT certified products with images scraped from multiple pages."

    ch_lastBuildDate = ET.SubElement(channel, "lastBuildDate")
    ch_lastBuildDate.text = datetime.now(timezone.utc).strftime('%a, %d %b %Y %H:%M:%S GMT')

    for prod in products:
        item = ET.SubElement(channel, "item")
        ET.SubElement(item, "title").text = prod["title"]
        ET.SubElement(item, "link").text = prod["link"]
        ET.SubElement(item, "description").text = prod["description"]
        ET.SubElement(item, "pubDate").text = prod["pubDate"]
        if prod["image"]:
            ET.SubElement(item, "enclosure", url=prod["image"], type="image/jpeg")

    return ET.tostring(rss, encoding="utf-8", xml_declaration=True)

def main():
    # Set up Selenium Chrome in headless mode with a custom user agent.
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    # Set a custom user agent to mimic a standard desktop browser.
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                "AppleWebKit/537.36 (KHTML, like Gecko) "
                                "Chrome/115.0.0.0 Safari/537.36")

    driver = webdriver.Chrome(options=chrome_options)

    all_products = []
    for page in range(1, NUM_PAGES + 1):
        url = construct_url(page)
        print(f"Fetching: {url}")
        try:
            html = fetch_page_selenium(url, driver)
            # Optionally check for a string indicating a forbidden request
            if "403 Forbidden" in html:
                print(f"403 Forbidden encountered on {url}")
                continue

            products = parse_products(html)
            print(f"Found {len(products)} products on page {page}")
            all_products.extend(products)
        except Exception as e:
            print(f"Error processing page {page}: {e}")

    driver.quit()

    if not all_products:
        print("No products found across pages.")
        return

    rss_feed = build_rss(all_products)
    with open("feed.xml", "wb") as f:
        f.write(rss_feed)
    print("RSS feed created successfully: feed.xml")

if __name__ == "__main__":
    main()
