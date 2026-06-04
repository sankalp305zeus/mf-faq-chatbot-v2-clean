"""Shared pytest configuration."""


def pytest_addoption(parser):
    parser.addoption(
        "--run-integration",
        action="store_true",
        default=False,
        help="Run tests that require a live ChromaDB index.",
    )
