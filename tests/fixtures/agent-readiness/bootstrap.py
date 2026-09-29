"""Import the installed wheel; never add core source to the import path."""
import importlib.metadata as md
from pathlib import Path
import sys
import agent_core
if Path(agent_core.__file__).resolve() != Path(md.distribution('agent-core').locate_file('agent_core/__init__.py')).resolve():
    raise RuntimeError('installed_core_import_mismatch')
if not Path(agent_core.__file__).resolve().is_relative_to(Path(sys.prefix).resolve()):
    raise RuntimeError('core_outside_project_environment')
