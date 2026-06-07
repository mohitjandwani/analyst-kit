#!/usr/bin/env python3
"""
CSV management utilities for company universe.
Handles CRUD operations on the company universe CSV file.
"""

import csv
import sys
import os
from datetime import datetime
from typing import Dict, List, Optional


CSV_HEADERS = [
    "company_name",
    "ticker_symbol",
    "exchange",
    "currency",
    "market_cap_category",
    "avg_market_cap",
    "avg_trading_volume",
    "competitors",
    "last_update_date",
    "investment_rationale",
    "source_url",
    "active"
]


def read_csv(csv_path):
    """Read CSV file and return list of dictionaries."""
    if not os.path.exists(csv_path):
        return []
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        return list(reader)


def write_csv(csv_path, data):
    """Write list of dictionaries to CSV file."""
    with open(csv_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
        writer.writeheader()
        writer.writerows(data)


def find_company(data, ticker=None, name=None):
    """Find company by ticker or name. Returns index and row, or (None, None)."""
    for idx, row in enumerate(data):
        if ticker and row.get('ticker_symbol', '').upper() == ticker.upper():
            return idx, row
        if name and row.get('company_name', '').lower() == name.lower():
            return idx, row
    return None, None


def add_company(csv_path, company_data):
    """Add a new company to the CSV."""
    data = read_csv(csv_path)
    
    # Check if company already exists
    ticker = company_data.get('ticker_symbol', '')
    idx, existing = find_company(data, ticker=ticker)
    
    if existing:
        return False, f"Company with ticker '{ticker}' already exists"
    
    # Ensure all required fields are present
    new_row = {header: company_data.get(header, '') for header in CSV_HEADERS}
    new_row['active'] = 'true'
    new_row['last_update_date'] = datetime.now().strftime('%Y-%m-%d')
    
    data.append(new_row)
    write_csv(csv_path, data)
    
    return True, f"Company '{ticker}' added successfully"


def update_company(csv_path, ticker, updates):
    """Update an existing company's information."""
    data = read_csv(csv_path)
    
    idx, existing = find_company(data, ticker=ticker)
    
    if not existing:
        return False, f"Company with ticker '{ticker}' not found"
    
    # Update fields
    for key, value in updates.items():
        if key in CSV_HEADERS:
            data[idx][key] = value
    
    data[idx]['last_update_date'] = datetime.now().strftime('%Y-%m-%d')
    
    write_csv(csv_path, data)
    
    return True, f"Company '{ticker}' updated successfully"


def remove_company(csv_path, ticker):
    """Soft delete a company (set active=false)."""
    data = read_csv(csv_path)
    
    idx, existing = find_company(data, ticker=ticker)
    
    if not existing:
        return False, f"Company with ticker '{ticker}' not found"
    
    data[idx]['active'] = 'false'
    data[idx]['last_update_date'] = datetime.now().strftime('%Y-%m-%d')
    
    write_csv(csv_path, data)
    
    return True, f"Company '{ticker}' removed from universe (soft delete)"


def reactivate_company(csv_path, ticker):
    """Reactivate a previously removed company."""
    data = read_csv(csv_path)
    
    idx, existing = find_company(data, ticker=ticker)
    
    if not existing:
        return False, f"Company with ticker '{ticker}' not found"
    
    data[idx]['active'] = 'true'
    data[idx]['last_update_date'] = datetime.now().strftime('%Y-%m-%d')
    
    write_csv(csv_path, data)
    
    return True, f"Company '{ticker}' reactivated"


def list_companies(csv_path, active_only=True):
    """List all companies, optionally filtering by active status."""
    data = read_csv(csv_path)
    
    if active_only:
        data = [row for row in data if row.get('active', 'true').lower() == 'true']
    
    return data


def initialize_csv(csv_path):
    """Create a new CSV file with headers."""
    if os.path.exists(csv_path):
        return False, "CSV file already exists"
    
    write_csv(csv_path, [])
    return True, "CSV file initialized"


def main():
    """Command-line interface."""
    if len(sys.argv) < 3:
        print("Usage:")
        print("  csv_manager.py init <csv_path>")
        print("  csv_manager.py list <csv_path> [--all]")
        print("  csv_manager.py add <csv_path> <ticker> <name> [field=value ...]")
        print("  csv_manager.py update <csv_path> <ticker> <field=value> [field=value ...]")
        print("  csv_manager.py remove <csv_path> <ticker>")
        print("  csv_manager.py reactivate <csv_path> <ticker>")
        sys.exit(1)
    
    action = sys.argv[1]
    csv_path = sys.argv[2]
    
    if action == "init":
        success, msg = initialize_csv(csv_path)
        print(msg)
        sys.exit(0 if success else 1)
    
    elif action == "list":
        active_only = "--all" not in sys.argv
        companies = list_companies(csv_path, active_only=active_only)
        
        if not companies:
            print("No companies found")
        else:
            # Print as table
            print(f"{'Ticker':<10} {'Name':<30} {'Exchange':<10} {'Active':<8}")
            print("-" * 60)
            for company in companies:
                ticker = company.get('ticker_symbol', '')
                name = company.get('company_name', '')[:28]
                exchange = company.get('exchange', '')
                active = company.get('active', 'true')
                print(f"{ticker:<10} {name:<30} {exchange:<10} {active:<8}")
    
    elif action == "add":
        if len(sys.argv) < 5:
            print("ERROR: add requires <ticker> and <name>", file=sys.stderr)
            sys.exit(1)
        
        ticker = sys.argv[3]
        name = sys.argv[4]
        
        company_data = {
            'ticker_symbol': ticker,
            'company_name': name
        }
        
        # Parse additional field=value pairs
        for arg in sys.argv[5:]:
            if '=' in arg:
                key, value = arg.split('=', 1)
                if key in CSV_HEADERS:
                    company_data[key] = value
        
        success, msg = add_company(csv_path, company_data)
        print(msg)
        sys.exit(0 if success else 1)
    
    elif action == "update":
        if len(sys.argv) < 5:
            print("ERROR: update requires <ticker> and <field=value> pairs", file=sys.stderr)
            sys.exit(1)
        
        ticker = sys.argv[3]
        updates = {}
        
        for arg in sys.argv[4:]:
            if '=' in arg:
                key, value = arg.split('=', 1)
                if key in CSV_HEADERS:
                    updates[key] = value
        
        success, msg = update_company(csv_path, ticker, updates)
        print(msg)
        sys.exit(0 if success else 1)
    
    elif action == "remove":
        if len(sys.argv) < 4:
            print("ERROR: remove requires <ticker>", file=sys.stderr)
            sys.exit(1)
        
        ticker = sys.argv[3]
        success, msg = remove_company(csv_path, ticker)
        print(msg)
        sys.exit(0 if success else 1)
    
    elif action == "reactivate":
        if len(sys.argv) < 4:
            print("ERROR: reactivate requires <ticker>", file=sys.stderr)
            sys.exit(1)
        
        ticker = sys.argv[3]
        success, msg = reactivate_company(csv_path, ticker)
        print(msg)
        sys.exit(0 if success else 1)
    
    else:
        print(f"ERROR: Unknown action '{action}'", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
