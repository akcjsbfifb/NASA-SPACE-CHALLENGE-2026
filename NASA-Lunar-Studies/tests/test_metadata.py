import pytest

from lunar_data.export import sha256_file
from lunar_data.metadata import MetadataError, load_metadata


def test_lbl_txt_resolution_keeps_originals_untouched(pds_product):
    xml, label, image = pds_product
    before = {p: sha256_file(p) for p in pds_product}
    meta = load_metadata(xml)
    assert meta.label_path == label
    assert meta.image_path == image
    assert meta.rows == 2880 and meta.columns == 5760
    assert meta.pixels_per_degree == 16
    assert "pds3_label_resolved_as_lbl_txt" in meta.warnings
    assert before == {p: sha256_file(p) for p in pds_product}
    assert not label.with_suffix("").exists()


@pytest.mark.parametrize("old,new", [
    ("PC_REAL", "IEEE_REAL"), ("SAMPLE_BITS = 32", "SAMPLE_BITS = 16"),
    ("UNIT = KILOMETER", "UNIT = METER"),
    ("CENTER_LONGITUDE = 180", "CENTER_LONGITUDE = 0"),
    ("LINE_PROJECTION_OFFSET = 1439.5", "LINE_PROJECTION_OFFSET = 1440"),
    ("SCALING_FACTOR = 1", "SCALING_FACTOR = 2"),
    ("LDEM_16_FLOAT.IMG", "OTHER.IMG"),
])
def test_rejects_conflicting_pds3(pds_product, old, new):
    xml, label, _ = pds_product
    label.write_text(label.read_text().replace(old, new), encoding="utf-8")
    with pytest.raises(MetadataError):
        load_metadata(xml)


@pytest.mark.parametrize("old,new", [
    ("Planetocentric", "Planetographic"), ("Equirectangular", "Polar Stereographic"),
    ("IEEE754LSBSingle", "IEEE754MSBSingle"), ("Top to Bottom", "Bottom to Top"),
    ('unit="km/pixel"', 'unit="m/pixel"'),
    ("ldem_16_float.img", "../other.img"),
    ('unit="byte">0', 'unit="byte">4'),
])
def test_rejects_unsupported_pds4(pds_product, old, new):
    xml, _, _ = pds_product
    xml.write_text(xml.read_text().replace(old, new), encoding="utf-8")
    with pytest.raises(MetadataError):
        load_metadata(xml)


def test_truncated_raster_rejected(pds_product):
    xml, _, image = pds_product
    with image.open("r+b") as stream:
        stream.truncate(8)
    with pytest.raises(MetadataError, match="tamaño IMG"):
        load_metadata(xml)


def test_xml_special_constant_parsed(pds_product):
    xml, _, _ = pds_product
    xml.write_text(xml.read_text().replace(
        "</Array_2D_Image>",
        "<Special_Constants><missing_constant>-9999</missing_constant></Special_Constants></Array_2D_Image>",
    ), encoding="utf-8")
    assert load_metadata(xml).special_constants == (-9999,)


@pytest.mark.local_data
@pytest.mark.parametrize("subdir,product,unit", [
    ("ldem", "ldem_16_float", "KILOMETER"), ("ldrm", "ldrm_32_50_float", "METER"),
])
def test_local_metadata(module_root, subdir, product, unit):
    path = module_root / "data/raw/lola" / subdir / f"{product}.xml"
    if not path.exists():
        pytest.skip("Datos locales no distribuidos con el código")
    meta = load_metadata(path)
    assert meta.raw_unit == unit
    if subdir == "ldrm":
        assert "ldrm_unit_text_conflict_resolved_as_meters" in meta.warnings
