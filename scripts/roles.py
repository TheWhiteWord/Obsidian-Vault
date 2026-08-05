"""
Vault role operations — the daily surface for agents (P6, §4.5).

The --role verb family mutates profile-vault bindings on a live vault.
Growth-protocol.md (manager skill) is the interactive reference; every
subcommand supports --dry-run. Grants are the truth: the role derives from
the live roles.yaml block; unbind comments the block out (deny-by-default,
re-bindable) and removes the SOUL block; the vault must always keep a
manager (transfer hands it off).

    python3 scripts/roles.py --vault <path> --role bind PROFILE [--new] [--manager] [--domain NAME] [--config FILE]
    python3 scripts/roles.py --vault <path> --role unbind PROFILE [--domain NAME]
    python3 scripts/roles.py --vault <path> --role transfer PROFILE --to SUCCESSOR [--domain NAME]
    python3 scripts/roles.py --vault <path> --role list
Environment:
    HERMES_HOME   override the Hermes home (default: ~/.hermes).
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from vault_ops import role_bind, role_unbind, role_transfer, role_list


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--vault", help="Vault root path (required)")
    ap.add_argument("--role", choices=["bind", "unbind", "transfer", "list"],
                    help="Role mutation action (\u00a74.5)")
    ap.add_argument("profile", nargs="?", metavar="PROFILE",
                    help="Target profile (bind/unbind/transfer)")
    ap.add_argument("--to", metavar="NAME",
                    help="Transfer target profile (--role transfer)")
    ap.add_argument("--new", action="store_true",
                    help="(bind) create the profile first")
    ap.add_argument("--manager", action="store_true",
                    help="(bind) bind as manager (mutually exclusive with "
                         "--domain \u2014 managers hold no content grants)")
    ap.add_argument("--domain", metavar="NAME",
                    help="(bind/unbind/transfer) operate on work/<NAME>/**")
    ap.add_argument("--config", metavar="FILE",
                    help="(bind --domain) prepared .vault/config.yaml "
                         "(default: minimal stub)")
    ap.add_argument("--dry-run", action="store_true",
                    help="Print actions without performing them")
    args = ap.parse_args()

    if not args.role:
        ap.print_help()
        return 1
    if not args.vault:
        ap.error("--vault is required")

    hermes_home = Path(os.environ.get("HERMES_HOME", "~/.hermes")).expanduser()
    vault_root = Path(args.vault).expanduser()
    if args.role == "list":
        role_list(hermes_home, vault_root)
    elif args.role == "bind":
        if not args.profile:
            ap.error("--role bind requires PROFILE")
        role_bind(hermes_home, vault_root, args.profile,
                  new=args.new, manager_role=args.manager,
                  domain=args.domain or "", config_file=args.config or "",
                  dry_run=args.dry_run)
    elif args.role == "unbind":
        if not args.profile:
            ap.error("--role unbind requires PROFILE")
        role_unbind(hermes_home, vault_root, args.profile,
                    domain=args.domain or "", dry_run=args.dry_run)
    else:  # transfer
        if not args.profile or not args.to:
            ap.error("--role transfer requires PROFILE and --to")
        role_transfer(hermes_home, vault_root, args.profile, args.to,
                      domain=args.domain or "", dry_run=args.dry_run)
    return 0

if __name__ == "__main__":
    sys.exit(main())
