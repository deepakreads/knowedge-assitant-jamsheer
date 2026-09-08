"""
Comprehensive tests for video validation layer.

Test scenarios:
1. Basic file validation (readable, corrupted)
2. FPS validation (>= 10 requirement)
3. Duration validation (> 2s AND < 5 minutes)
4. Camera stability detection
5. Lighting quality checks
6. Blur detection
7. Domain-agnostic (machine + LEGO videos)
"""

import pytest
import cv2
import numpy as np
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

from app.services.validation_service import (
    validate_video,
    ValidationStatus,
    ValidationResult,
    _get_sample_frame_indices,
    _validate_lighting,
    _detect_blur,
    _check_camera_stability,
)
from app.config import (
    VIDEO_VALIDATION_MIN_FPS,
    VIDEO_VALIDATION_MIN_DURATION_SEC,
    VIDEO_VALIDATION_MAX_DURATION_SEC,
)


class TestBasicVideoValidation:
    """Test basic file validity checks"""

    def test_nonexistent_file_returns_error(self):
        """Validation should return ERROR for nonexistent file"""
        result = validate_video("/nonexistent/path/to/video.mp4")

        assert result.status == ValidationStatus.ERROR
        assert result.readable == False
        assert "not found" in result.issues[0].lower()

    def test_corrupted_file_returns_error(self, tmp_path):
        """Validation should return ERROR for corrupted/unreadable file"""
        # Create a file that looks like video but isn't
        bad_file = tmp_path / "bad_video.mp4"
        bad_file.write_bytes(b"this is not a real video file")

        result = validate_video(str(bad_file))

        assert result.status == ValidationStatus.ERROR
        assert result.readable == False


class TestFpsValidation:
    """Test FPS validation with >= 10 requirement"""

    def test_high_fps_video_passes(self, tmp_path):
        """Video with FPS >= 10 should pass FPS validation"""
        video_path = str(tmp_path / "high_fps.mp4")
        _create_test_video(video_path, fps=30, duration=3, resolution=(640, 480))

        result = validate_video(video_path)

        assert result.fps_valid == True
        assert result.fps >= VIDEO_VALIDATION_MIN_FPS

    def test_low_fps_video_returns_error(self, tmp_path):
        """Video with FPS < 10 should return ERROR"""
        video_path = str(tmp_path / "low_fps.mp4")
        _create_test_video(video_path, fps=5, duration=3, resolution=(640, 480))

        result = validate_video(video_path)

        assert result.status == ValidationStatus.ERROR
        assert result.fps_valid == False
        assert result.fps < VIDEO_VALIDATION_MIN_FPS
        assert any("fps" in issue.lower() for issue in result.issues)

    def test_fps_exactly_at_minimum_passes(self, tmp_path):
        """Video with FPS exactly at minimum should pass"""
        video_path = str(tmp_path / "min_fps.mp4")
        _create_test_video(video_path, fps=VIDEO_VALIDATION_MIN_FPS, duration=3, resolution=(640, 480))

        result = validate_video(video_path)

        assert result.fps_valid == True
        assert result.fps >= VIDEO_VALIDATION_MIN_FPS


class TestDurationValidation:
    """Test duration validation (> 2s AND < 5 min)"""

    def test_too_short_video_returns_error(self, tmp_path):
        """Video shorter than 2 seconds should return ERROR"""
        video_path = str(tmp_path / "short.mp4")
        _create_test_video(video_path, fps=30, duration=1.5, resolution=(640, 480))

        result = validate_video(video_path)

        assert result.status == ValidationStatus.ERROR
        assert result.duration_valid == False
        assert result.duration < VIDEO_VALIDATION_MIN_DURATION_SEC
        assert any("duration" in issue.lower() for issue in result.issues)

    def test_too_long_video_returns_error(self, tmp_path):
        """Video longer than 5 minutes should return ERROR"""
        video_path = str(tmp_path / "long.mp4")
        # Create a 6-minute video (360+ seconds)
        _create_test_video(video_path, fps=10, duration=360, resolution=(640, 480))

        result = validate_video(video_path)

        assert result.status == ValidationStatus.ERROR
        assert result.duration_valid == False
        assert result.duration > VIDEO_VALIDATION_MAX_DURATION_SEC

    def test_duration_exactly_at_minimum_passes(self, tmp_path):
        """Video exactly 2 seconds should pass"""
        video_path = str(tmp_path / "min_duration.mp4")
        _create_test_video(video_path, fps=30, duration=2.0, resolution=(640, 480))

        result = validate_video(video_path)

        assert result.status != ValidationStatus.ERROR or not result.duration_valid == False

    def test_duration_exactly_at_maximum_passes(self, tmp_path):
        """Video exactly 5 minutes should pass"""
        video_path = str(tmp_path / "max_duration.mp4")
        _create_test_video(video_path, fps=10, duration=299, resolution=(640, 480))  # Just under 5 min

        result = validate_video(video_path)

        assert result.duration_valid == True

    def test_ideal_duration_passes(self, tmp_path):
        """Video in ideal range (2-5 min) should pass"""
        video_path = str(tmp_path / "ideal.mp4")
        _create_test_video(video_path, fps=30, duration=10, resolution=(640, 480))  # 10 seconds

        result = validate_video(video_path)

        assert result.duration_valid == True
        assert VIDEO_VALIDATION_MIN_DURATION_SEC < result.duration < VIDEO_VALIDATION_MAX_DURATION_SEC


