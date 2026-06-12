"""Тесты вспомогательной логики installer (без запуска DESIGNER)."""

import os

import pytest

from mcp_baf import installer


@pytest.mark.parametrize(
    ("source", "want"),
    [
        (r"C:\Program Files\BAF\8.3.18.1627\bin\1cv8.exe", (3, 18)),
        (r"C:\Program Files\1cv8\8.3.27.1859\bin\1cv8.exe", (3, 27)),
        ("/opt/1cv8/x86_64/8.3.22.1709/1cv8", (3, 22)),
        ("/Applications/1cv8.localized/8.3.25.1000/1cv8.app/Contents/MacOS/1cv8", (3, 25)),
        ("8.5.1.100", (5, 1)),
        ("no version here", (0, 0)),
    ],
)
def test_extract_platform_minor(source, want):
    assert installer.extract_platform_minor(source) == want


def test_platform_patterns_baf_first(monkeypatch):
    monkeypatch.setattr(installer.sys, "platform", "win32")
    patterns = installer._platform_patterns()
    assert patterns[0] == r"C:\Program Files\BAF\8.*\bin\1cv8.exe"
    assert patterns[1] == r"C:\Program Files (x86)\BAF\8.*\bin\1cv8.exe"


def test_parse_platform_version_override_priority():
    assert installer.parse_platform_version(
        r"C:\1cv8\8.3.27\bin\1cv8.exe", "8.3.13"
    ) == (3, 13)


@pytest.mark.parametrize(
    ("path", "want"),
    [
        (r"C:\Program Files\BAF\8.3.18.1627\bin\1cv8.exe", "2.11"),
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


def test_classify_designer_error_compat_mode_ukrainian():
    # Украинская локализация платформы пишет ошибки на украинском.
    err = installer.classify_designer_error(
        "1C DESIGNER failed (exit code 1):\n"
        "Розширення конфігурації з вказаним ім'ям не знайдено!"
    )
    assert "режим совместимости конфигурации запрещает расширения" in str(err)


def test_classify_designer_error_passthrough():
    err = installer.classify_designer_error("какая-то другая ошибка")
    assert str(err) == "какая-то другая ошибка"


def _copy_extension_sources(tmp_path):
    import shutil

    dst = tmp_path / "ext"
    shutil.copytree(installer.EXTENSION_SRC, dst)
    return dst


def test_localize_extension_ua(tmp_path):
    ext_dir = _copy_extension_sources(tmp_path)
    installer.localize_extension(str(ext_dir), "ua")

    service = (ext_dir / "HTTPServices" / "MCPService.xml").read_text(
        encoding="utf-8-sig"
    )
    # Код языка синонимов сменён на украинский.
    assert "<v8:lang>ru</v8:lang>" not in service
    assert "<v8:lang>uk</v8:lang>" in service
    # Тексты синонимов переведены.
    assert "<v8:content>Метадані</v8:content>" in service
    assert "<v8:content>Перевірка запиту</v8:content>" in service
    assert "<v8:content>Метаданные</v8:content>" not in service
    # Имена объектов и обработчики не тронуты — они привязаны к Module.bsl.
    assert "<Name>Метаданные</Name>" in service

    cfg = (ext_dir / "Configuration.xml").read_text(encoding="utf-8-sig")
    assert "<v8:lang>uk</v8:lang>" in cfg
    assert "<v8:content>MCP HTTPService</v8:content>" in cfg


def test_localize_extension_ru_is_noop(tmp_path):
    ext_dir = _copy_extension_sources(tmp_path)
    before = (ext_dir / "HTTPServices" / "MCPService.xml").read_bytes()
    installer.localize_extension(str(ext_dir), "ru")
    after = (ext_dir / "HTTPServices" / "MCPService.xml").read_bytes()
    assert before == after


def test_localize_extension_keeps_bom(tmp_path):
    # Локализация не должна терять UTF-8 BOM там, где он был в исходнике.
    ext_dir = _copy_extension_sources(tmp_path)
    bom_before = {}
    for root, _dirs, files in os.walk(ext_dir):
        for name in files:
            if name.lower().endswith(".xml"):
                path = os.path.join(root, name)
                with open(path, "rb") as f:
                    bom_before[path] = f.read(3) == b"\xef\xbb\xbf"

    installer.localize_extension(str(ext_dir), "ua")

    for path, had_bom in bom_before.items():
        with open(path, "rb") as f:
            assert (f.read(3) == b"\xef\xbb\xbf") == had_bom, path


def test_translations_cover_all_cyrillic_synonyms():
    # Каждый русский (кириллический) текст синонима в исходниках должен
    # иметь перевод, иначе после --lang ua останется русский текст с
    # украинским кодом языка.
    import re

    for root, _dirs, files in os.walk(installer.EXTENSION_SRC):
        for name in files:
            if not name.lower().endswith(".xml"):
                continue
            content = open(
                os.path.join(root, name), encoding="utf-8-sig"
            ).read()
            for text in re.findall(r"<v8:content>([^<]+)</v8:content>", content):
                if re.search(r"[а-яёА-ЯЁ]", text):
                    assert text in installer._SYNONYM_TRANSLATIONS_UA, (
                        f"{name}: no Ukrainian translation for {text!r}"
                    )


def test_install_rejects_unknown_lang():
    with pytest.raises(installer.InstallError, match="unsupported --lang"):
        installer.install("C:\\db", lang="en")


def test_lang_default_and_choices():
    from mcp_baf import config

    assert config.parse_args([]).lang == "ua"
    assert config.parse_args(["--lang", "ru"]).lang == "ru"
    with pytest.raises(SystemExit):
        config.parse_args(["--lang", "en"])


def test_extension_sources_present():
    # XML-исходники расширения должны попадать в пакет.
    expected = [
        "Configuration.xml",
        "ConfigDumpInfo.xml",
        os.path.join("HTTPServices", "MCPService.xml"),
        os.path.join("HTTPServices", "MCPService", "Ext", "Module.bsl"),
        os.path.join("Roles", "MCP_ОсновнаяРоль.xml"),
        os.path.join("Roles", "MCP_ОсновнаяРоль", "Ext", "Rights.xml"),
    ]
    for rel in expected:
        assert os.path.isfile(os.path.join(installer.EXTENSION_SRC, rel)), rel


def test_no_default_language():
    # DefaultLanguage (ОсновнойЯзык) — контролируемое свойство: оно должно
    # совпадать с основным языком базы, который заранее неизвестен (BAF —
    # украинский, другие базы — русский). Поэтому свойство и заимствованный
    # объект языка из расширения исключены — значение наследуется от базы.
    cfg = open(
        os.path.join(installer.EXTENSION_SRC, "Configuration.xml"),
        encoding="utf-8-sig",
    ).read()
    assert "<DefaultLanguage>" not in cfg
    assert "<Language>" not in cfg
    dump_info = open(
        os.path.join(installer.EXTENSION_SRC, "ConfigDumpInfo.xml"),
        encoding="utf-8-sig",
    ).read()
    assert "Language.Русский" not in dump_info
