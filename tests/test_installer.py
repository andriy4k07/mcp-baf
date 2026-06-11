"""Тесты вспомогательной логики installer (без запуска DESIGNER)."""

import os

import pytest

from mcp_baf import installer


@pytest.mark.parametrize(
    ("source", "want"),
    [
        (r"C:\Program Files\1cv8\8.3.27.1859\bin\1cv8.exe", (3, 27)),
        ("/opt/1cv8/x86_64/8.3.22.1709/1cv8", (3, 22)),
        ("/Applications/1cv8.localized/8.3.25.1000/1cv8.app/Contents/MacOS/1cv8", (3, 25)),
        ("8.5.1.100", (5, 1)),
        ("no version here", (0, 0)),
    ],
)
def test_extract_platform_minor(source, want):
    assert installer.extract_platform_minor(source) == want


def test_parse_platform_version_override_priority():
    assert installer.parse_platform_version(
        r"C:\1cv8\8.3.27\bin\1cv8.exe", "8.3.13"
    ) == (3, 13)


@pytest.mark.parametrize(
    ("path", "want"),
    [
        (r"C:\Program Files\1cv8\8.3.27.1859\bin\1cv8.exe", "2.20"),
        (r"C:\Program Files\1cv8\8.3.25.1394\bin\1cv8.exe", "2.18"),
        (r"C:\Program Files\1cv8\8.3.14.100\bin\1cv8.exe", "2.8"),
        (r"C:\Program Files\1cv8\8.3.13.100\bin\1cv8.exe", "2.7"),
        ("8.5.1.100", "2.21"),
        ("unknown", "2.7"),
    ],
)
def test_format_version_for_platform(path, want):
    assert installer.format_version_for_platform(path) == want


def test_patch_format_version(tmp_path):
    xml = tmp_path / "Configuration.xml"
    xml.write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<MetaDataObject xmlns="http://v8.1c.ru/8.3/MDClasses" version="2.18">\n'
        "</MetaDataObject>\n",
        encoding="utf-8",
    )
    installer.patch_format_version(str(tmp_path), "2.8")
    content = xml.read_text(encoding="utf-8")
    assert 'version="2.8"' in content
    # XML-декларация не тронута.
    assert '<?xml version="1.0"' in content


def test_patch_extension_xml_replace_and_insert(tmp_path):
    cfg = tmp_path / "Configuration.xml"
    cfg.write_text(
        "<Configuration>\n"
        "\t\t<Properties>\n"
        "\t\t\t<ConfigurationExtensionCompatibilityMode>Version8_3_24"
        "</ConfigurationExtensionCompatibilityMode>\n"
        "\t\t</Properties>\n"
        "</Configuration>\n",
        encoding="utf-8",
    )
    installer.patch_extension_xml(str(cfg), "Version8_3_10", "")
    content = cfg.read_text(encoding="utf-8")
    assert (
        "<ConfigurationExtensionCompatibilityMode>Version8_3_10"
        "</ConfigurationExtensionCompatibilityMode>"
    ) in content

    # Отсутствующий тег вставляется перед </Properties>.
    installer.patch_extension_xml(str(cfg), "", "Version8_2")
    content = cfg.read_text(encoding="utf-8")
    assert "<InterfaceCompatibilityMode>Version8_2</InterfaceCompatibilityMode>" in content
    assert content.index("InterfaceCompatibilityMode") < content.index("</Properties>")


def test_strip_inherited_properties(tmp_path):
    cfg = tmp_path / "Configuration.xml"
    cfg.write_text(
        "<Properties>\n"
        "<DefaultRunMode>ManagedApplication</DefaultRunMode>\n"
        "<Vendor>Тест</Vendor>\n"
        "<Synonym>Остаётся</Synonym>\n"
        "<DefaultRoles>\n<xr:Item>Роль</xr:Item>\n</DefaultRoles>\n"
        "</Properties>\n",
        encoding="utf-8",
    )
    installer.strip_inherited_properties(str(cfg))
    content = cfg.read_text(encoding="utf-8")
    assert "DefaultRunMode" not in content
    assert "Vendor" not in content
    assert "DefaultRoles" not in content
    assert "<Synonym>Остаётся</Synonym>" in content


def test_strip_unsupported_elements(tmp_path):
    cfg = tmp_path / "Configuration.xml"
    cfg.write_text(
        "<Configuration>\n"
        "<KeepMappingToExtendedConfigurationObjectsByIDs>true"
        "</KeepMappingToExtendedConfigurationObjectsByIDs>\n"
        "<InternalInfo>\n"
        "<xr:ContainedObject>\n"
        "<xr:ClassId>fb282519-d103-4dd3-bc12-cb271d631dfc</xr:ClassId>\n"
        "<xr:ObjectId>some-id</xr:ObjectId>\n"
        "</xr:ContainedObject>\n"
        "<xr:ContainedObject>\n"
        "<xr:ClassId>другой-класс</xr:ClassId>\n"
        "<xr:ObjectId>id2</xr:ObjectId>\n"
        "</xr:ContainedObject>\n"
        "</InternalInfo>\n"
        "</Configuration>\n",
        encoding="utf-8",
    )
    other = tmp_path / "Roles" / "Роль.xml"
    other.parent.mkdir()
    other.write_text(
        "<Role>\n<InternalInfo>\n<данные/>\n</InternalInfo>\n<Имя>Роль</Имя>\n</Role>\n",
        encoding="utf-8",
    )

    installer.strip_unsupported_elements(str(tmp_path))

    cfg_content = cfg.read_text(encoding="utf-8")
    # Configuration.xml: KeepMapping и Role-ContainedObject удалены,
    # сам InternalInfo с остальным содержимым остаётся (там UUID расширения).
    assert "KeepMappingToExtendedConfigurationObjectsByIDs" not in cfg_content
    assert "fb282519" not in cfg_content
    assert "<InternalInfo>" in cfg_content
    assert "другой-класс" in cfg_content

    # В остальных файлах InternalInfo вырезается целиком.
    other_content = other.read_text(encoding="utf-8")
    assert "InternalInfo" not in other_content
    assert "<Имя>Роль</Имя>" in other_content


def test_classify_designer_error_compat_mode():
    err = installer.classify_designer_error(
        "1C DESIGNER failed (exit code 1):\n"
        "Расширение конфигурации с указанным именем не найдено!"
    )
    assert "режим совместимости конфигурации запрещает расширения" in str(err)
    assert "Оригинальная ошибка DESIGNER" in str(err)


def test_classify_designer_error_passthrough():
    err = installer.classify_designer_error("какая-то другая ошибка")
    assert str(err) == "какая-то другая ошибка"


def test_extension_sources_present():
    # XML-исходники расширения должны попадать в пакет.
    expected = [
        "Configuration.xml",
        "ConfigDumpInfo.xml",
        os.path.join("HTTPServices", "MCPService.xml"),
        os.path.join("HTTPServices", "MCPService", "Ext", "Module.bsl"),
        os.path.join("Roles", "MCP_ОсновнаяРоль.xml"),
        os.path.join("Roles", "MCP_ОсновнаяРоль", "Ext", "Rights.xml"),
        os.path.join("Languages", "Русский.xml"),
    ]
    for rel in expected:
        assert os.path.isfile(os.path.join(installer.EXTENSION_SRC, rel)), rel
