from workshop_verify_agents.demo_generate_artefacts import generate_all_artefacts
from workshop_verify_agents.examples.conversations import list_scenarios


def test_generator_writes_every_registered_scenario(tmp_path, capsys) -> None:
    generate_all_artefacts(tmp_path)

    scenarios = list_scenarios()
    generated = [
        name for name in scenarios
        if (tmp_path / name / "manifest.json").is_file()
    ]
    assert generated == scenarios
    assert "Done. 15 scenarios written." in capsys.readouterr().out
