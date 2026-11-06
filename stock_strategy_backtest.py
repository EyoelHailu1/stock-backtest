"""Moving-average backtest for Thonny. Uses only Python's standard library.

CSV input: Date,Open,Close (one stock, ascending or descending dates).
Use consistently split-adjusted Open/Close prices. Dividends are excluded.
Signals use the previous day's close; trades execute at the next day's open.
Demo prices are fictional, not historical stock data or resume evidence.
"""

import csv
import math
import random
from datetime import date, timedelta
from pathlib import Path

STARTING_CASH = 10000.0
FAST_WINDOW = 10
SLOW_WINDOW = 30
FEE_RATE = 0.001  # 0.1% of each purchase or sale
OUTPUT_FOLDER = Path(__file__).resolve().parent


def demo_prices():
    """Create repeatable fictional prices so the program runs immediately."""
    rng = random.Random(42)
    rows = []
    day = date(2025, 1, 1)
    previous_close = 100.0
    while len(rows) < 300:
        if day.weekday() < 5:
            opening = previous_close * math.exp(rng.gauss(0, 0.003))
            closing = opening * math.exp(rng.gauss(0.0004, 0.015))
            rows.append((day, opening, closing))
            previous_close = closing
        day += timedelta(days=1)
    return rows


def load_prices(filename):
    """Read and validate a single-stock daily CSV."""
    rows = []
    with open(filename, newline='', encoding='utf-8-sig') as file:
        reader = csv.DictReader(file)
        required = {'Date', 'Open', 'Close'}
        if not required.issubset(reader.fieldnames or []):
            raise ValueError('CSV needs Date,Open,Close column headers.')
        for line, row in enumerate(reader, start=2):
            try:
                day = date.fromisoformat(row['Date'].strip())
                opening = float(row['Open'])
                closing = float(row['Close'])
                if not all(math.isfinite(p) and p > 0 for p in (opening, closing)):
                    raise ValueError('Prices must be positive finite numbers.')
                rows.append((day, opening, closing))
            except (ValueError, TypeError) as error:
                raise ValueError(f'Invalid CSV row {line}: {error}') from error
    rows.sort(key=lambda row: row[0])
    if len({row[0] for row in rows}) != len(rows):
        raise ValueError('CSV contains duplicate dates.')
    return rows


def max_drawdown(values):
    peak = values[0]
    largest_drop = 0.0
    for value in values:
        peak = max(peak, value)
        largest_drop = max(largest_drop, (peak - value) / peak)
    return largest_drop * 100


def backtest(rows):
    if not 1 <= FAST_WINDOW < SLOW_WINDOW:
        raise ValueError('Windows must satisfy 1 <= FAST_WINDOW < SLOW_WINDOW.')
    if STARTING_CASH <= 0 or not 0 <= FEE_RATE < 1:
        raise ValueError('Check starting cash and fee settings.')
    if len(rows) <= SLOW_WINDOW:
        raise ValueError(f'Provide at least {SLOW_WINDOW + 1} price rows.')

    cash = STARTING_CASH
    shares = 0.0
    trades = []
    daily = []
    closes = [row[2] for row in rows]
    # Both strategies begin after the same moving-average warm-up period.
    first_open = rows[SLOW_WINDOW][1]
    hold_shares = STARTING_CASH / (first_open * (1 + FEE_RATE))

    for i in range(SLOW_WINDOW, len(rows)):
        day, opening, closing = rows[i]
        # Slices stop BEFORE today: today's closing price cannot affect its trade.
        fast = sum(closes[i - FAST_WINDOW:i]) / FAST_WINDOW
        slow = sum(closes[i - SLOW_WINDOW:i]) / SLOW_WINDOW
        if fast > slow and shares == 0:
            shares = cash / (opening * (1 + FEE_RATE))
            fee = shares * opening * FEE_RATE
            cash = 0.0
            trades.append([day, 'BUY', opening, shares, fee])
        elif fast <= slow and shares > 0:
            fee = shares * opening * FEE_RATE
            cash = shares * opening - fee
            trades.append([day, 'SELL', opening, shares, fee])
            shares = 0.0
        # Daily balances use closing market value before any hypothetical exit fee.
        daily.append([day, closing, fast, slow,
                      cash + shares * closing, hold_shares * closing])

    # Liquidate both strategies at the final close for comparable net returns.
    final_day, _, final_close = rows[-1]
    if shares > 0:
        fee = shares * final_close * FEE_RATE
        cash += shares * final_close - fee
        trades.append([final_day, 'FINAL SELL', final_close, shares, fee])
    daily[-1][4] = cash
    daily[-1][5] = hold_shares * final_close * (1 - FEE_RATE)
    return daily, trades


def save_csv(filename, headings, rows):
    path = OUTPUT_FOLDER / filename
    with path.open('w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow(headings)
        writer.writerows(rows)
    print('Saved:', path)


def main():
    print('STOCK STRATEGY BACKTEST')
    print('Blank input runs FICTIONAL DEMO data. No downloads or packages needed.')
    filename = input('Historical CSV path, or press Enter for demo: ').strip()
    filename = filename.strip('"').strip("'")
    rows = load_prices(filename) if filename else demo_prices()
    daily, trades = backtest(rows)
    strategy = daily[-1][4]
    benchmark = daily[-1][5]
    print('\nData:', filename or 'FICTIONAL DEMO — not real market performance')
    print(f'Evaluation: {daily[0][0]} through {daily[-1][0]}')
    print(f'Starting balance: ${STARTING_CASH:,.2f}')
    print(f'Moving averages: {FAST_WINDOW} / {SLOW_WINDOW} sessions')
    print(f'Fee per transaction: {FEE_RATE:.2%}; fractional shares allowed')
    print(f'Strategy final balance: ${strategy:,.2f}')
    print(f'Strategy return: {(strategy / STARTING_CASH - 1):.2%}')
    print(f'Buy-and-hold final balance: ${benchmark:,.2f}')
    print(f'Buy-and-hold return: {(benchmark / STARTING_CASH - 1):.2%}')
    equity = [STARTING_CASH] + [row[4] for row in daily]
    print(f'Strategy maximum daily drawdown: {max_drawdown(equity):.2f}%')
    print(f'Transactions: {len(trades)} (includes final liquidation)')
    print('Excludes dividends, taxes, slippage, and spread; assumes fills at open.')
    save_csv('backtest_results.csv',
             ['Date', 'Close', 'Fast_MA', 'Slow_MA',
              'Strategy_Balance', 'Buy_Hold_Balance'], daily)
    save_csv('trade_log.csv', ['Date', 'Action', 'Price', 'Shares', 'Fee'], trades)
    if not filename:
        save_csv('demo_prices.csv', ['Date', 'Open', 'Close'], rows)


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError) as error:
        print('Error:', error)
