"""Keeps the cache-v1 release and manifest.json in sync.

incoming/<game path>  -> uploaded to the release, manifest entry added/updated, file removed from incoming/
DELETE (env)          -> comma/newline separated game paths removed from the release and manifest
RESCAN=true (env)     -> release files uploaded by hand on the website get their size/CRC32 written to the manifest
"""
import datetime, json, os, re, shutil, subprocess, sys, tempfile, zlib

REPO = os.environ["GITHUB_REPOSITORY"]
TAG = "cache-v1"
MANIFEST = "manifest.json"
INCOMING = "incoming"
RAW_BASE = f"https://raw.githubusercontent.com/{REPO}/main/"
DL_BASE = f"https://github.com/{REPO}/releases/download/{TAG}/"


def asset_name(path):
    return re.sub(r"[^A-Za-z0-9._-]", "_", path.replace("/", "__"))


def crc_of(file):
    crc = 0
    with open(file, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            crc = zlib.crc32(chunk, crc)
    return f"{crc:08X}"


def gh(*args, capture=False):
    r = subprocess.run(["gh", *args], check=True, text=True, capture_output=capture)
    return r.stdout if capture else None


def release_assets():
    out = gh("api", "--paginate", f"repos/{REPO}/releases/tags/{TAG}", "--jq",
             ".assets[] | [.id, .name, .size] | @tsv", capture=True)
    assets = {}
    for line in out.splitlines():
        aid, name, size = line.split("\t")
        assets[name] = (int(aid), int(size))
    return assets


def main():
    with open(MANIFEST) as fh:
        manifest = json.load(fh)
    entries = {f["path"]: f for f in manifest["files"]}
    changed = []

    # 1. files dropped into incoming/
    if os.path.isdir(INCOMING):
        for root, _, files in os.walk(INCOMING):
            for fn in files:
                src = os.path.join(root, fn)
                path = os.path.relpath(src, INCOMING).replace(os.sep, "/")
                if fn == ".gitkeep":
                    continue
                name = asset_name(path)
                with tempfile.TemporaryDirectory() as tmp:
                    dst = os.path.join(tmp, name)
                    shutil.copyfile(src, dst)
                    gh("release", "upload", TAG, dst, "-R", REPO, "--clobber")
                entries[path] = {"path": path, "size": os.path.getsize(src), "crc32": crc_of(src),
                                 "url": DL_BASE + name, "asset": name}
                changed.append(f"updated {path}")

    assets = release_assets()

    # 2. deletions
    for path in re.split(r"[,\n]", os.environ.get("DELETE", "")):
        path = path.strip().strip("/")
        if not path:
            continue
        name = entries.get(path, {}).get("asset") or asset_name(path)
        if name in assets:
            gh("release", "delete-asset", TAG, name, "-R", REPO, "--yes")
        if entries.pop(path, None) is not None or name in assets:
            changed.append(f"deleted {path}")
        else:
            print(f"::warning::{path} is not in the manifest or the release")

    # 3. hand-uploaded release files (new asset id or unknown name)
    if os.environ.get("RESCAN", "").lower() == "true":
        assets = release_assets()
        by_name = {e.get("asset") or asset_name(p): p for p, e in entries.items()}
        for name, (aid, size) in assets.items():
            path = by_name.get(name) or name.replace("__", "/")
            e = entries.get(path)
            if e and e.get("assetId") == aid and e.get("size") == size:
                continue
            with tempfile.TemporaryDirectory() as tmp:
                gh("release", "download", TAG, "-R", REPO, "-p", name, "-D", tmp)
                f = os.path.join(tmp, name)
                entries[path] = {"path": path, "size": os.path.getsize(f), "crc32": crc_of(f),
                                 "url": DL_BASE + name, "asset": name}
            changed.append(f"rescanned {path}")

    # asset ids let the next rescan notice a same-size replacement
    assets = release_assets()
    for e in entries.values():
        a = assets.get(e.get("asset") or asset_name(e["path"]))
        if a:
            e["assetId"] = a[0]
        else:
            print(f"::warning::{e['path']} has no file in the release")

    if not changed and all("assetId" in e for e in entries.values()) and manifest["files"] == sorted(entries.values(), key=lambda e: e["path"]):
        print("Nothing to do")
        return
    files = sorted(entries.values(), key=lambda e: e["path"])
    manifest.update({
        "generatedAt": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "baseUrl": RAW_BASE,
        "fileCount": len(files),
        "totalBytes": sum(f["size"] for f in files),
        "files": files,
    })
    with open(MANIFEST, "w") as fh:
        json.dump(manifest, fh, indent=2)
        fh.write("\n")
    print("\n".join(changed) or "manifest refreshed")
    with open(os.environ.get("GITHUB_OUTPUT", os.devnull), "a") as out:
        out.write("summary=" + "; ".join(changed)[:200] + "\n")


if __name__ == "__main__":
    sys.exit(main())
