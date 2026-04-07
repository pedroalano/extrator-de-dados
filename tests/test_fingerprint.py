from pathlib import Path

from app.utils.xml_fingerprint import compute_structure_hash


def test_structure_hash_stable(minimal_nfe_xml: bytes):
    h1 = compute_structure_hash(minimal_nfe_xml)
    h2 = compute_structure_hash(minimal_nfe_xml)
    assert h1 == h2
    assert len(h1) == 64


def test_structure_hash_changes_when_version_changes(minimal_nfe_xml: bytes):
    text = minimal_nfe_xml.decode("utf-8").replace('versao="4.00"', 'versao="3.10"', 1)
    h1 = compute_structure_hash(minimal_nfe_xml)
    h2 = compute_structure_hash(text.encode("utf-8"))
    assert h1 != h2


def test_structure_hash_fixture_file(fixture_dir: Path):
    data = (fixture_dir / "minimal_nfe.xml").read_bytes()
    assert compute_structure_hash(data)
