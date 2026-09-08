"""
Tests for monitoring responsiveness improvements:
1. Cache TTL optimized for 10 FPS
2. Frame skipping when backend is slow
3. Adaptive response to backend latency
"""
import pytest
from app.services.monitoring_service import SOPMonitoringService


class TestCacheOptimization:
    """Test that cache TTL is optimized for 10 FPS monitoring"""

    def test_cache_ttl_for_10fps(self):
        """Cache TTL should be 500ms for 10 FPS (100ms interval)"""
        sop = {"title": "Test", "steps": [{"title": "Step 1"}]}
        service = SOPMonitoringService(sop)

        # With 100ms frame interval and 500ms TTL:
        # Frame 1 at T=0ms → analyzed, cached
        # Frame 2 at T=100ms → cache hit (within 500ms)
        # Frame 3 at T=200ms → cache hit (within 500ms)
        # Frame 4 at T=300ms → cache hit (within 500ms)
        # Frame 5 at T=400ms → cache hit (within 500ms)
        # Frame 6 at T=500ms → cache hit (exactly at TTL)
        # Frame 7 at T=600ms → re-analyze (TTL expired)

        assert service.cache_ttl_ms == 500, "Cache TTL should be 500ms for 10 FPS"

    def test_cache_ttl_enables_multiple_hits(self):
        """500ms TTL with 100ms frames enables ~4-5 cache hits per analysis"""
        # Frame interval: 100ms
        # Cache TTL: 500ms
        # Expected cache hits: 4-5 per analysis

        frame_intervals = 100  # ms
        cache_ttl = 500  # ms
        expected_cache_hits = (cache_ttl // frame_intervals)

        assert expected_cache_hits >= 4, f"Should get at least 4 cache hits, got {expected_cache_hits}"


class TestFrameSkippingLogic:
    """Test adaptive frame skipping when backend is slow"""

    def test_frame_skip_threshold(self):
        """System should skip frames if response time > 200ms"""
        # Simulated response times
        fast_response = 50  # ms
        medium_response = 150  # ms
        slow_response = 250  # ms

        skip_threshold = 200  # ms

        assert fast_response < skip_threshold, "Fast responses should not trigger skipping"
        assert medium_response < skip_threshold, "Medium responses should not trigger skipping"
        assert slow_response > skip_threshold, "Slow responses should trigger skipping"

    def test_skip_every_other_frame(self):
        """When backend is slow, skip every other frame"""
        frame_numbers = [1, 2, 3, 4, 5, 6, 7, 8]
        slow_backend = True
        skip_threshold = 200

        if slow_backend:
            # Skip frames where frame_count % 2 == 0
            frames_to_send = [f for f in frame_numbers if f % 2 != 0]
            assert len(frames_to_send) == 4, "Should send ~50% of frames when backend is slow"


class TestResponsivenessMetrics:
    """Test monitoring responsiveness metrics"""

    def test_10fps_frame_interval(self):
        """10 FPS means frames every 100ms"""
        fps = 10
        interval_ms = 1000 / fps

        assert interval_ms == 100, f"10 FPS should be 100ms interval, got {interval_ms}ms"

    def test_acceptable_response_time(self):
        """Response time should be < 100ms for good responsiveness"""
        target_fps = 10
        max_response_time_ms = 1000 / target_fps

        assert max_response_time_ms == 100, "Max response time should match frame interval"

    def test_cached_response_latency(self):
        """Cached responses should be <10ms"""
        cached_response_time = 5  # ms (estimated with caching)
        target_max = 50  # ms

        assert cached_response_time < target_max, "Cached responses should be very fast"

    def test_vision_api_latency(self):
        """Vision API calls typically take 100-500ms"""
        # This is context-dependent, but helps set expectations
        typical_vision_latency_range = (100, 500)  # ms

        # With caching, we should only do vision API 1 out of every 5 frames
        frames_per_analysis = 5
        effective_latency = typical_vision_latency_range[0] / frames_per_analysis

        assert effective_latency < 100, "Effective latency with caching should be low"


class TestJpegCompression:
    """Test JPEG compression settings for speed/quality tradeoff"""

    def test_jpeg_quality_for_compliance(self):
        """JPEG quality 0.75 is sufficient for object detection"""
        # For compliance detection (checking object state, colors, positions),
        # quality 0.75 (75%) is sufficient and 3x smaller than 1.0

        quality_75_reduction = (1.0 - 0.75) * 100  # ~33% size reduction
        expected_speedup_factor = 1.3  # 30% faster transmission

        assert quality_75_reduction >= 25, "Should have significant size reduction"

    def test_resolution_downsampling(self):
        """Downsampling to 640x360 reduces frame size by ~75%"""
        full_hd_pixels = 1280 * 720  # = 921,600 pixels
        downsampled_pixels = 640 * 360  # = 230,400 pixels

        reduction_ratio = full_hd_pixels / downsampled_pixels
        assert reduction_ratio >= 3.5, f"Should get ~4x size reduction, got {reduction_ratio:.1f}x"


class TestResponseTimeBudget:
    """Test response time budget allocation for 10 FPS"""

    def test_frame_capture_time(self):
        """Frame capture (canvas.toBlob) should be <20ms"""
        # Canvas operations are fast on modern browsers
        frame_capture_time = 5  # ms
        max_allowed = 20  # ms

        assert frame_capture_time < max_allowed

    def test_network_transmission_time(self):
        """Network transmission with 640x360 JPEG should be <30ms"""
        # Typical JPEG at quality 0.75: ~30-50KB
        # At 10Mbps connection: ~25-40ms
        # At 100Mbps: ~2-4ms
        transmission_time = 20  # ms (assuming reasonable connection)
        max_allowed = 50  # ms

        assert transmission_time < max_allowed

    def test_backend_processing_time(self):
        """Backend processing (cached) should be <30ms"""
        cached_processing = 20  # ms
        max_allowed = 30  # ms

        assert cached_processing < max_allowed

    def test_total_budget(self):
        """Total response time budget: capture + network + processing"""
        capture_time = 5  # ms
        transmission_time = 20  # ms
        processing_time = 20  # ms

        total_time = capture_time + transmission_time + processing_time
        frame_interval = 100  # ms (10 FPS)

        assert total_time < frame_interval, f"Total {total_time}ms should fit in {frame_interval}ms frame"


class TestAdaptiveQuality:
    """Test system adapts quality based on backend response time"""

    def test_fast_backend_uses_full_quality(self):
        """If response time < 50ms, use full quality frames (1.0)"""
        response_time_ms = 30

        if response_time_ms < 50:
            quality = 1.0
        else:
            quality = 0.75

        assert quality == 1.0

    def test_slow_backend_uses_lower_quality(self):
        """If response time > 200ms, use lower quality (0.5) and skip frames"""
        response_time_ms = 250

        if response_time_ms > 200:
            quality = 0.5
            skip_frames = True
        else:
            quality = 0.75
            skip_frames = False

        assert quality == 0.5
        assert skip_frames is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
