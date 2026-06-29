from __future__ import annotations

import sys
import types

from ai.eval.actual_rag_core_base import *
from ai.eval.actual_rag_core_xlsx import *
from ai.eval.actual_rag_core_quality import *
from ai.eval.actual_rag_cli import *
from ai.eval import actual_rag_core_base as _base
from ai.eval import actual_rag_core_xlsx as _xlsx
from ai.eval import actual_rag_core_quality as _quality
from ai.eval import actual_rag_runner as _runner
from ai.eval import actual_rag_cli as _cli
from ai.eval.actual_rag_cli import (
    _synchronize_actual_rag_namespaces as _synchronize_actual_rag_namespaces,
)
from ai.eval.actual_rag_cli import build_parser as _cli_build_parser
from ai.eval.actual_rag_cli import main as _cli_main


_synchronize_actual_rag_namespaces()
for _module in (_base, _xlsx, _quality, _runner, _cli):
    globals().update(
        {
            _name: _value
            for _name, _value in _module.__dict__.items()
            if not (_name.startswith("__") and _name.endswith("__"))
        }
    )


def build_parser():
    return _cli_build_parser()


def main(argv=None) -> int:
    return _cli_main(argv)


class _ActualRagFacade(types.ModuleType):
    def __setattr__(self, name, value):
        super().__setattr__(name, value)
        for module in (_base, _xlsx, _quality, _runner, _cli):
            if hasattr(module, name):
                setattr(module, name, value)


sys.modules[__name__].__class__ = _ActualRagFacade


if __name__ == "__main__":
    raise SystemExit(main())