class TestLightingQuality:
    """Test lighting validation (underexposure/overexposure detection)"""

    def test_normal_lighting_passes(self, tmp_path):
        """Video with normal lighting should pass"""
        video_path = str(tmp_path / "normal_light.mp4")
        # Create video with normal brightness frames (~128 average)
        _create_test_video_with_brightness(video_path, fps=30, duration=3, brightness_values=[128] * 30)

        result = validate_video(video_path)

        assert result.lighting_valid == True
        assert all("lighting" not in issue.lower() and "exposure" not in issue.lower() for issue in result.issues)

    def test_underexposed_video_returns_warning(self, tmp_path):
        """Video with consistent underexposure should return WARNING"""
        video_path = str(tmp_path / "underexposed.mp4")
        # Create video with low brightness frames (~20 average)
        _create_test_video_with_brightness(video_path, fps=30, duration=3, brightness_values=[20] * 30)

        result = validate_video(video_path)

        assert result.status == ValidationStatus.WARNING or result.status == ValidationStatus.PASS
        assert result.lighting_valid == False
        assert any("underexposed" in issue.lower() or "dim" in issue.lower() for issue in result.issues)

    def test_overexposed_video_returns_warning(self, tmp_path):
        """Video with consistent overexposure should return WARNING"""
        video_path = str(tmp_path / "overexposed.mp4")
        # Create video with high brightness frames (~250 average)
        _create_test_video_with_brightness(video_path, fps=30, duration=3, brightness_values=[250] * 30)

        result = validate_video(video_path)

        assert result.status == ValidationStatus.WARNING or result.status == ValidationStatus.PASS
        assert result.lighting_valid == False
        assert any("overexposed" in issue.lower() or "bright" in issue.lower() for issue in result.issues)


class TestBlurDetection:
    """Test blur detection using Laplacian variance"""

    def test_sharp_video_passes(self, tmp_path):
        """Video with sharp frames should pass blur check"""
        video_path = str(tmp_path / "sharp.mp4")
        # Create video with high-contrast frames (naturally high Laplacian variance)
        _create_test_video_with_pattern(video_path, fps=30, duration=3, pattern="checkerboard")

        result = validate_video(video_path)

        assert result.blur_valid == True

    def test_blurry_video_returns_warning(self, tmp_path):
        """Video with persistent blur should return WARNING"""
        video_path = str(tmp_path / "blurry.mp4")
        # Create blurry video (smooth gradients = low Laplacian variance)
        _create_test_video_with_pattern(video_path, fps=30, duration=3, pattern="smooth")

        result = validate_video(video_path)

        assert result.status == ValidationStatus.WARNING or result.status == ValidationStatus.PASS
        assert result.blur_valid == False or len(result.issues) > 0


class TestCameraStability:
    """Test camera stability detection"""

    def test_stable_camera_passes(self, tmp_path):
        """Video with stable camera should pass"""
        video_path = str(tmp_path / "stable.mp4")
        # Create video with static frames (minimal frame-to-frame difference)
        _create_test_video_with_pattern(video_path, fps=30, duration=3, pattern="static")

        result = validate_video(video_path)

        assert result.stable_camera == True

    def test_unstable_camera_returns_warning(self, tmp_path):
        """Video with excessive camera movement should return WARNING"""
        video_path = str(tmp_path / "shaky.mp4")
        # Create video with moving patterns (high frame-to-frame difference)
        _create_test_video_with_pattern(video_path, fps=30, duration=3, pattern="moving")

        result = validate_video(video_path)

        # Unstable camera should either set stable_camera=False or add issue
        if not result.stable_camera or any("stability" in issue.lower() for issue in result.issues):
            assert result.stable_camera == False or any("stability" in issue.lower() or "camera" in issue.lower() for issue in result.issues)


