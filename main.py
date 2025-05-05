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
import json
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from webdriver_manager.chrome import ChromeDriverManager
from datetime import datetime
from google.oauth2.service_account import Credentials
from gspread import Cell
from multiprocessing import Pool
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


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
    CHROME_BIN = "/usr/bin/chromium"
    CHROMEDRIVER_BIN = "/usr/bin/chromedriver"

    service = Service(CHROMEDRIVER_BIN)
    return webdriver.Chrome(service=service, options=chrome_options)
def download_and_merge_redfin_data():
    COUNTY_URLS = {
        "Jackson County": "https://www.redfin.com/county/1647/MO/Jackson-County/filter/property-type=house,max-price=200k,min-beds=2,min-sqft=750-sqft,hoa=0,viewport=39.23710209353751:38.83281595697974:-94.10456377540925:-94.60859637048101",
        "Clay County": "https://www.redfin.com/county/1623/MO/Clay-County/filter/property-type=house,max-price=200k,min-beds=2,min-sqft=750-sqft,hoa=0,viewport=39.4561248969278:39.10960168335659:-94.21042181320779:-94.60761308742642",
        "Wyandotte County": "https://www.redfin.com/county/1109/KS/Wyandotte-County/filter/property-type=house,max-price=200k,min-beds=2,min-sqft=750-sqft,hoa=0,viewport=39.20228685639552:38.99083325655661:-94.58967061228006:-94.90928788466434",
        "Cass County": "https://www.redfin.com/county/1618/MO/Cass-County/filter/property-type=house,max-price=200k,min-beds=2,min-sqft=750-sqft,hoa=0,viewport=38.84720367446206:38.4450876188291:-94.06407332564088:-94.61304711807497",
        "Johnson County": "https://www.redfin.com/county/1650/MO/Johnson-County/filter/property-type=house,max-price=200k,min-beds=2,min-sqft=750-sqft,hoa=0,viewport=38.93811156437477:38.55600887794147:-93.49284823885266:-94.12963477619786"
    }

    download_path = os.path.expanduser(r"/app")
    driver = setup_driver(download_path)
    wait = WebDriverWait(driver, 20)
    all_dataframes = []

    def login_redfin():


        ActionChains(driver).move_to_element(download_button).click().perform()
        time.sleep(2)
        print("✅ Logging in")

        print("🔐 Logging into Redfin...")
        email = wait.until(EC.element_to_be_clickable((By.XPATH, '//*[@id="emailInput"]')))
        email.send_keys("jordonmedina708@gmail.com")
        time.sleep(2)

        wait.until(EC.element_to_be_clickable((By.XPATH, '//button/span[contains(text(), "Continue")]'))).click()
        time.sleep(3)

        password = wait.until(EC.element_to_be_clickable((By.XPATH, '//*[@id="passwordInput"]')))
        password.send_keys("jm12345!@#$%")
        time.sleep(2)

        wait.until(EC.element_to_be_clickable((By.XPATH, '//button/span[contains(text(), "Continue")]'))).click()
        time.sleep(5)
        print("✅ Logged in.")

    # Login once on first page
    first_county = next(iter(COUNTY_URLS))
    driver.get(COUNTY_URLS[first_county])
    time.sleep(10)

    try:
        download_button = wait.until(EC.element_to_be_clickable((By.XPATH, '//*[@id="download-and-save"]')))
        driver.execute_script("arguments[0].scrollIntoView();", download_button)
        time.sleep(2)
        driver.find_element(By.TAG_NAME, "body").send_keys(Keys.PAGE_UP)
        time.sleep(random.uniform(1.5, 3))
        driver.execute_script("window.scrollBy(0, 500);")
        login_redfin()
    except Exception as e:
        print("❌ Login failed:", e)
        driver.quit()
        return

    for county, url in COUNTY_URLS.items():
        print(f"🌎 Processing {county}...")
        driver.get(url)
        time.sleep(10)

        try:
            download_button = wait.until(EC.element_to_be_clickable((By.XPATH, '//*[@id="download-and-save"]')))
            driver.execute_script("arguments[0].scrollIntoView();", download_button)
            time.sleep(2)
            driver.find_element(By.TAG_NAME, "body").send_keys(Keys.PAGE_UP)
            time.sleep(random.uniform(1.5, 3))
            driver.execute_script("window.scrollBy(0, 500);")
            ActionChains(driver).move_to_element(download_button).click().perform()
            time.sleep(8)
        except Exception as e:
            print(f"⚠️ Failed to download from {county}: {e}")
            continue

        # Wait and grab the latest CSV
        time.sleep(5)
        try:
            files = sorted(
                [os.path.join(download_path, f) for f in os.listdir(download_path) if f.endswith(".csv")],
                key=os.path.getmtime,
                reverse=True
            )
            latest_file = files[0]

            df = pd.read_csv(latest_file, skiprows=[1])
            df.insert(1, 'County', county)
            all_dataframes.append(df)
            print(f"✅ Processed: {county}")
        except Exception as e:
            print(f"❌ Error processing CSV for {county}: {e}")

    # Merge all dataframes
    if all_dataframes:
        combined_df = pd.concat(all_dataframes, ignore_index=True)
        output_file = os.path.join(download_path, "redfin.csv")
        combined_df.to_csv(output_file, index=False)
        print(f"📁 Merged file saved as: {output_file}")
    else:
        print("⚠️ No data to merge.")

    driver.quit()
    print("🎉 All done!")


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
    download_and_merge_redfin_data()

    # Wait for the CSV file, retrying download if not found
    attempts = 0
    max_attempts = 10
    delay = 5
    while attempts < max_attempts:
        if wait_for_csv(folder_path):
            break  # Exit loop if the CSV is found and renamed

        print(f"🔄 Attempt {attempts + 1}/{max_attempts}: CSV not found, retrying download...")

        # Retry downloading the data
        download_and_merge_redfin_data()

        attempts += 1
        time.sleep(delay)
    else:
        print("❌ No CSV file found after multiple attempts.")

    # Cleanup by quitting the driver
    driver.quit()

