# SSH Key Loading for Controller Activities

## Why This Matters

Ansible cannot type a passphrase during a run. If a key is protected (and it should be), it must be loaded into the SSH agent first. The `-t` flag sets a lifetime so the key automatically unloads after the window closes, limiting exposure if you walk away from the terminal.

## Key Inventory

| Key                              | Purpose                           | Used by                    |
| -------------------------------- | --------------------------------- | -------------------------- |
| `gradus-raw-initial-id_ed25519`  | Onboarding raw nodes as `initial` | Ingress playbooks          |
| `gradus-dev-admin-id_ed25519`    | Human admin work on dev nodes     | Manual SSH, ad-hoc Ansible |
| `gradus-dev-deploy-id_ed25519`   | Automated deployment to dev       | Converge playbooks         |
| `gradus-stage-admin-id_ed25519`  | Human admin work on stage nodes   | Manual SSH, ad-hoc Ansible |
| `gradus-stage-deploy-id_ed25519` | Automated deployment to stage     | Converge playbooks         |
| `gradus-prod-admin-id_ed25519`   | Human admin work on prod nodes    | Manual SSH, ad-hoc Ansible |
| `gradus-prod-deploy-id_ed25519`  | Automated deployment to prod      | Converge playbooks         |

## Loading Keys

### Dev

```sh
ssh-add -t 1h ~/.ssh/gradus-raw-initial-id_ed25519 # onboarding
ssh-add -t 1h ~/.ssh/gradus-dev-admin-id_ed25519 # human admin work
ssh-add -t 1h ~/.ssh/gradus-dev-deploy-id_ed25519 # before the deploy
```

### Stage

```sh
ssh-add -t 30m ~/.ssh/gradus-stage-admin-id_ed25519
ssh-add -t 30m ~/.ssh/gradus-stage-deploy-id_ed25519
```

### Prod

```sh
ssh-add -t 15m ~/.ssh/gradus-prod-admin-id_ed25519
ssh-add -t 15m ~/.ssh/gradus-prod-deploy-id_ed25519
```

## Lifetime Guidance

| Environment | Suggested `-t` | Rationale                                         |
| ----------- | -------------- | ------------------------------------------------- |
| Dev         | `1h`           | Long enough for iterative development and testing |
| Stage       | `30m`          | Shorter window; stage work is more targeted       |
| Prod        | `15m`          | Minimum window for the task; auto-expires quickly |

The principle: shorter windows for higher environments. If the task takes longer than 15 minutes in prod, reload the key. The inconvenience is the feature.

## Checking What's Loaded

```sh
ssh-add -l # list fingerprints of loaded keys
```

Run this before any Ansible command to confirm the right key is loaded. If you see keys you don't expect, the agent may be holding stale keys from a previous session.

## Removing Keys

```sh
ssh-add -d ~/.ssh/gradus-prod-deploy-id_ed25519 # remove one key
ssh-add -D # remove all keys
```

Remove prod keys immediately after finishing, even if the lifetime hasn't expired. Don't wait for the timer.

## Common Pitfalls

**Key spraying.** If multiple keys are loaded, SSH offers each one in sequence until one works. Too many attempts trips `MaxAuthTries` on the target and gets the controller banned by fail2ban. The inventory sets `IdentitiesOnly=yes` to prevent this for Ansible, but manual SSH should use `-i` and `-o IdentitiesOnly=yes`:

```sh
ssh -i ~/.ssh/gradus-dev-admin-id_ed25519 -o IdentitiesOnly=yes initial@<node-ip>
```

**gnome-keyring interference.** On GNOME/Cinnamon desktops, `gnome-keyring-daemon` may intercept `ssh-add` and store keys in its own agent instead of OpenSSH's. Check which agent owns the socket:

```sh
echo "$SSH_AUTH_SOCK" # a keyring path means gnome-keyring owns it
```

If the path contains `keyring`, keys may not behave as expected with `-t` lifetimes. See the onboarding guide's troubleshooting section for disabling gnome-keyring's SSH component.

**Forgot to load.** Ansible fails with "Permission denied (publickey)" and no obvious cause. Check `ssh-add -l` first — it's almost always a missing key.

**Loaded the wrong environment's key.** If you load prod keys for a dev task and they share the same `IdentitiesOnly` group, SSH may try the prod key against dev nodes. Load only what you need for the current task.