import json
import tempfile
import unittest
from pathlib import Path
import sys


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from jianying_project import JianyingProject, assemble_keep_blocks, validate_content


def content(timeline_id="T1"):
    return {
        "id": timeline_id,
        "duration": 10_000_000,
        "materials": {"videos": [{"id": "M1"}]},
        "tracks": [{
            "id": "V1", "type": "video", "segments": [{
                "id": "S1", "material_id": "M1",
                "target_timerange": {"duration": 10_000_000},
                "source_timerange": {"start": 20_000_000, "duration": 10_000_000},
            }]
        }],
    }


class RuntimeTests(unittest.TestCase):
    def test_probe_plaintext_multi_timeline(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "Timelines" / "T1").mkdir(parents=True)
            (root / "Timelines" / "project.json").write_text(json.dumps({
                "main_timeline_id": "T1", "timelines": [{"id": "T1", "name": "one"}]
            }), encoding="utf-8")
            (root / "timeline_layout.json").write_text(json.dumps({"activeTimeline": "T1"}), encoding="utf-8")
            raw = json.dumps(content()).encode()
            (root / "draft_content.json").write_bytes(raw)
            (root / "Timelines" / "T1" / "draft_content.json").write_bytes(raw)
            project = JianyingProject(root)
            result = project.probe()
            self.assertEqual(result["layout"], "hybrid")
            self.assertEqual(result["active_timeline_id"], "T1")
            self.assertEqual(result["timelines"][0]["encoding"], "plaintext")

    def test_root_main_is_not_assumed_to_be_active_replica(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for timeline_id in ("T1", "T2"):
                (root / "Timelines" / timeline_id).mkdir(parents=True)
                (root / "Timelines" / timeline_id / "draft_content.json").write_text(
                    json.dumps(content(timeline_id)), encoding="utf-8"
                )
            (root / "Timelines" / "project.json").write_text(json.dumps({
                "main_timeline_id": "T1",
                "timelines": [{"id": "T1", "name": "main"}, {"id": "T2", "name": "active"}],
            }), encoding="utf-8")
            (root / "timeline_layout.json").write_text(json.dumps({"activeTimeline": "T2"}), encoding="utf-8")
            (root / "draft_content.json").write_text(json.dumps(content("T1")), encoding="utf-8")
            project = JianyingProject(root)
            self.assertEqual(project.active_timeline_id(), "T2")
            self.assertNotIn(root / "draft_content.json", project.replica_paths("T2"))

    def test_apply_plan_writes_and_reads_back_plaintext_replicas(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "Timelines" / "T1").mkdir(parents=True)
            (root / "Timelines" / "project.json").write_text(json.dumps({
                "main_timeline_id": "T1", "timelines": [{"id": "T1", "name": "one"}]
            }), encoding="utf-8")
            (root / "timeline_layout.json").write_text(json.dumps({"activeTimeline": "T1"}), encoding="utf-8")
            raw = json.dumps(content()).encode()
            (root / "draft_content.json").write_bytes(raw)
            (root / "Timelines" / "T1" / "draft_content.json").write_bytes(raw)
            project = JianyingProject(root)
            project._assert_editor_closed = lambda: None
            result = project.apply_plan("T1", {
                "version": 1, "ripple": "all",
                "keep_blocks": [{"start_us": 0, "end_us": 5_000_000}],
            })
            self.assertTrue(result["ok"])
            self.assertEqual(project.decode(root / "draft_content.json").value["duration"], 5_000_000)
            self.assertTrue(Path(result["backup"]).is_dir())

    def test_keep_blocks_split_and_reorder(self):
        value = assemble_keep_blocks(content(), [(5_000_000, 10_000_000), (0, 2_000_000)], "all", [])
        segments = value["tracks"][0]["segments"]
        self.assertEqual(value["duration"], 7_000_000)
        self.assertEqual(segments[0]["source_timerange"]["start"], 25_000_000)
        self.assertEqual(segments[1]["target_timerange"]["start"], 5_000_000)
        self.assertTrue(validate_content(value, "T1")["ok"])

    def test_replica_manifest_reports_observed_roles_without_fixed_count(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            timeline = root / "Timelines" / "T1"
            timeline.mkdir(parents=True)
            (root / "Timelines" / "project.json").write_text(json.dumps({
                "timelines": [{"id": "T1", "name": "one"}],
            }), encoding="utf-8")
            raw = json.dumps(content()).encode()
            for name in ("draft_content.json", ".bak", "template-2.tmp"):
                (timeline / name).write_bytes(raw)
            project = JianyingProject(root)
            manifest = project.replica_manifest("T1", include_root_mirror=False)
            self.assertEqual(manifest["count"], 3)
            self.assertEqual(
                {item["role"] for item in manifest["replicas"]},
                {"primary", "writable-backup", "writable-template"},
            )
            self.assertEqual(manifest["errors"], [])

    def test_locate_uses_tolerance_for_rounded_subtitle_start(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            timeline = root / "Timelines" / "T1"
            timeline.mkdir(parents=True)
            (root / "Timelines" / "project.json").write_text(json.dumps({
                "timelines": [{"id": "T1", "name": "one"}],
            }), encoding="utf-8")
            value = content()
            value["materials"] = {"texts": [{"id": "TXT1", "content": "重点句"}]}
            value["tracks"] = [{
                "id": "TEXT1", "type": "text", "segments": [{
                    "id": "SUB1", "material_id": "TXT1",
                    "target_timerange": {"start": 766_667, "duration": 1_000_000},
                }],
            }]
            raw = json.dumps(value).encode()
            (timeline / "draft_content.json").write_bytes(raw)
            project = JianyingProject(root)
            result = project.locate(
                "T1", track_type="text", start_us=767_000, text="重点句"
            )
            self.assertEqual(result["match_count"], 1)
            self.assertEqual(result["matches"][0]["segment_id"], "SUB1")
            self.assertEqual(result["matches"][0]["start_delta_us"], -333)

    def test_resolve_locator_requires_one_match(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            timeline = root / "Timelines" / "T1"
            timeline.mkdir(parents=True)
            (root / "Timelines" / "project.json").write_text(json.dumps({
                "timelines": [{"id": "T1", "name": "one"}],
            }), encoding="utf-8")
            value = content()
            value["tracks"] = [{
                "id": "TEXT1", "type": "text", "segments": [{
                    "id": "SUB1", "target_timerange": {"start": 766_667, "duration": 1_000_000},
                }],
            }]
            (timeline / "draft_content.json").write_text(json.dumps(value), encoding="utf-8")
            project = JianyingProject(root)
            match = project.resolve_locator("T1", {
                "track_id": "TEXT1", "segment_id": "SUB1", "start_us": 767_000,
            })
            self.assertEqual(match["segment_id"], "SUB1")

    def test_apply_plan_dry_run_does_not_write(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "Timelines" / "T1").mkdir(parents=True)
            (root / "Timelines" / "project.json").write_text(json.dumps({
                "main_timeline_id": "T1", "timelines": [{"id": "T1", "name": "one"}]
            }), encoding="utf-8")
            raw = json.dumps(content()).encode()
            path = root / "Timelines" / "T1" / "draft_content.json"
            path.write_bytes(raw)
            project = JianyingProject(root)
            result = project.apply_plan("T1", {
                "version": 1, "ripple": "all",
                "keep_blocks": [{"start_us": 0, "end_us": 5_000_000}],
            }, dry_run=True)
            self.assertTrue(result["dry_run"])
            self.assertEqual(path.read_bytes(), raw)

    def test_validation_compares_semantic_timeranges_not_raw_zero_shape(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            timeline = root / "Timelines" / "T1"
            timeline.mkdir(parents=True)
            (root / "Timelines" / "project.json").write_text(json.dumps({
                "timelines": [{"id": "T1", "name": "one"}],
            }), encoding="utf-8")
            primary = content()
            replica = content()
            replica["tracks"][0]["segments"][0]["target_timerange"]["start"] = 0
            (timeline / "draft_content.json").write_text(json.dumps(primary), encoding="utf-8")
            (timeline / ".bak").write_text(json.dumps(replica), encoding="utf-8")
            result = JianyingProject(root).validate("T1")
            self.assertTrue(result["ok"], result)


class MediaStageTests(unittest.TestCase):
    def test_stage_copies_external_file_into_draft(self):
        from media_stage import is_inside_draft, stage_local_asset

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            draft = root / "draft"
            draft.mkdir()
            external = root / "clip.mp4"
            external.write_bytes(b"fake-video")
            staged = stage_local_asset(draft, external)
            self.assertTrue(staged.is_file())
            self.assertTrue(is_inside_draft(draft, staged))
            self.assertEqual(staged.read_bytes(), b"fake-video")
            self.assertEqual(staged.parent.name, "materials")

    def test_stage_skips_when_already_inside_draft(self):
        from media_stage import stage_local_asset

        with tempfile.TemporaryDirectory() as directory:
            draft = Path(directory)
            media = draft / "materials" / "a.mp4"
            media.parent.mkdir()
            media.write_bytes(b"inside")
            staged = stage_local_asset(draft, media)
            self.assertEqual(staged, media.resolve())

    def test_stage_missing_source_raises(self):
        from media_stage import stage_local_asset

        with tempfile.TemporaryDirectory() as directory:
            draft = Path(directory)
            with self.assertRaises(FileNotFoundError):
                stage_local_asset(draft, draft / "nope.mp4")

    def test_stage_rejects_escaping_subdir(self):
        from media_stage import MediaStageError, stage_local_asset

        with tempfile.TemporaryDirectory() as directory:
            draft = Path(directory) / "draft"
            draft.mkdir()
            external = Path(directory) / "x.mp4"
            external.write_bytes(b"x")
            with self.assertRaises(MediaStageError):
                stage_local_asset(draft, external, subdir="../escape")

    def test_prepare_media_without_normalize_stages_source(self):
        from media_stage import prepare_media_for_draft

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            draft = root / "draft"
            draft.mkdir()
            external = root / "b.wav"
            external.write_bytes(b"RIFF")
            report = prepare_media_for_draft(draft, external, normalize=False)
            self.assertTrue(report["ok"] if "ok" in report else report["inside_draft"])
            self.assertTrue(Path(report["staged_path"]).is_file())
            self.assertFalse(report["normalized"])
            self.assertEqual(report["note"], "normalize_disabled")

    def test_cli_stage_media_entry(self):
        from jianying_project import main

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            draft = root / "draft"
            draft.mkdir()
            external = root / "c.bin"
            external.write_bytes(b"data")
            code = main([
                "stage-media", str(draft), "--media", str(external), "--no-normalize",
            ])
            self.assertEqual(code, 0)
            self.assertTrue(any((draft / "materials").iterdir()))


if __name__ == "__main__":
    unittest.main()
