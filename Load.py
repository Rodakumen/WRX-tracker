import os
import logging
import smtplib
import psycopg2
from psycopg2 import Error
from dotenv import load_dotenv
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from Transform import process_raw_htmls
from Extract import get_raw_html_and_links, get_bulk_pages_html


load_dotenv()


def connect_to_db():
    try:
        # Ingen hardkodede passord her lenger!
        return psycopg2.connect(
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            host=os.getenv("DB_HOST"),
            port=os.getenv("DB_PORT"),
            database=os.getenv("DB_NAME")
        )
    except (Exception, Error) as error:
        logging.error(f"Database connection failed: {error}")
        return None


def send_gmail_notification(car_details, status="NEW"):
    sender_email = os.getenv("GMAIL_USER")
    receiver_email = os.getenv("GMAIL_RECEIVER")
    app_password = os.getenv("GMAIL_APP_PASSWORD")

    if not all([sender_email, receiver_email, app_password]):
        logging.error("Email environment variables missing. Cannot send alert.")
        return

    msg = MIMEMultipart('alternative')
    msg['From'] = sender_email
    msg['To'] = receiver_email

    is_finn = "finn.no" in car_details.get('URL', '').lower()
    price_suffix = "kr (NOK)" if is_finn else "€"
    price_val = car_details.get('Price (kr)') if is_finn else car_details.get('Price (€)')
    image_url = car_details.get('Image_URL') or 'https://via.placeholder.com/400x250?text=No+Image+Found'

    if status == "NEW":
        msg['Subject'] = f"🚨 NY SUBARU WRX STI: {price_val} {price_suffix}"
        headline = "Ny bil funnet i overvåkingen!"
        price_html = f"<strong>Pris:</strong> {price_val} {price_suffix}"
    elif status == "PRICE_DROP":
        msg['Subject'] = f"📉 PRISFALL: {car_details.get('Title')} er satt ned!"
        headline = "Prisreduksjon registrert!"
        price_html = f"<strong>Ny pris:</strong> <span style='color:green;'>{price_val} {price_suffix}</span> (Var: {car_details.get('Old Price')} {price_suffix})"
    else:
        msg['Subject'] = f"🔺 PRISØKNING: {car_details.get('Title')} har gått opp"
        headline = "Prisen har økt på denne bilen"
        price_html = f"<strong>Ny pris:</strong> <span style='color:red;'>{price_val} {price_suffix}</span> (Var: {car_details.get('Old Price')} {price_suffix})"

    html_body = f"""
    <html>
      <body style="font-family: Arial, sans-serif; color: #333;">
        <h2 style="color: #023e8a;">{headline}</h2>
        <p><strong>Modell:</strong> {car_details.get('Title')}</p>
        <p>{price_html}</p>
        <p><strong>Kilometerstand:</strong> {car_details.get('Mileage')} km</p>
        <p><strong>Årsmodell:</strong> {car_details.get('Year')}</p>
        <p><strong>Hestekrefter:</strong> {car_details.get('Power (Hp)')} hk</p>
        <br>
        <div style="max-width: 500px;">
            <img src="{image_url}" alt="Subaru WRX" style="width: 100%; height: auto; border-radius: 8px;">
        </div>
        <br>
        <p><a href="{car_details.get('URL')}" style="background-color: #0077b6; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; display: inline-block;">Se annonsen</a></p>
      </body>
    </html>
    """
    msg.attach(MIMEText(html_body, 'html'))

    try:
        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()
            server.login(sender_email, app_password)
            server.send_message(msg)
        logging.info(f"Email notification ({status}) successfully dispatched.")
    except Exception as e:
        logging.error(f"Failed to dispatch email: {e}")


