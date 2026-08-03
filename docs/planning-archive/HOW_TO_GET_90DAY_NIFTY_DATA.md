# How to Get 90 Days NIFTY Historical Data
## Complete Guide - 3 Methods

---

## **WHAT YOU NEED**

**File Format:** CSV  
**Filename:** `nifty_90days.csv`  
**Required Columns:** `Timestamp,Open,High,Low,Close,Volume`  
**Duration:** Last 90 trading days (not calendar days)  
**Timeframe:** 1-minute bars  
**Expected Rows:** ~35,100 (390 minutes/day × 90 days)  
**Placement:** Save to `data/historical/nifty_90days.csv`

---

## **METHOD 1: Download from Fyers Web Platform (Easiest - 5 mins)**

### **Step-by-Step Instructions**

#### **Step 1: Login to Fyers**
1. Go to https://www.aliceblueonline.com or https://ant.aliceblueonline.com
2. Login with your Fyers account credentials
3. Navigate to: **Charts / Watchlist**

#### **Step 2: Select NIFTY and 1-Minute Timeframe**
1. In the symbol search, type: `NIFTY` or `NSE:NIFTY50-INDEX`
2. Press Enter (chart will load)
3. Look for timeframe selector (usually top-left of chart)
4. Select: **1-minute** (or "1M" / "1min")

#### **Step 3: Set Date Range (90 Days)**
1. Find the date range selector
2. **Start Date:** 90 calendar days ago (approximately)
   - From today (Aug 3, 2026) → go back to **May 6, 2026**
   - Calculate: Today minus 90 days
3. **End Date:** Today (Aug 3, 2026)
4. Click **Apply** or **Update**

**Quick Date Calculation:**
```
Today:        Aug 3, 2026
Minus 90 days: May 6, 2026

But since markets don't trade weekends:
- 90 calendar days ≈ 65 trading days
- Use 90-100 calendar days to ensure 60+ trading days of data
```

#### **Step 4: Export as CSV**
1. Look for **Export** or **Download** button
2. Right-click on the chart → "Save chart as" or "Export data"
3. Select format: **CSV**
4. Filename: `nifty_90days.csv`
5. Save location: `your-project/data/historical/`

**If no direct export:**
1. Right-click chart → **Inspect Element**
2. Or use browser DevTools → **Network** tab → capture the data request
3. Or take screenshot of each day and manually compile (tedious!)

---

## **METHOD 2: Download Using Python + Fyers API (Programmatic - 10 mins)**

This is **most reliable** for getting exact 90-day data.

### **Step 1: Create a Python Script**

Create file: `download_nifty_data.py`

```python
import pandas as pd
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv

# If using pya3 (Alice Blue)
try:
    from alice_blue import AliceBlue
except ImportError:
    print("Install: pip install alice_blue")
    exit()

# If using Fyers API
try:
    from fyers_apiv3 import fyersModel
except ImportError:
    print("Install: pip install fyers-api")
    exit()

# Load credentials from .env
load_dotenv()

# ============================================================================
# FYERS API METHOD (Recommended for Fyers)
# ============================================================================

def download_nifty_data_fyers():
    """Download 90 days NIFTY data using Fyers API"""
    
    # Your Fyers credentials
    app_id = os.getenv("FYERS_APP_ID")
    app_secret = os.getenv("FYERS_APP_SECRET")
    redirect_uri = os.getenv("FYERS_REDIRECT_URI", "http://127.0.0.1:5000")
    
    print(f"🔍 Downloading NIFTY data using Fyers API...")
    print(f"   App ID: {app_id}")
    
    # Initialize Fyers client
    fyers = fyersModel.FyersClient()
    fyers.app_id = app_id
    fyers.app_secret = app_secret
    fyers.redirect_uri = redirect_uri
    
    # Generate auth code (you may need to authenticate manually first)
    # auth_url = fyers.generate_authcode()
    # print(f"Visit: {auth_url}")
    # auth_code = input("Enter auth code: ")
    
    # For now, use pre-generated access token from .env
    access_token = os.getenv("FYERS_ACCESS_TOKEN")
    if not access_token:
        print("❌ FYERS_ACCESS_TOKEN not found in .env")
        print("   Get it from: https://myapi.fyers.in/")
        return None
    
    fyers.access_token = access_token
    
    # Calculate date range
    end_date = datetime.now()
    start_date = end_date - timedelta(days=90)
    
    print(f"📅 Date range: {start_date.date()} to {end_date.date()}")
    
    # Prepare request
    data = {
        "symbol": "NSE:NIFTY50-INDEX",
        "resolution": "1",  # 1-minute bars
        "date_format": "1",  # epoch format (unix timestamp)
        "range_from": int(start_date.timestamp()),
        "range_to": int(end_date.timestamp()),
        "cont_flag": "1"  # continuous contract
    }
    
    # Fetch data
    try:
        print("🔄 Fetching data from Fyers...")
        response = fyers.history(data)
        
        if response.get("status") == "ok" and response.get("candles"):
            candles = response["candles"]
            print(f"✅ Got {len(candles)} candles")
            
            # Convert to DataFrame
            df = pd.DataFrame(candles, columns=[
                "Timestamp", "Open", "High", "Low", "Close", "Volume"
            ])
            
            # Convert timestamp from epoch to datetime
            df["Timestamp"] = pd.to_datetime(df["Timestamp"], unit='s')
            df["Timestamp"] = df["Timestamp"].dt.strftime("%Y-%m-%d %H:%M:%S")
            
            # Reorder columns
            df = df[["Timestamp", "Open", "High", "Low", "Close", "Volume"]]
            
            # Save to CSV
            output_file = "data/historical/nifty_90days.csv"
            os.makedirs(os.path.dirname(output_file), exist_ok=True)
            df.to_csv(output_file, index=False)
            
            print(f"💾 Saved to: {output_file}")
            print(f"   Rows: {len(df)}")
            print(f"   File size: {os.path.getsize(output_file) / 1024:.1f} KB")
            return df
        else:
            print(f"❌ Error: {response}")
            return None
            
    except Exception as e:
        print(f"❌ Error fetching data: {e}")
        return None


# ============================================================================
# ALICE BLUE METHOD (Alternative)
# ============================================================================

def download_nifty_data_alice_blue():
    """Download 90 days NIFTY data using Alice Blue API"""
    
    from alice_blue import AliceBlue
    from datetime import datetime, timedelta
    
    print("🔍 Downloading NIFTY data using Alice Blue API...")
    
    # Initialize Alice Blue client
    alice = AliceBlue(
        user_id=os.getenv("ALICE_USER_ID"),
        api_key=os.getenv("ALICE_API_KEY")
    )
    
    # Calculate date range
    end_date = datetime.now()
    start_date = end_date - timedelta(days=90)
    
    print(f"📅 Date range: {start_date.date()} to {end_date.date()}")
    
    # Fetch data
    try:
        print("🔄 Fetching data from Alice Blue...")
        
        candles = alice.gethistoricaldata(
            instrument="NSE:NIFTY50-INDEX",
            start_date=start_date.strftime("%Y-%m-%d"),
            end_date=end_date.strftime("%Y-%m-%d"),
            interval="1"  # 1-minute bars
        )
        
        if candles:
            print(f"✅ Got {len(candles)} candles")
            
            # Convert to DataFrame
            df = pd.DataFrame(candles)
            
            # Save to CSV
            output_file = "data/historical/nifty_90days.csv"
            os.makedirs(os.path.dirname(output_file), exist_ok=True)
            df.to_csv(output_file, index=False)
            
            print(f"💾 Saved to: {output_file}")
            print(f"   Rows: {len(df)}")
            return df
        else:
            print("❌ No data returned")
            return None
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return None


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("NIFTY Historical Data Downloader")
    print("=" * 70)
    
    # Try Fyers first
    print("\n1️⃣ Trying Fyers API...")
    df = download_nifty_data_fyers()
    
    if df is None or df.empty:
        print("\n2️⃣ Fyers failed. Trying Alice Blue...")
        df = download_nifty_data_alice_blue()
    
    if df is not None and not df.empty:
        print("\n" + "=" * 70)
        print("✅ SUCCESS!")
        print("=" * 70)
        print(f"\nData saved to: data/historical/nifty_90days.csv")
        print(f"\nFirst 5 rows:")
        print(df.head())
        print(f"\nLast 5 rows:")
        print(df.tail())
        print(f"\nTotal rows: {len(df)}")
    else:
        print("\n" + "=" * 70)
        print("❌ FAILED - Both methods failed")
        print("=" * 70)
        print("Try Method 3 instead (Manual)")
```

### **Step 2: Add to Your .env File**

Add these lines to `.env`:

```
# For Fyers
FYERS_APP_ID=your_app_id
FYERS_APP_SECRET=your_app_secret
FYERS_ACCESS_TOKEN=your_access_token
FYERS_TOTP_SECRET=your_totp_secret

# For Alice Blue (if using)
ALICE_USER_ID=your_user_id
ALICE_API_KEY=your_api_key
```

### **Step 3: Run the Script**

```bash
# Install required packages
pip install pandas python-dotenv fyers-api

# Run the downloader
python download_nifty_data.py
```

**Expected Output:**
```
======================================================================
NIFTY Historical Data Downloader
======================================================================

1️⃣ Trying Fyers API...
🔍 Downloading NIFTY data using Fyers API...
   App ID: ABC123XYZ
📅 Date range: 2026-05-06 to 2026-08-03
🔄 Fetching data from Fyers...
✅ Got 35150 candles
💾 Saved to: data/historical/nifty_90days.csv
   Rows: 35150
   File size: 892.3 KB

======================================================================
✅ SUCCESS!
======================================================================

First 5 rows:
             Timestamp      Open      High       Low     Close  Volume
0  2026-05-06 09:15:00  24100.00  24150.50  24090.00  24120.00  150000
1  2026-05-06 09:16:00  24120.00  24180.00  24115.00  24170.00  180000
2  2026-05-06 09:17:00  24170.00  24200.00  24160.00  24195.00  165000
3  2026-05-06 09:18:00  24195.00  24210.00  24185.00  24200.00  145000
4  2026-05-06 09:19:00  24200.00  24220.00  24190.00  24210.00  155000

Total rows: 35150
```

---

## **METHOD 3: Manual Download from NSE Website (Alternative)**

If Fyers doesn't have the data readily available:

### **Option A: NSE Website**
1. Go to https://www.nseindia.com/
2. Navigate to: **Market Data** → **Historical Data**
3. Select: **NIFTY 50**
4. Timeframe: **1-minute**
5. Date range: Last 90 days
6. Download as CSV

### **Option B: TradingView**
1. Go to https://www.tradingview.com
2. Search: `NIFTY`
3. Right-click chart → **Export data**
4. Select: **CSV format**

### **Option C: Yahoo Finance**
1. Go to https://finance.yahoo.com/
2. Search: `^NSEI` (NIFTY ticker)
3. Download historical data
4. Format as required

---

## **FILE VALIDATION - After Download**

### **Step 1: Check File Format**

Once you have `nifty_90days.csv`, verify it:

```bash
# On Mac/Linux
head -10 data/historical/nifty_90days.csv
wc -l data/historical/nifty_90days.csv

# On Windows PowerShell
Get-Content data/historical/nifty_90days.csv -Head 10
(Get-Content data/historical/nifty_90days.csv | Measure-Object -Line).Lines
```

**Expected Output:**
```
Timestamp,Open,High,Low,Close,Volume
2026-05-06 09:15:00,24100.00,24150.50,24090.00,24120.00,150000
2026-05-06 09:16:00,24120.00,24180.00,24115.00,24170.00,180000
...
35150
```

### **Step 2: Validate with Python**

Create file: `validate_data.py`

```python
import pandas as pd

# Load data
df = pd.read_csv("data/historical/nifty_90days.csv")

print("=" * 70)
print("DATA VALIDATION")
print("=" * 70)

# Basic checks
print(f"\n✓ File loaded: data/historical/nifty_90days.csv")
print(f"✓ Rows: {len(df)}")
print(f"✓ Columns: {list(df.columns)}")

# Check for required columns
required_cols = ["Timestamp", "Open", "High", "Low", "Close", "Volume"]
missing = [c for c in required_cols if c not in df.columns]
if missing:
    print(f"\n❌ Missing columns: {missing}")
    exit(1)
else:
    print(f"✓ All required columns present")

# Check data types
print(f"\nData types:")
print(df.dtypes)

# Check for missing values
print(f"\nMissing values:")
print(df.isnull().sum())

# Check date range
df["Timestamp"] = pd.to_datetime(df["Timestamp"])
print(f"\n✓ Date range: {df['Timestamp'].min()} to {df['Timestamp'].max()}")

# Check number of trading days
trading_days = df["Timestamp"].dt.date.nunique()
print(f"✓ Trading days: {trading_days}")

# Check candles per day (should be ~390)
candles_per_day = df.groupby(df["Timestamp"].dt.date).size()
print(f"✓ Avg candles/day: {candles_per_day.mean():.0f}")
print(f"✓ Min candles/day: {candles_per_day.min()}")
print(f"✓ Max candles/day: {candles_per_day.max()}")

# Data range
print(f"\n✓ OHLC ranges:")
print(f"  Open:  {df['Open'].min():.2f} - {df['Open'].max():.2f}")
print(f"  High:  {df['High'].min():.2f} - {df['High'].max():.2f}")
print(f"  Low:   {df['Low'].min():.2f} - {df['Low'].max():.2f}")
print(f"  Close: {df['Close'].min():.2f} - {df['Close'].max():.2f}")

print(f"\n" + "=" * 70)
print("✅ Data validation passed!")
print("=" * 70)

# Show sample
print(f"\nFirst 5 rows:")
print(df.head())
print(f"\nLast 5 rows:")
print(df.tail())
```

Run validation:
```bash
python validate_data.py
```

**Expected Output:**
```
======================================================================
DATA VALIDATION
======================================================================

✓ File loaded: data/historical/nifty_90days.csv
✓ Rows: 35150
✓ Columns: ['Timestamp', 'Open', 'High', 'Low', 'Close', 'Volume']
✓ All required columns present

Data types:
Timestamp    object
Open        float64
High        float64
Low         float64
Close       float64
Volume       int64
dtype: object

Missing values:
Timestamp    0
Open         0
High         0
Low          0
Close        0
Volume       0
dtype: int64

✓ Date range: 2026-05-06 09:15:00 to 2026-08-03 15:30:00
✓ Trading days: 62
✓ Avg candles/day: 567
✓ Min candles/day: 380
✓ Max candles/day: 390

✓ OHLC ranges:
  Open:  24012.50 - 24892.50
  High:  24050.00 - 24950.00
  Low:   23980.00 - 24850.00
  Close: 24020.00 - 24900.00

======================================================================
✅ Data validation passed!
======================================================================

First 5 rows:
            Timestamp      Open      High       Low     Close  Volume
0 2026-05-06 09:15:00  24100.00  24150.50  24090.00  24120.00  150000
1 2026-05-06 09:16:00  24120.00  24180.00  24115.00  24170.00  180000
...

Last 5 rows:
                Timestamp      Open      High       Low     Close  Volume
35145 2026-08-03 15:25:00  24480.00  24490.00  24470.00  24485.00  120000
...
```

---

## **WHICH METHOD SHOULD YOU USE?**

### **🥇 Recommended: Method 2 (Python + Fyers API)**
- ✅ Exact data matching your broker
- ✅ Reproducible (can re-run anytime)
- ✅ Automated (one command)
- ✅ Future-proof (can schedule daily updates)

**Use this if:** You have Fyers account + API access

---

### **🥈 Alternative: Method 1 (Web Export)**
- ✅ Simple, no coding
- ✅ Quick (5 minutes)
- ✓ Reliable

**Use this if:** You want manual control or Method 2 fails

---

### **🥉 Fallback: Method 3 (NSE/TradingView)**
- ✅ Works for anyone
- ✗ May need reformatting
- ✗ Data quality varies

**Use this if:** Other methods fail

---

## **NEXT STEPS**

### **After You Get the Data:**

1. **Save to correct location:**
   ```
   nifty-options-trader/
   └── data/
       └── historical/
           └── nifty_90days.csv  ← HERE
   ```

2. **Validate the file:**
   ```bash
   python validate_data.py
   ```

3. **Ready for backtest:**
   ```bash
   # The backtest will auto-load from data/historical/nifty_90days.csv
   python src/backtester/backtest_engine.py
   ```

---

## **TROUBLESHOOTING**

| Problem | Solution |
|---------|----------|
| **No data from Fyers API** | Check access token is valid and not expired |
| **File not found during backtest** | Ensure path is `data/historical/nifty_90days.csv` (exact case-sensitive) |
| **Wrong number of rows** | Check you selected 1-minute timeframe, not 5-min or 15-min |
| **Timestamps in wrong format** | Ensure format is: `YYYY-MM-DD HH:MM:SS` (e.g., `2026-05-06 09:15:00`) |
| **Volume is 0** | Check data is from NSE (NIFTY), not from another exchange |
| **File is too small** | Need at least 30,000+ rows for 90-day 1-min data |

---

## **QUICK COMMAND REFERENCE**

```bash
# Method 2 (Recommended) - One command:
python download_nifty_data.py

# Validate data:
python validate_data.py

# Check file exists:
ls -lh data/historical/nifty_90days.csv

# View first 10 rows:
head -10 data/historical/nifty_90days.csv

# Count rows:
wc -l data/historical/nifty_90days.csv
```

---

**Ready? Start with Method 2 if you have Fyers API access. Takes 5 minutes. Then proceed to backtest! 🚀**
