import requests
import pandas as pd
import asyncio
import aiohttp
from twelvedata import TDClient
import nasdaqdatalink
import time
import sqlite3
import configparser
from datetime import datetime, date
from concurrent.futures import ThreadPoolExecutor
import json


class ProgressTracker:
    def __init__(self):
        self.processed = 0
        self.total = 0
        self.start_time = None
        self.request_count = 0

    def start(self, total):
        self.total = total
        self.start_time = time.time()
        print(f"\nStarting scan of {total} stocks...")

    def update(self, batch_size, requests_made):
        self.processed += batch_size
        self.request_count += requests_made
        elapsed = time.time() - self.start_time
        rate = self.processed / elapsed * 60 if elapsed > 0 else 0
        print(
            f"Processed {self.processed}/{self.total} stocks. Rate: {rate:.1f} stocks/minute. Requests: {self.request_count}")


async def fetch_stock_data_direct(session, apikey, ticker, today):
    try:
        today_url = f"https://api.twelvedata.com/time_series?symbol={ticker}&interval=5min&outputsize=78&apikey={apikey}"
        async with session.get(today_url) as response:
            today_data = await response.json()
            if 'values' not in today_data:
                return None, 1

            values = today_data['values']
            if not values:
                return None, 1

            today_prices = [float(v['high']) for v in values]
            today_volumes = [float(v['volume']) for v in values]

            daily_high = max(today_prices)
            daily_low = min(float(v['low']) for v in values)
            daily_close = float(values[0]['close'])
            daily_volume = sum(today_volumes)
            avg_day_vol = daily_volume / len(today_volumes)

        fiveday_url = f"https://api.twelvedata.com/time_series?symbol={ticker}&interval=5min&outputsize=390&apikey={apikey}"
        async with session.get(fiveday_url) as response:
            fiveday_data = await response.json()
            if 'values' not in fiveday_data:
                return None, 2

            fiveday_volumes = [float(v['volume']) for v in fiveday_data['values']]
            avg_5day_vol = sum(fiveday_volumes) / len(fiveday_volumes)

        percent_change = round((daily_high - daily_low) / daily_low * 100, 2)
        volume_ratio = round(avg_day_vol / avg_5day_vol, 2)

        return (ticker, daily_close, percent_change, volume_ratio, int(daily_volume)), 2

    except Exception as e:
        print(f"Error processing {ticker}: {e}")
        return None, 0


async def process_batch(cursor, conn, batch, session, apikey, today, progress):
    tasks = [fetch_stock_data_direct(session, apikey, ticker, today) for ticker in batch]
    results = await asyncio.gather(*tasks)

    requests_made = sum(req_count for _, req_count in results)
    valid_results = [data for data, _ in results if data is not None]

    if valid_results:
        cursor.executemany("""
        INSERT OR REPLACE INTO stocks 
        (ticker, latest_price, percent_change, volume_ratio, daily_volume, last_updated)
        VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, valid_results)
        conn.commit()

    progress.update(len(batch), requests_made)
    return len(valid_results), requests_made

async def scan_stocks(cursor, conn, tickers, apikey):
    today = date.today()
    progress = ProgressTracker()
    progress.start(len(tickers))

    stocks_processed = 0
    batch_size = 50
    request_count = 0

    async with aiohttp.ClientSession() as session:
        for i in range(0, len(tickers), batch_size):
            batch = tickers[i:i + batch_size]
            processed, requests = await process_batch(cursor, conn, batch, session, apikey, today, progress)
            stocks_processed += processed
            request_count += requests

            if request_count >= 360:
                print("Rate limit approaching - Pausing for 60 seconds")
                await asyncio.sleep(60)
                request_count = 0

    return stocks_processed


def create_tables(cursor, conn):
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS stocks (
        ticker TEXT PRIMARY KEY,
        latest_price REAL,
        percent_change REAL,
        volume_ratio REAL,
        daily_volume INTEGER,
        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS tickers (
        ticker TEXT PRIMARY KEY,
        category TEXT,
        market_cap TEXT,
        last_updated DATE
    )""")
    conn.commit()

def update_tickers(cursor, conn, nasdaq_key):
    today = date.today()
    print(f"\nChecking ticker updates for {today}")

    cursor.execute("SELECT COUNT(*), MAX(last_updated) FROM tickers")
    count, last_update = cursor.fetchone()

    if count == 0 or last_update != today.isoformat():
        print("Fetching fresh ticker data from NASDAQ...")
        nasdaqdatalink.ApiConfig.api_key = nasdaq_key
        data = nasdaqdatalink.get_table('SHARADAR/TICKERS', paginate=True)


        stock_categories = [
            'Domestic Common Stock', 'ADR Common Stock',
            'Canadian Common Stock', 'Domestic Common Stock Primary Class'
        ]
        stock_caps = ['5 - Large', '4 - Mid', '3 - Small']

        active_tickers = data[
            (data['isdelisted'] == 'N') &
            (data['exchange'] == 'NASDAQ') &
            (data['category'].isin(stock_categories)) &
            (data['scalemarketcap'].isin(stock_caps))
            ].drop_duplicates('ticker')

        cursor.execute("DELETE FROM tickers")

        tickers_data = [(row['ticker'], row['category'], row['scalemarketcap'], today.isoformat())
                        for _, row in active_tickers.iterrows()]

        cursor.executemany("""
        INSERT OR REPLACE INTO tickers (ticker, category, market_cap, last_updated)
        VALUES (?, ?, ?, ?)
        """, tickers_data)

        conn.commit()
        print(f"Updated {len(active_tickers)} tickers in database")
    else:
        print("Tickers already up to date")

    cursor.execute("SELECT ticker FROM tickers")
    return [row[0] for row in cursor.fetchall()]


async def main():
    config = configparser.ConfigParser()
    config.read('keys.ini')

    nasdaq_key = config.get('keys', 'nasdaqdatalink_api_key')
    twelve_data_key = config.get('keys', 'twelve_data_api_key')

    conn = sqlite3.connect("stock_data.db")
    cursor = conn.cursor()

    create_tables(cursor, conn)
    tickers = update_tickers(cursor, conn, nasdaq_key)

    while True:
        try:
            stocks_processed = await scan_stocks(cursor, conn, tickers, twelve_data_key)
            print(f"\nScan Successful - Processed {stocks_processed} stocks")
            await asyncio.sleep(1)
        except KeyboardInterrupt:
            print("\nStopping scanner...")
            break
        except Exception as e:
            print(f"Error in main loop: {e}")
            await asyncio.sleep(60)

    conn.close()


if __name__ == "__main__":
    asyncio.run(main())