user_agent = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

def parse_price(price_str):
    price_str = price_str.replace(",", "").upper()
    if 'K' in price_str:
        return int(float(price_str.replace("K", "")) * 1000)
    return int(price_str)


def get_average_estimate(url):
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--start-maximized")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option("useAutomationExtension", False)
    chrome_options.add_argument(f"user-agent={user_agent}")

    driver = None
    try:
        driver = webdriver.Chrome(service=Service("/usr/bin/chromedriver"), options=chrome_options)
        driver.get(url)

        driver.execute_script("window.scrollTo(0, document.body.scrollHeight / 2);")
        time.sleep(1)
        estimate_element = WebDriverWait(driver, 10).until(
            EC.visibility_of_element_located((By.XPATH, '//*[@id="redfin-estimate"]/div[2]/div[2]'))
        )
        estimate_text = estimate_element.text.strip()
        price_range = re.findall(r"\$([\d,.]+K?)", estimate_text, re.IGNORECASE)
        

        if len(price_range) < 2:
            print(f"[WARNING] Not enough prices found on {url}")
            return None

        lower_price = parse_price(price_range[0])
        higher_price = parse_price(price_range[1])

        average = (lower_price + higher_price) // 2
        print({"URL": url, "average": average})
        return average

    except Exception as e:
        print(f"{url}->Error: \n"
              f"{e}")
        return None
    finally:
        if driver:
            driver.quit()


