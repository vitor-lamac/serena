import logging
import os
import pathlib
import threading
from typing import Any

from solidlsp.language_servers.common import RuntimeDependency, RuntimeDependencyCollection
from solidlsp.ls import SolidLanguageServer
from solidlsp.ls_config import LanguageServerConfig
from solidlsp.lsp_protocol_handler.lsp_types import InitializeParams
from solidlsp.lsp_protocol_handler.server import ProcessLaunchInfo
from solidlsp.settings import SolidLSPSettings
from solidlsp.ls_utils import PathUtils

log = logging.getLogger(__name__)

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


class CobolLanguageServer(SolidLanguageServer):
    """
    Serena integration for COBOL using Eclipse Che4z COBOL Language Server.
    """

    def __init__(
        self,
        config: LanguageServerConfig,
        repository_root_path: str,
        solidlsp_settings: SolidLSPSettings,
    ):
        cmd = self._setup_runtime_dependencies(solidlsp_settings)

        super().__init__(
            config,
            repository_root_path,
            ProcessLaunchInfo(cmd=cmd, cwd=repository_root_path),
            "cobol",
            solidlsp_settings,
        )

        self.server_ready = threading.Event()

    # ------------------------------------------------------------------
    # Runtime dependencies
    # ------------------------------------------------------------------
    @classmethod
    def _setup_runtime_dependencies(cls, solidlsp_settings: SolidLSPSettings) -> list[str]:
        """
        Download and prepare the Che4z COBOL Language Server.
        """
        deps = RuntimeDependencyCollection(
            [
                RuntimeDependency(
                    id="che4z-cobol",
                    description="Eclipse Che4z COBOL Language Server",
                    url=CHE4Z_VSIX_URL,
                    archive_type="zip",
                    platform_id="any",
                )
            ]
        )

        ls_dir = pathlib.Path(cls.ls_resources_dir(solidlsp_settings)) / "cobol"
        ls_dir.mkdir(parents=True, exist_ok=True)

        vsix_path = ls_dir / CHE4Z_VSIX_FILENAME

        if not vsix_path.exists():
            log.info("Downloading Che4z COBOL language server VSIX")
            deps.install(str(ls_dir))

        jar_path = cls._find_server_jar(ls_dir)
        jar_dir = jar_path.parent

        classpath = str(jar_dir / "*")

        # 🔑 ENTRYPOINT CORRETO DO CHE4Z
        return [
            "java",
            "-cp",
            classpath,
            "org.eclipse.lsp.cobol.cli.CobolLanguageServerLauncher",
        ]

    @staticmethod
    def _find_server_jar(base_dir: pathlib.Path) -> pathlib.Path:
        """
        Locate the COBOL LSP server JAR inside the extracted VSIX.
        """
        jars = list(base_dir.rglob("*.jar"))
        if not jars:
            raise RuntimeError("COBOL LSP server JAR not found after extraction")

        # pick the largest JAR (actual server)
        return max(jars, key=lambda p: p.stat().st_size)

    # ------------------------------------------------------------------
    # LSP initialization
    # ------------------------------------------------------------------
    @staticmethod
    def _get_initialize_params(repository_absolute_path: str) -> InitializeParams:
        root_uri = PathUtils.path_to_uri(repository_absolute_path)
        return {
            "processId": os.getpid(),
            "rootUri": root_uri,
            "workspaceFolders": [
                {
                    "uri": root_uri,
                    "name": pathlib.Path(repository_absolute_path).name,
                }
            ],
            "capabilities": {},
        }

    def _start_server(self) -> None:
        """
        Start the COBOL language server and complete initialization.
        """

        def window_log_message(msg: dict) -> None:
            log.info(f"LSP[cobol]: {msg}")

        def do_nothing(_: Any) -> None:
            return

        self.server.on_notification("window/logMessage", window_log_message)
        self.server.on_notification("$/progress", do_nothing)
        self.server.on_notification("textDocument/publishDiagnostics", do_nothing)

        log.info("Starting COBOL language server process")
        self.server.start()

        init_params = self._get_initialize_params(self.repository_root_path)
        init_response = self.server.send.initialize(init_params)

        log.debug(f"COBOL initialize response: {init_response}")

        self.server.notify.initialized({})
        self.server_ready.set()
        self.completions_available.set()