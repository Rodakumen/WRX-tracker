import re
from bs4 import BeautifulSoup
from typing import List, Dict


def parse_digits(text: str) -> str:
    """Helper function to keep only digits from a string."""
    return "".join(char for char in text if char.isdigit())


def parse_float_digits(text: str) -> str:
    """Helper function to keep digits and decimals, converting commas to periods."""
    normalized = text.replace(",", ".")
    return "".join(char for char in normalized if char.isdigit() or char == ".")


def transform_auto24(soup: BeautifulSoup, url: str = "") -> Dict[str, any]:
    """Transforms auto24.ee single product detail HTML into a uniform dictionary."""
    details = {
        "URL": url,
        "Image URL": "",
        "Title": "",
        "Price (€)": "",
        "Price (kr)": "",
        "Mileage": "",
        "Year": "",
        "Power (kW)": "",
        "Power (Hp)": "",
        "Engine Size (L)": ""
    }

    # 1. Title Extraction
    title_tag = soup.find("h1", class_="commonSubtitle")
    if title_tag:
        raw_text = title_tag.get_text(" ", strip=True)
        cleaned_text = re.sub(r"-\s*Artcar.*|Saved.*|Updated.*", "", raw_text, flags=re.IGNORECASE)
        details["Title"] = cleaned_text.strip()

    # 2. Image URL Extraction
    try:
        image_tag = soup.find("div", class_="topSection__images vImages")
        if image_tag:
            image_url = image_tag.find("img")["src"]
            if "https://" not in image_url:
                details["Image URL"] = ""
            else:
                details["Image URL"] = image_url
    except (AttributeError, TypeError):
        details["Image URL"] = ""


    # 3. Price Extraction (Targeting strictly digits immediately preceding EUR/€)
    price_row = soup.find("tr", class_="field-soodushind") or soup.find("tr", class_="field-hind")
    if price_row:
        raw_price_text = price_row.get_text(" ", strip=True)
        # Matches numbers with spaces/commas that end with EUR or € (e.g. "24,900 EUR")
        price_match = re.search(r"([\d\s.,]+)\s*(?:EUR|€)", raw_price_text, re.IGNORECASE)
        if price_match:
            digits = parse_digits(price_match.group(1))
            details["Price (€)"] = int(digits) if digits else ""

    # 4. Engine Info Parser
    engine_row = soup.find("tr", class_="field-mootorvoimsus")
    if engine_row:
        engine_text = engine_row.get_text(" ", strip=True)

        kw_match = re.search(r"(\d+)\s*kW", engine_text, re.IGNORECASE)
        if kw_match:
            kw_val = int(kw_match.group(1))
            details["Power (kW)"] = kw_val
            details["Power (Hp)"] = round(kw_val * 1.341)

        liters_match = re.search(r"(\d+[.,]\d+|\d+)\s*(?=L|T|\d+\s*kW|kW|\s|$)", engine_text)
        if liters_match:
            matched_val = liters_match.group(1)
            if kw_match and matched_val == kw_match.group(1):
                details["Engine Size (L)"] = ""
            else:
                clean_liters = parse_float_digits(matched_val)
                try:
                    details["Engine Size (L)"] = float(clean_liters) if clean_liters else ""
                except ValueError:
                    details["Engine Size (L)"] = ""

    # 5. Mileage / Odometer Reading
    mileage_row = soup.find("tr", class_="field-labisoit")
    if mileage_row:
        raw_mileage_text = mileage_row.get_text(" ", strip=True)
        # Grab text before the bullet point separator to avoid downstream data pollution
        clean_part = raw_mileage_text.split("·")[0]
        digits = parse_digits(clean_part)
        details["Mileage"] = int(digits) if digits else ""

    # 6. Model Year Extraction
    year_row = soup.find("tr", class_="field-month_and_year")
    if year_row:
        raw_year_text = year_row.get_text(" ", strip=True)
        year_match = re.search(r"(\d{4})\s*$", raw_year_text)
        if year_match:
            details["Year"] = int(year_match.group(1))

    return details


