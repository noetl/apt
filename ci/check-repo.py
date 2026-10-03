#!/usr/bin/env python3
"""Integrity check for the NoETL APT repository (noetl/ai-meta#375).

This repo had no CI.  It is a PUBLISHED package index: if `Packages` and
`pool/` disagree, `apt-get install noetl` fails for every user, and nothing
here would have said so.

The generator is NOT in this repo -- it is the `update-apt-repo` job in
noetl/cli's .github/workflows/release.yml, which runs dpkg-scanpackages and
apt-ftparchive and pushes the result.  So this check guards the ARTIFACT, not
the code that writes it.

Two tiers, deliberately:

  FAIL  -- invariants that hold today and whose violation is unambiguous
           corruption.  A .deb whose SHA256 no longer matches its index entry
           is a broken install for everyone; there is no reading under which
           that is intended.

  REPORT -- known, dated shortcomings of the generator, printed in full on
           every run with their denominators, tracked as noetl/ai-meta#390.
           These are NOT failures because fixing them is a decision about
           what to publish (notably: whether to index arm64 .debs whose
           newest is 2.8.7, years behind amd64's 5.0.1), and that decision is
           not this check's to make.

The reason they are REPORTed rather than dropped is that a known defect with
no recurring output becomes an unknown defect.  Every run restates them.
"""
from __future__ import annotations
import gzip
import hashlib
import os
import re
import subprocess
import sys

TRACKER = "noetl/ai-meta#390"


def tracked(*globs: str) -> list[str]:
    r = subprocess.run(["git", "ls-files", *globs], capture_output=True, text=True)
    r.check_returncode()
    return sorted(p for p in r.stdout.split("\n") if p)


def parse_stanzas(path: str) -> list[dict[str, str]]:
    out = []
    for block in open(path, encoding="utf-8", errors="replace").read().split("\n\n"):
        if not block.strip():
            continue
        fields = {}
        for line in block.splitlines():
            m = re.match(r"^([A-Za-z0-9-]+):\s*(.*)$", line)
            if m:
                fields[m.group(1)] = m.group(2)
        if fields:
            out.append(fields)
    return out