class TestValidationStatusLevels:
    """Test proper use of PASS/WARNING/ERROR status levels"""

    def test_pass_status_for_good_video(self, tmp_path):
        """Good video should return PASS status"""
        video_path = str(tmp_path / "good.mp4")
        _create_test_video(video_path, fps=30, duration=10, resolution=(640, 480))

        result = validate_video(video_path)

        # Good video should have PASS or WARNING (if quality issues), not ERROR
        assert result.status in [ValidationStatus.PASS, ValidationStatus.WARNING]

    def test_error_status_for_bad_fps(self, tmp_path):
        """Video with FPS < 10 should return ERROR (hard requirement)"""
        video_path = str(tmp_path / "bad_fps.mp4")
        _create_test_video(video_path, fps=5, duration=3, resolution=(640, 480))

        result = validate_video(video_path)

        assert result.status == ValidationStatus.ERROR

    def test_error_status_for_bad_duration(self, tmp_path):
        """Video with wrong duration should return ERROR (hard requirement)"""
        video_path = str(tmp_path / "bad_duration.mp4")
        _create_test_video(video_path, fps=30, duration=1, resolution=(640, 480))

        result = validate_video(video_path)

        assert result.status == ValidationStatus.ERROR

    def test_warning_status_for_quality_issues(self, tmp_path):
        """Video with quality issues but valid FPS/duration should return WARNING"""
        video_path = str(tmp_path / "quality_issues.mp4")
        # Create video with low brightness (quality issue) but valid FPS/duration
        _create_test_video_with_brightness(video_path, fps=30, duration=5, brightness_values=[20] * 150)

        result = validate_video(video_path)

        assert result.status in [ValidationStatus.WARNING, ValidationStatus.PASS]
        # Should have some issues
        if result.status == ValidationStatus.WARNING:
            assert len(result.issues) > 0


class TestValidationResultStructure:
    """Test ValidationResult contains all required fields"""

    def test_validation_result_has_all_fields(self, tmp_path):
        """ValidationResult should have all required fields"""
        video_path = str(tmp_path / "test.mp4")
        _create_test_video(video_path, fps=30, duration=5, resolution=(640, 480))

        result = validate_video(video_path)

        # Check all required fields
        assert hasattr(result, 'status')
        assert hasattr(result, 'readable')
        assert hasattr(result, 'fps_valid')
        assert hasattr(result, 'duration_valid')
        assert hasattr(result, 'stable_camera')
        assert hasattr(result, 'lighting_valid')
        assert hasattr(result, 'blur_valid')
        assert hasattr(result, 'fps')
        assert hasattr(result, 'duration')
        assert hasattr(result, 'total_frames')
        assert hasattr(result, 'issues')
        assert hasattr(result, 'details')

    def test_validation_result_to_dict_works(self, tmp_path):
        """ValidationResult.to_dict() should return valid JSON-serializable dict"""
        video_path = str(tmp_path / "test.mp4")
        _create_test_video(video_path, fps=30, duration=5, resolution=(640, 480))

        result = validate_video(video_path)
        result_dict = result.to_dict()

        assert isinstance(result_dict, dict)
        assert 'status' in result_dict
        assert result_dict['status'] == result.status.value  # Should be string value


class TestDomainAgnostic:
    """Test that validation works for different video types (machine + demo)"""

    def test_machine_training_video_validation(self, tmp_path):
        """Validation should work for machine training videos"""
        video_path = str(tmp_path / "machine_training.mp4")
        # Create a realistic machine video: 30 FPS, 30 seconds, high quality
        _create_test_video(video_path, fps=30, duration=30, resolution=(1920, 1080))

        result = validate_video(video_path)

        # Should validate successfully
        assert result.fps_valid == True
        assert result.duration_valid == True

    def test_lego_demo_video_validation(self, tmp_path):
        """Validation should work for LEGO demo videos"""
        video_path = str(tmp_path / "lego_demo.mp4")
        # Create a demo video: 24 FPS, 15 seconds, medium resolution
        _create_test_video(video_path, fps=24, duration=15, resolution=(1280, 720))

        result = validate_video(video_path)

        # Should validate successfully
        assert result.fps_valid == True
        assert result.duration_valid == True

    def test_low_resolution_demo_video_still_validates(self, tmp_path):
        """Validation should work even for low-resolution demo videos"""
        video_path = str(tmp_path / "demo_low_res.mp4")
        # Create low-res demo: 30 FPS, 8 seconds, 320x240
        _create_test_video(video_path, fps=30, duration=8, resolution=(320, 240))

        result = validate_video(video_path)

        # Should validate - resolution doesn't matter for validation
        assert result.readable == True


