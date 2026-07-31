"""app_version — App Store 라이브 버전 자동 추적 회귀 테스트.

핵심 불변식:
- 자동 반영은 '올리기'만 한다 (스토어 심사 중 버전으로 먼저 안내하지 않음,
  수동으로 더 높게 잡은 값은 유지).
- 스토어 조회 실패는 저장값 서빙에 영향을 주지 않는다 (fail-open).
"""

import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import app_version


class AppVersionAutoTrackTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config_path = Path(self.temp_dir.name) / "app_version.json"
        self._orig_config_path = app_version.CONFIG_PATH
        self._orig_ttl = app_version.STORE_TTL_SECONDS
        app_version.CONFIG_PATH = self.config_path
        # 테스트에서 백그라운드 네트워크 갱신 스레드가 돌지 않도록 비활성.
        app_version.STORE_TTL_SECONDS = 0
        self._reset_store_cache()

    def tearDown(self) -> None:
        app_version.CONFIG_PATH = self._orig_config_path
        app_version.STORE_TTL_SECONDS = self._orig_ttl
        self._reset_store_cache()
        self.temp_dir.cleanup()

    def _reset_store_cache(self, version=None) -> None:
        with app_version._store_lock:
            app_version._store_cache["version"] = version
            app_version._store_cache["fetched_at"] = 0.0

    def _write_config(self, latest: str, min_supported: str = "1.0.0") -> None:
        config = dict(app_version.DEFAULTS)
        config["latest"] = latest
        config["min_supported"] = min_supported
        self.config_path.write_text(json.dumps(config), encoding="utf-8")

    def _read_persisted(self) -> dict:
        return json.loads(self.config_path.read_text(encoding="utf-8"))

    # --- 버전 비교 ---

    def test_is_newer_numeric_compare(self) -> None:
        self.assertTrue(app_version._is_newer("1.10.0", "1.2.4"))
        self.assertTrue(app_version._is_newer("1.4.0", "1.2.4"))
        self.assertFalse(app_version._is_newer("1.2.4", "1.2.4"))
        self.assertFalse(app_version._is_newer("1.2.3", "1.2.4"))

    def test_is_newer_malformed_is_false(self) -> None:
        self.assertFalse(app_version._is_newer("beta", "1.2.4"))
        self.assertFalse(app_version._is_newer("", "1.2.4"))
        self.assertFalse(app_version._is_newer(None, "1.2.4"))

    # --- 자동 반영 ---

    def test_store_newer_bumps_latest_and_persists(self) -> None:
        self._write_config("1.2.4")
        self._reset_store_cache("1.4.0")

        result = app_version.get_app_version()

        self.assertEqual(result["latest"], "1.4.0")
        self.assertEqual(result["store_latest"], "1.4.0")
        # 영속화 — 다음 재시작/조회 실패에도 유지된다.
        persisted = json.loads(self.config_path.read_text(encoding="utf-8"))
        self.assertEqual(persisted["latest"], "1.4.0")
        # min_supported(강제 업데이트)는 자동으로 건드리지 않는다.
        self.assertEqual(result["min_supported"], "1.0.0")

    def test_store_equal_or_older_keeps_stored(self) -> None:
        self._write_config("1.2.4")
        self._reset_store_cache("1.2.4")
        self.assertEqual(app_version.get_app_version()["latest"], "1.2.4")

        self._reset_store_cache("1.2.0")
        self.assertEqual(app_version.get_app_version()["latest"], "1.2.4")

    def test_manual_value_above_store_is_respected(self) -> None:
        # 어드민이 스토어보다 높게 잡아둔 경우(선공지) — 자동이 끌어내리지 않는다.
        self._write_config("1.5.0")
        self._reset_store_cache("1.4.0")
        self.assertEqual(app_version.get_app_version()["latest"], "1.5.0")

    def test_store_unavailable_serves_stored_value(self) -> None:
        self._write_config("1.2.4")
        self._reset_store_cache(None)
        result = app_version.get_app_version()
        self.assertEqual(result["latest"], "1.2.4")
        self.assertNotIn("store_latest", result)

    # --- 스토어 조회 파싱 ---

    def test_fetch_store_version_rejects_bad_shape(self) -> None:
        class FakeResp:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self):
                return json.dumps({"results": [{"version": "not-a-version"}]}).encode()

        with patch.object(app_version.urllib.request, "urlopen", return_value=FakeResp()):
            self.assertIsNone(app_version._fetch_store_version())

    def test_fetch_store_version_network_error_returns_none(self) -> None:
        with patch.object(
            app_version.urllib.request, "urlopen", side_effect=OSError("boom")
        ):
            self.assertIsNone(app_version._fetch_store_version())

    # --- 쓰기 안전성 ---

    def test_auto_bump_does_not_clobber_concurrent_admin_save(self) -> None:
        """자동 반영은 락 안에서 다시 읽는다 — 낡은 스냅샷으로 덮어쓰지 않는다.

        릴리즈 직후(스토어 > 저장값)에 어드민이 min_supported 를 올리는 창에서,
        auto-bump 가 POST 이전 스냅샷을 그대로 쓰면 강제 업데이트 설정이 조용히
        롤백된다. _apply_store_latest 에 락 밖 스냅샷을 넘겨 재현한다.
        """
        self._write_config("1.2.4", min_supported="1.0.0")
        stale = self._read_persisted()  # 어드민 POST 이전 상태
        self._reset_store_cache("1.4.0")

        # 그 사이 어드민이 강제 업데이트 기준을 올렸다.
        self._write_config("1.2.4", min_supported="1.3.0")

        result = app_version._apply_store_latest(stale)

        self.assertEqual(result["latest"], "1.4.0")
        self.assertEqual(result["min_supported"], "1.3.0")
        self.assertEqual(self._read_persisted()["min_supported"], "1.3.0")

    def test_write_config_is_atomic_and_leaves_no_temp(self) -> None:
        self._write_config("1.2.4")
        app_version._write_config({**app_version.DEFAULTS, "latest": "1.4.0"})
        self.assertEqual(self._read_persisted()["latest"], "1.4.0")
        leftovers = [p.name for p in self.config_path.parent.glob("*.tmp")]
        self.assertEqual(leftovers, [])

    def test_write_failure_leaves_previous_config_intact(self) -> None:
        """교체 전에 실패하면 기존 파일이 그대로 남는다(잘린 JSON 없음)."""
        self._write_config("1.2.4", min_supported="1.3.0")
        with patch.object(app_version.os, "replace", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                app_version._write_config(
                    {**app_version.DEFAULTS, "latest": "1.4.0"}
                )
        persisted = self._read_persisted()
        self.assertEqual(persisted["latest"], "1.2.4")
        self.assertEqual(persisted["min_supported"], "1.3.0")
        self.assertEqual([p.name for p in self.config_path.parent.glob("*.tmp")], [])

    def test_thread_start_failure_recovers_flag_and_does_not_raise(self) -> None:
        """스레드 생성 실패가 요청을 500 으로 만들거나 자동 추적을 죽이지 않는다."""
        self._write_config("1.2.4")
        app_version.STORE_TTL_SECONDS = 21600  # 갱신 경로를 켠다
        with patch.object(
            app_version.threading, "Thread", side_effect=RuntimeError("can't start new thread")
        ):
            app_version._maybe_refresh_store_cache_async()  # 예외가 새어나오면 실패
        self.assertFalse(app_version._refresh_in_flight)

        # 플래그가 풀렸으므로 다음 요청이 갱신을 다시 시도한다.
        with patch.object(app_version, "_fetch_store_version", return_value="1.4.0") as fetch:
            app_version._maybe_refresh_store_cache_async()
            for _ in range(200):
                if fetch.called:
                    break
                time.sleep(0.01)
        self.assertTrue(fetch.called)

    # --- 어드민 수동 갱신 경로 보존 ---

    def test_admin_update_still_writes_both_fields(self) -> None:
        self._write_config("1.2.4")
        payload = app_version.AppVersionUpdate(latest="1.4.0", min_supported="1.2.0")
        result = app_version.update_app_version(payload)
        self.assertEqual(result["latest"], "1.4.0")
        self.assertEqual(result["min_supported"], "1.2.0")
        persisted = json.loads(self.config_path.read_text(encoding="utf-8"))
        self.assertEqual(persisted["min_supported"], "1.2.0")


if __name__ == "__main__":
    unittest.main()
