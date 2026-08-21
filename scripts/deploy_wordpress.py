#!/usr/bin/env python3
"""Deploy the md-new integration with exact backups and provision draft pages."""

from __future__ import annotations

import argparse
import hashlib
import json
import shlex
import subprocess
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = Path.home() / ".env"
PHP = "/usr/local/lsws/lsphp83/bin/php"
WP = "/usr/local/bin/wp"
EXPECTED_LOADER_SHA256 = "301f10e8411b24c20d6d5450b8e29bf01fde519733b5154a0cd893e7fa600e99"
THEME_FILES = (
    "loader.php",
    "inc/blog-rankings.php",
    "templates/blog-rankings-hub.php",
    "templates/blog-ranking-category.php",
    "assets/css/blog-rankings.css",
    "assets/js/blog-rankings.js",
)


def load_env() -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip("'\"")
    required = {"GL_SSH_COMMAND", "GL_FOLDER"}
    missing = required - values.keys()
    if missing:
        raise RuntimeError(f"Missing environment keys: {', '.join(sorted(missing))}")
    return values


def hardened_ssh(command: str, env: dict[str, str], capture: bool = True) -> subprocess.CompletedProcess[str]:
    base = shlex.split(env["GL_SSH_COMMAND"])
    if not base or Path(base[0]).name != "ssh":
        raise RuntimeError("GL_SSH_COMMAND must begin with ssh")
    extra = [
        "-o",
        "IdentitiesOnly=yes",
        "-o",
        "IdentityAgent=none",
        "-o",
        "BatchMode=yes",
        "-o",
        "ConnectTimeout=15",
        "-o",
        "StrictHostKeyChecking=accept-new",
    ]
    ssh = [*base[:-1], *extra, base[-1], command]
    return subprocess.run(ssh, capture_output=capture, text=True, timeout=240, check=False)


def scp_upload(local: Path, remote: str, env: dict[str, str]) -> None:
    base = shlex.split(env["GL_SSH_COMMAND"])
    target = base[-1]
    options: list[str] = []
    index = 1
    while index < len(base) - 1:
        option = base[index]
        if option == "-p" and index + 1 < len(base) - 1:
            options.extend(["-P", base[index + 1]])
            index += 2
            continue
        options.append(option)
        index += 1
    options.extend(
        [
            "-o",
            "IdentitiesOnly=yes",
            "-o",
            "IdentityAgent=none",
            "-o",
            "BatchMode=yes",
            "-o",
            "ConnectTimeout=15",
            "-o",
            "StrictHostKeyChecking=accept-new",
        ]
    )
    result = subprocess.run(
        ["scp", *options, str(local), f"{target}:{remote}"],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or f"Upload failed: {local}")


def wp_command(args: list[str], env: dict[str, str]) -> str:
    root = env["GL_FOLDER"]
    remote = shlex.join([PHP, WP, f"--path={root}", *args])
    result = hardened_ssh(remote, env)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    return result.stdout.strip()


def remote_run(command: str, env: dict[str, str]) -> str:
    result = hardened_ssh(command, env)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    return result.stdout.strip()


