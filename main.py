import random
import os
import glob
import pandas as pd
import requests
import gspread
import time
import re
from google.auth.exceptions import GoogleAuthError
from gspread.exceptions import APIError
from selenium import webdriver
import json
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
from datetime import datetime
from google.oauth2.service_account import Credentials
from gspread import Cell

def setup_driver(download_dir):
    """Configures and returns a Selenium WebDriver instance."""
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--start-maximized")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option("useAutomationExtension", False)
    chrome_options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

    prefs = {
        "download.default_directory": download_dir,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True
    }
    chrome_options.add_experimental_option("prefs", prefs)

    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=chrome_options)
def download_redfin_data(driver):
    """Automates the Redfin download process."""
    url = "https://www.redfin.com/county/1647/MO/Jackson-County/filter/property-type=house,max-price=200k,min-beds=2,min-sqft=750-sqft,hoa=0,viewport=39.23710209353751:38.83281595697974:-94.10456377540925:-94.60859637048101"
    driver.get(url)
    time.sleep(10)
    wait = WebDriverWait(driver, 20)

    try:
        download_button = wait.until(EC.element_to_be_clickable((By.XPATH, '//*[@id="download-and-save"]')))
        driver.execute_script("arguments[0].scrollIntoView();", download_button)
        time.sleep(2)
        driver.find_element(By.TAG_NAME, "body").send_keys(Keys.PAGE_UP)
        time.sleep(random.uniform(1.5, 3))
        driver.execute_script("window.scrollBy(0, 500);")
        ActionChains(driver).move_to_element(download_button).click().perform()
        time.sleep(2)
        print("✅ Logging in")

        email_field = wait.until(EC.element_to_be_clickable((By.XPATH, '//*[@id="emailInput"]')))
        email_field.send_keys("jordonmedina708@gmail.com")
        time.sleep(2)

        continue_button = wait.until(
            EC.element_to_be_clickable((By.XPATH, '//button/span[contains(text(), "Continue")]')))
        continue_button.click()
        time.sleep(3)

        password_field = wait.until(EC.element_to_be_clickable((By.XPATH, '//*[@id="passwordInput"]')))
        password_field.send_keys("jm12345!@#$%")
        time.sleep(2)

        continue_button = wait.until(
            EC.element_to_be_clickable((By.XPATH, '//button/span[contains(text(), "Continue")]')))
        continue_button.click()
        time.sleep(5)
        print("✅ Logged in successfully!")

        download_button = wait.until(EC.element_to_be_clickable((By.XPATH, '//*[@id="download-and-save"]')))
        driver.execute_script("arguments[0].scrollIntoView();", download_button)
        time.sleep(1)
        driver.find_element(By.TAG_NAME, "body").send_keys(Keys.PAGE_UP)
        time.sleep(random.uniform(1.5, 3))
        driver.execute_script("window.scrollBy(0, 500);")
        ActionChains(driver).move_to_element(download_button).click().perform()
        time.sleep(5)
        print("✅ Download initiated!")
    except Exception as e:
        print("❌ Error during download:", e)


def wait_for_csv(folder_path, new_name="redfin.csv"):
    """Waits for a CSV file and renames it if found."""
    csv_files = [f for f in os.listdir(folder_path) if f.endswith(".csv")]

    if csv_files:
        old_path = os.path.join(folder_path, csv_files[0])
        new_path = os.path.join(folder_path, new_name)
        os.rename(old_path, new_path)
        print(f"✅ Renamed '{csv_files[0]}' to '{new_name}'")
        return True  # CSV file found and renamed
    else:
        print("🔄 No CSV file found.")
        return False  # No CSV file found


def automate_redfin(folder_path):
    """Main function to automate Redfin download and CSV renaming."""
    driver = setup_driver(folder_path)

    # First attempt to download data
    download_redfin_data(driver)

    # Wait for the CSV file, retrying download if not found
    attempts = 0
    max_attempts = 10
    delay = 5
    while attempts < max_attempts:
        if wait_for_csv(folder_path):
            break  # Exit loop if the CSV is found and renamed

        print(f"🔄 Attempt {attempts + 1}/{max_attempts}: CSV not found, retrying download...")

        # Retry downloading the data
        download_redfin_data(driver)

        attempts += 1
        time.sleep(delay)
    else:
        print("❌ No CSV file found after multiple attempts.")

    # Cleanup by quitting the driver
    driver.quit()


