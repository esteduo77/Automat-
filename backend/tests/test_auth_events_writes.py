import pytest
from backend.app.services.workflow_engine import block_kind

@pytest.mark.parametrize(("category", "label", "expected"), [
    ("Déclencheurs", "Déclencheur webhook", "trigger.webhook"),
    ("Google", "Envoyer un e-mail", "google.gmail.send"),
    ("Google", "Créer un fichier", "google.drive.create"),
    ("Google", "Modifier un fichier", "google.drive.update"),
    ("Microsoft", "Envoyer un e-mail", "microsoft.mail.send"),
    ("Microsoft", "Créer un fichier", "microsoft.drive.create"),
    ("Microsoft", "Modifier un fichier", "microsoft.drive.update"),
])
def test_new_event_and_write_block_mapping(category, label, expected):
    assert block_kind({"category": category, "label": label}) == expected
