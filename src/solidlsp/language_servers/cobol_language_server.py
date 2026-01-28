import os
from pathlib import Path
from typing import List

from solidlsp.language_servers.base import SolidLanguageServer
from solidlsp.dependency_providers import (
    LanguageServerDependencyProviderSinglePath
)
from solidlsp.utils import PathUtils


# ============================================================================
# Che4z COBOL Language Server configuration
# ============================================================================

CHE4Z_VERSION = "2.4.3"

CHE4Z_VSIX_URL = (
    "https://github.com/eclipse-che4z/"
    "che-che4z-lsp-for-cobol/"
    f"releases/download/{CHE4Z_VERSION}/"
    f"cobol-language-support-{CHE4Z_VERSION}.vsix"
)

CHE4Z_VSIX_FILENAME = f"cobol-language-support-{CHE4Z_VERSION}.vsix"


# ============================================================================
# COBOL Language Server
# ============================================================================

class CobolLanguageServer(SolidLanguageServer):
    """
    Serena integration for COBOL using Eclipse Che4z COBOL Language Server.

    This implementation:
      - Downloads the Che4z VSIX (Java-based)
      - Extracts it into Serena's LS resources directory
      - Locates the actual LSP server JAR dynamically
      - Launches the server via stdio
    """

    # ----------------------------------------------------------------------
    # Dependency Provider
    # ----------------------------------------------------------------------
    class DependencyProvider(LanguageServerDependencyProviderSinglePath):
        """
        Handles download, extraction and launch command creation
        for the Che4z COBOL Language Server.
        """

        def _get_or_install_core_dependency(self) -> Path:
            """
            Downloads and extracts the Che4z VSIX if not already present.

            Returns:
                Path: Root directory of the extracted VSIX.
            """
            return self._download_if_needed(
                url=CHE4Z_VSIX_URL,
                filename=CHE4Z_VSIX_FILENAME,
                extract=True
            )

        # ------------------------------------------------------------------
        # JAR discovery helpers
        # ------------------------------------------------------------------
        def _find_server_jar(self, core_path: Path) -> Path:
            """
            Locate the COBOL LSP server JAR inside the extracted VSIX.

            Strategy:
              1. Prefer jars under extension/server/
              2. If multiple, pick the largest (usually the executable server)
              3. Fallback to searching the entire VSIX tree

            Raises:
                RuntimeError: If no suitable JAR is found.
            """
            server_dir = core_path / "extension" / "server"

            if server_dir.exists():
                jars = list(server_dir.rglob("*.jar"))
                if jars:
                    return max(jars, key=lambda p: p.stat().st_size)

            # Fallback: search everywhere
            all_jars = list(core_path.rglob("*.jar"))
            if not all_jars:
                raise RuntimeError(
                    "COBOL LSP JAR not found inside extracted Che4z VSIX"
                )

            return max(all_jars, key=lambda p: p.stat().st_size)

        # ------------------------------------------------------------------
        # Launch command
        # ------------------------------------------------------------------
        def _create_launch_command(self, core_path: Path) -> List[str]:
            """
            Build the command used to start the COBOL language server.
            """
            jar_path = self._find_server_jar(core_path)

            return [
                "java",
                "-jar",
                str(jar_path),
                "--stdio"
            ]

    # ----------------------------------------------------------------------
    # SolidLanguageServer hooks
    # ----------------------------------------------------------------------
    def _create_dependency_provider(self):
        """
        Instantiate the DependencyProvider for this server.
        """
        return self.DependencyProvider(
            self._custom_settings,
            self._ls_resources_dir
        )

    def _get_initialize_params(self):
        """
        Provide language-server-specific initialization parameters.
        """
        root_uri = PathUtils.path_to_uri(self.repository_root_path)

        return {
            "processId": os.getpid(),
            "rootUri": root_uri,
            "workspaceFolders": [
                {
                    "uri": root_uri,
                    "name": "cobol-workspace"
                }
            ],
            "capabilities": {}
        }
