
import unittest
from unittest.mock import patch, MagicMock
import pandas as pd
import sys
import os

# Mock streamlit before importing utils.stock_data
mock_st = MagicMock()
mock_st.cache_data = lambda func=None, **kwargs: (lambda f: f) if func is None else func
mock_st.cache_resource = lambda func=None, **kwargs: (lambda f: f) if func is None else func
sys.modules['streamlit'] = mock_st

# Mock pypinyin
sys.modules['pypinyin'] = MagicMock()

# Now we can import
from utils import stock_data
from utils import cache_manager

class TestStockDataHandling(unittest.TestCase):
    
    def setUp(self):
        # Clear cache manager singleton if needed, but here we just mock methods
        pass

    @patch('utils.stock_data.ak')
    @patch('utils.cache_manager.ak')
    def test_get_market_snapshot_failure(self, mock_ak_cm, mock_ak_sd):
        """Test that get_market_snapshot returns empty DataFrame on failure."""
        # Setup mocks to raise exception
        mock_ak_sd.stock_zh_a_spot_em.side_effect = Exception("Network Error")
        mock_ak_sd.stock_zh_a_spot.side_effect = Exception("Network Error")
        mock_ak_sd.stock_info_a_code_name.side_effect = Exception("Network Error")
        
        # Also mock cache manager to return empty so it triggers fallback
        with patch.object(cache_manager.CompanyCacheManager, 'get_all_companies', return_value={}):
            # Also mock the fallback in cache manager if it tries to fetch
            mock_ak_cm.stock_zh_a_spot_em.side_effect = Exception("Network Error")
            mock_ak_cm.stock_zh_a_spot.side_effect = Exception("Network Error")
            
            df = stock_data.get_market_snapshot()
            
            self.assertIsInstance(df, pd.DataFrame)
            self.assertTrue(df.empty)

    @patch('utils.stock_data.ak')
    def test_get_stock_history_failure(self, mock_ak):
        """Test that get_stock_history returns empty DataFrame on failure."""
        mock_ak.stock_zh_a_hist.side_effect = Exception("Network Error")
        mock_ak.stock_zh_a_daily.side_effect = Exception("Network Error")
        
        df = stock_data.get_stock_history("600519")
        
        self.assertIsInstance(df, pd.DataFrame)
        self.assertTrue(df.empty)

    @patch('utils.stock_data.ak')
    def test_get_realtime_price_failure(self, mock_ak):
        """Test that get_realtime_price returns empty dict on failure."""
        mock_ak.stock_zh_a_hist.side_effect = Exception("Network Error")
        mock_ak.stock_zh_a_daily.side_effect = Exception("Network Error")
        
        data = stock_data.get_realtime_price("600519")
        
        self.assertIsInstance(data, dict)
        self.assertEqual(data, {})

    @patch('utils.stock_data.ak')
    def test_get_realtime_price_success(self, mock_ak):
        """Test success case with mocked real data structure."""
        # Mock successful return from stock_zh_a_hist
        mock_df = pd.DataFrame({
            "日期": ["2023-01-01", "2023-01-02"],
            "开盘": [100.0, 102.0],
            "收盘": [101.0, 103.0],
            "最高": [102.0, 104.0],
            "最低": [99.0, 101.0],
            "成交量": [1000, 1200]
        })
        mock_ak.stock_zh_a_hist.return_value = mock_df
        
        data = stock_data.get_realtime_price("600519")
        
        self.assertEqual(data['latest'], 103.0)
        # Change calculation: (103 - 101) / 101 * 100 = 1.98...
        self.assertAlmostEqual(data['change'], 1.98, places=2)

if __name__ == '__main__':
    unittest.main()
