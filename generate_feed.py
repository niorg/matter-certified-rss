import requests
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

# Base URL for the products
BASE_URL = "https://csa-iot.org/csa-iot_products/"
QUERY_PARAMS = "p_keywords&p_type%5B0%5D=17&p_type%5B1%5D=14&p_type%5B2%5D=1053&p_program_type%5B0%5D=1049&p_certificate&p_family&p_firmware_ver"
NUM_PAGES = 3


def construct_url(page_number):
    """ Construct the URL for the given page. """
    if page_number == 1:
        return f"{BASE_URL}?{QUERY_PARAMS}"
    else:
        return f"{BASE_URL}page/{page_number}/?{QUERY_PARAMS}"


def fetch_page_content(url):
    """Fetch page content using requests."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
    }
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.text


def fetch_certification_details(url):
    """Fetch the certification date and additional details from the product page."""
    try:
        html = fetch_page_content(url)
        soup = BeautifulSoup(html, "html.parser")

        # Find the certification date
        cert_date = "N/A"
        cert_date_tag = soup.find(string="Certified Date")
        if cert_date_tag:
            cert_date_str = cert_date_tag.find_next().text.strip()
            if cert_date_str:
                cert_date = datetime.strptime(cert_date_str, "%m/%d/%Y").replace(
                    hour=0, minute=0, second=0, microsecond=0, tzinfo=timezone.utc
                )
                cert_date = cert_date.strftime('%a, %d %b %Y %H:%M:%S GMT')

        # Fetch additional details
        firmware_version = "N/A"
        hardware_version = "N/A"
        transport_interface = "N/A"
        specification_version = "N/A"

        firmware_version_tag = soup.find(string="Firmware Version")
        if firmware_version_tag:
            firmware_version = firmware_version_tag.find_next().text.strip()

        hardware_version_tag = soup.find(string="Hardware Version")
        if hardware_version_tag:
            hardware_version = hardware_version_tag.find_next().text.strip()

        transport_interface_tag = soup.find(string="Transport Interface")
        if transport_interface_tag:
            transport_interface = transport_interface_tag.find_next().text.strip()

        specification_version_tag = soup.find(string="Specification Version")
        if specification_version_tag:
            specification_version = specification_version_tag.find_next().text.strip()

        # Fetch additional images
        image_tags = soup.find_all("img")
        images = [img["src"] for img in image_tags if img.has_attr("src")]

        details = {
            "cert_date": cert_date,
            "firmware_version": firmware_version,
            "hardware_version": hardware_version,
            "transport_interface": transport_interface,
            "specification_version": specification_version,
            "images": images
        }
        return details

    except Exception as e:
        print(f"Error fetching details for {url}: {e}")
        return {
            "cert_date": "N/A",
            "firmware_version": "N/A",
            "hardware_version": "N/A",
            "transport_interface": "N/A",
            "specification_version": "N/A",
            "images": []
        }


def parse_products(html):
    """ Parse product items from the HTML. """
    soup = BeautifulSoup(html, "html.parser")
    products = []
    product_tiles = soup.find_all("article")

    for tile in product_tiles:
        title_tag = tile.find(["h2", "h3", "h4"])
        title = title_tag.get_text(strip=True) if title_tag else tile.get_text(strip=True)
        learn_more_link = tile.find("a", href=True)
        url = learn_more_link["href"] if learn_more_link else None
        if url and not url.startswith("http"):
            url = "https://csa-iot.org" + url  # Ensure URL is absolute

        image_tag = tile.find("img")
        image_url = image_tag["src"] if image_tag and image_tag.has_attr("src") else None
        description = tile.get_text(" ", strip=True)

        # Exclude 'End Products' items
        if 'End Products' in title:
            continue

        # Fetch certification date and additional details
        if url and "csa_product" in url:
            details = fetch_certification_details(url)
        else:
            details = {
                "cert_date": "N/A",
                "firmware_version": "N/A",
                "hardware_version": "N/A",
                "transport_interface": "N/A",
                "specification_version": "N/A",
                "images": []
            }

        extended_description = (
            f"{description}\n\n"
            f"Firmware Version: {details['firmware_version']}\n"
            f"Hardware Version: {details['hardware_version']}\n"
            f"Transport Interface: {details['transport_interface']}\n"
            f"Specification Version: {details['specification_version']}"
        )

        products.append({
            "title": title,
            "link": url if url else "N/A",
            "image": image_url,
            "description": extended_description,
            "pubDate": details['cert_date'],
            "extra_images": details['images']
        })
    return products


def build_rss(products):
    """ Build an RSS XML string from the list of product dictionaries. """
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
        
        # Include main image
        if prod["image"]:
            ET.SubElement(item, "enclosure", url=prod["image"], type="image/jpeg")

        # Include extra images
        for extra_image in prod["extra_images"]:
            ET.SubElement(item, "enclosure", url=extra_image, type="image/jpeg")

    return ET.tostring(rss, encoding="utf-8", xml_declaration=True)


def main():
    all_products = []
    for page in range(1, NUM_PAGES + 1):
        url = construct_url(page)
        try:
            html = fetch_page_content(url)
            products = parse_products(html)
            all_products.extend(products)
            if len(all_products) >= 36:
                all_products = all_products[:36]  # Limit to 36 products
                break
        except Exception as e:
            print(f"Error processing page {page}: {e}")

    if not all_products:
        print("No products found across pages.")
        return

    rss_feed = build_rss(all_products)
    with open("feed.xml", "wb") as f:
        f.write(rss_feed)
    print("RSS feed created successfully: feed.xml")


if __name__ == "__main__":
    main()