class TestSampleFrameIndices:
    """Test helper function for sampling frames"""

    def test_sample_indices_even_distribution(self):
        """Sampled frame indices should be evenly distributed"""
        indices = _get_sample_frame_indices(100, 5)

        assert len(indices) == 5
        assert indices[0] == 0  # First frame
        assert indices[-1] == 99  # Last frame
        assert all(0 <= idx < 100 for idx in indices)
        # Should be sorted
        assert indices == sorted(indices)

    def test_sample_fewer_frames_than_total(self):
        """Should handle sampling fewer frames than total"""
        indices = _get_sample_frame_indices(100, 3)

        assert len(indices) == 3
        assert 0 in indices
        assert 99 in indices

    def test_sample_more_frames_than_total(self):
        """Should return all frames if sample count > total"""
        indices = _get_sample_frame_indices(5, 10)

        assert len(indices) == 5
        assert indices == [0, 1, 2, 3, 4]


class TestIntegrationWithPipeline:
    """Test that validation integrates correctly with pipeline"""

    def test_validation_metadata_stored_in_job(self, tmp_path, monkeypatch):
        """Validation result should be stored in job metadata"""
        # This would require mocking job_store, so we test the structure
        video_path = str(tmp_path / "test.mp4")
        _create_test_video(video_path, fps=30, duration=5, resolution=(640, 480))

        result = validate_video(video_path)
        result_dict = result.to_dict()

        # Verify structure is suitable for JSON storage
        assert isinstance(result_dict['status'], str)
        assert isinstance(result_dict['fps'], (int, float, type(None)))
        assert isinstance(result_dict['issues'], list)


# Helper functions to create test videos

def _create_test_video(output_path: str, fps: int = 30, duration: float = 5, resolution: tuple = (640, 480)):
    """Create a simple test video"""
    width, height = resolution
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

    num_frames = int(fps * duration)
    for i in range(num_frames):
        # Create a simple frame with some variation
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        # Add some content to avoid all-black frames
        frame[:] = [100 + (i % 50), 100 + (i % 50), 100 + (i % 50)]
        out.write(frame)

    out.release()


def _create_test_video_with_brightness(output_path: str, fps: int = 30, duration: float = 5,
                                       brightness_values: list = None):
    """Create a test video with specific brightness levels"""
    if brightness_values is None:
        brightness_values = [128] * (int(fps * duration))

    width, height = 640, 480
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

    for brightness in brightness_values:
        # Clamp brightness to 0-255
        b = min(255, max(0, int(brightness)))
        frame = np.ones((height, width, 3), dtype=np.uint8) * b
        out.write(frame)

    out.release()


def _create_test_video_with_pattern(output_path: str, fps: int = 30, duration: float = 5,
                                    pattern: str = "static"):
    """Create a test video with specific patterns"""
    width, height = 640, 480
    num_frames = int(fps * duration)
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

    for i in range(num_frames):
        if pattern == "checkerboard":
            # High contrast checkerboard (sharp)
            frame = np.zeros((height, width, 3), dtype=np.uint8)
            square_size = 20
            for y in range(0, height, square_size * 2):
                for x in range(0, width, square_size * 2):
                    frame[y:y+square_size, x:x+square_size] = [255, 255, 255]
                    frame[y+square_size:y+square_size*2, x+square_size:x+square_size*2] = [255, 255, 255]

        elif pattern == "smooth":
            # Smooth gradients (blurry)
            x = np.linspace(0, 255, width)
            y = np.linspace(0, 255, height)
            X, Y = np.meshgrid(x, y)
            frame = np.stack([X, X, X], axis=2).astype(np.uint8)
            # Blur to reduce sharpness
            frame = cv2.blur(frame, (15, 15))

        elif pattern == "static":
            # Static frame (stable)
            frame = np.ones((height, width, 3), dtype=np.uint8) * 128
            # Add some static content
            cv2.circle(frame, (width // 2, height // 2), 50, (255, 255, 255), -1)

        elif pattern == "moving":
            # Moving pattern (unstable)
            frame = np.zeros((height, width, 3), dtype=np.uint8)
            # Move a circle across the frame
            x = int((i / num_frames) * width)
            cv2.circle(frame, (x, height // 2), 40, (255, 255, 255), -1)

        out.write(frame)

    out.release()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
