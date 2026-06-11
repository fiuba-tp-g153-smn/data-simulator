"""Filesystem emission: hardlink with copy fallback, partial-file safe."""

import logging
import os
import shutil
from pathlib import Path
from typing import Callable

logger = logging.getLogger(__name__)


class FileEmitter:
    """Creates destination files from seed files without ever mutating the seed.

    Copies land under a ``.part`` name and are renamed into place so the
    producer's globs never see a half-written file. Hardlinks are atomic.
    """

    def __init__(self, link_mode: str = "hardlink") -> None:
        self._force_copy = link_mode == "copy"

    def emit_file(self, src: Path, dst: Path) -> bool:
        """Place ``src`` at ``dst``. Returns False if ``dst`` already exists."""
        if dst.exists():
            logger.debug("Skipping existing %s", dst)
            return False
        dst.parent.mkdir(parents=True, exist_ok=True)
        if self._force_copy:
            self.copy_file(src, dst)
            return True
        self._link_or_copy(src, dst)
        return True

    def copy_file(self, src: Path, dst: Path) -> None:
        part = dst.with_name(dst.name + ".part")
        shutil.copyfile(src, part)
        os.replace(part, dst)

    def emit_copy_with(self, src: Path, dst: Path, mutate: Callable[[Path], None]) -> bool:
        """Copy ``src``, apply ``mutate`` to the partial file, rename into place."""
        if dst.exists():
            logger.debug("Skipping existing %s", dst)
            return False
        dst.parent.mkdir(parents=True, exist_ok=True)
        part = dst.with_name(dst.name + ".part")
        shutil.copyfile(src, part)
        mutate(part)
        os.replace(part, dst)
        return True

    def _link_or_copy(self, src: Path, dst: Path) -> None:
        try:
            os.link(src, dst)
        except OSError as exc:
            logger.warning("Hardlink %s -> %s failed (%s); copying", src, dst, exc)
            self.copy_file(src, dst)
