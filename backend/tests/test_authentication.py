from app.services.authentication import create_session, delete_session, get_session, role_for_password


def test_existing_edit_password_roles(monkeypatch):
    monkeypatch.setenv("MNH_ENV", "development")
    monkeypatch.delenv("MNH_ADMIN_PASSWORD", raising=False)
    monkeypatch.delenv("MNH_LECTURER_PASSWORD", raising=False)
    assert role_for_password('rep') == 'administrator'
    assert role_for_password('staff') == 'lecturer'
    assert role_for_password('incorrect') is None


def test_session_lifecycle():
    token = create_session('administrator')
    assert get_session(token)['role'] == 'administrator'
    delete_session(token)
    assert get_session(token) is None


def test_management_roles_can_be_configured(monkeypatch):
    monkeypatch.setenv('MNH_HOD_PASSWORD', 'hod-secret')
    monkeypatch.setenv('MNH_COORDINATOR_PASSWORD', 'coordinator-secret')
    monkeypatch.setenv('MNH_ED_PASSWORD', 'dean-secret')
    assert role_for_password('hod-secret') == 'hod'
    assert role_for_password('coordinator-secret') == 'coordinator'
    assert role_for_password('dean-secret') == 'executive_dean'


def test_development_passwords_are_disabled_in_production(monkeypatch):
    monkeypatch.setenv("MNH_ENV", "production")
    monkeypatch.delenv("MNH_ADMIN_PASSWORD", raising=False)
    monkeypatch.delenv("MNH_LECTURER_PASSWORD", raising=False)

    assert role_for_password("rep") is None
    assert role_for_password("staff") is None


def test_production_passwords_must_be_explicitly_configured(monkeypatch):
    monkeypatch.setenv("MNH_ENV", "production")
    monkeypatch.setenv("MNH_ADMIN_PASSWORD", "a-unique-admin-secret")
    monkeypatch.setenv("MNH_LECTURER_PASSWORD", "a-unique-staff-secret")

    assert role_for_password("a-unique-admin-secret") == "administrator"
    assert role_for_password("a-unique-staff-secret") == "lecturer"
