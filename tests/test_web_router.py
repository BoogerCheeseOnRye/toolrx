#!/usr/bin/env python3
"""Parity test: the JS router must match the Python router exactly.

The GitHub Pages dashboard runs toolrx/web/router.js in the browser. If the two
implementations drift, the live page silently stops agreeing with the server,
so this test routes a spread of queries through both and compares the tool,
confidence, margin, and extracted arguments.
"""

import json
import os
import shutil
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
NODE = shutil.which("node")

QUERIES = [
    "add five and seven",
    "sum 12 30 and 7",
    "read my notes.txt",
    "list the files in the project folder",
    "cat all files",
    "how much memory is free on this machine",
    "show me the disk usage",
    "what is the uptime",
    "show network interfaces",
    "ping 8.8.8.8",
    "write hello to notes.txt",
    "run the memory tracker every 10 seconds for 2 minutes",
    "clear all modules",
    "bring the lab down",
]

JS = r"""
const fs=require('fs');
global.self=global;
eval(fs.readFileSync(process.argv[1],'utf8'));
eval(fs.readFileSync(process.argv[2],'utf8'));
const raw=JSON.parse(fs.readFileSync(process.argv[3],'utf8'));
const model=self.toolrxRouter.load(raw);
const qs=JSON.parse(process.argv[4]);
console.log(JSON.stringify(qs.map(q=>{
  const r=self.toolrxRouter.route(q,model,[]);
  return {tool:r.tool,confidence:r.confidence,margin:r.margin,args:r.args};
})));
"""


@unittest.skipUnless(NODE, "node is not installed")
class WebRouterParityTest(unittest.TestCase):
    def test_matches_python_router(self):
        sys.path.insert(0, os.path.join(ROOT, "toolrx"))
        import router

        model = router.load(os.path.join(ROOT, "toolrx", "micro_model.json"))
        proc = subprocess.run(
            [NODE, "-e", JS,
             os.path.join(ROOT, "toolrx", "web", "blake2b.js"),
             os.path.join(ROOT, "toolrx", "web", "router.js"),
             os.path.join(ROOT, "toolrx", "micro_model.json"),
             json.dumps(QUERIES)],
            capture_output=True, text=True, timeout=120,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr[-2000:])
        js = json.loads(proc.stdout)
        self.assertEqual(len(js), len(QUERIES))

        for q, got in zip(QUERIES, js):
            want = router.route(q, model)
            self.assertEqual(got["tool"], want["tool"], q)
            self.assertAlmostEqual(got["confidence"], want["confidence"], places=9, msg=q)
            self.assertAlmostEqual(got["margin"], want["margin"], places=9, msg=q)
            self.assertEqual(got["args"], want["args"], q)


if __name__ == "__main__":
    unittest.main(verbosity=2)
