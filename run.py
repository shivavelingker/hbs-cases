'''
This script automates the process of scraping case metadata from HBS and submitting it through a form.

File Instructions:
1. Fill in your HBS email address in the `YOUR_EMAIL` variable down below.
2. Add the case links you want to download in the `CASE_LINKS_TO_DOWNLOAD` list.

Python Setup:
1. Save this code in a folder in a file named `run.py`.
2. Setup your Python by running: "python -m venv venv"
3. Activate the virtual environment by running: "source venv/bin/activate" (Linux/Mac) or "venv\Scripts\activate" (Windows).
4. Install the required packages by running: "pip install -r requirements.txt" (make sure you have a `requirements.txt` file with the necessary libraries).
5. Run the script to scrape metadata and submit the form by running the command: "python run.py"

'''
import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
import time
import os

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# -------------- FILL THIS IN --------------
YOUR_EMAIL = "YOU@mba2025.hbs.edu"

CASE_LINKS_TO_DOWNLOAD = [
    "https://www.hbs.edu/faculty/Pages/item.aspx?num=66865",
    # Add more links here
]

# -------------- LOAD PREVIOUS SUBMISSIONS --------------
OUTPUT_FILE = "output.csv"
if os.path.exists(OUTPUT_FILE):
    df_existing = pd.read_csv(OUTPUT_FILE)
    submitted_links = set(df_existing["URL"].tolist())
else:
    df_existing = pd.DataFrame()
    submitted_links = set()

# -------------- METADATA SCRAPER --------------
def extract_case_data(url, max_retries=3, delay=2):
    for attempt in range(1, max_retries + 1):
        try:
            response = requests.get(url, timeout=10)
            soup = BeautifulSoup(response.text, "html.parser")

            hbs_title = soup.select_one("h1.beta")
            if not hbs_title:
                raise ValueError("Page didn't load properly")

            date_text = soup.select_one("ul.linear.mu-uc.datesource li")
            abstract = soup.select_one("div.description-content")
            author = soup.select_one("h4.kappa")
            citation = soup.select_one("div.mu.light.citation.add-underline")

            case_number = ""
            if citation:
                match = re.search(r"\b(\d{3}-\d{3})\b", citation.text)
                if match:
                    case_number = match.group(1)

            original_date, updated_date = "", ""
            if date_text:
                date_str = date_text.text.strip()
                original_match = re.match(r"([A-Za-z]+ \d{4})", date_str)
                if original_match:
                    original_date = original_match.group(1)
                revised_match = re.search(r"\(Revised ([A-Za-z]+ \d{4})\)", date_str)
                if revised_match:
                    updated_date = revised_match.group(1)

            print(f"[OK] Scraped: {hbs_title.text.strip()}")
            return {
                "URL": url,
                "Case Number": case_number,
                "Title": hbs_title.text.strip(),
                "Date": original_date,
                "Updated": updated_date,
                "Abstract": abstract.text.strip() if abstract else "",
                "Main Author": author.text.strip() if author else "",
            }

        except Exception as e:
            print(f"[Retry {attempt}/{max_retries}] Failed to load {url}: {e}")
            time.sleep(delay)

    print(f"[FAIL] Skipped after {max_retries} attempts: {url}")
    return None

# -------------- BROWSER SETUP --------------
options = webdriver.ChromeOptions()
options.add_argument("--start-maximized")
driver = webdriver.Chrome(options=options)

print("⏳ Waiting for Duo login and page to load...")
driver.get("https://www.library.hbs.edu/databases-cases-and-more/hbs-cases/case-request-form")
WebDriverWait(driver, 60).until(
    lambda d: "Case Request Form" in d.page_source
)
print("✅ Login complete, form page is ready.")

# -------------- MAIN LOOP --------------
for link in CASE_LINKS_TO_DOWNLOAD:
    if link in submitted_links:
        print(f"[SKIP] Already submitted: {link}")
        continue

    metadata = extract_case_data(link)
    if not metadata:
        continue

    try:
        driver.get("https://www.library.hbs.edu/databases-cases-and-more/hbs-cases/case-request-form")
        wait = WebDriverWait(driver, 20)

        # Wait for and switch to iframe
        iframe = wait.until(EC.presence_of_element_located((By.TAG_NAME, "iframe")))
        driver.switch_to.frame(iframe)

        # Fill out the form
        wait.until(EC.presence_of_element_located((By.ID, "element_1"))).send_keys(YOUR_EMAIL)
        driver.find_element(By.ID, "element_2").send_keys(metadata["Case Number"])
        driver.find_element(By.ID, "element_3").send_keys(metadata["Title"])
        checkbox = driver.find_element(By.ID, "element_6_1")
        driver.execute_script("arguments[0].click()", checkbox)

        # Submit
        submit = driver.find_element(By.ID, "submit_form")
        # driver.execute_script("arguments[0].click()", submit)
        time.sleep(5)

        # Confirm
        if "Thank you for submitting your request" in driver.page_source:
            print(f"✅ Submitted: {metadata['Title']}")
            metadata["Status"] = "Requested"
            df_existing = pd.concat([df_existing, pd.DataFrame([metadata])], ignore_index=True)
            df_existing.to_csv(OUTPUT_FILE, index=False)
        else:
            print(f"⚠️ Submission might have failed for: {metadata['Title']}")

        driver.switch_to.default_content()

    except Exception as e:
        print(f"❌ Error on {metadata['Case Number']}: {e}")
        driver.switch_to.default_content()
        continue

driver.quit()
print("🏁 All done.")