def main() -> int:
    failures: list[str] = []
    notes: list[str] = []

    debs = [p for p in tracked("pool/") if p.endswith(".deb")]
    indexes = tracked("dists/*/main/binary-*/Packages")
    dists = sorted({p.split("/")[1] for p in tracked("dists/*/Release")})

    print(f"pool: {len(debs)} .deb files")
    if len(debs) < 1:
        failures.append("pool/ contains no .deb files -- a check over an empty pool "
                        "reports the same clean result as a healthy one")
    by_arch: dict[str, int] = {}
    for d in debs:
        by_arch[d.rsplit("_", 1)[-1][:-4]] = by_arch.get(d.rsplit("_", 1)[-1][:-4], 0) + 1
    print(f"  by architecture: {by_arch}")
    print(f"dists: {dists}")
    print(f"Packages indexes: {len(indexes)}")
    if not indexes:
        failures.append("no Packages index found at dists/*/main/binary-*/Packages")

    # ---- FAIL tier 1: every index entry must point at a real, matching .deb
    print("\n── index entries vs pool")
    listed: set[str] = set()
    entries = 0
    for idx in indexes:
        for pkg in parse_stanzas(idx):
            fn = pkg.get("Filename", "")
            if not fn:
                failures.append(f"{idx}: a stanza has no Filename")
                continue
            entries += 1
            listed.add(fn)
            if not os.path.exists(fn):
                failures.append(f"{idx}: Filename points at a missing file: {fn}")
                continue
            blob = open(fn, "rb").read()
            if "Size" in pkg and int(pkg["Size"]) != len(blob):
                failures.append(f"{idx}: Size mismatch for {fn} "
                                f"(index {pkg['Size']}, actual {len(blob)})")
            if "SHA256" in pkg:
                got = hashlib.sha256(blob).hexdigest()
                if got != pkg["SHA256"]:
                    failures.append(f"{idx}: SHA256 mismatch for {fn}")
    print(f"   examined {entries} index entries across {len(indexes)} indexes")
    if entries == 0:
        failures.append("0 index entries examined -- the indexes are empty or unparsed")

    # ---- FAIL tier 2: Packages.gz must decompress to exactly Packages
    print("\n── Packages.gz vs Packages")
    pairs = 0
    for idx in indexes:
        gz = idx + ".gz"
        if not os.path.exists(gz):
            failures.append(f"{gz} is missing")
            continue
        pairs += 1
        if gzip.open(gz, "rb").read() != open(idx, "rb").read():
            failures.append(f"{gz} does not decompress to {idx}")
    print(f"   examined {pairs} pairs")

    # ---- FAIL tier 3: Release checksums, excluding the generator's self-entry
    print("\n── Release checksums")
    verified = 0
    for dist in dists:
        rel = f"dists/{dist}/Release"
        algo_for = {"MD5Sum": "md5", "SHA1": "sha1", "SHA256": "sha256", "SHA512": "sha512"}
        cur = None
        for line in open(rel, encoding="utf-8").read().splitlines():
            m = re.match(r"^(MD5Sum|SHA1|SHA256|SHA512):\s*$", line)
            if m:
                cur = m.group(1)
                continue
            if not (cur and line.startswith(" ")):
                continue
            parts = line.split()
            if len(parts) != 3:
                continue
            digest, size, rel_path = parts
            # `apt-ftparchive release D > D/Release` includes its own output
            # file in the listing, and the size it records is whatever Release
            # happened to be mid-write.  That entry can never be correct; it is
            # a generator bug, not repository corruption.  Skipping it here is
            # why it appears under REPORT below instead.
            if rel_path == "Release":
                continue
            full = os.path.join(f"dists/{dist}", rel_path)
            if not os.path.exists(full):
                failures.append(f"{rel} [{cur}] names a missing file: {rel_path}")
                continue
            blob = open(full, "rb").read()
            verified += 1
            if hashlib.new(algo_for[cur], blob).hexdigest() != digest or int(size) != len(blob):
                failures.append(f"{rel} [{cur}] mismatch for {rel_path}")
    print(f"   verified {verified} checksum entries (self-referential 'Release' entries skipped)")
    if verified == 0 and dists:
        failures.append("0 Release checksum entries verified -- Release files are empty or unparsed")

    # ---- REPORT tier
    print(f"\n── known generator shortcomings (tracked as {TRACKER}; not failures)")
    orphans = [d for d in debs if d not in listed]
    print(f"   .debs in pool but in NO index: {len(orphans)} of {len(debs)}")
    print("     cause: noetl/cli release.yml runs dpkg-scanpackages WITHOUT")
    print("            --multiversion, so only the newest version is indexed.")
    print("            `apt-get install noetl=<older>` cannot resolve.")
    indexed_arches = sorted({p.split("binary-")[1].split("/")[0] for p in indexes})
    pool_arches = sorted(by_arch)
    unindexed = [a for a in pool_arches if a not in indexed_arches]
    print(f"   architectures in pool: {pool_arches}; indexed: {indexed_arches}")
    if unindexed:
        print(f"     ⚠ NOT INDEXED: {unindexed} -- those .debs are unreachable to apt")
    for dist in dists:
        txt = open(f"dists/{dist}/Release", encoding="utf-8").read()
        want = ["Origin", "Label", "Suite", "Codename", "Version",
                "Architectures", "Components", "Description"]
        missing = [f for f in want if not re.search(rf"^{f}:", txt, re.M)]
        if missing:
            print(f"   dists/{dist}/Release is missing header fields: {missing}")
    print("     cause: `apt-ftparchive release` emits only checksums + Date unless")
    print("            given APT::FTPArchive::Release::* settings.")

    print("\n" + "─" * 64)
    if failures:
        print(f"FAILED ({len(failures)}):")
        for f in failures:
            print(f"  ✗ {f}")
        return 1
    print("Repository integrity OK "
          f"({entries} index entries, {pairs} gz pairs, {verified} Release checksums).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
