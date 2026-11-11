"""인스타그램 Daily Verse 자동 게시 (이슈 #62) — 캡션 규칙·말씀 고르기·토큰·게시 흐름·매니페스트."""

import io
import json
import os
import stat
import tempfile
import unittest
import urllib.error
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from instagram import daily_post
from instagram.caption import (
    APP_LINE, CAPTION_MAX, build_caption, display_ref, find_caption_problems, find_copy_problems,
    find_post_problems,
)
from instagram.graph import INSTAGRAM_HOST, GraphError, InstagramClient, TokenStore
from instagram.posts import MANIFEST, card_text, load_daily_verses
from instagram.selection import REPEAT_WINDOW_DAYS, app_verse_for, pick_verse_id
from notifications.verse_provider import _HOLIDAY_ONLY, text_fingerprint


class CopyRulesTest(unittest.TestCase):
    def problems(self, text, limit=125):
        return find_copy_problems(text, limit=limit, field="hook")

    def test_good_copy_passes(self):
        for text in ("For the days fear gets the first word.",
                     "Not a perfect day. Still a day worth being glad in.",
                     "Most of the words we regret came after we should have stopped talking."):
            self.assertEqual(self.problems(text), [], text)

    def test_divine_voice_is_rejected(self):
        for text in ("God is telling you to rest today.", "This is your sign to let go.",
                     "Jesus wants you to know you are loved.", "A message from heaven for you."):
            self.assertTrue(any("신의 목소리" in p for p in self.problems(text)), text)

    def test_persona_is_rejected(self):
        for text in ("I have been there too.", "As a pastor, this verse matters.", "My favorite verse."):
            self.assertTrue(any("사람이 쓴 척" in p for p in self.problems(text)), text)

    def test_ads_self_harm_dashes_length(self):
        self.assertTrue(self.problems("Daily verses, no ads."))
        self.assertTrue(self.problems("For when you want to die."))
        self.assertTrue(self.problems("Rest — then rise."))
        self.assertTrue(self.problems("Rest - then rise."))
        self.assertTrue(self.problems("x" * 126))
        self.assertTrue(self.problems("A journey of hope."))

    def test_caption_shape(self):
        caption = build_caption(hook="For the days fear gets the first word.", verse_text="Don’t be afraid.",
                                ref="Isaiah 41:10", note="A note.", cta="Save this.", topic="#courage",
                                app_line=APP_LINE)
        self.assertEqual(find_caption_problems(caption), [])
        self.assertTrue(caption.startswith("For the days fear gets the first word.\n\n“Don’t be afraid.” Isaiah 41:10 (WEB)"))
        self.assertIn("(written with AI)", caption)
        self.assertTrue(caption.endswith("#bibleverse #dailybibleverse #courage"))
        self.assertTrue(find_caption_problems(caption + "x" * CAPTION_MAX))
        with self.assertRaises(ValueError):
            build_caption(hook="h", verse_text="t", ref="r", note="n", cta="c", topic="#nope")

    def test_display_ref_and_card_text(self):
        self.assertEqual(display_ref("Psalms 34:18"), "Psalm 34:18")
        self.assertEqual(display_ref("Psalms 40:1-2"), "Psalm 40:1–2")
        self.assertEqual(display_ref("1 John 4:18"), "1 John 4:18")
        self.assertEqual(card_text("They don’t toil, neither do they spin,"),
                         "They don’t toil, neither do they spin…")
        self.assertEqual(card_text("and slow to anger;"), "and slow to anger…")
        self.assertEqual(card_text("Rest."), "Rest.")


