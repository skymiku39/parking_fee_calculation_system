"""Integration tests: Pub/Sub subscribers refresh runtime state."""


def test_calendar_persisted_event_reloads_calculator(isolated_system):
    system = isolated_system
    original = system.multidimensional_calculator
    assert original is not None

    cal = system.load_calendar()
    cal["description"] = "pubsub-test-marker"
    system.save_calendar(cal, source="test")

    assert system.multidimensional_calculator is not None
    assert system.holiday_calendar is not None
    # 日曆儲存事件同時觸發 MDP 重載，計算器應被重新建立
    assert system.multidimensional_calculator is not original


def test_mdp_saved_event_reloads_calculator(isolated_system):
    system = isolated_system
    original = system.multidimensional_calculator
    assert original is not None

    cfg = system.load_mdp_config()
    system.save_mdp_config(cfg, template_id="全天_無假日", action="save")

    assert system.multidimensional_calculator is not None
    assert system.multidimensional_calculator is not original


def test_system_config_mode_change_reloads_calculator(isolated_system):
    system = isolated_system
    original = system.multidimensional_calculator
    assert original is not None

    system.update_system_config({"system_mode": "multidimensional"})

    assert system.multidimensional_calculator is not original


def test_system_config_non_mode_change_does_not_reload(isolated_system):
    system = isolated_system
    original = system.multidimensional_calculator
    assert original is not None

    system.update_system_config({"currency_symbol": "USD"})

    # 未變更 system_mode 時不應重建計算器
    assert system.multidimensional_calculator is original