def install_server_cron(wp_root: str, backup: str, env: dict[str, str]) -> bool:
    """Install one idempotent hourly runner while preserving the prior crontab."""
    cron_line = (
        f"17 * * * * {PHP} {WP} --path={wp_root} cron event run --due-now --quiet "
        ">/dev/null 2>&1 # gatilab_blog_rankings_hourly"
    )
    previous = f"{backup}/crontab.before"
    command = (
        f"(crontab -l 2>/dev/null || true) > {shlex.quote(previous)} && "
        f"chmod 600 {shlex.quote(previous)} && "
        f"if ! grep -q gatilab_blog_rankings_hourly {shlex.quote(previous)}; then "
        f"{{ cat {shlex.quote(previous)}; printf '%s\\n' {shlex.quote(cron_line)}; }} | crontab -; fi && "
        "crontab -l 2>/dev/null | grep -q gatilab_blog_rankings_hourly"
    )
    remote_run(command, env)
    return True


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-ref", required=True, help="Immutable Git commit used for preview JSON")
    parser.add_argument(
        "--preserve-source",
        action="store_true",
        help="Keep the currently configured ranking feed instead of pinning it to --source-ref",
    )
    parser.add_argument(
        "--skip-provision",
        action="store_true",
        help="Deploy theme files without creating or modifying ranking pages",
    )
    parser.add_argument("--output", type=Path, default=ROOT / "build" / "wordpress-deploy.json")
    args = parser.parse_args()

    if not all(character in "0123456789abcdef" for character in args.source_ref.lower()) or len(args.source_ref) != 40:
        raise RuntimeError("--source-ref must be a full 40-character Git commit")

    env = load_env()
    wp_root = env["GL_FOLDER"].rstrip("/")
    theme = f"{wp_root}/wp-content/themes/md-new"
    active = json.loads(wp_command(["theme", "list", "--status=active", "--fields=name,status,version", "--format=json"], env))
    if len(active) != 1 or active[0].get("name") != "md-new":
        raise RuntimeError("md-new is not the single active Gatilab theme")

    current_loader = remote_run(f"sha256sum {shlex.quote(theme + '/loader.php')} | cut -d' ' -f1", env)
    desired_loader = hashlib.sha256((ROOT / "wordpress" / "md-new" / "loader.php").read_bytes()).hexdigest()
    if current_loader not in {EXPECTED_LOADER_SHA256, desired_loader}:
        raise RuntimeError(f"Active loader.php changed since inspection: {current_loader}")

    stamp = time.strftime("%Y%m%d-%H%M%S")
    remote_temp = remote_run("mktemp -d /tmp/gatilab-blog-rankings.XXXXXX", env)
    backup = f"{wp_root}/.codex-backups/blog-rankings/{stamp}"
    remote_run(f"mkdir -p {shlex.quote(backup)} && chmod 700 {shlex.quote(backup)}", env)

    upload_map: list[tuple[Path, str]] = []
    for relative in THEME_FILES:
        upload_map.append((ROOT / "wordpress" / "md-new" / relative, relative))
    for image in sorted((ROOT / "wordpress" / "md-new" / "assets" / "images" / "blog-rankings").glob("*.svg")):
        upload_map.append((image, f"assets/images/blog-rankings/{image.name}"))
    upload_map.append((ROOT / "wordpress" / "provision-pages.php", "provision-pages.php"))

    for local, relative in upload_map:
        if not local.is_file():
            raise RuntimeError(f"Missing deployment file: {local}")
        remote_file = f"{remote_temp}/{relative}"
        remote_run(f"mkdir -p {shlex.quote(str(Path(remote_file).parent))}", env)
        scp_upload(local, remote_file, env)

    php_files = [relative for _, relative in upload_map if relative.endswith(".php")]
    for relative in php_files:
        remote_run(f"{shlex.quote(PHP)} -l {shlex.quote(remote_temp + '/' + relative)}", env)

    install_commands = []
    for _, relative in upload_map:
        if relative == "provision-pages.php":
            continue
        destination = f"{theme}/{relative}"
        destination_dir = str(Path(destination).parent)
        backup_file = f"{backup}/{relative}"
        install_commands.extend(
            [
                f"mkdir -p {shlex.quote(destination_dir)} {shlex.quote(str(Path(backup_file).parent))}",
                f"if [ -f {shlex.quote(destination)} ]; then cp -p {shlex.quote(destination)} {shlex.quote(backup_file)}; fi",
                f"install -m 0644 {shlex.quote(remote_temp + '/' + relative)} {shlex.quote(destination)}",
            ]
        )
    remote_run(" && ".join(install_commands), env)

    try:
        if args.preserve_source:
            source_base = wp_command(["option", "get", "gatilab_br_source_base"], env)
            if not source_base.startswith("https://"):
                raise RuntimeError("The existing ranking feed is not a valid HTTPS URL")
        else:
            source_base = f"https://raw.githubusercontent.com/wpgaurav/blog-rankings/{args.source_ref}/dist/web/latest/"
            wp_command(["option", "update", "gatilab_br_source_base", source_base, "--autoload=no"], env)

        if args.skip_provision:
            provision = {"skipped": True, "reason": "published-theme-update"}
        else:
            provision = json.loads(wp_command(["eval-file", f"{remote_temp}/provision-pages.php"], env))

        refresh = json.loads(wp_command(["eval", "$result = gatilab_br_refresh_all(); echo wp_json_encode($result);"], env))
        server_cron = install_server_cron(wp_root, backup, env)
        wp_command(["cache", "flush"], env)

        verification = json.loads(
            wp_command(
                [
                    "eval",
                    "$out=array('active'=>get_stylesheet(),'source'=>get_option('gatilab_br_source_base'),'technology'=>get_option('gatilab_br_payload_technology'),'marketing'=>get_option('gatilab_br_payload_marketing-seo')); echo wp_json_encode(array('active'=>$out['active'],'source'=>$out['source'],'technology_edition'=>$out['technology']['payload']['edition']??null,'marketing_edition'=>$out['marketing']['payload']['edition']??null));",
                ],
                env,
            )
        )
    except Exception:
        remote_run(f"rm -r {shlex.quote(remote_temp)}", env)
        raise

    remote_run(f"rm -r {shlex.quote(remote_temp)}", env)
    report = {
        "deployed_at": stamp,
        "source_ref": args.source_ref,
        "source_base": source_base,
        "backup": backup,
        "active_theme": active,
        "provision": provision,
        "refresh": refresh,
        "server_cron": server_cron,
        "verification": verification,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
