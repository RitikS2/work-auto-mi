import pandas as pd
import requests
from datetime import datetime, date
import calendar

# ==== API Configuration ====
API_URL = "https://api-platform.mastersindia.co/api/v2/saas-apis/irn/"
AUTH_TOKEN = "JWT eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ0b2tlbl90eXBlIjoiYWNjZXNzIiwiZXhwIjoxNzU2NDQyMDEzLCJqdGkiOiI5NGVhZThlMTA1NmQ0NWY3YjU1ZmQ3NzhhYWE1OTM2MiIsInVzZXJfaWQiOjE0OCwidXNlcm5hbWUiOiJwcmF0ZWVrcmFpK2RlbW9AbWFzdGVyc2luZGlhLmNvIiwiZW1haWwiOiJwcmF0ZWVrcmFpK2RlbW9AbWFzdGVyc2luZGlhLmNvIiwib3JnX2lkIjpudWxsfQ.q6-mpUao4KNcGGdP83AmUf01tn2IZqLr-ZPJAFWR-s8"  # Replace with full token
COOKIE = "AWSALB=eDmFkB8IgQviTqXkfj7q1St/C6bKJoeIouYZWIRZZ/liV61/hfxu5TlsBig5CQAgKqapYUOdkqmWpgXI4LjCoCq3Itfv+G5d+sZiXaNYQ3Y3MjVvWUq6tdVgejqj; AWSALBCORS=eDmFkB8IgQviTqXkfj7q1St/C6bKJoeIouYZWIRZZ/liV61/hfxu5TlsBig5CQAgKqapYUOdkqmWpgXI4LjCoCq3Itfv+G5d+sZiXaNYQ3Y3MjVvWUq6tdVgejqj"  # Replace with actual cookie if needed

HEADERS = {
    "Authorization": AUTH_TOKEN,
    "Content-Type": "application/json",
    "Cookie": COOKIE
}

# ==== API Call ====
def fetch_api_data(gstin, month_name, date_from=None, date_to=None, year=2025):
    month_number = list(calendar.month_name).index(month_name.capitalize())
    params = {
        "page": 1,
        "page_size": 2000,
        "year": str(year),
        "month": f"{month_number:02}",
        "irn_type": "purchase"
    }

    if date_from and date_to:
        params["ack_date_from"] = date_from
        params["ack_date_to"] = date_to
    else:
        # If not provided, use default range for current month
        today = date.today()
        if today.month == month_number and today.year == year:
            params["ack_date_from"] = date(year, month_number, 1).strftime("%Y-%m-%d")
            params["ack_date_to"] = today.strftime("%Y-%m-%d")

    headers = HEADERS.copy()
    headers["Gstin"] = gstin
    response = requests.get(API_URL, headers=headers, params=params)
    response.raise_for_status()
    return response.json()

# ==== Response Parser ====
def process_response(resp):
    count = resp.get("count", 0)
    if count == 0:
        return "No Data"
    data_list = resp.get("data", [])

    max_date = None
    for item in data_list:
        doc_date_str = item.get("docDt")
        if doc_date_str:
            try:
                doc_date = datetime.strptime(doc_date_str, "%d/%m/%Y")
                if not max_date or doc_date > max_date:
                    max_date = doc_date
            except ValueError:
                continue

    return f"{count} inv, Data till {max_date.strftime('%d/%m/%Y')}"

# ==== Main Processing Function ====
def process_excel_file(file_path, month_date_map, output_path=None):
    df = pd.read_excel(file_path)
    if "GSTIN" not in df.columns:
        raise ValueError("Excel must have a 'GSTIN' column.")

    for month, dates in month_date_map.items():
        col_name = f"{month.capitalize()} Data"
        df[col_name] = ""

        date_from = dates.get("from")
        date_to = dates.get("to")

        for idx, row in df.iterrows():
            gstin = row["GSTIN"]
            try:
                resp = fetch_api_data(gstin, month, date_from, date_to)
                summary = process_response(resp)
                df.at[idx, col_name] = summary
            except Exception as e:
                df.at[idx, col_name] = f"Error: {str(e)}"

    # Save to output path if given, else overwrite input file
    save_path = output_path or file_path
    df.to_excel(save_path, index=False)
    return save_path