class SelectionTest(unittest.TestCase):
    def setUp(self):
        self.items = load_daily_verses()
        self.all_ids = {i["verse_id"] for i in self.items}

    def test_same_as_app_verse(self):
        for d in (date(2026, 11, 10), date(2026, 11, 26), date(2027, 3, 3)):
            vid, reason = pick_verse_id(d, {}, self.all_ids)
            self.assertEqual((vid, reason), (app_verse_for(d).verse_id, "app"))

    def test_holiday_only_verse_only_on_its_day(self):
        self.assertEqual(pick_verse_id(date(2026, 12, 25), {}, self.all_ids)[0], "luk-2-14")
        start = date(2026, 1, 1)
        picked = {pick_verse_id(start + timedelta(n), {}, self.all_ids)[0] for n in range(400)
                  if (start + timedelta(n)).timetuple()[1:3] != (12, 25)}
        self.assertFalse(picked & _HOLIDAY_ONLY)

    def test_recent_verse_goes_to_the_far_side(self):
        d = date(2026, 11, 12)
        app = app_verse_for(d).verse_id
        recent = {app: (d - timedelta(days=5)).isoformat()}
        vid, reason = pick_verse_id(d, recent, self.all_ids)
        self.assertNotEqual(vid, app)
        self.assertEqual(reason, f"recent:{app}")
        # 다음 날 앱 말씀은 그대로 다음 차례 — 한 칸씩 밀리지 않는다
        nxt = d + timedelta(days=1)
        self.assertEqual(pick_verse_id(nxt, {**recent, vid: d.isoformat()}, self.all_ids),
                         (app_verse_for(nxt).verse_id, "app"))
        # 바꿔 올린 말씀은 앱 차례까지 반 바퀴쯤 떨어져 있다
        rotation = [i["verse_id"] for i in self.items if i["verse_id"] not in _HOLIDAY_ONLY]
        gap = (rotation.index(vid) - rotation.index(app)) % len(rotation)
        self.assertGreater(min(gap, len(rotation) - gap), REPEAT_WINDOW_DAYS)

    def test_old_post_is_fine_again(self):
        d = date(2026, 11, 12)
        app = app_verse_for(d).verse_id
        old = {app: (d - timedelta(days=REPEAT_WINDOW_DAYS + 1)).isoformat()}
        self.assertEqual(pick_verse_id(d, old, self.all_ids), (app, "app"))

    def test_missing_from_manifest(self):
        d = date(2026, 11, 12)
        app = app_verse_for(d).verse_id
        vid, reason = pick_verse_id(d, {}, self.all_ids - {app})
        self.assertEqual(reason, f"missing:{app}")
        self.assertIn(vid, self.all_ids)


# ── Graph API 가짜 ──────────────────────────────────────────────

class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FakeGraph:
    """urlopen 대역 — (메서드, 경로) 별 응답을 돌려주고 호출을 모은다."""

    def __init__(self, routes):
        self.routes = routes
        self.calls = []

    def __call__(self, req, timeout=None):
        from urllib.parse import parse_qs, urlparse

        u = urlparse(req.full_url)
        params = parse_qs(u.query or (req.data or b"").decode())
        path = u.path.split("/", 2)[-1] if u.path.startswith("/v") else u.path.lstrip("/")
        self.calls.append((req.get_method(), path, {k: v[0] for k, v in params.items()}))
        out = self.routes.get((req.get_method(), path))
        if callable(out):
            out = out()
        if isinstance(out, Exception):
            raise out
        if out is None:
            raise AssertionError(f"예상 못 한 호출 {req.get_method()} {path}")
        return FakeResponse(json.dumps(out).encode())


def http_error(code, message, token="SECRET"):
    body = json.dumps({"error": {"message": f"{message} {token}", "code": 190}}).encode()
    return urllib.error.HTTPError("u", code, "err", {}, io.BytesIO(body))


