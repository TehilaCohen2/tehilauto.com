import datetime as dt
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

import config
import content
import mailer
import store as st
import tasks
from topics_bank import BANK, SEED


class FakeWS:
    def __init__(self, headers):
        self.vals = [list(headers)]

    def get_all_values(self):
        return [list(r) for r in self.vals]

    def update_cell(self, r, c, v):
        row = self.vals[r - 1]
        row += [""] * (c - len(row))
        row[c - 1] = str(v)

    def append_row(self, row, value_input_option=None):
        self.vals.append([str(x) for x in row])


@pytest.fixture
def env(monkeypatch):
    s = st.Store(tabs={n: FakeWS(h) for n, h in st.TABS.items()})
    tasks.seed(s)
    sent = []
    monkeypatch.setattr(mailer, "send_mail",
                        lambda subj, body, to=None: sent.append((subj, body)) or f"<id{len(sent)}@x>")
    return s, sent


def test_seed_and_bank_unique():
    names = [t[0] for t in SEED + BANK]
    assert len(names) == len(set(names))


def test_post_max_5_lines():
    for t in SEED + BANK:
        assert len(content.write_post(*t, seed=3).splitlines()) <= 5


def test_task2_marks_used_and_never_deletes(env):
    s, sent = env
    n = len(s.posts())
    tasks.task2_post(s)
    assert sent[0][0].startswith("פוסט WhatsApp ליום רביעי - ")
    used = [p for p in s.posts() if s.is_used(p)]
    assert len(used) == 1 and used[0]["תאריך שימוש"] == config.today()
    assert len(s.posts()) == n
    tasks.task2_post(s)  # אותו יום: לא שולח שוב
    assert len(sent) == 1


def test_task1_prompt_and_rotation(env):
    s, sent = env
    for i, d in enumerate(["2026-01-05", "", "2026-01-01", "2026-02-01", "2026-03-01", "2026-04-01"]):
        s.t[st.STYLES].set(i + 2, "בשימוש_אחרון (תאריך)", d)
    tasks.task1_prompt(s)
    subj, body = sent[0]
    assert subj.startswith("פרומפט סרטון ליום ראשון - ")
    assert body.startswith("צור סרטון לפי סקיל social-video-nadav")
    assert "מילות סגנון: שרטוט טכני" in body and "לשאול על נדב לפני התחלה" in body
    assert [x["בשימוש_אחרון (תאריך)"] for x in s.styles()][1] == config.today()
    video_post = next(p for p in s.posts() if p["תאריך סרטון"])
    assert not s.is_used(video_post)
    tasks.task2_post(s)  # לא חוזר על נושא הסרטון
    assert next(p for p in s.posts() if s.is_used(p))["ID"] != video_post["ID"]


def test_task3_and_approval(env, monkeypatch):
    s, sent = env
    tasks.task3_propose(s)
    subj, body = sent[0]
    assert subj == "נושאים חדשים לאישור - רשימת תפוצה WhatsApp"
    assert "APPROVE 1,3,5" in body and body.count("קטגוריה:") == 5
    before = len(s.posts())
    monkeypatch.setattr(mailer, "fetch_replies",
                        lambda since, mid: [("<r1>", "APPROVE 1,3,5\n\n> APPROVE 2")])
    tasks.check_approvals(s)
    assert len(s.posts()) == before + 3
    assert s.get_state("pending_batch") == ""
    tasks.check_approvals(s)  # לא מוסיף שוב
    assert len(s.posts()) == before + 3


def test_proposals_exclude_existing_and_cover_categories(env):
    picks = content.pick_proposals([t[0] for t in SEED], 0)
    assert len(picks) == 5 and len({p[2] for p in picks}) == 3


def test_parse_approval():
    assert mailer.parse_approval("APPROVE 1,3,5") == [1, 3, 5]
    assert mailer.parse_approval("approve: 2, 4\nתודה") == [2, 4]
    assert mailer.parse_approval("אוקיי\n> APPROVE 1") is None
    assert mailer.parse_approval("השב APPROVE + מספרים") is None