def load_data():
    index_search_urls = [
        "https://www.auto24.ee/kasutatud/nimekiri.php?bn=2&a=100&c=Impreza&ae=8&af=50&ssid=282991690",
        "https://www.finn.no/mobility/search/car?q=subaru+wrx"
    ]

    # STEP 1 & 2: EXTRACT USING RE-ENGINEERED BULK FLYT
    product_links = get_raw_html_and_links(index_search_urls)
    if not product_links:
        logging.warning("No product links gathered. Exiting pipeline.")
        return

    # Kaller den nye raske bulk-funksjonen
    html_payloads = get_bulk_pages_html(product_links)

    # STEP 3: TRANSFORM
    car_products = process_raw_htmls(html_payloads)
    logging.info(f"Transformation complete. Prepared {len(car_products)} entities.")

    connection = connect_to_db()
    if not connection:
        return

    # Ved å bruke 'with', vil cursor og connection LUKKES automatisk uansett feil!
    try:
        with connection:
            with connection.cursor() as cursor:

                # Tabelloppretting (Uten UNIQUE på image_url!)
                cursor.execute("""
                               CREATE TABLE IF NOT EXISTS subaru_prices
                               (
                                   id
                                   SERIAL
                                   PRIMARY
                                   KEY,
                                   url
                                   TEXT
                                   UNIQUE,
                                   image_url
                                   TEXT,
                                   title
                                   VARCHAR
                               (
                                   255
                               ),
                                   price_eur INT,
                                   price_nok INT,
                                   mileage INT,
                                   year INT,
                                   power_kw INT,
                                   power_hp INT,
                                   engine_size_l FLOAT,
                                   date_registered TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                                   );
                               """)

                insert_query = """
                               INSERT INTO subaru_prices AS old (url, title, image_url, price_eur, price_nok, mileage, year, power_kw, power_hp, engine_size_l)
                               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                               ON CONFLICT (url) DO \
                               UPDATE SET
                                   title = EXCLUDED.title, \
                                   image_url = EXCLUDED.image_url, \
                                   price_eur = EXCLUDED.price_eur, \
                                   price_nok = EXCLUDED.price_nok, \
                                   mileage = EXCLUDED.mileage, \
                                   year = EXCLUDED.year, \
                                   power_kw = EXCLUDED.power_kw, \
                                   power_hp = EXCLUDED.power_hp, \
                                   engine_size_l = EXCLUDED.engine_size_l, \
                                   date_registered = CURRENT_TIMESTAMP \
                                   RETURNING (xmax = 0) AS is_new_insert, old.price_eur, old.price_nok;
                               """

                def safe_int(val):
                    if val in (None, ""): return None
                    try:
                        cleaned = "".join(char for char in str(val) if char.isdigit())
                        return int(cleaned) if cleaned else None
                    except:
                        return None

                for car in car_products:
                    url_str = car.get("URL", "").lower()
                    is_finn = "finn.no" in url_str
                    eur_val = None if is_finn else car.get('Price (€)')
                    nok_val = car.get('Price (kr)') if is_finn else None
                    actual_image_url = car.get("Image_URL") or car.get("Image URL")

                    car["Image_URL"] = actual_image_url

                    car_data = (
                        car.get("URL"),
                        car.get("Title"),
                        actual_image_url,
                        safe_int(eur_val),
                        safe_int(nok_val),
                        safe_int(car.get('Mileage')),
                        safe_int(car.get('Year')),
                        safe_int(car.get('Power (kW)')),
                        safe_int(car.get('Power (Hp)')),
                        float(car.get('Engine Size (L)')) if car.get('Engine Size (L)') not in (None, "") else None
                    )

                    cursor.execute(insert_query, car_data)
                    row = cursor.fetchone()
                    is_new, old_eur, old_nok = row[0], row[1], row[2]

                    new_price = safe_int(nok_val) if is_finn else safe_int(eur_val)
                    old_price = old_nok if is_finn else old_eur

                    if is_new:
                        logging.info(f"New asset verified. Dispatched alert for: {car.get('Title')}")
                        # send_gmail_notification(car, status="NEW")
                    elif old_price is not None and new_price != old_price:
                        logging.info(
                            f"Price volatility detected for {car.get('Title')}. Old: {old_price} -> New: {new_price}")
                        car["Old Price"] = old_price
                        # send_gmail_notification(car, status="PRICE_DROP" if new_price < old_price else "PRICE_RISE")

        logging.info("Pipeline executed successfully. All connections closed contextually.")

    except (Exception, Error) as error:
        logging.error(f"Critical pipeline fault inside database operation: {error}")


if __name__ == "__main__":
    load_data()