def scrape_redfin_data(input_csv, output_csv, folder_path, max_attempts=3):
    """Scrapes Redfin data and retries downloading if the CSV URL column is empty."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.redfin.com/"
    }

    url_column = "URL (SEE https://www.redfin.com/buy-a-home/comparative-market-analysis FOR INFO ON PRICING)"

    for attempt in range(max_attempts):
        try:
            if not os.path.exists(input_csv) or os.stat(input_csv).st_size == 0:
                print(f"⚠️ CSV file missing or empty. Attempt {attempt + 1}/{max_attempts} to redownload.")
                automate_redfin(folder_path)
                time.sleep(5)
                continue

            df = pd.read_csv(input_csv)
            if df.empty or df[url_column].isna().all():
                print(f"⚠️ URL column is empty. Attempt {attempt + 1}/{max_attempts} to redownload.")
                automate_redfin(folder_path)
                time.sleep(5)
                continue

            df = df.drop(index=0, errors='ignore')
            df["URL_BACKUP"] = df[url_column]
            df["avg ARV/sqft"] = None  # Ensure the column exists

            for index, row in df.iterrows():
                url = row.get(url_column, "").strip()
                if not url:
                    df.at[index, "avg ARV/sqft"] = "No URL"
                    print(f"⚠️ Skipping row {index + 1}, no URL found.")
                    continue

                print(f"🔍 Processing {index + 1}/{len(df)}: {url}")

                try:
                    response = requests.get(url, headers=headers, timeout=10)

                    if response.status_code == 200:
                        soup = BeautifulSoup(response.text, "html.parser")
                        nearby_span = soup.find(
                            lambda tag: tag.name == "span" and "Nearby homes similar to" in tag.text)

                        if nearby_span:
                            match = re.search(r"at an average of \$(\d+)", nearby_span.text.strip())
                            df.at[index, "avg ARV/sqft"] = f"${match.group(1)}" if match else "N/A"
                            print(f"✅ Found AVG/sqft: {df.at[index, 'avg ARV/sqft']}")
                        else:
                            df.at[index, "avg ARV/sqft"] = "N/A"
                            print("⚠️ 'Nearby homes similar' span not found.")
                    else:
                        df.at[index, "avg ARV/sqft"] = "Request Failed"
                        print(f"❌ Request failed with status code: {response.status_code}")
                except Exception as e:
                    df.at[index, "avg ARV/sqft"] = f"Error: {str(e)}"
                    print(f"❌ Error occurred: {str(e)}")

                time.sleep(1)  # Delay to avoid getting blocked

            df["URL"] = df["URL_BACKUP"]
            df.drop(columns=["URL_BACKUP"], inplace=True)
            df.to_csv(output_csv, index=False)
            print(f"✅ Scraping completed! Results saved to {output_csv}")
            return
        except Exception as e:
            print(f"❌ Error processing CSV: {str(e)}")

    print("❌ Max attempts reached. Could not process the CSV.")


def format_dollar_column(col_series):
    formatted = []
    for val in col_series.fillna("").astype(str):
        val_clean = val.replace(',', '').replace('$', '')
        if val_clean.replace('.', '', 1).isdigit():
            try:
                formatted.append(f"${int(float(val_clean)):,}")
            except:
                formatted.append(val)
        else:
            formatted.append(val)
    return formatted



def sync_redfin_with_google_sheet(
    credentials_file: str,
    spreadsheet_id: str,
    sheet_name: str,
    csv_file: str
):
    try:
        # === 🔹 Authenticate and Access Google Sheets ===
        creds = Credentials.from_service_account_file(credentials_file, scopes=["https://www.googleapis.com/auth/spreadsheets"])
        client = gspread.authorize(creds)
        sheet = client.open_by_key(spreadsheet_id).worksheet(sheet_name)

    except FileNotFoundError:
        print(f"❌ Credentials file '{credentials_file}' not found.")
        return
    except GoogleAuthError as e:
        print(f"❌ Authentication error: {e}")
        return
    except APIError as e:
        print(f"❌ Google Sheets API error: {e}")
        return
    except Exception as e:
        print(f"❌ Unexpected error during authentication or sheet access: {e}")
        return

    try:
        # === 🔹 Load Data ===
        data = sheet.get_all_values()
        df_sheet = pd.DataFrame(data[1:], columns=data[0])  # First row as headers
        df_csv = pd.read_csv(csv_file, dtype=str)

    except FileNotFoundError:
        print(f"❌ CSV file '{csv_file}' not found.")
        return
    except Exception as e:
        print(f"❌ Error reading data: {e}")
        return

    try:
        # === 🔹 Preprocess ===
        df_csv = df_csv.drop(columns=["HOA/MONTH"], errors="ignore")
        df_sheet = df_sheet.drop(columns=["HOA/MONTH"], errors="ignore")

        csv_columns = list(df_sheet.columns)
        if "avg ARV/sqft" in csv_columns:
            csv_columns.remove("avg ARV/sqft")
            csv_columns.insert(28, "avg ARV/sqft")
        if "OLD PRICE" not in df_csv.columns:
            df_csv["OLD PRICE"] = ""
        if "OLD PRICE" in df_sheet.columns:
            old_price_mapping = df_sheet.set_index(["ADDRESS", "YEAR BUILT"])["OLD PRICE"].to_dict()
            df_csv["OLD PRICE"] = df_csv.apply(
                lambda row: old_price_mapping.get((row["ADDRESS"], row["YEAR BUILT"]), row["OLD PRICE"]),
                axis=1
            )

        df_csv = df_csv.reindex(columns=csv_columns, fill_value="")
        df_csv.to_csv(csv_file, index=False)
        df_csv = pd.read_csv(csv_file, dtype=str)

        # === 🔹 Data Formatting ===
        integer_columns = ["ZIP OR POSTAL CODE", "SQUARE FEET", "LOT SIZE", "DAYS ON MARKET"]
        for col in integer_columns:
            if col in df_csv.columns:
                df_csv[col] = pd.to_numeric(df_csv[col], errors="coerce").fillna(0).astype(int).astype(str)

        if "YEAR BUILT" in df_csv.columns:
            df_csv["YEAR BUILT"] = df_csv["YEAR BUILT"].apply(
                lambda x: str(int(float(x))) if pd.notna(x) and x.strip() != "" else "")

        dollar_columns = ["PRICE", "$/SQUARE FEET", "avg ARV/sqft", "OLD PRICE"]
        for col in dollar_columns:
            if col in df_csv.columns:
                print(f"🔹 Formatting {col}")
                df_csv[col] = format_dollar_column(df_csv[col])

        # === 🔹 Clean and Prepare ===
        df_csv = df_csv[df_csv["ADDRESS"].notna() & df_csv["ADDRESS"].str.strip().ne("")]
        df_csv = df_csv.drop_duplicates(subset=["ADDRESS", "YEAR BUILT"], keep="first")
        df_sheet = df_sheet[df_sheet["ADDRESS"].notna() & df_sheet["ADDRESS"].str.strip().ne("")]
        df_sheet = df_sheet.drop_duplicates(subset=["ADDRESS", "YEAR BUILT"], keep="first")
        df_csv = df_csv.fillna("")
        df_sheet = df_sheet.fillna("")

        if "ADDRESS" not in df_csv.columns or "YEAR BUILT" not in df_csv.columns:
            print("❌ Required columns 'ADDRESS' or 'YEAR BUILT' are missing from CSV.")
            return

        IGNORE_COLUMNS = set(df_sheet.columns[18:32])
        IGNORE_COLUMNS.add("rejected")  # AT
        IGNORE_COLUMNS.add("interested/offer submitted")  # AU
        IGNORE_COLUMNS.add("copy offers")  # AV
        IGNORE_COLUMNS.discard("URL")
        IGNORE_COLUMNS.discard("avg ARV/sqft")
        # === 🔹 Add New Listings ===
        new_entries = df_csv[
            ~df_csv.set_index(["ADDRESS", "YEAR BUILT"]).index.isin(df_sheet.set_index(["ADDRESS", "YEAR BUILT"]).index)
        ]

        if not new_entries.empty:
            print(f"\n🆕 Found {len(new_entries)} new entries. Adding them to Google Sheets...")
            new_entries["added date"] = datetime.now().strftime('%m/%d/%Y')
            new_entries = new_entries[csv_columns]

            col_a = sheet.col_values(1)
            start_row = next((i + 1 for i, v in enumerate(col_a) if not v.strip()), len(col_a) + 1)
            end_row = start_row + len(new_entries) - 1
            end_col_letter = gspread.utils.rowcol_to_a1(1, len(csv_columns)).split("1")[0]
            cell_range = f"A{start_row}:{end_col_letter}{end_row}"

            values = new_entries.values.tolist()
            sheet.update(cell_range, values, value_input_option="RAW")
            print(f"✅ Added {len(values)} new entries to rows {start_row} to {end_row}.")

        # === 🔹 Update Existing Rows ===
        cells_to_update = []
        updates_log = []

        for sheet_idx, sheet_row in df_sheet.iterrows():
            key_address = sheet_row.get("ADDRESS", "").strip()
            key_year_built = sheet_row.get("YEAR BUILT", "").strip()

            matched_rows = df_csv[(df_csv["ADDRESS"] == key_address) & (df_csv["YEAR BUILT"] == key_year_built)]
            if matched_rows.empty:
                continue

            csv_row = matched_rows.iloc[0]

            for col in csv_columns:
                if col in ["ADDRESS", "YEAR BUILT", "added date"] or col in IGNORE_COLUMNS:
                    continue

                sheet_value = str(sheet_row.get(col, "")).strip()
                csv_value = str(csv_row.get(col, "")).strip()

                if sheet_value.lower() == "nan":
                    sheet_value = ""
                if csv_value.lower() == "nan":
                    csv_value = ""

                if col == "PRICE" and sheet_value != csv_value:
                    old_price_col_index = csv_columns.index("OLD PRICE") + 1
                    row_index = sheet_idx + 2
                    cells_to_update.append(
                        Cell(row_index, old_price_col_index, sheet_value))  # Save old price before updating
                    updates_log.append(f"Row {row_index}: OLD PRICE set to '{sheet_value}'")
                if sheet_value != csv_value:
                    row_index = sheet_idx + 2
                    col_index = csv_columns.index(col) + 1
                    cells_to_update.append(Cell(row_index, col_index, csv_value))
                    updates_log.append(f"Row {row_index}: {col} updated to '{csv_value}' (Old: '{sheet_value}')")

        if cells_to_update:
            sheet.update_cells(cells_to_update, value_input_option="RAW")
            print("\n🔄 Update Log:")
            for log in updates_log:
                print(log)
            print(f"\n✅ Update complete! {len(cells_to_update)} cells updated.")
        else:
            print("✅ No updates needed.")

    except KeyError as e:
        print(f"❌ Key error: Missing expected column {e}")
    except PermissionError:
        print("❌ Permission denied while reading or writing files.")
    except APIError as e:

        print(f"❌ Google Sheets API error during update: {e}")
        if "exceeds grid limits" in str(e):
            script_url = "https://script.google.com/macros/s/AKfycbxSySb5SAv5Gl1Z5Gxb4jfHpMoDjCxBn8TAsjVli4RreWf_clqLJ3WkHkbvkEVzoqCD/exec"

            response = requests.get(script_url)

            if response.status_code == 200:
                print("Success:", response.text)
                sync_redfin_with_google_sheet(credentials_file, spreadsheet_id, sheet_name, csv_file)
            else:
                print("Error:", response.status_code, response.text)


    except Exception as e:
        print(f"❌ An unexpected error occurred: {e}")


def delete_all_csv():
    """Deletes all CSV files in the current directory."""
    csv_files = glob.glob("*.csv")
    for file in csv_files:
        try:
            os.remove(file)
            print(f"🗑️ Deleted: {file}")
        except WindowsError as e:
            print(f" ⚠️ Error deleting {file}: {e}. Please ensure the file is closed.")
            input("Press Enter if closed")
            delete_all_csv()
        except Exception as e:
            print(f"⚠️ Error deleting {file}: {e}")



# === MAIN EXECUTION ===
def main():
    SERVICE_ACCOUNT_FILE = json.loads(os.environ["GOOGLE_CREDENTIALS"])
    SCOPES = ['https://www.googleapis.com/auth/drive.file']


    # Example: Load credentials in your code



    script_url = "https://script.google.com/macros/s/AKfycbxSySb5SAv5Gl1Z5Gxb4jfHpMoDjCxBn8TAsjVli4RreWf_clqLJ3WkHkbvkEVzoqCD/exec"
    response = requests.post(script_url, json={"action": "unhideColumns"})
    print(response.text)  # Should print "Columns Unhidden Successfully"


    folder_path = r"/app"
    delete_all_csv()
    automate_redfin(folder_path)
    input_csv = "redfin.csv"
    output_csv = "redfin.csv"
    scrape_redfin_data(input_csv, output_csv, folder_path, 5)

    CREDENTIALS_FILE =  SERVICE_ACCOUNT_FILE
    SPREADSHEET_ID = "1lHnsqMM94omtG_WcXhixVPluETrFtZBcRJ-Hpdag5mM"
    SHEET_NAME = "redfin_2025-03-01-22-36-12"
    CSV_FILE = "redfin.csv"

    sync_redfin_with_google_sheet(CREDENTIALS_FILE,SPREADSHEET_ID,SHEET_NAME,CSV_FILE)
    print("✅ Process completed successfully!")

    response = requests.get(script_url)

    if response.status_code == 200:
        print("Success:", response.text)
    else:
        print("Error:", response.status_code, response.text)
    # Hide Columns

    response = requests.post(script_url, json={"action": "hideColumns"})
    print(response.text)  # Should print "Columns Hidden Successfully"
    response = requests.post(script_url, json={"action": "removeBlankRows"})
    print(response.text)  # Should print "Columns Hidden Successfully"

if __name__ == "__main__":
    main()

# Example usage:
