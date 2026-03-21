"""Integration tests for Google Maps tool"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, ANY
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from data_sources.maps.google_maps import GoogleMapsTool


class TestGoogleMapsIntegration:
    """Test Google Maps tool integration"""

    @pytest.fixture
    def tool(self, tmp_path):
        """Create a GoogleMapsTool with temporary cache directory"""
        return GoogleMapsTool(cache_dir=tmp_path / "cache")

    def test_tool_initialization(self, tool):
        """Test that tool initializes correctly"""
        assert tool is not None
        assert tool.cache_dir.exists()

    @patch('data_sources.maps.google_maps_scraper.search_google_maps')
    def test_search_returns_structured_data(self, mock_search, tool):
        """Test that search returns properly structured data"""
        # Mock the scraper response
        mock_search.return_value = [
            {
                'name': 'Test HVAC',
                'address': '123 Main St, Los Angeles, CA',
                'phone': '(310) 555-0100',
                'website': 'testhvac.com',
                'rating': 4.5,
                'reviews': 100,
                'place_id': 'test123',
                'lat': 34.0522,
                'lng': -118.2437,
                'category': 'HVAC'
            }
        ]

        # Call search
        result = tool.search(
            industry='HVAC',
            location='Los Angeles',
            max_results=10,
            use_cache=False
        )

        # Verify structure
        assert 'source' in result
        assert result['source'] == 'google_maps'
        assert 'search_date' in result
        assert 'industry' in result
        assert result['industry'] == 'HVAC'
        assert 'location' in result
        assert result['location'] == 'Los Angeles'
        assert 'total_found' in result
        assert result['total_found'] == 1
        assert 'results' in result
        assert len(result['results']) == 1

        # Verify business structure
        business = result['results'][0]
        assert business['name'] == 'Test HVAC'
        assert business['address'] == '123 Main St, Los Angeles, CA'
        assert business['phone'] == '(310) 555-0100'
        assert business['website'] == 'testhvac.com'
        assert business['rating'] == 4.5
        assert business['reviews'] == 100
        assert business['place_id'] == 'test123'

    @patch('data_sources.maps.google_maps_scraper.search_google_maps')
    def test_caching_works(self, mock_search, tool):
        """Test that caching works correctly"""
        # Mock the scraper response
        mock_search.return_value = [
            {'name': 'Test Business', 'place_id': 'test123'}
        ]

        # First call - should call scraper
        result1 = tool.search(
            industry='car wash',
            location='Houston',
            max_results=10,
            use_cache=True
        )
        assert mock_search.call_count == 1
        assert result1['total_found'] == 1

        # Second call - should use cache
        result2 = tool.search(
            industry='car wash',
            location='Houston',
            max_results=10,
            use_cache=True
        )
        # Scraper should still only be called once
        assert mock_search.call_count == 1
        assert result2['total_found'] == 1

    @patch('data_sources.maps.google_maps_scraper.search_google_maps')
    def test_no_cache_bypasses_cache(self, mock_search, tool):
        """Test that no_cache flag bypasses cache"""
        # Mock the scraper response
        mock_search.return_value = [
            {'name': 'Test Business', 'place_id': 'test123'}
        ]

        # First call with cache
        result1 = tool.search(
            industry='pizza',
            location='Chicago',
            max_results=10,
            use_cache=True
        )
        assert mock_search.call_count == 1

        # Second call without cache
        result2 = tool.search(
            industry='pizza',
            location='Chicago',
            max_results=10,
            use_cache=False
        )
        # Scraper should be called twice
        assert mock_search.call_count == 2

    @patch('data_sources.maps.google_maps_scraper.search_google_maps')
    def test_max_results_respected(self, mock_search, tool):
        """Test that max_results parameter is respected"""
        # Mock the scraper to return many results
        mock_search.return_value = [
            {'name': f'Business {i}', 'place_id': f'test{i}'}
            for i in range(100)
        ]

        # Request only 25 results
        result = tool.search(
            industry='HVAC',
            location='Los Angeles',
            max_results=25,
            use_cache=False
        )

        # Verify max_results was passed to scraper
        mock_search.assert_called_once_with(
            industry='HVAC',
            city='Los Angeles',
            api_key=ANY,
            max_results=25
        )

    @patch('data_sources.maps.google_maps_scraper.search_google_maps')
    def test_handles_empty_results(self, mock_search, tool):
        """Test that tool handles empty results gracefully"""
        # Mock empty response
        mock_search.return_value = []

        result = tool.search(
            industry='nonexistent',
            location='Nowhere',
            max_results=10,
            use_cache=False
        )

        assert result['total_found'] == 0
        assert result['results'] == []

    def test_cache_ttl_is_90_days(self, tool):
        """Test that cache TTL is set to 90 days"""
        assert tool.CACHE_TTL_DAYS == 90


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