class GraphClientTest(unittest.TestCase):
    def test_publish_flow(self):
        statuses = iter([{"status_code": "IN_PROGRESS"}, {"status_code": "FINISHED"}])
        fake = FakeGraph({
            ("GET", "me"): {"user_id": "17841", "username": "withgod.app"},
            ("POST", "17841/media"): {"id": "C1"},
            ("GET", "C1"): lambda: next(statuses),
            ("POST", "17841/media_publish"): {"id": "M1"},
            ("GET", "M1"): {"permalink": "https://www.instagram.com/p/x/"},
        })
        sleeps = []
        c = InstagramClient("SECRET", host=INSTAGRAM_HOST, opener=fake, sleep=sleeps.append)
        cid = c.create_image_container("https://img/x.jpg", "cap", "alt")
        self.assertEqual(c.wait_until_finished(cid), "FINISHED")
        self.assertEqual(c.publish(cid), "M1")
        self.assertEqual(c.permalink("M1"), "https://www.instagram.com/p/x/")
        create = next(call for call in fake.calls if call[1] == "17841/media")
        self.assertEqual(create[2]["image_url"], "https://img/x.jpg")
        self.assertEqual(create[2]["alt_text"], "alt")
        self.assertEqual(sleeps, [5])

    def test_container_error_and_token_scrubbed(self):
        fake = FakeGraph({("GET", "C1"): {"status_code": "ERROR", "status": "2207026"},
                          ("POST", "1/media"): http_error(400, "bad image")})
        c = InstagramClient("SECRET", "1", opener=fake, sleep=lambda s: None)
        with self.assertRaises(GraphError):
            c.wait_until_finished("C1")
        with self.assertRaises(GraphError) as ctx:
            c.create_image_container("u", "c")
        self.assertNotIn("SECRET", str(ctx.exception))
        self.assertEqual(ctx.exception.status, 400)

    def test_me_accepts_data_array(self):
        fake = FakeGraph({("GET", "me"): {"data": [{"user_id": "9", "username": "w"}]}})
        self.assertEqual(InstagramClient("t", host=INSTAGRAM_HOST, opener=fake).me(),
                         {"user_id": "9", "username": "w"})

    def test_facebook_host_reads_account_by_id(self):
        fake = FakeGraph({("GET", "17841"): {"id": "17841", "username": "withgod.app", "media_count": 0}})
        c = InstagramClient("t", "17841", opener=fake)
        self.assertEqual(c.me()["username"], "withgod.app")
        with self.assertRaises(GraphError):
            InstagramClient("t", opener=fake).me()  # Facebook 경로는 id 가 필요하다

    def test_carousel(self):
        n = iter(range(10))
        fake = FakeGraph({
            ("POST", "17841/media"): lambda: {"id": f"K{next(n)}"},
            **{("GET", f"K{i}"): {"status_code": "FINISHED"} for i in range(10)},
        })
        c = InstagramClient("t", "17841", opener=fake, sleep=lambda s: None)
        parent = c.create_carousel(["https://a", "https://b", "https://c"], "cap", ["alt a"])
        posts = [call for call in fake.calls if call[1] == "17841/media"]
        self.assertEqual([p[2].get("is_carousel_item") for p in posts[:3]], ["true"] * 3)
        self.assertEqual(posts[0][2]["alt_text"], "alt a")
        self.assertEqual(posts[3][2]["media_type"], "CAROUSEL")
        self.assertEqual(posts[3][2]["children"], "K0,K1,K2")
        self.assertEqual(parent, "K3")
        with self.assertRaises(GraphError):
            c.create_carousel(["https://a"], "cap")


class TokenStoreTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = Path(self.dir.name) / "token.json"
        self.clock = [datetime(2026, 11, 20, tzinfo=timezone.utc)]

    def tearDown(self):
        self.dir.cleanup()

    def store(self, env="ENV1"):
        return TokenStore(self.path, env, now=lambda: self.clock[0])

    def test_seed_refresh_and_reseed(self):
        st = self.store().load()
        self.assertEqual(st.access_token, "ENV1")
        self.assertEqual(stat.S_IMODE(os.stat(self.path).st_mode), 0o600)
        self.assertFalse(self.store().needs_refresh(st))  # 받은 지 24시간 전
        self.clock[0] += timedelta(hours=25)
        self.assertTrue(self.store().needs_refresh(st))
        fake = FakeGraph({("GET", "refresh_access_token"): {"access_token": "NEW", "expires_in": 5184000}})
        client = InstagramClient("ENV1", host=INSTAGRAM_HOST, opener=fake)
        new = self.store().refresh(st, client)
        self.assertEqual((new.access_token, client.token), ("NEW", "NEW"))
        again = self.store().load()  # 같은 env 토큰이면 갱신본을 그대로 쓴다
        self.assertEqual(again.access_token, "NEW")
        self.assertFalse(self.store().needs_refresh(again))
        self.clock[0] += timedelta(days=8)
        self.assertTrue(self.store().needs_refresh(again))  # 마지막 갱신 뒤 7일
        self.assertEqual(self.store("ENV2").load().access_token, "ENV2")  # env 토큰을 바꾸면 새로

    def test_no_token(self):
        self.assertIsNone(TokenStore(self.path, "").load())


# ── 실행기 ──────────────────────────────────────────────────────

def fake_manifest(path: Path) -> None:
    posts = {}
    for item in load_daily_verses():
        posts[item["verse_id"]] = {
            "ko_reference": item["reference"], "ko_fp": text_fingerprint(item["text"]),
            "ref": "Psalms 1:1", "display_ref": "Psalm 1:1", "text": "Blessed is the man.",
            "kicker": "For an ordinary day", "hook": "For a plain morning.", "cta": "Save this.",
            "topic": "#hope", "note": "A short note.", "alt_text": "Bible verse card.",
            "image": f"cards/{item['verse_id']}-0123456789.jpg",
        }
    path.write_text(json.dumps({"version": 1, "posts": posts}), encoding="utf-8")


class RunTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        root = Path(self.dir.name)
        fake_manifest(root / "m.json")
        self.cfg = daily_post.Config(mode="dry-run", state_dir=root / "state", manifest=root / "m.json",
                                     token="", user_id="17841", tg_token="t", tg_chats=["1"])
        self.sent = []
        self.graph_routes = {
            ("GET", "17841"): {"id": "17841", "username": "withgod.app"},
            ("POST", "17841/media"): {"id": "C1"},
            ("GET", "C1"): {"status_code": "FINISHED"},
            ("POST", "17841/media_publish"): {"id": "M1"},
            ("GET", "M1"): {"permalink": "https://www.instagram.com/p/x/"},
        }
        self.fake = FakeGraph(self.graph_routes)
        # 2026-11-12 07:00 EST = 12:00 UTC
        self.now = datetime(2026, 11, 12, 12, 1, tzinfo=timezone.utc)
        self.deps = daily_post.Deps(
            presign=lambda b, r, k, s: f"https://s3.example/{k}?sig=1",
            probe=lambda url: (206, "image/jpeg", 120_000),
            telegram=lambda cfg, text, photos: self.sent.append((text, photos)) or True,
            client_factory=lambda cfg, token: InstagramClient(token, cfg.user_id, host=cfg.api_host,
                                                              opener=self.fake, sleep=lambda s: None),
            now=lambda: self.now,
        )

    def tearDown(self):
        self.dir.cleanup()

    def test_dry_run_sends_preview_without_publishing(self):
        out = daily_post.run(self.cfg, self.deps)
        self.assertEqual(out["status"], "dry-run")
        self.assertEqual(out["verse_id"], app_verse_for(date(2026, 11, 12)).verse_id)
        self.assertTrue(self.sent[0][1][0].startswith("https://s3.example/cards/"))
        self.assertIn("dry-run", self.sent[0][0])
        self.assertIn("토큰: 없음", self.sent[0][0])
        self.assertEqual(self.fake.calls, [])
        self.assertFalse((self.cfg.state_dir / "posted.json").exists())

    def test_dry_run_checks_token_but_does_not_post(self):
        self.cfg.token = "T"
        daily_post.run(self.cfg, self.deps)
        self.assertEqual([c[1] for c in self.fake.calls], ["17841"])
        self.assertFalse((self.cfg.state_dir / "token.json").exists())  # 시스템 사용자 토큰은 따로 저장하지 않는다
        self.assertIn("정상 @withgod.app", self.sent[0][0])

    def test_live_posts_once(self):
        self.cfg.mode, self.cfg.token = "live", "T"
        out = daily_post.run(self.cfg, self.deps)
        self.assertEqual((out["status"], out["media_id"]), ("posted", "M1"))
        rows = json.loads((self.cfg.state_dir / "posted.json").read_text())
        self.assertEqual(rows[0]["date"], "2026-11-12")
        self.assertEqual(rows[0]["permalink"], "https://www.instagram.com/p/x/")
        self.assertFalse((self.cfg.state_dir / "pending.json").exists())
        self.assertTrue(self.sent[-1][0].startswith("✅"))
        with self.assertRaises(daily_post.Skip):
            daily_post.run(self.cfg, self.deps)  # 같은 날 두 번째 실행
        create = next(c for c in self.fake.calls if c[1] == "17841/media")
        self.assertIn("#bibleverse", create[2]["caption"])

    def test_live_carousel(self):
        self.cfg.mode, self.cfg.token = "live", "T"
        manifest = json.loads(self.cfg.manifest.read_text())
        for e in manifest["posts"].values():
            e["images"] = [e["image"], e["image"].replace(".jpg", "-2.jpg"), e["image"].replace(".jpg", "-3.jpg")]
        self.cfg.manifest.write_text(json.dumps(manifest))
        n = iter(range(10))
        self.graph_routes[("POST", "17841/media")] = lambda: {"id": f"K{next(n)}"}
        for i in range(10):
            self.graph_routes[("GET", f"K{i}")] = {"status_code": "FINISHED"}
        self.graph_routes[("POST", "17841/media_publish")] = {"id": "M1"}
        out = daily_post.run(self.cfg, self.deps)
        self.assertEqual(out["status"], "posted")
        publish = next(c for c in self.fake.calls if c[1] == "17841/media_publish")
        self.assertEqual(publish[2]["creation_id"], "K3")

    def test_live_recovers_published_pending_container(self):
        self.cfg.mode, self.cfg.token = "live", "T"
        state = daily_post.State(self.cfg.state_dir)
        state.set_pending({"date": "2026-11-12", "verse_id": "x", "container": "C0"})
        self.graph_routes[("GET", "C0")] = {"status_code": "PUBLISHED"}
        out = daily_post.run(self.cfg, self.deps)
        self.assertEqual(out["media_id"], "unknown")
        self.assertFalse(any(c[1] == "17841/media" for c in self.fake.calls))

    def test_live_without_token_fails(self):
        self.cfg.mode = "live"
        with self.assertRaises(RuntimeError):
            daily_post.run(self.cfg, self.deps)

    def test_too_late_is_skipped(self):
        self.now = datetime(2026, 11, 12, 19, 30, tzinfo=timezone.utc)  # 14:30 ET
        with self.assertRaises(daily_post.Skip) as ctx:
            daily_post.run(self.cfg, self.deps)
        self.assertTrue(ctx.exception.notify)
        self.assertEqual(daily_post.run(self.cfg, self.deps, day=date(2026, 11, 12))["status"], "dry-run")

    def test_unreachable_image_fails(self):
        self.deps.probe = lambda url: (403, "application/xml", 0)
        with self.assertRaises(RuntimeError):
            daily_post.run(self.cfg, self.deps)

    def test_app_line_on_wednesday_and_sunday(self):
        self.assertEqual(daily_post.app_line_for(date(2026, 11, 11)), APP_LINE)  # 수
        self.assertEqual(daily_post.app_line_for(date(2026, 11, 15)), APP_LINE)  # 일
        self.assertEqual(daily_post.app_line_for(date(2026, 11, 12)), "")

    def test_manual_posts_are_avoided(self):
        day = date(2026, 11, 12)
        app = app_verse_for(day).verse_id
        daily_post.mark_posted(self.cfg, [app], day - timedelta(days=2))
        out = daily_post.run(self.cfg, self.deps)
        self.assertNotEqual(out["verse_id"], app)

    def test_env_config(self):
        cfg = daily_post.Config.from_env({"IG_MODE": "live", "STATE_DIRECTORY": "/var/lib/with-god-ig",
                                          "TG_CHAT_IDS": "1, 2", "IG_LATE_LIMIT_HOURS": "3"})
        self.assertEqual((cfg.mode, cfg.tg_chats, cfg.late_limit), ("live", ["1", "2"], timedelta(hours=3)))
        self.assertEqual(cfg.api_host, "https://graph.facebook.com")
        with self.assertRaises(ValueError):
            daily_post.Config.from_env({"IG_MODE": "yes"})


@unittest.skipUnless(MANIFEST.exists(), "매니페스트 없음(scripts/build_ig_daily_posts.py)")
class ManifestDataTest(unittest.TestCase):
    """레포의 매니페스트가 지금 목록·풀이·영어 변환과 맞는지. 목록이나 풀이를 고치면 여기서 걸린다
    → scripts/build_ig_daily_posts.py --upload 로 다시 만든다."""

    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        cls.items = load_daily_verses()

    def test_covers_every_daily_verse_with_current_text(self):
        posts = self.manifest["posts"]
        self.assertEqual(set(posts), {i["verse_id"] for i in self.items})
        stale = [i["verse_id"] for i in self.items if posts[i["verse_id"]]["ko_fp"] != text_fingerprint(i["text"])]
        self.assertEqual(stale, [])

    def test_notes_match_reviewed_interpretations(self):
        from instagram.posts import en_note

        drift = [i["verse_id"] for i in self.items
                 if self.manifest["posts"][i["verse_id"]]["note"] != en_note(i["verse_id"], i["text"])]
        self.assertEqual(drift, [])

    def test_texts_match_app_localization(self):
        from instagram.posts import localize_all

        en = localize_all(self.items)
        wrong = [(vid, e["text"][:30]) for vid, e in self.manifest["posts"].items()
                 if e["text"] != card_text(en[vid]["text"]) or e["ref"] != en[vid]["ref"]]
        self.assertEqual(wrong, [])

    def test_copy_and_captions_pass_rules(self):
        bad = {vid: p for vid, e in self.manifest["posts"].items() if (p := find_post_problems(e))}
        self.assertEqual(bad, {})

    def test_unique_images(self):
        keys = [e["image"] for e in self.manifest["posts"].values()]
        self.assertEqual(len(keys), len(set(keys)))
