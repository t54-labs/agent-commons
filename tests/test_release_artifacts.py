from __future__ import annotations

import email.parser
import unittest

from scripts import check_release_artifacts


class ReleaseArtifactChecksTests(unittest.TestCase):
    def test_distribution_metadata_accepts_canonical_project_urls(self) -> None:
        project_urls = "\n".join(
            f"Project-URL: {name}, {url}"
            for name, url in check_release_artifacts.EXPECTED_PROJECT_URLS.items()
        )
        metadata = email.parser.Parser().parsestr(
            "\n".join(
                (
                    "Name: agent-commons",
                    "Version: 0.3.1.dev0",
                    "License-Expression: Apache-2.0",
                    project_urls,
                    "",
                )
            )
        )

        failures = check_release_artifacts.validate_core_metadata(
            metadata,
            "0.3.1.dev0",
            "fixture.whl",
        )

        self.assertEqual([], failures)

    def test_distribution_metadata_reports_missing_project_url(self) -> None:
        metadata = email.parser.Parser().parsestr(
            "\n".join(
                (
                    "Name: agent-commons",
                    "Version: 0.3.1.dev0",
                    "License-Expression: Apache-2.0",
                    "Project-URL: Homepage, https://github.com/t54-labs/agent-commons",
                    "",
                )
            )
        )

        failures = check_release_artifacts.validate_core_metadata(
            metadata,
            "0.3.1.dev0",
            "fixture.whl",
        )

        self.assertTrue(any("missing Project-URL labels" in failure for failure in failures))


if __name__ == "__main__":
    unittest.main()
