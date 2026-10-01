"""Keep Linux pre-exec parent memory out of worker peak measurements."""
import json
from pathlib import Path
import subprocess
import sys
import unittest


@unittest.skipUnless(sys.platform.startswith("linux") and Path("/proc/self/status").exists(),
                     "Linux VmHWM regression")
class MemoryTests(unittest.TestCase):
    def test_fork_parent_high_water_does_not_inflate_exec_worker(self):
        child = ('import json,resource; from pdftoepub.convert import peak_memory_mib; '
                 'print(json.dumps({"worker":peak_memory_mib(),'
                 '"inherited":resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024}))')
        parent = ("import os,sys; allocation=bytearray(128*1024*1024); pid=os.fork(); "
                  f"os.execv(sys.executable,[sys.executable,'-c',{child!r}]) if pid==0 else os.waitpid(pid,0)")
        result = subprocess.run([sys.executable, "-c", parent], capture_output=True, text=True,
                                cwd=Path(__file__).resolve().parents[1], check=True, timeout=30)
        values = json.loads(result.stdout.strip())
        self.assertGreater(values["inherited"], 128)
        self.assertLess(values["worker"], values["inherited"] - 60)
