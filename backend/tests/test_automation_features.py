from backend.app.services.workflow_engine import block_kind
from backend.app.routers.automations import ScheduleCreate
import pytest

@pytest.mark.parametrize(("category", "label", "expected"), [
    ("Google", "Rechercher un e-mail", "google.gmail.search"),
    ("Google", "Rechercher un fichier", "google.drive.search"),
    ("Microsoft", "Rechercher un message", "microsoft.mail.search"),
    ("Microsoft", "Rechercher un fichier", "microsoft.drive.search"),
    ("Déclencheurs", "Déclencheur planifié", "trigger.schedule"),
])
def test_provider_and_schedule_block_mapping(category, label, expected):
    assert block_kind({"category": category, "label": label}) == expected

def test_schedule_interval_is_bounded():
    assert ScheduleCreate(interval_seconds=60).interval_seconds == 60
    assert ScheduleCreate(interval_seconds=300).interval_seconds == 300
    with pytest.raises(Exception):
        ScheduleCreate(interval_seconds=30)
    with pytest.raises(Exception):
        ScheduleCreate(interval_seconds=31_536_001)
