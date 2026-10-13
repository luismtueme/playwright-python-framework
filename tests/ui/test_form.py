import pytest
from playwright.sync_api import Page, expect

from pages.form_page import FormPage


@pytest.fixture(autouse=True)
def _open(form_page: FormPage) -> None:
    form_page.open()


def test_has_the_expected_structure(page: Page) -> None:
    expect(page.get_by_role("main")).to_match_aria_snapshot(
        """
        - main:
          - heading "Example Application" [level=1]
          - region "Example action":
            - button "Run example action"
          - text: Example input
          - textbox "Example input"
          - button "Submit"
          - status
        """
    )


@pytest.mark.smoke
def test_shows_the_example_action_result(form_page: FormPage) -> None:
    form_page.run_example_action()
    expect(form_page.result).to_be_visible()


_CASES = [
    ("a valid value", "Sewer main inspection", "Form submitted successfully"),
    ("an empty value", "", "Please enter a value"),
    ("a value over 50 chars", "x" * 51, "Value must be 50 characters or fewer"),
]


@pytest.mark.parametrize(("name", "value", "message"), _CASES, ids=[case[0] for case in _CASES])
def test_submitting_shows_the_message(form_page: FormPage, name: str, value: str, message: str) -> None:
    form_page.submit(value)
    expect(form_page.message).to_have_text(message)
    assert name