def scrape_redfin_data(input_csv, output_csv, max_workers=2, max_attempts=3):
    url_column_original = "URL (SEE https://www.redfin.com/buy-a-home/comparative-market-analysis FOR INFO ON PRICING)"

    for attempt in range(max_attempts):
        try:
            if not os.path.exists(input_csv) or os.stat(input_csv).st_size == 0:
                print(f"CSV file missing or empty. Attempt {attempt + 1}/{max_attempts}.")
                time.sleep(5)
                continue

            df = pd.read_csv(input_csv)
            

            if df.empty or df[url_column_original].isna().all():
                print(f"URL column is empty. Attempt {attempt + 1}/{max_attempts}.")
                time.sleep(5)
                continue

            df.rename(columns={url_column_original: "URL"}, inplace=True)
            urls = df["URL"].fillna("").tolist()
            print(f"Starting multiprocessing with {max_workers} workers on {len(urls)} URLs...")

            with Pool(processes=max_workers) as pool:
                average_estimates = pool.map(get_average_estimate, urls)


            # Fix: convert all column names to strings
            df.columns = df.columns.astype(str)

            while len(df.columns) < 29:
                new_col_name = f"ExtraCol_{len(df.columns)+1}"
                print(f"[DEBUG] Adding column: {new_col_name}")
                df[new_col_name] = ""

            df.insert(28, "ARV", average_estimates)

            df.to_csv(output_csv, index=False)
            print(f"✅ Done! Output saved to {output_csv}")
            return

        except Exception as e:
            print(f"Error during processing: {e}")

    print("❌ Max attempts reached. Could not complete scraping.")




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
        creds = Credentials.from_service_account_info(credentials_file, scopes=["https://www.googleapis.com/auth/spreadsheets"])
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
        print(f"❌3 Unexpected error during authentication or sheet access: {e}")
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
        print(f"❌2 Error reading data: {e}")
        return

    try:
        # === 🔹 Preprocess ===
        df_csv = df_csv.drop(columns=["HOA/MONTH"], errors="ignore")
        df_sheet = df_sheet.drop(columns=["HOA/MONTH"], errors="ignore")

        csv_columns = list(df_sheet.columns)
        if "ARV" in csv_columns:
            csv_columns.remove("ARV")
            csv_columns.insert(29, "ARV")
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

        dollar_columns = ["PRICE", "$/SQUARE FEET", "ARV", "OLD PRICE"]
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
        IGNORE_COLUMNS.discard("ARV")
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
            script_url = "https://script.google.com/macros/s/AKfycby82Smixl_KxlVkgfC9UKOgMV5jRC0cr8qxW9kK4FONsoCs0aL-Zai4GxooaLaMyOD6/exec"

            response = requests.post(script_url, json={"action": "addEmptyRow"})
            print(response.text)


    except Exception as e:
        print(f"❌1 An unexpected error occurred: {e}")


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
    SERVICE_ACCOUNT_FILE = json.loads(os.environ["GOOGLE_CREDENTIALS_FILE"])
    SCOPES = ['https://www.googleapis.com/auth/drive.file']
    script_url = "https://script.google.com/macros/s/AKfycby82Smixl_KxlVkgfC9UKOgMV5jRC0cr8qxW9kK4FONsoCs0aL-Zai4GxooaLaMyOD6/exec"


    folder_path = r"/app"
    delete_all_csv()
    download_and_merge_redfin_data()
    input_csv = "redfin.csv"
    output_csv = "redfin.csv"
    scrape_redfin_data(input_csv, output_csv, 1, 5)

    CREDENTIALS_FILE =  SERVICE_ACCOUNT_FILE
    SPREADSHEET_ID = "1lHnsqMM94omtG_WcXhixVPluETrFtZBcRJ-Hpdag5mM"
    SHEET_NAME = "script file"
    CSV_FILE = "redfin.csv"

    sync_redfin_with_google_sheet(CREDENTIALS_FILE,SPREADSHEET_ID,SHEET_NAME,CSV_FILE)
    response = requests.post(script_url, json={"action": "setCheckboxesForMultipleColumns"})
    print(response.text)
    response = requests.get(script_url)

    if response.status_code == 200:
        print("Success:", response.text)
    else:
        print("Error:", response.status_code, response.text)
    # Hide Columns
    response = requests.post(script_url, json={"action": "setCheckboxesForMultipleColumns"})
    print(response.text)
    response = requests.post(script_url, json={"action": "removeBlankRows"})
    print(response.text)  # Should print "Columns Hidden Successfully"
    print("✅ Process completed successfully!")
if __name__ == "__main__":
    
    script_url = "https://script.google.com/macros/s/AKfycby82Smixl_KxlVkgfC9UKOgMV5jRC0cr8qxW9kK4FONsoCs0aL-Zai4GxooaLaMyOD6/exec"
    main()
    response = requests.get(script_url)
    response = requests.post(script_url, json={"action": "setCheckboxesForMultipleColumns"})
    print(response.text)
# Example usage:
