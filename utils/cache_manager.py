import json
import os
import time
import threading
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import akshare as ak
import pandas as pd

try:
    from pypinyin import lazy_pinyin
    HAS_PYPINYIN = True
except ImportError:
    HAS_PYPINYIN = False

# Configure logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("CompanyCacheManager")

DATA_DIR = "data"
CACHE_DIR = os.path.join(DATA_DIR, "company_cache")
LOG_FILE = os.path.join(DATA_DIR, "cache_update.log")

class CompanyCacheManager:
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(CompanyCacheManager, cls).__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        self._ensure_dirs()
        self.refresh_interval = 600  # 10 minutes
        self.last_update_time = None
        self.cache_index = {} # Map code -> file_path or metadata
        self._load_index()
        self._initialized = True
        
    def _ensure_dirs(self):
        if not os.path.exists(CACHE_DIR):
            os.makedirs(CACHE_DIR)
        
    def _load_index(self):
        """Load cache index from disk."""
        index_path = os.path.join(CACHE_DIR, "index.json")
        if os.path.exists(index_path):
            try:
                with open(index_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.cache_index = data.get("index", {})
                    self.last_update_time = datetime.fromisoformat(data.get("last_updated")) if data.get("last_updated") else None
            except Exception as e:
                logger.error(f"Failed to load cache index: {e}")
                self.cache_index = {}
        
    def _save_index(self):
        """Save cache index to disk."""
        index_path = os.path.join(CACHE_DIR, "index.json")
        data = {
            "last_updated": self.last_update_time.isoformat() if self.last_update_time else None,
            "index": self.cache_index
        }
        with open(index_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False)
            
    def _log_operation(self, message: str):
        """Append log to file."""
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(f"{datetime.now().isoformat()} - {message}\n")

    def get_company_data(self, code: str) -> Optional[Dict[str, Any]]:
        """Retrieve company data from cache (< 100ms target)."""
        # Read from master cache directly for speed, as it's small enough.
        # Reading single file per company is actually slower if we don't have them split.
        # My implementation merged everything into master_cache.json for bulk efficiency.
        # So we should read from memory or reload master cache.
        
        # For concurrency, we might want to reload if file changed.
        # But for <100ms, in-memory dict is best.
        
        # Simple implementation: Load master cache if not loaded or stale?
        # Let's just load master cache.
        master_cache_path = os.path.join(CACHE_DIR, "master_cache.json")
        if os.path.exists(master_cache_path):
            try:
                # In a real high-concurrency app, we'd use a memory cache with TTL.
                # Here, reading 2MB JSON is fast (<10ms).
                with open(master_cache_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data.get(code)
            except Exception as e:
                logger.error(f"Error reading cache for {code}: {e}")
        return None

    def _fetch_financials(self, code: str) -> Dict[str, float]:
        """Fetch financial indicators (ROE, Gross, Net) for a single stock."""
        result = {}
        try:
            # 1. Try stock_financial_abstract (More reliable for EPS/ROE)
            try:
                df = ak.stock_financial_abstract(symbol=code)
                if not df.empty:
                    # Find the latest date column (usually sorted desc, exclude metadata cols)
                    date_cols = [c for c in df.columns if c not in ['选项', '指标']]
                    if date_cols:
                        latest_col = date_cols[0] 
                        
                        def get_val_abstract(metric_name):
                            row = df[df['指标'] == metric_name]
                            if not row.empty:
                                val = row.iloc[0][latest_col]
                                try:
                                    return float(val)
                                except:
                                    return 0.0
                            return 0.0

                        result["EPS"] = get_val_abstract('基本每股收益')
                        result["ROE"] = get_val_abstract('净资产收益率(ROE)')
                        result["GrossMargin"] = get_val_abstract('毛利率')
                        result["NetMargin"] = get_val_abstract('销售净利率')
                        result["DebtRatio"] = get_val_abstract('资产负债率')
                        
                        # Return if we found valid data
                        if any(v != 0 for v in result.values()):
                            return result
            except Exception as e:
                logger.warning(f"stock_financial_abstract failed for {code}: {e}")

            # 2. Fallback to stock_financial_analysis_indicator
            df = ak.stock_financial_analysis_indicator(symbol=code)
            if not df.empty:
                df = df.sort_values('日期', ascending=False)
                latest = df.iloc[0]
                
                def get_val(col_keyword):
                    cols = [c for c in df.columns if col_keyword in c]
                    return float(latest[cols[0]]) if cols else 0.0
                    
                result["ROE"] = get_val('净资产收益率')
                result["GrossMargin"] = get_val('销售毛利率')
                result["NetMargin"] = get_val('销售净利率')
                result["EPS"] = get_val('每股收益')
                result["DebtRatio"] = get_val('资产负债率')
            else:
                logger.warning(f"Financial data empty for {code} (both methods)")
                
        except Exception as e:
            logger.error(f"Error fetching financials for {code}: {e}")
            pass
        return result

    def update_financials(self, code: str):
        """Update financials for a specific stock in cache."""
        master_cache_path = os.path.join(CACHE_DIR, "master_cache.json")
        if not os.path.exists(master_cache_path):
            return

        # Load
        with open(master_cache_path, 'r', encoding='utf-8') as f:
            cache = json.load(f)
            
        if code in cache:
            # Fetch new data
            fin_data = self._fetch_financials(code)
            if fin_data:
                cache[code]['financials'] = fin_data
                cache[code]['last_updated'] = datetime.now().isoformat()
                
                # Save
                with open(master_cache_path, 'w', encoding='utf-8') as f:
                    json.dump(cache, f, ensure_ascii=False)
                
                logger.info(f"Updated financials for {code}")

    def get_financials(self, code: str) -> Dict[str, float]:
        """Get financials from cache, trigger update if missing."""
        data = self.get_company_data(code)
        if data:
            fin = data.get('financials', {})
            if fin:
                 return fin
        
        # If missing, we might want to trigger an update?
        # But this method is called by UI, so we should return empty first and maybe background update?
        # Or just return empty and let the caller decide.
        # Given "Optimization", let's try to fetch if missing (Lazy Load) and update cache.
        
        # Lazy Load
        fin_data = self._fetch_financials(code)
        if fin_data:
            # Update cache asynchronously or synchronously? 
            # Sync for now to ensure data availability
            self.update_financials(code) # This re-reads cache which is inefficient but safe
            return fin_data
            
        return {"ROE": 0.0, "GrossMargin": 0.0, "NetMargin": 0.0, "EPS": 0.0}

    def update_cache(self, force: bool = False):
        """
        Incremental update mechanism.
        Target: < 30s execution time.
        """
        start_time = time.time()
        logger.info("Starting cache update...")
        
        if not force and self.last_update_time:
            elapsed = (datetime.now() - self.last_update_time).total_seconds()
            if elapsed < self.refresh_interval:
                logger.info(f"Skipping update, elapsed {elapsed}s < {self.refresh_interval}s")
                return

        retry_count = 0
        max_retries = 3
        
        while retry_count < max_retries:
            try:
                self._perform_update(start_time)
                break
            except Exception as e:
                retry_count += 1
                logger.error(f"Update failed (Attempt {retry_count}/{max_retries}): {e}")
                if retry_count == max_retries:
                    self._log_operation(f"Update FAILED after {max_retries} attempts: {e}")
                    raise e
                time.sleep(1)

    def _perform_update(self, start_time):
        # 1. Fetch Snapshot (The only fast way to get data for ALL stocks)
        # We prioritize EastMoney (EM) as it has more fields.
        df = pd.DataFrame()
        error_msgs = []
        source = "EM"
        
        try:
            df = ak.stock_zh_a_spot_em()
            # EM returns Market Value in Yuan (e.g. 2000000000000)
        except Exception as e:
            error_msgs.append(f"EastMoney: {str(e)}")
            # Fallback to Sina
            try:
                df = ak.stock_zh_a_spot()
                source = "Sina"
                # Sina returns: symbol, code, name, trade, pricechange, changepercent, buy, sell, settlement, open, high, low, volume, amount, ticktime, per, pb, mktcap, nmc, turnoverratio
                # mktcap/nmc are in Wan (10^4). Need to convert to Yuan.
                # Rename columns to match EM style for consistent processing below
                # Assuming Sina columns: code, name, trade (price), changepercent, mktcap, nmc, per, pb, volume, amount
                
                # Check column names if possible. If standard API, we assume standard names.
                # Map Sina columns to EM columns:
                # 代码 -> code
                # 名称 -> name
                # 最新价 -> trade
                # 涨跌幅 -> changepercent
                # 成交量 -> volume
                # 成交额 -> amount
                # 市盈率-动态 -> per
                # 市净率 -> pb
                # 总市值 -> mktcap * 10000
                # 流通市值 -> nmc * 10000
                
                rename_map = {
                    'code': '代码',
                    'name': '名称',
                    'trade': '最新价',
                    'changepercent': '涨跌幅',
                    'volume': '成交量',
                    'amount': '成交额',
                    'per': '市盈率-动态',
                    'pb': '市净率'
                }
                df = df.rename(columns=rename_map)
                
                # Handle Market Value Unit Conversion (Wan -> Yuan)
                if 'mktcap' in df.columns:
                    df['总市值'] = df['mktcap'] * 10000
                if 'nmc' in df.columns:
                    df['流通市值'] = df['nmc'] * 10000
                    
            except Exception as e_sina:
                error_msgs.append(f"Sina: {str(e_sina)}")
        
        if df.empty:
            error_detail = "; ".join(error_msgs)
            logger.warning(f"Failed to fetch market data: {error_detail}. Returning empty.")
            return

        # Normalize Data
        # Ensure '代码' is string and 6 digits
        df['代码'] = df['代码'].astype(str)
        # Basic cleaning if needed
        
        changes_count = 0
        
        # 2. Process Data
        # For performance (<30s), we cannot read/write 5000 files.
        # We should only write if data changed significantly or if it's a new stock.
        # However, price changes every second. 
        # "Incremental update" in this context usually means updating the *Store*.
        # If we write 5000 small JSON files, it might take > 30s on slow disk.
        # Let's batch write or check diff.
        
        # Optimization: We only update "Active" stocks fully? 
        # But requirement says "Every company".
        # Let's assume we update the `company_cache/{code}.json` file.
        
        # To meet <30s, we might need multi-threading or just efficient IO.
        # Let's try sequential first, but only write if changed.
        # Actually, for a "cache", maybe we just keep a large dict in memory and dump to a few files?
        # But requirement says "JSON format... easy to query". Individual files are easiest to query by ID.
        
        timestamp = datetime.now().isoformat()
        
        # Convert DF to list of dicts for iteration
        records = df.to_dict('records')
        
        for row in records:
            code = str(row.get('代码', ''))
            if not code: continue
            
            # Clean code (remove sh/sz prefix if any, though EM usually returns clean 6 digits)
            # If using Sina fallback, might need cleaning.
            if not code.isdigit():
                 import re
                 digits = re.findall(r'\d+', code)
                 if digits: code = digits[-1][-6:]
            
            # Prepare new data
            new_data = {
                "base": {
                    "code": code,
                    "name": row.get('名称', ''),
                    # Add pinyin if needed, but it's slow to generate for all 5000 every time
                },
                "quote": {
                    "price": row.get('最新价'),
                    "change_pct": row.get('涨跌幅'),
                    "volume": row.get('成交量'),
                    "amount": row.get('成交额'),
                    "timestamp": timestamp
                },
                "last_updated": timestamp
            }
            
        # Implementation Detail:
        # We will maintain a `data/company_cache/master_cache.json` containing everything.
        # It's about 5000 stocks * 500 bytes ~= 2.5MB. Very small.
        # Reading/Writing 2.5MB is instant.
        
        # Load Master Cache
        master_cache_path = os.path.join(CACHE_DIR, "master_cache.json")
        current_cache = {}
        if os.path.exists(master_cache_path):
            with open(master_cache_path, 'r', encoding='utf-8') as f:
                current_cache = json.load(f)
        
        # Bulk Update
        updated_count = 0
        
        # Pre-calc Pinyin if needed (only for new stocks)
        # We can cache pinyin in a separate dict to avoid re-calc.
        
        def clean_num(val):
            """Convert NaN/inf to None for JSON compliance."""
            if val is None: return None
            try:
                if pd.isna(val): return None
                # Handle infinite values if any
                if val == float('inf') or val == float('-inf'): return None
                return float(val)
            except:
                return None

        for row in records:
            code = str(row.get('代码'))
            # Cleaning...
            if not code.isdigit():
                 import re
                 digits = re.findall(r'\d+', code)
                 if digits: code = digits[-1][-6:]
                 else: continue

            name = row.get('名称', '')
            price = row.get('最新价')
            
            # Check change
            old_entry = current_cache.get(code, {})
            old_quote = old_entry.get('quote', {})
            
            # If price changed or volume changed, we update
            # Using simple inequality
            if (old_quote.get('price') != price) or (old_entry.get('base', {}).get('name') != name):
                # Update
                base = old_entry.get('base', {})
                if base.get('name') != name or 'pinyin' not in base:
                    base['name'] = name
                    base['code'] = code
                    if 'pinyin' not in base:
                         if HAS_PYPINYIN:
                             try:
                                 base['pinyin'] = "".join([w[0] for w in lazy_pinyin(name)]).upper()
                             except:
                                 base['pinyin'] = ""
                         else:
                             base['pinyin'] = ""
                
                quote = {
                    "price": clean_num(price),
                    "change_pct": clean_num(row.get('涨跌幅')),
                    "volume": clean_num(row.get('成交量')),
                    "amount": clean_num(row.get('成交额')),
                    "turnover_rate": clean_num(row.get('换手率')),
                    "pe": clean_num(row.get('市盈率-动态')),
                    "pb": clean_num(row.get('市净率')),
                    "total_mv": clean_num(row.get('总市值')),
                    "circ_mv": clean_num(row.get('流通市值')),
                    "timestamp": timestamp
                }
                
                current_cache[code] = {
                    "base": base,
                    "quote": quote,
                    "last_updated": timestamp,
                    # Preserve other fields if any (e.g. financials fetched separately)
                    "financials": old_entry.get('financials', {}),
                    "relations": old_entry.get('relations', {})
                }
                updated_count += 1
        
        # Save Master Cache
        with open(master_cache_path, 'w', encoding='utf-8') as f:
            json.dump(current_cache, f, ensure_ascii=False)
            
        self.last_update_time = datetime.now()
        self._save_index()
        
        duration = time.time() - start_time
        log_msg = f"Update success. Changed: {updated_count}. Duration: {duration:.2f}s"
        logger.info(log_msg)
        self._log_operation(log_msg)
        
    def get_all_companies(self) -> Dict[str, Any]:
        """Get the full master cache."""
        master_cache_path = os.path.join(CACHE_DIR, "master_cache.json")
        if os.path.exists(master_cache_path):
             with open(master_cache_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}

# Singleton Accessor
_cache_manager = CompanyCacheManager()

def get_cache_manager():
    return _cache_manager