def transform_finn(soup, url="", shadow_price=None) -> Dict[str, any]:
    """Transforms finn.no single product detail HTML into a uniform dictionary."""
    details = {
        "URL": url,
        "Image URL": "",
        "Title": "",
        "Price (€)": "",
        "Price (kr)": "",  # Must completely match the map expected by your Load.py script
        "Mileage": "",
        "Year": "",
        "Power (kW)": "",
        "Power (Hp)": "",
        "Engine Size (L)": ""
    }

    # 1. Title Processing
    h1_title = soup.find("h1", class_="t1")
    p_sub = soup.find("p", class_="s-text-subtle")

    title_parts = []
    if h1_title:
        title_parts.append(h1_title.text.strip())
    if p_sub and "Modellår" not in p_sub.text:
        title_parts.append(p_sub.text.strip())

    details["Title"] = " ".join(title_parts)

    # 2. Image URL Extraction
    try:
        # 1. Find the image (Adjust the find() logic if the 'li' tag doesn't exist)
        img_tag = soup.find("img", id="gallery-image-0")
        srcset = img_tag["srcset"]

        # 2. Get the first URL before the first space
        first_url = srcset.split(",")[0].split(" ")[0]

        details["Image URL"] = first_url
    except (AttributeError, TypeError, KeyError):
        details["Image URL"] = ""

    # 3. Price Extraction (Sanitizing whitespace anomalies)
    if shadow_price:
        digits = parse_digits(shadow_price)
        details["Price (kr)"] = int(digits) if digits else ""

    # 4. Year & Mileage
    for item in soup.find_all("div", class_="flex"):
        label_span = item.find("span", class_="s-text-subtle")
        val_p = item.find("p", class_="font-bold")

        if label_span and val_p:
            lbl = label_span.text.strip()
            val = val_p.text.strip()

            if "Modellår" in lbl:
                details["Year"] = int(val) if val.isdigit() else val
            elif "Kilometerstand" in lbl:
                digits = parse_digits(val)
                details["Mileage"] = int(digits) if digits else ""

    # 5. Engine Capacity and Power Sizing
    dt_elements = soup.find_all("div", style=lambda v: v and "break-inside" in v)
    for block in dt_elements:
        dt = block.find("dt")
        dd = block.find("dd")
        if dt and dd:
            label = dt.text.strip().lower()
            value = dd.text.strip()

            if "slagvolum" in label:
                clean_v = parse_float_digits(value)
                details["Engine Size (L)"] = float(clean_v) if clean_v else ""

            elif "effekt" in label:
                digits = parse_digits(value)
                if digits:
                    hp_val = int(digits)
                    details["Power (Hp)"] = hp_val
                    details["Power (kW)"] = round(hp_val / 1.341)

    return details


def process_raw_htmls(html_inputs: List[Dict[str, str]]) -> List[Dict[str, any]]:
    transformed_dataset = []

    for payload in html_inputs:
        url = payload.get("url", "")
        raw_html = payload.get("html", "")

        if not raw_html:
            continue

        soup = BeautifulSoup(raw_html, "html.parser")

        if "auto24.ee" in url or soup.find(class_=re.compile("auto24")):
            product_data = transform_auto24(soup, url)
            transformed_dataset.append(product_data)
        elif "finn.no" in url or soup.find(attrs={"data-testid": "price"}):
            product_data = transform_finn(soup, url, payload.get("shadow_price"))
            transformed_dataset.append(product_data)
        else:
            print(f"Unknown parser interface required for tracking reference: {url}")

    return transformed_dataset


if __name__ == "__main__":
    # Test execution matching your exact database records
    mock_auto24_html = """
    <h1 class="commonSubtitle"><font dir="auto">Subaru Impreza WRX STI TYPE - RA V-Limited 2.0 T 206kW </font><a href="/infocatalog" class="dealer-name">- Artcar OÜ</a></h1>
    <table class="main-data">
        <tr class="field-month_and_year"><td class="value"><font>09/2011</font></td></tr>
        <tr class="field-mootorvoimsus"><td class="value"><font>2.5 221kW</font></td></tr>
        <tr class="field-labisoit"><td class="value"><font>146,546 km</font></td></tr>
        <tr class="field-hind"><td class="value"><font>24,900 EUR</font></td></tr>
        <tr class="field-soodushind"><td class="value"><font>23,500 EUR</font></td></tr>
    </table>
    """

    mock_finn_html = """
    <h1 class="t1">Subaru Impreza</h1>
    <p class="s-text-subtle">2,5 WRX STi</p>
    <h2 data-testid="price">399 942 kr</h2>
    <div class="flex"><span class="s-text-subtle">Modellår</span><p class="font-bold">2003</p></div>
    <div class="flex"><span class="s-text-subtle">Kilometerstand</span><p class="font-bold">75&nbsp;000 km</p></div>
    <div style="break-inside:avoid-column"><dt class="s-text-subtle">Slagvolum</dt><dd class="t4">2,5 L</dd></div>
    <div style="break-inside:avoid-column"><dt class="s-text-subtle">Effekt</dt><dd class="t4">265 hk</dd></div>
    """

    test_payload = [
        {"url": "https://www.auto24.ee/soidukid/4320477", "html": mock_auto24_html},
        {"url": "https://www.finn.no/mobility/item/466512254", "html": mock_finn_html}
    ]

    results = process_raw_htmls(test_payload)

    print("--- Transformed Output Results ---")
    for car in results:
        print(f"\nSource Location: {car['URL']}")
        for key, val in car.items():
            if key != "URL":
                print(f"  {key}: {val}")